#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_render_media.py – Version 0.42.1

Media renderers: images and SVG (EXIF-aware), audio with player
and seek bar, video info tiles.
"""

import os
import sys
import math
import re
import struct
import threading
import traceback

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    MAX_IMAGE_HEIGHT, format_seconds,
    _pixbuf_from_bytes,
    pack_hint,
    pack_meta_grid,
    cover_round_path,
)

# --- Optional modules (missing ones just reduce the previews) ---

# GStreamer for audio/video metadata (Discoverer) and playback.
HAVE_GST = False
try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import Gst, GstPbutils
    Gst.init(None)
    HAVE_GST = True
except Exception as e:
    dbg("media/module-level: suppressed: %s" % e)

# librsvg for the SVG preview: GdkPixbuf has had no built-in SVG
# loader since gdk-pixbuf 2.42.
HAVE_RSVG = False
try:
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    HAVE_RSVG = True
except Exception as e:
    dbg("media/module-level: suppressed: %s" % e)

# PangoCairo + pycairo to draw the placeholder cover tile (F18).
HAVE_PANGOCAIRO = False
try:
    import cairo  # pycairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo
    HAVE_PANGOCAIRO = True
except Exception as e:
    dbg("media/module-level: suppressed: %s" % e)

# K3: Cairo alone suffices for the SVG-DPI route (see _rsvg_cairo_pb):
# render_document replaces the deprecated get_pixbuf() and renders big.
HAVE_CAIRO = False
try:
    import cairo  # pycairo
    HAVE_CAIRO = True
except Exception as e:
    dbg("media/module-level: suppressed: %s" % e)


# Process state for media probing (convention: module dict, no
# global): was the GI warm-up already done?
_MEDIA_STATE = {"warmed": False}


def _media_gi_warmup():
    """
    R1-Härtung: PyGObject erzeugt die Method-Tabellen von GI-Klassen
    erst beim ERSTEN Attribut-Zugriff. Damit der Erkundungs-Worker
    (der die Medien-Tags liest) stabile Verhältnisse vorfindet, wird
    der Erstkontakt mit allen beteiligten Klassen einmalig im
    GTK-THREAD erledigt (siehe _media_probe_async). Der Name
    discover_uri_sync wird hier bewusst mit angefasst: Existiert er
    im Binding nicht, ist das kein Fehler – dann greift die Erkundung
    auf den korrekten Namen discover_uri zurück.
    """
    if _MEDIA_STATE["warmed"]:
        return
    _MEDIA_STATE["warmed"] = True

    def _touch(base, dotted):
        # Lazy path resolution: a missing symbol (e.g. Gst.PlayFlags
        # is absent from the Mint 22 binding) must never raise here.
        try:
            obj = base
            for part in dotted.split("."):
                obj = getattr(obj, part)
        except Exception as e:
            dbg("media/_touch: suppressed: %s" % e)

    for dotted in ("Discoverer.discover_uri",
                   "Discoverer.discover_uri_sync",
                   "DiscovererInfo.get_duration",
                   "DiscovererInfo.get_tags"):
        _touch(GstPbutils, dotted)
    for dotted in ("TagList.get_string",
                   "TagList.get_sample",
                   "Sample.get_buffer",
                   "Buffer.extract_dup",
                   "ElementFactory",
                   "State.PAUSED",
                   "State.PLAYING",
                   "State.NULL",
                   "SeekFlags.FLUSH",
                   "Format.TIME",
                   "Element.set_state",
                   "Element.get_state"):
        _touch(Gst, dotted)


# 0.9.2 (audit "buffer overflow/OOM"): caps against decompression
# and decoding bombs – crafted files must never blow up Nemo.
_IMAGE_FILE_CAP = 64 * 1024 * 1024   # image file: raw bytes before decoding
_MEDIA_IMAGE_CAP = 32 * 1024 * 1024  # embedded cover from media tags

# --- F36: photo metadata (EXIF) with stdlib only -----------------------------

_EXIF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def _exif_read_ifd(data, base, bo, off, out, depth=0):
    """
    Ein TIFF-IFD lesen: sammelt Tag→(Typ, Rohbytes) und lädt die
    Spezial-Zeiger ExifIFD (0x8769) und GPSIFD (0x8825) als Unter-
    IFDs nach. depth dämpft Zeiger-Verrücktheit (B7).
    """
    # → REF MED-EXIF-1
    try:
        n = struct.unpack_from(bo + "H", data, off)[0]
        if n > 512 or off + 2 + n * 12 > len(data):
            return                      # B7: bomb cap
        for i in range(n):
            e = off + 2 + i * 12
            tag, typ, cnt = struct.unpack_from(bo + "HHI", data, e)
            size = _EXIF_TYPE_SIZE.get(typ, 1) * cnt
            if size <= 4:
                val = data[e + 8:e + 8 + size]
            else:
                vo = base + struct.unpack_from(bo + "I", data, e + 8)[0]
                if vo + size > len(data):
                    continue
                val = data[vo:vo + size]
            out[tag] = (typ, val)
        for tag in (0x8769, 0x8825):
            if tag in out and depth < 2:
                try:
                    sub = base + struct.unpack(bo + "I", out[tag][1])[0]
                    _exif_read_ifd(data, base, bo, sub, out, depth + 1)
                except Exception as e:
                    dbg("media/_exif_read_ifd: suppressed: %s" % e)
    except Exception as e:
        dbg("media/_exif_read_ifd: suppressed: %s" % e)


def _exif_str(entry):
    """ASCII-Feld (Typ 2) als Text oder None."""
    if not entry or entry[0] != 2:
        return None
    try:
        return (entry[1].decode("utf-8", "replace")
                .rstrip("\x00").strip() or None)
    except Exception:
        return None


def _exif_num(entry, bo):
    """Erster Zahlenwert (SHORT/LONG) eines Tags oder None."""
    if not entry:
        return None
    typ, val = entry
    try:
        if typ == 3 and len(val) >= 2:
            return struct.unpack_from(bo + "H", val)[0]
        if typ == 4 and len(val) >= 4:
            return struct.unpack_from(bo + "I", val)[0]
    except Exception as e:
        dbg("media/_exif_num: suppressed: %s" % e)
    return None


def _exif_frac(entry, bo):
    """RATIONAL/SRATIONAL (num/den) als float oder None."""
    if not entry:
        return None
    typ, val = entry
    try:
        if typ in (5, 10) and len(val) >= 8:
            fmt = bo + ("ii" if typ == 10 else "II")
            n, d = struct.unpack_from(fmt, val)
            return float(n) / d if d else None
    except Exception as e:
        dbg("media/_exif_frac: suppressed: %s" % e)
    return None


def _exif_dms(tags, tag, bo):
    """GPS-Grad/Minuten/Sekunden (3 RATIONALS) in Dezimalgrade."""
    entry = tags.get(tag)
    if not entry or entry[0] != 5 or len(entry[1]) < 24:
        return None
    try:
        n = struct.unpack_from(bo + "IIIIII", entry[1])
        g = n[0] / n[1] if n[1] else 0.0
        m = n[2] / n[3] if n[3] else 0.0
        s = n[4] / n[5] if n[5] else 0.0
        return g + m / 60.0 + s / 3600.0
    except Exception:
        return None


# F38: standard XMP namespaces – anything BEYOND counts as
# "user-defined" and lands in its own table row here.
_XMP_STD = {"exif", "tiff", "x", "xmp", "xmpMM", "xmpBJ", "xmpRights",
            "xmpDM", "xap", "xapMM", "xapBJ", "xapRights", "dc",
            "photoshop", "Iptc4xmpCore", "Iptc", "aux", "crs", "crss",
            "lr", "rdf", "xml", "xmlns", "xsi", "stEvt", "stRef",
            "stDim", "MicrosoftPhoto", "pdf", "xmpTPg", "xmpGImg"}


def _xmp_clean(val):
    """F38: XML-Reste aus XMP-Werten kehren; Entities dekodieren."""
    val = re.sub(r"<[^>]+>", " ", val)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&apos;", "'")):
        val = val.replace(a, b)
    return " ".join(val.split())[:120]


def _xmp_parse(data):
    """
    F38 (Nutzer-Wunsch): XMP-Felder aus dem JPEG-APP1-Segment mit
    Python-Bordmitteln (Regex über das eingebettete RDF-XML, keine
    neue Pflicht-Abhängigkeit – passend zum EXIF-Parser). Zurück
    kommt ein Dict: „Location“ (IPTC Core, Element- ODER Attribut-
    Form) plus benutzerdefinierte Felder aus nicht-standardisierten
    Namensräumen als „Präfix:Name“ – nur vorhandene, nicht-leere
    Werte.
    """
    # → REF MED-XMP-1
    out = {}
    try:
        pos = data.find(b"http://ns.adobe.com/xap/1.0/", 0, 262144)
        if pos < 0:
            return out
        start = data.find(b"<x:xmpmeta", pos)
        end = data.find(b"</x:xmpmeta>", pos)
        if start < 0 or end < 0 or end <= start:
            return out
        xmp = data[start:end + 12].decode("utf-8", "replace")
        # F38: "Location" – textual place from IPTC Core (digikam,
        # Lightroom); Adobe tools may write simple values as attributes.
        m = (re.search(r'<[^>]*Iptc4xmpCore:Location="([^"]+)"', xmp)
             or re.search(
                 r"<Iptc4xmpCore:Location>(.*?)</Iptc4xmpCore:Location>",
                 xmp, re.S))
        if m:
            loc = _xmp_clean(m.group(1))
            if loc:
                out["Location"] = loc
        # F38: user-defined fields – element form: opening tags and
        # matching end tags, never one nested match (→ REF MED-XMP-1).
        custom = {}
        for m in re.finditer(r"<(\w+):(\w+)[^>]*>", xmp):
            pfx, name = m.group(1), m.group(2)
            if pfx in _XMP_STD or name in _XMP_STD:
                continue
            close = xmp.find("</%s:%s>" % (pfx, name), m.end())
            if close < 0:
                continue
            val = _xmp_clean(xmp[m.end():close])
            if val:
                custom.setdefault("%s:%s" % (pfx, name), val)
        # F38: user-defined fields – attribute form (simple values
        # without their own element, preferred by Adobe tools).
        for m in re.finditer(r'(\w+):(\w+)="([^"]+)"', xmp):
            pfx, name, val = m.group(1), m.group(2), m.group(3)
            val = _xmp_clean(val)
            if pfx not in _XMP_STD and name not in _XMP_STD and val:
                custom.setdefault("%s:%s" % (pfx, name), val)
        for key in list(custom)[:10]:
            out[key] = custom[key]
    except Exception as e:
        dbg("media/_xmp_parse: suppressed: %s" % e)
    return out


def _exif_valid(data, base, bo, magic):
    """F42: Struktur-Check eines TIFF-Kandidaten (42-Magie optional –
    Olympus ORF trägt „RO“ statt 42): IFD0-Offset ≥ 8, Eintragszahl
    1–4096, erster IFD komplett im Puffer."""
    try:
        if magic and struct.unpack_from(bo + "H", data,
                                        base + 2)[0] != 42:
            return False
        off = struct.unpack_from(bo + "I", data, base + 4)[0]
        if off < 8:
            return False
        cnt = struct.unpack_from(bo + "H", data, base + off)[0]
        return 0 < cnt <= 4096 and base + off + 2 + cnt * 12 <= len(data)
    except Exception:
        return False


def _exif_bases(data):
    """
    F42 (Nutzer-Meldung): Liefert EXIF-Kandidaten im GANZEN Puffer –
    Paare (Basis-Offset, 42-Magie prüfen). Drei Quellen:
    1. „Exif“-Marker wie im JPEG-APP1 – HEIC/HEIF-Exif-Items tragen
       teils denselben Vorspann, oft mitten oder am Ende der Datei;
       dahinter folgt nach F36-Padding der TIFF-Kopf. RAWs mit ein-
       gebettetem JPEG (RAF, RW2) kommen über denselben Weg.
    2. Direkte TIFF-Köpfe (II*/MM*) – HEIC-Items ohne Vorspann, Plain-
       TIFF und TIFF-basierte RAWs (NEF, CR2, ARW, DNG, PEF) tragen
       ihn ab Byte 0 oder in einem Sub-Block.
    3. Olympus-ORF-Köpfe (IIRO/IIRS) – TIFF-artig, ohne 42-Magie.
    Jeder Kandidat wird validiert (_exif_valid), Duplikate fallen
    weg. Ein falscher „Exif“-Treffer – der Item-Typ in der HEIC-
    Meta-Box ist einer – fällt durch die Validierung oder liefert
    kein EXIF; der nächste Kandidat gewinnt. Genau daran scheiterte
    F41: Der früheste „Exif“-Treffer bestimmte allein, ob und wo
    gesucht wurde. Reihenfolge: Marker vor Direkt-Köpfen, je nach
    Position.
    """
    # → REF MED-EXIF-3
    out, seen = [], set()
    nul = bytes([0])
    marker = b"Exif" + nul + nul

    def add(base, bo, magic):
        if base in seen or not _exif_valid(data, base, bo, magic):
            return
        seen.add(base)
        out.append((base, magic))

    # 1. "Exif" marker anywhere in the buffer (F41 scanned only 256 KB).
    pos = data.find(marker)
    while pos >= 0:
        base = pos + 6
        # F36: skip padding between marker and TIFF head (0x00/0x20,
        # partly Samsung/Olympus) – the head follows later.
        stop = base + 16
        while base < stop and data[base:base + 1] in (nul, b" "):
            base += 1
        head = data[base:base + 2]
        add(base, "<" if head == b"II" else ">", True)
        pos = data.find(marker, pos + 1)
    # 2. Direct TIFF heads (II*/MM*) anywhere in the buffer.
    for pat, bo in ((b"II*" + nul, "<"), (b"MM" + nul + b"*", ">")):
        pos = data.find(pat)
        while pos >= 0:
            add(pos, bo, True)
            pos = data.find(pat, pos + 1)
    # 3. Olympus ORF: IIRO/IIRS instead of II*/MM* – the IFD0
    # pointer still sits at offset 4, only the 42 magic is missing.
    for pat in (b"IIRO", b"IIRS"):
        pos = data.find(pat)
        while pos >= 0:
            add(pos, "<", False)
            pos = data.find(pat, pos + 1)
    return out


def _exif_parse(data):
    """
    F36: EXIF-Kerninformationen aus JPEG-/TIFF-Bytes – mit
    Python-Bordmitteln, ohne neue Pflicht-Abhängigkeit. Hersteller-
    Eigenheiten fangen Standard-Fallbacks ab (APEX statt Direktwert,
    Datums-Kaskade, GPS-Dezimalgrad). Zurück kommt ein Dict mit
    fertigen Anzeige-Texten – nur vorhandene Werte.
    F42 (Nutzer-Meldung): Kandidaten-Schleife – _exif_bases sammelt
    validierte TIFF-Kandidaten im ganzen Puffer, der erste mit EXIF
    gewinnt (HEIC/HEIF und RAW, → REF MED-EXIF-3).
    """
    # → REF MED-EXIF-2 (F42: Kandidaten-Schleife)
    bases = _exif_bases(data)
    dbg("EXIF: %d candidate(s)" % len(bases))
    for base, magic in bases:
        out = _exif_parse_at(data, base, magic)
        if out:
            return out
    return {}


def _exif_bo(data, base, magic):
    """
    S8 (0.42.0): Byte-Order des TIFF-Kopfes – None, wenn Kopf oder
    Magie nicht passen (MM/II; 42 magisch, Olympus ORF trägt „RO“).
    """
    head = data[base:base + 2]
    if head == b"MM":
        bo = ">"
    elif head == b"II":
        bo = "<"
    else:
        return None
    if magic and struct.unpack_from(bo + "H", data,
                                    base + 2)[0] != 42:
        return None
    return bo


def _exif_camera(tags, out):
    """
    F36: Kameramodell – viele Modelle wiederholen den Hersteller
    im Modellnamen („Canon“ + „Canon EOS …“): nur dann kürzen.
    """
    make = _exif_str(tags.get(0x010F))
    model = _exif_str(tags.get(0x0110))
    if model:
        if make and model.lower().startswith(make.lower()):
            out["Kameramodell"] = model
        elif make:
            out["Kameramodell"] = "%s %s" % (make, model)
        else:
            out["Kameramodell"] = model


def _exif_date(tags, out):
    # F36: date taken – original before digitized before file
    # date; makers may write the real date in only one spot.
    for tag in (0x9003, 0x9004, 0x0132):
        dt = _exif_str(tags.get(tag))
        if dt and len(dt) >= 16 and dt[4] == ":" and dt[7] == ":":
            out["Aufnahmedatum"] = "%s.%s.%s %s" % (
                dt[8:10], dt[5:7], dt[0:4], dt[11:16])
            return


def _exif_exposure(tags, bo, out):
    # F36: exposure time – direct value, else APEX time value
    # (t = 2^-av; some compacts only write that one).
    t = _exif_frac(tags.get(0x829A), bo)
    if t is None:
        av = _exif_frac(tags.get(0x9201), bo)
        if av is not None:
            t = 2.0 ** -av
    if not t:
        return
    if t < 1.0:
        out["Belichtungszeit"] = "1/%d s" % max(2, round(1.0 / t))
    elif t == int(t):
        out["Belichtungszeit"] = "%d s" % int(t)
    else:
        out["Belichtungszeit"] = "%.1f s" % t


def _exif_aperture(tags, bo, out):
    # F36: aperture – FNumber, else APEX opening (N = 2^(av/2)).
    fn = _exif_frac(tags.get(0x829D), bo)
    if fn is None:
        av = _exif_frac(tags.get(0x9202), bo)
        if av is not None:
            fn = 2.0 ** (av / 2.0)
    if fn:
        out["Blende"] = "f/%.1f" % fn


def _exif_focal(tags, bo, out):
    # F36: "zoom" as focal length, plus 35 mm equivalent when it
    # differs (full-frame cameras carry no own tag).
    fl = _exif_frac(tags.get(0x920A), bo)
    fl35 = _exif_num(tags.get(0xA405), bo)
    if fl:
        txt = "%g mm" % fl
        if fl35 and abs(fl35 - fl) > 0.5:
            txt += " (%d mm äquiv.)" % fl35
        out["Brennweite"] = txt
    elif fl35:
        out["Brennweite"] = "%d mm" % fl35


def _exif_iso_size(tags, bo, out):
    # F36: ISO – classic ISOSpeedRatings, else ISOSpeed.
    iso = _exif_num(tags.get(0x8827), bo)
    if iso is None:
        iso = _exif_num(tags.get(0x8833), bo)
    if iso:
        out["ISO"] = str(iso)
    # F42 (RAW): pixel dimensions – the only size source without
    # decoding (A002/A003 from the ExifIFD).
    pw = _exif_num(tags.get(0xA002), bo)
    ph = _exif_num(tags.get(0xA003), bo)
    if pw and ph:
        out["Maße"] = "%d × %d px" % (pw, ph)


def _exif_place(tags, bo, out):
    # F36: location – GPS deg/min/sec to decimal degrees; the
    # reference letters (N/S, E/W) come from the GPS tags.
    lat = _exif_dms(tags, 0x0002, bo)
    lon = _exif_dms(tags, 0x0004, bo)
    if lat is not None and lon is not None:
        lr = (_exif_str(tags.get(0x0001)) or "N")[:1]
        lor = (_exif_str(tags.get(0x0003)) or "E")[:1]
        out["Aufnahmeort"] = "%.4f° %s, %.4f° %s" % (
            abs(lat), lr, abs(lon), lor)


def _exif_parse_at(data, base, magic=True):
    """
    F42: EXIF an EINEM TIFF-Basis-Offset – formatierender Teil der
    F36-Logik, von der Kandidaten-Schleife je Kandidat aufgerufen.
    S8 (0.42.0): Zerlegt – _exif_bo prüft den Kopf, je Themenblock
    (Kamera, Datum, Belichtung, Blende, Brennweite, ISO/Maße, Ort)
    füllt ein kleiner Helfer das Dict; alles bleibt im try gegen
    kaputte Dateien.
    """
    out = {}
    try:
        bo = _exif_bo(data, base, magic)
        if bo is None:
            return out
        ifd0 = base + struct.unpack_from(bo + "I", data, base + 4)[0]
        tags = {}
        _exif_read_ifd(data, base, bo, ifd0, tags)
        _exif_camera(tags, out)
        _exif_date(tags, out)
        _exif_exposure(tags, bo, out)
        _exif_aperture(tags, bo, out)
        _exif_focal(tags, bo, out)
        _exif_iso_size(tags, bo, out)
        _exif_place(tags, bo, out)
    except Exception as exc:
        dbg("EXIF parse failed: %s" % exc)
    return out


def _exif_rows(exif, xmp):
    """
    F42: Foto-Zeilen aus EXIF/XMP – gemeinsam für die Bild-Ansicht
    (unter Höhe/Breite) und den RAW-Fallback (unter dem Icon). Nur
    vorhandene Werte, Reihenfolge wie in der Bild-Tabelle.
    """
    rows = []
    for key in ("Aufnahmedatum", "Aufnahmeort"):
        if exif and key in exif:
            rows.append((key, exif[key]))
    if xmp and xmp.get("Location"):
        rows.append(("Location", xmp["Location"]))
    for key in ("Kameramodell", "Belichtungszeit", "Brennweite",
                "Blende", "ISO"):
        if exif and key in exif:
            rows.append((key, exif[key]))
    if xmp:
        for key in [k for k in xmp if k != "Location"][:10]:
            rows.append((key, xmp[key]))
    return rows

# ========================== Renderer: media =================================


class MediaRendererMixin:
    """Mixin: Renderer für Bild (inkl. EXIF), SVG, Audio und Video."""

    def _pack_image_capped(self, scroll):
        """
        F38 (Nutzer-Wunsch): Die Spalte ist für Bild-Vorschauen in
        einen 60-%-Bereich für das Bild (vertikal und horizontal
        mittig) und einen 40-%-Bereich für die Bildinformationen
        geteilt; zwischen beiden ein Trenner. Die Höhe des Bild-
        bereichs wird live auf 60 % der Spaltenhöhe gehalten.
        """
        # → REF MED-SPLIT-1
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # F38 strip fix: never align=CENTER the ScrolledWindow (it
        # shrinks to ~0); halign/valign CENTER on the image instead.
        try:
            vp = scroll.get_child()
            img = vp.get_child() if vp is not None else None
            if img is not None:
                img.set_halign(Gtk.Align.CENTER)
                img.set_valign(Gtk.Align.CENTER)
        except Exception as e:
            dbg("media/_pack_image_capped: suppressed: %s" % e)
        top.pack_start(scroll, True, True, 0)
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # F38: info area – _meta_grid packs the image table here.
        self._image_info_box = bottom
        top.set_size_request(-1,
                             max(80, int(self._preview_height() * 0.6)))
        top.connect("size-allocate", self._image_split_sync)
        # F38: expand=False keeps the height at the 60% request –
        # expand/fill in a vertical GtkBox only affect the HEIGHT.
        self._content.pack_start(top, False, True, 0)
        sep = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        self._content.pack_start(sep, False, True, 0)
        self._content.pack_start(bottom, True, True, 0)

    def _image_split_sync(self, widget, allocation):
        """F38: Bildbereich auf 60 % der Spaltenhöhe nachziehen."""
        # → REF MED-SPLIT-1
        try:
            ch = self._content.get_allocated_height()
            if ch > 100:
                want = max(80, int(ch * 0.6))
                cur = widget.get_size_request()[1] or 0
                if abs(cur - want) > 2:
                    widget.set_size_request(-1, want)
        except Exception as e:
            dbg("media/_image_split_sync: suppressed: %s" % e)

    def _rsvg_cairo_pb(self, handle):
        """
        K3 (2026-10-30): SVG über die Cairo-Route (render_document)
        DPI-artig auf die Panelbreite gerendert – intrinsisch kleine
        SVGs blieben bisher winzig, und get_pixbuf() ist in neuerem
        librsvg deprecated. Zurück kommt (Pixbuf, (Breite, Höhe)) in
        INTRINSISCHEN Pixeln oder None – der Aufrufer fällt dann auf
        den bisherigen get_pixbuf()-Pfad zurück.
        """
        # → REF MED-SVG-DPI-1
        if not HAVE_CAIRO:
            return None
        try:
            dim = handle.get_intrinsic_size_in_pixels()
            if not dim:
                return None
            w, h = float(dim[0]), float(dim[1])
            if w <= 0 or h <= 0:
                return None
            # K3: the target is the panel width (small SVGs grow
            # sharp, vector instead of raster upscaling); height capped.
            f = float(self._preview_width()) / w
            if h * f > MAX_IMAGE_HEIGHT:
                f = float(MAX_IMAGE_HEIGHT) / h
            if f <= 0:
                return None
            tw = max(1, int(w * f))
            th = max(1, int(h * f))
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, tw, th)
            ctx = cairo.Context(surface)
            handle.render_document(ctx, Rsvg.Rectangle(
                x=0.0, y=0.0, width=float(tw), height=float(th)))
            pb = Gdk.pixbuf_get_from_surface(surface, 0, 0, tw, th)
            if pb is None:
                return None
            return pb, (int(w), int(h))
        except Exception:
            return None

    def _render_svg(self, path):
        """
        SVG-Vorschau via librsvg: GdkPixbuf kann SVG nicht laden.
        K3 (2026-10-30): Bevorzugt die Cairo-Route (_rsvg_cairo_pb –
        DPI-artig auf Panelbreite, render_document statt des dep-
        recated get_pixbuf()); scheitert sie (kein pycairo, altes
        librsvg, keine intrinsische Größe), greift der alte Pfad.
        Das Maße-Label zeigt die INTRINSISCHE Größe.
        """
        if not HAVE_RSVG:
            pack_hint(self._content, "SVG-Vorschau nicht verfügbar – "
                       "Paket gir1.2-rsvg installieren.")
            self._render_generic()
            return
        handle = None
        pb = None
        dims = None
        err = None
        try:
            handle = Rsvg.Handle.new_from_file(path)
        except Exception as e:
            err = e
        if handle is not None:
            got = self._rsvg_cairo_pb(handle)
            if got is not None:
                pb, dims = got
            else:
                # K3 fallback: the old path, deprecated in newer
                # librsvg – works until then.
                try:
                    pb = handle.get_pixbuf()
                except Exception as e:
                    err = err or e
        if pb is None:
            pack_hint(self._content, "Konnte SVG nicht lesen: %s" % err)
            self._render_generic()
            return
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False,
                                    keep_height=True, frac_h=0.6)
        self._pack_image_capped(scroll)
        try:
            if dims is None:
                dims = (pb.get_width(), pb.get_height())
            info = Gtk.Label(label="%d × %d px" % dims)
            info.get_style_context().add_class("dim-label")
            info.set_halign(Gtk.Align.START)
            # F38: dimensions into the info area of the column split.
            box = getattr(self, "_image_info_box", None) or self._content
            box.pack_start(info, False, False, 0)
        except Exception as e:
            dbg("media/_render_svg: suppressed: %s" % e)

    def _render_image(self, path):
        """
        R9 (0.10.2) mit Feld-Korrektur (0.10.3): Große Bilder
        (typisch 20-MB-JPEGs mit 50–100 Megapixeln) blockierten den
        GTK-Main-Loop – Lesen, Dekodieren und EXIF-Drehung liefen
        synchron in einem Rutsch bei der Auswahl, die UI stand
        still. Zweistufig wie bei den Medien (R1): (1) sofort
        Hinweis zeigen, die UI bleibt bedienbar; (2) der Daemon-
        Thread liest NUR die Datei (reines Python-I/O) und reicht
        die Bytes per GLib.idle_add zurück. Dekodierung, EXIF-
        Drehung und Skalierung laufen zurück im GTK-Thread – der
        Feldtest von 0.10.2 zeigte: Gdk-Objekte (PixbufLoader) im
        Worker scheitern still, das R1-Muster „keine Gdk-Objekte
        im Worker" gilt auch hier.
        Geschwindigkeitshebel bleibt der Decode-Deckel
        max(2 × Panelbreite, 1024): Die Dekodierung wird um ein
        Vielfaches billiger, die Live-Skalierung verliert nichts
        (die Quelle bleibt breiter als jede Panelbreite, wie bei
        PDF-R2 mit 2-facher Breite). Der Bomben-Schutz aus 0.9.2
        bleibt vollständig erhalten. Schlägt der Thread-Start
        ausnahmsweise fehl, läuft der alte synchrone Weg als
        Rettungsanker.
        """
        pack_hint(self._content, "Lade Bild – einen Moment …")
        try:
            target_w = max(1024, self._preview_width() * 2)
        except Exception:
            target_w = 1024

        def work():
            data, err, exif, xmp = None, None, None, None
            try:
                with open(path, "rb") as fh:
                    data = fh.read(_IMAGE_FILE_CAP)
                dbg("Image read: %s (%d bytes)" % (path, len(data)))
            except Exception as exc:
                data, err = None, exc
                dbg("Image read failed (%s): %s" % (path, exc))
            # F36: evaluate EXIF right in the worker – pure byte
            # work, fitting the R1/B7 thread discipline. F38: XMP too.
            if data:
                exif = _exif_parse(data)
                xmp = _xmp_parse(data)
            try:
                GLib.idle_add(self._image_probe_done,
                              path, target_w, data, err, exif, xmp)
            except Exception as exc:
                dbg("Image return failed (%s): %s"
                    % (path, exc))

        try:
            threading.Thread(target=work, daemon=True).start()
        except Exception:
            # Lifeline: thread not startable → read synchronously,
            # _image_probe_done decodes directly.
            data, err, exif, xmp = None, None, None, None
            try:
                with open(path, "rb") as fh:
                    data = fh.read(_IMAGE_FILE_CAP)
                if data:
                    exif = _exif_parse(data)
                    xmp = _xmp_parse(data)
            except Exception as exc:
                data, err = None, exc
            self._image_probe_done(path, target_w, data, err, exif, xmp)

    def _image_probe_done(self, path, target_w, data, err, exif=None,
                          xmp=None):
        """
        R9-Rückkehr (0.10.3/0.10.4): Dekodierung der im Worker
        gelesenen Bytes HIER im GTK-Thread (gleiche Disziplin wie bei
        den Medien-Covern in _media_probe_done – Gdk-Objekte entstehen
        nur im GTK-Thread). Decode-Deckel target_w; bei weiterge-
        wanderter Auswahl wird das Ergebnis still verworfen.
        Schlägt die Dekodierung fehl, greift der synchrone
        at_scale-Fallback (begrenzt die Dekodierung intern und ist
        damit ebenfalls bombensicher); erst wenn auch der scheitert,
        erscheint der generische Fehlerhinweis.
        0.10.4: Alle hier gepackten Widgets liegen NACH dem
        show_all() des Render-Durchlaufs – genau wie in
        _media_probe_done braucht der Callback daher sein EIGENES
        show_all, sonst bleibt die Vorschau unsichtbar (Feld-Ursache
        der B7-Regression, in 0.10.2/0.10.3 übersehen).
        """
        if self._path != path:
            dbg("Image result dropped, selection changed: %s" % path)
            return False      # selection changed meanwhile
        self._clear_content()
        pb, orig = None, {}
        if data is not None:
            try:
                # The decode cap (0.9.2) stays: set_size shrinks at
                # DECODE time – bomb images only cost the capped area.
                pb = _pixbuf_from_bytes(
                    data, max_w=target_w, max_h=2 * MAX_IMAGE_HEIGHT,
                    orig=orig)
            except Exception as exc:
                dbg("Image decode failed (%s): %s"
                    % (path, exc))
        if pb is None:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, 4096, 4096, True)
            except Exception:
                pb = None
        if pb is None:
            # F42: Gdk-Pixbuf mostly cannot decode RAW (NEF, CR2 …);
            # EXIF/XMP are in the buffer – show a photo table (→ REF MED-EXIF-3).
            rows = []
            if exif and "Maße" in exif:
                rows.append(("Maße", exif["Maße"]))
            rows += _exif_rows(exif, xmp)
            if rows:
                dbg("RAW/undecodable: photo table (%d rows)"
                    % len(rows))
                self._render_generic()
                pack_meta_grid(rows, self._content)
                self._content.show_all()
                return False
            pack_hint(self._content, "Konnte Bild nicht laden: %s" % (err or "unbekannt"))
            self._render_generic()
            # This fallback also packs AFTER the render pass's
            # show_all() – invisible without its own show_all.
            self._content.show_all()
            return False
        # Apply the EXIF orientation: photos that only carry the
        # rotation in the Orientation tag would otherwise lie sideways.
        try:
            pb = pb.apply_embedded_orientation()
        except Exception as e:
            dbg("media/_image_probe_done: suppressed: %s" % e)
        dbg("Image decoded: %s (%d × %d px)" %
            (path, pb.get_width(), pb.get_height()))
        if pb.get_width() > 4096 or pb.get_height() > MAX_IMAGE_HEIGHT:
            pb = self._scale_pixbuf(pb, 4096, MAX_IMAGE_HEIGHT)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False,
                                    keep_height=True, frac_h=0.6)
        self._pack_image_capped(scroll)
        try:
            # Dimensions: the ORIGINAL sizes from the file header
            # (size-prepared, before capping), not the decode size.
            w = orig.get("w", pb.get_width())
            h = orig.get("h", pb.get_height())
            if (w > h) != (pb.get_width() > pb.get_height()):
                w, h = h, w
            # F36: the dimensions row moved into the photo info
            # table; further rows only if EXIF provides them.
            rows = [("Höhe", "%d px" % h), ("Breite", "%d px" % w)]
            # F42: EXIF/XMP rows together with the RAW fallback.
            rows += _exif_rows(exif, xmp)
            # F38: table into the 40% info area of the split.
            pack_meta_grid(rows, self._image_info_box)
        except Exception as e:
            dbg("media/_image_probe_done: suppressed: %s" % e)
        # → REF MED-B7-1
        self._content.show_all()
        return False

    def _render_audio(self, path, uri):
        """
        Audio-Vorschau: Cover, Tags und Player-Leiste.
        R1: Tags, Dauer und Cover werden im Hintergrund-Thread erkannt
        (siehe _media_probe_async) – das Panel erscheint sofort mit
        einem Lese-Hinweis und bleibt bedienbar, statt auf der Stelle
        einzufrieren, wenn das Medium langsam erreichbar ist.
        """
        self._media_probe_async(path, uri, self._finish_audio)

    def _media_probe_async(self, path, uri, finish, video=False):
        """
        R1: Medien-Erkundung ohne UI-Blockade. Der GStreamer-Discoverer
        läuft in einem Daemon-Thread (Tags, Dauer, Bildbytes – KEIN
        Pixbuf, Gdk-Objekte entstehen erst zurück im GTK-Thread) und
        schwenkt das Ergebnis per GLib.idle_add in den Main-Loop;
        finish ist die Fortsetzung (_finish_audio/_finish_video).

        R1-Fix (0.5.0-Testergebnis): Die synchrone Erkundung heißt im
        Python-Binding discover_uri() – der C-Name gst_discoverer_
        discover_uri wird OHNE „_sync“ gebunden; ein discover_uri_sync
        existiert nicht (AttributeError). Damit hatte die Tags/Dauer/
        Cover-Erkundung noch NIE funktioniert – das Platzhalter-Cover
        (F18) machte den Altfehler erstmals sichtbar. Zusätzlich werden
        die GI-Klassen einmalig HIER im GTK-Thread warmgefahren
        (PyGObject löst Method-Tabellen lazy auf) und die Erkundung
        läuft im Worker als fertig aufgelöstes Callable.
        """
        pack_hint(self._content, "Lese Medien-Informationen – einen Moment …")
        _media_gi_warmup()
        try:
            try:
                disc = GstPbutils.Discoverer.new(10 * Gst.SECOND)
            except (AttributeError, TypeError):
                # Newer PyGObject builds do not map gst_discoverer_new
                # as a constructor – use explicit .new() with fallback.
                disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            # Attribute resolution IN the GTK thread; the worker only
            # calls the finished callable (discover_uri, sync fallback).
            probe = getattr(disc, "discover_uri", None)
            if probe is None:
                probe = disc.discover_uri_sync
        except Exception as e:
            dbg("Discoverer not creatable: %s" % e)
            # Without the Discoverer still build the UI (placeholder,
            # player) – do not get stuck on the hint.
            GLib.idle_add(self._media_probe_done, path, uri, finish,
                          {}, -1, None)
            return

        def work():
            tags, duration, image_bytes = {}, -1, None
            try:
                info = probe(uri)
                duration = info.get_duration() // Gst.SECOND
                taglist = info.get_tags()
                if taglist:
                    for key, gst_tag in (("title", Gst.TAG_TITLE),
                                         ("artist", Gst.TAG_ARTIST),
                                         ("album", Gst.TAG_ALBUM),
                                         # F35: genre – plain string tag.
                                         ("genre", Gst.TAG_GENRE)):
                        ok, val = taglist.get_string(gst_tag)
                        if ok and val:
                            tags[key] = val
                    # F33: extended music tags in their own brackets –
                    # an error here must never cost the cover too.
                    try:
                        for key, gst_tag in (
                                ("album_artist",
                                 getattr(Gst, "TAG_ALBUM_ARTIST",
                                         "album-artist")),
                                ("codec",
                                 getattr(Gst, "TAG_AUDIO_CODEC",
                                         "audio-codec"))):
                            ok, val = taglist.get_string(gst_tag)
                            if ok and val:
                                tags[key] = val
                        # Codec fallback: the container (e.g. "Ogg")
                        # if the audio codec itself is missing.
                        if "codec" not in tags:
                            ok, val = taglist.get_string(
                                getattr(Gst, "TAG_CONTAINER_FORMAT",
                                        "container-format"))
                            if ok and val:
                                tags["codec"] = val
                        tags["track"], tags["track_total"] = (
                            self._tag_number_pair(
                                taglist, Gst.TAG_TRACK_NUMBER,
                                Gst.TAG_TRACK_COUNT))
                        tags["disc"], tags["disc_total"] = (
                            self._tag_number_pair(
                                taglist, Gst.TAG_ALBUM_VOLUME_NUMBER,
                                Gst.TAG_ALBUM_VOLUME_COUNT))
                        tags["year"] = self._tag_year(taglist)
                    except Exception as e:
                        dbg("Tag extraction (F33) failed: %s" % e)
                    # Collect image bytes (decoding happens in the
                    # GTK thread). Videos: still image; audio: cover.
                    order = ((Gst.TAG_PREVIEW_IMAGE, Gst.TAG_IMAGE) if video
                             else (Gst.TAG_IMAGE, Gst.TAG_PREVIEW_IMAGE))
                    for gst_tag in order:
                        ok, sample = taglist.get_sample(gst_tag)
                        if ok and sample:
                            buf = sample.get_buffer()
                            # 0.9.2: byte cap – embedded covers can
                            # be arbitrarily large otherwise.
                            image_bytes = buf.extract_dup(
                                0, min(buf.get_size(), _MEDIA_IMAGE_CAP))
                            break
            except Exception as e:
                dbg("Discoverer error: %s" % e)
            GLib.idle_add(self._media_probe_done, path, uri, finish,
                          tags, duration, image_bytes)

        threading.Thread(target=work, daemon=True).start()

    def _media_probe_done(self, path, uri, finish, tags, duration,
                          image_bytes):
        """R1: Rückkehr der Hintergrund-Erkundung in den GTK-Main-Loop."""
        # Selection changed meanwhile – drop the result.
        if self._path != path:
            return False
        pixbuf = None
        if image_bytes:
            try:
                # 0.9.2: guarded loader with a decode cap (see
                # _pixbuf_from_bytes) instead of a raw PixbufLoader.
                pixbuf = _pixbuf_from_bytes(image_bytes)
            except Exception as exc:
                dbg("Media image not displayable: %s" % exc)
        # Remove the reading hint and build the actual preview.
        self._clear_content()
        try:
            finish(path, uri, tags, duration, pixbuf)
        except Exception:
            # Same guard as in _render: never raise, always fall back.
            dbg("Media preview build error (%r):" % path)
            traceback.print_exc()
            try:
                self._clear_content()
                self._render_generic()
            except Exception as e:
                dbg("media/_media_probe_done: suppressed: %s" % e)
        # Widgets packed only here sit AFTER the render pass's
        # show_all() – they need their own show_all.
        self._content.show_all()
        return False

    def _media_cover_placeholder(self, glyph="♫",
                                 fallback_icon="audio-x-generic",
                                 grad=((0.145, 0.173, 0.216),
                                       (0.251, 0.204, 0.322)),
                                 perforations=False):
        """
        Generische Kachel für Medien ohne eingebettetes Bild: dunkle
        Kachel mit diagonalem Farbverlauf, halbtransparentem Symbol und
        abgerundeten Ecken – in doppelter Auflösung gezeichnet (640 px
        für 320 px Anzeige), damit die Kachel auch auf HiDPI-Schirmen
        scharf bleibt. Musik ohne Cover (F18) zeigt das Notensymbol,
        Video ohne eingebettetes Vorschaubild (F22) das Abspiel-
        Dreieck mit Filmperforation am oberen und unteren Rand.
        Ohne PangoCairo (oder bei Zeichenfehlern) greift ein Icon-
        Fallback auf dunklem Grund.
        """
        size = 640
        try:
            if not HAVE_PANGOCAIRO:
                raise ValueError("PangoCairo nicht verfügbar")
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
            cr = cairo.Context(surf)
            # Rounded corners as a clip path; the area outside
            # stays transparent (0.25.1: a third subtler than F34).
            r = 56.0 * 2.0 / 3.0
            cr.new_sub_path()
            cr.arc(size - r, r, r, -0.5 * math.pi, 0.0)
            cr.arc(size - r, size - r, r, 0.0, 0.5 * math.pi)
            cr.arc(r, size - r, r, 0.5 * math.pi, math.pi)
            cr.arc(r, r, r, math.pi, 1.5 * math.pi)
            cr.close_path()
            cr.clip()
            # Diagonal gradient (color pair per media type)
            pat = cairo.LinearGradient(0.0, 0.0, size, size)
            pat.add_color_stop_rgba(0.0, grad[0][0], grad[0][1], grad[0][2],
                                   1.0)
            pat.add_color_stop_rgba(1.0, grad[1][0], grad[1][1], grad[1][2],
                                   1.0)
            cr.set_source(pat)
            cr.paint()
            # Film perforation (video tile only): semi-transparent
            # hole rows at the top and bottom edges.
            if perforations:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
                for i in range(8):
                    x = 23.0 + i * 80.0
                    cr.rectangle(x, 20.0, 34.0, 26.0)
                    cr.rectangle(x, size - 46.0, 34.0, 26.0)
                cr.fill()
            # Symbol in semi-transparent white, centered (Pango
            # finds a font with the glyph itself – serif first).
            layout = PangoCairo.create_layout(cr)
            layout.set_text(glyph, -1)
            font = Pango.FontDescription()
            font.set_family("Serif")
            font.set_absolute_size(320 * Pango.SCALE)
            layout.set_font_description(font)
            lw, lh = layout.get_pixel_size()
            cr.move_to((size - lw) / 2.0, (size - lh) / 2.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.82)
            PangoCairo.update_layout(cr, layout)
            PangoCairo.show_layout(cr, layout)
            return Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)
        except Exception as exc:
            dbg("Placeholder cover not drawable (%s) – icon fallback"
                % exc)
        # Fallback: file icon on a dark, opaque background
        pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8,
                                  size, size)
        pb.fill(0x151a22ff)
        try:
            icon = Gtk.IconTheme.get_default().load_icon(
                fallback_icon, 256, Gtk.IconLookupFlags.FORCE_SIZE)
            icon.composite(pb,
                           (size - icon.get_width()) // 2,
                           (size - icon.get_height()) // 2,
                           icon.get_width(), icon.get_height(),
                           0, 0, 1, 1, GdkPixbuf.InterpType.BILINEAR, 255)
        except Exception as e:
            dbg("media/_media_cover_placeholder: suppressed: %s" % e)
        return pb

    def _tag_number_pair(self, taglist, num_tag, count_tag):
        """
        F33: (Nummer, Gesamtzahl) aus der Tag-Liste lesen – Titelnummer
        und CD-Nummer je nach Codec anders verpackt.
        """
        # → REF MED-AUDTAG-1
        num = total = None
        try:
            ok, val = taglist.get_uint(num_tag)
            if ok and val and int(val) > 0:
                num = int(val)
        except Exception:
            num = None
        try:
            ok, val = taglist.get_uint(count_tag)
            if ok and val and int(val) > 0:
                total = int(val)
        except Exception:
            total = None
        if num is None:
            # String fallback: "3/12" carries the total count along.
            tail = ""
            try:
                ok, val = taglist.get_string(num_tag)
                if ok and val:
                    head, _, tail = val.strip().partition("/")
                    num = int(head)
            except Exception:
                num = None
            if num is not None and num > 0 and total is None and tail:
                try:
                    total = int(tail)
                except ValueError as e:
                    dbg("media/_tag_number_pair: suppressed: %s" % e)
        return num, total

    def _tag_year(self, taglist):
        """
        F33: Veröffentlichungs-Jahr – die Originalveröffentlichung hat
        Vorrang, sonst wird das Datums-Tag als Jahr gelesen.
        """
        # → REF MED-AUDTAG-2
        for name in ("original-date", "datetime", "date"):
            try:
                ok, dt = taglist.get_date_time(name)
                if ok and dt:
                    year = dt.get_year()
                    if year and year > 0:
                        return year
            except Exception as e:
                dbg("media/_tag_year: suppressed: %s" % e)
            try:
                ok, gd = taglist.get_date(name)
                if ok and gd:
                    year = gd.get_year()
                    if year and year > 0:
                        return year
            except Exception as e:
                dbg("media/_tag_year: suppressed: %s" % e)
            try:
                ok, val = taglist.get_string(name)
                if ok and val:
                    head = str(val).strip()[:4]
                    if head.isdigit():
                        return int(head)
            except Exception as e:
                dbg("media/_tag_year: suppressed: %s" % e)
        return None

    def _cover_shadowed(self, pb):
        """
        F34: Cover mit Platzhalter-Ecken und kleinem Schlagschatten.
        """
        # → REF MED-COVER-1
        if not HAVE_PANGOCAIRO:
            return pb
        try:
            w, h = pb.get_width(), pb.get_height()
            if w < 8 or h < 8:
                return pb
            # Same rounding as the placeholder tile: 56/960 of the
            # smaller edge (0.25.1: a third subtler than F34's 56/640).
            r = max(2.0, min(w, h) * 56.0 / 960.0)
            pad = max(6, int(min(w, h) * 0.02))
            # F35: shadow offset right and down – 3 px more area
            # there – and more transparent than in F34.
            dx = max(2, pad // 2)
            dy = max(2, pad // 2)
            ow, oh = w + 2 * pad + 3, h + 2 * pad + 3
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
            cr = cairo.Context(surf)
            # Shadow: six stacked tiles growing outward.
            for i in range(6, 0, -1):
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.04)
                cover_round_path(cr, pad + dx - i, pad + dy - i,
                                       w + 2 * i, h + 2 * i, r + i)
                cr.fill()
            # Tile: corner clipping, then the cover inside.
            cr.save()
            cover_round_path(cr, pad, pad, w, h, r)
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, pb, pad, pad)
            cr.paint()
            cr.restore()
            out = Gdk.pixbuf_get_from_surface(surf, 0, 0, ow, oh)
            return out if out is not None else pb
        except Exception as e:
            dbg("Cover frame (F34) failed: %s" % e)
            return pb

    def _finish_audio(self, path, uri, tags, duration, cover):
        """
        R1-Fortsetzung: Cover, Abspielleiste und Infos aufbauen. F33
        (Nutzer-Wunsch): Die Leiste sitzt mit etwas Abstand UNTER dem
        Cover, die Informationen folgen darunter – nicht mehr darüber.
        """
        # F18: without an embedded cover (or if it was not
        # decodable) show the placeholder tile – a uniform, calm look.
        if cover is None:
            cover = self._media_cover_placeholder()
        # F34: corners like the placeholder tile plus a small
        # shadow – file cover and placeholder look the same.
        cover = self._cover_shadowed(cover)
        scroll = self._scaled_image(cover, 320, upscale=False,
                                    keep_height=True)
        # F33: spacing between cover and play bar.
        scroll.set_margin_bottom(10)
        self._content.pack_start(scroll, False, False, 0)

        # --- Play bar (F33: between cover and information) ---
        self._playbin_set_uri(uri)
        self._player_bar(duration)

        def _num_row(label, num, total):
            # F33: "x of y" – the total count first, else just the number.
            if num:
                rows.append((label, ("%d von %d" % (num, total))
                             if total else str(num)))

        rows = []
        if "title" in tags:
            rows.append(("Titel", tags["title"]))
        if "artist" in tags:
            rows.append(("Interpret", tags["artist"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))
        _num_row("Titelnummer", tags.get("track"),
                 tags.get("track_total"))
        # F35: year as its own row BELOW the album – label
        # "First released" (based on the F33 year detection).
        if "album" in tags:
            rows.append(("Album", tags["album"]))
        if tags.get("year"):
            rows.append(("Zuerst erschienen", str(tags["year"])))
        if "album_artist" in tags:
            rows.append(("Albuminterpret", tags["album_artist"]))
        _num_row("CD-Nummer", tags.get("disc"),
                 tags.get("disc_total"))
        if "codec" in tags:
            rows.append(("Codec", tags["codec"]))
        # F35: genre – only show the row if the tag exists.
        if "genre" in tags:
            rows.append(("Genre", tags["genre"]))

        # 0.9.1: info table via the central helper (previously
        # inline). F35: colons are set centrally in _meta_grid.
        pack_meta_grid(rows, self._content)

    def _playbin_set_uri(self, uri):
        """
        Playbin einmalig anlegen und die URI setzen. B2: Bus-Watch –
        ohne ihn kennt der Player sein Trackende nicht (Pause-Icon
        blieb stehen, Position fror ein) und Abspielfehler blieben
        unsichtbar. Zentraler Baustein – ein späterer Neuversuch der
        Video-Wiedergabe kann ihn unverändert wiederverwenden.
        """
        if self._playbin is None:
            self._playbin = Gst.ElementFactory.make("playbin", "previewer-playbin")
            bus = self._playbin.get_bus()
            bus.add_signal_watch()
            bus.connect("message::eos", self._on_player_eos)
            bus.connect("message::error", self._on_player_error)
        self._playbin.set_property("uri", uri)

    def _player_bar(self, duration):
        """
        Player-Leiste (Play/Pause, Slider, Position) bauen und packen –
        zentraler Baustein der Musik-Vorschau (B2/B3).
        """
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
        # While the user drags the slider, the timer must not push
        # it back (it would jump away under the hand).
        self._seek_dragging = False
        self._seek_scale.connect("button-press-event", self._on_seek_press)
        self._seek_scale.connect("button-release-event",
                                 self._on_seek_release)
        player_box.pack_start(self._seek_scale, True, True, 0)

        self._pos_label = Gtk.Label(label="0:00")
        player_box.pack_start(self._pos_label, False, False, 0)
        # F33: some spacing between play bar and information.
        player_box.set_margin_bottom(6)
        self._content.pack_start(player_box, False, False, 0)

        self._ensure_progress_timer()

    def _on_player_eos(self, bus, msg):
        """Trackende: zurück an den Anfang, Icon zurück auf Play (B2)."""
        try:
            self._playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
            self._playbin.set_state(Gst.State.PAUSED)
            if getattr(self, "_btn_play", None):
                self._btn_play.set_image(Gtk.Image.new_from_icon_name(
                    "media-playback-start-symbolic", Gtk.IconSize.BUTTON))
            if getattr(self, "_pos_label", None):
                self._pos_label.set_text("0:00")
            if getattr(self, "_seek_scale", None):
                self._seek_scale.set_value(0)
        except Exception as e:
            dbg("media/_on_player_eos: suppressed: %s" % e)

    def _on_player_error(self, bus, msg):
        """Abspielfehler: still abstoppen und im Panel melden (B2)."""
        try:
            err, detail = msg.parse_error()
            dbg("Playback error: %s (%s)" % (err, detail))
        except Exception:
            err = "unknown playback error"
        try:
            self._playbin.set_state(Gst.State.NULL)
            if getattr(self, "_btn_play", None):
                self._btn_play.set_image(Gtk.Image.new_from_icon_name(
                    "media-playback-start-symbolic", Gtk.IconSize.BUTTON))
            pack_hint(self._content, "Abspielfehler – Datei über den Öffnen-Knopf "
                       "mit einer anderen Anwendung betrachten.")
        except Exception as e:
            dbg("media/_on_player_error: suppressed: %s" % e)

    def _ensure_progress_timer(self):
        """Positionstimer anlegen, falls er gerade nicht läuft (B3)."""
        if not self._progress_timer:
            self._progress_timer = GLib.timeout_add(400, self._tick_player)

    def _scale_pixbuf(self, pb, max_w, max_h):
        w, h = pb.get_width(), pb.get_height()
        if w <= max_w and h <= max_h:
            return pb
        scale = min(max_w / w, max_h / h)
        return pb.scale_simple(max(1, int(w * scale)),
                               max(1, int(h * scale)),
                               GdkPixbuf.InterpType.BILINEAR)

    def _render_video(self, path, uri):
        """
        Video-Vorschau: Kachel und Infos.
        R1: Erkundung im Hintergrund-Thread (siehe _media_probe_async) –
        UI bleibt sofort bedienbar. Ohne eingebettetes Vorschaubild
        erscheint die generische Kachel wie bei Musik (F22). Die Panel-
        Wiedergabe aus 0.7.0–0.7.2 ist in 0.8.0 wieder entfernt – zum
        Abspielen der Öffnen-Knopf (Medienprogramm der Wahl).
        """
        self._media_probe_async(path, uri, self._finish_video, video=True)

    def _finish_video(self, path, uri, tags, duration, image):
        """R1-Fortsetzung: Kachel und Infos aufbauen."""
        # F22: without an embedded preview image show the generic
        # tile – play triangle and film perforation instead of notes.
        if image is None:
            image = self._media_cover_placeholder(
                glyph="▶", fallback_icon="video-x-generic",
                grad=((0.086, 0.141, 0.180), (0.122, 0.322, 0.369)),
                perforations=True)
        scroll = self._scaled_image(image, 320, upscale=False,
                                    keep_height=True)
        self._content.pack_start(scroll, False, False, 0)

        rows = [("Datei", os.path.basename(path))]
        if "title" in tags:
            rows.append(("Titel", tags["title"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))
        # 0.9.1: info table via the central helper (previously
        # inline, now uniform like EML/e-book/audio).
        pack_meta_grid(rows, self._content)

    # --- Audio player logic ---------------------------------------------------

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
            # B3: the timer only runs while playback exists – after
            # pause/stop it is cleared; recreate it here if gone.
            self._ensure_progress_timer()

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
        except Exception as e:
            dbg("media/_on_seek: suppressed: %s" % e)
        return False

    def _tick_player(self):
        """Positionsanzeige aktualisieren (B3: nur während der Wiedergabe)."""
        if self._playbin is None:
            self._progress_timer = 0
            return False
        try:
            ok, state, pending = self._playbin.get_state(0)
            if (state != Gst.State.PLAYING
                    and pending != Gst.State.PLAYING):
                # Playback is not running (or starting) – timer off;
                # _on_play_pause re-creates it on the next start.
                self._progress_timer = 0
                return False
            ok, pos = self._playbin.query_position(Gst.Format.TIME)
            ok2, dur = self._playbin.query_duration(Gst.Format.TIME)
            if ok and pos >= 0:
                self._pos_label.set_text(format_seconds(pos // Gst.SECOND))
                if ok2 and dur > 0:
                    # → REF MED-SEEK-1
                    self._ensure_seek_range(dur)
                    self._update_seek_pos(pos)
        except Exception as e:
            dbg("media/_tick_player: suppressed: %s" % e)
        return True  # keep running

    def _ensure_seek_range(self, dur_ns):
        """Slider-Bereich an die echte Dauer (ns) anpassen, falls nötig."""
        scale = getattr(self, "_seek_scale", None)
        if scale is None:
            return
        upper = max(1, int(dur_ns // Gst.SECOND))
        adj = scale.get_adjustment()
        if abs(adj.get_upper() - upper) > 1:
            dbg("Slider range adjusted: 0–%d s (was 0–%d s)"
                % (upper, int(adj.get_upper())))
            adj.configure(0.0, 0.0, float(upper), 1.0, 10.0, 0.0)

    def _update_seek_pos(self, pos_ns):
        """Slider auf die aktuelle Position (ns) schieben."""
        if getattr(self, "_seek_dragging", False):
            return          # user is dragging – do not push
        scale = getattr(self, "_seek_scale", None)
        if scale is None:
            return
        sec = pos_ns / Gst.SECOND
        adj = scale.get_adjustment()
        # Threshold small enough for short tracks, large enough so
        # the slider does not jitter on every tick.
        if abs(adj.get_value() - sec) > 0.75:
            scale.set_value(sec)

    def _on_seek_press(self, widget, event):
        self._seek_dragging = True
        return False        # let GTK keep processing the event

    def _on_seek_release(self, widget, event):
        self._seek_dragging = False
        return False        # let GTK keep processing the event

    def _stop_playback(self):
        # B3: tear down the timer (it otherwise runs forever, even
        # after window destruction) and cleanly NULL the player.
        if self._progress_timer:
            GLib.source_remove(self._progress_timer)
            self._progress_timer = 0
        if self._playbin is not None:
            try:
                self._playbin.set_state(Gst.State.NULL)
            except Exception as e:
                dbg("media/_stop_playback: suppressed: %s" % e)


PREVIEWER_VERSION = "0.42.1"
dbg("previewer_render_media %s loaded (F31: image/SVG/audio/video "
    "renderer; R9/B7 discipline and caps stay)"
    % PREVIEWER_VERSION)