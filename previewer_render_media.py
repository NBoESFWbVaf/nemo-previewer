#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Renderer-Modul Medien (previewer_render_media.py)
=============================================================

STAND: Version 0.22.0 – F38 (Nutzer-Wunsch): Die Bild-Spalte ist in
einen 60-%-Bereich (Bild, vertikal und horizontal mittig) und einen
40-%-Bereich (Info-Tabelle) geteilt, live an die Spaltenhöhe gekop-
pelt; Streifen-Fix (Mittig-Zentrierung am Bild statt am Scrolled-
Window, siehe MED-SPLIT-1) und XMP-Ergänzung: „Location“ (IPTC
Core) plus benutzerdefinierte XMP-Felder in der Tabelle. K3: SVG
über die Cairo-Route DPI-artig auf Panelbreite gerendert (→ REF
MED-SVG-DPI-1). F36-Basis (EXIF-Parser mit APEX-Fallbacks), F35/
F34/F33 unberührt. (0.15.0/F31: aus dem Panel-Kern hierher gezogen.)

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
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
)

# --- Optionale Module (Fehlen ist kein Fehler, nur weniger Vorschau) ---

# GStreamer für Audio-/Video-Metadaten (Discoverer) und Wiedergabe.
HAVE_GST = False
try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import Gst, GstPbutils
    Gst.init(None)
    HAVE_GST = True
except Exception:
    pass

# librsvg für die SVG-Vorschau: GdkPixbuf bringt (seit gdk-pixbuf 2.42)
# keinen eigenen SVG-Loader mehr mit.
HAVE_RSVG = False
try:
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    HAVE_RSVG = True
except Exception:
    pass

# PangoCairo + pycairo, um das Platzhalter-Cover (F18) zu zeichnen.
HAVE_PANGOCAIRO = False
try:
    import cairo  # pycairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo
    HAVE_PANGOCAIRO = True
except Exception:
    pass

# K3: Cairo allein genügt für die SVG-DPI-Route (siehe _rsvg_cairo_pb):
# render_document ersetzt das in neuerem librsvg deprecated
# get_pixbuf() und rendert zusätzlich beliebig groß.
HAVE_CAIRO = False
try:
    import cairo  # pycairo
    HAVE_CAIRO = True
except Exception:
    pass


# Prozess-Zustand für die Medien-Erkundung (Konvention: Modul-Dict statt
# global): wurde das GI-Warm-up bereits erledigt?
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
        # Lazy Pfad-Auflösung: Ein fehlendes Symbol (z.B. Gst.PlayFlags
        # ist im Mint-22-Binding NICHT vorhanden) darf hier NIE eine
        # AttributeError werfen – sonst reißt der Warm-up die gesamte
        # Medien-Vorschau mit (Lehre aus dem 0.6.0-Test).
        try:
            obj = base
            for part in dotted.split("."):
                obj = getattr(obj, part)
        except Exception:
            pass

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


# 0.9.2 (Audit „Pufferüberlauf/OOM“): Deckel gegen Dekompressions- und
# Dekodierbomben – ein präpariertes Bild/PDF/EPUB/DOCX/EML darf Nemo
# niemals durch Riesen-Allokationen abschießen.
_IMAGE_FILE_CAP = 64 * 1024 * 1024   # Bilddatei: Rohbytes vor Dekodierung
_MEDIA_IMAGE_CAP = 32 * 1024 * 1024  # eingebettetes Cover aus Medien-Tags

# --- F36: Foto-Metadaten (EXIF) mit Python-Bordmitteln --------------------

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
            return                      # B7: Bomben-Deckel
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
                except Exception:
                    pass
    except Exception:
        pass


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
    except Exception:
        pass
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
    except Exception:
        pass
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


