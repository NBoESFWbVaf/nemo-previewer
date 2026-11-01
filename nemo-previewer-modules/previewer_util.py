#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_util.py – Version 0.42.0

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

def dbg(msg):
    """Debug-Ausgabe – sichtbar, wenn Nemo im Terminal gestartet wird."""
    print("[previewer] %s" % msg)


# Verbose diagnostics (dumps, signals) stay silent in daily use; set
# True to investigate a new Nemo version or a new system.
VERBOSE_DIAG = True


def diag(msg):
    """Diagnose-Ausgabe – nur sichtbar bei VERBOSE_DIAG=True."""
    if VERBOSE_DIAG:
        dbg(msg)


# F45: step trace for all functions via one central sys.settrace
# hook; level via NEMO_PREVIEWER_TRACE (1/call, line). → REF UT-TRACE-1
def install_step_trace():
    """
    F45 (Nutzer-Wunsch): sys.settrace-Hook installieren, wenn
    NEMO_PREVIEWER_TRACE gesetzt ist (1/call oder line). Rückgabe
    True, wenn der Trace läuft. Verfolgt nur Dateien mit Präfix
    previewer_ – Nemo, GTK und fremde Extensions bleiben frei;
    dbg/diag sind ausgenommen, damit der Logger sich nicht selbst
    protokolliert; Fehler im Hook schalten still ab.
    """
    level = os.environ.get("NEMO_PREVIEWER_TRACE", "").strip().lower()
    if level not in ("1", "call", "calls", "line", "lines"):
        return False
    want_lines = level.startswith("line")

    def _fmt(val):
        try:
            s = repr(val)
        except Exception as e:
            dbg("util/_fmt: suppressed: %s" % e)
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
        except Exception as e:
            dbg("util/_tracer: suppressed: %s" % e)

    sys.settrace(_tracer)
    dbg("Step trace ON (level: %s)"
        % ("line" if want_lines else "call"))
    return True


def pick_icon(names, fallback):
    """
    F40: Das erste im aktiven Icon-Thema VORHANDENE Symbol aus names
    zurückgeben – Mint-/Nemo-Themes liefern nicht jeden Namen –, sonst
    fallback. So bleibt kein Knopf ersatzlos ohne Bild.
    """
    try:
        theme = Gtk.IconTheme.get_default()
        for name in names:
            if theme.has_icon(name):
                return name
    except Exception as e:
        dbg("util/pick_icon: suppressed: %s" % e)
    return fallback


def walk(widget):
    """Alle Widgets im Teilbaum inkl. widget selbst liefern."""
    yield widget
    if isinstance(widget, Gtk.Container):
        try:
            children = widget.get_children()
        except Exception as e:
            dbg("util/walk: suppressed: %s" % e)
        for child in children:
            yield from walk(child)


def type_name(w):
    try:
        return w.__gtype__.name
    except Exception as e:
        dbg("util/type_name: suppressed: %s" % e)


def human_size(num):
    try:
        return GLib.format_size(num)
    except Exception as e:
        dbg("util/human_size: suppressed: %s" % e)


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
    except Exception as e:
        dbg("util/query_file_info: suppressed: %s" % e)
    return mime, size, mtime


# --- Shared base helpers (F31: formerly in previewer_panel.py) ---

def _pixbuf_from_bytes(data, max_w=4096, max_h=4096, orig=None):
    """
    Bytes zu einer Pixbuf dekodieren – GdkPixbuf riecht das Format –
    mit Decode-Deckel (0.9.2): Das size-prepared-Signal feuert, BEVOR
    die Pixeldaten alloziert werden; set_size() verkleinert dort die
    Dekodierung. Ein Bild, das nur im Header Riesenmaße deklariert
    (PNG-Bombe), kostet damit nur die gedeckelte Fläche statt
    Gigabytes. Bei Dekodierfehlern wird wie bisher geworfen (der
    jeweilige Aufrufer fängt).
    orig: optionales Dict – wird mit den VOR der Deckelung gemeldeten
    Originalmaßen gefüllt (R9): size-prepared meldet sie, bevor
    set_size verkleinert, sodass die Bild-Vorschau die echten Maße
    anzeigen kann, obwohl gedeckelt dekodiert wird.
    """
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


