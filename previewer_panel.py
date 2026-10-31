#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Panel-Modul (previewer_panel.py)
============================================

STAND: Version 0.29.0 – F43-Feinschliff (Nutzer-Wunsch): Ordner-Vorschau trägt Icons vor den Namen (Typ-Symbol aus dem Icon-Theme, MENU-Größe, mit Fallback) und den Innenabstand der Text-Vorschauen (10/10/8/8 px).
F44-Nachtrag (0.28.1, Nutzer-Wunsch): Syntax-Hervorhebung ist EINSTELLBAR – Schlüssel text_syntax, Rubrik „Textdateien“, Default an; ausgeschaltet oder ohne GtkSource-Binding zeigt sich immer der schlichte Text.
F44 (0.28.0): Syntax-Hervorhebung in der Text-Vorschau – GtkSourceView
(optionales Binding gir1.2-gtksource-4, dasselbe Modul wie xed),
Sprache über den GtkSource-LanguageManager geraten, dunkles Theme
bekommt ein dunkles Schema (→ REF PAN-F44-1).
F12 Teil 3/F14 (0.27.0): Der Seiten-Deckel für PDF- und Office-
Dokumente ist EINSTELLBAR – conf-Schlüssel
doc_page_limit/doc_max_pages, Defaults wie bisher (Begrenzung an,
20 Seiten); Merker _last_docview lässt Deckel-Änderungen live auf
die aktuelle Dokument-Vorschau wirken (→ REF PAN-F12-1).
F7 (0.26.0): Visitenkartenformate – vCard (.vcf/.vcard), LDIF
(.ldif), Windows-Contact (.contact) – rendert die Visitenkarte aus
dem Text-Modul (→ REF PAN-VCARD-1). F43: Ordner-Vorschau zeigt den
Inhalt als Liste statt nur eines Ordner-Icons (→ REF PAN-FOLDER-1).
F40: Kopfzeile trägt nur noch den Öffnen-Knopf (Stift-Symbol
document-edit) – der Ausblenden-Knopf ist in Nemos Werkzeugleiste
gewandert. F38: _meta_grid bekommt einen optionalen container – die
EXIF-Tabelle der Bild-Vorschau packt in den 40-%-Info-Bereich der
neuen Aufteilung. Sonstiger Stand: Zeilennummern als Randzeichnung –
dunkler (Alpha 0.75) und in 80 % der Textschriftgröße –, connect_after-
Draw, Merker _last_textish markiert TextView-basierte Vorschauen.
Schlüssel text_line_numbers, Rubrik „Textdateien“ im Toolbar-Modul.

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
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
)
from previewer_render_media import MediaRendererMixin, HAVE_GST
from previewer_render_docs import (
    DocsRendererMixin, HAVE_POPPLER, _OFFICE_EXTS,
)
from previewer_render_text import TextRendererMixin
from previewer_toolbar import PreviewToolbarMixin

