#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer
=========

Eine Nemo-Python-Extension namens "Previewer": dockt rechts im Nemofenster
ein Panel an und zeigt eine gerenderte Vorschau der aktuell selektierten
Datei.

Unterstützte Vorschauen
-----------------------
- Bilder (JPEG, PNG, WebP, GIF, TIFF, ... alles, was Gdk-Pixbuf kennt)
- Text/Quellcode (read-only, monospace)
- PDF (erste Seite; benötigt gir1.2-poppler)
- Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX): eingebettete
  Miniaturansicht plus Textauszug – direkt aus dem ZIP, ohne Zusatzpakete
- Audio (Tags, Cover, Play/Pause mit Seek-Leiste; via GStreamer)
- Video (Erstframe als Standbild, Tags, Dauer)
- Ordner und alles andere: Icon + Dateiinformationen

Installation
------------
1) Diese Datei als previewer.py in den Nemo-Extension-Ordner kopieren:
       ~/.local/share/nemo-python/extensions/previewer.py
   (Ordner ggf. anlegen: mkdir -p ~/.local/share/nemo-python/extensions)

2) Pakete, falls nicht vorhanden:
       sudo apt install nemo-python python3-gi \
            gir1.2-gst-plugins-base-1.0 gir1.2-poppler-0.18 python3-cairo

3) Nemo neu starten:
       nemo -q && nemo

Bedienung
---------
- Panel ein-/ausblenden: Strg+Alt+P (oder den Knopf oben rechts im Panel)
- Trenner zwischen Dateiansicht und Panel ist verschiebbar (Gtk.Paned)
- Play/Pause & Seek bei Audio über die Bedienelemente im Panel

Deinstallation: Datei aus dem extensions-Ordner löschen, Nemo neu starten.

Technik (für Interessierte)
---------------------------
Das offizielle Nemo-Extension-API bietet keinen "Side-Panel-Provider".
Das Panel nutzt deshalb die bewährte Crowbar-Technik von nemo-terminal:
Über Nemo.LocationWidgetProvider erhält man ein Referenz-Widget im Slot,
steigt im Widget-Baum auf und verpackt den Fenster-Inhaltsbereich (den
Nemo-Pane) in ein horizontales Gtk.Paned, dessen zweite Hälfte das
Vorschau-Panel ist – es sitzt damit fest an der rechten Fensterrandkante.

Die Auswahl wird ermittelt über:
- Auswahl-Signale, die zur Laufzeit entdeckt und verbunden werden –
  im Widget-Teilbaum der Ansicht und auf den ATK-Objekten; so ist es
  egal, wie Nemo seine Signale genau benennt,
- direkte Auswahl über NemoView.peek_selection: der Funktionszeiger
  wird dazu aus dem Klassen-VTable von NemoView gelesen (libnemo-private
  ist auf Mint 22 statisch gelinkt, es gibt keine ladbare .so); die
  NemoFile-Einträge werden über ihr NemoFileInfo-Interface befragt,
- Gtk.IconView-/Gtk.TreeView-Auswahl als Fallback (das Nemo-Listenmodell
  trägt den Dateinamen erst in den Attribut-Spalten; Spalte 0 enthält
  das NemoFile-Objekt),
- ATK-Selection, ATK-Zustände und Fokus nur als Fallback für gemappte Views,
- als Sicherheitsnetz einen leichtgewichtigen Timer.

Alle Zugriffe sind defensiv gekapselt (try/except), damit die Extension
Nemo niemals zum Absturz bringen kann. Alles läuft im Nemo-Prozess.

Getestet gegen Nemo 6.x unter Linux Mint 22. Da interne Widget-Strukturen
von Nemo-Updates geändert werden könnten, ist die Injektion mit Fallbacks
und Reconciliation (Prüfung pro Timer-Tick) abgesichert.

