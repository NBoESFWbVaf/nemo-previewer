#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Helfer-Modul (previewer_util.py)
===========================================

STAND: Version 0.30.1 – F40: Neuer Helfer pick_icon (erstes im Icon-
Thema vorhandenes Symbol, Fallback sonst) für den Nemo-Titelleisten-
Umschalter und den Öffnen-Knopf. Die Basis-Helfer _pixbuf_from_bytes
und _zf_read_capped (0.15.0/F31) bleiben unverändert.

Gemeinsame Bausteine der Nemo-Extension "Previewer": Logging, kleine
Hilfsfunktionen und die zentralen Konfigurations-Konstanten. Teil der
achtteiligen Extension (Einstieg und Übersicht: previewer.py;
Installation: INSTALL.md im Repository).
"""

import os


import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf

# ------------------------------ Konfiguration ------------------------------
# F12 (0.13.0): Startbreite laut Nutzer-Wunsch per Default 300 px –
# konfigurierbar im Einstellungsfenster („Standardbreite beim Start")
# und in ~/.config/nemo-previewer/nemo-previewer.conf; eine per Ziehen
# gewählte Breite wird dort automatisch zur künftigen Startbreite.
PANEL_WIDTH = 300          # Standard-Startbreite des Panels in Pixeln
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
VERBOSE_DIAG = True


def diag(msg):
    """Diagnose-Ausgabe – nur sichtbar bei VERBOSE_DIAG=True."""
    if VERBOSE_DIAG:
        dbg(msg)


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
    except Exception:
        pass
    return fallback


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



# --- Gemeinsame Basis-Helfer (F31: früher in previewer_panel.py) ---

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
            except Exception:
                pass
        if w > max_w or h > max_h:
            f = min(max_w / max(w, 1), max_h / max(h, 1))
            try:
                loader.set_size(max(1, int(w * f)),
                                max(1, int(h * f)))
            except Exception:
                pass

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



# Version: wird beim Laden vom Einstieg (previewer.py) geprüft.
PREVIEWER_VERSION = "0.30.1"
dbg("previewer_util %s geladen" % PREVIEWER_VERSION)