# → REF PAN-F44-1
HAVE_GTKSOURCE = False
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAVE_GTKSOURCE = True
except Exception:
    pass

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
        # 0.17.0: Spaltenhöhe für die Bild-Höhenkappe mitverfolgen
        # (max. 60 % der Spalte, Nutzer-Wunsch).
        self._render_height = 0
        # Skalierbare Vorschauen (R3): JEDES Bild bringt seine Parameter
        # als eigenen Dict-Eintrag mit (siehe _scaled_image) – so sind
        # beliebig viele live-skalierte Bilder pro Vorschau möglich,
        # ohne sich gegenseitig zu überschreiben.
        self._scale_items = []
        # F38: 40-%-Info-Bereich der Bild-Aufteilung (gesetzt, sobald
        # _pack_image_capped die Spalte für eine Bild-Vorschau teilt).
        self._image_info_box = None
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
        # F44-Nachtrag (0.28.1, Nutzer-Wunsch): Syntax-Hervorhebung
        # als EINSTELLUNG – Rubrik „Textdateien“, Default an; greift
        # live über _last_textish.
        self._conf_text_syntax = True
        # F12 Teil 3 (0.27.0): Dokument-Deckel einstellbar – PDF- und
        # Office-Vorschauen begrenzen (Performance) oder komplett
        # anzeigen. Defaults: Begrenzung AN mit 20 Seiten – genau das
        # bis dahin fest verdrahtete Verhalten (MAX_PDF_PAGES im
        # Docs-Modul).
        self._conf_doc_page_limit = True
        self._conf_doc_max_pages = 20
        # F12 Teil 3: Merker – ist die AKTUELLE Vorschau eine PDF-/Office-
        # Seitenansicht? Dann wirken Deckel-Änderungen sofort (Gegen-
        # stück zu _last_textish der Zeilennummern).
        self._last_docview = False
        # Merker: Ist die AKTUELLE Vorschau TextView-basiert, der
        # Zeilennummern-Toggle also billig anwendbar? (Damit der
        # Einstellungs-Toggle nur solche Vorschauen neu rendert,
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
        self._settings_pages_spin = None
        self._config_load()

        # --- Kopfzeile (F35: nur noch Bedienelemente – Icon, Name,
        # Typ, Größe und Datum stehen bereits in der Nemo-Liste und
        # wären dort Doppelungen) ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)

        # Öffnen-Knopf (F40: Systemausführungs-Symbol statt Dokument-
        # Öffnen – es startet ja die Datei in IHRER Anwendung). Der
        # Ausblenden-Knopf ist als Vorschau-Umschalter in Nemos
        # Titelleiste aufgewacht (→ REF ENT-TOGGLE-1).
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
        # F38: Info-Bereich der letzten Bild-Vorschau freigeben.
        self._image_info_box = None
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
        # F12 Teil 3: War sie eine Dokument-Seitenansicht (PDF/Office)?
        self._last_docview = False

    def _show_placeholder(self):
        # F35: Die frühere Kopfzeile ist entfallen – der Platzhalter-
        # Text im Inhaltsbereich genügt als Zustandsmeldung.
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
            # F35: Der Name steht in der Nemo-Liste – übrig bleibt nur
            # der Warnhinweis, und zwar im Inhaltsbereich.
            self._hint("(Datei nicht gefunden)")
            return

        mime, size, mtime = query_file_info(path)
        is_dir = os.path.isdir(path)

        # F35: Die frühere Kopfzeilen-Füllung (Icon, Name, Typ · Größe ·
        # Änderungsdatum) ist entfallen – die Nemo-Liste zeigt all das
        # bereits neben der Vorschau-Spalte.

        uri = GLib.filename_to_uri(path)
        lower = path.lower()

        # --- nach Typ rendern ---
        if is_dir:
            self._render_folder(path)
        elif mime == "image/svg+xml" or lower.endswith(".svg"):
            self._render_svg(path)
        elif (mime.startswith("image/") or
              mime == "application/x-xpixmap" or
              lower.endswith((".heic", ".heif", ".hif"))):
            # F42: HEIC-Endungen als Backup, falls shared-mime-info
            # den Typ (noch) nicht kennt.
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
        elif (lower.endswith((".vcf", ".vcard", ".ldif", ".contact"))
              or mime == "text/vcard"):
            # F7: Visitenkartenformate – vCard, LDIF, Windows-Contact
            # (Renderer im Text-Modul).
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
            height = allocation.height
            if (width >= PANEL_MIN_WIDTH
                    and width != self._panel_width):
                self._panel_width = width
                self._panel_width_schedule_save()
            # 0.17.0: Höhenänderungen (Fenster-Resize) lösen ebenfalls
            # eine Live-Anpassung aus – die Bild-Höhenkappe koppelt an
            # die aktuelle Spaltenhöhe. Vor dem 12-px-Filter, sonst
            # bliebe die Kappe bei kleineren Fensterzügen stehen.
            if (height > 100
                    and abs(height - self._render_height) >= 12):
                self._render_height = height
                self._apply_scale()
            if abs(width - self._render_width) < 12:
                return
            self._render_width = width
            self._apply_scale()
            self._apply_pdf_scale()
        except Exception:
            pass

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
                "keeph": keep_height, "frac": frac_h, "lastw": 0}
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
                maxh = item["maxh"]
                if item["frac"]:
                    # 0.17.0: Höhenkappe – Bruchteil der SPALTENHÖHE
                    # (Bild-Vorschau: 60 %), live bei Fenster-Resize.
                    maxh = min(maxh, max(1, int(item["frac"] *
                                                 self._preview_height())))
                target = self._preview_width()
                f = float(target) / sw
                if f > 1.0:
                    if item["upscale"]:
                        # Hochskalieren, aber begrenzt: kleine Quellen
                        # (Office-Miniaturansichten) werden sonst unleserlich.
                        f = min(f, item["maxup"])
                    else:
                        f = 1.0      # kleine Bilder nicht unscharf aufblasen
                if f * sh > maxh:
                    f = float(maxh) / sh
                w = max(1, int(sw * f))
                h = max(1, int(sh * f))
                # 0.17.0: Zusätzlich HÖHE vergleichen – die Höhenkappe
                # kann sich bei gleichbleibender Breite ändern (Fenster
                # höher/niedriger gezogen).
                if (abs(w - item["lastw"]) < 4
                        and abs(h - item.get("lasth", -1)) < 4):
                    continue
                item["lastw"] = w
                item["lasth"] = h
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
        except Exception:
            pass
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
            except Exception:
                pass
            if dark:
                for sid in ("oblivion", "solarized-dark"):
                    if sid in ids:
                        return mgr.get_scheme(sid)
            if "classic" in ids:
                return mgr.get_scheme("classic")
        except Exception:
            pass
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
        """
        # F44 (0.28.0): Quellcode hervorheben – nur wenn das GtkSource-
        # Binding da ist, der LanguageManager eine Sprache erkennt UND
        # die Einstellung text_syntax angeschaltet ist (0.28.1,
        # Nutzer-Wunsch; Default an).
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
                    dbg("F44: Syntax-Hervorhebung aktiv (%s)"
                        % lang.get_name())
                except Exception as exc:
                    dbg("Syntax-Hervorhebung nicht aktivierbar (%s) – "
                        "zeige normalen Text" % exc)
                    view = None
        if view is None:
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
        # 0.16.2: Merker immer True setzen – „aktuelle Vorschau ist
        # TextView-basiert (billig neu renderbar)“. Vorher stand hier
        # der linenumbers-Schalter, deshalb wirkte der Einstellungs-
        # Toggle nur beim Deaktivieren: Nach dem Abschalten war der
        # Merker False und das erneute Aktivieren renderte nicht.
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
        # 0.16.3 (Nutzer-Wunsch): Die Nummern zeichnen sich etwas
        # KLEINER als der Text – Grundgröße (Parameter oder Theme-
        # Schrift) holen und auf 80 % skalieren. Die gleiche
        # verkleinerte Probe misst unten die Randbreite, sodass
        # Rand und Nummern-Schrift zusammenpassen. Floor auf 1 pt,
        # damit winzige Größenangaben nicht auf 0 rutschen.
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
        except Exception:
            pass
        # 0.16.1: get_pixel_size() statt get_pixel_width() – die
        # GI-Bindung bietet get_pixel_width nicht an (Testfeld:
        # AttributeError im Moment der Randbreiten-Messung).
        pw, _ph = probe.get_pixel_size()
        view.set_left_margin(pw + 16)

        reported = [False]

        def _on_draw(view, cr):
            # 0.16.2: Exceptions einmalig melden statt still pass –
            # draw feuert oft, das Closure-Flag verhindert Log-Spam.
            try:
                vis = view.get_visible_rect()
                it, _top = view.get_line_at_y(vis.y)
                if it is None:
                    return False
                color = ctx.get_color(view.get_state_flags())
                # 0.16.3 (Nutzer-Wunsch): Alpha 0.6 → 0.75 – auf
                # hellem Grund waren die Nummern zu verwaschen;
                # etwas dunkler, gut lesbar, aber klar kleiner
                # als der Text und so unterscheidbar.
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
                    dbg("Zeilennummern-Zeichnung fehlgeschlagen: %r" % exc)
            return False

        # 0.16.2: connect_after statt connect – "draw" ist ein
        # RUN_LAST-Signal; der User-Handler liefe VOR der Standard-
        # zeichnung, die den Hintergrund füllt und die Nummern
        # übermalt (Testfeld: Platz war da, Nummern blieben unsichtbar).
        view.connect_after("draw", _on_draw)

    # --- E-Books: EPUB, FictionBook, MOBI -----------------------------------

    def _meta_grid(self, rows, container=None):
        """
        Schlüssel-Wert-Tabelle (dim-Label links, Wert rechts mit
        END-Ellipsize und Tooltip) – zentraler Helfer für E-Book-,
        EML-, Audio- und Video-Infos. 0.9.1: zuvor zusätzlich mehrfach
        identisch inline gebaut; die Inline-Kopien sind entfallen.
        F35: Jede Bezeichnung bekommt automatisch einen Doppelpunkt
        am Ende (falls nicht bereits vorhanden).
        F38: Mit optionalem container packt die Tabelle an jede
        Stelle – Bild-Vorschauen geben ihren 40-%-Info-Bereich mit.
        """
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
            # F35: Bezeichnungen enden auf Doppelpunkt.
            if not k.endswith(":"):
                k += ":"
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
        # F38: container schlägt _content – Bild-Tabellen gehören in
        # den 40-%-Info-Bereich der neuen Bild-Aufteilung.
        target = container if container is not None else self._content
        target.pack_start(grid, False, False, 0)

    def _render_folder(self, path):
        """
        F43 (Nutzer-Wunsch): Die Ordner-Vorschau zeigt den Inhalt als
        Liste statt nur eines Ordner-Icons – Ordner zuerst (fett),
        dann Dateien, je alphabetisch; pro Zeile Icon, Name plus
        „Ordner“ bzw. Größe. Seit 0.29.0 (Nutzer-Wunsch): Vor jedem
        Namen das Typ-Icon aus dem Icon-Theme, die Liste trägt den
        Innenabstand der Text-Vorschauen (10/10/8/8 px). K1 bleibt:
        ALLE Einträge zählen, versteckte separat ausweisen – sie
        stehen gedimmt MIT in der Liste,
        nichts fehlt stillschweigend. Riesige Ordner: die ersten
        300 Zeilen im Scroll-Fenster, Rest als Fußzeile – sonst
        baute ein Ordner mit zehntausend Einträgen ebensoviele
        Label-Widgets.
        """
        # → REF PAN-FOLDER-1
        dirs, files = [], []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    (dirs if entry.is_dir() else files).append(
                        entry.name)
        except Exception:
            self._hint("Ordner")
            return
        total = len(dirs) + len(files)
        if total == 0:
            self._hint("Der Ordner ist leer.")
            return
        hidden = sum(1 for n in dirs + files if n.startswith("."))
        unit = "Datei" if total == 1 else "Dateien"
        if hidden > 0:
            self._hint("Der Ordner enthält %d %s, davon %d versteckt."
                       % (total, unit, hidden))
        else:
            self._hint("Der Ordner enthält %d %s." % (total, unit))
        # F43: Anzeige-Reihenfolge – Ordner vor Dateien, je alphabet-
        # isch (case-insensitiv). Versteckte Einträge stehen an ihrer
        # alphabetischen Position, nur gedimmt – so liest sich der
        # Ordner wie in `ls -A`.
        shown = ([(n, True) for n in sorted(dirs, key=str.lower)]
                 + [(n, False) for n in sorted(files, key=str.lower)])
        rest = max(0, len(shown) - 300)
        box = Gtk.ListBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        # 0.29.0 (Nutzer-Wunsch): derselbe Innenabstand wie bei den
        # Text-Vorschauen (10/10/8/8 px)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        for name, is_dir in shown[:300]:
            # 0.29.0 (Nutzer-Wunsch): Typ-Icon vor dem Namen – Ordner
            # über inode/directory, Dateien über den Inhaltstyp, den
            # Gio zum Namen rät; greift das Icon-Theme nicht, bleibt
            # der klassische Fallback
            ic = Gtk.Image()
            try:
                if is_dir:
                    ctype = "inode/directory"
                else:
                    ctype = Gio.content_type_guess(name, None)[0]
                ic.set_from_gicon(Gio.content_type_get_icon(ctype),
                                  Gtk.IconSize.MENU)
            except Exception:
                ic.set_from_icon_name(
                    "folder" if is_dir else "text-x-generic",
                    Gtk.IconSize.MENU)
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
                except Exception:
                    pass
            side.get_style_context().add_class("dim-label")
            side.set_halign(Gtk.Align.END)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=6)
            hbox.pack_start(ic, False, False, 0)
            hbox.pack_start(nm, True, True, 0)
            hbox.pack_start(side, False, False, 0)
            box.add(hbox)
        if rest > 0:
            more = Gtk.Label(label="… und %d weitere" % rest)
            more.get_style_context().add_class("dim-label")
            more.set_halign(Gtk.Align.START)
            box.add(more)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                          Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(box)
        self._content.pack_start(scroll, True, True, 0)
        dbg("Ordner-Liste: %d Einträge, %d Zeilen gebaut"
            % (total, min(300, len(shown))))

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
            # F44-Nachtrag (0.28.1): Syntax-Hervorhebung an/aus.
            try:
                self._conf_text_syntax = kf.get_boolean(
                    "previewer", "text_syntax")
            except Exception:
                pass
            # F12 Teil 3 (0.27.0): Dokument-Deckel (PDF/Office) –
            # Begrenzung ja/nein und maximale Seitenzahl (1–999).
            try:
                self._conf_doc_page_limit = kf.get_boolean(
                    "previewer", "doc_page_limit")
            except Exception:
                pass
            try:
                p = kf.get_integer("previewer", "doc_max_pages")
                if 1 <= p <= 999:
                    self._conf_doc_max_pages = int(p)
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
            # F44-Nachtrag (0.28.1): Syntax-Hervorhebung mitspeichern.
            kf.set_boolean("previewer", "text_syntax",
                           self._conf_text_syntax)
            # F12 Teil 3 (0.27.0): Dokument-Deckel mitspeichern.
            kf.set_boolean("previewer", "doc_page_limit",
                           self._conf_doc_page_limit)
            kf.set_integer("previewer", "doc_max_pages",
                           int(self._conf_doc_max_pages))
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



PREVIEWER_VERSION = "0.29.0"
dbg("previewer_panel %s geladen (F28/F29/F31 Struktur-Release: Kern "
    "behält Dispatch, Helfer und Konfiguration – Renderer als Mixins "
    "in eigenen Modulen, Toolbar samt Einstellungen ausgelagert; alle "
    "Deckel und Fixes bleiben)"
    % PREVIEWER_VERSION)