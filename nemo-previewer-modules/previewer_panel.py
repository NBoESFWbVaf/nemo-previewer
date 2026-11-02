#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_panel.py – Version 0.46.0

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


def _sniff_is_text(path, probe=4096):
    """
    F23/B10: Ist eine Datei lesbarer Text? Gio rät den MIME-Typ nur
    aus dem Dateinamen – B10 ruft den Schnüffler als LETZTE Instanz
    auf, bevor die Vorschau aufgibt: endungslose Dateien (notes,
    Dotfiles) und Endungen, deren geratener Typ nirgends getippt
    ist (.pub, .crt, .csr, .pref …), bekommen die Text-Vorschau
    nach INHALT statt nach Namen. Kurzer Blick in die ersten
    Bytes: NULL-Bytes und ein überhöhter Anteil an Steuerzeichen
    (alles außer Tab/LF/CR) deuten auf Binärdaten; B10 ergänzt die
    UTF-8-Decodier-Probe als zweites Kriterium – ein Kopf, der zu
    mindestens 30 % aus 8-Bit-Bytes besteht, die KEIN gültiges
    UTF-8 ergeben, ist gepackt/verschlüsselt und fällt durch
    (Latin-1-Text bleibt erlaubt, Umlaute mischen sich unter viel
    ASCII). Encoding-agnostisch – UTF-8 wie Latin-1-Text bestehen,
    Zufalls-Binärdaten fallen sicher durch. Die eigentliche
    Text-Vorschau kappelt wie immer bei 256 KB / 2000 Zeilen.
    """
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


def _silhouette(theme, sname, fg, size=16):
    """
    0.31.2 (Nutzer-Fund): Gewähltes Symbol laden und als einfarbige
    Silhouette in der Vordergrundfarbe nachzeichnen. Die 0.31.1-
    Diagnose zeigte, dass der Ladekurs durchweg -symbolic-Namen
    wählt – das WhiteSur-Theme liefert unter diesen Namen aber
    selbst farbige Icons, die im Darkmode als dunkle Platten mit
    hartem Rand erscheinen. Die Nachzeichnung behält den Alpha-
    kanal des Originals (Form) und setzt RGB einheitlich auf die
    übergebene Farbe – so ist das Icon im Darkmode hell und im
    Lightmode dunkel, egal was das Theme einschmuggelt. Rückgabe:
    Pixbuf oder None (dann lädt der Aufrufer das Symbol unverändert).
    """
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

