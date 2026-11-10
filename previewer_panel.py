#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_panel.py – Version 1.8.0

Panel core: file-type dispatch, preview widgets and configuration;
inherits the toolbar and renderer mixins and paints the panel
background.
"""

import os
import struct
import sys
import tempfile
import traceback
import zipfile

import gi

gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    _,
    dbg,
    set_debug_log,
    debug_log_active,
    debug_log_cleanup,
    PANEL_WIDTH, PANEL_MIN_WIDTH,
    query_file_info,
    pick_icon,
    human_size,
    pack_hint,
    build_scaled_image,
    build_text_view,
    apply_font_size_css,
    effective_text_font,
    system_font_size_px,
)
from previewer_render_media import MediaRendererMixin, _ensure_gst
from previewer_render_docs import (
    DocsRendererMixin, HAVE_POPPLER, _OFFICE_EXTS,
)
from previewer_render_text import (
    TextRendererMixin, _FONT_SAMPLE_TEXT,
    _markdown_to_pango, _epub_data, _mobi_data, _font_faces,
)
from previewer_toolbar import PreviewToolbarMixin

# → REF PAN-F44-1
HAVE_GTKSOURCE = False
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAVE_GTKSOURCE = True
except Exception as e:
    dbg("panel/module-level: suppressed: %s" % e)

# K11: one-shot flag – the undershoot CSS goes to the screen
# ONCE per process, not once per Nemo window.
_K11_STATE = {"screen_css": False}

# F47: the MIME database types .theme and backup endings as
# x-theme/x-trash, not text – whitelisted; binary .swp stays out.
_TEXT_EXTRAS = {
    '.py', '.sh', '.bash', '.zsh', '.js', '.ts', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.csv', '.log', '.md', '.rst',
    '.css', '.html', '.xml', '.patch', '.diff', '.desktop', '.service',
    '.gitignore', '.nemo_action', '.pyw', '.lua', '.pl', '.rb', '.go',
    '.rs', '.c', '.h', '.cpp', '.hpp', '.java', '.sql', '.tex',
    '.theme', '.old', '.bak', '.orig',
}

# B10: known-binary MIME types – the last-resort sniffer never
# runs on them; they skip straight to the generic preview.
_SNIFF_BINARY_MIMES = {
    "application/zip", "application/x-tar", "application/gzip",
    "application/x-bzip2", "application/x-xz",
    "application/x-7z-compressed", "application/x-rar",
    "application/x-executable", "application/x-sharedlib",
    "application/x-ms-dos-executable",
}

# B11: SQLite dispatch gate – the .db ending alone proves nothing.
_SQLITE_MAGIC = b"SQLite format 3\x00"

# F12: configuration of the preview column – GLib-native INI
# format, no extra dependency; created on first save.
CONF_DIR = os.path.expanduser("~/.config/nemo-previewer")
CONF_FILE = os.path.join(CONF_DIR, "nemo-previewer.conf")

# F2: heavy renderers wait this many ms of selection quiet before
# they start – fast browsing never fires a render it drops anyway.
_RENDER_QUIET_MS = 400
# → REF PAN-B8-1
try:
    _KEYFILE_CLS = GLib.KeyFile
except AttributeError:
    _KEYFILE_CLS = getattr(GLib, "Keyfile", None)
try:
    _KEYFILE_FLAGS_NONE = GLib.KeyFileFlags.NONE
except AttributeError:
    _KEYFILE_FLAGS_NONE = 0


# → REF PAN-DOC-1
def _sniff_is_text(path, probe=4096):
    try:
        with open(path, "rb") as fh:
            head = fh.read(probe)
    except Exception:
        return False
    if not head or b"\x00" in head:
        return False
    ctrl = sum(1 for b in head if b < 9 or 14 <= b <= 31 or b == 127)
    if ctrl / len(head) >= 0.05:
        return False
    high = sum(1 for b in head if b >= 0x80)
    if high:
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            if high / len(head) >= 0.30:
                return False
    return True


def _is_sqlite(path):
    # B11: dispatch gate – text based database files (e.g. workman.db)
    # must fall through to the sniffer instead of dead-ending here.
    try:
        with open(path, "rb") as fh:
            return fh.read(16) == _SQLITE_MAGIC
    except Exception:
        return False


# → REF PAN-DOC-2
def _silhouette(theme, sname, fg, size=16):
    try:
        info = theme.lookup_icon(sname, size, 0)
        if info is None:
            return None
        pb = info.load_icon()
        if pb is None or not pb.get_has_alpha():
            # Without an alpha channel the icon is a solid slab –
            # the redraw would come back colored; load unchanged.
            return None
        w, h = pb.get_width(), pb.get_height()
        src = pb.get_pixels()
        rs = pb.get_rowstride()
        nc = pb.get_n_channels()
        r = int(round(fg.red * 255))
        g = int(round(fg.green * 255))
        b = int(round(fg.blue * 255))
        out = bytearray(w * h * 4)
        op = 0
        for y in range(h):
            sp = y * rs
            for x in range(w):
                out[op] = r
                out[op + 1] = g
                out[op + 2] = b
                out[op + 3] = src[sp + x * nc + 3]
                op += 4
        return GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(bytes(out)),
            GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
    except Exception:
        return None

# ================================ Panel ====================================

# → REF PAN-DOC-3
class PreviewPanel(PreviewToolbarMixin, MediaRendererMixin, DocsRendererMixin,
                   TextRendererMixin, Gtk.Box):

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(PANEL_MIN_WIDTH, -1)
        # 0.31.3 (F46): style class background – the panel paints
        # its empty areas itself, else they stay black (→ REF PAN-BG-1).
        self.get_style_context().add_class("background")
        # 0.31.4 (F46 II): GtkBox paints NO CSS background itself –
        # the panel draws the themed background first in draw (→ REF PAN-BG-1).
        self.connect("draw", self._on_panel_draw)
        # 0.31.5 (F46 III): flag against dbg flooding in draw – the
        # painter logs only on change, per widget (→ REF PAN-BG-2).
        self._bg_dbg_keys = {}
        # 0.31.7 (F46 V): CSS rule for the scroll areas – the
        # provider is created in the folder render (→ REF PAN-BG-2).
        self._surface_provider = None
        # 0.31.8 (F46 VI): CSS dbg line only on color change.
        self._surface_css_color = None

        self._window = window
        self._path = None
        self._names = []
        self._playbin = None
        self._progress_timer = 0
        self._render_width = 0
        # 0.17.0: track the column height for the image height cap
        # (max 60% of the column, user request).
        self._render_height = 0
        # Scalable previews (R3): every image carries its parameters
        # as its own dict entry (see _scaled_image) – no clashes.
        self._scale_items = []
        # F38: 40% info area of the image split (set when
        # _pack_image_capped splits the column for an image preview).
        self._image_info_box = None
        # Background conversion for office documents (LibreOffice → PDF)
        self._office_job = None
        self._office_failed = set()
        # F77: pending print conversion (office print button).
        self._print_job = None
        # 0.9.1: remember panel teardown – a running LibreOffice
        # child-watch must not render after that.
        self._destroyed = False
        # Multi-page PDF preview: source pixbufs per page + display images
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_scaled = None
        self._pdf_box = None
        self._pdf_scroll = None
        self._pdf_last_w = 0
        # → REF PAN-R2-1
        self._pdf_gen = 0
        # K12: generation of the incremental resize passes.
        self._pdf_scale_gen = 0
        # Image rescales run generation-guarded in idle steps.
        self._img_scale_gen = 0
        # F14: page indicator of the PDF preview + total page count
        self._pdf_page_label = None
        self._pdf_count = 0
        # F68/F11: live waterfall items (set to a LIST by
        # _render_font) – re-rendered on column resize.
        self._font_wf = None
        # → REF PAN-F12-1
        self._conf_show_at_start = True
        # F48: folder preview with contents list is the mandatory
        # default; the settings switch toggles the plain icon (→ REF PAN-FOLDER-2).
        self._conf_folder_contents = True
        # F12: waterfall sample text of the font preview – default
        # is the classic sentence, editable in the settings (→ REF TXT-FONT-2).
        self._conf_font_sample_text = _(_FONT_SAMPLE_TEXT)
        # F24: line numbers in the plain text preview – default ON
        # (user request), toggleable in the settings ("Text files").
        self._conf_text_linenumbers = True
        # F44: syntax highlighting as a SETTING – "Text files"
        # section, default on; applies live via _last_textish.
        self._conf_text_syntax = True
        # F25: extra line spacing in text previews – default 0 (the
        # normal look), configurable in the settings, applied live.
        self._conf_text_line_spacing = 0
        # F69: font sizes in px – default = the detected system font
        # size; 0 stays selectable as the explicit theme font.
        sys_px = system_font_size_px()
        self._conf_text_font_size = sys_px
        self._conf_meta_font_size = sys_px
        # F12 part 3: document cap configurable – limit PDF/office
        # previews or show all; default matches the old hard cap.
        self._conf_doc_page_limit = True
        self._conf_doc_max_pages = 20
        # F65: debug logging – default off; mirrors dbg lines into
        # the log file under XDG_STATE_HOME.
        self._conf_debug_log = False
        # F12 part 3: marker – is the CURRENT preview a PDF/office
        # page view? Cap changes then apply immediately.
        self._last_docview = False
        # Marker: is the CURRENT preview TextView-based, i.e. the
        # line-number toggle is cheap to apply? The settings toggle
        # then re-renders only those previews.
        self._last_textish = False
        # Start width: default PANEL_WIDTH (350 px, 0.41.0); the
        # settings spin button is the only place that changes it.
        self._panel_width = PANEL_WIDTH
        # F66: aux column state - the reusable second column is
        # built at the end of __init__ (→ REF PAN-AUX-1).
        self._aux_key = None
        self._aux_refresh = None
        self._aux_trigger = None
        self._aux_width = 0
        # F66 III: inner divider drag state (1.2.1, → REF PAN-AUX-2).
        self._aux_pos = 0
        self._aux_manual_width = 0
        self._aux_handle = None
        self._aux_syncing = False
        # 1.2.4: outer divider hook state (PAN-AUX-2).
        self._aux_outer_pos = 0
        self._aux_outer_hold = False
        self._aux_outer_hid = None
        # 1.2.5: one-shot handle calibration hook (PAN-AUX-2).
        self._aux_calib_hid = None
        # F25: pending quiet re-render of the spacing spin.
        self._spacing_render_id = None
        # B12: pending quiet re-render of the font size spin.
        self._textsize_render_id = None
        # F2: pending debounced heavy render (selection quiet).
        self._pending_render_id = None
        self._config_load()
        # F69: initial font size rules – later saves reload them.
        apply_font_size_css(self._conf_text_font_size,
                            self._conf_meta_font_size)
        # F65b: stale debug logs (older than 7 days) vanish at
        # every panel start – even with logging off.
        debug_log_cleanup()

        # --- Header (F35: controls only – icon, name, type, size
        # and date already sit in the Nemo list) ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)

        # F65: red recording dot – visible exactly while debug
        # logging is active (live).
        self._rec_dot = Gtk.Image.new_from_icon_name(
            pick_icon(("media-record-symbolic",), "media-record"),
            Gtk.IconSize.BUTTON)
        self._rec_dot.set_name("previewer-rec-dot")
        self._rec_dot.set_no_show_all(True)
        self._rec_dot.set_tooltip_text(_("Debug logging is active"))
        try:
            css = Gtk.CssProvider()
            css.load_from_data(
                b"#previewer-rec-dot { color: #e01b24; }")
            self._rec_dot.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            dbg("panel/rec dot css: suppressed: %s" % e)
        header.pack_start(self._rec_dot, False, False, 0)
        self._update_rec_dot()

        # Reset-width button (F63, user wish): jumps the preview
        # column back to the CONFIGURED width with a single click.
        btn_width = Gtk.Button.new_from_icon_name(
            pick_icon(("sidebar-collapse-right-symbolic",
                       "arrow-right-symbolic", "go-next-symbolic",
                       "arrow-right"),
                      "go-next"),
            Gtk.IconSize.BUTTON)
        btn_width.set_tooltip_text(
            _("Reset preview column to configured width"))
        btn_width.set_relief(Gtk.ReliefStyle.NONE)
        btn_width.connect("clicked", self._on_reset_width_clicked)
        header.pack_end(btn_width, False, False, 0)

        # Open button (F40: system run icon). The hide button moved
        # to Nemo's title bar as the preview toggle (→ REF ENT-TOGGLE-1).
        btn_open = Gtk.Button.new_from_icon_name(
            pick_icon(("document-edit-symbolic", "document-edit",
                       "edit-symbolic", "text-editor-symbolic"),
                      "document-open-symbolic"),
            Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text(_("Open with the default application"))
        btn_open.set_relief(Gtk.ReliefStyle.NONE)
        btn_open.connect("clicked", self._on_open_clicked)
        header.pack_end(btn_open, False, False, 0)

        self.pack_start(header, False, False, 0)
        self._separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self._separator, False, False, 0)

        # --- Preview area ---
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._content.set_border_width(8)
        self.pack_start(self._content, True, True, 0)
        # The preview resizes when the panel width (Gtk.Paned
        # divider) changes: debounced re-render on width changes.
        self._content.connect("size-allocate",
                              self._on_content_size_allocate)
        # K11: GTK paints dashed undershoot hints at the edges of
        # scroll areas (theme-dependent) – hide them preview-wide.
        # → REF PAN-K11-1
        self.set_name("previewer-panel")
        if not _K11_STATE["screen_css"]:
            _K11_STATE["screen_css"] = True
            try:
                css = Gtk.CssProvider()
                css.load_from_data(
                    b"#previewer-panel undershoot, "
                    b"#previewer-panel .undershoot "
                    b"{ background-image: none; "
                    b"background-color: transparent; }")
                Gtk.StyleContext.add_provider_for_screen(
                    self.get_screen(), css,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            except Exception as e:
                dbg("panel/undershoot css: suppressed: %s" % e)


        # --- F19: toolbar at the bottom of the preview column ---
        # Construction, settings button, CSS and shortcut (Ctrl+Alt+P)
        # live in the toolbar module (F29).
        self._build_toolbar(window)

        self._show_placeholder()

        # F66: horizontal shell [aux | preview] - since 1.2.1 a
        # Gtk.Paned: its divider drags the column width (PAN-AUX-2).
        self._aux_shell = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL)
        self._aux_column = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0)
        # Same name as the panel: the K11 undershoot CSS covers the
        # aux scroll areas too; the painter mirrors the panel look.
        self._aux_column.set_name("previewer-panel")
        self._aux_column.get_style_context().add_class("background")
        self._aux_column.connect("draw", self._on_aux_draw)
        self._aux_column.connect("key-press-event", self._on_aux_key)
        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)
        self._aux_title_label = Gtk.Label(label="")
        self._aux_title_label.set_halign(Gtk.Align.START)
        self._aux_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        btn_close = Gtk.Button.new_from_icon_name(
            pick_icon(("window-close-symbolic", "window-close"),
                      "window-close"),
            Gtk.IconSize.BUTTON)
        btn_close.set_tooltip_text(_("Close"))
        btn_close.set_relief(Gtk.ReliefStyle.NONE)
        btn_close.connect("clicked", lambda *a: self._close_aux())
        header.pack_start(self._aux_title_label, True, True, 0)
        header.pack_start(btn_close, False, False, 0)
        self._aux_column.pack_start(header, False, False, 0)
        self._aux_column.pack_start(Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        self._aux_scroll = Gtk.ScrolledWindow()
        self._aux_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                                    Gtk.PolicyType.AUTOMATIC)
        self._aux_column.pack_start(self._aux_scroll, True, True, 0)
        # Plain show/hide instead of a Revealer: its animated width
        # reporting derailed the synchronous paned moves (1.1.1).
        # no_show_all keeps Nemo's window-level show_all from
        # pulling the hidden column into view (K17/K18 family).
        self._aux_column.show_all()
        self._aux_column.set_no_show_all(True)
        self._aux_column.hide()
        # 1.2.4: shrink False + the 320 px request give the inner
        # divider a hard floor - the preview can never swallow
        # the column (deploy report on 1.2.3).
        self._aux_column.set_size_request(320, -1)
        self._aux_shell.pack1(self._aux_column, False, False)
        self._aux_shell.pack2(self, True, False)
        self._aux_shell.connect("notify::position",
                                self._on_aux_dragged)

        # B3: on panel teardown, cleanly stop playback and timer
        self.connect("destroy", self._on_panel_destroy)

    def _on_panel_draw(self, widget, cr):
        # 0.31.5 (F46 III): GtkBox never calls gtk_render_background
        # itself – this hook paints the background before all children,
        # additionally on the scroll window of the folder list (→ REF PAN-BG-2).
        self._paint_background(widget, cr)
        return False

    # → REF PAN-DOC-4
    def _bg_content_ctx(self):
        target = None

        def _visit(w):
            nonlocal target
            if target is not None:
                return
            if isinstance(w, (Gtk.ListBox, Gtk.TextView)):
                target = w
            elif isinstance(w, Gtk.Container):
                w.foreach(_visit)

        try:
            content = self._content
            if content is not None:
                content.foreach(_visit)
        except Exception as e:
            dbg("panel/_bg_content_ctx: suppressed: %s" % e)
        try:
            return target.get_style_context()
        except Exception:
            return None

    # → REF PAN-DOC-5
    def _derived_base(self):
        fg = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        return 0.12 if (fg.red + fg.green + fg.blue) / 3.0 > 0.5 \
            else 0.92

    # → REF PAN-DOC-6
    def _paint_background(self, widget, cr):
        cands = [("Panel", self.get_style_context())]
        try:
            top = self.get_toplevel()
            if top is not None and top is not self:
                cands.append(("Toplevel", top.get_style_context()))
        except Exception as e:
            dbg("panel/_paint_background: suppressed: %s" % e)
        content_ctx = self._bg_content_ctx()
        if content_ctx is not None:
            cands.append(("Content", content_ctx))
        ctx, used, report = None, None, []
        for name, cctx in cands:
            try:
                rgba = cctx.get_background_color(
                    Gtk.StateFlags.NORMAL)
            except Exception:
                rgba = None
            report.append("%s=%s" % (
                name, rgba.to_string() if rgba is not None else "-"))
            if ctx is None and rgba is not None \
                    and rgba.alpha > 0.0:
                ctx, used = cctx, name
        # 0.31.7 (F46 V): log the widget context's own color – shows
        # what the theme paints there itself (→ REF PAN-BG-2).
        try:
            eigen = widget.get_style_context().get_background_color(
                Gtk.StateFlags.NORMAL)
            report.append("own=%s" % eigen.to_string())
        except Exception as e:
            dbg("panel/_paint_background: suppressed: %s" % e)
        w, h = widget.get_allocated_width(), \
            widget.get_allocated_height()
        if ctx is not None:
            Gtk.render_background(ctx, cr, 0, 0, w, h)
        elif content_ctx is not None:
            # No color resolved – but the slab paints visibly: its
            # context may render a gradient get_background_color hides.
            Gtk.render_background(content_ctx, cr, 0, 0, w, h)
            used = "content-unchecked"
        else:
            # Last resort: base area derived from the fg color –
            # contrast-correct (0.38.1, F46 XI): bright fg → dark base.
            base = self._derived_base()
            cr.set_source_rgba(base, base, base, 1.0)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            used = "Vordergrund-abgeleitet"
        wname = type(widget).__name__
        # 0.31.8 (F46 VI): flag per widget – a single value let the
        # dbg lines of the four widgets oscillate endlessly.
        key = "%s|%s" % (used, ";".join(report))
        if self._bg_dbg_keys.get(wname) != key:
            self._bg_dbg_keys[wname] = key
            dbg("Panel bg (%s): source=%s – candidates: %s"
                % (wname, used, "; ".join(report)))

    # → REF PAN-DOC-7
    def _on_scroll_realized(self, sc):
        try:
            for bar in (sc.get_vscrollbar(), sc.get_hscrollbar()):
                if bar is not None:
                    bar.connect("draw", self._on_panel_draw)
                    if self._surface_provider is not None:
                        bar.get_style_context().add_provider(
                            self._surface_provider,
                            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            dbg("panel/_on_scroll_realized: suppressed: %s" % e)

    # → REF PAN-DOC-8
    def _apply_surface_css(self, scroll):
        try:
            color = None
            try:
                rgba = self.get_style_context().get_background_color(
                    Gtk.StateFlags.NORMAL)
                if rgba is not None and rgba.alpha > 0.0:
                    color = rgba.to_string()
            except Exception as e:
                dbg("panel/_apply_surface_css: suppressed: %s" % e)
            if color is None:
                # 0.38.1 (F46 XI): fallback is fg-derived now – the
                # old hardcoded rgb(56,56,56) shone dark in light mode.
                base = self._derived_base()
                color = "rgb(%d,%d,%d)" % (
                    round(base * 255), round(base * 255),
                    round(base * 255))
            css = (
                ".pvw-surface,"
                ".pvw-surface junction,"
                ".pvw-surface viewport,"
                ".pvw-surface scrollbar,"
                ".pvw-surface scrollbar trough,"
                ".pvw-surface scrollbar undershoot"
                " { background-color: %s; }" % color).encode("utf-8")
            prov = Gtk.CssProvider()
            prov.load_from_data(css)
            scroll.get_style_context().add_class("pvw-surface")
            scroll.get_style_context().add_provider(
                prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._surface_provider = prov
            for ctx in self._surface_css_contexts(scroll):
                ctx.add_provider(
                    prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            # 0.31.8 (F46 VI): print only on color change – the
            # line would otherwise repeat on every folder selection.
            if self._surface_css_color != color:
                self._surface_css_color = color
                dbg("Panel bg CSS: rule for scroll areas installed "
                    "(color %s)" % color)
        except Exception as e:
            dbg("Panel bg CSS: failed – %s" % e)

    # → REF PAN-DOC-9
    def _surface_css_contexts(self, scroll):
        ctxs = []
        try:
            vp = scroll.get_child()
            if vp is not None:
                ctxs.append(vp.get_style_context())
        except Exception as e:
            dbg("panel/_surface_css_contexts: suppressed: %s" % e)
        try:
            for bar in (scroll.get_vscrollbar(),
                        scroll.get_hscrollbar()):
                if bar is not None:
                    ctxs.append(bar.get_style_context())
        except Exception as e:
            dbg("panel/_surface_css_contexts: suppressed: %s" % e)
        return ctxs


    # ------------------------------ Selection ------------------------------

    # → REF PAN-DOC-10
    def set_selection(self, names, dir_path):
        # Always cleanly stop the audio player when something changes
        self._stop_playback()

        if not names:
            self._path = None
            self._names = []
            self._cancel_pending_render()
            self._show_placeholder()
            # F74: no selection – the x-bit button hides as well.
            self._update_xbit_button()
            # F77: the print button follows the same rule.
            self._update_print_button()
            return

        self._names = list(names)
        first = names[0]
        if dir_path:
            self._path = os.path.join(dir_path, first)
        else:
            self._path = first
        # F2: a queued debounced render never survives a new
        # selection – heavy formats re-arm, light ones render now.
        self._cancel_pending_render()
        if self._is_heavy(self._path):
            self._pending_render_id = GLib.timeout_add(
                _RENDER_QUIET_MS, self._on_pending_render)
        else:
            self._render()

    # → REF PAN-DOC-33
    def _cancel_pending_render(self):
        # F2: drop a queued debounced render – the selection moved
        # on, so its result would be thrown away anyway.
        if self._pending_render_id is not None:
            GLib.source_remove(self._pending_render_id)
            self._pending_render_id = None

    def _on_pending_render(self):
        # F2: fires once after selection quiet; returning False
        # removes the timeout source by itself.
        self._pending_render_id = None
        if self._path:
            self._render()
        return False

    def _is_heavy(self, path):
        # F2: heavy formats – PDF/Office parsing and GStreamer
        # pipelines; _OFFICE_EXTS is a set, hence tuple().
        lower = path.lower()
        if lower.endswith((".pdf",) + tuple(_OFFICE_EXTS)):
            return True
        mime, _size, _mtime = query_file_info(path)
        return (mime.startswith(("audio/", "video/")) or
                lower.endswith((".mp3", ".flac", ".ogg", ".opus",
                                ".m4a", ".wav", ".wma")))

    # ------------------------------ Rendering ------------------------------

    def _clear_content(self):
        for child in list(self._content.get_children()):
            self._content.remove(child)
        # Release scale sources (memory of the full resolution)
        self._scale_items = []
        # F38: release the info area of the last image preview.
        self._image_info_box = None
        # likewise the PDF page pixbufs; bump the render generation
        # so running idle feed steps (R2) abort instead of painting.
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_scaled = None
        self._pdf_box = None
        self._pdf_scroll = None
        self._pdf_last_w = 0
        self._pdf_page_label = None
        self._pdf_count = 0
        self._pdf_gen += 1
        # K12: incremental resize passes abort as well.
        self._pdf_scale_gen += 1
        # F68: drop the font waterfall state as well.
        self._font_wf = None
        # F24: was the just torn-down preview a text preview?
        self._last_textish = False
        # F12 part 3: was it a document page view (PDF/office)?
        self._last_docview = False
        # F66 II: reset the media "more" title - a non-media
        # selection must not refresh the tags column (PAN-AUX-3).
        self._tags_title = None

    def _show_placeholder(self):
        # F35: the former header is gone – the placeholder text in
        # the content area suffices as a status message.
        self._clear_content()
        # Nemo logo, centered (horizontal and vertical) in the column
        logo = Gtk.Image()
        logo_name = "folder"
        try:
            theme = Gtk.IconTheme.get_default()
            if theme.has_icon("nemo"):
                logo_name = "nemo"
        except Exception as e:
            dbg("panel/_show_placeholder: suppressed: %s" % e)
        try:
            logo.set_from_icon_name(logo_name, Gtk.IconSize.DIALOG)
            logo.set_pixel_size(96)
        except Exception:
            logo.set_from_icon_name("folder", Gtk.IconSize.DIALOG)
        lbl = Gtk.Label(label=_("Select a file\nto see a preview."))
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.pack_start(logo, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        self._content.pack_start(box, True, True, 0)
        self._content.show_all()

    # → REF PAN-DOC-11
    def _render(self):
        try:
            self._render_inner()
        except Exception:
            dbg("Render error for %r:" % self._path)
            traceback.print_exc()
            try:
                self._render_generic()
            except Exception as e:
                dbg("panel/_render: suppressed: %s" % e)
        self._content.show_all()
        # F74: keep the x-bit button in sync with the previewed file.
        self._update_xbit_button()
        # F77: keep the print button in sync as well.
        self._update_print_button()
        # F66: keep an open aux view in sync with the new file.
        self._aux_on_render()

    def _render_inner(self):
        path = self._path
        self._clear_content()
        # 0.31.4 (F46 II): reset the content area's outer margin to
        # 8 px per render – edgeless renderers zero it themselves (→ REF PAN-BG-1).
        self._content.set_border_width(8)

        # K6: multi-selection shows no preview – the column
        # only shows the count (→ REF PAN-K6-1).
        if len(self._names) > 1:
            extra = Gtk.Label(label=_("%d items selected")
                              % len(self._names))
            extra.get_style_context().add_class("dim-label")
            extra.set_halign(Gtk.Align.CENTER)
            extra.set_valign(Gtk.Align.CENTER)
            self._content.pack_start(extra, True, True, 0)
            dbg("panel/_render_inner: K6: %d items selected, no preview" %
                len(self._names))
            return

        if not path or not os.path.exists(path):
            # F35: the name sits in the Nemo list – only the warning
            # hint remains, in the content area.
            pack_hint(self._content, _("(file not found)"))
            return

        mime, size, mtime = query_file_info(path)
        is_dir = os.path.isdir(path)

        # F35: the former header fill (icon, name, type · size ·
        # modified date) is gone – the Nemo list shows all of that
        # next to the preview column.

        uri = GLib.filename_to_uri(path)
        lower = path.lower()

        # --- render by type ---
        if is_dir:
            # F48: the contents list is the mandatory default; the
            # settings switch toggles the plain folder icon (→ REF PAN-FOLDER-2).
            if self._conf_folder_contents:
                self._render_folder(path)
            else:
                self._render_generic()
        elif mime == "image/svg+xml" or lower.endswith(".svg"):
            self._render_svg(path)
        elif (mime.startswith("image/") or
              mime == "application/x-xpixmap" or
              lower.endswith((".heic", ".heif", ".hif"))):
            # F42: HEIC endings as a backup in case shared-mime-info
            # does not know the type (yet).
            self._render_image(path)
        elif mime == "application/pdf" or lower.endswith(".pdf"):
            if HAVE_POPPLER:
                self._render_pdf(path)
            else:
                pack_hint(self._content, _("PDF preview not available – "
                           "install package gir1.2-poppler-0.18."))
                self._render_generic()
        elif mime.startswith("audio/") or lower.endswith((".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".wma")):
            if _ensure_gst():
                self._render_audio(path, uri)
            else:
                pack_hint(self._content, _("Audio preview not available – "
                           "install package gir1.2-gst-plugins-base-1.0."))
                self._render_generic()
        elif mime.startswith("video/"):
            if _ensure_gst():
                self._render_video(path, uri)
            else:
                self._render_generic()
        elif lower.endswith((".md", ".markdown")):
            self._render_markdown(path)
        elif lower.endswith(".eml") or mime == "message/rfc822":
            self._render_eml(path)
        elif (lower.endswith((".vcf", ".vcard", ".ldif", ".contact"))
              or mime == "text/vcard"):
            # F7: contact card formats – vCard, LDIF, Windows
            # contact (renderers in the text module).
            # → REF PAN-VCARD-1
            self._render_vcard(path)
        elif lower.endswith(".ics") or mime == "text/calendar":
            # F52: iCalendar files – event cards in the text module.
            self._render_ics(path)
        elif mime == "application/epub+zip" or lower.endswith(".epub"):
            self._render_epub(path)
        elif (mime in ("application/x-fictionbook+xml",
                       "application/x-fictionbook")
              or lower.endswith(".fb2")):
            self._render_fb2(path)
        elif (mime == "application/x-mobipocket-ebook"
              or lower.endswith((".mobi", ".prc", ".azw", ".azw3"))):
            self._render_mobi(path)
        # F60: package formats (DEB, RPM, Pacman) – text module.
        elif (mime in ("application/vnd.debian.binary-package",
                       "application/x-debian-package",
                       "application/x-deb")
              or lower.endswith(".deb")):
            self._render_deb(path)
        elif (mime in ("application/x-rpm",
                       "application/x-redhat-package-manager")
              or lower.endswith(".rpm")):
            self._render_rpm(path)
        elif lower.endswith((".pkg.tar.xz", ".pkg.tar.zst")):
            self._render_pkg(path)
        elif (mime in ("text/csv", "text/comma-separated-values",
                       "application/csv")
              or lower.endswith((".csv", ".tsv", ".tab"))):
            self._render_csv(path)
        # F6/B11: .db and friends only count as SQLite when the
        # magic matches – text based .db files reach the sniffer.
        # → REF PAN-SQL-1
        elif ((mime in ("application/vnd.sqlite3", "application/x-sqlite3")
               or lower.endswith((".db", ".sqlite", ".sqlite3")))
              and _is_sqlite(path)):
            self._render_sqlite(path)
        elif (mime in ("font/ttf", "font/otf", "font/collection",
                       "font/woff",
                       "application/x-font-ttf", "application/x-font-otf",
                       "application/vnd.ms-opentype")
              or lower.endswith((".ttf", ".otf", ".ttc", ".woff"))):
            self._render_font(path)
        elif mime.startswith("text/") or os.path.splitext(lower)[1] in _TEXT_EXTRAS:
            self._render_text(path)
        elif os.path.splitext(lower)[1] in _OFFICE_EXTS:
            self._render_office(path)
        elif mime not in _SNIFF_BINARY_MIMES and _sniff_is_text(path):
            # F23/F47/B10: the type rater reads only the NAME – for
            # unclassified files (no extension, opaque types, unknown
            # endings like .pub/.crt/.csr/.pref) the sniffer decides
            # by CONTENT as last resort; binary mimes stay out via
            # _SNIFF_BINARY_MIMES (→ REF PAN-B10-1).
            dbg("panel/_render_inner: B10 sniff: %s -> text (mime %s)"
                % (os.path.basename(path), mime))
            self._render_text(path)
        else:
            self._render_generic()

    # --- individual renderers --------------------------------------------------

    # → REF PAN-DOC-12
    def _on_content_size_allocate(self, widget, allocation):
        try:
            width = allocation.width
            height = allocation.height
            # 0.17.0: height changes (window resize) also trigger a
            # live adjustment – the height cap follows the column.
            if (height > 100
                    and abs(height - self._render_height) >= 12):
                self._render_height = height
                self._apply_scale()
            if abs(width - self._render_width) < 12:
                return
            self._render_width = width
            self._apply_scale()
            self._apply_pdf_scale()
            # F68: the font waterfall re-renders at the new width.
            self._apply_font_scale()
        except Exception as e:
            dbg("panel/_on_content_size_allocate: suppressed: %s" % e)

    # → REF PAN-DOC-13
    def _scaled_image(self, src, max_h, upscale=False, keep_height=False,
                      max_upscale=1.0, frac_h=None):
        img, scroll, item = build_scaled_image(
            src, max_h, upscale, keep_height, max_upscale, frac_h)
        if self._scale_items is None:
            self._scale_items = []
        self._scale_items.append(item)
        self._apply_scale()
        return scroll

    # → REF PAN-DOC-14
    def _apply_scale(self):
        # R3: the rescale follows the pdf pattern (K12) – generation
        # guard + one item per idle step, never a sync backlog.
        self._img_scale_gen += 1
        GLib.idle_add(self._scale_step, 0, self._img_scale_gen)

    # → REF PAN-DOC-14
    def _scale_step(self, i, gen):
        # Stale pass – a newer resize or a clear ran.
        if gen != self._img_scale_gen:
            return False
        items = self._scale_items or []
        if i >= len(items):
            return False
        try:
            self._scale_item(items[i])
        except Exception as e:
            dbg("panel/_scale_step: suppressed: %s" % e)
        GLib.idle_add(self._scale_step, i + 1, gen)
        return False

    # → REF PAN-DOC-15
    def _scale_item(self, item):
        src = item["src"]
        if src is None:
            return
        sw, sh = src.get_width(), src.get_height()
        if sw <= 0 or sh <= 0:
            return
        maxh = item["maxh"]
        if item["frac"]:
            # 0.17.0: height cap – fraction of the COLUMN
            # HEIGHT (image preview: 60%), live on resize.
            maxh = min(maxh, max(1, int(item["frac"] *
                                        self._preview_height())))
        target = self._preview_width()
        f = float(target) / sw
        if f > 1.0:
            if item["upscale"]:
                # Upscale, but limited: small sources
                # (office thumbnails) else blur.
                f = min(f, item["maxup"])
            else:
                f = 1.0      # do not blur up small images
        if f * sh > maxh:
            f = float(maxh) / sh
        w = max(1, int(sw * f))
        h = max(1, int(sh * f))
        # 0.17.0: also compare HEIGHT – the cap can change
        # at constant width (window taller/shorter).
        if (abs(w - item["lastw"]) < 4
                and abs(h - item.get("lasth", -1)) < 4):
            return
        item["lastw"] = w
        item["lasth"] = h
        # Interpolate better when upscaling
        interp = (GdkPixbuf.InterpType.HYPER if f > 1.0
                  else GdkPixbuf.InterpType.BILINEAR)
        item["img"].set_from_pixbuf(src.scale_simple(w, h, interp))
        # → REF PAN-BILD-1
        if item["keeph"]:
            item["scroll"].set_min_content_height(h)
            item["scroll"].get_vadjustment().set_value(0)

    # → REF PAN-DOC-16
    def _preview_width(self):
        try:
            w = self._content.get_allocated_width()
            if w > 40:
                # Subtract the padding (8 px border per side)
                return max(PANEL_MIN_WIDTH - 20, w - 16)
        except Exception as e:
            dbg("panel/_preview_width: suppressed: %s" % e)
        return PANEL_WIDTH - 40

    # → REF PAN-DOC-17
    def _preview_height(self):
        try:
            h = self._content.get_allocated_height()
            if h > 100:
                return h
        except Exception as e:
            dbg("panel/_preview_height: suppressed: %s" % e)
        return 600

    # → REF PAN-DOC-18
    def _source_language(self, path):
        try:
            return GtkSource.LanguageManager.get_default().guess_language(
                os.path.basename(path), None)
        except Exception:
            return None

    # → REF PAN-DOC-19
    def _source_scheme(self):
        try:
            mgr = GtkSource.StyleSchemeManager.get_default()
            ids = set(mgr.get_scheme_ids())
            dark = False
            try:
                settings = Gtk.Settings.get_default()
                name = (settings.get_property("gtk-theme-name")
                        or "").lower()
                dark = ("dark" in name
                        or bool(settings.get_property(
                            "gtk-application-prefer-dark-theme")))
            except Exception as e:
                dbg("panel/_source_scheme: suppressed: %s" % e)
            if dark:
                for sid in ("oblivion", "solarized-dark"):
                    if sid in ids:
                        return mgr.get_scheme(sid)
            if "classic" in ids:
                return mgr.get_scheme("classic")
        except Exception as e:
            dbg("panel/_source_scheme: suppressed: %s" % e)
        return None

    # → REF PAN-DOC-20
    def _text_view(self, text, font="9", markup=None, linenumbers=False,
                   source_path=None):
        # F44: highlight source code – only if the GtkSourceView
        # binding exists, a language is detected AND text_syntax is on.
        view = None
        if (source_path is not None and HAVE_GTKSOURCE
                and self._conf_text_syntax):
            lang = self._source_language(source_path)
            if lang is not None:
                try:
                    view = GtkSource.View()
                    sbuf = GtkSource.Buffer()
                    sbuf.set_language(lang)
                    sbuf.set_style_scheme(self._source_scheme())
                    view.set_buffer(sbuf)
                    dbg("F44: syntax highlighting on (%s)"
                        % lang.get_name())
                except Exception as exc:
                    dbg("Syntax highlighting unavailable (%s) – "
                        "showing plain text" % exc)
                    view = None
        if view is None:
            view = Gtk.TextView()
        scroll = build_text_view(view, text, font, markup,
                                  self._conf_text_line_spacing)
        if linenumbers:
            self._install_line_numbers(view, font,
                                       self._conf_text_line_spacing)
        self._content.pack_start(scroll, True, True, 0)
        # 0.16.2: always set the marker True ("current preview is
        # TextView-based"); previously the line-number switch sat
        # here, so the toggle only worked on disable.
        self._last_textish = True
        return view

    # → REF PAN-DOC-21
    def _install_line_numbers(self, view, font=None, spacing=0):
        # spacing (F25): the extra pixels above every line – the
        # numbers must center on the text, not on the whole box.
        ctx = view.get_style_context()
        probe = view.create_pango_layout("00000")
        # 0.16.3: the numbers draw a bit SMALLER than the text –
        # take the base size and scale to 80%, floored at 1 pt.
        try:
            if font is not None:
                # B12: measure with the effective font – explicit
                # fonts carry the configured size now.
                fd = effective_text_font(font)
            else:
                fd = view.get_pango_context().get_font_description()
            if fd is not None:
                size = fd.get_size()
                if size > 0:
                    fd.set_size(max(int(size * 0.8), Pango.SCALE))
                probe.set_font_description(fd)
        except Exception as e:
            dbg("panel/_install_line_numbers: suppressed: %s" % e)
        # 0.16.1: get_pixel_size() instead of get_pixel_width() –
        # the GI binding does not offer the latter.
        pw, _ph = probe.get_pixel_size()
        view.set_left_margin(pw + 16)

        reported = [False]

        def _on_draw(view, cr):
            # 0.16.2: report exceptions once instead of silent pass
            # – draw fires often; the closure flag prevents log spam.
            try:
                vis = view.get_visible_rect()
                it, _top = view.get_line_at_y(vis.y)
                if it is None:
                    return False
                color = ctx.get_color(view.get_state_flags())
                # 0.16.3: alpha 0.6 → 0.75 – the numbers were too
                # washed out on light backgrounds; still smaller
                # than the text and so distinguishable.
                cr.set_source_rgba(color.red, color.green, color.blue,
                                   color.alpha * 0.75)
                margin = view.get_left_margin()
                while True:
                    y, h = view.get_line_yrange(it)
                    if y > vis.y + vis.height:
                        break
                    probe.set_text(str(it.get_line() + 1))
                    pw, ph = probe.get_pixel_size()
                    _x, wy = view.buffer_to_window_coords(
                        Gtk.TextWindowType.WIDGET, 0, y)
                    # The number font is smaller – center it vertically
                    # on the text area, below the extra line spacing.
                    Gtk.render_layout(ctx, cr, margin - pw - 8,
                                      wy + spacing + max(
                                          (h - spacing - ph) // 2, 0),
                                      probe)
                    if not it.forward_line():
                        break
            except Exception as exc:
                if not reported[0]:
                    reported[0] = True
                    dbg("Line number draw failed: %r" % exc)
            return False

        # 0.16.2: connect_after instead of connect – "draw" is a
        # RUN_LAST signal; the default fill would paint over the
        # numbers.
        view.connect_after("draw", _on_draw)

    # --- E-books: EPUB, FictionBook, MOBI ------------------------------------


    # → REF PAN-DOC-22
    def _folder_symbol(self, theme, sil, is_dir, name, fg):
        ic = Gtk.Image()
        try:
            if is_dir:
                ctype = "inode/directory"
            else:
                ctype = Gio.content_type_guess(name, None)[0]
            sname = ("folder-symbolic" if is_dir
                     else "text-x-generic-symbolic")
            for base in Gio.content_type_get_icon(ctype).get_names():
                cand = base + "-symbolic"
                if theme.has_icon(cand):
                    sname = cand
                    break
            if sname not in sil:
                sil[sname] = _silhouette(theme, sname, fg)
            if sil[sname] is not None:
                ic.set_from_pixbuf(sil[sname])
            else:
                ic.set_from_icon_name(sname, Gtk.IconSize.MENU)
        except Exception:
            ic.set_from_icon_name(
                "folder-symbolic" if is_dir
                else "text-x-generic-symbolic",
                Gtk.IconSize.MENU)
        return ctype, sname, ic

    # → REF PAN-DOC-23
    def _folder_row(self, box, theme, sil, picked, fg, nr, path,
                    name, is_dir):
        ctype, sname, ic = self._folder_symbol(theme, sil, is_dir,
                                               name, fg)
        picked[ctype] = sname
        nm = Gtk.Label()
        if is_dir:
            nm.set_markup("<b>%s</b>"
                          % GLib.markup_escape_text(name))
        else:
            nm.set_text(name)
        nm.set_halign(Gtk.Align.START)
        nm.set_hexpand(True)
        nm.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        nm.set_tooltip_text(name)
        if name.startswith("."):
            nm.get_style_context().add_class("dim-label")
        side = Gtk.Label(label=_("Folder") if is_dir else "")
        if not is_dir:
            try:
                side.set_text(human_size(
                    os.stat(os.path.join(path, name)).st_size))
            except Exception as e:
                dbg("panel/_folder_row: suppressed: %s" % e)
        side.get_style_context().add_class("dim-label")
        side.set_halign(Gtk.Align.END)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=6)
        hbox.set_margin_start(10)
        hbox.set_margin_end(10)
        if nr == 0:
            hbox.set_margin_top(8)
        hbox.pack_start(ic, False, False, 0)
        hbox.pack_start(nm, True, True, 0)
        hbox.pack_start(side, False, False, 0)
        box.add(hbox)
        return hbox

    # → REF PAN-DOC-24
    def _folder_scroll(self, box):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                          Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_overlay_scrolling(False)
        scroll.add(box)
        scroll.connect("draw", self._on_panel_draw)
        try:
            vp = scroll.get_child()
            if vp is not None:
                vp.connect("draw", self._on_panel_draw)
        except Exception as e:
            dbg("panel/_folder_scroll: suppressed: %s" % e)
        scroll.connect("realize", self._on_scroll_realized)
        self._apply_surface_css(scroll)
        return scroll

    # → REF PAN-DOC-25
    def _render_folder(self, path):
        # → REF PAN-FOLDER-1
        dirs, files = [], []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    (dirs if entry.is_dir() else files).append(
                        entry.name)
        except Exception:
            pack_hint(self._content, _("Folder"))
            return
        total = len(dirs) + len(files)
        if total == 0:
            pack_hint(self._content, _("The folder is empty."))
            return
        hidden = sum(1 for n in dirs + files if n.startswith("."))
        unit = _("file") if total == 1 else _("files")
        if hidden > 0:
            pack_hint(self._content,
                      _("The folder contains %d %s, %d of them hidden.")
                      % (total, unit, hidden))
        else:
            pack_hint(self._content,
                      _("The folder contains %d %s.") % (total, unit))
        # 0.30.0: show hidden files only if Nemo shows them; an
        # unreadable setting falls back to showing everything.
        show_hidden = True
        try:
            nemo_prefs = Gio.Settings.new("org.nemo.preferences")
            show_hidden = nemo_prefs.get_boolean("show-hidden-files")
        except Exception as e:
            dbg("panel/_render_folder: suppressed: %s" % e)
        if not show_hidden:
            dirs = [n for n in dirs if not n.startswith(".")]
            files = [n for n in files if not n.startswith(".")]
        # F43: display order – folders before files, alphabetical
        # (case-insensitive).
        shown = ([(n, True) for n in sorted(dirs, key=str.lower)]
                 + [(n, False) for n in sorted(files, key=str.lower)])
        if not shown:
            return
        rest = max(0, len(shown) - 300)
        box = Gtk.ListBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        theme = Gtk.IconTheme.get_default()
        picked = {}
        fg = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        sil = {}
        last_row = None
        for nr, (name, is_dir) in enumerate(shown[:300]):
            last_row = self._folder_row(box, theme, sil, picked, fg,
                                        nr, path, name, is_dir)
        if rest > 0:
            more = Gtk.Label(label=_("… and %d more") % rest)
            more.get_style_context().add_class("dim-label")
            more.set_halign(Gtk.Align.START)
            # Same row padding as the rows above (0.31.11).
            more.set_margin_start(10)
            more.set_margin_end(10)
            box.add(more)
            last_row = more
        # 0.31.11: bottom padding on the last row content instead
        # of a ListBox margin.
        if last_row is not None:
            last_row.set_margin_bottom(8)
        self._content.pack_start(self._folder_scroll(box),
                                 True, True, 0)
        dbg("Folder list: %d entries, %d rows built"
            % (total, min(300, len(shown))))
        # 0.31.1: log content type → chosen symbol; since 0.31.2 the
        # silhouette count, since 0.31.3 the foreground color.
        dbg("Folder icons: " + ", ".join(
            "%s→%s" % kv for kv in sorted(picked.items()))
            + " – silhouettes redrawn: %d/%d"
            " – fg color: %d,%d,%d"
            % (sum(1 for p in sil.values() if p is not None),
               len(sil),
               int(round(fg.red * 255)), int(round(fg.green * 255)),
               int(round(fg.blue * 255))))

    def _render_generic(self):
        mime, size, mtime = query_file_info(self._path)
        big = Gtk.Image()
        try:
            icon = Gio.content_type_get_icon(mime or "text-x-generic")
            big.set_from_gicon(icon, Gtk.IconSize.DIALOG)
            big.set_pixel_size(96)
        except Exception:
            big.set_from_icon_name("text-x-generic", Gtk.IconSize.DIALOG)
        self._content.pack_start(big, True, True, 0)

    # → REF PAN-DOC-26
    def _on_panel_destroy(self, *a):
        # 0.9.1: mark teardown – the child-watch of a running
        # LibreOffice conversion then drops its result.
        self._destroyed = True
        # F66: the aux column state goes down with the panel.
        self._aux_key = None
        self._aux_refresh = None
        self._aux_trigger = None
        # 1.2.4: drop the outer divider hook of the dead shell.
        if getattr(self, "_aux_outer_hid", None) is not None:
            try:
                paned = self._host_paned()
                if paned is not None:
                    paned.handler_disconnect(self._aux_outer_hid)
            except Exception:
                pass
            self._aux_outer_hid = None
        # 1.2.5: drop a pending calibration hook as well.
        if getattr(self, "_aux_calib_hid", None) is not None:
            try:
                self._aux_shell.handler_disconnect(
                    self._aux_calib_hid)
            except Exception:
                pass
            self._aux_calib_hid = None
        self._stop_playback()
        # F71: drop the queued one-shot timers (F2 render, F25
        # line spacing) so they cannot fire into the dead panel.
        self._cancel_pending_render()
        if getattr(self, "_spacing_render_id", None) is not None:
            try:
                GLib.source_remove(self._spacing_render_id)
            except Exception as e:
                dbg("panel/_on_panel_destroy: suppressed: %s" % e)
            self._spacing_render_id = None
        if getattr(self, "_textsize_render_id", None) is not None:
            try:
                GLib.source_remove(self._textsize_render_id)
            except Exception as e:
                dbg("panel/_on_panel_destroy: suppressed: %s" % e)
            self._textsize_render_id = None
        if self._playbin is not None:
            try:
                self._playbin.get_bus().remove_signal_watch()
            except Exception as e:
                dbg("panel/_on_panel_destroy: suppressed: %s" % e)

    # --- Aux column (F66) ---------------------------------------------------

    # → REF PAN-AUX-1
    @property
    def aux_shell(self):
        # Public handle: the entry packs this shell into the paned
        # and toggles its visibility (F66).
        return self._aux_shell

    def _on_aux_draw(self, widget, cr):
        # Same painter chain as the panel – no unpainted areas.
        self._paint_background(widget, cr)
        return False

    def _on_aux_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self._close_aux()
            return True
        return False

    def _host_paned(self):
        # 1.2.2: the shell is a Paned itself since 1.2.1 – the
        # walk starts ABOVE it, else it returns the inner shell.
        node = self._aux_shell.get_parent()
        while node is not None and not isinstance(node, Gtk.Paned):
            node = node.get_parent()
        return node

    def _aux_max_width(self):
        # User wish: the column never grows past half the screen
        # – 600 px fallback when the monitor is unknown.
        try:
            win = self.get_window()
            if win is not None:
                mon = self.get_display().get_monitor_at_window(win)
                if mon is not None:
                    geo = mon.get_geometry()
                    return max(320, geo.width // 2)
        except Exception as e:
            dbg("panel/_aux_max_width: suppressed: %s" % e)
        return 600

    def _aux_handle_px(self):
        # 1.2.5: the real handle width is the separator's CSS
        # min-width - the handle-size style property is
        # deprecated since GTK 3.20 and the themes stopped
        # writing it: the legacy read keeps reporting the
        # default 5 while the separator on themed systems is
        # only 1-2 px, so every open moved the outer divider
        # too far and the preview grew by the difference
        # (deploy report on 1.2.4).  The calibration after
        # each open measures the ground truth (PAN-AUX-2).
        if self._aux_handle is None:
            got = 0
            try:
                shell_ctx = self._aux_shell.get_style_context()
                path = shell_ctx.get_path().copy()
                path.append_type(Gtk.Separator)
                ctx = Gtk.StyleContext.new()
                ctx.set_path(path)
                ctx.set_screen(shell_ctx.get_screen())
                got = int(ctx.get_property(
                    "min-width", Gtk.StateFlags.NORMAL))
            except Exception as e:
                dbg("panel/_aux_handle_px: css: %s" % e)
            if got < 1:
                try:
                    got = int(
                        self._aux_shell.style_get_property(
                            "handle-size"))
                except Exception as e:
                    dbg("panel/_aux_handle_px: suppressed: %s" % e)
                    got = 5
            self._aux_handle = got
            dbg("panel/aux: handle %d px" % got)
        return self._aux_handle

    def _on_aux_calib_alloc(self, widget, alloc):
        # 1.2.5: one-shot - the children allocate right after
        # the shell; measure from the idle so the whole layout
        # is settled (PAN-AUX-2).
        hid = self._aux_calib_hid
        if hid is not None:
            self._aux_calib_hid = None
            try:
                widget.handler_disconnect(hid)
            except Exception:
                pass
        GLib.idle_add(self._aux_calibrate)

    def _aux_calibrate(self):
        # 1.2.5: ground truth after the open - the allocated
        # widths reveal the real handle: shell = column +
        # handle + preview; a wrong prediction shifts the
        # outer divider by the difference so the preview ends
        # up exact.
        if (self._destroyed or self._aux_key is None
                or not self._aux_column.get_visible()):
            return False
        s = self._aux_shell.get_allocation().width
        c = self._aux_column.get_allocation().width
        p = self.get_allocation().width
        if s <= c + p or c < 1 or p < 1:
            return False
        real = s - c - p
        if real == self._aux_handle:
            return False
        err = self._aux_handle - real
        self._aux_handle = real
        self._aux_width = c + real
        dbg("panel/aux: handle %d px (was %d px)"
            % (real, real + err))
        if err:
            outer = self._host_paned()
            if outer is not None:
                try:
                    old = outer.get_position()
                    self._aux_outer_hold = True
                    outer.set_position(max(0, old + err))
                    if outer.get_position() == old:
                        self._aux_outer_hold = False
                except Exception as e:
                    dbg("panel/_aux_calibrate: suppressed: %s" % e)
        return False

    def _on_aux_dragged(self, paned, param):
        # 1.2.3: pure recorder - the divider is native GTK and
        # this never moves a divider back (no feedback loops).
        if self._aux_syncing:
            return
        new_pos = paned.get_position()
        if new_pos == self._aux_pos:
            return
        self._aux_pos = new_pos
        if self._aux_key is not None:
            self._aux_manual_width = new_pos
        self._aux_width = new_pos + self._aux_handle_px()
        dbg("panel/aux: divider at %d px" % new_pos)

    def _on_aux_outer_moved(self, paned, param):
        # 1.2.4: the outer divider moved - the COLUMN absorbs the
        # change BEFORE the layout runs, so the preview never
        # wobbles; programmatic moves hold off one cycle.
        new_pos = paned.get_position()
        delta = new_pos - self._aux_outer_pos
        self._aux_outer_pos = new_pos
        if delta == 0:
            return
        if self._aux_outer_hold:
            self._aux_outer_hold = False
            return
        if self._aux_key is None or not self._aux_column.get_visible():
            return
        try:
            self._aux_shell.set_position(
                min(self._aux_max_width(),
                    max(320, self._aux_shell.get_position()
                        - delta)))
            dbg("panel/aux: outer delta %d px" % delta)
        except Exception as e:
            dbg("panel/_on_aux_outer_moved: suppressed: %s" % e)

    # → REF PAN-AUX-2
    def _aux_apply_width(self, widget):
        # Standard 520 px (former window rule 420 plus the 100 px
        # user wish, 1.3.1) - manual drags win (1.2.1).
        try:
            mn, nat = widget.get_preferred_width()
        except Exception as e:
            dbg("panel/_aux_apply_width: suppressed: %s" % e)
            mn = nat = 400
        manual = self._aux_manual_width
        if manual:
            new_w = min(max(manual, 320), self._aux_max_width())
        else:
            new_w = min(max(520, mn + 32, nat + 32),
                        self._aux_max_width())
        extra = new_w + self._aux_handle_px()
        paned = self._host_paned()
        if paned is not None:
            try:
                old_pos = paned.get_position()
                # 1.2.4: the outer hook skips our own move.
                self._aux_outer_hold = True
                paned.set_position(
                    max(0, old_pos + self._aux_width - extra))
                if paned.get_position() == old_pos:
                    self._aux_outer_hold = False
            except Exception as e:
                dbg("panel/_aux_apply_width: suppressed: %s" % e)
        # The inner position IS the column width; the guard keeps
        # the drag handler out of programmatic moves (1.2.1).
        self._aux_syncing = True
        try:
            self._aux_shell.set_position(new_w)
        except Exception as e:
            dbg("panel/_aux_apply_width: suppressed: %s" % e)
        self._aux_syncing = False
        self._aux_pos = new_w
        self._aux_width = extra
        dbg("panel/aux: width %d px (content %d/%d px)"
            % (new_w, mn, nat))

    def _open_aux(self, key, title, widget, refresh=None, trigger=None):
        # Generic entry point: open or swap a view; the SAME key
        # collapses the column again (PAN-AUX-1).
        if key is not None and key == self._aux_key:
            self._close_aux()
            return
        # 1.2.4: hook the outer divider once - the column absorbs
        # its drags; programmatic moves hold off (PAN-AUX-2).
        if self._aux_outer_hid is None:
            outer = self._host_paned()
            if outer is not None:
                self._aux_outer_pos = outer.get_position()
                self._aux_outer_hid = outer.connect(
                    "notify::position", self._on_aux_outer_moved)
        self._mirror_aux_trigger(trigger)
        self._aux_key = key
        self._aux_refresh = refresh
        self._aux_title_label.set_text(title)
        child = self._aux_scroll.get_child()
        if child is not None:
            self._aux_scroll.remove(child)
        self._aux_scroll.add(widget)
        # Measure and move the divider while the column is still
        # hidden - no requisition clamp in the way (PAN-AUX-2).
        self._aux_apply_width(widget)
        self._aux_column.show()
        widget.show_all()
        # 1.2.5: calibrate the handle width from the real
        # allocation once this layout settles (PAN-AUX-2).
        if self._aux_calib_hid is None:
            self._aux_calib_hid = self._aux_shell.connect(
                "size-allocate", self._on_aux_calib_alloc)
        dbg("panel/aux: open %r" % key)

    def _close_aux(self):
        if self._aux_key is None:
            return
        dbg("panel/aux: close %r" % self._aux_key)
        self._aux_key = None
        self._aux_refresh = None
        self._mirror_aux_trigger(None)
        # Hide FIRST so the requisition drops before the divider
        # returns - a visible column would clamp the move (1.1.1).
        self._aux_column.hide()
        # Restore the position SYNCHRONOUSLY and relative – no
        # timer races in the crowbar embedding (K17/K18 lessons).
        paned = self._host_paned()
        if paned is not None:
            try:
                old_pos = paned.get_position()
                self._aux_outer_hold = True
                paned.set_position(max(0, old_pos + self._aux_width))
                if paned.get_position() == old_pos:
                    self._aux_outer_hold = False
            except Exception as e:
                dbg("panel/_close_aux: suppressed: %s" % e)
        self._aux_width = 0

    # → REF PAN-AUX-3
    def _aux_on_render(self):
        # A new selection refreshes an open aux view; None
        # collapses, a (title, widget) tuple retitles (F66 II).
        if self._aux_key is None or self._aux_refresh is None:
            return
        try:
            res = self._aux_refresh()
        except Exception as e:
            dbg("panel/_aux_on_render: suppressed: %s" % e)
            res = None
        if res is None:
            self._close_aux()
            return
        if isinstance(res, tuple):
            self._aux_title_label.set_text(res[0])
            widget = res[1]
        else:
            widget = res
        child = self._aux_scroll.get_child()
        if child is not None:
            self._aux_scroll.remove(child)
        self._aux_scroll.add(widget)
        self._aux_apply_width(widget)
        widget.show_all()

    def _mirror_aux_trigger(self, btn):
        # Tint the button whose view is open; clear the previous
        # one so only ever one button carries the class.
        old = self._aux_trigger
        if old is not None and old is not btn:
            try:
                old.get_style_context().remove_class("pvw-aux-active")
            except Exception as e:
                dbg("panel/_mirror_aux_trigger: suppressed: %s" % e)
        self._aux_trigger = btn
        if btn is not None:
            btn.get_style_context().add_class("pvw-aux-active")

    # --- Actions --------------------------------------------------------------

    def _on_open_clicked(self, *a):
        if not self._path or not os.path.exists(self._path):
            return
        try:
            Gio.AppInfo.launch_default_for_uri(
                GLib.filename_to_uri(self._path), None)
        except Exception as e:
            dbg("Open failed: %s" % e)

    # → REF PAN-DOC-27
    def _config_load(self):
        if _KEYFILE_CLS is None:
            dbg("GLib.KeyFile missing – config "
                "stays on defaults")
            return
        try:
            kf = _KEYFILE_CLS()
            kf.load_from_file(CONF_FILE, _KEYFILE_FLAGS_NONE)
            try:
                self._conf_show_at_start = kf.get_boolean(
                    "previewer", "show_at_start")
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F48: folder contents list on/off.
            try:
                self._conf_folder_contents = kf.get_boolean(
                    "previewer", "folder_contents")
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F12: waterfall sample text of the font preview.
            try:
                t = kf.get_string("previewer", "font_sample_text")
                if t and t.strip():
                    self._conf_font_sample_text = t
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            try:
                self._conf_text_linenumbers = kf.get_boolean(
                    "previewer", "text_line_numbers")
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F44: syntax highlighting on/off.
            try:
                self._conf_text_syntax = kf.get_boolean(
                    "previewer", "text_syntax")
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F25: extra line spacing in text previews (px, 0–12).
            try:
                ls = kf.get_integer("previewer", "text_line_spacing")
                if 0 <= ls <= 12:
                    self._conf_text_line_spacing = int(ls)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F69: font sizes (px, 0 = theme font) – text previews
            # and info tables.
            try:
                ts = kf.get_integer("previewer", "text_font_size")
                if 0 <= ts <= 28:
                    self._conf_text_font_size = int(ts)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            try:
                ms = kf.get_integer("previewer", "meta_font_size")
                if 0 <= ms <= 28:
                    self._conf_meta_font_size = int(ms)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F12 part 3: document cap (PDF/office) – limit on/off
            # and the maximum page count (1–999).
            try:
                self._conf_doc_page_limit = kf.get_boolean(
                    "previewer", "doc_page_limit")
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            try:
                p = kf.get_integer("previewer", "doc_max_pages")
                if 1 <= p <= 999:
                    self._conf_doc_max_pages = int(p)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            try:
                w = kf.get_integer("previewer", "panel_width")
                if PANEL_MIN_WIDTH <= w <= 2400:
                    self._panel_width = int(w)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            # F65: debug logging toggle – mirrors dbg into the log
            # file; the env var NEMO_PREVIEWER_DEBUG always wins.
            try:
                d = kf.get_boolean("previewer", "debug_log")
                self._conf_debug_log = bool(d)
            except Exception as e:
                dbg("panel/_config_load: suppressed: %s" % e)
            if self._conf_debug_log:
                set_debug_log(True)
        except Exception as e:
            dbg("panel/_config_load: suppressed: %s" % e)

    # → REF PAN-DOC-28
    def _config_save(self):
        if _KEYFILE_CLS is None:
            dbg("GLib.KeyFile missing – config not savable")
            return
        try:
            os.makedirs(CONF_DIR, exist_ok=True)
            kf = _KEYFILE_CLS()
            kf.set_boolean("previewer", "show_at_start",
                           self._conf_show_at_start)
            # F48: persist the folder contents list on/off.
            kf.set_boolean("previewer", "folder_contents",
                           self._conf_folder_contents)
            # F12: persist the waterfall sample text.
            kf.set_string("previewer", "font_sample_text",
                          self._conf_font_sample_text)
            kf.set_boolean("previewer", "text_line_numbers",
                           self._conf_text_linenumbers)
            # F44: persist syntax highlighting.
            kf.set_boolean("previewer", "text_syntax",
                           self._conf_text_syntax)
            # F25: persist the line spacing.
            kf.set_integer("previewer", "text_line_spacing",
                           int(self._conf_text_line_spacing))
            # F69: persist both font sizes.
            kf.set_integer("previewer", "text_font_size",
                           int(self._conf_text_font_size))
            kf.set_integer("previewer", "meta_font_size",
                           int(self._conf_meta_font_size))
            # F12 part 3: persist the document cap.
            kf.set_boolean("previewer", "doc_page_limit",
                           self._conf_doc_page_limit)
            kf.set_integer("previewer", "doc_max_pages",
                           int(self._conf_doc_max_pages))
            kf.set_integer("previewer", "panel_width",
                           int(self._panel_width))
            # F65: persist the debug logging toggle.
            kf.set_boolean("previewer", "debug_log",
                           self._conf_debug_log)
            kf.save_to_file(CONF_FILE)
            # F69: reloaded CSS rules restyle open widgets live.
            apply_font_size_css(self._conf_text_font_size,
                                self._conf_meta_font_size)
        except Exception as exc:
            dbg("Config not saved: %s" % exc)

    # → REF PAN-DOC-29
    def apply_start_settings(self):
        if not self._conf_show_at_start:
            self._aux_shell.hide()
            dbg("Start setting: preview column stays hidden "
                "at start")

    # → REF PAN-DOC-30
    def _apply_panel_width_live(self):
        try:
            parent = self._host_paned()
            if parent is None:
                return
            total = parent.get_allocated_width()
            if total > self._panel_width + 100:
                # F66: an open aux column keeps its width - only
                # the panel side is reset to the configured width.
                old_pos = parent.get_position()
                # 1.2.4: the outer hook skips our own move.
                self._aux_outer_hold = True
                parent.set_position(
                    total - self._panel_width - self._aux_width)
                if parent.get_position() == old_pos:
                    self._aux_outer_hold = False
        except Exception as e:
            dbg("panel/_apply_panel_width_live: suppressed: %s" % e)

    # → REF PAN-DOC-31
    def _on_reset_width_clicked(self, *a):
        # F63: back to the CONFIGURED width (spin button/config)
        # – applied live; _panel_width itself stays as is.
        try:
            parent = self._host_paned()
            if parent is None:
                return
            # 0.52.1: compare the LIVE column width, not
            # _panel_width – dragging never updates it (0.41.0).
            cur = parent.get_allocated_width() - parent.get_position()
            if cur == self._panel_width:
                return
            dbg("panel/reset_width: %d px -> %d px"
                % (cur, self._panel_width))
            self._apply_panel_width_live()
        except Exception as e:
            dbg("panel/_on_reset_width_clicked: suppressed: %s" % e)

    # → REF PAN-DOC-32
    def _update_rec_dot(self):
        # F65: mirror the live debug logging state into the header
        # dot – called from init and the settings toggle. Plain
        # show()/hide(): the battle-tested GTK3 mapping pair.
        try:
            if self._rec_dot is None:
                return
            if debug_log_active():
                self._rec_dot.show()
            else:
                self._rec_dot.hide()
        except Exception as e:
            dbg("panel/_update_rec_dot: suppressed: %s" % e)


PREVIEWER_VERSION = "1.8.0"
dbg("previewer_panel %s loaded (F28/F29/F31 core: dispatch, helpers, "
    "config; renderers and toolbar as mixins)"
    % PREVIEWER_VERSION)


# --- F1: parser selftest (python3 previewer_panel.py --selftest) ---


# → REF PAN-SELFTEST-1
def _st_md_fixture(path):
    text = ("# Fixture Head\n"
            "\n"
            "Some **bold**, *italic* and ~~struck~~ text.\n"
            "\n"
            "- first item\n"
            "- second item\n"
            "\n"
            "`inline code` plus [a link](https://example.com)\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _st_epub_fixture(path):
    opf = ("<?xml version=\"1.0\"?>"
           "<package xmlns=\"http://www.idpf.org/2007/opf\" "
           "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
           "version=\"2.0\">"
           "<metadata>"
           "<dc:title>Fixture Book</dc:title>"
           "<dc:creator>Fixture Author</dc:creator>"
           "<dc:language>en</dc:language>"
           "</metadata>"
           "<manifest>"
           "<item id=\"ncx\" href=\"toc.ncx\" "
           "media-type=\"application/x-dtbncx+xml\"/>"
           "</manifest>"
           "<spine><itemref idref=\"ncx\"/></spine>"
           "</package>")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("content.opf", opf)


def _st_mobi_fixture(path):
    author = b"Fixture Author"
    exth = bytearray(struct.pack(">4sII", b"EXTH", 20 + len(author), 1))
    exth += struct.pack(">II", 100, 8 + len(author)) + author
    while len(exth) % 4:
        exth += b"\x00"
    r0 = bytearray(84)
    struct.pack_into(">H", r0, 0, 1)          # PalmDOC: no compression
    struct.pack_into(">I", r0, 4, 16)         # text length
    struct.pack_into(">H", r0, 8, 1)         # text record count
    struct.pack_into(">H", r0, 10, 4096)     # record size
    r0[16:20] = b"MOBI"
    struct.pack_into(">I", r0, 20, 232)       # MOBI header length
    struct.pack_into(">I", r0, 28, 65001)    # utf-8 encoding
    struct.pack_into(">I", r0, 80, 1)        # first non-book record
    r0 += exth
    data = bytearray(86)
    data[0:12] = b"Fixture Book"
    data[60:68] = b"BOOKMOBI"
    struct.pack_into(">H", data, 76, 1)      # one record
    struct.pack_into(">I", data, 78, 86)     # record 0 offset (4 bytes)
    data += r0
    with open(path, "wb") as fh:
        fh.write(bytes(data))


def _st_font_fixture(path):
    family = "Fixture Sans".encode("utf-16-be")
    style = "Bold".encode("utf-16-be")
    table = (struct.pack(">HHH", 0, 2, 30)
             + struct.pack(">HHHHHH", 3, 1, 0x409, 1, len(family), 0)
             + struct.pack(">HHHHHH", 3, 1, 0x409, 2, len(style),
                           len(family))
             + family + style)
    head = struct.pack(">4sHHHH", b"\x00\x01\x00\x00", 1, 16, 0, 0)
    entry = struct.pack(">4sIII", b"name", 0, 28, len(table))
    with open(path, "wb") as fh:
        fh.write(head + entry + table)


def _st_md_test(path):
    with open(path, "r", encoding="utf-8") as fh:
        out = _markdown_to_pango(fh.read())
    ok = ("<b>bold</b>" in out
          and "<i>italic</i>" in out
          and "<s>struck</s>" in out
          and "<tt>inline code</tt>" in out
          and "size='x-large'" in out
          and "Fixture Head" in out
          and out.count("\u2022") >= 2)
    return ok, out


def _st_epub_test(path):
    rows, cover = _epub_data(path)
    meta = dict(rows)
    ok = (meta.get("Book title") == "Fixture Book"
          and meta.get("Author") == "Fixture Author"
          and cover is None)
    return ok, str(rows)


def _st_mobi_test(path):
    rows, _cover = _mobi_data(path)
    meta = dict(rows)
    ok = (meta.get("Book title") == "Fixture Book"
          and meta.get("Author") == "Fixture Author")
    return ok, str(rows)


def _st_font_test(path):
    reg, fmt, faces = _font_faces(path)
    ok = (fmt == "TrueType"
          and faces == [("Fixture Sans", "Bold")]
          and reg == path)
    return ok, "%s %s %s" % (reg, fmt, str(faces))


def run_selftest():
    # F1: regression tests for the file parsers - four synthetic
    # fixtures in a temp dir, no Nemo or GTK involved.
    tmpdir = tempfile.mkdtemp(prefix="previewer-selftest-")
    checks = []
    try:
        for name, ext, builder, test in (
                ("markdown", ".md", _st_md_fixture, _st_md_test),
                ("epub", ".epub", _st_epub_fixture, _st_epub_test),
                ("mobi", ".mobi", _st_mobi_fixture, _st_mobi_test),
                ("font", ".ttf", _st_font_fixture, _st_font_test)):
            path = os.path.join(tmpdir, "fixture" + ext)
            builder(path)
            try:
                ok, detail = test(path)
            except Exception as e:
                ok, detail = False, "%s: %s" % (type(e).__name__, e)
            checks.append((name, ok, detail))
    finally:
        for name in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, name))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    failed = 0
    for name, ok, detail in checks:
        print("%s %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            failed += 1
            print("  %s" % detail)
    print("%d/%d passed" % (len(checks) - failed, len(checks)))
    return 1 if failed else 0


if __name__ == "__main__" and sys.argv[1:] == ["--selftest"]:
    sys.exit(run_selftest())