# F38: Standard-XMP-Namensräume – alles DARÜBER hinaus gilt als
# „vom Benutzer definiert“ und landet als eigene Tabellen-Zeile hier.
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
        # F38: „Location“ – textlicher Ort aus IPTC Core (digikam,
        # Lightroom & Co. füllen ihn im Ort-Dialog), Attribute zuerst:
        # Adobe-Tools schreiben einfache Werte gern als Attribut der
        # rdf:Description statt als eigenes Element.
        m = (re.search(r'<[^>]*Iptc4xmpCore:Location="([^"]+)"', xmp)
             or re.search(
                 r"<Iptc4xmpCore:Location>(.*?)</Iptc4xmpCore:Location>",
                 xmp, re.S))
        if m:
            loc = _xmp_clean(m.group(1))
            if loc:
                out["Location"] = loc
        # F38: benutzerdefinierte Felder – Element-Form: Öffnungs-Tags
        # scannen und das passende Schluss-Tag suchen, NICHT als
        # verschachtelten Gesamt-Match (→ REF MED-XMP-1: sonst
        # verschluckt <x:xmpmeta> als erster Treffer das Dokument).
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
        # F38: benutzerdefinierte Felder – Attribut-Form (einfache
        # Werte ohne eigenes Element, von Adobe-Tools bevorzugt).
        for m in re.finditer(r'(\w+):(\w+)="([^"]+)"', xmp):
            pfx, name, val = m.group(1), m.group(2), m.group(3)
            val = _xmp_clean(val)
            if pfx not in _XMP_STD and name not in _XMP_STD and val:
                custom.setdefault("%s:%s" % (pfx, name), val)
        for key in list(custom)[:10]:
            out[key] = custom[key]
    except Exception:
        pass
    return out


def _exif_parse(data):
    """
    F36: EXIF-Kerninformationen aus JPEG-/TIFF-Bytes – mit
    Python-Bordmitteln, ohne neue Pflicht-Abhängigkeit. Hersteller-
    Eigenheiten fangen Standard-Fallbacks ab (APEX statt Direktwert,
    Datums-Kaskade, GPS-Dezimalgrad). Zurück kommt ein Dict mit
    fertigen Anzeige-Texten – nur vorhandene Werte.
    """
    # → REF MED-EXIF-2
    out = {}
    try:
        pos = data.find(b"Exif\x00\x00", 0, 262144)
        base = pos + 6 if pos >= 0 else 0
        # F36: Puffer zwischen Marker und TIFF-Kopf überlesen (0x00/
        # 0x20-Padding, teils Samsung/Olympus) – der Kopf folgt erst.
        stop = base + 16
        while base < stop and data[base:base + 1] in (b"\x00", b"\x20"):
            base += 1
        head = data[base:base + 2]
        if head == b"MM":
            bo = ">"
        elif head == b"II":
            bo = "<"
        else:
            return out
        if struct.unpack_from(bo + "H", data, base + 2)[0] != 42:
            return out
        ifd0 = base + struct.unpack_from(bo + "I", data, base + 4)[0]
        tags = {}
        _exif_read_ifd(data, base, bo, ifd0, tags)
        # F36: Kameramodell – viele Modelle wiederholen den Hersteller
        # im Modell-Namen („Canon“ + „Canon EOS …“): nur dann kürzen.
        make = _exif_str(tags.get(0x010F))
        model = _exif_str(tags.get(0x0110))
        if model:
            if make and model.lower().startswith(make.lower()):
                out["Kameramodell"] = model
            elif make:
                out["Kameramodell"] = "%s %s" % (make, model)
            else:
                out["Kameramodell"] = model
        # F36: Aufnahmedatum – Original vor digitalisiert vor Datei-
        # Datum; Hersteller schreiben das echte Datum teils nur an
        # einer der drei Stellen.
        for tag in (0x9003, 0x9004, 0x0132):
            dt = _exif_str(tags.get(tag))
            if dt and len(dt) >= 16 and dt[4] == ":" and dt[7] == ":":
                out["Aufnahmedatum"] = "%s.%s.%s %s" % (
                    dt[8:10], dt[5:7], dt[0:4], dt[11:16])
                break
        # F36: Belichtungszeit – Direktwert, sonst APEX-Zeitwert
        # (t = 2^-av; manche Kompakte schreiben nur den).
        t = _exif_frac(tags.get(0x829A), bo)
        if t is None:
            av = _exif_frac(tags.get(0x9201), bo)
            if av is not None:
                t = 2.0 ** -av
        if t:
            if t < 1.0:
                out["Belichtungszeit"] = "1/%d s" % max(
                    2, round(1.0 / t))
            elif t == int(t):
                out["Belichtungszeit"] = "%d s" % int(t)
            else:
                out["Belichtungszeit"] = "%.1f s" % t
        # F36: Blende – FNumber, sonst APEX-Öffnung (N = 2^(av/2)).
        fn = _exif_frac(tags.get(0x829D), bo)
        if fn is None:
            av = _exif_frac(tags.get(0x9202), bo)
            if av is not None:
                fn = 2.0 ** (av / 2.0)
        if fn:
            out["Blende"] = "f/%.1f" % fn
        # F36: „Zoom“ als Brennweite, plus 35-mm-Äquivalent, wenn es
        # abweicht (Vollformat-Kameras tragen kein eigenes Tag).
        fl = _exif_frac(tags.get(0x920A), bo)
        fl35 = _exif_num(tags.get(0xA405), bo)
        if fl:
            txt = "%g mm" % fl
            if fl35 and abs(fl35 - fl) > 0.5:
                txt += " (%d mm äquiv.)" % fl35
            out["Brennweite"] = txt
        elif fl35:
            out["Brennweite"] = "%d mm" % fl35
        # F36: ISO – klassische ISOSpeedRatings, sonst ISOSpeed.
        iso = _exif_num(tags.get(0x8827), bo)
        if iso is None:
            iso = _exif_num(tags.get(0x8833), bo)
        if iso:
            out["ISO"] = str(iso)
        # F36: Aufnahmeort – GPS-Gradminuten in Dezimalgrade; die
        # Referenz-Buchstaben (N/S, E/W) gibt das jeweilige GPS-Tag.
        lat = _exif_dms(tags, 0x0002, bo)
        lon = _exif_dms(tags, 0x0004, bo)
        if lat is not None and lon is not None:
            lr = (_exif_str(tags.get(0x0001)) or "N")[:1]
            lor = (_exif_str(tags.get(0x0003)) or "E")[:1]
            out["Aufnahmeort"] = "%.4f° %s, %.4f° %s" % (
                abs(lat), lr, abs(lon), lor)
    except Exception as exc:
        dbg("EXIF-Parsing fehlgeschlagen: %s" % exc)
    return out

