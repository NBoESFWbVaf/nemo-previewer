#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_util.py – Version 0.62.1

Shared helpers and constants: logging and diagnostics, step
trace, type helpers, pixbuf and byte-reading helpers.
"""

import math
import os
import sys
import time


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
TOGGLE_ACCEL_KEY = Gdk.KEY_p
TOGGLE_ACCEL_MODS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK
# F65: debug log file – the settings toggle or NEMO_PREVIEWER_DEBUG=1
# enables it; XDG_STATE_HOME is the standard place for user logs.
DEBUG_LOG_CAP = 512 * 1024
DEBUG_LOG_MAX_AGE = 7 * 86400  # F65b: retention, logs vanish after a week
LOG_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME")
    or os.path.expanduser("~/.local/state"),
    "nemo-previewer")
LOG_FILE = os.path.join(LOG_DIR, "previewer.log")


# ------------------------------- Helpers -----------------------------------

# F65: debug logging state – the env var NEMO_PREVIEWER_DEBUG=1
# wins over the settings toggle (power-user one-shot, no traces).
DEBUG_ENV = os.environ.get(
    "NEMO_PREVIEWER_DEBUG", "").strip().lower() not in ("", "0", "false")
DEBUG_LOG = DEBUG_ENV
_log_rotated = False


# → REF UT-LOG-1
def set_debug_log(on):
    # Deploy feedback: live switch – OFF takes effect during the
    # session; the env var alone still wins.
    global DEBUG_LOG
    DEBUG_LOG = DEBUG_ENV or bool(on)


def _debug_log_file(msg):
    # F65: timestamped append; rotates ONCE per session at the first
    # write (cap 512 KB, keeps exactly ONE .old backup).
    global _log_rotated
    try:
        if not _log_rotated:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.exists(LOG_FILE) and \
                    os.path.getsize(LOG_FILE) > DEBUG_LOG_CAP:
                if os.path.exists(LOG_FILE + ".old"):
                    os.remove(LOG_FILE + ".old")
                os.rename(LOG_FILE, LOG_FILE + ".old")
            _log_rotated = True
            with open(LOG_FILE, "a") as fh:
                fh.write("%s [previewer] --- session start, version %s"
                         " ---\n"
                         % (time.strftime("%Y-%m-%d %H:%M:%S"),
                            PREVIEWER_VERSION))
        with open(LOG_FILE, "a") as fh:
            fh.write("%s [previewer] %s\n"
                     % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception as e:
        print("[previewer] debug log file: suppressed: %s" % e)


def debug_log_active():
    # F65: live state for the red recording dot in the header.
    return DEBUG_LOG


def debug_log_cleanup():
    # F65b: delete stale debug logs (mtime older than 7 days) –
    # runs at every panel start, even with logging off.
    try:
        cutoff = time.time() - DEBUG_LOG_MAX_AGE
        for path in (LOG_FILE, LOG_FILE + ".old"):
            if os.path.exists(path) and \
                    os.path.getmtime(path) < cutoff:
                os.remove(path)
    except Exception as e:
        print("[previewer] debug log cleanup: suppressed: %s" % e)


# → REF UT-DOC-1
def dbg(msg):
    # Deploy feedback: debug output is fully GATED – with the
    # toggle and the env var off, dbg writes NOTHING at all.
    if not DEBUG_LOG:
        return
    _debug_log_file(msg)
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

# --- F69: font sizes for text previews and info tables (CSS) ---


# → REF UT-DOC-16
TEXT_SIZE_CSS_CLASS = "pvw-text-size"
META_SIZE_CSS_CLASS = "pvw-meta-size"
_SIZE_CSS_PROVIDER = None


def apply_font_size_css(text_px, meta_px):
    # F69: one provider on the default screen (K11 pattern); a rule
    # exists only while the size is > 0 – 0 means the theme font.
    global _SIZE_CSS_PROVIDER
    try:
        if _SIZE_CSS_PROVIDER is None:
            _SIZE_CSS_PROVIDER = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), _SIZE_CSS_PROVIDER,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        rules = []
        if text_px:
            rules.append(".%s { font-size: %dpx; }"
                         % (TEXT_SIZE_CSS_CLASS, int(text_px)))
        if meta_px:
            rules.append(".%s { font-size: %dpx; }"
                         % (META_SIZE_CSS_CLASS, int(meta_px)))
        _SIZE_CSS_PROVIDER.load_from_data(
            "\n".join(rules).encode("utf-8"), -1)
    except Exception as e:
        dbg("util/apply_font_size_css: suppressed: %s" % e)


# → REF UT-DOC-16
def system_font_size_px():
    # F69: the theme font size in px – measured from a fresh
    # TextView, so the size spins start at the system value.
    try:
        desc = Gtk.TextView().get_style_context().get_font(
            Gtk.StateFlags.NORMAL)
        size = desc.get_size()
        if desc.get_size_is_absolute():
            px = int(round(float(size) / Pango.SCALE))
        else:
            px = int(round(size * 96.0 / 72.0 / Pango.SCALE))
        if 0 < px <= 28:
            return px
    except Exception as e:
        dbg("util/system_font_size_px: suppressed: %s" % e)
    return 0


# → REF UT-DOC-10
def pack_hint(box, text):
    lbl = Gtk.Label(label=text)
    lbl.set_line_wrap(True)
    lbl.get_style_context().add_class("dim-label")
    lbl.set_halign(Gtk.Align.START)
    box.pack_start(lbl, False, False, 0)


# → REF UT-DOC-11
def pack_meta_grid(rows, container, wrap=False, bold_keys=False,
                   italic_values=False, title_width=None):
    grid = Gtk.Grid()
    # F69: class carries the configurable info table font size.
    grid.get_style_context().add_class(META_SIZE_CSS_CLASS)
    grid.set_row_spacing(2)
    grid.set_column_spacing(10)
    for i, (k, v) in enumerate(rows):
        # F35: labels end with a colon.
        if not k.endswith(":"):
            k += ":"
        kl = Gtk.Label()
        if bold_keys:
            # F54: bold labels instead of dim (EML header, user
            # request); markup needs escaped text.
            kl.set_markup("<b>%s</b>" % GLib.markup_escape_text(k))
        else:
            kl.set_label(k)
            kl.get_style_context().add_class("dim-label")
        kl.set_halign(Gtk.Align.END)
        if title_width:
            # F52: fixed title column (ICS event table); ellipsize
            # plus tooltip keeps the width at the requested pixels.
            kl.set_size_request(title_width, -1)
            kl.set_ellipsize(Pango.EllipsizeMode.END)
            kl.set_tooltip_text(k)
        vl = Gtk.Label()
        if italic_values:
            # F54: italic values (EML header, user request).
            vl.set_markup("<i>%s</i>" % GLib.markup_escape_text(v))
        else:
            vl.set_label(v)
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
def build_text_view(view, text, font, markup, spacing=0):
    view.set_editable(False)
    view.set_cursor_visible(False)
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    # F69: class carries the configurable text preview font size.
    view.get_style_context().add_class(TEXT_SIZE_CSS_CLASS)
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
    # F25: extra line spacing – ONE TextTag over the whole buffer,
    # reapplied on every rebuild; the clipboard stays untouched.
    if spacing:
        tag = buf.create_tag("previewer-line-spacing",
                             pixels_above_lines=int(spacing))
        buf.apply_tag(tag, buf.get_start_iter(), buf.get_end_iter())
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
PREVIEWER_VERSION = "0.62.1"
dbg("previewer_util %s loaded" % PREVIEWER_VERSION)