#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_panel.py – Version 0.48.0

Panel core: file-type dispatch, preview widgets and configuration;
inherits the toolbar and renderer mixins and paints the panel
background.
"""

import os
import sys
import traceback

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    PANEL_WIDTH, PANEL_MIN_WIDTH,
    query_file_info,
    pick_icon,
    human_size,
    pack_hint,
    build_scaled_image,
    build_text_view,
)
from previewer_render_media import MediaRendererMixin, HAVE_GST
from previewer_render_docs import (
    DocsRendererMixin, HAVE_POPPLER, _OFFICE_EXTS,
)
from previewer_render_text import TextRendererMixin, _FONT_SAMPLE_TEXT
from previewer_toolbar import PreviewToolbarMixin

# → REF PAN-F44-1
HAVE_GTKSOURCE = False
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAVE_GTKSOURCE = True
except Exception as e:
    dbg("panel/module-level: suppressed: %s" % e)

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

# F12: configuration of the preview column – GLib-native INI
# format, no extra dependency; created on first save.
CONF_DIR = os.path.expanduser("~/.config/nemo-previewer")
CONF_FILE = os.path.join(CONF_DIR, "nemo-previewer.conf")
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
        # 0.9.1: remember panel teardown – a running LibreOffice
        # child-watch must not render after that.
        self._destroyed = False
        # Multi-page PDF preview: source pixbufs per page + display images
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_box = None
        self._pdf_last_w = 0
        # → REF PAN-R2-1
        self._pdf_gen = 0
        # F14: page indicator of the PDF preview + total page count
        self._pdf_page_label = None
        self._pdf_count = 0
        # → REF PAN-F12-1
        self._conf_show_at_start = True
        # F48: folder preview with contents list is the mandatory
        # default; the settings switch toggles the plain icon (→ REF PAN-FOLDER-2).
        self._conf_folder_contents = True
        # F12: waterfall sample text of the font preview – default
        # is the classic sentence, editable in the settings (→ REF TXT-FONT-2).
        self._conf_font_sample_text = _FONT_SAMPLE_TEXT
        # F24: line numbers in the plain text preview – default ON
        # (user request), toggleable in the settings ("Text files").
        self._conf_text_linenumbers = True
        # F44: syntax highlighting as a SETTING – "Text files"
        # section, default on; applies live via _last_textish.
        self._conf_text_syntax = True
        # F12 part 3: document cap configurable – limit PDF/office
        # previews or show all; default matches the old hard cap.
        self._conf_doc_page_limit = True
        self._conf_doc_max_pages = 20
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
        self._settings_win = None
        self._settings_spin = None
        self._settings_pages_spin = None
        self._config_load()

        # --- Header (F35: controls only – icon, name, type, size
        # and date already sit in the Nemo list) ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)

        # Open button (F40: system run icon). The hide button moved
        # to Nemo's title bar as the preview toggle (→ REF ENT-TOGGLE-1).
        btn_open = Gtk.Button.new_from_icon_name(
            pick_icon(("document-edit-symbolic", "document-edit",
                       "edit-symbolic", "text-editor-symbolic"),
                      "document-open-symbolic"),
            Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text("Open with the default application")
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


        # --- F19: toolbar at the bottom of the preview column ---
        # Construction, settings button, CSS and shortcut (Ctrl+Alt+P)
        # live in the toolbar module (F29).
        self._build_toolbar(window)

        self._show_placeholder()

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
            self._show_placeholder()
            return

        self._names = list(names)
        first = names[0]
        if dir_path:
            self._path = os.path.join(dir_path, first)
        else:
            self._path = first
        self._render()

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
        self._pdf_box = None
        self._pdf_last_w = 0
        self._pdf_page_label = None
        self._pdf_count = 0
        self._pdf_gen += 1
        # F24: was the just torn-down preview a text preview?
        self._last_textish = False
        # F12 part 3: was it a document page view (PDF/office)?
        self._last_docview = False

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
        lbl = Gtk.Label(label="Select a file\nto see a preview.")
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

    def _render_inner(self):
        path = self._path
        self._clear_content()
        # 0.31.4 (F46 II): reset the content area's outer margin to
        # 8 px per render – edgeless renderers zero it themselves (→ REF PAN-BG-1).
        self._content.set_border_width(8)

        if len(self._names) > 1:
            extra = Gtk.Label(label="… and %d more selected" %
                              (len(self._names) - 1))
            extra.get_style_context().add_class("dim-label")
            extra.set_halign(Gtk.Align.START)
            self._content.pack_start(extra, False, False, 0)

        if not path or not os.path.exists(path):
            # F35: the name sits in the Nemo list – only the warning
            # hint remains, in the content area.
            pack_hint(self._content, "(file not found)")
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
                pack_hint(self._content, "PDF preview not available – "
                           "install package gir1.2-poppler-0.18.")
                self._render_generic()
        elif mime.startswith("audio/") or lower.endswith((".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".wma")):
            if HAVE_GST:
                self._render_audio(path, uri)
            else:
                pack_hint(self._content, "Audio preview not available – "
                           "install package gir1.2-gst-plugins-base-1.0.")
                self._render_generic()
        elif mime.startswith("video/"):
            if HAVE_GST:
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
        elif (mime in ("application/vnd.sqlite3", "application/x-sqlite3")
              or lower.endswith((".db", ".sqlite", ".sqlite3"))):
            self._render_sqlite(path)
        elif (mime in ("font/ttf", "font/otf", "font/collection",
                       "application/x-font-ttf", "application/x-font-otf",
                       "application/vnd.ms-opentype")
              or lower.endswith((".ttf", ".otf", ".ttc"))):
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
        for item in self._scale_items or ():
            try:
                self._scale_item(item)
            except Exception as e:
                dbg("panel/_apply_scale: suppressed: %s" % e)

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
        scroll = build_text_view(view, text, font, markup)
        if linenumbers:
            self._install_line_numbers(view, font)
        self._content.pack_start(scroll, True, True, 0)
        # 0.16.2: always set the marker True ("current preview is
        # TextView-based"); previously the line-number switch sat
        # here, so the toggle only worked on disable.
        self._last_textish = True
        return view

    # → REF PAN-DOC-21
    def _install_line_numbers(self, view, font=None):
        ctx = view.get_style_context()
        probe = view.create_pango_layout("00000")
        # 0.16.3: the numbers draw a bit SMALLER than the text –
        # take the base size and scale to 80%, floored at 1 pt.
        try:
            if font is not None:
                fd = Pango.FontDescription(font)
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
                    y, _h = view.get_line_yrange(it)
                    if y > vis.y + vis.height:
                        break
                    probe.set_text(str(it.get_line() + 1))
                    pw, _ph = probe.get_pixel_size()
                    _x, wy = view.buffer_to_window_coords(
                        Gtk.TextWindowType.WIDGET, 0, y)
                    Gtk.render_layout(ctx, cr, margin - pw - 8,
                                      wy + 1, probe)
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
        side = Gtk.Label(label="Folder" if is_dir else "")
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
            pack_hint(self._content, "Folder")
            return
        total = len(dirs) + len(files)
        if total == 0:
            pack_hint(self._content, "The folder is empty.")
            return
        hidden = sum(1 for n in dirs + files if n.startswith("."))
        unit = "file" if total == 1 else "files"
        if hidden > 0:
            pack_hint(self._content,
                      "The folder contains %d %s, %d of them hidden."
                      % (total, unit, hidden))
        else:
            pack_hint(self._content,
                      "The folder contains %d %s." % (total, unit))
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
            more = Gtk.Label(label="… and %d more" % rest)
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
        self._stop_playback()
        if self._playbin is not None:
            try:
                self._playbin.get_bus().remove_signal_watch()
            except Exception as e:
                dbg("panel/_on_panel_destroy: suppressed: %s" % e)

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
            # F12 part 3: persist the document cap.
            kf.set_boolean("previewer", "doc_page_limit",
                           self._conf_doc_page_limit)
            kf.set_integer("previewer", "doc_max_pages",
                           int(self._conf_doc_max_pages))
            kf.set_integer("previewer", "panel_width",
                           int(self._panel_width))
            kf.save_to_file(CONF_FILE)
        except Exception as exc:
            dbg("Config not saved: %s" % exc)

    # → REF PAN-DOC-29
    def apply_start_settings(self):
        if not self._conf_show_at_start:
            self.hide()
            dbg("Start setting: preview column stays hidden "
                "at start")

    # → REF PAN-DOC-30
    def _apply_panel_width_live(self):
        try:
            parent = self.get_parent()
            if parent is None:
                return
            total = parent.get_allocated_width()
            if total > self._panel_width + 100:
                parent.set_position(total - self._panel_width)
        except Exception as e:
            dbg("panel/_apply_panel_width_live: suppressed: %s" % e)


PREVIEWER_VERSION = "0.48.0"
dbg("previewer_panel %s loaded (F28/F29/F31 core: dispatch, helpers, "
    "config; renderers and toolbar as mixins)"
    % PREVIEWER_VERSION)