# ========================== Renderer: Medien ================================


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
        # F38-Streifen-Fix: Mittig macht DAS BILD, nicht der Scroll.
        # align=CENTER schrumpft einen ScrolledWindow auf seine
        # NATÜRLICHE Breite – ein scrollbares Widget kann sie auf
        # ~0 senken, das auf Spaltenbreite skalierte Bild wäre also
        # nur ein schmaler Streifen. Das Gtk.Image sitzt via
        # Viewport im Scroll; halign/valign CENTER am Bild zentriert
        # es in beiden Richtungen im 60-%-Bereich.
        try:
            vp = scroll.get_child()
            img = vp.get_child() if vp is not None else None
            if img is not None:
                img.set_halign(Gtk.Align.CENTER)
                img.set_valign(Gtk.Align.CENTER)
        except Exception:
            pass
        top.pack_start(scroll, True, True, 0)
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # F38: Info-Bereich – _meta_grid packt die Bild-Tabelle hierher.
        self._image_info_box = bottom
        top.set_size_request(-1,
                             max(80, int(self._preview_height() * 0.6)))
        top.connect("size-allocate", self._image_split_sync)
        # F38: expand=False hält die Höhe auf der 60-%-Anforderung –
        # expand/fill wirken in einer vertikalen GtkBox nur auf die
        # HÖHE; die Breite quer gibt die Box Kindern ohnehin voll.
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
        except Exception:
            pass

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
            # K3: Ziel ist die Panelbreite (kleine SVGs wachsen scharf
            # mit, Vektor statt Raster-Upcast), Höhe gedeckelt.
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
            self._hint("SVG-Vorschau nicht verfügbar – "
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
                # K3-Fallback: der bisherige, in neuerem librsvg
                # deprecated Pfad – funktioniert bis dahin.
                try:
                    pb = handle.get_pixbuf()
                except Exception as e:
                    err = err or e
        if pb is None:
            self._hint("Konnte SVG nicht lesen: %s" % err)
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
            # F38: Maße in den Info-Bereich der Spalten-Aufteilung.
            box = getattr(self, "_image_info_box", None) or self._content
            box.pack_start(info, False, False, 0)
        except Exception:
            pass

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
        self._hint("Lade Bild – einen Moment …")
        try:
            target_w = max(1024, self._preview_width() * 2)
        except Exception:
            target_w = 1024

        def work():
            data, err, exif, xmp = None, None, None, None
            try:
                with open(path, "rb") as fh:
                    data = fh.read(_IMAGE_FILE_CAP)
                dbg("Bild gelesen: %s (%d Bytes)" % (path, len(data)))
            except Exception as exc:
                data, err = None, exc
                dbg("Bild-Lesen fehlgeschlagen (%s): %s" % (path, exc))
            # F36: EXIF gleich im Worker auswerten – reine Byte-Arbeit
            # ohne Gdk-Objekte, passend zur R1/B7-Thread-Disziplin.
            # F38: XMP (Location + benutzerdefinierte Felder) ebenso.
            if data:
                exif = _exif_parse(data)
                xmp = _xmp_parse(data)
            try:
                GLib.idle_add(self._image_probe_done,
                              path, target_w, data, err, exif, xmp)
            except Exception as exc:
                dbg("Bild-Rückgabe fehlgeschlagen (%s): %s"
                    % (path, exc))

        try:
            threading.Thread(target=work, daemon=True).start()
        except Exception:
            # Rettungsanker: Thread nicht startbar → synchron lesen,
            # die Dekodierung übernimmt _image_probe_done direkt.
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
            dbg("Bild-Ergebnis verworfen, Auswahl wechselte: %s" % path)
            return False      # Auswahl hat inzwischen gewechselt
        self._clear_content()
        pb, orig = None, {}
        if data is not None:
            try:
                # Decode-Deckel (0.9.2) bleibt: set_size verkleinert
                # zur DEKODIERzeit – Bomben-Bilder kosten nur die
                # gedeckelte Fläche.
                pb = _pixbuf_from_bytes(
                    data, max_w=target_w, max_h=2 * MAX_IMAGE_HEIGHT,
                    orig=orig)
            except Exception as exc:
                dbg("Bild-Dekodierung fehlgeschlagen (%s): %s"
                    % (path, exc))
        if pb is None:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, 4096, 4096, True)
            except Exception:
                pb = None
        if pb is None:
            self._hint("Konnte Bild nicht laden: %s" % (err or "unbekannt"))
            self._render_generic()
            # Auch dieser Fallback packt NACH dem show_all() des
            # Render-Durchlaufs – ohne eigenes show_all unsichtbar.
            self._content.show_all()
            return False
        # EXIF-Ausrichtung anwenden: Fotos, die die Drehung nur im
        # Orientation-Tag tragen (typisch bei Smartphone-Kameras),
        # würden sonst quer oder auf dem Kopf liegen.
        try:
            pb = pb.apply_embedded_orientation()
        except Exception:
            pass
        dbg("Bild dekodiert: %s (%d × %d px)" %
            (path, pb.get_width(), pb.get_height()))
        if pb.get_width() > 4096 or pb.get_height() > MAX_IMAGE_HEIGHT:
            pb = self._scale_pixbuf(pb, 4096, MAX_IMAGE_HEIGHT)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False,
                                    keep_height=True, frac_h=0.6)
        self._pack_image_capped(scroll)
        try:
            # Maße: die ORIGINALMAßE aus dem Datei-Kopf (size-prepared,
            # vor der Deckelung), nicht die gedeckelte Dekodiergröße –
            # sonst hieße ein 50-MP-Foto plötzlich „1024 px". Das
            # Hoch-/Querformat folgt dem orientierten Bild (EXIF).
            w = orig.get("w", pb.get_width())
            h = orig.get("h", pb.get_height())
            if (w > h) != (pb.get_width() > pb.get_height()):
                w, h = h, w
            # F36: Maße-Zeile ist in der Foto-Info-Tabelle aufgegangen;
            # alle weiteren Zeilen nur, wenn EXIF sie hergibt.
            rows = [("Höhe", "%d px" % h), ("Breite", "%d px" % w)]
            for key in ("Aufnahmedatum", "Aufnahmeort"):
                if exif and key in exif:
                    rows.append((key, exif[key]))
            # F38: „Location“ (XMP/IPTC Core) direkt nach dem
            # Aufnahmeort – falls vorhanden.
            if xmp and xmp.get("Location"):
                rows.append(("Location", xmp["Location"]))
            for key in ("Kameramodell", "Belichtungszeit",
                        "Brennweite", "Blende", "ISO"):
                if exif and key in exif:
                    rows.append((key, exif[key]))
            # F38: benutzerdefinierte XMP-Felder aus nicht-standard-
            # Namensräumen – jede Zeile nur mit vorhandenem Wert.
            if xmp:
                for key in [k for k in xmp if k != "Location"][:10]:
                    rows.append((key, xmp[key]))
            # F38: Tabelle in den 40-%-Info-Bereich der Aufteilung.
            self._meta_grid(rows, self._image_info_box)
        except Exception:
            pass
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
        self._hint("Lese Medien-Informationen – einen Moment …")
        _media_gi_warmup()
        try:
            try:
                disc = GstPbutils.Discoverer.new(10 * Gst.SECOND)
            except (AttributeError, TypeError):
                # Neuere PyGObject-Builds mappen gst_discoverer_new
                # NICHT als Konstruktor – deshalb explizit .new(),
                # mit Fallback für ältere Builds.
                disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            # Attribut-Auflösung IM GTK-Thread; der Worker ruft nur das
            # fertige Callable auf. discover_uri = korrekter Name,
            # discover_uri_sync nur als Defensiv-Fallback.
            probe = getattr(disc, "discover_uri", None)
            if probe is None:
                probe = disc.discover_uri_sync
        except Exception as e:
            dbg("Discoverer nicht anlegbar: %s" % e)
            # Ohne Discoverer trotzdem die UI aufbauen (Platzhalter,
            # Player) – nicht im Hinweis stecken bleiben.
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
                                         # F35: Genre – reines String-Tag.
                                         ("genre", Gst.TAG_GENRE)):
                        ok, val = taglist.get_string(gst_tag)
                        if ok and val:
                            tags[key] = val
                    # F33: erweiterte Musik-Tags in eigener Klammern –
                    # ein Fehler hier darf nie auch noch das Cover
                    # kosten. Konstanten per getattr mit String-Fallback
                    # (der kanonische GStreamer-Tag-Name ist beides).
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
                        # Codec-Fallback: der Container (z. B. „Ogg“),
                        # wenn der Audio-Codec selbst fehlt.
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
                        dbg("Tag-Erweiterung (F33) fehlgeschlagen: %s" % e)
                    # Bild-Bytes sammeln (nicht dekodieren – das passiert
                    # erst im GTK-Thread). Videos: Standbild bevorzugt;
                    # Audio: eingebettetes Cover bevorzugt.
                    order = ((Gst.TAG_PREVIEW_IMAGE, Gst.TAG_IMAGE) if video
                             else (Gst.TAG_IMAGE, Gst.TAG_PREVIEW_IMAGE))
                    for gst_tag in order:
                        ok, sample = taglist.get_sample(gst_tag)
                        if ok and sample:
                            buf = sample.get_buffer()
                            # 0.9.2: Byte-Deckel – eingebettete Cover
                            # können sonst beliebig groß sein.
                            image_bytes = buf.extract_dup(
                                0, min(buf.get_size(), _MEDIA_IMAGE_CAP))
                            break
            except Exception as e:
                dbg("Discoverer-Fehler: %s" % e)
            GLib.idle_add(self._media_probe_done, path, uri, finish,
                          tags, duration, image_bytes)

        threading.Thread(target=work, daemon=True).start()

    def _media_probe_done(self, path, uri, finish, tags, duration,
                          image_bytes):
        """R1: Rückkehr der Hintergrund-Erkundung in den GTK-Main-Loop."""
        # Auswahl hat inzwischen gewechselt – Ergebnis verwerfen.
        if self._path != path:
            return False
        pixbuf = None
        if image_bytes:
            try:
                # 0.9.2: bewachter Loader mit Decode-Deckel (siehe
                # _pixbuf_from_bytes) statt rohem PixbufLoader.
                pixbuf = _pixbuf_from_bytes(image_bytes)
            except Exception as exc:
                dbg("Medien-Bild nicht darstellbar: %s" % exc)
        # Lese-Hinweis entfernen und die eigentliche Vorschau aufbauen.
        self._clear_content()
        try:
            finish(path, uri, tags, duration, pixbuf)
        except Exception:
            # Gleicher Schutz wie in _render: nie werfen, immer Fallback.
            dbg("Fehler beim Aufbauen der Medien-Vorschau (%r):" % path)
            traceback.print_exc()
            try:
                self._clear_content()
                self._render_generic()
            except Exception:
                pass
        # Erst hier gepackte Widgets liegen NACH dem show_all() des
        # Render-Durchlaufs – sie brauchen daher ihr eigenes show_all.
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
            # Abgerundete Ecken als Beschneidungspfad; außerhalb bleibt
            # die Fläche transparent – die Kachel wirkt auf jedem Theme.
            r = 56.0
            cr.new_sub_path()
            cr.arc(size - r, r, r, -0.5 * math.pi, 0.0)
            cr.arc(size - r, size - r, r, 0.0, 0.5 * math.pi)
            cr.arc(r, size - r, r, 0.5 * math.pi, math.pi)
            cr.arc(r, r, r, math.pi, 1.5 * math.pi)
            cr.close_path()
            cr.clip()
            # Diagonaler Verlauf (Farbpaar je Medientyp)
            pat = cairo.LinearGradient(0.0, 0.0, size, size)
            pat.add_color_stop_rgba(0.0, grad[0][0], grad[0][1], grad[0][2],
                                   1.0)
            pat.add_color_stop_rgba(1.0, grad[1][0], grad[1][1], grad[1][2],
                                   1.0)
            cr.set_source(pat)
            cr.paint()
            # Filmperforation (nur Video-Kachel): halbtransparente
            # Lochreihen am oberen und unteren Rand.
            if perforations:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
                for i in range(8):
                    x = 23.0 + i * 80.0
                    cr.rectangle(x, 20.0, 34.0, 26.0)
                    cr.rectangle(x, size - 46.0, 34.0, 26.0)
                cr.fill()
            # Symbol halbtransparent weiß, mittig (Pango findet selbst
            # eine Schrift mit dem Glyph – Serife zuerst).
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
            dbg("Platzhalter-Cover nicht zeichenbar (%s) – Icon-Fallback"
                % exc)
        # Fallback: Datei-Icon auf dunklem, deckendem Grund
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
        except Exception:
            pass
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
            # String-Fallback: „3/12“ trägt die Gesamtzahl gleich mit.
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
                except ValueError:
                    pass
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
            except Exception:
                pass
            try:
                ok, gd = taglist.get_date(name)
                if ok and gd:
                    year = gd.get_year()
                    if year and year > 0:
                        return year
            except Exception:
                pass
            try:
                ok, val = taglist.get_string(name)
                if ok and val:
                    head = str(val).strip()[:4]
                    if head.isdigit():
                        return int(head)
            except Exception:
                pass
        return None

    @staticmethod
    def _cover_round_path(cr, x, y, w, h, r):
        """F34: Rechteck mit runden Ecken als aktuellen Cairo-Pfad."""
        r = min(r, w / 2.0, h / 2.0)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -0.5 * math.pi, 0.0)
        cr.arc(x + w - r, y + h - r, r, 0.0, 0.5 * math.pi)
        cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        cr.close_path()

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
            # Gleiche Rundung wie die Platzhalter-Kachel: 56/640 der
            # Kantenlänge (min(w, h)), mit der Anzeige skaliert.
            r = max(2.0, min(w, h) * 56.0 / 640.0)
            pad = max(6, int(min(w, h) * 0.02))
            # F35: Schatten nach rechts und unten versetzt – dort 3 px
            # mehr Fläche – und transparenter als in F34.
            dx = max(2, pad // 2)
            dy = max(2, pad // 2)
            ow, oh = w + 2 * pad + 3, h + 2 * pad + 3
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
            cr = cairo.Context(surf)
            # Schatten: sechs gestapelte, nach außen wachsende Kacheln.
            for i in range(6, 0, -1):
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.04)
                self._cover_round_path(cr, pad + dx - i, pad + dy - i,
                                       w + 2 * i, h + 2 * i, r + i)
                cr.fill()
            # Kachel: Ecken-Beschneidung, dann das Cover hinein.
            cr.save()
            self._cover_round_path(cr, pad, pad, w, h, r)
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, pb, pad, pad)
            cr.paint()
            cr.restore()
            out = Gdk.pixbuf_get_from_surface(surf, 0, 0, ow, oh)
            return out if out is not None else pb
        except Exception as e:
            dbg("Cover-Rahmen (F34) fehlgeschlagen: %s" % e)
            return pb

    def _finish_audio(self, path, uri, tags, duration, cover):
        """
        R1-Fortsetzung: Cover, Abspielleiste und Infos aufbauen. F33
        (Nutzer-Wunsch): Die Leiste sitzt mit etwas Abstand UNTER dem
        Cover, die Informationen folgen darunter – nicht mehr darüber.
        """
        # F18: Ohne eingebettetes Cover (oder wenn es nicht dekodierbar
        # war) die Platzhalter-Kachel zeigen – Dateien mit und ohne Bild
        # haben damit das gleiche, ruhige Erscheinungsbild.
        if cover is None:
            cover = self._media_cover_placeholder()
        # F34: Ecken wie die Platzhalter-Kachel, dazu ein kleiner
        # Schatten – Datei-Cover und Platzhalter sehen gleich aus.
        cover = self._cover_shadowed(cover)
        scroll = self._scaled_image(cover, 320, upscale=False,
                                    keep_height=True)
        # F33: Abstand zwischen Cover und Abspielleiste.
        scroll.set_margin_bottom(10)
        self._content.pack_start(scroll, False, False, 0)

        # --- Abspielleiste (F33: zwischen Cover und Informationen) ---
        self._playbin_set_uri(uri)
        self._player_bar(duration)

        def _num_row(label, num, total):
            # F33: „x von y“ – erst die Gesamtzahl, sonst nur die Zahl.
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
        # F35: Jahr als eigene Zeile UNTER dem Album – Bezeichnung
        # „Zuerst erschienen“ (Basis: F33-Jahresermittlung).
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
        # F35: Genre – nur die Zeile zeigen, wenn das Tag existiert.
        if "genre" in tags:
            rows.append(("Genre", tags["genre"]))

        # 0.9.1: Info-Tabelle über den zentralen Helfer (zuvor inline
        # identisch gebaut – jetzt wie EML/E-Book einheitlich). F35:
        # Doppelpunkte an den Bezeichnungen setzt _meta_grid zentral.
        self._meta_grid(rows)

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
        # Während der Nutzer am Slider zieht, darf der Timer den Slider
        # nicht zurückschieben (sonst springt er unter der Hand weg).
        self._seek_dragging = False
        self._seek_scale.connect("button-press-event", self._on_seek_press)
        self._seek_scale.connect("button-release-event",
                                 self._on_seek_release)
        player_box.pack_start(self._seek_scale, True, True, 0)

        self._pos_label = Gtk.Label(label="0:00")
        player_box.pack_start(self._pos_label, False, False, 0)
        # F33: etwas Abstand zwischen Abspielleiste und Informationen.
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
        except Exception:
            pass

    def _on_player_error(self, bus, msg):
        """Abspielfehler: still abstoppen und im Panel melden (B2)."""
        try:
            err, detail = msg.parse_error()
            dbg("Abspielfehler: %s (%s)" % (err, detail))
        except Exception:
            err = "unbekannter Abspielfehler"
        try:
            self._playbin.set_state(Gst.State.NULL)
            if getattr(self, "_btn_play", None):
                self._btn_play.set_image(Gtk.Image.new_from_icon_name(
                    "media-playback-start-symbolic", Gtk.IconSize.BUTTON))
            self._hint("Abspielfehler – Datei über den Öffnen-Knopf "
                       "mit einer anderen Anwendung betrachten.")
        except Exception:
            pass

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
        # F22: Ohne eingebettetes Vorschaubild die generische Kachel
        # zeigen – Abspiel-Dreieck und Filmperforation statt Noten.
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
        # 0.9.1: Info-Tabelle über den zentralen Helfer (zuvor inline
        # identisch gebaut – jetzt wie EML/E-Book/Audio einheitlich).
        self._meta_grid(rows)

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
            # B3: Timer läuft nur, solange eine Wiedergabe existiert –
            # nach Pause/Stop wird er im _tick_player bzw. beim Wechsel
            # abgeräumt; hier wieder anlegen, falls er weg ist.
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
        except Exception:
            pass
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
                # Wiedergabe läuft (oder läuft an) nicht – Timer aus;
                # _on_play_pause legt ihn bei erneutem Start wieder an.
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
        except Exception:
            pass
        return True  # weiterlaufen

    def _ensure_seek_range(self, dur_ns):
        """Slider-Bereich an die echte Dauer (ns) anpassen, falls nötig."""
        scale = getattr(self, "_seek_scale", None)
        if scale is None:
            return
        upper = max(1, int(dur_ns // Gst.SECOND))
        adj = scale.get_adjustment()
        if abs(adj.get_upper() - upper) > 1:
            dbg("Slider-Bereich nachgezogen: 0–%d s (war 0–%d s)"
                % (upper, int(adj.get_upper())))
            adj.configure(0.0, 0.0, float(upper), 1.0, 10.0, 0.0)

    def _update_seek_pos(self, pos_ns):
        """Slider auf die aktuelle Position (ns) schieben."""
        if getattr(self, "_seek_dragging", False):
            return          # Nutzer zieht gerade – nicht reinschieben
        scale = getattr(self, "_seek_scale", None)
        if scale is None:
            return
        sec = pos_ns / Gst.SECOND
        adj = scale.get_adjustment()
        # Schwellwert klein genug für kurze Stücke, aber groß genug,
        # dass der Slider nicht bei jedem Tick zittert.
        if abs(adj.get_value() - sec) > 0.75:
            scale.set_value(sec)

    def _on_seek_press(self, widget, event):
        self._seek_dragging = True
        return False        # GTK soll das Event weiterverarbeiten

    def _on_seek_release(self, widget, event):
        self._seek_dragging = False
        return False        # GTK soll das Event weiterverarbeiten

    def _stop_playback(self):
        # B3: Timer aufräumen (lief sonst ewig weiter, auch nach
        # Fensterabbau) und Player sauber auf NULL legen.
        if self._progress_timer:
            GLib.source_remove(self._progress_timer)
            self._progress_timer = 0
        if self._playbin is not None:
            try:
                self._playbin.set_state(Gst.State.NULL)
            except Exception:
                pass



PREVIEWER_VERSION = "0.22.0"
dbg("previewer_render_media %s geladen (F31: Bild/SVG/Audio/Video-"
    "Renderer; R9/B7-Disziplin und Deckel bleiben)"
    % PREVIEWER_VERSION)