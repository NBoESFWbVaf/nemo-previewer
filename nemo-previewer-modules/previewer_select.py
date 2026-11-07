#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_select.py – Version 0.65.8

Selection detection: reads the currently selected file from the
Nemo view via selection signals, vtable access and GTK/ATK
fallbacks.
"""

import os
import sys
import traceback
import urllib.parse
import ctypes

import gi

gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Atk', '1.0')

from gi.repository import GObject, Nemo, Gtk, Gio, Atk

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import dbg, diag, type_name, walk


class _NativeGList(ctypes.Structure):
    pass


_NativeGList._fields_ = [
    ("data", ctypes.c_void_p),
    ("next", ctypes.POINTER(_NativeGList)),
    ("prev", ctypes.POINTER(_NativeGList)),
]


# → REF SEL-DOC-1
def _gobject_pointer(widget):
    capsule = None
    try:
        capsule = getattr(widget, "__gpointer__", None)
    except Exception:
        capsule = None
    if capsule is None:
        return None
    # Variant 1: some PyGObject builds return the address directly.
    if isinstance(capsule, int):
        return capsule
    try:
        get_pointer = ctypes.pythonapi.PyCapsule_GetPointer
        get_pointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        get_pointer.restype = ctypes.c_void_p
        # Try with the exact name first …
        try:
            get_name = ctypes.pythonapi.PyCapsule_GetName
            get_name.argtypes = [ctypes.py_object]
            get_name.restype = ctypes.c_char_p
            name = get_name(capsule)
            ptr = get_pointer(capsule, name)
            if ptr:
                return ptr
        except Exception as e:
            dbg("select/_gobject_pointer: suppressed: %s" % e)
        # … then nameless (a NULL name only accepts nameless capsules).
        return get_pointer(capsule, None)
    except Exception:
        return None


# → REF SEL-DOC-2
def _read_cptr(addr, offset=0):
    if not addr:
        return None
    try:
        return ctypes.cast(
            addr + offset, ctypes.POINTER(ctypes.c_void_p)).contents.value
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Native selection via the NemoView class vtable (peek_selection).
# → REF SEL-VTABLE-1

_NATIVE_VTABLE_API = None
_NATIVE_VTABLE_TRIED = False
_NATIVE_VTABLE_BROKEN = False
_VTABLE_GUARD_WARNED = False
_VTABLE_CRASH_WARNED = False


# → REF SEL-DOC-3
def _native_vtable_api():
    global _NATIVE_VTABLE_API, _NATIVE_VTABLE_TRIED
    global _NATIVE_VTABLE_BROKEN
    if _NATIVE_VTABLE_TRIED:
        return None if _NATIVE_VTABLE_BROKEN else _NATIVE_VTABLE_API
    _NATIVE_VTABLE_TRIED = True
    try:
        # → REF SEL-GTYPE-1
        gobj = ctypes.CDLL("libgobject-2.0.so.0")
        type_from_name = gobj.g_type_from_name
        type_from_name.argtypes = [ctypes.c_char_p]
        type_from_name.restype = ctypes.c_size_t
        view_gtype = type_from_name(b"NemoView")
        file_gtype = type_from_name(b"NemoFile")
        iface_gtype = type_from_name(b"NemoFileInfo")
        if not view_gtype or not file_gtype or not iface_gtype:
            dbg("VTable API: GTypes missing "
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
            # NemoViewClass: parent class + 12 pointers up to
            # peek_selection.
            "peek_offset": parent_size + 12 * ptr_size,
            # NemoFileInfoInterface: interface head (2 pointers), then
            # is_gone/get_name/get_uri.
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
        dbg("VTable API ready (peek_offset=%d, IntPtr=%d)"
            % (api["peek_offset"], ptr_size))
        return api
    except Exception as exc:
        dbg("VTable API setup failed: %s" % exc)
        _NATIVE_VTABLE_BROKEN = True
        return None


# --- Wildcall guard (0.9.2, audit "buffer overflow/OOM") --------------------
# → REF SEL-WILDCALL-1
_NEMO_TEXT_RANGES = None


# → REF SEL-DOC-4
def _nemo_addr_ranges():
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


# → REF SEL-DOC-5
def _ptr_in_nemo(ranges, ptr):
    return bool(ranges) and any(lo <= ptr < hi for lo, hi in ranges)


# --- shared helpers (audit 0.9.1: this logic was previously
# duplicated identically in three places) ----------------------------------

# → REF SEL-DOC-6
def _name_from_uri(uri):
    try:
        return Gio.File.new_for_uri(uri).get_basename() or ""
    except Exception:
        try:
            return os.path.basename(urllib.parse.urlparse(uri).path)
        except Exception:
            return ""


# → REF SEL-DOC-7
def _iface_file_name(api, file_ptr):
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


# → REF SEL-DOC-8
def _vtable_selection_names(view):
    global _NATIVE_VTABLE_BROKEN, _VTABLE_GUARD_WARNED
    api = _native_vtable_api()
    if api is None:
        return None, False
    ptr = _gobject_pointer(view)
    if not ptr or not api["is_a"](ptr, api["view_gtype"]):
        # Log once WHY the vtable route rejects this view –
        # otherwise this guard fails silently (see symbol view).
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
                # Never call is_a with a NULL pointer – that would
                # segfault the Nemo process (no try/except there).
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
            dbg("VTable guard failed (%s): %s"
                % (type_name(view), "; ".join(info)))
        return None, False
    try:
        class_ptr = _read_cptr(ptr)                 # GTypeInstance.g_class
        peek_ptr = _read_cptr(class_ptr, api["peek_offset"])
        if not peek_ptr:
            if not _NATIVE_VTABLE_BROKEN:
                dbg("VTable API: peek_selection pointer is NULL – disabled")
            _NATIVE_VTABLE_BROKEN = True
            return None, False
        # 0.9.2: wildcall guard – the pointer gets CALLED and must
        # therefore lie inside Nemo.
        if not _ptr_in_nemo(_nemo_addr_ranges(), peek_ptr):
            if not _NATIVE_VTABLE_BROKEN:
                dbg("VTable API: peek_selection pointer outside "
                    "the Nemo libraries – disabled")
            _NATIVE_VTABLE_BROKEN = True
            return None, False
        peek = ctypes.cast(
            peek_ptr,
            ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p))
        node = peek(ptr)
    except Exception as exc:
        if not _NATIVE_VTABLE_BROKEN:
            dbg("VTable API: peek_selection call failed: %s "
                "– disabled" % exc)
        _NATIVE_VTABLE_BROKEN = True
        return None, False

    names = []
    seen = set()
    limit = 0
    while node and node not in seen and limit < 4096:
        seen.add(node)
        data = _read_cptr(node)                     # GList.data = NemoFile*
        if data:
            # Sanity check: the instance must really be a NemoFile (the
            # GType lives in the class, hence g_type_check_instance_is_a).
            if not api["is_a"](data, api["file_gtype"]):
                if not _NATIVE_VTABLE_BROKEN:
                    dbg("VTable API: selection item not a NemoFile – "
                        "disabled")
                _NATIVE_VTABLE_BROKEN = True
                return None, False
            # 0.9.1: name/URI via the shared interface helper
            # (previously implemented identically inline).
            name = _iface_file_name(api, data)
            if name:
                names.append(name)
        node = _read_cptr(node, api["ptr_size"])     # GList.next
        limit += 1
    return names, True


# → REF SEL-DOC-9
def _nemo_file_name_from_ptr(file_ptr):
    api = _native_vtable_api()
    if not api or not file_ptr:
        return ""
    try:
        if not api["is_a"](file_ptr, api["file_gtype"]):
            return ""
    except Exception:
        return ""
    return _iface_file_name(api, file_ptr)


# → REF SEL-DOC-10
def _dump_widget_tree(view, max_widgets=100):
    diag("Widget tree dump starts")
    count = 0
    for w in walk(view):
        if count >= max_widgets:
            diag("Widget tree dump truncated (limit %d)" % max_widgets)
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
            except Exception as e:
                dbg("select/_dump_widget_tree: suppressed: %s" % e)
        try:
            mapped = bool(w.get_mapped())
        except Exception:
            mapped = False
        diag("Widget[%d]: %s mapped=%s methods=%s" %
            (count, type_name(w), mapped, ",".join(methods) or "-"))
    diag("Widget tree dump end (%d widgets)" % count)


# --------------------- Signal discovery & a11y helpers ----------------------

# GtkWidget clipboard/X11 selection signals are named "selection…"
# but have nothing to do with the FILE selection.
_CLIPBOARD_SIGNALS = {
    "selection-get", "selection-received", "selection-clear-event",
    "selection-request-event",
}


# → REF SEL-DOC-11
def _signals_of_gtype(gtype):
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
                continue   # handler would have to return a value – too risky
        except Exception:
            continue
        if name and "select" in name.lower() and name not in _CLIPBOARD_SIGNALS:
            out.append(name)
    return out


# → REF SEL-DOC-12
def selection_signals(widget):
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
        except Exception as e:
            dbg("select/selection_signals: suppressed: %s" % e)
        try:
            parent = GObject.type_parent(t)
            if parent:
                queue.append(parent)
        except Exception as e:
            dbg("select/selection_signals: suppressed: %s" % e)
    return sorted(names)


# → REF SEL-DOC-13
def _atk_children(acc, max_children=200):
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
            except Exception as e:
                dbg("select/_atk_children: suppressed: %s" % e)
        return children
    # Unknown child count: probe blindly; ref_child throws on the first
    # invalid index – the natural end.
    for i in range(max_children):
        try:
            children.append(acc.ref_child(i))
        except Exception:
            break
    return children


# → REF SEL-DOC-14
def _a11y_root(view):
    try:
        if not isinstance(view, Gtk.Widget) or not view.get_mapped():
            return None
        return view.get_accessible()
    except Exception:
        return None


# → REF SEL-DOC-15
def _atk_selection_objects(view, max_depth=12):
    implementors = []
    root = _a11y_root(view)
    if root is None:
        return implementors

    def collect(acc, depth):
        if acc is None or depth > max_depth or len(implementors) >= 8:
            return
        try:
            acc.get_selection_count()
            implementors.append(acc)   # implements AtkSelection
        except Exception:
            pass
        for child in _atk_children(acc):
            collect(child, depth + 1)

    collect(root, 0)
    return implementors


# → REF SEL-DOC-16
def is_nemo_view(w):
    name = type_name(w)
    # NemoDesktopIconView belongs to the desktop background, not to a
    # normal file browser window – never inject a panel there.
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
    except Exception as e:
        dbg("select/is_nemo_view: suppressed: %s" % e)
    return False


# → REF SEL-DOC-17
def find_view(window):
    try:
        for w in walk(window):
            if not is_nemo_view(w):
                continue
            try:
                if w.get_mapped() and w.get_realized():
                    return w
            except Exception:
                # The widget may be mid-destruction.
                continue
    except Exception as e:
        dbg("select/find_view: suppressed: %s" % e)
    return None


# ============================ Selection readers =============================

# → REF SEL-DOC-18
class SelectionReader:

    @staticmethod
    # → REF SEL-DOC-19
    def read(view, dir_path):
        empty_source = None
        for source, fetch in (
                # NemoView.peek_selection via the vtable is the
                # authoritative source: it works in every view.
                ("nemo-vtable", lambda: SelectionReader._read_nemo_vtable(
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
                # Name probably does not belong to a file entry
                continue
            out.append(n)
        if out:
            return out
        # Nothing resolvable? Keep the raw name – the panel then shows
        # WHAT was read (important for diagnostics).
        return [n.strip() for n in names if (n or "").strip()]

    @staticmethod
    # → REF SEL-DOC-20
    def _read_nemo_vtable(view, dir_path):
        try:
            names, supported = _vtable_selection_names(view)
        except Exception as exc:
            global _VTABLE_CRASH_WARNED
            if not _VTABLE_CRASH_WARNED:
                _VTABLE_CRASH_WARNED = True
                dbg("VTable route: unexpected exception (%s): %r – %s"
                    % (type_name(view), exc,
                       traceback.format_exc().strip().splitlines()[-1]))
            return None
        if not supported:
            return None
        return names

    @staticmethod
    # → REF SEL-DOC-21
    def _read_icon_view(view, dir_path):
        for w in walk(view):
            # Nemo may use its own widget class that is not typed as
            # Gtk.IconView but offers the same selection methods.
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
                    # Nemo model columns differ per version; check the
                    # file name against actual existence in the folder.
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
                # An empty list here is a valid, directly readable selection.
                return names
            except Exception:
                continue
        return None

    @staticmethod
    # → REF SEL-DOC-22
    def _read_atk(view):
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
            return []          # readable, but nothing selected
        return None

    @staticmethod
    # → REF SEL-DOC-23
    def _read_atk_states(view):
        root = _a11y_root(view)
        if root is None:
            return None
        selected = []

        def rec(acc, depth):
            if acc is None or depth > 12:
                return
            name = ""
            try:
                name = acc.get_name() or ""
            except Exception as e:
                dbg("select/_read_atk_states: suppressed: %s" % e)
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
    # → REF SEL-DOC-24
    def _read_atk_focused(view, dir_path):
        if not dir_path:
            return None
        root = _a11y_root(view)
        if root is None:
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
    # → REF SEL-DOC-25
    def _tree_row_name(model, it, dir_path):
        # --- Stage 1: column 0 (NemoFile wrapper or raw pointer) ---
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
                except Exception as e:
                    dbg("select/_tree_row_name: suppressed: %s" % e)
            if not fallback_name:
                for attr in ("get_uri",):
                    try:
                        method = getattr(raw, attr, None)
                        uri = method() if callable(method) else None
                        if uri and isinstance(uri, str) and "://" in uri:
                            fallback_name = (Gio.File.new_for_uri(
                                uri).get_basename() or "")
                            break
                    except Exception as e:
                        dbg("select/_tree_row_name: suppressed: %s" % e)
        elif isinstance(raw, int) and raw > 0:
            try:
                fallback_name = _nemo_file_name_from_ptr(raw)
            except Exception:
                fallback_name = ""

        # --- Stage 2: scan all string columns ---
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
        # Prefer a resolvable candidate that names a real file
        for cand in candidates:
            if not dir_path or os.path.exists(os.path.join(dir_path, cand)):
                return cand
        if candidates:
            return candidates[0]
        return fallback_name or None

    @staticmethod
    # → REF SEL-DOC-26
    def _read_tree(view, dir_path):
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
                        diag("GtkTreeView selection diagnostics: widget=%s, mode=%s, selected paths=%r, model columns=%s, model rows=%s" % (
                            type_name(w), mode, paths, ncols, nrows))
                    # A zero-row model may be a transient tree, not
                    # the file model – let ATK/native fallbacks inspect.
                    if model is None:
                        continue
                    try:
                        if model.iter_n_children(None) == 0:
                            continue
                    except Exception as e:
                        dbg("select/_read_tree: suppressed: %s" % e)
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


# Version: checked at load time by the entry point (previewer.py).
PREVIEWER_VERSION = "0.65.8"
dbg("previewer_select %s loaded" % PREVIEWER_VERSION)