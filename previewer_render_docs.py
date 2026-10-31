#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Renderer-Modul Dokumente (previewer_render_docs.py)
===============================================================

STAND: Version 0.31.2 – F12 Teil 3/F14 (Nutzer-Wunsch): Der Seiten-
Deckel ist einstellbar – ausgeschaltet zeigt die Vorschau ALLE
Seiten, eingeschaltet die konfigurierte Anzahl (Default 20, wie
bisher MAX_PDF_PAGES); das Seiten-Label steht jetzt über jedem
Dokument – auch einseitige zeigen „Seite 1 von 1“ – und zählt im
Format „Seite X von Y“. F39: Ältere Office-Formate ohne ZIP-Anteil
(.doc/.xls/.ppt, RTF) werden über die LibreOffice-Konvertierung
scharf gerendert; die Übergangsansicht zeigt saubere Hinweise
(→ REF DOC-LEGACY-1). K2: Kaputtes Office-ZIP zeigt das Datei-Icon
neben der Fehlermeldung. (0.15.0/F31: aus dem Panel-Kern hierher
gezogen; Lese- und Decode-Deckel 0.9.2 unverändert.)

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
"""

import os
import sys
import hashlib
import shutil
import zipfile
import re
import tempfile
import xml.etree.ElementTree as ElementTree

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    MAX_IMAGE_HEIGHT,
    _zf_read_capped, _pixbuf_from_bytes,
)

# --- Optionale Module (Fehlen ist kein Fehler, nur weniger Vorschau) ---

# Poppler + pycairo für die PDF-Vorschau (Seiten als Pixbuf).
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
    ".doc", ".xls", ".ppt",                           # MS Office (F39)
    ".rtf",                                           # RTF (F39)
}
# F39: Office-Formate OHNE ZIP-Anteil – keine eingebettete
# Miniaturansicht, einzig die LibreOffice-Konvertierung bringt eine
# Vorschau: die binären MS-Formate und RTF.
_OFFICE_NOZIP_EXTS = {".doc", ".xls", ".ppt", ".rtf"}
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
        # 0.9.2: Lese-Deckel gegen Dekompressionsbomben – auch der
        # Textauszug braucht nur den Anfang des Dokuments (die Grenze
        # _OFFICE_MAX_TEXT_CHARS schneidet ohnehin weit davor).
        root = ElementTree.fromstring(
            _zf_read_capped(zf, entry, _OFFICE_XML_CAP))
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


# PDF: alle Seiten bis zu dieser Obergrenze scrollbar untereinander –
# seit 0.27.0 (F12 Teil 3) nur noch der DEFAULT: Wirksam ist die
# Einstellung doc_max_pages (doc_page_limit aus = unbegrenzt).
MAX_PDF_PAGES = 20
# 0.9.2 (Audit „Pufferüberlauf/OOM“): Deckel gegen Dekompressions- und
# Dekodierbomben – ein präpariertes Bild/PDF/EPUB/DOCX/EML darf Nemo
# niemals durch Riesen-Allokationen abschießen.
_PDF_PIXEL_BUDGET = 4096 * 4096      # Fläche je PDF-Seite (sonst ~1,6 GB)
_OFFICE_THUMB_CAP = 16 * 1024 * 1024  # eingebettete Office-Miniatur
_OFFICE_XML_CAP = 2 * 1024 * 1024     # content.xml / word/document.xml


# ========================= Renderer: Dokumente ==============================


class DocsRendererMixin:
    """Mixin: Renderer für PDF- und Office-Dokumente."""

    def _pdf_page_pixbuf(self, page, target_w):
        """Eine PDF-Seite auf target_w Pixel Breite rendern (weiße Unterlage)."""
        pw, ph = page.get_size()
        # Mit doppelter Zielbreite rendern, damit die Live-Skalierung
        # auch beim Ziehen des Trenners scharf bleibt; extrem hohe
        # Seiten werden gedeckelt (Platz und Speicher).
        scale = min(float(target_w) / max(pw, 1.0),
                    2.0 * MAX_IMAGE_HEIGHT / max(ph, 1.0))
        scale = max(0.2, min(3.0, scale))
        w, h = max(1, int(pw * scale)), max(1, int(ph * scale))
        # → REF DOC-BUDGET-1
        if w * h > _PDF_PIXEL_BUDGET:
            f = (_PDF_PIXEL_BUDGET / float(w * h)) ** 0.5
            w, h = max(1, int(w * f)), max(1, int(h * f))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        # Weiße Unterlage: PDF-Seiten dürfen transparente Flächen haben –
        # ohne Unterlage sähen sie auf dunklen Themes unleserlich schwarz aus.
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.paint()
        cr.scale(scale, scale)
        page.render(cr)
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)

    def _pdf_page_cap(self):
        """
        F12 Teil 3 (0.27.0): Wirksamer Deckel für die Dokument-Vorschau
        – 0 heißt unbegrenzt, sonst die Anzahl anzeigbarer Seiten.
        Einstellbar im Einstellungsfenster (Performance); fehlen die
        Konfig-Werte (alte conf, fremdes Binding), gilt der bisherige
        Zustand: Begrenzung mit MAX_PDF_PAGES.
        """
        try:
            if not self._conf_doc_page_limit:
                return 0
            return max(1, min(int(self._conf_doc_max_pages), 999))
        except Exception:
            return MAX_PDF_PAGES

    def _render_pdf(self, path):
        """
        PDF-Vorschau scrollbar: alle Seiten (bis zum eingestellten
        Deckel, sonst alle) werden untereinander in einem scrollbaren
        Bereich gestapelt. Jede Seite wird in doppelter Panelbreite
        gerendert und bei Breitenänderung – wie bei der Bild-Vorschau –
        nur neu skaliert, nicht neu gerendert.
        F14: Über dem Bereich zeigt ein dezentes Label „Seite X von Y“,
        das beim Scrollen auf die Seite am oberen Sichtfensterrand
        nachführt – seit 0.27.0 IMMER, auch einseitige Dokumente
        zeigen „Seite 1 von 1“ (Nutzer-Wunsch).
        R2: Seite 1 wird sofort synchron gerendert, die übrigen Seiten
        piecewise im GLib-Idle nachgeschoben – das Panel steht auch bei
        großen/gescannten PDFs augenblicklich, die UI friert nicht ein.
        """
        doc = Poppler.Document.new_from_file(GLib.filename_to_uri(path), None)
        n = doc.get_n_pages()
        if n == 0:
            self._hint("PDF enthält keine Seiten.")
            return
        cap = self._pdf_page_cap()
        count = n if cap == 0 else min(n, cap)
        self._pdf_count = count
        # F12 Teil 3: Die aktuelle Vorschau ist eine Dokument-Seiten-
        # ansicht – Deckel-Änderungen aus den Einstellungen wirken
        # live darauf (Merker _last_docview).
        self._last_docview = True
        dbg("PDF geöffnet: %d Seite(n), zeige %d untereinander "
            "(scrollbar; Deckel %s)"
            % (n, count, ("%d Seiten" % cap) if cap else "aus"))
        src_w = max(300, self._preview_width() * 2)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._pdf_src = []
        self._pdf_imgs = []
        self._pdf_box = box
        # Seite 1 sofort – erst danach ist das Panel benutzbar.
        try:
            pb = self._pdf_page_pixbuf(doc.get_page(0), src_w)
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            box.pack_start(img, False, False, 0)
            self._pdf_src.append(pb)
            self._pdf_imgs.append(img)
        except Exception as exc:
            dbg("PDF-Seite 1 nicht renderbar: %s" % exc)
        if not self._pdf_src:
            self._hint("PDF konnte nicht gerendert werden.")
            self._pdf_box = None
            return
        # F14 (0.27.0, Nutzer-Wunsch): Seitenanzeige über dem
        # scrollbaren Bereich – IMMER, auch einseitige Dokumente zeigen
        # „Seite 1 von 1“; beim Scrollen zählt sie nach.
        self._pdf_page_label = Gtk.Label(label="Seite 1 von %d" % count)
        self._pdf_page_label.get_style_context().add_class("dim-label")
        self._content.pack_start(self._pdf_page_label, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(box)
        scroll.get_vadjustment().connect("value-changed",
                                         self._on_pdf_scrolled)
        self._content.pack_start(scroll, True, True, 0)
        self._apply_pdf_scale()
        # R2: restliche Seiten je eine pro Idle-Durchlauf nachschieben.
        # Die Generation wird MITGEBEN (nicht später gelesen), damit der
        # Schritt eindeutig weiß, zu welchem Render-Durchlauf er gehört.
        if count > 1:
            GLib.idle_add(self._pdf_idle_step, doc, path, src_w, count, 1,
                          self._pdf_gen)
        if n > count:
            self._hint("Erste %d von %d Seiten – ganze Datei über den "
                       "Öffnen-Knopf betrachten." % (count, n))
        # → REF DOC-F14-1
        self._content.show_all()

    def _pdf_idle_step(self, doc, path, src_w, count, i, gen):
        """R2: eine weitere PDF-Seite im Idle rendern (UI bleibt flüssig).
        Der Index wird im Aufruf geführt, nicht aus len(self._pdf_src)
        abgeleitet – sonst könnte ein Renderfehler zur Endlosschleife
        werden. Rückkehr False: nicht automatisch wiederholen, der
        Nachschub wird jeweils explizit neu angesetzt."""
        try:
            # Abbruch, wenn inzwischen ein neuer Render-Durchlauf lief
            # (Generation hochgezählt) oder die PDF-Ansicht entsorgt
            # wurde (Stale-Check).
            if gen != self._pdf_gen or self._pdf_box is None:
                return False
            pb = self._pdf_page_pixbuf(doc.get_page(i), src_w)
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            self._pdf_box.pack_start(img, False, False, 0)
            img.show()
            self._pdf_src.append(pb)
            self._pdf_imgs.append(img)
            # Nur die neue Seite skalieren – _apply_pdf_scale springt
            # dank Breiten-Schwellenwert früh ab, wenn sich die Panel-
            # breite nicht geändert hat, und würde sie sonst übersehen.
            self._pdf_scale_one(pb, img, self._preview_width())
        except Exception as exc:
            dbg("PDF-Seite %d nicht renderbar: %s" % (i + 1, exc))
        i += 1
        if i >= count:
            return False
        GLib.idle_add(self._pdf_idle_step, doc, path, src_w, count, i, gen)
        return False

    def _on_pdf_scrolled(self, adj):
        """
        F14: Seitenanzeige beim Scrollen nachführen. Aktuell ist die
        Seite, deren Unterkante den oberen Rand des Sichtfensters
        überschreitet – die Seite, über der man gerade steht. Die
        Koordinaten der Seiten-Images sind Box-Koordinaten und damit
        direkt mit dem Stellwert des Scrollbalkens vergleichbar.
        """
        imgs = self._pdf_imgs
        if not imgs or self._pdf_page_label is None:
            return False
        value = adj.get_value()
        page = 1
        for i, img in enumerate(imgs):
            alloc = img.get_allocation()
            if alloc.y + alloc.height > value:
                page = i + 1
                break
        self._pdf_page_label.set_text(
            "Seite %d von %d" % (page, max(1, self._pdf_count)))
        return False

    def _pdf_scale_one(self, src, img, target):
        """Eine PDF-Seite auf die Zielbreite skalieren und zuweisen."""
        sw, sh = src.get_width(), src.get_height()
        f = min(float(target) / sw, 1.0)   # nicht hochskalieren
        w = max(1, int(sw * f))
        h = max(1, int(sh * f))
        img.set_from_pixbuf(
            src.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))

    def _apply_pdf_scale(self):
        """Alle PDF-Seiten an die aktuelle Panelbreite anpassen."""
        srcs = self._pdf_src
        imgs = self._pdf_imgs
        if not srcs or not imgs:
            return
        target = self._preview_width()
        if abs(target - self._pdf_last_w) < 8:
            return
        self._pdf_last_w = target
        try:
            for src, img in zip(srcs, imgs):
                self._pdf_scale_one(src, img, target)
        except Exception:
            pass

    def _render_office(self, path):
        """
        Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX; F39: auch
        DOC/XLS/PPT und RTF) – scharfe Route:
        Ist ein frisches LibreOffice-Konvertierungs-PDF im Cache, wird
        dessen Seiten per Poppler scharf und in voller Panelbreite
        gerendert (identisch zur PDF-Vorschau, scrollbar). Sonst
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
        # F39: Office-Formate ohne ZIP-Anteil (binär + RTF) – der Weg
        # über Miniaturansicht/Textauszug läuft hier ins
        # Leere (→ REF DOC-LEGACY-1).
        if os.path.splitext(path)[1].lower() in _OFFICE_NOZIP_EXTS:
            if converting:
                self._hint("Scharfe Vorschau wird im Hintergrund "
                           "erstellt (LibreOffice) – einen Moment …")
            elif SOFFICE and HAVE_POPPLER:
                # F39: Konvertierung angetreten, aber ohne Ergebnis
                # (kaputte Datei) – nicht endlos erneut ansetzen.
                self._hint("Scharfe Vorschau konnte nicht erstellt "
                           "werden – Datei über den Öffnen-Knopf "
                           "betrachten.")
            else:
                self._hint("Keine Vorschau möglich – LibreOffice "
                           "installieren (Paket libreoffice-core), "
                           "dann konvertiert die Vorschau schar.")
            return
        thumb = None
        text = ""
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                for member in _OFFICE_THUMBS:
                    if member in names:
                        try:
                            # 0.9.2: Lese-Deckel – ein präpariertes
                            # DOCX könnte eine Riesen-Miniatur als
                            # Dekompressionsbombe packen.
                            thumb = _zf_read_capped(zf, member,
                                                    _OFFICE_THUMB_CAP)
                        except Exception:
                            thumb = None
                        break
                text = _extract_office_text(zf, names)
        except Exception as e:
            # K2 (2026-10-30): Nur die Hinweiszeile wirkt leer – das
            # Datei-Icon gibt der Fehlermeldung einen visuellen Anker.
            self._render_generic()
            self._hint("Office-Dokument konnte nicht geöffnet werden: %s" % e)
            return
        shown = False
        if thumb:
            try:
                # 0.9.2: bewachter Loader mit Decode-Deckel.
                pb = _pixbuf_from_bytes(thumb)
                if pb is not None:
                    # → REF DOC-UPSCALE-1
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
            # 0.9.1: über den gemeinsamen TextView-Helfer (zuvor inline
            # identisch gebaut).
            self._text_view(text, font="Monospace 9")
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
        # 0.9.1: Panel ist bereits abgebaut (Fenster zu, Reiter weg) –
        # Ergebnis verwerfen und nur den Temp-Ordner aufräumen; ein
        # Rendern auf das tote Panel wäre vergebliche Liebesmüh'.
        if getattr(self, "_destroyed", False):
            shutil.rmtree(tmpdir, ignore_errors=True)
            return
        try:
            if os.path.exists(out_pdf):
                cache_ok = False
                try:
                    # shutil.move statt os.replace: /tmp liegt häufig auf
                    # einem eigenen Gerät (tmpfs) – rename(2) scheitert dann
                    # mit EXDEV, move kopiert in dem Fall.
                    shutil.move(out_pdf, office_cache_path(path))
                    cache_ok = True
                except Exception as exc:
                    dbg("Office-Cache konnte nicht geschrieben werden: %s"
                        % exc)
                if not cache_ok:
                    # → REF DOC-B4-1
                    self._office_failed.add(path)
                    if len(self._office_failed) > 256:
                        self._office_failed.clear()
                    if self._path == path:
                        try:
                            # Übergangs-Miniaturansicht mit ihrem
                            # „wird konvertiert"-Hinweis entfernen,
                            # sonst steht die scharfe Ansicht UNTER
                            # der Miniaturansicht.
                            self._clear_content()
                            self._render_pdf(out_pdf)
                        except Exception as exc:
                            dbg("Office-PDF aus Temp-Ordner nicht "
                                "darstellbar (%s): %s" % (path, exc))
                elif self._path == path:
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



PREVIEWER_VERSION = "0.31.2"
dbg("previewer_render_docs %s geladen (F31: PDF-/Office-Renderer; "
    "Lese-Deckel und LibreOffice-Cache bleiben)"
    % PREVIEWER_VERSION)