class PreviewPanel(PreviewToolbarMixin, MediaRendererMixin, DocsRendererMixin,
                   TextRendererMixin, Gtk.Box):
    """Das angedockte Vorschau-Panel (rechte Hälfte des Gtk.Paned)."""

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
        self._surface_css_farbe = None

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
        btn_open.set_tooltip_text("Mit Standardanwendung öffnen")
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

    def _bg_content_ctx(self):
        """Stil-Kontext des gerenderten Inhalts (Liste/Text-Ansicht).

        Dessen Fläche ist sichtbar gemalt – eine dort aufgelöste
        Hintergrundfarbe ist garantiert echt und passt zur Platte.
        """
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

    def _derived_base(self):
        """Contrast-correct base from the panel fg color (0.38.1, F46
        XI): bright fg → dark base and vice versa."""
        fg = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        return 0.12 if (fg.red + fg.green + fg.blue) / 3.0 > 0.5 \
            else 0.92

    def _paint_background(self, widget, cr):
        """Hintergrund unter alle Kinder malen – als Kette (F46 III).

        Erste Quelle mit aufgelöster Farbe gewinnt; dbg nennt alle
        Kandidaten, damit das Log zeigt, was das Theme liefert
        (→ REF PAN-BG-2).
        """
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

    def _on_scroll_realized(self, sc):
        """Bildlaufleisten an den Painter hängen (F46 IV) – sie
        entstehen erst beim Realisieren (→ REF PAN-BG-2).
        0.31.7 (F46 V): Auch die Flächen-CSS-Regel nachreichen."""
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

    def _apply_surface_css(self, scroll):
        """F46 V: Hintergrund der Scroll-Flächen per CSS setzen.

        Der draw-Painter läuft VOR dem Widget-Standard-Draw – malt
        das Theme dort eine eigene Fläche (Trough, Viewport), über-
        deckt sie ihn. Eine CSS-Regel hingegen färbt im regulären
        Mal-Durchlauf, mit Anwendungspriorität über dem Theme. Die
        Regel gilt nur unterhalb der Klasse pvw-surface, berührt
        Nemo selbst also nicht (→ REF PAN-BG-2).
        """
        try:
            farbe = None
            try:
                rgba = self.get_style_context().get_background_color(
                    Gtk.StateFlags.NORMAL)
                if rgba is not None and rgba.alpha > 0.0:
                    farbe = rgba.to_string()
            except Exception as e:
                dbg("panel/_apply_surface_css: suppressed: %s" % e)
            if farbe is None:
                # 0.38.1 (F46 XI): fallback is fg-derived now – the
                # old hardcoded rgb(56,56,56) shone dark in light mode.
                base = self._derived_base()
                farbe = "rgb(%d,%d,%d)" % (
                    round(base * 255), round(base * 255),
                    round(base * 255))
            css = (
                ".pvw-surface,"
                ".pvw-surface junction,"
                ".pvw-surface viewport,"
                ".pvw-surface scrollbar,"
                ".pvw-surface scrollbar trough,"
                ".pvw-surface scrollbar undershoot"
                " { background-color: %s; }" % farbe).encode("utf-8")
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
            if self._surface_css_farbe != farbe:
                self._surface_css_farbe = farbe
                dbg("Panel bg CSS: rule for scroll areas installed "
                    "(color %s)" % farbe)
        except Exception as e:
            dbg("Panel bg CSS: failed – %s" % e)

    def _surface_css_contexts(self, scroll):
        """Stil-Kontexte, die die Flächen-Regel zusätzlich brauchen
        (F46 V) – Provider greifen zwar über die Eltern-Kette, zur
        Sicherheit stehen sie auch direkt an jedem Kind (→ REF
        PAN-BG-2)."""
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

    def set_selection(self, names, dir_path):
        """Auswahl setzen und Vorschau neu rendern (names = Dateinamen)."""
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
        lbl = Gtk.Label(label="Wähle eine Datei aus,\num eine Vorschau zu sehen.")
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.pack_start(logo, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        self._content.pack_start(box, True, True, 0)
        self._content.show_all()

    def _render(self):
        """Vorschau für self._path aufbauen. Nie werfen – immer Fallback."""
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
            extra = Gtk.Label(label="… und %d weitere ausgewählt" %
                              (len(self._names) - 1))
            extra.get_style_context().add_class("dim-label")
            extra.set_halign(Gtk.Align.START)
            self._content.pack_start(extra, False, False, 0)

        if not path or not os.path.exists(path):
            # F35: the name sits in the Nemo list – only the warning
            # hint remains, in the content area.
            pack_hint(self._content, "(Datei nicht gefunden)")
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
                pack_hint(self._content, "PDF-Vorschau nicht verfügbar – "
                           "Paket gir1.2-poppler-0.18 installieren.")
                self._render_generic()
        elif mime.startswith("audio/") or lower.endswith((".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".wma")):
            if HAVE_GST:
                self._render_audio(path, uri)
            else:
                pack_hint(self._content, "Audio-Vorschau nicht verfügbar – "
                           "Paket gir1.2-gst-plugins-base-1.0 installieren.")
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

    def _on_content_size_allocate(self, widget, allocation):
        """
        Breitenänderung des Vorschau-Bereichs beobachten (der Nutzer zieht
        den Gtk.Paned-Trenner). Es wird NICHT neu gerendert – stattdessen
        wird nur die angezeigte Pixbuf der skalierbaren Vorschau sofort
        an die neue Breite angepasst (billig, ohne Neu-Decodieren).
        0.41.0: Eine gezogene Breite gilt nur für die laufende
        Sitzung und ändert die STARTBREITE nicht mehr – die steht
        allein im Einstellungsfenster.
        """
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

    def _scaled_image(self, src, max_h, upscale=False, keep_height=False,
                      max_upscale=1.0, frac_h=None):
        """
        Gtk.Image, das mit der Panelbreite lebt. Die Quelle (src) bleibt
        in voller Auflösung im Speicher; die angezeigte Pixbuf wird bei
        Breitenänderungen live neu skaliert. Das Bild liegt in einem
        ScrolledWindow, damit seine Minimalbreite das Gtk.Paned beim
        Verkleinern nicht blockiert (das war die Ruckel-Ursache).
        upscale=True lässt kleine Quellen (z.B. Office-Miniaturansichten)
        mit der Panelbreite mitwachsen – begrenzt durch max_upscale,
        damit kleine Miniaturansichten nicht zu unleserlichem Brei
        hochgeblasen werden.
        keep_height=True nur bei nicht-expandiertem Packen (Office,
        Cover, Video-Frame): hält die Containerhöhe auf Bildhöhe, damit
        das Bild unter Platzdruck nicht unten abgeschnitten wird. Bei
        expandiertem Packen (PDF) darf KEINE Mindesthöhe gesetzt werden
        – hochkantige Bilder würden sonst dem Fenster ihre Höhe
        aufzwingen.
        0.17.0: frac_h (z. B. 0.6) begrenzt die Anzeige-Höhe auf diesen
        Bruchteil der SPALTENHÖHE – live, weil _apply_scale bei jedem
        Fenster-Resize neu heranzieht. Nutzt die Bild-Vorschau
        (Nutzer-Wunsch: max. 60 % der Spalte, darunter ein Trenner und
        später zusätzliche Informationen); eingebettete Bilder (Cover,
        Office-Miniatur, Video-Frame) bleiben ohne frac.
        R3: Skalier-Parameter liegen als Python-Daten-Dict JEWEILS am
        Bild-Eintrag in self._scale_items statt in Panel-Einzelattributen
        – mehrere live-skalierte Bilder pro Vorschau (Cover +
        Kapitelbilder …) überschreiben sich damit nicht mehr gegenseitig.
        (Bewusst NICHT Gtk set_data/get_data: PyGObject blockiert die
        GObject-Daten-Methoden mit 'Data access methods are unsupported'
        – das Panel stürzte sonst beim ersten Bild ab.)
        Gibt den fertigen Container (Gtk.ScrolledWindow) zurück.
        S6 (0.42.0): Der Widget-Bau liegt als build_scaled_image()
        in previewer_util; hier bleiben Registrierung und
        Erst-Skalierung.
        """
        img, scroll, item = build_scaled_image(
            src, max_h, upscale, keep_height, max_upscale, frac_h)
        if self._scale_items is None:
            self._scale_items = []
        self._scale_items.append(item)
        self._apply_scale()
        return scroll

    def _apply_scale(self):
        """Angezeigte Pixbufs ALLER registrierten Vorschau-Bilder an die
        aktuelle Panelbreite anpassen (R3: Liste statt Einzel-Slot;
        Einträge sind Daten-Dicts, siehe _scaled_image)."""
        for item in self._scale_items or ():
            try:
                self._scale_item(item)
            except Exception as e:
                dbg("panel/_apply_scale: suppressed: %s" % e)

    def _scale_item(self, item):
        """EIN Vorschau-Bild an die Panelbreite anpassen (R3/0.17.0) –
        Höhen-Deckel frisch, Upscale begrenzt, bei unter 4 px Änderung
        auslassen (Early-Return statt Schachtelung)."""
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

    def _preview_width(self):
        """
        Breite, die Vorschau-Objekte zur Verfügung haben. Live aus der
        aktuellen Fläche des Inhaltsbereichs (get_allocated_width),
        damit die Vorschau mit der Panelbreite skalieren kann; die
        Startbreite dient nur als Fallback, solange noch keine
        Größenzuweisung erfolgt ist.
        """
        try:
            w = self._content.get_allocated_width()
            if w > 40:
                # Subtract the padding (8 px border per side)
                return max(PANEL_MIN_WIDTH - 20, w - 16)
        except Exception as e:
            dbg("panel/_preview_width: suppressed: %s" % e)
        return PANEL_WIDTH - 40

    def _preview_height(self):
        """
        0.17.0: Höhe des Inhaltsbereichs – Basis für die Höhenkappe
        der Bild-Vorschau (max. 60 % der Spaltenhöhe, Nutzer-Wunsch:
        unter dem Bild bleibt Platz für einen Trenner und zusätzliche
        Informationen). Live aus der aktuellen Fläche, Fallback
        solange noch keine Größenzuweisung erfolgt ist.
        """
        try:
            h = self._content.get_allocated_height()
            if h > 100:
                return h
        except Exception as e:
            dbg("panel/_preview_height: suppressed: %s" % e)
        return 600

    def _source_language(self, path):
        """
        F44 (0.28.0): Sprache der Datei über den GtkSource-
        LanguageManager raten (anhand des Namens). None heißt: keine
        erkannte Sprache – dann bleibt es bei der normalen Text-
        Vorschau.
        """
        try:
            return GtkSource.LanguageManager.get_default().guess_language(
                os.path.basename(path), None)
        except Exception:
            return None

    def _source_scheme(self):
        """
        F44 (0.28.0): Farbschema ans System-Theme anpassen – dunkles
        Theme (gtk-theme-name enthält „dark“ oder prefer-dark gesetzt)
        bekommt ein dunkles Schema (oblivion, notfalls solarized-
        dark), sonst das helle „classic“. Fehlt ein Kandidat, greift
        der Widget-Default.
        """
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

    def _text_view(self, text, font="9", markup=None, linenumbers=False,
                   source_path=None):
        """
        Fertig konfigurierter TextView im ScrolledWindow, gepackt in
        self._content. font: Pango-Beschreibung; None belässt die
        System-Schrift des GTK-Themes (also die Schriftgröße des
        Systems) und ruft override_font gar nicht erst auf. markup:
        optionaler Pango-Markup-String (muss vorher validiert sein);
        ohne Markup wird der Rohtext gesetzt. linenumbers (F24):
        Zeilennummern am linken Rand – nur von _render_text gesetzt
        (Textdateien und endungslose Textdateien), gerenderte
        Vorschauen (Markdown, E-Mail, E-Book, Font-Wasserfall)
        bleiben ohne. source_path (F44, 0.28.0): Datei, deren Sprache
        GtkSourceView raten soll – wird eine Sprache erkannt, zeigt
        sich Syntax-Hervorhebung; ohne Binding oder Sprache bleibt
        es beim normalen TextView.
        S6 (0.42.0): Konfiguration und Pufferfüllung liegen als
        build_text_view() in previewer_util.
        """
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

    def _install_line_numbers(self, view, font=None):
        """
        F24 (0.16.0): Zeilennummern in den linken Rand des TextView
        zeichnen – nicht in den Textbuffer. Damit sind sie von der
        Auswahl ausgeschlossen und landen NIE im kopierten Text
        (Nutzer-Wunsch: Nummern nicht kopierbar, Text schon), während
        der Text selbst normal selektier- und kopierbar bleibt. Der
        draw-Handler feuert bei jedem Neuzeichnen (auch beim
        Scrollen) und zeichnet nur die sichtbaren Zeilen; umgebrochene
        Zeilen bekommen ihre Nummer an der ersten visuellen Zeile.
        """
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


    def _folder_symbol(self, theme, sil, is_dir, name, fg):
        """
        S2 (0.42.0): Symbol-Icon einer Ordnerzeile – Kandidaten aus
        dem content type mit -symbolic-Suffix gegen das Theme prüfen
        (0.30.1), fehlende Varianten generisch halten, nie das
        farbige Voll-Icon; jede gewählte Symbolform wird als
        Silhouette in der Vordergrundfarbe nachgezeichnet (0.31.2,
        → REF PAN-FOLDER-1).
        """
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

    def _folder_row(self, box, theme, sil, picked, fg, nr, path,
                    name, is_dir):
        """
        S2 (0.42.0): Eine Zeile der Ordnerliste – Icon, Name (Ordner
        fett, Versteckte gedimmt), Größe rechts. Das Padding der
        Platte (10 px seitlich, 8 px oben bei der ersten Zeile)
        liegt am Zeilen-Inhalt, nicht an der ListBox (0.31.11,
        → REF PAN-FOLDER-1).
        """
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
        side = Gtk.Label(label="Ordner" if is_dir else "")
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

    def _folder_scroll(self, box):
        """
        S2 (0.42.0): Scroll-Fenster der Ordnerliste mit der ganzen
        F46-Hintergrund-Absicherung – Inline-Balken statt Overlay
        (0.31.10), Painter an Scroll-Fenster und Viewport (0.31.5/
        0.31.6), CSS-Regel obendrauf (0.31.7) (→ REF PAN-BG-2).
        """
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

    def _render_folder(self, path):
        """
        F43 (Nutzer-Wunsch): Die Ordner-Vorschau zeigt den Inhalt als
        Liste statt nur eines Ordner-Icons – Ordner zuerst (fett),
        dann Dateien, je alphabetisch; pro Zeile Icon, Name plus
        „Ordner“ bzw. Größe. Seit 0.29.0 (Nutzer-Wunsch): Vor jedem
        Namen das Typ-Icon aus dem Icon-Theme, die Liste trägt den
        Innenabstand der Text-Vorschauen (10/10/8/8 px). Seit 0.30.0
        (Nutzer-Wunsch): Die Icons sind symbolisch und folgen dem
        System-Theme (Darkmode hell, Lightmode dunkel); versteckte
        Einträge stehen nur in der Liste, wenn Nemo sie anzeigt
        (Strg+H, org.nemo.preferences show-hidden-files), sonst weist
        der Kopf-Hinweis sie zahlenmäßig aus (K1). Riesige Ordner: die ersten
        300 Zeilen im Scroll-Fenster, Rest als Fußzeile – sonst
        baute ein Ordner mit zehntausend Einträgen ebensoviele
        Label-Widgets.
        S2 (0.42.0): Zerlegt – _folder_symbol, _folder_row und
        _folder_scroll bauen Icon, Zeile und Scroll-Fenster; hier
        bleibt nur der Ablauf.
        """
        # → REF PAN-FOLDER-1
        dirs, files = [], []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    (dirs if entry.is_dir() else files).append(
                        entry.name)
        except Exception:
            pack_hint(self._content, "Ordner")
            return
        total = len(dirs) + len(files)
        if total == 0:
            pack_hint(self._content, "Der Ordner ist leer.")
            return
        hidden = sum(1 for n in dirs + files if n.startswith("."))
        unit = "Datei" if total == 1 else "Dateien"
        if hidden > 0:
            pack_hint(self._content,
                      "Der Ordner enthält %d %s, davon %d versteckt."
                      % (total, unit, hidden))
        else:
            pack_hint(self._content,
                      "Der Ordner enthält %d %s." % (total, unit))
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
            more = Gtk.Label(label="… und %d weitere" % rest)
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

    def _on_panel_destroy(self, *a):
        """Panel wird abgebaut: Wiedergabe und Timer stoppen (B3)."""
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

    def _config_load(self):
        """
        F12 (0.12.0): Einstellungen aus CONF_FILE lesen. Ohne Datei
        oder bei JEGLICHEM Fehler gelten die Defaults – eine kaputte
        oder halb geschriebene Konfiguration darf Nemo niemals am
        Start hindern. Neue Einstellungen docken als get_boolean/
        get_string mit try/except hier an.
        """
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

    def _config_save(self):
        """
        F12 (0.12.0): Einstellungen sofort in CONF_FILE schreiben
        (Verzeichnis bei Bedarf anlegen). Aufgerufen nach jeder
        Änderung im Einstellungsfenster – ein separater Speichern-
        Knopf ist damit unnötig.
        """
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

    def apply_start_settings(self):
        """
        F12 (0.12.0): Geladene Konfiguration auf das Panel anwenden.
        Wird vom Einstieg NACH dem show_all der Injizierung aufge-
        rufen – sonst würde eine verlangte Unsichtbarkeit beim Start
        sofort wieder überschrieben. Neue Start-Einstellungen docken
        hier an.
        """
        if not self._conf_show_at_start:
            self.hide()
            dbg("Start setting: preview column stays hidden "
                "at start")

    def _apply_panel_width_live(self):
        """
        F12 (0.13.0): Neue Startbreite sofort anwenden, während das
        Einstellungsfenster offen ist – der Nutzer sieht die Wirkung
        direkt. Die Paned-Position wird so gesetzt, dass die
        Vorschauspalte self._panel_width breit ist; geht es nicht
        (Fenster zu klein), bleibt alles unverändert.
        """
        try:
            parent = self.get_parent()
            if parent is None:
                return
            total = parent.get_allocated_width()
            if total > self._panel_width + 100:
                parent.set_position(total - self._panel_width)
        except Exception as e:
            dbg("panel/_apply_panel_width_live: suppressed: %s" % e)


PREVIEWER_VERSION = "0.46.0"
dbg("previewer_panel %s loaded (F28/F29/F31 core: dispatch, helpers, "
    "config; renderers and toolbar as mixins)"
    % PREVIEWER_VERSION)