#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Auswahl-Modul (previewer_select.py)
===============================================

STAND: Version 0.12.0 – aktuelle Fassung (keine Änderungen in dieser
Datei – nur Versions-Sync zum F12-Konfigurations-Start).

Erkennt die in Nemo markierten Dateien – mehrstufig und defensiv:

1. NemoView.peek_selection über den Klassen-VTable (primäre API; läuft
   in allen Ansichten: Symbol, Liste, Kompakt)
2. NemoView.get_selection() über GI bzw. die native C-API, falls verfügbar
3. Gtk.IconView-/Gtk.TreeView-Auswahl als Fallback
4. ATK-Selection, ATK-Zustände und Fokus als letzter Rückhalt

Außerdem: Erkennung echter Nemo-Dateiansichten (is_nemo_view/find_view),
Laufzeit-Entdeckung der Auswahl-Signale und Diagnose-Helfer.

Gehört zur vierteiligen Extension "Previewer" (siehe previewer.py).
"""

import os
import sys
import traceback
import urllib.parse
import ctypes
import ctypes.util
import glob

import gi

gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Atk', '1.0')

from gi.repository import GObject, Nemo, Gtk, Gio, Atk

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import dbg, diag, type_name, walk


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
            diag("Nemo-C-Auswahl-API nicht verfügbar; Bibliothekskandidaten=%r; Details=%r" %
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


# --- Wildcall-Schutz (0.9.2, Audit „Pufferüberlauf/OOM“) ------------------
# Die ctypes-Routen lesen Funktionszeiger aus berechneten VTable-Offsets
# (peek_selection, get_name, get_uri) und rufen sie auf. Verschiebt ein
# Nemo-Update das Klassen-/Interface-Layout, könnte ein Slot auf einen
# falschen, aber nicht-NULL Zeiger zeigen – sein Aufruf wäre ein
# Wildcall und würde Nemo schlagartig beenden (try/except wirkt bei
# Speicherzugriffsverletzungen nicht). Jedes Call-Ziel muss deshalb
# innerhalb einer Nemo-Bibliothek liegen, bevor es gerufen wird;
# andernfalls wird die Route abgeschaltet (fail-closed – die anderen
# Auswahl-Strategien übernehmen).
_NEMO_TEXT_RANGES = None


def _nemo_addr_ranges():
    """
    Adressbereiche aller ausführbaren Mappings von Nemo-Bibliotheken
    (einmalig aus /proc/self/maps gelesen). Gibt None zurück, wenn die
    Maps nicht lesbar sind – Aufrufer behandeln das als fail-closed:
    lieber eine Route zu viel abgeschaltet als ein möglicher Wildcall.
    """
    global _NEMO_TEXT_RANGES
    if _NEMO_TEXT_RANGES is not None:
        return _NEMO_TEXT_RANGES
    ranges = []
    try:
        with open("/proc/self/maps", "r", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 6:
                    continue
                perms = parts[1]
                path = parts[5].lower()
                if "nemo" not in path or "x" not in perms:
                    continue
                lo, hi = parts[0].split("-", 1)
                ranges.append((int(lo, 16), int(hi, 16)))
    except Exception:
        ranges = None
    _NEMO_TEXT_RANGES = ranges
    return ranges


def _ptr_in_nemo(ranges, ptr):
    """True, wenn ptr in einem der Nemo-Adressbereiche liegt."""
    return bool(ranges) and any(lo <= ptr < hi for lo, hi in ranges)


# --- gemeinsame Helfer (Audit 0.9.1: Logik war zuvor mehrfach identisch
# in _vtable_selection_names, _nemo_file_name_from_ptr und
# _read_native_nemo_selection implementiert) ------------------------------

def _name_from_uri(uri):
    """Dateiname (Basename) aus einer Nemo-URI – ein Ort, eine Wahrheit."""
    try:
        return Gio.File.new_for_uri(uri).get_basename() or ""
    except Exception:
        try:
            return os.path.basename(urllib.parse.urlparse(uri).path)
        except Exception:
            return ""


def _iface_file_name(api, file_ptr):
    """
    Dateiname eines rohen NemoFile-Zeigers über das NemoFileInfo-
    Interface: get_name, falls der Zeiger vorhanden; sonst get_uri mit
    Basename-Fallback. Gibt "" zurück, wenn nichts zu holen ist.
    Der Aufrufer muss file_ptr vorher gegen den NemoFile-GTyp
    validiert haben (api["is_a"]).
    0.9.2: Die Funktionszeiger werden vor dem Call gegen die
    Nemo-Adressbereiche geprüft (Wildcall-Schutz) – verschiebt ein
    Nemo-Update das Interface-Layout, wird der falsche Zeiger nicht
    gerufen, sondern still "" geliefert.
    """
    try:
        file_class = _read_cptr(file_ptr)             # GTypeInstance.g_class
        if not file_class:
            return ""
        iface = api["iface_peek"](file_class, api["iface_gtype"])
        if not iface:
            return ""
        ranges = _nemo_addr_ranges()
        if ranges is None:
            return ""
        str_fn_t = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
        name_ptr = _read_cptr(iface, api["iface_name_off"])
        if name_ptr and _ptr_in_nemo(ranges, name_ptr):
            raw = ctypes.cast(name_ptr, str_fn_t)(file_ptr)
            if raw:
                try:
                    return ctypes.string_at(raw).decode("utf-8", "replace")
                finally:
                    api["g_free"](raw)
        uri_ptr = _read_cptr(iface, api["iface_uri_off"])
        if uri_ptr and _ptr_in_nemo(ranges, uri_ptr):
            raw = ctypes.cast(uri_ptr, str_fn_t)(file_ptr)
            if raw:
                try:
                    uri = ctypes.string_at(raw).decode("utf-8", "replace")
                finally:
                    api["g_free"](raw)
                if uri:
                    return _name_from_uri(uri)
    except Exception:
        return ""
    return ""


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
        # 0.9.2: Wildcall-Schutz – der Zeiger wird GECALLT und muss
        # deshalb innerhalb von Nemo liegen.
        if not _ptr_in_nemo(_nemo_addr_ranges(), peek_ptr):
            if not _NATIVE_VTABLE_BROKEN:
                dbg("VTable-API: peek_selection-Zeiger liegt außerhalb "
                    "der Nemo-Bibliotheken – deaktiviert")
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
            # 0.9.1: Name/URI über den gemeinsamen Interface-Helfer
            # (zuvor identisch inline implementiert).
            name = _iface_file_name(api, data)
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
    0.9.1: Die Interface-Lese-Logik steckt im gemeinsamen Helfer
    _iface_file_name (zuvor identisch in _vtable_selection_names).
    """
    api = _native_vtable_api()
    if not api or not file_ptr:
        return ""
    try:
        if not api["is_a"](file_ptr, api["file_gtype"]):
            return ""
    except Exception:
        return ""
    return _iface_file_name(api, file_ptr)


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
                        # 0.9.1: Basename über den gemeinsamen Helfer
                        # (zuvor identisch inline implementiert).
                        name = _name_from_uri(uri)
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
    diag("Widget-Baum-Diagnose beginnt")
    count = 0
    for w in walk(view):
        if count >= max_widgets:
            diag("Widget-Baum-Diagnose gekürzt (Limit %d)" % max_widgets)
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
        diag("Widget[%d]: %s mapped=%s Methoden=%s" %
            (count, type_name(w), mapped, ",".join(methods) or "-"))
    diag("Widget-Baum-Diagnose Ende (%d Widgets)" % count)


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
                        diag("GtkTreeView-Auswahl-Diagnose: Widget=%s, Auswahlmodus=%s, markierte_Pfade=%r, Modellspalten=%s, Modellzeilen=%s" % (
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


# Version: wird beim Laden vom Einstieg (previewer.py) geprüft.
PREVIEWER_VERSION = "0.12.0"
dbg("previewer_select %s geladen" % PREVIEWER_VERSION)