Autor: für Mirakuli Teebaum, 2026. Lizenz: GPLv3 oder später.
"""

import os
import re
import sys
import traceback
import urllib.parse
import zipfile
import xml.etree.ElementTree as ElementTree
import ctypes
import ctypes.util
import glob
from datetime import datetime

import gi

gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Atk', '1.0')

from gi.repository import GObject, Nemo, Gtk, Gdk, Gio, GLib, Pango, Atk
from gi.repository import GdkPixbuf

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

# ------------------------------ Konfiguration ------------------------------

PANEL_WIDTH = 340          # Startbreite des Panels in Pixeln
PANEL_MIN_WIDTH = 260      # kleinste erlaubte Breite (durch Ziehen)
POLL_MS = 500              # Timer für Auswahl-Abgleich (Sicherheitsnetz)
MAX_TEXT_BYTES = 256 * 1024
MAX_TEXT_LINES = 2000
MAX_IMAGE_HEIGHT = 1600
TOGGLE_ACCEL_KEY = Gdk.KEY_p
TOGGLE_ACCEL_MODS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK

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


# ------------------------------ Hilfsfunktionen -----------------------------

def dbg(msg):
    """Debug-Ausgabe – sichtbar, wenn Nemo im Terminal gestartet wird."""
    print("[previewer] %s" % msg)


def walk(widget):
    """Alle Widgets im Teilbaum inkl. widget selbst liefern."""
    yield widget
    if isinstance(widget, Gtk.Container):
        try:
            children = widget.get_children()
        except Exception:
            children = []
        for child in children:
            yield from walk(child)


def type_name(w):
    try:
        return w.__gtype__.name
    except Exception:
        return ""


# Nemo's private NemoView API is not exported through the installed GI
# namespace on some Linux Mint builds. These wrappers call only the
# read-only nemo_view_peek_selection() API, after validating the GObject
# pointer against NemoView's registered GType.
_NATIVE_NEMO_API = None
_NATIVE_NEMO_API_TRIED = False
_NATIVE_NEMO_API_MESSAGE_SHOWN = False


class _NativeGList(ctypes.Structure):
    pass


_NativeGList._fields_ = [
    ("data", ctypes.c_void_p),
    ("next", ctypes.POINTER(_NativeGList)),
    ("prev", ctypes.POINTER(_NativeGList)),
]


def _native_nemo_api():
    global _NATIVE_NEMO_API, _NATIVE_NEMO_API_TRIED
    global _NATIVE_NEMO_API_MESSAGE_SHOWN
    if _NATIVE_NEMO_API_TRIED:
        return _NATIVE_NEMO_API
    _NATIVE_NEMO_API_TRIED = True

    candidates = []
    found = ctypes.util.find_library("nemo-private")
    if found:
        candidates.append(found)

    # Nemo packages have used more than one private-library directory/name.
    for pattern in (
            "/usr/lib/*/nemo/libnemo-private.so*",
            "/usr/lib/nemo/libnemo-private.so*",
            "/usr/lib/*/libnemo-private.so*",
            "/usr/lib/libnemo-private.so*",
            "/lib/*/nemo/libnemo-private.so*",
            "/lib/*/libnemo-private.so*"):
        candidates.extend(glob.glob(pattern))
    candidates.extend([
        "libnemo-private.so.2", "libnemo-private.so",
    ])
    candidates = list(dict.fromkeys(candidates))

    errors = []
    lib = None
    selected_path = None
    for candidate in candidates:
        try:
            probe = ctypes.CDLL(candidate)
        except Exception as exc:
            errors.append("%s: %s" % (candidate, exc))
            continue

        missing = [name for name in (
            "nemo_view_get_type", "nemo_view_peek_selection",
            "nemo_file_get_uri") if not hasattr(probe, name)]
        if missing:
            errors.append("%s: Symbole fehlen: %s" %
                          (candidate, ",".join(missing)))
            continue
        lib = probe
        selected_path = candidate
        break

    if lib is None:
        if not _NATIVE_NEMO_API_MESSAGE_SHOWN:
            dbg("Nemo-C-Auswahl-API nicht verfügbar; Bibliothekskandidaten=%r; Details=%r" %
                (candidates, errors[:8]))
            _NATIVE_NEMO_API_MESSAGE_SHOWN = True
        return None

    try:
        view_get_type = lib.nemo_view_get_type
        peek_selection = lib.nemo_view_peek_selection
        file_get_uri = lib.nemo_file_get_uri
        view_get_type.restype = ctypes.c_size_t
        peek_selection.argtypes = [ctypes.c_void_p]
        peek_selection.restype = ctypes.c_void_p
        file_get_uri.argtypes = [ctypes.c_void_p]
        file_get_uri.restype = ctypes.c_void_p

        gobj_name = ctypes.util.find_library("gobject-2.0") or "libgobject-2.0.so.0"
        glib_name = ctypes.util.find_library("glib-2.0") or "libglib-2.0.so.0"
        gobj = ctypes.CDLL(gobj_name)
        glib = ctypes.CDLL(glib_name)
        is_a = gobj.g_type_check_instance_is_a
        is_a.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        is_a.restype = ctypes.c_int
        g_free = glib.g_free
        g_free.argtypes = [ctypes.c_void_p]
        g_free.restype = None

        _NATIVE_NEMO_API = {
            "lib": lib,
            "path": selected_path,
            "view_type": view_get_type,
            "peek_selection": peek_selection,
            "file_get_uri": file_get_uri,
            "is_a": is_a,
            "g_free": g_free,
        }
        if not _NATIVE_NEMO_API_MESSAGE_SHOWN:
            dbg("Nemo-C-Auswahl-API geladen aus %s; NemoView-GType-Prüfung aktiviert" %
                selected_path)
            _NATIVE_NEMO_API_MESSAGE_SHOWN = True
        return _NATIVE_NEMO_API
    except Exception as exc:
        if not _NATIVE_NEMO_API_MESSAGE_SHOWN:
            dbg("Nemo-C-Auswahl-API konnte nicht vorbereitet werden: %s" % exc)
            _NATIVE_NEMO_API_MESSAGE_SHOWN = True
        _NATIVE_NEMO_API = None
        return None


def _gobject_pointer(widget):
    """
    Den GObject-Zeiger eines PyGObject-Wrappers ermitteln. PyGObject legt
    ihn normalerweise als PyCapsule in __gpointer__ ab; manche Builds
    liefern direkt eine Ganzzahl. Beide Varianten werden unterstützt,
    inklusive namenloser Kapseln (PyCapsule_GetPointer verlangt eine
    exakte Namens-Übereinstimmung – bei Namens-Mismatch liefert der alte
    Weg still None zurück).
    """
    capsule = None
    try:
        capsule = getattr(widget, "__gpointer__", None)
    except Exception:
        capsule = None
    if capsule is None:
        return None
    # Variante 1: einige PyGObject-Builds liefern gleich die Adresse.
    if isinstance(capsule, int):
        return capsule
    try:
        get_pointer = ctypes.pythonapi.PyCapsule_GetPointer
        get_pointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        get_pointer.restype = ctypes.c_void_p
        # Erst mit exaktem Namen probieren …
        try:
            get_name = ctypes.pythonapi.PyCapsule_GetName
            get_name.argtypes = [ctypes.py_object]
            get_name.restype = ctypes.c_char_p
            name = get_name(capsule)
            ptr = get_pointer(capsule, name)
            if ptr:
                return ptr
        except Exception:
            pass
        # … dann namenlos (NULL-Name akzeptiert nur namenlose Kapseln).
        return get_pointer(capsule, None)
    except Exception:
        return None


def _read_cptr(addr, offset=0):
    """Zeiger aus dem Prozessspeicher lesen (Adresse addr + offset)."""
    if not addr:
        return None
    try:
        return ctypes.cast(
            addr + offset, ctypes.POINTER(ctypes.c_void_p)).contents.value
    except Exception:
        return None


def _read_size(addr, offset=0):
    """size_t (z.B. GTyp) aus dem Prozessspeicher lesen."""
    if not addr:
        return 0
    try:
        return ctypes.cast(
            addr + offset, ctypes.POINTER(ctypes.c_size_t)).contents.value
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Native Auswahl über den Klassen-VTable von NemoView (peek_selection).
#
# Auf Linux Mint 22 ist libnemo-private eine STATISCHE Bibliothek – es gibt
# keine .so, deren Symbole man laden könnte (der dlopen-Versuch oben bleibt
# als Fallback für ältere Systeme). Nemos Auswahl ist trotzdem erreichbar:
# NemoView hält 'peek_selection' als Funktionszeiger im Klassen-VTable
# (nemo-view.h, NemoViewClass: Index 12 nach GtkScrolledWindowClass), und
# NemoFile implementiert das Interface NemoFileInfo, dessen VTable laut
# nemo-file-info.h 'get_name' (Index 1) und 'get_uri' (Index 2) enthält.
# Die Größe der Eltern-Klasse wird zur LAUFZEIT über GObject.type_query()
# vom tatsächlich gelinkten GTK erfragt – nichts wird geraten. Die Indizes
# sind aus den Mint-22- und Master-Zweigen von nemo-view.h verifiziert.
# ----------------------------------------------------------------------------

_NATIVE_VTABLE_API = None
_NATIVE_VTABLE_TRIED = False
_NATIVE_VTABLE_BROKEN = False
_VTABLE_GUARD_WARNED = False
_VTABLE_CRASH_WARNED = False


def _native_vtable_api():
    """VTable-Zugriff auf NemoView.peek_selection vorbereiten (einmalig)."""
    global _NATIVE_VTABLE_API, _NATIVE_VTABLE_TRIED
    global _NATIVE_VTABLE_BROKEN
    if _NATIVE_VTABLE_TRIED:
        return None if _NATIVE_VTABLE_BROKEN else _NATIVE_VTABLE_API
    _NATIVE_VTABLE_TRIED = True
    try:
        # GType-IDs DIREKT über libgobject holen: PyGObject liefert bei
        # type_from_name() neuerdings ein GType-OBJEKT, das ctypes nicht
        # als Argument akzeptiert ('cannot be interpreted as an integer'
        # – ArgumentError, der die ganze Route lautlos tötete). Der Weg
        # über g_type_from_name aus libgobject liefert garantiert die
        # rohe numerische ID aus derselben GLib-Laufzeit.
        gobj = ctypes.CDLL("libgobject-2.0.so.0")
        type_from_name = gobj.g_type_from_name
        type_from_name.argtypes = [ctypes.c_char_p]
        type_from_name.restype = ctypes.c_size_t
        view_gtype = type_from_name(b"NemoView")
        file_gtype = type_from_name(b"NemoFile")
        iface_gtype = type_from_name(b"NemoFileInfo")
        if not view_gtype or not file_gtype or not iface_gtype:
            dbg("VTable-API: GTypen fehlen "
                "(NemoView=%r NemoFile=%r NemoFileInfo=%r)"
                % (view_gtype, file_gtype, iface_gtype))
            _NATIVE_VTABLE_BROKEN = True
            return None
        ptr_size = ctypes.sizeof(ctypes.c_void_p)
        parent_size = GObject.type_query(Gtk.ScrolledWindow).class_size
        api = {
            "view_gtype": view_gtype,
            "file_gtype": file_gtype,
            "iface_gtype": iface_gtype,
            # NemoViewClass: Eltern-Klasse + 12 Zeiger bis peek_selection
            "peek_offset": parent_size + 12 * ptr_size,
            # NemoFileInfoInterface: GTypeInterface-Kopf (2 Zeiger),
            # dann is_gone(0), get_name(1), get_uri(2)
            "iface_name_off": 3 * ptr_size,
            "iface_uri_off": 4 * ptr_size,
        }
        glib = ctypes.CDLL("libglib-2.0.so.0")
        is_a = gobj.g_type_check_instance_is_a
        is_a.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        is_a.restype = ctypes.c_int
        iface_peek = gobj.g_type_interface_peek
        iface_peek.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        iface_peek.restype = ctypes.c_void_p
        g_free = glib.g_free
        g_free.argtypes = [ctypes.c_void_p]
        g_free.restype = None
        api["is_a"] = is_a
        api["iface_peek"] = iface_peek
        api["g_free"] = g_free
        api["ptr_size"] = ptr_size
        _NATIVE_VTABLE_API = api
        dbg("VTable-API bereit (peek_offset=%d, IntPtr=%d)"
            % (api["peek_offset"], ptr_size))
        return api
    except Exception as exc:
        dbg("VTable-API konnte nicht vorbereitet werden: %s" % exc)
        _NATIVE_VTABLE_BROKEN = True
        return None


def _vtable_selection_names(view):
    """
    Auswahl über NemoView.peek_selection lesen. Gibt (names, supported)
    zurück; supported=False bedeutet, die Strategie ist nicht einsetzbar.
    names=[] ist eine gültige, leere Auswahl.
    """
    global _NATIVE_VTABLE_BROKEN, _VTABLE_GUARD_WARNED
    api = _native_vtable_api()
    if api is None:
        return None, False
    ptr = _gobject_pointer(view)
    if not ptr or not api["is_a"](ptr, api["view_gtype"]):
        # Einmalig melden, WARUM die VTable-Route die Ansicht ablehnt –
        # sonst scheitert diese Wache lautlos (siehe Symbolansicht).
        if not _VTABLE_GUARD_WARNED:
            _VTABLE_GUARD_WARNED = True
            info = ["ptr=%r" % ptr]
            try:
                gp = view.__gpointer__
                info.append("__gpointer__=%r (%s)"
                            % (gp, type(gp).__name__))
            except Exception as exc:
                info.append("__gpointer__-Fehler: %r" % exc)
            try:
                # is_a nie mit NULL-Zeiger aufrufen – das wäre ein
                # Segfault im Nemo-Prozess (try/except hilft dort nicht).
                info.append("is_a=%r" % (api["is_a"](ptr, api["view_gtype"])
                                        if ptr else None))
            except Exception as exc:
                info.append("is_a-Fehler: %r" % exc)
            try:
                info.append("gtype=%s typ_ist_nemo_view=%s"
                            % (view.__gtype__,
                               GObject.type_is_a(
                                   view.__gtype__,
                                   GObject.type_from_name("NemoView"))))
            except Exception as exc:
                info.append("gtype-Fehler: %r" % exc)
            dbg("VTable-Guard fehlgeschlagen (%s): %s"
                % (type_name(view), "; ".join(info)))
        return None, False
    try:
        class_ptr = _read_cptr(ptr)                 # GTypeInstance.g_class
        peek_ptr = _read_cptr(class_ptr, api["peek_offset"])
        if not peek_ptr:
            if not _NATIVE_VTABLE_BROKEN:
                dbg("VTable-API: peek_selection-Zeiger ist NULL – deaktiviert")
            _NATIVE_VTABLE_BROKEN = True
            return None, False
        peek = ctypes.cast(
            peek_ptr,
            ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p))
        node = peek(ptr)
    except Exception as exc:
        if not _NATIVE_VTABLE_BROKEN:
            dbg("VTable-API: Aufruf von peek_selection fehlgeschlagen: %s "
                "– deaktiviert" % exc)
        _NATIVE_VTABLE_BROKEN = True
        return None, False

    str_fn_t = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
    names = []
    seen = set()
    limit = 0
    while node and node not in seen and limit < 4096:
        seen.add(node)
        data = _read_cptr(node)                     # GList.data = NemoFile*
        if data:
            # Plausibilitätsprüfung: Instanz muss wirklich ein NemoFile sein
            # (Der GTyp steht in der Klasse, nicht in der Instanz – deshalb
            # der Weg über g_type_check_instance_is_a.)
            if not api["is_a"](data, api["file_gtype"]):
                if not _NATIVE_VTABLE_BROKEN:
                    dbg("VTable-API: Auswahl-Element ist kein NemoFile – "
                        "deaktiviert")
                _NATIVE_VTABLE_BROKEN = True
                return None, False
            name = ""
            try:
                file_class = _read_cptr(data)       # GTypeInstance.g_class
                iface = api["iface_peek"](file_class, api["iface_gtype"])
                if iface:
                    name_ptr = _read_cptr(iface, api["iface_name_off"])
                    if name_ptr:
                        raw = ctypes.cast(name_ptr, str_fn_t)(data)
                        if raw:
                            try:
                                name = ctypes.string_at(raw).decode(
                                    "utf-8", "replace")
                            finally:
                                api["g_free"](raw)
                    if not name:
                        uri_ptr = _read_cptr(iface, api["iface_uri_off"])
                        if uri_ptr:
                            raw = ctypes.cast(uri_ptr, str_fn_t)(data)
                            if raw:
                                try:
                                    uri = ctypes.string_at(raw).decode(
                                        "utf-8", "replace")
                                finally:
                                    api["g_free"](raw)
                                if uri:
                                    try:
                                        name = Gio.File.new_for_uri(
                                            uri).get_basename() or ""
                                    except Exception:
                                        name = os.path.basename(
                                            urllib.parse.urlparse(uri).path)
            except Exception as exc:
                dbg("VTable-API: Namenszugriff fehlgeschlagen: %s" % exc)
            if name:
                names.append(name)
        node = _read_cptr(node, api["ptr_size"])     # GList.next
        limit += 1
    return names, True


def _nemo_file_name_from_ptr(file_ptr):
    """
    Dateinamen zu einem rohen NemoFile-Zeiger ermitteln (ctypes über das
    NemoFileInfo-Interface). Gibt "" zurück, wenn der Zeiger ungültig ist
    oder die VTable-API nicht bereitsteht. Validiert die Instanz vorher
    gegen den NemoFile-GTyp – ein falscher Zeiger wird nie verfolgt.
    """
    api = _native_vtable_api()
    if not api or not file_ptr:
        return ""
    try:
        if not api["is_a"](file_ptr, api["file_gtype"]):
            return ""
        file_class = _read_cptr(file_ptr)            # GTypeInstance.g_class
        if not file_class:
            return ""
        iface = api["iface_peek"](file_class, api["iface_gtype"])
        if not iface:
            return ""
        str_fn_t = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
        name_ptr = _read_cptr(iface, api["iface_name_off"])
        if name_ptr:
            raw = ctypes.cast(name_ptr, str_fn_t)(file_ptr)
            if raw:
                try:
                    return ctypes.string_at(raw).decode("utf-8", "replace")
                finally:
                    api["g_free"](raw)
        uri_ptr = _read_cptr(iface, api["iface_uri_off"])
        if uri_ptr:
            raw = ctypes.cast(uri_ptr, str_fn_t)(file_ptr)
            if raw:
                try:
                    uri = ctypes.string_at(raw).decode("utf-8", "replace")
                finally:
                    api["g_free"](raw)
                if uri:
                    try:
                        return Gio.File.new_for_uri(uri).get_basename() or ""
                    except Exception:
                        return os.path.basename(urllib.parse.urlparse(uri).path)
    except Exception:
        return ""
    return ""


def _read_native_nemo_selection(view):
    """Return (names, supported); names=[] is a valid empty selection."""
    api = _native_nemo_api()
    if api is None:
        return None, False

    ptr = _gobject_pointer(view)
    if not ptr:
        return None, False

    try:
        view_type = api["view_type"]()
        if not view_type or not api["is_a"](ptr, view_type):
            return None, False

        node_addr = api["peek_selection"](ptr)
        names = []
        seen = set()
        limit = 0
        while node_addr and node_addr not in seen and limit < 4096:
            seen.add(node_addr)
            node = ctypes.cast(node_addr, ctypes.POINTER(_NativeGList)).contents
            file_ptr = node.data
            if file_ptr:
                uri_ptr = api["file_get_uri"](file_ptr)
                if uri_ptr:
                    try:
                        uri = ctypes.string_at(uri_ptr).decode("utf-8", "replace")
                    finally:
                        api["g_free"](uri_ptr)
                    if uri:
                        try:
                            name = Gio.File.new_for_uri(uri).get_basename()
                        except Exception:
                            name = os.path.basename(urllib.parse.urlparse(uri).path)
                        if name:
                            names.append(name)
            node_addr = ctypes.cast(node.next, ctypes.c_void_p).value
            limit += 1
        return names, True
    except Exception as exc:
        dbg("Nemo-C-Auswahl konnte nicht gelesen werden: %s" % exc)
        return None, False


def _dump_widget_tree(view, max_widgets=100):
    """Diagnose actual GTK descendants and their selection-related methods."""
    dbg("Widget-Baum-Diagnose beginnt")
    count = 0
    for w in walk(view):
        if count >= max_widgets:
            dbg("Widget-Baum-Diagnose gekürzt (Limit %d)" % max_widgets)
            break
        count += 1
        methods = []
        for name in (
                "get_selection", "peek_selection", "get_selected_items",
                "get_selected_rows", "get_selected", "get_model",
                "get_selection_count", "get_selected_files",
                "get_selected_uris", "get_path_at_pos"):
            try:
                if callable(getattr(w, name, None)):
                    methods.append(name)
            except Exception:
                pass
        try:
            mapped = bool(w.get_mapped())
        except Exception:
            mapped = False
        dbg("Widget[%d]: %s mapped=%s Methoden=%s" %
            (count, type_name(w), mapped, ",".join(methods) or "-"))
    dbg("Widget-Baum-Diagnose Ende (%d Widgets)" % count)


# --------------------- Signal-Entdeckung & a11y-Helfer -----------------------

# Zwischenablage-/X11-Auswahl-Signale von GtkWidget: heißen zwar
# "selection…", haben aber mit der DATEI-Auswahl nichts zu tun.
_CLIPBOARD_SIGNALS = {
    "selection-get", "selection-received", "selection-clear-event",
    "selection-request-event",
}


def _signals_of_gtype(gtype):
    """void-Signale dieses GTyps mit 'select' im Namen (ohne geerbte)."""
    out = []
    try:
        ids = GObject.signal_list_ids(gtype)
    except Exception:
        return out
    for sid in ids:
        try:
            q = GObject.signal_query(sid)
            name = q.signal_name
            if q.return_type != GObject.TYPE_NONE:
                continue   # Handler müsste etwas zurückgeben – zu riskant
        except Exception:
            continue
        if name and "select" in name.lower() and name not in _CLIPBOARD_SIGNALS:
            out.append(name)
    return out


def selection_signals(widget):
    """
    Alle 'Auswahl'-Signale eines GObjects – inklusive geerbter, indem
    die GTyp-Hierarchie nach oben durchlaufen wird; zusätzlich auch
    die Signale implementierter Interfaces (ATK meldet Auswahl-
    Änderungen z.B. über ein Interface-Signal von AtkSelection).
    Nemo benennt seine Signale nicht garantiert einheitlich (Striche
    vs. Unterstriche); hier wird deshalb nichts geraten, sondern der
    tatsächliche Name zur Laufzeit gelesen. Sortierte Liste, evtl. leer.
    """
    names = []
    try:
        t = widget.__gtype__
    except Exception:
        return names
    seen = set()
    queue = [t]
    while queue:
        t = queue.pop(0)
        if t is None or t in seen:
            continue
        seen.add(t)
        for n in _signals_of_gtype(t):
            if n not in names:
                names.append(n)
        try:
            for itype in GObject.type_interfaces(t):
                queue.append(itype)
        except Exception:
            pass
        try:
            parent = GObject.type_parent(t)
            if parent:
                queue.append(parent)
        except Exception:
            pass
    return sorted(names)


def _atk_children(acc, max_children=200):
    """
    Kinder eines ATK-Objekts defensiv ermitteln. get_n_children() schlägt
    auf manchen Systemen fehl (bei Nemo-Views wurde -1 gemeldet, der a11y-
    Baum schien leer); deshalb wird bei Ausnahme/Unsinn blind ref_child()
    für die ersten Indizes probiert, bis ref_child selbst scheitert.
    Gibt eine (evtl. leere) Liste zurück – nie None.
    """
    children = []
    n = -1
    try:
        n = acc.get_n_children()
    except Exception:
        n = -1
    if isinstance(n, int) and n >= 0:
        for i in range(min(n, max_children)):
            try:
                children.append(acc.ref_child(i))
            except Exception:
                pass
        return children
    # Unbekannte Kinderzahl: blind probieren; ref_child wirft beim ersten
    # ungültigen Index, das ist das natürliche Ende.
    for i in range(max_children):
        try:
            children.append(acc.ref_child(i))
        except Exception:
            break
    return children


def _atk_selection_objects(view, max_depth=12):
    """Alle AtkSelection-Implementoren im a11y-Baum der Ansicht sammeln."""
    implementors = []
    # Niemals ATK auf einer gerade versteckten/abgebauten Ansicht aufrufen.
    try:
        if not isinstance(view, Gtk.Widget) or not view.get_mapped():
            return implementors
        root = view.get_accessible()
        if root is None:
            return implementors
    except Exception:
        return implementors

    def collect(acc, depth):
        if acc is None or depth > max_depth or len(implementors) >= 8:
            return
        try:
            acc.get_selection_count()
            implementors.append(acc)   # AtkSelection implementiert
        except Exception:
            pass
        for child in _atk_children(acc):
            collect(child, depth + 1)

    collect(root, 0)
    return implementors


def is_nemo_view(w):
    """
    Ist dieses Widget eine echte Nemo-DATEI-Ansicht?
    WICHTIG: KEINE Bäume der Seitenleisten! 'NemoPlacesTreeView' (Orte-
    Seitenleiste) beginnt mit 'Nemo' und endet auf 'View', ist aber ein
    GtkTreeView der Seitenleiste – genau dieser Fall hat die Auswahl-
    Erkennung lange unsichtbar sabotiert. Die Erkennung läuft deshalb
    nur positiv: über den Basistyp NemoView oder die bekannten
    Ansichtsnamen, nie über 'beginnt mit Nemo + endet auf View'.
    """
    name = type_name(w)
    # NemoDesktopIconView gehört zum Desktop-Hintergrund, nicht zu einem
    # normalen Dateibrowserfenster. Niemals daran ein Panel injizieren.
    if name == "NemoDesktopIconView":
        return False
    if name in ("NemoIconView", "NemoListView", "NemoCompactView"):
        return True
    if name in ("NemoPlacesTreeView", "NemoTreeView", "NemoTreeSidebar",
                "NemoSearchRecentTreeView", "NemoQueryEditor"):
        return False
    try:
        vt = GObject.type_from_name("NemoView")
        if vt:
            return GObject.type_is_a(w.__gtype__, vt)
    except Exception:
        pass
    return False


def find_view(window):
    """Nur eine aktuell gemappte Nemo-Dateiansicht zurückgeben.

    Beim Ordnerwechsel kann die alte Ansicht noch im Widget-Baum stehen,
    obwohl ihre GObject-Instanz bereits abgebaut wird. Deshalb wird keine
    ungemappte Ansicht mehr als Fallback zurückgegeben.
    """
    try:
        for w in walk(window):
            if not is_nemo_view(w):
                continue
            try:
                if w.get_mapped() and w.get_realized():
                    return w
            except Exception:
                # Das Widget kann gerade zerstört werden.
                continue
    except Exception:
        pass
    return None


def find_paned_above(widget):
    """Der erste Gtk.Paned oberhalb von widget (ohne widget selbst)."""
    p = widget.get_parent()
    while p is not None:
        if isinstance(p, Gtk.Paned):
            return p
        p = p.get_parent()
    return None


def find_slot_box(view):
    """
    Die Gtk.Box, die die Ansicht direkt enthält (Slot-Box).
    Annahme (wie bei nemo-terminal): Die Slot-Box hängt unter einem
    Gtk.Paned und enthält [Location-Widget-Box, Ansicht].
    """
    p = view.get_parent()
    last_box = None
    while p is not None:
        if isinstance(p, Gtk.Box):
            last_box = p
        if isinstance(p, Gtk.Paned):
            return last_box
        p = p.get_parent()
    return last_box


def human_size(num):
    try:
        return GLib.format_size(num)
    except Exception:
        return "%d B" % num


def format_seconds(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


def query_file_info(path):
    """(mime_type, size, mtime) – alle mit Fallbacks."""
    mime, size, mtime = "unbekannt", -1, -1
    try:
        f = Gio.File.new_for_path(path)
        info = f.query_info(
            "standard::size,standard::content-type,time::modified",
            Gio.FileQueryInfoFlags.NONE, None)
        mime = info.get_content_type() or mime
        size = info.get_size()
        mtime = info.get_attribute_uint64("time::modified")
    except Exception:
        pass
    return mime, size, mtime


def content_type_description(mime):
    """
    Menschliche Beschreibung eines Content-Types. Die Funktion lag
    früher im GLib-Namespace (GLib.content_type_get_description) und
    ist in neueren GI-Builds nach Gio gewandert – deshalb werden beide
    versucht, und als letzte Rückfallebene der MIME-Typ selbst
    zurückgegeben (nie raise).
    """
    for owner in (Gio, GLib):
        try:
            fn = getattr(owner, "content_type_get_description", None)
            if callable(fn):
                desc = fn(mime)
                if desc:
                    return desc
        except Exception:
            pass
    return mime


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

    def _show_placeholder(self):
        self._name_label.set_text("Keine Datei ausgewählt")
        self._meta_label.set_text("")
        self._icon_image.set_from_icon_name("edit-find-symbolic",
                                           Gtk.IconSize.DIALOG)
        self._clear_content()
        lbl = Gtk.Label(label="Wähle eine Datei aus,\num eine Vorschau zu sehen.")
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        self._content.pack_start(lbl, True, True, 0)
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

    def _preview_width(self):
        return PANEL_WIDTH - 40

    def _render_image(self, path):
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            path, self._preview_width(), MAX_IMAGE_HEIGHT, True)
        img = Gtk.Image.new_from_pixbuf(pb)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
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
        scale = min(1.0, self._preview_width() / max(pw, 1))
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
        img = Gtk.Image.new_from_pixbuf(pb)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
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
            pb = self._scale_pixbuf(cover, self._preview_width(), 320)
            self._content.pack_start(Gtk.Image.new_from_pixbuf(pb),
                                     False, False, 0)

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
            pb = self._scale_pixbuf(frame, self._preview_width(), 320)
            self._content.pack_start(Gtk.Image.new_from_pixbuf(pb),
                                     False, False, 0)
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
        ODT/ODS/ODP und DOCX/XLSX/PPTX: diese Formate sind ZIP-Archive.
        Zeigt die vom Dokument selbst eingebettete Miniaturansicht
        (Thumbnails/thumbnail.png bzw. docProps/thumbnail.*). Nur wenn
        KEINE Miniaturansicht vorhanden ist, wird ersatzweise ein
        Textauszug aus dem Dokumentinhalt gezeigt.
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
                    pw = self._preview_width()
                    if pb.get_width() > pw:
                        ratio = pw / float(pb.get_width())
                        pb = pb.scale_simple(
                            pw, max(1, int(pb.get_height() * ratio)),
                            GdkPixbuf.InterpType.BILINEAR)
                    img = Gtk.Image.new_from_pixbuf(pb)
                    self._content.pack_start(img, False, False, 0)
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


# ============================ Auswahl-Leser ================================

class SelectionReader:
    """Liest die aktuelle Auswahl der Nemo-Ansicht – mehrstufig."""

    @staticmethod
    def read(view, dir_path):
        """
        Liefert (Liste_von_Namen, Strategie) oder (None, None), wenn die
        Auswahl nicht lesbar war. Es werden ALLE Strategien befragt und
        das erste NICHT-LEERE Ergebnis gewinnt:
        1. NemoView.peek_selection über den Klassen-VTable (primäre API)
        2. NemoView.get_selection()/GI/CTypes, falls verfügbar
        3. Gtk.IconView-/Gtk.TreeView-Auswahl
        4. ATK Selection, SELECTED-State und Fokus als Fallback
        Meldet eine Strategie [] (lesbar, aber nichts selektiert), wird
        trotzdem weitergefragt – eine 'blinde' Strategie blockiert so
        nie die anderen.
        """
        empty_source = None
        for source, fetch in (
                # NemoView.peek_selection über den VTable ist die
                # maßgebliche Quelle: Sie funktioniert in ALLEN Ansichten
                # (Icon, Liste, Kompakt), weil die Ansicht selbst gefragt
                # wird. Alles andere sind Fallbacks.
                ("nemo-vtable", lambda: SelectionReader._read_nemo_vtable(
                    view, dir_path)),
                # NemoView.get_selection() liefert auf Nemo 6.x typischerweise
                # NemoFile-Objekte und ist die maßgebliche API. Erst danach
                # werden GTK- und ATK-Fallbacks versucht.
                ("nemo-selection", lambda: SelectionReader._read_nemo_selection(
                    view, dir_path)),
                ("iconview", lambda: SelectionReader._read_icon_view(
                    view, dir_path)),
                ("treeview", lambda: SelectionReader._read_tree(
                    view, dir_path)),
                ("atk-selection", lambda: SelectionReader._read_atk(view)),
                ("atk-states", lambda: SelectionReader._read_atk_states(view)),
                ("atk-focused", lambda: SelectionReader._read_atk_focused(
                    view, dir_path))):
            try:
                names = fetch()
            except Exception:
                names = None
            if names:
                return SelectionReader._filter(names, dir_path), source
            if names == [] and empty_source is None:
                empty_source = source
        if empty_source is not None:
            return [], empty_source
        return None, None

    @staticmethod
    def _filter(names, dir_path):
        out = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            if dir_path and not os.path.exists(os.path.join(dir_path, n)):
                # Name gehört vermutlich zu keinem Dateieintrag
                continue
            out.append(n)
        if out:
            return out
        # Nichts auflösbar? Rohnamen behalten – so zeigt das Panel,
        # WAS gelesen wurde (wichtig für die Diagnose).
        return [n.strip() for n in names if (n or "").strip()]

    @staticmethod
    def _read_nemo_vtable(view, dir_path):
        """Auswahl über NemoView.peek_selection (VTable) – siehe Modulkopf.

        Gibt None zurück, wenn die Strategie nicht verfügbar ist, sonst
        die (evtl. leere) Namensliste. Eine leere Liste ist eine gültige
        Auswahl, keine Fehlermeldung. Unerwartete Ausnahmen (die read()
        sonst lautlos schlucken würde) werden einmalig mit Ursache
        gemeldet, damit stille Ausfälle sichtbar werden.
        """
        try:
            names, supported = _vtable_selection_names(view)
        except Exception as exc:
            global _VTABLE_CRASH_WARNED
            if not _VTABLE_CRASH_WARNED:
                _VTABLE_CRASH_WARNED = True
                dbg("VTable-Route: unerwartete Ausnahme (%s): %r – %s"
                    % (type_name(view), exc,
                       traceback.format_exc().strip().splitlines()[-1]))
            return None
        if not supported:
            return None
        return names

    @staticmethod
    def _read_nemo_selection(view, dir_path):
        """Liest NemoFile-Objekte zuerst über Nemo's native C-API.

        Einige Mint-GI-Builds exportieren NemoView nicht als Nemo.View.
        In diesem Fall wird die read-only Funktion nemo_view_peek_selection()
        aus libnemo-private verwendet, nachdem der GObject-Zeiger gegen den
        registrierten NemoView-GType geprüft wurde. Falls das nicht geht,
        bleiben die GI-basierten und GTK-Fallbacks aktiv.
        """
        native_names, native_supported = _read_native_nemo_selection(view)
        if native_supported:
            return native_names

        selected = None
        for method_name in ("get_selection", "peek_selection"):
            getter = getattr(view, method_name, None)
            if callable(getter):
                try:
                    selected = getter()
                    break
                except Exception:
                    selected = None
            # Fallback: C-Funktionen aus nemo-view.h können durch GI als
            # Modul-Funktionen erscheinen, obwohl Nemo.View selbst nicht
            # als Python-Attribut exportiert wird (wie bei manchen Mint-Builds).
            api_names = {
                "get_selection": ("view_get_selection", "get_selection"),
                "peek_selection": ("view_peek_selection", "peek_selection"),
            }.get(method_name, ())
            for api_name in api_names:
                try:
                    api = getattr(Nemo, api_name, None)
                    if callable(api):
                        selected = api(view)
                        break
                except Exception:
                    selected = None
            if selected is not None:
                break
        if selected is None:
            return None
        try:
            selected = list(selected)
        except Exception:
            # Manche GI-Bindings geben GList-Elemente als .data/.next-Kette
            # zurück statt als direkt iterierbare Python-Liste.
            chain = []
            node = selected
            seen = set()
            while node is not None and id(node) not in seen and len(chain) < 4096:
                seen.add(id(node))
                item = getattr(node, "data", None)
                if item is not None:
                    chain.append(item)
                node = getattr(node, "next", None)
            if not chain:
                return None
            selected = chain

        names = []
        for item in selected:
            name = None
            for attr in ("get_name", "get_display_name"):
                try:
                    method = getattr(item, attr, None)
                    if callable(method):
                        value = method()
                        if value:
                            name = os.path.basename(str(value))
                            break
                except Exception:
                    pass
            if not name:
                for attr in ("get_uri", "get_uri_scheme"):
                    try:
                        method = getattr(item, attr, None)
                        uri = method() if callable(method) else None
                        if uri and isinstance(uri, str) and "://" in uri:
                            name = Gio.File.new_for_uri(uri).get_basename()
                            break
                    except Exception:
                        pass
            if not name:
                try:
                    method = getattr(item, "get_location", None)
                    location = method() if callable(method) else None
                    if location is not None:
                        name = location.get_basename()
                except Exception:
                    pass
            if name and (not dir_path or os.path.exists(os.path.join(dir_path, name))):
                names.append(name)
        return names

    @staticmethod
    def _read_icon_view(view, dir_path):
        """Direkte GTK-Auswahl für Gtk.IconView-basierte Nemo-Ansichten."""
        for w in walk(view):
            # Nemo kann eine eigene Widget-Klasse verwenden, die nicht als
            # Gtk.IconView typisiert ist, aber dieselben Auswahlmethoden anbietet.
            try:
                get_selected_items = getattr(w, "get_selected_items", None)
                get_model = getattr(w, "get_model", None)
                if not callable(get_selected_items) or not callable(get_model):
                    continue
                model = get_model()
                paths = get_selected_items()
                names = []
                if model is None:
                    continue
                for path in paths:
                    try:
                        it = model.get_iter(path)
                    except Exception:
                        continue
                    candidates = []
                    # Nemo-Modellspalten unterscheiden sich je nach Version;
                    # Dateiname über tatsächliche Existenz im Ordner prüfen.
                    for col in range(min(8, model.get_n_columns())):
                        try:
                            val = model.get_value(it, col)
                        except Exception:
                            continue
                        if isinstance(val, str) and val.strip():
                            val = val.strip()
                            if val not in candidates:
                                candidates.append(val)
                    match = next((v for v in candidates if dir_path and
                                  os.path.exists(os.path.join(dir_path, v))), None)
                    if match:
                        names.append(match)
                # Eine leere Liste ist hier eine gültige, direkt lesbare Auswahl.
                return names
            except Exception:
                continue
        return None

    @staticmethod
    def _read_atk(view):
        """
        Über die Barrierefreiheits-Schnittstelle (Symbolansicht).
        Es werden ALLE AtkSelection-Implementierungen im a11y-Baum der
        Ansicht befragt; die erste mit echter Auswahl gewinnt. So kann
        ein falsches AtkSelection-Objekt (das stets 0 meldet) die echte
        Auswahl nicht mehr verschlucken.
        """
        implementors = _atk_selection_objects(view)
        for acc in implementors:
            try:
                count = acc.get_selection_count()
                if count <= 0:
                    continue
                names = []
                for i in range(count):
                    obj = acc.ref_selection(i)
                    if obj is not None:
                        names.append(obj.get_name() or "")
                if names:
                    return names
            except Exception:
                continue
        if implementors:
            return []          # lesbar, aber nichts selektiert
        return None

    @staticmethod
    def _read_atk_states(view):
        """
        Fallback für die Symbolansicht: über den a11y-Baum der Ansicht
        alle Objekte mit ATK-State SELECTED sammeln und deren Namen
        übernehmen. Liefert die Namen oder None (Baum nicht auswertbar).
        """
        try:
            if not isinstance(view, Gtk.Widget) or not view.get_mapped():
                return None
            root = view.get_accessible()
            if root is None:
                return None
        except Exception:
            return None
        selected = []

        def rec(acc, depth):
            if acc is None or depth > 12:
                return
            name = ""
            try:
                name = acc.get_name() or ""
            except Exception:
                pass
            if name:
                try:
                    states = acc.get_state_set()
                    if (states is not None and
                            states.contains_state(Atk.StateType.SELECTED)):
                        selected.append(name)
                except Exception:
                    pass
            for child in _atk_children(acc):
                rec(child, depth + 1)

        rec(root, 0)
        return selected or None

    @staticmethod
    def _read_atk_focused(view, dir_path):
        """
        Ein-Klick-Fallback: das einzige fokussierte Objekt im a11y-Baum
        benennen. Nach einem einfachen Klick ist das angeklickte Symbol
        fokussiert, auch wenn AtkSelection versagt. Der Name zählt nur,
        wenn er zu einer echten Datei im angezeigten Ordner auflöst.
        """
        if not dir_path:
            return None
        try:
            if not isinstance(view, Gtk.Widget) or not view.get_mapped():
                return None
            root = view.get_accessible()
            if root is None:
                return None
        except Exception:
            return None
        hits = []

        def rec(acc, depth):
            if acc is None or depth > 12 or len(hits) > 1:
                return
            focused, name = False, ""
            try:
                name = (acc.get_name() or "").strip()
                ss = acc.get_state_set()
                focused = (ss is not None and
                           ss.contains_state(Atk.StateType.FOCUSED))
            except Exception:
                pass
            if focused and name and os.path.exists(
                    os.path.join(dir_path, name)):
                hits.append(name)
            for child in _atk_children(acc):
                rec(child, depth + 1)

        rec(root, 0)
        if len(hits) == 1:
            return hits
        return None

    @staticmethod
    def _tree_row_name(model, it, dir_path):
        """
        Dateinamen einer markierten Listenzeile ermitteln.

        Nemos Listenmodell (nemo-list-model.h) speichert in Spalte 0 KEINEN
        String, sondern das NemoFile-Objekt; die Pixbufs folgen in den
        Spalten 1–7, der sichtbare Dateiname steckt erst in einer der
        dynamischen Attribut-Spalten (12+, je nach Sortierung/Spaltenwahl).
        Deshalb zweistufig:
        1. Spalte 0 auslesen: ein PyGObject-Wrapper wird über seine
           NemoFileInfo-Interface-Methoden (get_name/get_uri) befragt –
           genau so lesen alle Nemo-Python-Extensions ihre Dateien.
           Liefert PyGObject nur den rohen Zeiger (int), übernimmt die
           ctypes-Route (_nemo_file_name_from_ptr). Das Ergebnis dient
           als Fallback.
        2. Zusätzlich ALLE Stringspalten scannen und den String
           bevorzugen, der im angezeigten Ordner auf eine echte Datei
           auflöst; sonst den ersten String, ganz am Ende den Namen aus
           Stufe 1 übernehmen.
        """
        # --- Stufe 1: Spalte 0 (NemoFile-Wrapper oder roher Zeiger) ---
        fallback_name = ""
        try:
            raw = model.get_value(it, 0)
        except Exception:
            raw = None
        if raw is not None and not isinstance(raw, (int, float, str, bool)):
            for attr in ("get_name", "get_display_name"):
                try:
                    method = getattr(raw, attr, None)
                    if callable(method):
                        value = method()
                        if value:
                            fallback_name = os.path.basename(str(value))
                            break
                except Exception:
                    pass
            if not fallback_name:
                for attr in ("get_uri",):
                    try:
                        method = getattr(raw, attr, None)
                        uri = method() if callable(method) else None
                        if uri and isinstance(uri, str) and "://" in uri:
                            fallback_name = (Gio.File.new_for_uri(
                                uri).get_basename() or "")
                            break
                    except Exception:
                        pass
        elif isinstance(raw, int) and raw > 0:
            try:
                fallback_name = _nemo_file_name_from_ptr(raw)
            except Exception:
                fallback_name = ""

        # --- Stufe 2: alle Stringspalten scannen ---
        try:
            n_cols = model.get_n_columns()
        except Exception:
            n_cols = 0
        n_cols = min(n_cols, 64)
        candidates = []
        for col in range(1, n_cols):
            try:
                val = model.get_value(it, col)
            except Exception:
                continue
            if isinstance(val, str) and val.strip():
                candidates.append(val.strip())
        # Auflösbaren Kandidaten bevorzugen, der eine echte Datei benennt
        for cand in candidates:
            if not dir_path or os.path.exists(os.path.join(dir_path, cand)):
                return cand
        if candidates:
            return candidates[0]
        return fallback_name or None

    @staticmethod
    def _read_tree(view, dir_path):
        """GtkTreeView-basierte Ansichten (Liste, Kompakt)."""
        for w in walk(view):
            if isinstance(w, Gtk.TreeView):
                try:
                    tsel = w.get_selection()
                    model, paths = tsel.get_selected_rows()
                    # Log the actual GTK selection/model shape once per widget
                    # class; useful when Nemo emits a signal but rows stay empty.
                    marker = "_previewer_tree_diag_done"
                    if not getattr(w, marker, False):
                        setattr(w, marker, True)
                        try:
                            ncols = model.get_n_columns() if model is not None else -1
                            nrows = model.iter_n_children(None) if model is not None else -1
                        except Exception:
                            ncols, nrows = -1, -1
                        try:
                            mode = tsel.get_mode()
                        except Exception:
                            mode = "?"
                        dbg("GtkTreeView-Auswahl-Diagnose: Widget=%s, Auswahlmodus=%s, markierte_Pfade=%r, Modellspalten=%s, Modellzeilen=%s" % (
                            type_name(w), mode, paths, ncols, nrows))
                    # A zero-row model can be a transient/auxiliary tree
                    # rather than Nemo's populated file model. Do not report
                    # this as a successful empty selection; allow ATK/native
                    # fallbacks to inspect the real view.
                    if model is None:
                        continue
                    try:
                        if model.iter_n_children(None) == 0:
                            continue
                    except Exception:
                        pass
                    names = []
                    for p in paths:
                        try:
                            it = model.get_iter(p)
                        except Exception:
                            continue
                        val = SelectionReader._tree_row_name(
                            model, it, dir_path)
                        if val:
                            names.append(val)
                    return names
                except Exception:
                    continue
        return None


# ============================== Provider ===================================

class PanelState:
    """Zustand pro Nemo-Fenster (am Fenster-Objekt gespeichert)."""

    def __init__(self, window):
        self.window = window
        self.panel = PreviewPanel(window)
        self.hpaned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        self.dir_path = None
        self.view = None
        self.view_handlers = []
        self.poll_id = 0
        self.last_sel = None
        self.pos_pending = True
        self.none_dbg_at = 0
        self._a11y_dumps = 0
        self.hpaned.connect("size-allocate", self._on_size_allocate)

    def _on_size_allocate(self, paned, alloc):
        if not self.pos_pending:
            return
        if alloc.width > PANEL_WIDTH + 200:
            paned.set_position(alloc.width - PANEL_WIDTH)
            self.pos_pending = False


def _uri_to_dir(uri):
    try:
        path, _ = GLib.filename_from_uri(uri)
        return path
    except Exception:
        try:
            parsed = urllib.parse.urlparse(uri)
            return urllib.parse.unquote(parsed.path)
        except Exception:
            return None


def _reconcile(st):
    """
    Panel an der rechten Kante des Nemo-Fensters verankern.
    Technik: Das direkte Kindelement der Fenster-Hauptbox, das die
    Dateiansicht enthält (der Nemo-'Pane'), wird in unser HPaned
    verpackt: [ Pane | Panel ]. Das Panel sitzt damit zuverlässig am
    rechten Rand und behält seine Position über Reiterwechsel hinweg.
    """
    window = st.window
    view = find_view(window)
    if view is None:
        return

    try:
        kids = window.get_children()
    except Exception:
        return
    top_box = kids[0] if kids else None
    if not isinstance(top_box, Gtk.Container):
        dbg("Injektion: unerwartete Fensterstruktur (%s)"
            % type_name(top_box))
        return

    # Injektionsziel: das Widget, das DIREKT unter der Hauptbox auf dem
    # Pfad von der Ansicht nach oben liegt. Wir folgen dazu schlicht den
    # Eltern-Zeigern – das ist deterministisch und unabhängig von
    # is_ancestor-Semantik-Spezialitäten.
    target = None
    node = view
    while node is not None:
        parent = node.get_parent()
        if parent is top_box:
            target = node
            break
        node = parent

    if target is None:
        chain = []
        node = view
        while node is not None:
            chain.append(type_name(node))
            node = node.get_parent()
        dbg("Injektion: Ansicht hängt nicht unter der Hauptbox – "
            "Kette nach oben: %s" % " < ".join(chain))
        return

    # Wichtig: Hängt die Ansicht bereits unter unserem HPaned, ist der
    # gefundene Ziel-Knoten unser EIGENES HPaned – dann ist bereits
    # alles injiziert und es darf NICHT nochmal passieren (sonst
    # verpacken wir das Paned in sich selbst und zerstören den Baum).
    if target is st.hpaned:
        st._view_ok(view)
        return

    # Bereits korrekt injiziert?
    if (st.hpaned.get_parent() is top_box
            and st.hpaned.get_child1() is target):
        st._view_ok(view)
        return

    # Neu injizieren: alten Zustand rückgängig machen
    _detach(st)

    try:
        if isinstance(top_box, Gtk.Box):
            pos = top_box.child_get_property(target, "position")
            top_box.remove(target)
            st.hpaned.pack1(target, True, False)
            st.hpaned.pack2(st.panel, False, False)
            top_box.pack_start(st.hpaned, True, True, 0)
            top_box.reorder_child(st.hpaned, pos)
        elif isinstance(top_box, Gtk.Grid):
            left = top_box.child_get_property(target, "left-attach")
            top = top_box.child_get_property(target, "top-attach")
            width = top_box.child_get_property(target, "width")
            height = top_box.child_get_property(target, "height")
            # Validieren, BEVOR wir etwas entfernen – sonst droht ein
            # irreparabel zerstörter Widget-Baum
            if (not all(isinstance(v, int) and v >= 0 for v in (left, top))
                    or not all(isinstance(v, int) and v >= 1
                               for v in (width, height))):
                dbg("Injektion: Grid-Eigenschaften nicht lesbar "
                    "(%r, %r, %r, %r) – Vorgang abgebrochen, "
                    "Nemo bleibt unangetastet" % (left, top, width, height))
                return
            top_box.remove(target)
            st.hpaned.pack1(target, True, False)
            st.hpaned.pack2(st.panel, False, False)
            top_box.attach(st.hpaned, left, top, width, height)
        else:
            dbg("Injektion: Hauptbox ist weder Box noch Grid (%s)"
                % type_name(top_box))
            return
        st.pos_pending = True
        st.hpaned.show()
        st.panel.show_all()
        dbg("Panel an Fensterrand injiziert (Ziel: %s)"
            % type_name(target))
    except Exception:
        traceback.print_exc()
        return

    st._view_ok(view)


def _detach(st):
    """Panel aus dem Widget-Baum lösen und Originalstruktur wiederherstellen."""
    parent = st.hpaned.get_parent()
    if parent is None:
        return
    try:
        child1 = st.hpaned.get_child1()
        if child1 is None:
            parent.remove(st.hpaned)
            return
        if isinstance(parent, Gtk.Box):
            pos = parent.child_get_property(st.hpaned, "position")
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.pack_start(child1, True, True, 0)
            parent.reorder_child(child1, pos)
        elif isinstance(parent, Gtk.Grid):
            left = parent.child_get_property(st.hpaned, "left-attach")
            top = parent.child_get_property(st.hpaned, "top-attach")
            width = parent.child_get_property(st.hpaned, "width")
            height = parent.child_get_property(st.hpaned, "height")
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.attach(child1, left, top, width, height)
        else:
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.add(child1)
    except Exception:
        traceback.print_exc()


def _connect_view_signals(st, view):
    """
    Auswahl-Signale dynamisch entdecken und verbinden. Statt einen
    festen Signalnamen zu raten, werden im Teilbaum der Ansicht und
    auf den AtkSelection-Objekten alle void-Signale mit 'select' im
    Namen verbunden – so ist es egal, ob Nemo Striche oder Unter-
    striche benutzt. Verbunden wird pro Widget; die Handler-IDs
    landen als (Objekt, ID)-Paare in st.view_handlers.
    """
    names_found = set()

    for w in walk(view):
        try:
            if not isinstance(w, Gtk.Widget) or not w.get_mapped():
                continue
        except Exception:
            continue
        for sig in selection_signals(w):
            try:
                hid = w.connect(
                    sig,
                    lambda *a, _w=w, _s=sig: (
                        dbg("Signal %s empfangen (%s)" % (_s, type_name(_w))),
                        _dump_a11y_once(st),
                        _refresh_soon(st))[-1])
            except Exception:
                continue
            st.view_handlers.append((w, hid))
            names_found.add(sig)

    # Keine Signalhandler an ATK-Objekten registrieren. Diese Objekte sind
    # beim Ordnerwechsel häufig kurzlebig und führten zu disconnect-Warnungen.

    dbg("Ansicht verbunden: %s – Auswahl-Signale: %s"
        % (type_name(view), ", ".join(sorted(names_found)) or "KEINE"))


def _dump_a11y_once(st):
    """
    Den a11y-Baum der Ansicht bis zu zweimal ausgeben: einmal nach dem
    Verbinden (Grundzustand) und einmal beim ersten Auswahl-Signal
    (Zustand nach dem Klick). Die Zeilen zeigen Tiefe, Kinderzahl,
    Rolle, Namen, AtkSelection-Zähler sowie SELECTED/FOCUSED – damit
    ist sichtbar, wo Nemo die Auswahl tatsächlich hergibt.
    """
    if st._a11y_dumps >= 2 or st.view is None:
        return
    st._a11y_dumps += 1
    view = st.view
    tag = "a11y[%s]" % type_name(view)
    try:
        if not isinstance(view, Gtk.Widget) or not view.get_mapped():
            return
        root = view.get_accessible()
        if root is None:
            dbg("%s: kein Accessible verfügbar" % tag)
            return
    except Exception:
        dbg("%s: kein Accessible verfügbar" % tag)
        return
    budget = [45]

    def rec(acc, depth):
        if acc is None or depth > 10 or budget[0] <= 0:
            return
        n = -1
        try:
            n = acc.get_n_children()
        except Exception as exc:
            n = -1
            # Ursache des scheinbar leeren a11y-Baums einmalig ausgeben.
            if not getattr(_dump_a11y_once, "_n_children_err", None):
                _dump_a11y_once._n_children_err = repr(exc)
                dbg("%s: get_n_children() schlug fehl: %r – "
                    "weitere Kinder werden blind über ref_child() probiert"
                    % (tag, exc))
        try:
            role = acc.get_role()
            try:
                role = role.value_nick
            except Exception:
                role = str(role)
        except Exception:
            role = "?"
        try:
            name = acc.get_name() or ""
        except Exception:
            name = ""
        extra = []
        try:
            extra.append("AtkSel=%d" % acc.get_selection_count())
        except Exception:
            pass
        try:
            ss = acc.get_state_set()
            if ss is not None:
                if ss.contains_state(Atk.StateType.SELECTED):
                    extra.append("SELECTED")
                if ss.contains_state(Atk.StateType.FOCUSED):
                    extra.append("FOCUSED")
                if ss.contains_state(Atk.StateType.ACTIVE):
                    extra.append("ACTIVE")
        except Exception:
            pass
        budget[0] -= 1
        dbg("%s d%d kinder=%d rolle=%s name=%r %s"
            % (tag, depth, n, role, name, " ".join(extra)))
        for child in _atk_children(acc, max_children=60):
            rec(child, depth + 1)

    rec(root, 0)
    dbg("%s – Ende der Diagnose" % tag)


def _view_ok(self, view):
    """Signal-Anmeldung (self ist hier ein PanelState via Erweiterung unten)."""
    if self.view is not view:
        for obj, hid in self.view_handlers:
            try:
                if obj.handler_is_connected(hid):
                    obj.disconnect(hid)
            except Exception:
                # Objekt/Handler kann durch Nemo bereits abgebaut sein.
                pass
        self.view_handlers = []
        self.view = view
        self._a11y_dumps = 0
        try:
            _connect_view_signals(self, view)
        except Exception:
            traceback.print_exc()
        _dump_a11y_once(self)
        _refresh_soon(self)


PanelState._view_ok = _view_ok


def _refresh(st):
    try:
        # Immer die LIVE-Ansicht suchen: st.view kann nach einem
        # Ordnerwechsel auf einen bereits abgebauten Slot zeigen.
        view = find_view(st.window)
        if view is None:
            return
        names, strategy = SelectionReader.read(view, st.dir_path)
        # Diagnose pro konkretem Ansichtstyp, nicht nur einmal pro Fenster:
        # Nemo kann beim Ansichtswechsel ListView gegen IconView austauschen.
        diag_key = "_selection_diag_" + type_name(view)
        if not getattr(st, diag_key, False):
            setattr(st, diag_key, True)
            dbg("Auswahl-Diagnose: View=%s, Instanz.get_selection=%s, Instanz.peek_selection=%s, Nemo.view_get_selection=%s, Nemo.view_peek_selection=%s" % (
                type_name(view),
                callable(getattr(view, "get_selection", None)),
                callable(getattr(view, "peek_selection", None)),
                callable(getattr(Nemo, "view_get_selection", None)),
                callable(getattr(Nemo, "view_peek_selection", None))))
            _dump_widget_tree(view)
        if names is None:
            # Keine Strategie konnte lesen – gedrosselte Debug-Meldung
            now = GLib.get_monotonic_time()
            if now - st.none_dbg_at > 5000000:  # max. alle 5 Sekunden
                st.none_dbg_at = now
                dbg("Auswahl nicht lesbar (Ansicht: %s)" % type_name(view))
            return
        if names != st.last_sel:
            dbg("Auswahl geändert: %r (via %s)" % (names, strategy))
            st.last_sel = names
            st.panel.set_selection(names, st.dir_path)
    except Exception:
        traceback.print_exc()


def _refresh_soon(st):
    """Auswahl-Refresh in den Main-Loop einplanen (Signal-Kontext verlassen)."""
    GLib.idle_add(lambda: (_refresh(st), False)[1])


def _poll(st):
    """Timer: Reconciliation + Auswahl-Abgleich als Sicherheitsnetz."""
    try:
        _reconcile(st)
        _refresh(st)
    except Exception:
        traceback.print_exc()
    return True


def _get_state(window):
    st = getattr(window, "_previewer_state", None)
    if st is None:
        st = PanelState(window)
        window._previewer_state = st
        st.poll_id = GLib.timeout_add(POLL_MS, _poll, st)
        dbg("PanelState für Fenster angelegt")
    return st


def _on_crowbar_placed(crowbar, window, uri, tries):
    """
    Idle-Callback: crowbar ist jetzt im Baum → Panel injizieren.
    Der Ordnerpfad wird erst übernommen, wenn die crowbar tatsächlich
    platziert ist – ein überholter Aufruf einer alten crowbar würde
    sonst den aktuellen Pfad mit einem ALTEN Pfad überschreiben.
    """
    st = _get_state(window)
    if crowbar.get_parent() is None:
        tries[0] += 1
        return tries[0] < 40  # noch nicht platziert → weiter zuwarten
    st.dir_path = _uri_to_dir(uri)
    _reconcile(st)
    _refresh(st)
    return False


# ------- Provider-Klasse (dynamisch, damit NameAndDescProvider optional) ----

def _is_desktop_window(window):
    """Erkennt Desktop-Fenster, damit dort kein Vorschau-Panel landet."""
    name = type_name(window)
    # Cinnamon/Nemo-Versionen unterscheiden sich bei den konkreten Typnamen.
    if "desktop" in name.lower():
        return True
    # Zusätzliche Prüfung des Widget-Baums: Desktop-Icon-Ansichten dürfen
    # niemals als Anker für die Injektion dienen.
    try:
        for child in walk(window):
            if type_name(child) == "NemoDesktopIconView":
                return True
    except Exception:
        pass
    return False


def _get_widget(self, uri, window):
    """LocationWidgetProvider: liefert die unsichtbare 'Brechstange'."""
    window_type = type_name(window)
    dbg("get_widget aufgerufen für %s (Fenstertyp: %s)" % (uri, window_type))
    if _is_desktop_window(window):
        dbg("Desktop-Fenster erkannt – kein Vorschau-Panel")
        return None
    st = _get_state(window)
    new_dir = _uri_to_dir(uri)
    if new_dir != st.dir_path:
        st.last_sel = None
        st.panel.set_selection([], new_dir)
    st.dir_path = new_dir   # sofort: neuer Ordner ist bekannt
    crowbar = Gtk.Box()
    crowbar.set_size_request(-1, 0)
    crowbar.set_no_show_all(True)
    tries = [0]
    GLib.idle_add(_on_crowbar_placed, crowbar, window, uri, tries)
    return crowbar


def _get_name_and_desc(self):
    return ["previewer:::"
            "Angedockte Vorschau der ausgewählten Datei:::"]


_bases = [GObject.GObject, Nemo.LocationWidgetProvider]
if hasattr(Nemo, "NameAndDescProvider"):
    _bases.append(Nemo.NameAndDescProvider)

_provider_dict = {
    "get_widget": _get_widget,
    "get_name_and_desc": _get_name_and_desc,
}

Provider = type("NemoPreviewerProvider", tuple(_bases), _provider_dict)


# ------------------------- Gtk-Protokoll-Filter ------------------------------
#
# Beim Ordnerwechsel baut Nemo den alten Slot ab. GTK druckt dabei
# teilweise die Meldung
#   gtk_container_foreach: assertion 'GTK_IS_CONTAINER (container)' failed
# für Widgets, die bereits halb zerstört sind – auch wenn fremder Code
# (wie diese Extension) den Baum nur liest. Genau DIESE eine Meldung
# wird unterdrückt; alle anderen Gtk-Meldungen bleiben sichtbar.

_GTK_FOREACH_MSG = "gtk_container_foreach: assertion 'GTK_IS_CONTAINER"


def _install_log_filter():
    def handler(domain, level, message, *user_data):
        if message and _GTK_FOREACH_MSG in message:
            return
        try:
            GLib.log_default_handler(domain, level, message)
        except Exception:
            pass
    try:
        GLib.log_set_handler("Gtk",
                             GLib.LogLevelFlags.LEVEL_CRITICAL, handler)
    except Exception:
        pass


_install_log_filter()
