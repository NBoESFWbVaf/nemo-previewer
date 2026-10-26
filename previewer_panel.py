#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Panel-Modul (previewer_panel.py)
============================================

Das angedockte Vorschau-Panel samt allen Renderern: Bilder, Text, PDF,
Audio (mit Player), Video, Ordner und Office-Dokumente.

Office (ODT/ODS/ODP, DOCX/XLSX/PPTX) wird, wenn LibreOffice und Poppler
vorhanden sind, scharf und in voller Panelbreite angezeigt: LibreOffice
konvertiert im Hintergrund einmalig nach PDF (Cache in ~/.cache/previewer),
Poppler rendert die erste Seite. Während der Konvertierung ist die
eingebettete Miniaturansicht aus dem Dokument-ZIP mit einem Hinweis zu
sehen; das scharfe Ergebnis erscheint automatisch. Ohne LibreOffice gilt
weiterhin die ZIP-Miniaturansicht ohne Zusatzpakete.

Gehört zur vierteiligen Extension "Previewer" (siehe previewer.py).
"""

import os
import re
import sys
import hashlib
import shutil
import tempfile
import traceback
import zipfile
import xml.etree.ElementTree as ElementTree
from datetime import datetime

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
    MAX_TEXT_BYTES, MAX_TEXT_LINES, MAX_IMAGE_HEIGHT,
    TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
    query_file_info, human_size, format_seconds,
    content_type_description,
)

# --- Optionale Module (Fehlen ist kein Fehler, nur weniger Vorschau) ---

HAVE_GST = False
try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import Gst, GstPbutils
    Gst.init(None)
    HAVE_GST = True
except Exception:
    pass

HAVE_POPPLER = False
try:
    import cairo  # pycairo
    gi.require_version('Poppler', '0.18')
    from gi.repository import Poppler
    HAVE_POPPLER = True
except Exception:
    pass

# LibreOffice für die scharfe Office-Vorschau (Hintergrundkonvertierung
# nach PDF). Fehlt es, bleibt die eingebettete Miniaturansicht.
SOFFICE = None
try:
    SOFFICE = shutil.which("soffice")
except Exception:
    SOFFICE = None

# Cache für LibreOffice-Konvertierungen: ~/.cache/previewer/<hash>.pdf


def office_cache_dir():
    """Cache-Ordner ~/.cache/previewer (wird bei Bedarf angelegt)."""
    d = os.path.join(GLib.get_user_cache_dir(), "previewer")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def office_cache_path(path):
    """Cache-Pfad des konvertierten PDFs (Key = Hash des absoluten Pfads)."""
    key = hashlib.sha1(
        os.path.abspath(path).encode("utf-8", "replace")).hexdigest()
    return os.path.join(office_cache_dir(), key + ".pdf")


# Office-Dokumente sind ZIP-Archive: eingebettete Miniaturansicht zeigen
# und/oder einen Textauszug. Ohne neue Pakete (nur Python-Bordmittel).
_OFFICE_EXTS = {
    ".odt", ".ods", ".odp", ".odg", ".odf",          # OpenDocument
    ".docx", ".xlsx", ".pptx",                        # MS Office (OOXML)
}
_OFFICE_THUMBS = (
    "Thumbnails/thumbnail.png",                       # ODF
    "docProps/thumbnail.jpeg",                       # OOXML
    "docProps/thumbnail.png",
)
_OFFICE_TEXT_ENTRIES = (
    "content.xml",                                   # ODF
    "word/document.xml",                              # OOXML (Text)
)
_OFFICE_MAX_TEXT_CHARS = 4000


def _extract_office_text(zf, names):
    """
    Textauszug aus einem Office-ZIP ziehen. ODF trägt den Inhalt in
    content.xml (text:p/text:h/text:span), OOXML in word/document.xml
    (w:p/w:t) – in beiden Fällen genügt das Sammeln der Textknoten,
    Absätze werden als Zeilenumbrüche übernommen.
    """
    entry = next((n for n in _OFFICE_TEXT_ENTRIES if n in names), None)
    if not entry:
        return ""
    try:
        root = ElementTree.fromstring(zf.read(entry))
    except Exception:
        return ""
    parts = []
    for elem in root.iter():
        tag = elem.tag if isinstance(elem.tag, str) else ""
        if tag.endswith("}p") or tag.endswith("}h"):
            parts.append("\n")
        elif tag.endswith("}tab"):
            parts.append(" ")
        if elem.text:
            parts.append(elem.text)
    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:_OFFICE_MAX_TEXT_CHARS]


# Zusätzliche Text-Dateiendungen, die GtkSourceView-artige Vorschau erhalten.
_TEXT_EXTRAS = {
    '.py', '.sh', '.bash', '.zsh', '.js', '.ts', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.csv', '.log', '.md', '.rst',
    '.css', '.html', '.xml', '.patch', '.diff', '.desktop', '.service',
    '.gitignore', '.nemo_action', '.pyw', '.lua', '.pl', '.rb', '.go',
    '.rs', '.c', '.h', '.cpp', '.hpp', '.java', '.sql', '.tex',
}

# ================================ Panel ====================================

class PreviewPanel(Gtk.Box):
    """Das angedockte Vorschau-Panel (rechte Hälfte des Gtk.Paned)."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(PANEL_MIN_WIDTH, -1)

        self._window = window
        self._path = None
        self._names = []
        self._playbin = None
        self._progress_timer = 0
        self._render_width = 0
        # Skalierbare Vorschau: Quelle in voller Auflösung behalten und
        # nur die angezeigte Pixbuf bei Breitenänderung neu skalieren.
        self._scale_img = None
        self._scale_src = None
        self._scale_max_h = 0
        self._scale_upscale = False
        self._scale_max_up = 1.0
        self._scale_keep_h = False
        self._scale_last_w = 0
        # Hintergrund-Konvertierung für Office-Dokumente (LibreOffice → PDF)
        self._office_job = None
        self._office_failed = set()

        # --- Kopfzeile ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)

        self._icon_image = Gtk.Image.new_from_icon_name(
            "text-x-generic", Gtk.IconSize.DIALOG)
        header.pack_start(self._icon_image, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._name_label = Gtk.Label(label="Keine Datei ausgewählt")
        self._name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.set_hexpand(True)
        self._name_label.get_style_context().add_class("dim-label")
        self._name_label.set_line_wrap(False)
        title_box.pack_start(self._name_label, True, True, 0)

        self._meta_label = Gtk.Label(label="")
        self._meta_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._meta_label.set_halign(Gtk.Align.START)
        self._meta_label.get_style_context().add_class("dim-label")
        self._meta_label.set_hexpand(True)
        title_box.pack_start(self._meta_label, True, True, 0)
        header.pack_start(title_box, True, True, 0)

        # Öffnen- und Ausblenden-Knöpfe
        btn_open = Gtk.Button.new_from_icon_name(
            "document-open-symbolic", Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text("Mit Standardanwendung öffnen")
        btn_open.set_relief(Gtk.ReliefStyle.NONE)
        btn_open.connect("clicked", self._on_open_clicked)
        header.pack_end(btn_open, False, False, 0)

        btn_hide = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.BUTTON)
        btn_hide.set_tooltip_text("Panel ausblenden (Strg+Alt+P)")
        btn_hide.set_relief(Gtk.ReliefStyle.NONE)
        btn_hide.connect("clicked", lambda *a: self.hide())
        header.pack_end(btn_hide, False, False, 0)

        self.pack_start(header, False, False, 0)
        self._separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self._separator, False, False, 0)

        # --- Vorschau-Bereich ---
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._content.set_border_width(8)
        self.pack_start(self._content, True, True, 0)
        # Vorschau passt ihre Größe an, wenn die Panelbreite (Gtk.Paned-
        # Trenner) verändert wird: entprelltes Neu-Rendern bei Breiten-
        # änderung.
        self._content.connect("size-allocate",
                              self._on_content_size_allocate)

        self._show_placeholder()

        # Tastenkürzel zum Wieder-Einblenden
        try:
            accel = Gtk.AccelGroup()
            window.add_accel_group(accel)
            accel.connect(TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
                          Gtk.AccelFlags.VISIBLE, self._on_toggle_accel)
        except Exception:
            pass

    # ------------------------------ Selektion ------------------------------

    def set_selection(self, names, dir_path):
        """Auswahl setzen und Vorschau neu rendern (names = Dateinamen)."""
        # Audio-Player immer sauber stoppen, wenn sich etwas ändert
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
        # Skalier-Quelle freigeben (Speicher der vollen Auflösung)
        self._scale_img = None
        self._scale_src = None
        self._scale_last_w = 0

    def _show_placeholder(self):
        self._name_label.set_text("Keine Datei ausgewählt")
        self._meta_label.set_text("")
        self._icon_image.set_from_icon_name("edit-find-symbolic",
                                           Gtk.IconSize.DIALOG)
        self._clear_content()
        # Nemo-Logo, mittig (horizontal und vertikal) in der Spalte
        logo = Gtk.Image()
        logo_name = "folder"
        try:
            theme = Gtk.IconTheme.get_default()
            if theme.has_icon("nemo"):
                logo_name = "nemo"
        except Exception:
            pass
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
            dbg("Fehler beim Rendern von %r:" % self._path)
            traceback.print_exc()
            try:
                self._render_generic()
            except Exception:
                pass
        self._content.show_all()

    def _render_inner(self):
        path = self._path
        self._clear_content()

        if len(self._names) > 1:
            extra = Gtk.Label(label="… und %d weitere ausgewählt" %
                              (len(self._names) - 1))
            extra.get_style_context().add_class("dim-label")
            extra.set_halign(Gtk.Align.START)
            self._content.pack_start(extra, False, False, 0)

        if not path or not os.path.exists(path):
            self._name_label.set_text(
                self._names[0] if self._names else "?")
            self._meta_label.set_text("(Datei nicht gefunden)")
            self._icon_image.set_from_icon_name(
                "dialog-warning-symbolic", Gtk.IconSize.DIALOG)
            return

        mime, size, mtime = query_file_info(path)
        is_dir = os.path.isdir(path)

        # Kopfzeile füllen
        self._name_label.set_text(os.path.basename(path))
        self._name_label.set_tooltip_text(path)
        meta_parts = []
        if mime:
            meta_parts.append(content_type_description(mime))
        if size >= 0:
            meta_parts.append(human_size(size))
        if mtime > 0:
            meta_parts.append(
                datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M"))
        self._meta_label.set_text(" · ".join(meta_parts))
        self._set_icon(mime, is_dir)

        uri = GLib.filename_to_uri(path)
        lower = path.lower()

        # --- nach Typ rendern ---
        if is_dir:
            self._render_folder(path)
        elif mime.startswith("image/") or mime == "application/x-xpixmap":
            self._render_image(path)
        elif mime == "application/pdf" or lower.endswith(".pdf"):
            if HAVE_POPPLER:
                self._render_pdf(path)
            else:
                self._hint("PDF-Vorschau nicht verfügbar – "
                           "Paket gir1.2-poppler-0.18 installieren.")
                self._render_generic()
        elif mime.startswith("audio/") or lower.endswith((".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".wma")):
            if HAVE_GST:
                self._render_audio(path, uri)
            else:
                self._hint("Audio-Vorschau nicht verfügbar – "
                           "Paket gir1.2-gst-plugins-base-1.0 installieren.")
                self._render_generic()
        elif mime.startswith("video/"):
            if HAVE_GST:
                self._render_video(path, uri)
            else:
                self._render_generic()
        elif mime.startswith("text/") or os.path.splitext(lower)[1] in _TEXT_EXTRAS:
            self._render_text(path)
        elif os.path.splitext(lower)[1] in _OFFICE_EXTS:
            self._render_office(path)
        else:
            self._render_generic()

    # --- einzelne Renderer --------------------------------------------------

    def _set_icon(self, mime, is_dir):
        try:
            if is_dir:
                name = "folder"
            else:
                icon = Gio.content_type_get_icon(mime or "text-x-generic")
                names = icon.get_names()
                name = names[0] if names else "text-x-generic"
            self._icon_image.set_from_icon_name(name, Gtk.IconSize.DIALOG)
        except Exception:
            self._icon_image.set_from_icon_name(
                "text-x-generic", Gtk.IconSize.DIALOG)

    def _on_content_size_allocate(self, widget, allocation):
        """
        Breitenänderung des Vorschau-Bereichs beobachten (der Nutzer zieht
        den Gtk.Paned-Trenner). Es wird NICHT neu gerendert – stattdessen
        wird nur die angezeigte Pixbuf der skalierbaren Vorschau sofort
        an die neue Breite angepasst (billig, ohne Neu-Decodieren).
        """
        try:
            width = allocation.width
            if abs(width - self._render_width) < 12:
                return
            self._render_width = width
            self._apply_scale()
        except Exception:
            pass

    def _scaled_image(self, src, max_h, upscale=False, keep_height=False,
                      max_upscale=1.0):
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
        expandiertem Packen (Bild, PDF) darf KEINE Mindesthöhe gesetzt
        werden – hochkantige Bilder würden sonst dem Fenster ihre Höhe
        aufzwingen.
        Gibt den fertigen Container (Gtk.ScrolledWindow) zurück.
        """
        self._scale_src = src
        self._scale_max_h = max_h
        self._scale_upscale = upscale
        self._scale_max_up = max_upscale
        self._scale_keep_h = keep_height
        self._scale_last_w = 0
        img = Gtk.Image()
        # Horizontal mittig: kleine Vorschauen (Cover, Office-Miniatur)
        # kleben nicht am linken Rand, sondern sitzen zentriert.
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.START)
        self._scale_img = img
        scroll = Gtk.ScrolledWindow()
        self._scale_scroll = scroll
        # AUTOMATIC in beide Richtungen: bricht die Weitergabe der
        # Kind-Minimalbreite nach oben ab, das Pane bleibt frei ziehbar.
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
        self._apply_scale()
        return scroll

    def _apply_scale(self):
        """Angezeigte Pixbuf der Vorschau an die aktuelle Breite anpassen."""
        img = self._scale_img
        src = self._scale_src
        if img is None or src is None:
            return
        try:
            sw, sh = src.get_width(), src.get_height()
            if sw <= 0 or sh <= 0:
                return
            target = self._preview_width()
            f = float(target) / sw
            if f > 1.0:
                if self._scale_upscale:
                    # Hochskalieren, aber begrenzt: kleine Quellen
                    # (Office-Miniaturansichten) werden sonst unleserlich.
                    f = min(f, self._scale_max_up)
                else:
                    f = 1.0          # kleine Bilder nicht unscharf aufblasen
            if f * sh > self._scale_max_h:
                f = float(self._scale_max_h) / sh
            w = max(1, int(sw * f))
            h = max(1, int(sh * f))
            if abs(w - self._scale_last_w) < 4:
                return
            self._scale_last_w = w
            # Beim Hochskalieren qualitativ besser interpolieren
            interp = (GdkPixbuf.InterpType.HYPER if f > 1.0
                      else GdkPixbuf.InterpType.BILINEAR)
            img.set_from_pixbuf(src.scale_simple(w, h, interp))
            # Mindesthöhe nur bei keep_height: hält den Container auf
            # Bildhöhe, wenn er nicht expandiert gepackt ist (sonst
            # würde das Bild unten abgeschnitten). Zusätzlich die
            # Scrollposition zurücksetzen – nach einem Aufziehen-/
            # Zurückschieben-Zyklus stünde das Bild sonst versetzt.
            try:
                if self._scale_keep_h:
                    self._scale_scroll.set_min_content_height(h)
                    self._scale_scroll.get_vadjustment().set_value(0)
            except Exception:
                pass
        except Exception:
            pass

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
                # Innenabstand (Rahmen 8 px je Seite) abziehen
                return max(PANEL_MIN_WIDTH - 20, w - 16)
        except Exception:
            pass
        return PANEL_WIDTH - 40

    def _render_image(self, path):
        # Quelle in voller Auflösung laden (Riesenbilder werden auf eine
        # sinnvolle Deckelung verkleinert); die ANZEIGE regelt die Live-
        # Skalierung über die Panelbreite.
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path, 4096, 4096, True)
        if pb.get_width() > 4096 or pb.get_height() > MAX_IMAGE_HEIGHT:
            pb = self._scale_pixbuf(pb, 4096, MAX_IMAGE_HEIGHT)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False)
        self._content.pack_start(scroll, True, True, 0)
        try:
            w, h = GdkPixbuf.Pixbuf.get_file_info(path)[1:3]
            info = Gtk.Label(label="%d × %d px" % (w, h))
            info.get_style_context().add_class("dim-label")
            info.set_halign(Gtk.Align.START)
            self._content.pack_start(info, False, False, 0)
        except Exception:
            pass

    def _render_text(self, path):
        try:
            with open(path, 'rb') as fh:
                data = fh.read(MAX_TEXT_BYTES)
            text = data.decode('utf-8', 'replace')
            truncated = False
            if len(data) == MAX_TEXT_BYTES:
                truncated = True
            lines = text.split("\n")
            if len(lines) > MAX_TEXT_LINES:
                lines = lines[:MAX_TEXT_LINES]
                truncated = True
            text = "\n".join(lines)
        except Exception as e:
            self._hint("Konnte Datei nicht lesen: %s" % e)
            return

        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.override_font(Pango.FontDescription("Monospace 9"))
        # Innenabstand, damit der Text nicht am Rand klebt
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)
        if truncated:
            self._hint("Vorschau gekürzt (lange Datei).")

    def _render_pdf(self, path):
        doc = Poppler.Document.new_from_file(GLib.filename_to_uri(path), None)
        if doc.get_n_pages() == 0:
            self._hint("PDF enthält keine Seiten.")
            return
        page = doc.get_page(0)
        pw, ph = page.get_size()
        # Mit doppelter Zielbreite rendern, damit die Live-Skalierung
        # auch beim Ziehen des Trenners scharf bleibt.
        scale = min(3.0, max(1.0, self._preview_width() * 2.0 / max(pw, 1)))
        w, h = max(1, int(pw * scale)), max(1, int(ph * scale))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        # Weiße Unterlage: PDF-Seiten dürfen transparente Flächen haben –
        # ohne Unterlage sähen sie auf dunklen Themes unleserlich schwarz aus.
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.paint()
        cr.scale(scale, scale)
        page.render(cr)
        pb = Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False)
        self._content.pack_start(scroll, True, True, 0)
        if doc.get_n_pages() > 1:
            self._hint("Seite 1 von %d – gesamte Datei über den "
                       "Öffnen-Knopf betrachten." % doc.get_n_pages())

    def _render_folder(self, path):
        try:
            with os.scandir(path) as it:
                n = sum(1 for _ in it)
            self._hint("Ordner mit %d Einträgen." % n)
        except Exception:
            self._hint("Ordner")
        big = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
        big.set_pixel_size(128)
        self._content.pack_start(big, True, True, 0)

    def _render_audio(self, path, uri):
        tags = {}
        duration = -1
        cover = None
        try:
            disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            info = disc.discover_uri_sync(uri)
            duration = info.get_duration() // Gst.SECOND
            taglist = info.get_tags()
            if taglist:
                for key, gst_tag in (("title", Gst.TAG_TITLE),
                                     ("artist", Gst.TAG_ARTIST),
                                     ("album", Gst.TAG_ALBUM)):
                    ok, val = taglist.get_string(gst_tag)
                    if ok and val:
                        tags[key] = val
                ok, sample = taglist.get_sample(Gst.TAG_IMAGE)
                if not (ok and sample):
                    ok, sample = taglist.get_sample(Gst.TAG_PREVIEW_IMAGE)
                if ok and sample:
                    cover = self._pixbuf_from_sample(sample)
        except Exception as e:
            dbg("Discoverer-Fehler: %s" % e)

        if cover:
            scroll = self._scaled_image(cover, 320, upscale=False,
                                        keep_height=True)
            self._content.pack_start(scroll, False, False, 0)

        rows = []
        if "title" in tags and tags["title"] != os.path.basename(path):
            rows.append(("Titel", tags["title"]))
        rows.append(("Datei", os.path.basename(path)))
        if "artist" in tags:
            rows.append(("Interpret", tags["artist"]))
        if "album" in tags:
            rows.append(("Album", tags["album"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))

        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(label=k)
            kl.set_halign(Gtk.Align.END)
            kl.get_style_context().add_class("dim-label")
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            vl.set_ellipsize(Pango.EllipsizeMode.END)
            vl.set_hexpand(True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._content.pack_start(grid, False, False, 0)

        # --- Player-Leiste ---
        if self._playbin is None:
            self._playbin = Gst.ElementFactory.make("playbin", "previewer-playbin")
        self._playbin.set_property("uri", uri)

        player_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._btn_play = Gtk.Button.new_from_icon_name(
            "media-playback-start-symbolic", Gtk.IconSize.BUTTON)
        self._btn_play.connect("clicked", self._on_play_pause)
        player_box.pack_start(self._btn_play, False, False, 0)

        self._seek_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, max(duration, 1), 1)
        self._seek_scale.set_value(0)
        self._seek_scale.set_draw_value(False)
        self._seek_scale.set_hexpand(True)
        self._seek_scale.connect("change-value", self._on_seek)
        player_box.pack_start(self._seek_scale, True, True, 0)

        self._pos_label = Gtk.Label(label="0:00")
        player_box.pack_start(self._pos_label, False, False, 0)
        self._content.pack_start(player_box, False, False, 0)

        if self._progress_timer:
            GLib.source_remove(self._progress_timer)
        self._progress_timer = GLib.timeout_add(400, self._tick_player)

    def _pixbuf_from_sample(self, sample):
        buf = sample.get_buffer()
        data = buf.extract_dup(0, buf.get_size())
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        return loader.get_pixbuf()

    def _scale_pixbuf(self, pb, max_w, max_h):
        w, h = pb.get_width(), pb.get_height()
        if w <= max_w and h <= max_h:
            return pb
        scale = min(max_w / w, max_h / h)
        return pb.scale_simple(max(1, int(w * scale)),
                               max(1, int(h * scale)),
                               GdkPixbuf.InterpType.BILINEAR)

    def _render_video(self, path, uri):
        duration = -1
        frame = None
        tags = {}
        try:
            disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            info = disc.discover_uri_sync(uri)
            duration = info.get_duration() // Gst.SECOND
            taglist = info.get_tags()
            if taglist:
                for key, gst_tag in (("title", Gst.TAG_TITLE),
                                     ("artist", Gst.TAG_ARTIST)):
                    ok, val = taglist.get_string(gst_tag)
                    if ok and val:
                        tags[key] = val
            ok, sample = taglist.get_sample(Gst.TAG_PREVIEW_IMAGE) if taglist else (False, None)
            if ok and sample:
                frame = self._pixbuf_from_sample(sample)
        except Exception as e:
            dbg("Discoverer-Fehler: %s" % e)

        if frame:
            scroll = self._scaled_image(frame, 320, upscale=False,
                                        keep_height=True)
            self._content.pack_start(scroll, False, False, 0)
        else:
            self._hint("Kein Standbild verfügbar – Video im Player öffnen.")

        rows = [("Datei", os.path.basename(path))]
        if "title" in tags:
            rows.append(("Titel", tags["title"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(label=k)
            kl.set_halign(Gtk.Align.END)
            kl.get_style_context().add_class("dim-label")
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            vl.set_ellipsize(Pango.EllipsizeMode.END)
            vl.set_hexpand(True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._content.pack_start(grid, False, False, 0)

    def _render_office(self, path):
        """
        Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX) – scharfe Route:
        Ist ein frisches LibreOffice-Konvertierungs-PDF im Cache, wird
        dessen erste Seite per Poppler scharf und in voller Panelbreite
        gerendert (identisch zur PDF-Vorschau, live skalierbar). Sonst
        erscheint zunächst die eingebettete Miniaturansicht mit
        Hinweis, und die Konvertierung läuft im Hintergrund los – das
        scharfe Ergebnis zeigt sich automatisch, sobald es fertig ist.
        Ohne LibreOffice/Poppler bleibt es bei der Miniaturansicht.
        """
        if HAVE_POPPLER and SOFFICE:
            cached = self._office_cached_pdf(path)
            if cached:
                try:
                    self._render_pdf(cached)
                    return
                except Exception as exc:
                    dbg("Office-PDF-Vorschau fehlgeschlagen (%s): %s"
                        % (path, exc))
                    # Halb gepackte Reste der PDF-Ansicht entfernen,
                    # bevor die Miniaturansicht gepackt wird.
                    self._clear_content()
                    # Ungültiges Cache-PDF: als gescheitert merken, sonst
                    # würde jede Neudarstellung erneut konvertieren.
                    self._office_failed.add(path)
            failed = path in self._office_failed
            self._render_office_thumb(path, converting=not failed)
            self._office_start_job(path)
            return
        self._render_office_thumb(path, converting=False)

    def _render_office_thumb(self, path, converting=False):
        """
        Übergangs-Ansicht für Office-Dokumente: die vom Dokument selbst
        eingebettete Miniaturansicht (Thumbnails/thumbnail.png bzw.
        docProps/thumbnail.*). Nur wenn KEINE Miniaturansicht vorhanden
        ist, wird ersatzweise ein Textauszug gezeigt. Bei converting=True
        läuft parallel die LibreOffice-Konvertierung – dann mit Hinweis.
        """
        thumb = None
        text = ""
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                for member in _OFFICE_THUMBS:
                    if member in names:
                        try:
                            thumb = zf.read(member)
                        except Exception:
                            thumb = None
                        break
                text = _extract_office_text(zf, names)
        except Exception as e:
            self._hint("Office-Dokument konnte nicht geöffnet werden: %s" % e)
            return
        shown = False
        if thumb:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(thumb)
                loader.close()
                pb = loader.get_pixbuf()
                if pb is not None:
                    # Upscale: Office-Miniaturansichten sind oft nur
                    # 256 px breit – sie wachsen mit der Panelbreite mit,
                    # statt klein in der Ecke zu kleben.
                    # Office-Miniaturansichten NATIV und scharf zeigen:
                    # Die eingebettete Miniatur hat nur ~256 px – jede
                    # Vergrößerung macht sie unleserlich schwammig.
                    scroll = self._scaled_image(pb, 1600, upscale=True,
                                                keep_height=True,
                                                max_upscale=1.0)
                    self._content.pack_start(scroll, False, False, 0)
                    shown = True
            except Exception:
                pass
        # Text nur als Ersatzvorschau, wenn keine Miniaturansicht
        # eingebettet war.
        if not shown and text.strip():
            view = Gtk.TextView()
            view.set_editable(False)
            view.set_cursor_visible(False)
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            view.override_font(Pango.FontDescription("Monospace 9"))
            view.set_left_margin(10)
            view.set_right_margin(10)
            view.set_top_margin(8)
            view.set_bottom_margin(8)
            view.get_buffer().set_text(text)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(view)
            self._content.pack_start(scroll, True, True, 0)
            shown = True
        if not shown:
            self._hint("Keine eingebettete Vorschau und kein Text "
                       "gefunden – Datei über den Öffnen-Knopf betrachten.")
        if converting:
            self._hint("Scharfe Vorschau wird im Hintergrund erstellt "
                       "(LibreOffice) – einen Moment …")

    # --- Office: scharfe Vorschau via LibreOffice --------------------------

    def _office_cached_pdf(self, path):
        """Frisch konvertiertes PDF aus dem Cache oder None."""
        try:
            cache_pdf = office_cache_path(path)
            if (os.path.exists(cache_pdf)
                    and os.path.getmtime(cache_pdf)
                    >= os.path.getmtime(path)):
                return cache_pdf
        except Exception:
            pass
        return None

    def _office_start_job(self, path):
        """LibreOffice-Konvertierung im Hintergrund starten."""
        if self._office_job is not None:
            return          # es läuft bereits eine Konvertierung
        if not SOFFICE or not HAVE_POPPLER:
            return
        if path in self._office_failed:
            return          # bereits gescheitert – nicht endlos erneut
        self._office_job = path
        tmpdir = tempfile.mkdtemp(prefix="previewer-office-")
        out_pdf = os.path.join(
            tmpdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        try:
            pid = GLib.spawn_async(
                [SOFFICE, "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, path],
                flags=GLib.SpawnFlags.SEARCH_PATH
                | GLib.SpawnFlags.DO_NOT_REAP_CHILD)[0]
        except Exception as exc:
            dbg("LibreOffice-Konvertierung nicht gestartet (%s): %s"
                % (path, exc))
            shutil.rmtree(tmpdir, ignore_errors=True)
            self._office_job = None
            return
        GLib.child_watch_add(pid, self._office_job_done,
                             (path, tmpdir, out_pdf))

    def _office_job_done(self, pid, status, data):
        """Konvertierung beendet: Ergebnis cachen, Vorschau auffrischen."""
        path, tmpdir, out_pdf = data
        self._office_job = None
        try:
            if os.path.exists(out_pdf):
                try:
                    os.replace(out_pdf, office_cache_path(path))
                except Exception as exc:
                    dbg("Office-Cache konnte nicht geschrieben werden: %s"
                        % exc)
                if self._path == path:
                    self._render()   # scharfe Seitenansicht zeigen
            else:
                # Gescheiterte Konvertierung merken – verhindert eine
                # Endlosschleife aus erneuten Konvertierungsversuchen.
                self._office_failed.add(path)
                if len(self._office_failed) > 256:
                    self._office_failed.clear()
                if self._path == path:
                    dbg("LibreOffice-Konvertierung ohne Ergebnis "
                        "(Status %s) – Miniaturansicht bleibt" % status)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        # Wartet die aktuelle Auswahl auf ihre Konvertierung, direkt die
        # nächste starten (es läuft ja keine mehr).
        try:
            cur = self._path
            if (cur and os.path.splitext(cur.lower())[1] in _OFFICE_EXTS
                    and cur not in self._office_failed
                    and self._office_cached_pdf(cur) is None
                    and self._office_job is None):
                self._office_start_job(cur)
        except Exception:
            pass

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

    def _hint(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        lbl.set_halign(Gtk.Align.START)
        self._content.pack_start(lbl, False, False, 0)

    # --- Audio-Player-Logik -------------------------------------------------

    def _on_play_pause(self, *a):
        if self._playbin is None:
            return
        ok, state, pending = self._playbin.get_state(0)
        if state == Gst.State.PLAYING:
            self._playbin.set_state(Gst.State.PAUSED)
            self._btn_play.set_image(Gtk.Image.new_from_icon_name(
                "media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        else:
            self._playbin.set_state(Gst.State.PLAYING)
            self._btn_play.set_image(Gtk.Image.new_from_icon_name(
                "media-playback-pause-symbolic", Gtk.IconSize.BUTTON))

    def _on_seek(self, scale, scroll_type, value):
        if self._playbin is None:
            return False
        try:
            ok, dur = self._playbin.query_duration(Gst.Format.TIME)
            if ok and dur > 0:
                self._playbin.seek_simple(
                    Gst.Format.TIME, Gst.SeekFlags.FLUSH,
                    int(value / max(scale.get_adjustment().get_upper(), 1)
                        * dur))
        except Exception:
            pass
        return False

    def _tick_player(self):
        """Positionsanzeige aktualisieren; Timer läuft, solange Panel lebt."""
        if self._playbin is None:
            self._progress_timer = 0
            return False
        try:
            ok, pos = self._playbin.query_position(Gst.Format.TIME)
            ok2, dur = self._playbin.query_duration(Gst.Format.TIME)
            if ok and ok2 and dur > 0:
                self._pos_label.set_text(format_seconds(pos // Gst.SECOND))
                # Signalblockade vermeiden: Skala nur bei Abweichung setzen
                target = pos / dur * self._seek_scale.get_adjustment().get_upper()
                if abs(self._seek_scale.get_value() - target) > 1.5:
                    self._seek_scale.set_value(target)
        except Exception:
            pass
        return True  # weiterlaufen

    def _stop_playback(self):
        if self._playbin is not None:
            try:
                self._playbin.set_state(Gst.State.NULL)
            except Exception:
                pass

    # --- Aktionen -----------------------------------------------------------

    def _on_open_clicked(self, *a):
        if not self._path or not os.path.exists(self._path):
            return
        try:
            Gio.AppInfo.launch_default_for_uri(
                GLib.filename_to_uri(self._path), None)
        except Exception as e:
            dbg("Öffnen fehlgeschlagen: %s" % e)

    def _on_toggle_accel(self, group, accelerable, key, mods):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
        return True