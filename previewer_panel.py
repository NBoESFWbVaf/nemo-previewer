#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Panel-Modul (previewer_panel.py)
============================================

STAND: Version 0.16.1 – F24-Feld-Fix: 0.16.0 maß die Randbreite
mit Pango.Layout.get_pixel_width, das die GI-Bindung nicht anbietet
(Testfeld: AttributeError bei jeder Text-Vorschau) – jetzt misst
get_pixel_size(). Sonst unverändert: F24-Zeilennummern als
Randzeichnung (nicht im kopierbaren Text), Schlüssel
text_line_numbers, Rubrik „Textdateien“ im Toolbar-Modul.

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
"""

import os
import sys
import traceback
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
    query_file_info, human_size,
    content_type_description,
)
from previewer_render_media import MediaRendererMixin, HAVE_GST
from previewer_render_docs import (
    DocsRendererMixin, HAVE_POPPLER, _OFFICE_EXTS,
)
from previewer_render_text import TextRendererMixin
from previewer_toolbar import PreviewToolbarMixin

_TEXT_EXTRAS = {
    '.py', '.sh', '.bash', '.zsh', '.js', '.ts', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.csv', '.log', '.md', '.rst',
    '.css', '.html', '.xml', '.patch', '.diff', '.desktop', '.service',
    '.gitignore', '.nemo_action', '.pyw', '.lua', '.pl', '.rb', '.go',
    '.rs', '.c', '.h', '.cpp', '.hpp', '.java', '.sql', '.tex',
}

# F12 (0.12.0): Konfiguration der Vorschauspalte – GLib-natives
# INI-Format, braucht keine zusätzliche Abhängigkeit. Verzeichnis
# wird beim ersten Speichern angelegt.
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
    F23: Ist eine endungslose Datei lesbarer Text? Gio rät den
    MIME-Typ nur aus dem Dateinamen – frei benannte Dateien (notes,
    todo, Dotfiles wie .bashrc) landen sonst auf application/
    octet-stream und damit ohne Text-Vorschau. Kurzer Blick in die
    ersten Bytes statt Vertrauen auf den Namen: NULL-Bytes und ein
    überhöhter Anteil an Steuerzeichen (alles außer Tab/LF/CR)
    deuten auf Binärdaten. Encoding-agnostisch – UTF-8 wie Latin-1-
    Text bestehen, Zufalls-Binärdaten fallen sicher durch. Die
    eigentliche Text-Vorschau kappelt wie immer bei 256 KB /
    2000 Zeilen.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(probe)
    except Exception:
        return False
    if not head or b"\x00" in head:
        return False
    ctrl = sum(1 for b in head if b < 9 or 14 <= b <= 31 or b == 127)
    return ctrl / len(head) < 0.05

# ================================ Panel ====================================

class PreviewPanel(PreviewToolbarMixin, MediaRendererMixin, DocsRendererMixin,
                   TextRendererMixin, Gtk.Box):
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
        # Skalierbare Vorschauen (R3): JEDES Bild bringt seine Parameter
        # als eigenen Dict-Eintrag mit (siehe _scaled_image) – so sind
        # beliebig viele live-skalierte Bilder pro Vorschau möglich,
        # ohne sich gegenseitig zu überschreiben.
        self._scale_items = []
        # Hintergrund-Konvertierung für Office-Dokumente (LibreOffice → PDF)
        self._office_job = None
        self._office_failed = set()
        # 0.9.1: Panel-Abbau merken – der child-watch einer laufenden
        # LibreOffice-Konvertierung darf dann nicht mehr rendern.
        self._destroyed = False
        # Mehrseitige PDF-Vorschau: Quell-Pixbufs je Seite + Anzeige-Images
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_box = None
        self._pdf_last_w = 0
        # → REF PAN-R2-1
        self._pdf_gen = 0
        # F14: Seitenanzeige der PDF-Vorschau + Gesamtzahl der Seiten
        self._pdf_page_label = None
        self._pdf_count = 0
        # → REF PAN-F12-1
        self._conf_show_at_start = True
        # F24 (0.16.0): Zeilennummern in der reinen Text-Vorschau –
        # Default laut Nutzer-Wunsch AN, umschaltbar im Einstellungs-
        # fenster (Rubrik „Textdateien“).
        self._conf_text_linenumbers = True
        # Merker: Zeigt die AKTUELLE Vorschau Zeilennummern? (Damit
        # der Einstellungs-Toggle nur Textvorschauen neu rendert,
        # statt z.B. Audio-Player oder Office-Konvertierung.)
        self._last_textish = False
        # Standardbreite beim Start: Default PANEL_WIDTH (300 px,
        # Nutzer-Wunsch). Eine per Ziehen gewählte Breite wird zur
        # künftigen Startbreite und landet entprellt in der conf;
        # _panel_width_saved verhindert Doppel-Schreibvorgänge.
        self._panel_width = PANEL_WIDTH
        self._panel_width_saved = PANEL_WIDTH
        self._panel_width_timer = 0
        self._settings_win = None
        self._settings_spin = None
        self._settings_width_label = None
        self._config_load()

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


        # --- F19: Toolbar am unteren Rand der Vorschauspalte ---
        # Aufbau inkl. Einstellungs-Knopf, CSS-Feintuning und Tasten-
        # kürzel (Strg+Alt+P) liegt im Toolbar-Modul (F29).
        self._build_toolbar(window)

        self._show_placeholder()

        # B3: Beim Abbauen des Panels Wiedergabe und Timer sauber stoppen
        self.connect("destroy", self._on_panel_destroy)


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
        # Skalier-Quellen freigeben (Speicher der vollen Auflösung)
        self._scale_items = []
        # ebenso die Quell-Pixbufs der PDF-Seiten; die Render-Generation
        # hochzählen, damit laufende Idle-Nachschub-Schritte (R2)
        # abbrechen, statt in eine verwaiste Ansicht hinein zu malen.
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_box = None
        self._pdf_last_w = 0
        self._pdf_page_label = None
        self._pdf_count = 0
        self._pdf_gen += 1
        # F24: War die gerade abgebaute Vorschau eine Text-Vorschau?
        self._last_textish = False

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
        elif mime == "image/svg+xml" or lower.endswith(".svg"):
            self._render_svg(path)
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
        elif lower.endswith((".md", ".markdown")):
            self._render_markdown(path)
        elif lower.endswith(".eml") or mime == "message/rfc822":
            self._render_eml(path)
        elif mime == "application/epub+zip" or lower.endswith(".epub"):
            self._render_epub(path)
        elif (mime in ("application/x-fictionbook+xml",
                       "application/x-fictionbook")
              or lower.endswith(".fb2")):
            self._render_fb2(path)
        elif (mime == "application/x-mobipocket-ebook"
              or lower.endswith((".mobi", ".prc", ".azw", ".azw3"))):
            self._render_mobi(path)
        elif (mime in ("font/ttf", "font/otf", "font/collection",
                       "application/x-font-ttf", "application/x-font-otf",
                       "application/vnd.ms-opentype")
              or lower.endswith((".ttf", ".otf", ".ttc"))):
            self._render_font(path)
        elif mime.startswith("text/") or os.path.splitext(lower)[1] in _TEXT_EXTRAS:
            self._render_text(path)
        elif os.path.splitext(lower)[1] in _OFFICE_EXTS:
            self._render_office(path)
        elif not os.path.splitext(lower)[1] and _sniff_is_text(path):
            # → REF PAN-F23-1
            self._render_text(path)
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
        F12 (0.13.0): Eine gezogene Breite wird außerdem zur künftigen
        STARTBREITE – sie steht dann als aktueller Wert im Einstellungs-
        fenster und landet entprellt in der conf. Das Tracking liegt VOR
        der 12-px-Render-Schwelle, damit auch kleine Züge zählen.
        """
        try:
            width = allocation.width
            if (width >= PANEL_MIN_WIDTH
                    and width != self._panel_width):
                self._panel_width = width
                self._panel_width_schedule_save()
            if abs(width - self._render_width) < 12:
                return
            self._render_width = width
            self._apply_scale()
            self._apply_pdf_scale()
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
        R3: Skalier-Parameter liegen als Python-Daten-Dict JEWEILS am
        Bild-Eintrag in self._scale_items statt in Panel-Einzelattributen
        – mehrere live-skalierte Bilder pro Vorschau (Cover +
        Kapitelbilder …) überschreiben sich damit nicht mehr gegenseitig.
        (Bewusst NICHT Gtk set_data/get_data: PyGObject blockiert die
        GObject-Daten-Methoden mit 'Data access methods are unsupported'
        – das Panel stürzte sonst beim ersten Bild ab.)
        Gibt den fertigen Container (Gtk.ScrolledWindow) zurück.
        """
        img = Gtk.Image()
        # Horizontal mittig: kleine Vorschauen (Cover, Office-Miniatur)
        # kleben nicht am linken Rand, sondern sitzen zentriert.
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.START)
        scroll = Gtk.ScrolledWindow()
        # AUTOMATIC in beide Richtungen: bricht die Weitergabe der
        # Kind-Minimalbreite nach oben ab, das Pane bleibt frei ziehbar.
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
        item = {"img": img, "scroll": scroll, "src": src, "maxh": max_h,
                "upscale": upscale, "maxup": max_upscale,
                "keeph": keep_height, "lastw": 0}
        if self._scale_items is None:
            self._scale_items = []
        self._scale_items.append(item)
        self._apply_scale()
        return scroll

    def _apply_scale(self):
        """Angezeigte Pixbufs ALLER registrierten Vorschau-Bilder an die
        aktuelle Panelbreite anpassen (R3: Liste statt Einzel-Slot;
        Einträge sind Daten-Dicts, siehe _scaled_image)."""
        if not self._scale_items:
            return
        for item in self._scale_items:
            try:
                src = item["src"]
                if src is None:
                    continue
                sw, sh = src.get_width(), src.get_height()
                if sw <= 0 or sh <= 0:
                    continue
                target = self._preview_width()
                f = float(target) / sw
                if f > 1.0:
                    if item["upscale"]:
                        # Hochskalieren, aber begrenzt: kleine Quellen
                        # (Office-Miniaturansichten) werden sonst unleserlich.
                        f = min(f, item["maxup"])
                    else:
                        f = 1.0      # kleine Bilder nicht unscharf aufblasen
                if f * sh > item["maxh"]:
                    f = float(item["maxh"]) / sh
                w = max(1, int(sw * f))
                h = max(1, int(sh * f))
                if abs(w - item["lastw"]) < 4:
                    continue
                item["lastw"] = w
                # Beim Hochskalieren qualitativ besser interpolieren
                interp = (GdkPixbuf.InterpType.HYPER if f > 1.0
                          else GdkPixbuf.InterpType.BILINEAR)
                item["img"].set_from_pixbuf(src.scale_simple(w, h, interp))
                # → REF PAN-BILD-1
                if item["keeph"]:
                    item["scroll"].set_min_content_height(h)
                    item["scroll"].get_vadjustment().set_value(0)
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

    def _text_view(self, text, font="9", markup=None, linenumbers=False):
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
        bleiben ohne.
        """
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        if font is not None:
            view.override_font(Pango.FontDescription(font))
        # Innenabstand, damit der Text nicht am Rand klebt
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        if linenumbers:
            self._install_line_numbers(view, font)
        buf = view.get_buffer()
        if markup is not None:
            buf.insert_markup(buf.get_end_iter(), markup, -1)
        else:
            buf.set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)
        self._last_textish = linenumbers
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
        try:
            if font is not None:
                probe.set_font_description(Pango.FontDescription(font))
            else:
                fd = view.get_pango_context().get_font_description()
                if fd is not None:
                    probe.set_font_description(fd)
        except Exception:
            pass
        # 0.16.1: get_pixel_size() statt get_pixel_width() – die
        # GI-Bindung bietet get_pixel_width nicht an (Testfeld:
        # AttributeError im Moment der Randbreiten-Messung).
        pw, _ph = probe.get_pixel_size()
        view.set_left_margin(pw + 16)

        def _on_draw(view, cr):
            try:
                vis = view.get_visible_rect()
                it, _top = view.get_line_at_y(vis.y)
                if it is None:
                    return False
                color = ctx.get_color(view.get_state_flags())
                cr.set_source_rgba(color.red, color.green, color.blue,
                                   color.alpha * 0.6)
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
            except Exception:
                pass
            return False

        view.connect("draw", _on_draw)

    # --- E-Books: EPUB, FictionBook, MOBI -----------------------------------

    def _meta_grid(self, rows):
        """
        Schlüssel-Wert-Tabelle (dim-Label links, Wert rechts mit
        END-Ellipsize und Tooltip) – zentraler Helfer für E-Book-,
        EML-, Audio- und Video-Infos. 0.9.1: zuvor zusätzlich mehrfach
        identisch inline gebaut; die Inline-Kopien sind entfallen.
        """
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
            vl.set_tooltip_text(v)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._content.pack_start(grid, False, False, 0)

    def _render_folder(self, path):
        """
        Ordner-Vorschau: Ordner-Icon plus Anzahl der Einträge.
        K1 (Kompromiss statt nur-sichtbar-zählen): Es wird ALLES
        gezählt, der Nutzer aber informiert – versteckte Einträge
        werden separat ausgewiesen: „Der Ordner enthält X Dateien,
        davon X versteckt." So stimmt die Zahl mit `ls -A` überein,
        ohne dass versteckte Dateien stillschweigend fehlen.
        """
        total = hidden = 0
        ok = False
        try:
            with os.scandir(path) as it:
                for entry in it:
                    total += 1
                    if entry.name.startswith("."):
                        hidden += 1
            ok = True
        except Exception:
            pass
        if not ok:
            self._hint("Ordner")
        elif total == 0:
            self._hint("Der Ordner ist leer.")
        else:
            unit = "Datei" if total == 1 else "Dateien"
            if hidden > 0:
                self._hint("Der Ordner enthält %d %s, davon %d versteckt."
                           % (total, unit, hidden))
            else:
                self._hint("Der Ordner enthält %d %s." % (total, unit))
        big = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
        big.set_pixel_size(128)
        self._content.pack_start(big, True, True, 0)

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

    def _on_panel_destroy(self, *a):
        """Panel wird abgebaut: Wiedergabe und Timer stoppen (B3)."""
        # 0.9.1: Abbau markieren – der child-watch einer noch laufenden
        # LibreOffice-Konvertierung (_office_job_done) verwirft sein
        # Ergebnis dann, statt auf das tote Panel zu rendern.
        self._destroyed = True
        self._stop_playback()
        if self._playbin is not None:
            try:
                self._playbin.get_bus().remove_signal_watch()
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

    def _config_load(self):
        """
        F12 (0.12.0): Einstellungen aus CONF_FILE lesen. Ohne Datei
        oder bei JEGLICHEM Fehler gelten die Defaults – eine kaputte
        oder halb geschriebene Konfiguration darf Nemo niemals am
        Start hindern. Neue Einstellungen docken als get_boolean/
        get_string mit try/except hier an.
        """
        if _KEYFILE_CLS is None:
            dbg("GLib.KeyFile fehlt im Binding – Konfiguration "
                "bleibt auf Defaults")
            return
        try:
            kf = _KEYFILE_CLS()
            kf.load_from_file(CONF_FILE, _KEYFILE_FLAGS_NONE)
            try:
                self._conf_show_at_start = kf.get_boolean(
                    "previewer", "show_at_start")
            except Exception:
                pass
            try:
                self._conf_text_linenumbers = kf.get_boolean(
                    "previewer", "text_line_numbers")
            except Exception:
                pass
            try:
                w = kf.get_integer("previewer", "panel_width")
                if PANEL_MIN_WIDTH <= w <= 2400:
                    self._panel_width = int(w)
            except Exception:
                pass
            self._panel_width_saved = self._panel_width
        except Exception:
            pass

    def _config_save(self):
        """
        F12 (0.12.0): Einstellungen sofort in CONF_FILE schreiben
        (Verzeichnis bei Bedarf anlegen). Aufgerufen nach jeder
        Änderung im Einstellungsfenster – ein separater Speichern-
        Knopf ist damit unnötig.
        """
        if _KEYFILE_CLS is None:
            dbg("GLib.KeyFile fehlt im Binding – Konfiguration "
                "nicht speicherbar")
            return
        try:
            os.makedirs(CONF_DIR, exist_ok=True)
            kf = _KEYFILE_CLS()
            kf.set_boolean("previewer", "show_at_start",
                           self._conf_show_at_start)
            kf.set_boolean("previewer", "text_line_numbers",
                           self._conf_text_linenumbers)
            kf.set_integer("previewer", "panel_width",
                           int(self._panel_width))
            kf.save_to_file(CONF_FILE)
        except Exception as exc:
            dbg("Konfiguration nicht speicherbar: %s" % exc)

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
            dbg("Start-Einstellung: Vorschauspalte bleibt zu Beginn "
                "ausgeblendet")

    def _panel_width_schedule_save(self):
        """
        F12 (0.13.0): Gezogene Breite erst speichern, wenn der
        Trenner stillsteht (~800 ms) – nicht bei jedem Zieh-Pixel.
        Der laufende Timer wird dabei jeweils ersetzt.
        """
        try:
            if self._panel_width_timer:
                GLib.source_remove(self._panel_width_timer)
            self._panel_width_timer = GLib.timeout_add(
                800, self._panel_width_save)
        except Exception:
            self._panel_width_timer = 0

    def _panel_width_save(self):
        """
        F12 (0.13.0): Breite in die conf schreiben, sobald sie sich
        gegen den zuletzt gespeicherten Wert geändert hat. Ist das
        Einstellungsfenster offen, zieht der SpinButton nach (außer
        der Nutzer tippt dort gerade) und die „aktuell"-Zeile wird
        frisch gesetzt.
        """
        self._panel_width_timer = 0
        try:
            if self._panel_width != self._panel_width_saved:
                self._panel_width_saved = self._panel_width
                self._config_save()
                dbg("Panelbreite (gezogen) gespeichert: %d px"
                    % self._panel_width)
        except Exception:
            pass
        try:
            if self._settings_spin is not None:
                if not self._settings_spin.has_focus():
                    self._settings_spin.set_value(self._panel_width)
            self._update_width_hint()
        except Exception:
            pass
        return False

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
        except Exception:
            pass



PREVIEWER_VERSION = "0.16.1"
dbg("previewer_panel %s geladen (F28/F29/F31 Struktur-Release: Kern "
    "behält Dispatch, Helfer und Konfiguration – Renderer als Mixins "
    "in eigenen Modulen, Toolbar samt Einstellungen ausgelagert; alle "
    "Deckel und Fixes bleiben)"
    % PREVIEWER_VERSION)