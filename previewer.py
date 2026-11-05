#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer.py – Version 0.57.0

Entry point and Nemo integration: injects the preview panel into
every Nemo window, loads the seven modules from the
nemo-previewer-modules subfolder and enforces the version lock.
"""

import sys
import traceback
import urllib.parse

import gi

gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Atk', '1.0')

from gi.repository import GObject, Nemo, Gtk, GLib, Atk

# Find sibling modules, however nemo-python loaded this file.
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# 0.35.0: the seven modules live in the nemo-previewer-modules
# subfolder, placed first on the import path (→ REF ENT-MODDIR-1).
_MODDIR = os.path.join(_HERE, "nemo-previewer-modules")
if os.path.isdir(_MODDIR) and _MODDIR not in sys.path:
    sys.path.insert(0, _MODDIR)

from previewer_util import (
    dbg, diag, VERBOSE_DIAG,
    walk, type_name,
    PANEL_WIDTH, POLL_MS,
    pick_icon,
    install_step_trace,
)
# F45: set the step trace right after the util import – module imports
# and every function then run under the hook (→ REF UT-TRACE-1).
install_step_trace()
# 0.35.0: confirm the module subfolder in the log (→ REF ENT-MODDIR-1).
dbg("Module dir: %s"
    % (_MODDIR if os.path.isdir(_MODDIR)
       else "(flat install)"))
from previewer_select import (
    find_view, selection_signals, SelectionReader,
    _atk_children, _dump_widget_tree,
)
from previewer_panel import PreviewPanel

# PREVIEWER_VERSION must be identical in all eight modules; the entry
# point checks loaded modules and warns about outdated copies.
PREVIEWER_VERSION = "0.57.0"
import previewer_util
import previewer_select
import previewer_panel
import previewer_toolbar
import previewer_render_media
import previewer_render_docs
import previewer_render_text

for _mod in (previewer_util, previewer_select, previewer_panel,
             previewer_toolbar, previewer_render_media,
             previewer_render_docs, previewer_render_text):
    _ver = getattr(_mod, "PREVIEWER_VERSION", None)
    if _ver != PREVIEWER_VERSION:
        # Plain print – a version mismatch must stay visible even
        # with debug logging switched off.
        print("[previewer] WARNING: %s.py is version %r, expected %r – "
              "replace the old file with the current one!"
              % (_mod.__name__, _ver, PREVIEWER_VERSION))

# ============================== Provider ===================================

# → REF ENT-DOC-1
class PanelState:

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
        self.toggle_btn = None
        self.hpaned.connect("size-allocate", self._on_size_allocate)
        # F46 X (0.34.1): paint the Paned handle window – in light mode
        # the left edge otherwise showed black.
        self.hpaned.connect("draw", self._on_hpaned_draw)

    # → REF ENT-DOC-2
    def _install_toolbar_toggle(self):
        # Idempotent: reconciliation may run repeatedly; a button
        # already packed is never added twice. → REF ENT-TOGGLE-1
        if self.toggle_btn is not None or getattr(
                self.window, "_previewer_toggle", None) is not None:
            return
        icon = pick_icon(("builder-view-right-pane-symbolic",
                          "view-right-pane", "sidebar-show-symbolic",
                          "sidebar-symbolic"), "pan-end-symbolic")
        # Route 1: title bar as GtkHeaderBar (CSD desktops) – add the
        # button at the far right via pack_end.
        try:
            bar = self.window.get_titlebar()
        except Exception:
            bar = None
        if isinstance(bar, Gtk.HeaderBar):
            btn = Gtk.ToggleButton()
            btn.set_image(Gtk.Image.new_from_icon_name(
                icon, Gtk.IconSize.BUTTON))
            btn.set_relief(Gtk.ReliefStyle.NONE)
            self._pack_toggle(btn, icon, "title bar",
                              lambda b: bar.pack_end(b))
            return
        # Route 2: classic Nemo – the view buttons sit in a GtkToolbar
        # (NemoToolbar is a GtkBox around it); insert right after them.
        toolbar = self._find_first_widget(
            self.window, lambda w: isinstance(w, Gtk.Toolbar))
        if toolbar is None:
            dbg("Preview toggle: no HeaderBar or GtkToolbar "
                "found – Ctrl+Alt+P only")
            return
        btn = Gtk.ToggleToolButton()
        btn.set_icon_name(icon)
        pos = self._pos_after_view_buttons(toolbar)
        self._pack_toggle(btn, icon, "toolbar",
                           lambda b: toolbar.insert(b, pos))

    # → REF ENT-DOC-3
    def _pack_toggle(self, btn, icon, where, pack):
        btn.set_tooltip_text("Preview side panel (Ctrl+Alt+P)")
        # F40: sync the initial state – notify::visible only fires on
        # change; set_active before connecting triggers nothing (→ REF ENT-TOGGLE-1).
        btn.set_active(self.panel.get_visible())
        btn.connect("toggled", self._on_toolbar_toggle)
        self.toggle_btn = btn
        pack(btn)
        # Track state when the panel is toggled elsewhere (Ctrl+Alt+P,
        # show_at_start setting).
        self.panel.connect("notify::visible", self._on_panel_visibility)
        try:
            self.window._previewer_toggle = btn
        except Exception as e:
            dbg("previewer/_pack_toggle: suppressed: %s" % e)
        btn.show()
        dbg("Preview toggle placed in Nemo's %s (icon: %s)"
            % (where, icon))

    # → REF ENT-DOC-4
    def _find_first_widget(self, widget, pred):
        if pred(widget):
            return widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                found = self._find_first_widget(child, pred)
                if found is not None:
                    return found
        return None

    # → REF ENT-DOC-5
    def _pos_after_view_buttons(self, toolbar):
        pos = -1
        for item in toolbar.get_children():
            child = item.get_child()
            if child is not None and self._has_view_icon(child):
                pos = toolbar.get_item_index(item)
        return -1 if pos < 0 else pos + 1

    # → REF ENT-DOC-6
    def _has_view_icon(self, widget):
        if isinstance(widget, Gtk.Image):
            try:
                name = widget.get_icon_name()[0]
            except Exception:
                name = None
            if name and name.startswith("view-"):
                return True
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                if self._has_view_icon(child):
                    return True
        return False

    # → REF ENT-DOC-7
    def _on_toolbar_toggle(self, btn):
        if btn.get_active():
            self.panel.show_all()
        else:
            self.panel.hide()

    # → REF ENT-DOC-8
    def _on_panel_visibility(self, panel, prop):
        try:
            self.toggle_btn.set_active(panel.get_visible())
        except Exception as e:
            dbg("previewer/_on_panel_visibility: suppressed: %s" % e)

    # → REF ENT-DOC-9
    def _on_hpaned_draw(self, paned, cr):
        try:
            self.panel._paint_background(paned, cr)
        except Exception as e:
            dbg("previewer/_on_hpaned_draw: suppressed: %s" % e)
        return False

    def _on_size_allocate(self, paned, alloc):
        if not self.pos_pending:
            return
        # F12: start width from the config; without config the
        # default PANEL_WIDTH (350 px) applies – since 0.41.0 the
        # settings spin button value wins, not dragged widths.
        width = getattr(self.panel, "_panel_width", None) or PANEL_WIDTH
        if alloc.width > width + 200:
            paned.set_position(alloc.width - width)
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


# → REF ENT-DOC-10
def _reconcile(st):
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
        dbg("Injection: unexpected window structure (%s)"
            % type_name(top_box))
        return

    # Injection target: the widget DIRECTLY under the main box on the
    # path up from the view – found by following parent pointers.
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
        dbg("Injection: view not under main box – chain: %s"
            % " < ".join(chain))
        return

    # If the view already sits under our HPaned, the found node IS our
    # own HPaned – already injected; re-injecting would destroy the tree.
    if target is st.hpaned:
        st._view_ok(view)
        return

    # Already correctly injected?
    if (st.hpaned.get_parent() is top_box
            and st.hpaned.get_child1() is target):
        st._view_ok(view)
        return

    # Inject anew: undo the old state
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
            # Validate BEFORE removing anything – otherwise the widget
            # tree can be destroyed beyond repair.
            if (not all(isinstance(v, int) and v >= 0 for v in (left, top))
                    or not all(isinstance(v, int) and v >= 1
                               for v in (width, height))):
                dbg("Injection: grid props unreadable "
                    "(%r, %r, %r, %r) – aborted, Nemo untouched"
                    % (left, top, width, height))
                return
            top_box.remove(target)
            st.hpaned.pack1(target, True, False)
            st.hpaned.pack2(st.panel, False, False)
            top_box.attach(st.hpaned, left, top, width, height)
        else:
            dbg("Injection: main box neither Box nor Grid (%s)"
                % type_name(top_box))
            return
        st.pos_pending = True
        st.hpaned.show()
        st.panel.show_all()
        # F12: apply the config only AFTER show_all – requested
        # invisibility would otherwise be overridden at startup.
        _apply = getattr(st.panel, "apply_start_settings", None)
        if callable(_apply):
            _apply()
        dbg("Panel injected at window edge (target: %s)"
            % type_name(target))
    except Exception:
        traceback.print_exc()
        return

    st._view_ok(view)


# → REF ENT-DOC-11
def _detach(st):
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


# → REF ENT-DOC-12
def _connect_view_signals(st, view):
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
                        diag("Signal %s received (%s)" % (_s, type_name(_w))),
                        _dump_a11y_once(st),
                        _refresh_soon(st))[-1])
            except Exception:
                continue
            st.view_handlers.append((w, hid))
            names_found.add(sig)

    # Never register signal handlers on ATK objects: they are often
    # short-lived on folder changes and caused disconnect warnings.

    diag("View connected: %s – selection signals: %s"
        % (type_name(view), ", ".join(sorted(names_found)) or "none"))


# → REF ENT-DOC-13
def _dump_a11y_once(st):
    if not VERBOSE_DIAG:
        return
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
            dbg("%s: no accessible available" % tag)
            return
    except Exception:
        dbg("%s: no accessible available" % tag)
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
            # Log the cause of the seemingly empty a11y tree once.
            if not getattr(_dump_a11y_once, "_n_children_err", None):
                _dump_a11y_once._n_children_err = repr(exc)
                dbg("%s: get_n_children() failed: %r – "
                    "probing remaining children via ref_child()"
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
        dbg("%s d%d children=%d role=%s name=%r %s"
            % (tag, depth, n, role, name, " ".join(extra)))
        for child in _atk_children(acc, max_children=60):
            rec(child, depth + 1)

    rec(root, 0)
    dbg("%s – end of dump" % tag)


# → REF ENT-DOC-14
def _view_ok(self, view):
    if self.view is not view:
        for obj, hid in self.view_handlers:
            try:
                if obj.handler_is_connected(hid):
                    obj.disconnect(hid)
            except Exception as e:
                # Object/handler may already be torn down by Nemo.
                dbg("previewer/_view_ok: suppressed: %s" % e)
        self.view_handlers = []
        self.view = view
        self._a11y_dumps = 0
        try:
            _connect_view_signals(self, view)
        except Exception:
            traceback.print_exc()
        _dump_a11y_once(self)
        _refresh_soon(self)
        # F40: add the button later (if the toolbar was not there yet)
        # – idempotent, no double packing.
        self._install_toolbar_toggle()


PanelState._view_ok = _view_ok


def _refresh(st):
    try:
        # Always look up the LIVE view: st.view may point to an
        # already torn-down slot after a folder change.
        view = find_view(st.window)
        if view is None:
            return
        names, strategy = SelectionReader.read(view, st.dir_path)
        # Diagnostics per concrete view type, not once per window:
        # Nemo may swap ListView for IconView on view switches.
        diag_key = "_selection_diag_" + type_name(view)
        if not getattr(st, diag_key, False):
            setattr(st, diag_key, True)
            _dump_widget_tree(view)
        if names is None:
            # No strategy could read – throttled debug message
            now = GLib.get_monotonic_time()
            if now - st.none_dbg_at > 5000000:  # at most every 5 seconds
                st.none_dbg_at = now
                dbg("Selection unreadable (view: %s)" % type_name(view))
            return
        if names != st.last_sel:
            dbg("Selection changed: %r (via %s)" % (names, strategy))
            st.last_sel = names
            st.panel.set_selection(names, st.dir_path)
    except Exception:
        traceback.print_exc()


# → REF ENT-DOC-15
def _refresh_soon(st):
    GLib.idle_add(lambda: (_refresh(st), False)[1])


# → REF ENT-DOC-16
def _poll(st):
    try:
        _reconcile(st)
        _refresh(st)
    except Exception:
        traceback.print_exc()
    return True


# → REF ENT-DOC-17
def _on_window_destroyed(window, st):
    try:
        if st.poll_id:
            GLib.source_remove(st.poll_id)
        st.poll_id = 0
    except Exception as e:
        dbg("previewer/_on_window_destroyed: suppressed: %s" % e)
    return False


def _get_state(window):
    st = getattr(window, "_previewer_state", None)
    if st is None:
        st = PanelState(window)
        window._previewer_state = st
        # 0.9.1: tear down the timer when the window disappears.
        try:
            window.connect("destroy", _on_window_destroyed, st)
        except Exception as e:
            dbg("previewer/_get_state: suppressed: %s" % e)
        st.poll_id = GLib.timeout_add(POLL_MS, _poll, st)
        dbg("PanelState created for window")
    return st


# → REF ENT-DOC-18
def _on_crowbar_placed(crowbar, window, uri, tries):
    st = _get_state(window)
    if crowbar.get_parent() is None:
        tries[0] += 1
        return tries[0] < 40  # not placed yet → keep waiting
    _reconcile(st)
    _refresh(st)
    return False


# ------- Provider class (dynamic, so NameAndDescProvider stays optional) ----

# → REF ENT-DOC-19
def _is_desktop_window(window):
    name = type_name(window)
    # Cinnamon/Nemo versions differ in their concrete type names.
    if "desktop" in name.lower():
        return True
    # Extra widget-tree check: desktop icon views must never serve
    # as the anchor for the injection.
    try:
        for child in walk(window):
            if type_name(child) == "NemoDesktopIconView":
                return True
    except Exception as e:
        dbg("previewer/_is_desktop_window: suppressed: %s" % e)
    return False


# → REF ENT-DOC-20
def _get_widget(self, uri, window):
    window_type = type_name(window)
    dbg("get_widget called for %s (window type: %s)" % (uri, window_type))
    if _is_desktop_window(window):
        dbg("Desktop window detected – no preview panel")
        return None
    st = _get_state(window)
    new_dir = _uri_to_dir(uri)
    if new_dir != st.dir_path:
        st.last_sel = None
        st.panel.set_selection([], new_dir)
    st.dir_path = new_dir   # immediately: new folder is known
    crowbar = Gtk.Box()
    crowbar.set_size_request(-1, 0)
    crowbar.set_no_show_all(True)
    tries = [0]
    GLib.idle_add(_on_crowbar_placed, crowbar, window, uri, tries)
    return crowbar


def _get_name_and_desc(self):
    return ["previewer:::"
            "Docked preview of the selected file:::"]


_bases = [GObject.GObject, Nemo.LocationWidgetProvider]
if hasattr(Nemo, "NameAndDescProvider"):
    _bases.append(Nemo.NameAndDescProvider)

_provider_dict = {
    "get_widget": _get_widget,
    "get_name_and_desc": _get_name_and_desc,
}

Provider = type("NemoPreviewerProvider", tuple(_bases), _provider_dict)


# ------------------------- Gtk protocol filter -------------------------------
# → REF ENT-FILTER-1

_GTK_FOREACH_MSG = "gtk_container_foreach: assertion 'GTK_IS_CONTAINER"


def _install_log_filter():
    def handler(domain, level, message, *user_data):
        if message and _GTK_FOREACH_MSG in message:
            return
        try:
            GLib.log_default_handler(domain, level, message)
        except Exception as e:
            dbg("previewer/handler: suppressed: %s" % e)
    try:
        GLib.log_set_handler("Gtk",
                             GLib.LogLevelFlags.LEVEL_CRITICAL, handler)
    except Exception as e:
        dbg("previewer/handler: suppressed: %s" % e)


_install_log_filter()

dbg("previewer (entry) v%s ready" % PREVIEWER_VERSION)