def _zf_read_capped(zf, name, cap):
    """
    R4: Ein ZIP-Mitglied mit Lese-Deckel lesen – Schutz vor Dekompressions-
    Bomben: gezippte XHTML-Kapitel können entpackt ein Vielfaches ihrer
    gepackten Größe belegen und das Panel wäre für Sekunden blockiert.
    Alles jenseits des Deckels wird bewusst abgeschnitten – für die
    Vorschau reicht der Anfang des Kapitels bzw. Bildes.
    """
    with zf.open(name) as zh:
        return zh.read(cap)

# ------------------------------ Widget helpers ------------------------------

def pack_hint(box, text):
    """
    S6 (0.42.0): Dim-Label mit Zeilenumbruch, linksbündig, gepackt
    in den Container – der frühere _hint-Teil des Panel-Mixins,
    jetzt util für Panel, Media, Docs und Text.
    """
    lbl = Gtk.Label(label=text)
    lbl.set_line_wrap(True)
    lbl.get_style_context().add_class("dim-label")
    lbl.set_halign(Gtk.Align.START)
    box.pack_start(lbl, False, False, 0)


def pack_meta_grid(rows, container):
    """
    Schlüssel-Wert-Tabelle (dim-Label links, Wert rechts mit
    END-Ellipsize und Tooltip) – zentraler Helfer für E-Book-,
    EML-, Audio- und Video-Infos. 0.9.1: zuvor zusätzlich mehrfach
    identisch inline gebaut; die Inline-Kopien sind entfallen.
    F35: Jede Bezeichnung bekommt automatisch einen Doppelpunkt
    am Ende (falls nicht bereits vorhanden).
    F38: packt an jede übergebene Stelle – Bild-Vorschauen geben
    ihren 40-%-Info-Bereich mit.
    S6 (0.42.0): Als Mixin-Methode _meta_grid des Panels geboren,
    jetzt util-weit nutzbar.
    """
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
        vl.set_ellipsize(Pango.EllipsizeMode.END)
        vl.set_hexpand(True)
        vl.set_tooltip_text(v)
        grid.attach(kl, 0, i, 1, 1)
        grid.attach(vl, 1, i, 1, 1)
    # F38: the caller decides the target – image tables belong in
    # the 40% info area of the image split.
    container.pack_start(grid, False, False, 0)


def cover_round_path(cr, x, y, w, h, r):
    """
    F34: Rechteck mit runden Ecken als aktuellen Cairo-Pfad.
    S6 (0.42.0): Aus previewer_render_media (staticmethod
    _cover_round_path) nach util gezogen – auch Text-Cover nutzen
    ihn.
    """
    r = min(r, w / 2.0, h / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -0.5 * math.pi, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def build_scaled_image(src, max_h, upscale=False, keep_height=False,
                       max_upscale=1.0, frac_h=None):
    """
    S6 (0.42.0): Bild im Scroll-Fenster – der Widget-Teil der
    Panel-Methode _scaled_image (R3-Dokumentation bleibt dort);
    Registrierung und Erst-Skalierung bleiben beim Panel.
    """
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


def build_text_view(view, text, font, markup):
    """
    S6 (0.42.0): TextView-Konfiguration und Pufferfüllung – der
    Widget-Teil der Panel-Methode _text_view; Zeilennummern,
    GtkSourceView-Raterei und Packen bleiben beim Panel.
    """
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

# Version: checked at load time by the entry point (previewer.py).
PREVIEWER_VERSION = "0.42.0"
dbg("previewer_util %s loaded" % PREVIEWER_VERSION)