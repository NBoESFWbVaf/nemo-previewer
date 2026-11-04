#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_util.py – Version 0.52.2

Shared helpers and constants: logging and diagnostics, step
trace, type helpers, pixbuf and byte-reading helpers.
"""

import math
import os
import sys


import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Pango', '1.0')

from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf, Pango

# ------------------------------ Configuration ------------------------------
# F12: default start width, configurable in the settings window and
# the keyfile; a dragged width becomes the new start width.
PANEL_WIDTH = 350          # panel start width in pixels
PANEL_MIN_WIDTH = 260      # smallest allowed width while dragging
POLL_MS = 500              # selection polling timer (safety net)
MAX_TEXT_BYTES = 256 * 1024
MAX_TEXT_LINES = 2000
MAX_IMAGE_HEIGHT = 1600
MAX_EBOOK_CHARS = 30000    # book text shown in the e-book preview
TOGGLE_ACCEL_KEY = Gdk.KEY_p
TOGGLE_ACCEL_MODS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK


# ------------------------------- Helpers -----------------------------------

# → REF UT-DOC-1
def dbg(msg):
    print("[previewer] %s" % msg)


# Verbose diagnostics (dumps, signals) stay silent in daily use; set
# True to investigate a new Nemo version or a new system.
VERBOSE_DIAG = True


# → REF UT-DOC-2
def diag(msg):
    if VERBOSE_DIAG:
        dbg(msg)


# F45: step trace for all functions via one central sys.settrace
# hook; level via NEMO_PREVIEWER_TRACE (1/call, line). → REF UT-TRACE-1
# → REF UT-DOC-3
def install_step_trace():
    level = os.environ.get("NEMO_PREVIEWER_TRACE", "").strip().lower()
    if level not in ("1", "call", "calls", "line", "lines"):
        return False
    want_lines = level.startswith("line")

    def _fmt(val):
        try:
            s = repr(val)
        except Exception:
            s = "<no repr>"
        return s if len(s) <= 60 else s[:57] + "…"

    def _tracer(frame, event, arg):
        try:
            base = os.path.basename(frame.f_code.co_filename)
            if not base.startswith("previewer_"):
                return None
            name = frame.f_code.co_name
            if name in ("dbg", "diag"):
                return None
            mod = base[:-3]
            if event == "call":
                keys = frame.f_code.co_varnames[:frame.f_code.co_argcount]
                args = ", ".join(_fmt(frame.f_locals.get(k)) for k in keys)
                dbg("TRACE→ %s:%s(%s)" % (mod, name, args))
            elif event == "return":
                dbg("TRACE← %s:%s = %s" % (mod, name, _fmt(arg)))
            elif event == "exception":
                dbg("TRACE! %s:%s raised %s: %s"
                    % (mod, name, arg[0].__name__, _fmt(arg[1])))
            elif event == "line" and want_lines:
                dbg("TRACE· %s:%s L%d" % (mod, name, frame.f_lineno))
            return _tracer
        except Exception:
            return None

    sys.settrace(_tracer)
    dbg("Step trace ON (level: %s)"
        % ("line" if want_lines else "call"))
    return True


# → REF UT-DOC-4
def pick_icon(names, fallback):
    try:
        theme = Gtk.IconTheme.get_default()
        for name in names:
            if theme.has_icon(name):
                return name
    except Exception as e:
        dbg("util/pick_icon: suppressed: %s" % e)
    return fallback


# → REF UT-DOC-5
def walk(widget):
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


def human_size(num):
    try:
        return GLib.format_size(num)
    except Exception:
        return "%d B" % num


def format_seconds(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


# → REF UT-DOC-6
def query_file_info(path):
    mime, size, mtime = "unknown", -1, -1
    try:
        f = Gio.File.new_for_path(path)
        info = f.query_info(
            "standard::size,standard::content-type,time::modified",
            Gio.FileQueryInfoFlags.NONE, None)
        mime = info.get_content_type() or mime
        size = info.get_size()
        mtime = info.get_attribute_uint64("time::modified")
    except Exception as e:
        dbg("util/query_file_info: suppressed: %s" % e)
    return mime, size, mtime


# --- Shared base helpers (F31: formerly in previewer_panel.py) ---

# → REF UT-DOC-7
def _pixbuf_from_bytes(data, max_w=4096, max_h=4096, orig=None):
    loader = GdkPixbuf.PixbufLoader()

    def _on_size(loader, w, h):
        if orig is not None:
            try:
                orig["w"], orig["h"] = w, h
            except Exception as e:
                dbg("util/_on_size: suppressed: %s" % e)
        if w > max_w or h > max_h:
            f = min(max_w / max(w, 1), max_h / max(h, 1))
            try:
                loader.set_size(max(1, int(w * f)),
                                max(1, int(h * f)))
            except Exception as e:
                dbg("util/_on_size: suppressed: %s" % e)

    loader.connect("size-prepared", _on_size)
    loader.write(data)
    loader.close()
    return loader.get_pixbuf()


# → REF UT-DOC-8
def _zf_read_capped(zf, name, cap):
    with zf.open(name) as zh:
        return zh.read(cap)


# → REF UT-DOC-9
def _xml_dtd_rejected(data, source):
    head = data[:65536]
    if isinstance(head, bytes):
        head = head.decode("utf-8", "replace")
    low = head.lower()
    if "<!doctype" in low or "<!entity" in low:
        dbg("util/_xml_dtd_rejected: %s: DTD rejected (R10)" % source)
        return True
    return False

# ------------------------------ Widget helpers ------------------------------

# → REF UT-DOC-10
def pack_hint(box, text):
    lbl = Gtk.Label(label=text)
    lbl.set_line_wrap(True)
    lbl.get_style_context().add_class("dim-label")
    lbl.set_halign(Gtk.Align.START)
    box.pack_start(lbl, False, False, 0)


# → REF UT-DOC-11
def pack_meta_grid(rows, container, wrap=False):
    grid = Gtk.Grid()
    grid.set_row_spacing(2)
    grid.set_column_spacing(10)
    for i, (k, v) in enumerate(rows):
        # F35: labels end with a colon.
        if not k.endswith(":"):
            k += ":"
        kl = Gtk.Label(label=k)
        kl.set_halign(Gtk.Align.END)
        kl.get_style_context().add_class("dim-label")
        vl = Gtk.Label(label=v)
        vl.set_halign(Gtk.Align.START)
        if wrap:
            vl.set_line_wrap(True)
            vl.set_ellipsize(Pango.EllipsizeMode.NONE)
        else:
            vl.set_ellipsize(Pango.EllipsizeMode.END)
        vl.set_hexpand(True)
        vl.set_tooltip_text(v)
        grid.attach(kl, 0, i, 1, 1)
        grid.attach(vl, 1, i, 1, 1)
    # F38: the caller decides the target – image tables belong in
    # the 40% info area of the image split.
    container.pack_start(grid, False, False, 0)


# → REF UT-DOC-12
def cover_round_path(cr, x, y, w, h, r):
    r = min(r, w / 2.0, h / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -0.5 * math.pi, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


# → REF UT-DOC-13
def build_scaled_image(src, max_h, upscale=False, keep_height=False,
                       max_upscale=1.0, frac_h=None):
    img = Gtk.Image()
    # Horizontally centered: small previews (cover, office
    # thumbnail) do not stick to the left edge.
    img.set_halign(Gtk.Align.CENTER)
    img.set_valign(Gtk.Align.START)
    scroll = Gtk.ScrolledWindow()
    # AUTOMATIC in both directions: stops the child minimum
    # width from propagating – the pane stays freely draggable.
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.add(img)
    item = {"img": img, "scroll": scroll, "src": src, "maxh": max_h,
            "upscale": upscale, "maxup": max_upscale,
            "keeph": keep_height, "frac": frac_h, "lastw": 0}
    return img, scroll, item


# → REF UT-DOC-14
def build_text_view(view, text, font, markup):
    view.set_editable(False)
    view.set_cursor_visible(False)
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    if font is not None:
        view.override_font(Pango.FontDescription(font))
    # Padding so the text does not stick to the border
    view.set_left_margin(10)
    view.set_right_margin(10)
    view.set_top_margin(8)
    view.set_bottom_margin(8)
    buf = view.get_buffer()
    if markup is not None:
        buf.insert_markup(buf.get_end_iter(), markup, -1)
    else:
        buf.set_text(text)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.set_shadow_type(Gtk.ShadowType.IN)
    scroll.add(view)
    return scroll

# → REF UT-DOC-15
def center_window(win, width):
    try:
        mon = Gdk.Display.get_default().get_primary_monitor()
        if mon is None:
            mon = Gdk.Display.get_default().get_monitor(0)
        rect = mon.get_geometry()
        height = int(rect.height * 0.6)
        dbg("util/center_window: monitor %dx%d -> window %dx%d"
            % (rect.width, rect.height, width, height))
        win.set_default_size(width, height)
        win.set_position(Gtk.WindowPosition.CENTER)

        def _force_size(_win=None):
            try:
                win.resize(width, height)
            except Exception as e:
                dbg("util/center_window/_force_size: suppressed: %s" % e)
            return False
        GLib.idle_add(_force_size)
    except Exception as e:
        dbg("util/center_window: suppressed: %s" % e)

# Version: checked at load time by the entry point (previewer.py).
PREVIEWER_VERSION = "0.52.2"
dbg("previewer_util %s loaded" % PREVIEWER_VERSION)