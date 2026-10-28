#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Helfer-Modul (previewer_util.py)
===========================================

STAND: Version 0.12.0 – aktuelle Fassung (F12-Konfigurations-Start:
keine Änderungen in dieser Datei – nur Versions-Sync mit den drei
anderen Modulen).

Gemeinsame Bausteine der Nemo-Extension "Previewer": Logging, kleine
Hilfsfunktionen und die zentralen Konfigurations-Konstanten. Teil der
vierteiligen Extension (Einstieg und Übersicht: previewer.py;
Installation: INSTALL.md im Repository).
"""

import os


import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, Gio, GLib

# ------------------------------ Konfiguration ------------------------------
PANEL_WIDTH = 340          # Startbreite des Panels in Pixeln
PANEL_MIN_WIDTH = 260      # kleinste erlaubte Breite (durch Ziehen)
POLL_MS = 500              # Timer für Auswahl-Abgleich (Sicherheitsnetz)
MAX_TEXT_BYTES = 256 * 1024
MAX_TEXT_LINES = 2000
MAX_IMAGE_HEIGHT = 1600
MAX_EBOOK_CHARS = 30000    # Buchtext-Anfang in der E-Book-Vorschau
TOGGLE_ACCEL_KEY = Gdk.KEY_p
TOGGLE_ACCEL_MODS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK


# ------------------------------ Hilfsfunktionen -----------------------------

def dbg(msg):
    """Debug-Ausgabe – sichtbar, wenn Nemo im Terminal gestartet wird."""
    print("[previewer] %s" % msg)


# Diagnose-Ausgaben (a11y-/Widget-/Auswahl-Dumps, Signal-Meldungen) sind
# im Alltagsbetrieb still. Auf True setzen, wenn eine neue Nemo-Version
# oder ein neues System untersucht werden soll – dann erscheinen die
# ausführlichen Dumps wie in der Entwicklungsphase.
VERBOSE_DIAG = False


def diag(msg):
    """Diagnose-Ausgabe – nur sichtbar bei VERBOSE_DIAG=True."""
    if VERBOSE_DIAG:
        dbg(msg)


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


# Version: wird beim Laden vom Einstieg (previewer.py) geprüft.
PREVIEWER_VERSION = "0.12.0"
dbg("previewer_util %s geladen" % PREVIEWER_VERSION)