#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Panel-Modul (previewer_panel.py)
============================================

STAND: Version 0.4.1 – aktuelle Fassung (Schrift-Wasserfall: eigener
frischer Pango-FontMap statt GTK-Standard, Größen bis 36 pt).

Das angedockte Vorschau-Panel samt allen Renderern: Bilder (inkl.
EXIF-Ausrichtung), Text, Markdown (gerendert), E-Mail-Dateien, E-Books
(EPUB, FictionBook, MOBI), Schriftarten (Wasserfall für TrueType und
OpenType), PDF, Audio (mit Player), Video, Ordner und Office-Dokumente.

Office (ODT/ODS/ODP, DOCX/XLSX/PPTX) wird, wenn LibreOffice und Poppler
vorhanden sind, scharf und in voller Panelbreite angezeigt: LibreOffice
konvertiert im Hintergrund einmalig nach PDF (Cache in ~/.cache/previewer),
Poppler rendert die Seiten (untereinander scrollbar). Während der Konvertierung ist die
eingebettete Miniaturansicht aus dem Dokument-ZIP mit einem Hinweis zu
sehen; das scharfe Ergebnis erscheint automatisch. Ohne LibreOffice gilt
weiterhin die ZIP-Miniaturansicht ohne Zusatzpakete.

Gehört zur vierteiligen Extension "Previewer" (siehe previewer.py).
"""

import os
import re
import sys
import base64
import ctypes
import ctypes.util
import email
import hashlib
import html
import shutil
import struct
import tempfile
import traceback
import zipfile
from email import policy
import xml.etree.ElementTree as ElementTree
from datetime import datetime

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    PANEL_WIDTH, PANEL_MIN_WIDTH,
    MAX_TEXT_BYTES, MAX_TEXT_LINES, MAX_IMAGE_HEIGHT,
    MAX_EBOOK_CHARS,
    TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
    query_file_info, human_size, format_seconds,
    content_type_description,
)

# --- Optionale Module (Fehlen ist kein Fehler, nur weniger Vorschau) ---

HAVE_GST = False
try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import Gst, GstPbutils
    Gst.init(None)
    HAVE_GST = True
except Exception:
    pass

HAVE_POPPLER = False
try:
    import cairo  # pycairo
    gi.require_version('Poppler', '0.18')
    from gi.repository import Poppler
    HAVE_POPPLER = True
except Exception:
    pass

# librsvg für SVG-Vorschau: GdkPixbuf bringt (seit gdk-pixbuf 2.42)
# keinen eigenen SVG-Loader mehr mit.
HAVE_RSVG = False
try:
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    HAVE_RSVG = True
except Exception:
    pass

# PangoCairo + pycairo, um den Schrift-Wasserfall mit einem eigenen,
# FRISCHEN Pango-FontMap vorzurendern – GTKs Standard-FontMap wird beim
# Start gebaut und überliest zur Laufzeit hinzugefügte Schriften.
HAVE_PANGOCAIRO = False
try:
    import cairo  # pycairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo
    HAVE_PANGOCAIRO = True
except Exception:
    pass

# LibreOffice für die scharfe Office-Vorschau (Hintergrundkonvertierung
# nach PDF). Fehlt es, bleibt die eingebettete Miniaturansicht.
SOFFICE = None
try:
    SOFFICE = shutil.which("soffice")
except Exception:
    SOFFICE = None

# Cache für LibreOffice-Konvertierungen: ~/.cache/previewer/<hash>.pdf


def office_cache_dir():
    """Cache-Ordner ~/.cache/previewer (wird bei Bedarf angelegt)."""
    d = os.path.join(GLib.get_user_cache_dir(), "previewer")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def office_cache_path(path):
    """Cache-Pfad des konvertierten PDFs (Key = Hash des absoluten Pfads)."""
    key = hashlib.sha1(
        os.path.abspath(path).encode("utf-8", "replace")).hexdigest()
    return os.path.join(office_cache_dir(), key + ".pdf")


# Office-Dokumente sind ZIP-Archive: eingebettete Miniaturansicht zeigen
# und/oder einen Textauszug. Ohne neue Pakete (nur Python-Bordmittel).
_OFFICE_EXTS = {
    ".odt", ".ods", ".odp", ".odg", ".odf",          # OpenDocument
    ".docx", ".xlsx", ".pptx",                        # MS Office (OOXML)
}
_OFFICE_THUMBS = (
    "Thumbnails/thumbnail.png",                       # ODF
    "docProps/thumbnail.jpeg",                       # OOXML
    "docProps/thumbnail.png",
)
_OFFICE_TEXT_ENTRIES = (
    "content.xml",                                   # ODF
    "word/document.xml",                              # OOXML (Text)
)
_OFFICE_MAX_TEXT_CHARS = 4000


def _extract_office_text(zf, names):
    """
    Textauszug aus einem Office-ZIP ziehen. ODF trägt den Inhalt in
    content.xml (text:p/text:h/text:span), OOXML in word/document.xml
    (w:p/w:t) – in beiden Fällen genügt das Sammeln der Textknoten,
    Absätze werden als Zeilenumbrüche übernommen.
    """
    entry = next((n for n in _OFFICE_TEXT_ENTRIES if n in names), None)
    if not entry:
        return ""
    try:
        root = ElementTree.fromstring(zf.read(entry))
    except Exception:
        return ""
    parts = []
    for elem in root.iter():
        tag = elem.tag if isinstance(elem.tag, str) else ""
        if tag.endswith("}p") or tag.endswith("}h"):
            parts.append("\n")
        elif tag.endswith("}tab"):
            parts.append(" ")
        if elem.text:
            parts.append(elem.text)
    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:_OFFICE_MAX_TEXT_CHARS]


# Zusätzliche Text-Dateiendungen, die GtkSourceView-artige Vorschau erhalten.
_TEXT_EXTRAS = {
    '.py', '.sh', '.bash', '.zsh', '.js', '.ts', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.csv', '.log', '.md', '.rst',
    '.css', '.html', '.xml', '.patch', '.diff', '.desktop', '.service',
    '.gitignore', '.nemo_action', '.pyw', '.lua', '.pl', '.rb', '.go',
    '.rs', '.c', '.h', '.cpp', '.hpp', '.java', '.sql', '.tex',
}

# PDF: alle Seiten bis zu dieser Obergrenze scrollbar untereinander
MAX_PDF_PAGES = 20


# --- Markdown -> Pango-Markup (Vorschau-Qualität, kein voller Parser) ---

def _pango_escape(s):
    """Text für Pango-Markup entschärfen (& < >)."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md_inline(t):
    """Inline-Formatierung: **fett**, *kursiv*, `code`, [Link](url)."""
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"__(.+?)__", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+?)`", r"<tt>\1</tt>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
               r"<span size='small'>[Bild: \1]</span>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               r"\1 <span size='small' foreground='grey'>\2</span>", t)
    return t


def _markdown_to_pango(text):
    """
    Markdown grob in Pango-Markup übersetzen: Überschriften, Fett/
    Kursiv, Inline- und Block-Code, Listen, Zitate, Trennlinien,
    Links. Bewusst kein vollständiger Parser – für die Vorschau im
    Panel reicht das, und es entstehen keine neuen Paket-Abhängigkeiten.
    """
    out = []
    in_code = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append("")
            continue
        if in_code:
            out.append("<tt>%s</tt>" % _pango_escape(line))
            continue
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            # Wichtig: "+" statt impliziter String-Verkettung –
            # "a" "b" * 12 ergibt sonst ("ab") * 12 (Rangfolge-Falle):
            # 12 ungeöffnete <span>-Tags machten das Markup komplett
            # ungültig, und jede Datei mit einer ----Linie (YAML-
            # Front-Matter!) blieb ohne Vorschau.
            out.append("<span size='small' foreground='grey'>"
                       + "\u2500" * 12 + "</span>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            depth = len(m.group(1))
            if depth == 1:
                tag = ("<span size='x-large' weight='bold'>",
                       "</span>")
            elif depth == 2:
                tag = ("<span size='large' weight='bold'>", "</span>")
            else:
                tag = "<span weight='bold'>", "</span>"
            out.append(tag[0] + _md_inline(_pango_escape(m.group(2)))
                       + tag[1])
            continue
        if stripped.startswith(">"):
            out.append("<i>%s</i>"
                       % _md_inline(_pango_escape(
                           stripped.lstrip("> ").strip())))
            continue
        m = re.match(r"^[-*+]\s+(.*)$", stripped)
        if m:
            out.append("\u2022 " + _md_inline(_pango_escape(m.group(1))))
            continue
        out.append(_md_inline(_pango_escape(line)))
    return "\n".join(out)


def _html_to_text(text):
    """HTML grob zu lesbarem Text bereinigen (für EML-Textkörper)."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# --- E-Books: EPUB, FictionBook, MOBI (nur Python-Bordmittel) ---------------


def _xml_local(tag):
    """XML-Tag ohne Namespace (OPF und FB2 verzichten nicht darauf)."""
    return tag.rsplit("}", 1)[-1]


def _pixbuf_from_bytes(data):
    """Pixbuf aus Rohbytes (E-Book-Cover); GdkPixbuf riecht das Format."""
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    return loader.get_pixbuf()


def _palmdoc_decompress(data):
    """
    PalmDoc-Entpackung (MOBI-Kompressionsverfahren 1). Bytes 0x80–0xBF
    sind Rückverweise; byteweise Kopieren behandelt Überlappungen richtig.
    """
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        i += 1
        if b == 0 or 9 <= b <= 0x7f:
            out.append(b)
        elif b <= 8:
            out.extend(data[i:i + b])
            i += b
        elif b <= 0xbf:
            if i < n:
                dist = (((b & 0x3f) << 8) | data[i]) + 1
                i += 1
                start = len(out) - dist
                if 0 <= start < len(out):
                    for _ in range((b >> 6) + 2):
                        out.append(out[start])
                        start += 1
        else:
            out.append(0x20)              # Leerzeichen + (Byte ^ 0x80)
            out.append(b ^ 0x80)
    return bytes(out)


def _epub_data(path):
    """
    EPUB öffnen: Metadaten (Titel, Autor, Sprache), Cover-Bytes und der
    Textanfang in Lesereihenfolge (Spine). Rückgabe (rows, cover, text).
    """
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        # OPF-Inhaltsdatei: steht in META-INF/container.xml
        opf_path = None
        try:
            container = zf.read("META-INF/container.xml").decode(
                "utf-8", "replace")
            m = re.search(r'full-path="([^"]+)"', container)
            if m:
                opf_path = m.group(1)
        except Exception:
            pass
        if not opf_path:
            for name in names:
                if name.lower().endswith(".opf"):
                    opf_path = name
                    break
        if not opf_path:
            raise ValueError("keine OPF-Inhaltsdatei gefunden")

        base = (opf_path.rsplit("/", 1)[0] + "/") if "/" in opf_path else ""
        root = ElementTree.fromstring(zf.read(opf_path))

        title = author = lang = None
        manifest = {}          # id -> (href, Medientyp)
        spine = []             # hrefs in Lesereihenfolge
        cover_id = None
        for el in root.iter():
            tag = _xml_local(el.tag)
            if tag == "title" and title is None:
                title = (el.text or "").strip()
            elif tag == "creator" and author is None:
                author = (el.text or "").strip()
            elif tag == "language" and lang is None:
                lang = (el.text or "").strip()
            elif tag == "manifest":
                for item in el:
                    if _xml_local(item.tag) != "item":
                        continue
                    manifest[item.get("id")] = (
                        item.get("href"), item.get("media-type"))
                    if "cover-image" in (item.get("properties") or ""):
                        cover_id = item.get("id")
            elif tag == "spine":
                for itemref in el:
                    if _xml_local(itemref.tag) == "itemref":
                        spine.append(itemref.get("idref"))
            elif (tag == "meta" and el.get("name") == "cover"
                    and cover_id is None):
                cover_id = el.get("content")

        # Cover-Bilddaten (Manifest, sonst Heuristik: Dateiname enthält
        # "cover" und sieht nach Bild aus)
        cover = None
        if cover_id in manifest:
            try:
                cover = zf.read(base + manifest[cover_id][0])
            except KeyError:
                cover = None
        if not cover:
            for name in names:
                low = name.rsplit("/", 1)[-1].lower()
                if "cover" in low and low.endswith(
                        (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                    try:
                        cover = zf.read(name)
                        break
                    except KeyError:
                        pass

        # Textanfang: Spine-Dokumente in Lesereihenfolge zu Text bereinigen
        parts = []
        total = 0
        for idref in spine:
            if total >= MAX_EBOOK_CHARS:
                break
            href, mtype = manifest.get(idref, (None, None))
            if not href:
                continue
            if mtype and "html" not in mtype and "xml" not in mtype:
                continue
            try:
                raw = zf.read(base + href)
            except KeyError:
                continue
            chunk = _html_to_text(raw.decode("utf-8", "replace"))
            if chunk.strip():
                parts.append(chunk)
                total += len(chunk)
        text = "\n\n".join(parts)[:MAX_EBOOK_CHARS]

    rows = [(k, v) for k, v in (("Titel", title), ("Autor", author),
                                ("Sprache", lang)) if v]
    return rows, cover, text


def _fb2_data(path):
    """
    FictionBook 2 (.fb2): Titel, Autor, Cover (base64-binär) und
    Textanfang des ersten Körpers (Fußnoten-Körper werden ignoriert).
    """
    root = ElementTree.parse(path).getroot()

    title = author = None
    cover_ref = None
    body = None
    for el in root.iter():
        tag = _xml_local(el.tag)
        if tag == "book-title" and title is None:
            title = (el.text or "").strip()
        elif tag == "author" and author is None:
            first = last = None
            for child in el:
                ct = _xml_local(child.tag)
                if ct == "first-name":
                    first = (child.text or "").strip()
                elif ct == "last-name":
                    last = (child.text or "").strip()
            author = " ".join(x for x in (first, last) if x)
        elif tag == "coverpage" and cover_ref is None:
            for child in el:
                if _xml_local(child.tag) == "image":
                    cover_ref = (child.get("l:href") or
                                 child.get("href") or "").lstrip("#")
        elif tag == "body" and body is None:
            body = el

    lines = []
    total = 0
    if body is not None:
        for el in body.iter():
            tag = _xml_local(el.tag)
            if tag in ("p", "v", "subtitle", "text-author"):
                txt = "".join(el.itertext()).strip()
                if txt:
                    lines.append(txt)
                    total += len(txt) + 1
            elif tag == "title":
                lines.append("")
                txt = "".join(el.itertext()).strip()
                if txt:
                    lines.append(txt)
                    total += len(txt) + 1
            elif tag == "empty-line":
                lines.append("")
            if total >= MAX_EBOOK_CHARS:
                break
    text = "\n".join(lines)[:MAX_EBOOK_CHARS]

    # Cover: eingebettete <binary>-Ressource (base64)
    cover = None
    if cover_ref:
        for el in root.iter():
            if (_xml_local(el.tag) == "binary"
                    and el.get("id") == cover_ref):
                b64 = re.sub(r"\s+", "", "".join(el.itertext()))
                try:
                    cover = base64.b64decode(b64)
                except Exception:
                    cover = None
                break

    rows = [(k, v) for k, v in (("Titel", title), ("Autor", author)) if v]
    return rows, cover, text


def _mobi_data(path):
    """
    MOBI/PRC (Palm-Container): Titel, Autor (EXTH) und Textanfang.
    Unterstützt Kompressionsverfahren 1 (PalmDoc) und 2 (unkomprimiert);
    HUFF/CDIC (einige neuere AZW) wird abgelehnt – KF8-Dateien (AZW3)
    liefern bestenfalls HTML-Reste, sind aber lesbar, wenn PalmDoc
    komprimiert ist.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 88 or data[60:68] not in (b"BOOKMOBI", b"TEXtREAd"):
        raise ValueError("kein MOBI-Container")

    title = data[0:32].split(b"\x00")[0].decode("utf-8", "replace").strip()
    num_rec = struct.unpack(">H", data[76:78])[0]
    # Datensatz-Tabelle ab Offset 78: je 8 Bytes, Offset in den ersten 3
    rec_offs = []
    for i in range(num_rec):
        p = 78 + 8 * i
        if p + 3 > len(data):
            break
        rec_offs.append(int.from_bytes(data[p:p + 3], "big"))
    if not rec_offs:
        raise ValueError("keine Datensätze")
    recs = []
    for i, off in enumerate(rec_offs):
        end = rec_offs[i + 1] if i + 1 < len(rec_offs) else len(data)
        if off < end <= len(data):
            recs.append(data[off:end])

    compression = 1
    encoding = "cp1252"
    first_non_book = len(recs)
    author = None
    r0 = recs[0] if recs else b""
    if len(r0) >= 24 and r0[16:20] == b"MOBI":
        compression = struct.unpack(">H", r0[0:2])[0]
        if len(r0) >= 32:
            encoding = ("utf-8"
                        if struct.unpack(">I", r0[28:32])[0] == 65001
                        else "cp1252")
        if len(r0) >= 84:
            first_non_book = struct.unpack(">I", r0[80:84])[0]
        first_non_book = max(1, min(first_non_book, len(recs)))
        # EXTH-Header: Eintrag Typ 100 = Autor
        pos = r0.find(b"EXTH", 24)
        if pos >= 0 and len(r0) >= pos + 12:
            count = struct.unpack(">I", r0[pos + 8:pos + 12])[0]
            q = pos + 12
            for _ in range(count):
                if q + 8 > len(r0):
                    break
                etype, elen = struct.unpack(">II", r0[q:q + 8])
                if elen < 8 or q + elen > len(r0):
                    break
                if etype == 100:
                    author = r0[q + 8:q + elen].decode(encoding, "replace")
                q += elen

    if compression not in (1, 2):
        raise ValueError("Kompressionsverfahren %d nicht unterstützt "
                         "(HUFF/CDIC)" % compression)

    parts = []
    total = 0
    for rec in recs[1:first_non_book]:
        if compression == 1:
            rec = _palmdoc_decompress(rec)
        parts.append(rec.decode(encoding, "replace"))
        total += len(parts[-1])
        if total >= MAX_EBOOK_CHARS * 2:
            break
    text = _html_to_text(" ".join(parts))[:MAX_EBOOK_CHARS]

    rows = [(k, v) for k, v in (("Titel", title), ("Autor", author)) if v]
    return rows, None, text

# --- Schriftarten: Wasserfall für TrueType/OpenType (Bordmittel) ------------

_FONT_SIZES = (8, 11, 14, 18, 24, 36)
_FONT_SAMPLE_TEXT = ("Zwölf Boxkämpfer jagen Viktor quer über den "
                     "großen Sylter Deich")
# Prozess-Zustand (kein global-Schlüsselwort, siehe Projekt-Konvention):
# temporärer Ordner für die Fontconfig-Übernahme + bereits übernommene Pfade
_FONT_STATE = {"tmpdir": None, "added": set()}


def _font_info(path):
    """
    Familie und Stil aus der Namens-Tabelle einer TrueType-/OpenType-
    Datei lesen (sfnt-Kopf, name-Tabelle – reine Bytes-Arbeit).
    Rückgabe (Format-Text, Familie, Stil).
    """
    with open(path, "rb") as fh:
        data = fh.read(4 * 1024 * 1024)
    if len(data) < 12:
        raise ValueError("Datei zu klein")
    tag = data[0:4]
    offset = 0
    fmt = "TrueType"
    if tag == b"ttcf":
        if len(data) < 16:
            raise ValueError("Collection ohne Kopf")
        offset = int.from_bytes(data[12:16], "big")
        if offset + 12 > len(data):
            raise ValueError("Collection-Offset kaputt")
        tag = data[offset:offset + 4]
        fmt = "TrueType-Collection"
    if tag == b"OTTO":
        fmt = ("OpenType (CFF)" if offset == 0
               else "OpenType-Collection (CFF)")
    elif tag not in (b"true", b"\x00\x01\x00\x00") and offset == 0:
        raise ValueError("keine TrueType-/OpenType-Datei")

    num_tables = int.from_bytes(data[offset + 4:offset + 6], "big")
    name_off = name_len = 0
    for i in range(num_tables):
        p = offset + 12 + 16 * i
        if p + 16 > len(data):
            break
        ttag, _cksum, toff, tlen = struct.unpack(">4sIII", data[p:p + 16])
        if ttag == b"name":
            name_off, name_len = toff, tlen
            break
    if not name_off:
        raise ValueError("Namens-Tabelle fehlt")
    end = min(len(data), name_off + name_len)
    count = int.from_bytes(data[name_off + 2:name_off + 4], "big")
    stroff = int.from_bytes(data[name_off + 4:name_off + 6], "big")
    recs = {}
    for i in range(count):
        p = name_off + 6 + 12 * i
        if p + 12 > end:
            break
        plat, _enc, _lang, nid, ln, off2 = struct.unpack(
            ">6H", data[p:p + 12])
        s = name_off + stroff + off2
        if s + ln > end:
            continue
        raw = data[s:s + ln]
        try:
            if plat in (0, 3):            # Unicode bzw. Windows: UTF-16BE
                text = raw.decode("utf-16-be", "replace")
            else:                          # Mac & Co.: grob Latin-1
                text = raw.decode("latin-1", "replace")
        except Exception:
            continue
        text = text.strip("\x00 ").strip()
        if text:
            recs.setdefault(nid, text)
    family = recs.get(1) or recs.get(16) or recs.get(4)
    style = recs.get(2) or recs.get(17)
    if not family:
        raise ValueError("kein Familienname in der Datei")
    return fmt, family, style or "Regular"


def _fc_add_font_file(path):
    """
    Schriftdatei für DIESEN Prozess in Fontconfig aufnehmen – ohne sie
    systemweit zu installieren: Kopie in einen temporären Ordner, dann
    FcConfigAppFontAddDir (libfontconfig via ctypes). Pango liest die
    Familie danach ganz normal über Fontconfig.
    """
    state = _FONT_STATE
    if path in state["added"]:
        return True
    try:
        if state["tmpdir"] is None:
            state["tmpdir"] = tempfile.mkdtemp(prefix="previewer-font-")
        dest = os.path.join(state["tmpdir"], os.path.basename(path))
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
        lib = ctypes.CDLL(ctypes.util.find_library("fontconfig")
                          or "libfontconfig.so.1")
        res = lib.FcConfigAppFontAddDir(
            None, state["tmpdir"].encode("utf-8"))
        if res:
            state["added"].add(path)
            return True
        return False
    except Exception:
        return False


def _font_known(font_map, family):
    """
    Liegt die Familie im übergebenen (frischen) FontMap? Die Prüfung
    geht über einen NEUEN FontMap, denn der Standard-FontMap von GTK
    kennt nur den Stand beim Start.
    """
    try:
        low = family.lower()
        for fam in font_map.list_families():
            if (fam.get_name() or "").lower() == low:
                return True
        return False
    except Exception:
        return True      # Prüfung unmöglich – nicht blocken

# ================================ Panel ====================================

class PreviewPanel(Gtk.Box):
    """Das angedockte Vorschau-Panel (rechte Hälfte des Gtk.Paned)."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(PANEL_MIN_WIDTH, -1)

        self._window = window
        self._path = None
        self._names = []
        self._playbin = None
        self._progress_timer = 0
        self._render_width = 0
        # Skalierbare Vorschau: Quelle in voller Auflösung behalten und
        # nur die angezeigte Pixbuf bei Breitenänderung neu skalieren.
        self._scale_img = None
        self._scale_src = None
        self._scale_max_h = 0
        self._scale_upscale = False
        self._scale_max_up = 1.0
        self._scale_keep_h = False
        self._scale_last_w = 0
        # Hintergrund-Konvertierung für Office-Dokumente (LibreOffice → PDF)
        self._office_job = None
        self._office_failed = set()
        # Mehrseitige PDF-Vorschau: Quell-Pixbufs je Seite + Anzeige-Images
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_last_w = 0

        # --- Kopfzeile ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_border_width(6)

        self._icon_image = Gtk.Image.new_from_icon_name(
            "text-x-generic", Gtk.IconSize.DIALOG)
        header.pack_start(self._icon_image, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._name_label = Gtk.Label(label="Keine Datei ausgewählt")
        self._name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.set_hexpand(True)
        self._name_label.get_style_context().add_class("dim-label")
        self._name_label.set_line_wrap(False)
        title_box.pack_start(self._name_label, True, True, 0)

        self._meta_label = Gtk.Label(label="")
        self._meta_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._meta_label.set_halign(Gtk.Align.START)
        self._meta_label.get_style_context().add_class("dim-label")
        self._meta_label.set_hexpand(True)
        title_box.pack_start(self._meta_label, True, True, 0)
        header.pack_start(title_box, True, True, 0)

        # Öffnen- und Ausblenden-Knöpfe
        btn_open = Gtk.Button.new_from_icon_name(
            "document-open-symbolic", Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text("Mit Standardanwendung öffnen")
        btn_open.set_relief(Gtk.ReliefStyle.NONE)
        btn_open.connect("clicked", self._on_open_clicked)
        header.pack_end(btn_open, False, False, 0)

        btn_hide = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.BUTTON)
        btn_hide.set_tooltip_text("Panel ausblenden (Strg+Alt+P)")
        btn_hide.set_relief(Gtk.ReliefStyle.NONE)
        btn_hide.connect("clicked", lambda *a: self.hide())
        header.pack_end(btn_hide, False, False, 0)

        self.pack_start(header, False, False, 0)
        self._separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self._separator, False, False, 0)

        # --- Vorschau-Bereich ---
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._content.set_border_width(8)
        self.pack_start(self._content, True, True, 0)
        # Vorschau passt ihre Größe an, wenn die Panelbreite (Gtk.Paned-
        # Trenner) verändert wird: entprelltes Neu-Rendern bei Breiten-
        # änderung.
        self._content.connect("size-allocate",
                              self._on_content_size_allocate)

        self._show_placeholder()

        # Tastenkürzel zum Wieder-Einblenden
        try:
            accel = Gtk.AccelGroup()
            window.add_accel_group(accel)
            accel.connect(TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
                          Gtk.AccelFlags.VISIBLE, self._on_toggle_accel)
        except Exception:
            pass

    # ------------------------------ Selektion ------------------------------

    def set_selection(self, names, dir_path):
        """Auswahl setzen und Vorschau neu rendern (names = Dateinamen)."""
        # Audio-Player immer sauber stoppen, wenn sich etwas ändert
        self._stop_playback()

        if not names:
            self._path = None
            self._names = []
            self._show_placeholder()
            return

        self._names = list(names)
        first = names[0]
        if dir_path:
            self._path = os.path.join(dir_path, first)
        else:
            self._path = first
        self._render()

    # ------------------------------ Rendering ------------------------------

    def _clear_content(self):
        for child in list(self._content.get_children()):
            self._content.remove(child)
        # Skalier-Quelle freigeben (Speicher der vollen Auflösung)
        self._scale_img = None
        self._scale_src = None
        self._scale_last_w = 0
        # ebenso die Quell-Pixbufs der PDF-Seiten
        self._pdf_src = None
        self._pdf_imgs = None
        self._pdf_last_w = 0

    def _show_placeholder(self):
        self._name_label.set_text("Keine Datei ausgewählt")
        self._meta_label.set_text("")
        self._icon_image.set_from_icon_name("edit-find-symbolic",
                                           Gtk.IconSize.DIALOG)
        self._clear_content()
        # Nemo-Logo, mittig (horizontal und vertikal) in der Spalte
        logo = Gtk.Image()
        logo_name = "folder"
        try:
            theme = Gtk.IconTheme.get_default()
            if theme.has_icon("nemo"):
                logo_name = "nemo"
        except Exception:
            pass
        try:
            logo.set_from_icon_name(logo_name, Gtk.IconSize.DIALOG)
            logo.set_pixel_size(96)
        except Exception:
            logo.set_from_icon_name("folder", Gtk.IconSize.DIALOG)
        lbl = Gtk.Label(label="Wähle eine Datei aus,\num eine Vorschau zu sehen.")
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.pack_start(logo, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        self._content.pack_start(box, True, True, 0)
        self._content.show_all()

    def _render(self):
        """Vorschau für self._path aufbauen. Nie werfen – immer Fallback."""
        try:
            self._render_inner()
        except Exception:
            dbg("Fehler beim Rendern von %r:" % self._path)
            traceback.print_exc()
            try:
                self._render_generic()
            except Exception:
                pass
        self._content.show_all()

    def _render_inner(self):
        path = self._path
        self._clear_content()

        if len(self._names) > 1:
            extra = Gtk.Label(label="… und %d weitere ausgewählt" %
                              (len(self._names) - 1))
            extra.get_style_context().add_class("dim-label")
            extra.set_halign(Gtk.Align.START)
            self._content.pack_start(extra, False, False, 0)

        if not path or not os.path.exists(path):
            self._name_label.set_text(
                self._names[0] if self._names else "?")
            self._meta_label.set_text("(Datei nicht gefunden)")
            self._icon_image.set_from_icon_name(
                "dialog-warning-symbolic", Gtk.IconSize.DIALOG)
            return

        mime, size, mtime = query_file_info(path)
        is_dir = os.path.isdir(path)

        # Kopfzeile füllen
        self._name_label.set_text(os.path.basename(path))
        self._name_label.set_tooltip_text(path)
        meta_parts = []
        if mime:
            meta_parts.append(content_type_description(mime))
        if size >= 0:
            meta_parts.append(human_size(size))
        if mtime > 0:
            meta_parts.append(
                datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M"))
        self._meta_label.set_text(" · ".join(meta_parts))
        self._set_icon(mime, is_dir)

        uri = GLib.filename_to_uri(path)
        lower = path.lower()

        # --- nach Typ rendern ---
        if is_dir:
            self._render_folder(path)
        elif mime == "image/svg+xml" or lower.endswith(".svg"):
            self._render_svg(path)
        elif mime.startswith("image/") or mime == "application/x-xpixmap":
            self._render_image(path)
        elif mime == "application/pdf" or lower.endswith(".pdf"):
            if HAVE_POPPLER:
                self._render_pdf(path)
            else:
                self._hint("PDF-Vorschau nicht verfügbar – "
                           "Paket gir1.2-poppler-0.18 installieren.")
                self._render_generic()
        elif mime.startswith("audio/") or lower.endswith((".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".wma")):
            if HAVE_GST:
                self._render_audio(path, uri)
            else:
                self._hint("Audio-Vorschau nicht verfügbar – "
                           "Paket gir1.2-gst-plugins-base-1.0 installieren.")
                self._render_generic()
        elif mime.startswith("video/"):
            if HAVE_GST:
                self._render_video(path, uri)
            else:
                self._render_generic()
        elif lower.endswith((".md", ".markdown")):
            self._render_markdown(path)
        elif lower.endswith(".eml") or mime == "message/rfc822":
            self._render_eml(path)
        elif mime == "application/epub+zip" or lower.endswith(".epub"):
            self._render_epub(path)
        elif (mime in ("application/x-fictionbook+xml",
                       "application/x-fictionbook")
              or lower.endswith(".fb2")):
            self._render_fb2(path)
        elif (mime == "application/x-mobipocket-ebook"
              or lower.endswith((".mobi", ".prc", ".azw", ".azw3"))):
            self._render_mobi(path)
        elif (mime in ("font/ttf", "font/otf", "font/collection",
                       "application/x-font-ttf", "application/x-font-otf",
                       "application/vnd.ms-opentype")
              or lower.endswith((".ttf", ".otf", ".ttc"))):
            self._render_font(path)
        elif mime.startswith("text/") or os.path.splitext(lower)[1] in _TEXT_EXTRAS:
            self._render_text(path)
        elif os.path.splitext(lower)[1] in _OFFICE_EXTS:
            self._render_office(path)
        else:
            self._render_generic()

    # --- einzelne Renderer --------------------------------------------------

    def _set_icon(self, mime, is_dir):
        try:
            if is_dir:
                name = "folder"
            else:
                icon = Gio.content_type_get_icon(mime or "text-x-generic")
                names = icon.get_names()
                name = names[0] if names else "text-x-generic"
            self._icon_image.set_from_icon_name(name, Gtk.IconSize.DIALOG)
        except Exception:
            self._icon_image.set_from_icon_name(
                "text-x-generic", Gtk.IconSize.DIALOG)

    def _on_content_size_allocate(self, widget, allocation):
        """
        Breitenänderung des Vorschau-Bereichs beobachten (der Nutzer zieht
        den Gtk.Paned-Trenner). Es wird NICHT neu gerendert – stattdessen
        wird nur die angezeigte Pixbuf der skalierbaren Vorschau sofort
        an die neue Breite angepasst (billig, ohne Neu-Decodieren).
        """
        try:
            width = allocation.width
            if abs(width - self._render_width) < 12:
                return
            self._render_width = width
            self._apply_scale()
            self._apply_pdf_scale()
        except Exception:
            pass

    def _scaled_image(self, src, max_h, upscale=False, keep_height=False,
                      max_upscale=1.0):
        """
        Gtk.Image, das mit der Panelbreite lebt. Die Quelle (src) bleibt
        in voller Auflösung im Speicher; die angezeigte Pixbuf wird bei
        Breitenänderungen live neu skaliert. Das Bild liegt in einem
        ScrolledWindow, damit seine Minimalbreite das Gtk.Paned beim
        Verkleinern nicht blockiert (das war die Ruckel-Ursache).
        upscale=True lässt kleine Quellen (z.B. Office-Miniaturansichten)
        mit der Panelbreite mitwachsen – begrenzt durch max_upscale,
        damit kleine Miniaturansichten nicht zu unleserlichem Brei
        hochgeblasen werden.
        keep_height=True nur bei nicht-expandiertem Packen (Office,
        Cover, Video-Frame): hält die Containerhöhe auf Bildhöhe, damit
        das Bild unter Platzdruck nicht unten abgeschnitten wird. Bei
        expandiertem Packen (Bild, PDF) darf KEINE Mindesthöhe gesetzt
        werden – hochkantige Bilder würden sonst dem Fenster ihre Höhe
        aufzwingen.
        Gibt den fertigen Container (Gtk.ScrolledWindow) zurück.
        """
        self._scale_src = src
        self._scale_max_h = max_h
        self._scale_upscale = upscale
        self._scale_max_up = max_upscale
        self._scale_keep_h = keep_height
        self._scale_last_w = 0
        img = Gtk.Image()
        # Horizontal mittig: kleine Vorschauen (Cover, Office-Miniatur)
        # kleben nicht am linken Rand, sondern sitzen zentriert.
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.START)
        self._scale_img = img
        scroll = Gtk.ScrolledWindow()
        self._scale_scroll = scroll
        # AUTOMATIC in beide Richtungen: bricht die Weitergabe der
        # Kind-Minimalbreite nach oben ab, das Pane bleibt frei ziehbar.
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
        self._apply_scale()
        return scroll

    def _apply_scale(self):
        """Angezeigte Pixbuf der Vorschau an die aktuelle Breite anpassen."""
        img = self._scale_img
        src = self._scale_src
        if img is None or src is None:
            return
        try:
            sw, sh = src.get_width(), src.get_height()
            if sw <= 0 or sh <= 0:
                return
            target = self._preview_width()
            f = float(target) / sw
            if f > 1.0:
                if self._scale_upscale:
                    # Hochskalieren, aber begrenzt: kleine Quellen
                    # (Office-Miniaturansichten) werden sonst unleserlich.
                    f = min(f, self._scale_max_up)
                else:
                    f = 1.0          # kleine Bilder nicht unscharf aufblasen
            if f * sh > self._scale_max_h:
                f = float(self._scale_max_h) / sh
            w = max(1, int(sw * f))
            h = max(1, int(sh * f))
            if abs(w - self._scale_last_w) < 4:
                return
            self._scale_last_w = w
            # Beim Hochskalieren qualitativ besser interpolieren
            interp = (GdkPixbuf.InterpType.HYPER if f > 1.0
                      else GdkPixbuf.InterpType.BILINEAR)
            img.set_from_pixbuf(src.scale_simple(w, h, interp))
            # Mindesthöhe nur bei keep_height: hält den Container auf
            # Bildhöhe, wenn er nicht expandiert gepackt ist (sonst
            # würde das Bild unten abgeschnitten). Zusätzlich die
            # Scrollposition zurücksetzen – nach einem Aufziehen-/
            # Zurückschieben-Zyklus stünde das Bild sonst versetzt.
            try:
                if self._scale_keep_h:
                    self._scale_scroll.set_min_content_height(h)
                    self._scale_scroll.get_vadjustment().set_value(0)
            except Exception:
                pass
        except Exception:
            pass

    def _preview_width(self):
        """
        Breite, die Vorschau-Objekte zur Verfügung haben. Live aus der
        aktuellen Fläche des Inhaltsbereichs (get_allocated_width),
        damit die Vorschau mit der Panelbreite skalieren kann; die
        Startbreite dient nur als Fallback, solange noch keine
        Größenzuweisung erfolgt ist.
        """
        try:
            w = self._content.get_allocated_width()
            if w > 40:
                # Innenabstand (Rahmen 8 px je Seite) abziehen
                return max(PANEL_MIN_WIDTH - 20, w - 16)
        except Exception:
            pass
        return PANEL_WIDTH - 40

    def _render_svg(self, path):
        """SVG-Vorschau via librsvg: GdkPixbuf kann SVG nicht laden."""
        if not HAVE_RSVG:
            self._hint("SVG-Vorschau nicht verfügbar – "
                       "Paket gir1.2-rsvg installieren.")
            self._render_generic()
            return
        try:
            handle = Rsvg.Handle.new_from_file(path)
            pb = handle.get_pixbuf()
        except Exception as e:
            self._hint("Konnte SVG nicht lesen: %s" % e)
            self._render_generic()
            return
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False)
        self._content.pack_start(scroll, True, True, 0)
        try:
            info = Gtk.Label(label="%d × %d px"
                             % (pb.get_width(), pb.get_height()))
            info.get_style_context().add_class("dim-label")
            info.set_halign(Gtk.Align.START)
            self._content.pack_start(info, False, False, 0)
        except Exception:
            pass

    def _render_image(self, path):
        # Quelle in voller Auflösung laden (Riesenbilder werden auf eine
        # sinnvolle Deckelung verkleinert); die ANZEIGE regelt die Live-
        # Skalierung über die Panelbreite.
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, 4096, 4096, True)
            except Exception as exc:
                self._hint("Konnte Bild nicht laden: %s" % exc)
                self._render_generic()
                return
        # EXIF-Ausrichtung anwenden: Fotos, die die Drehung nur im
        # Orientation-Tag tragen (typisch bei Smartphone-Kameras),
        # würden sonst quer oder auf dem Kopf liegen.
        try:
            pb = pb.apply_embedded_orientation()
        except Exception:
            pass
        if pb.get_width() > 4096 or pb.get_height() > MAX_IMAGE_HEIGHT:
            pb = self._scale_pixbuf(pb, 4096, MAX_IMAGE_HEIGHT)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False)
        self._content.pack_start(scroll, True, True, 0)
        try:
            # Maße des orientierten Bildes (die ANZEIGE ist der Maßstab,
            # nicht die rohen Pixeldaten der Datei)
            info = Gtk.Label(label="%d × %d px"
                             % (pb.get_width(), pb.get_height()))
            info.get_style_context().add_class("dim-label")
            info.set_halign(Gtk.Align.START)
            self._content.pack_start(info, False, False, 0)
        except Exception:
            pass

    def _render_text(self, path):
        try:
            with open(path, 'rb') as fh:
                data = fh.read(MAX_TEXT_BYTES)
            text = data.decode('utf-8', 'replace')
            truncated = False
            if len(data) == MAX_TEXT_BYTES:
                truncated = True
            lines = text.split("\n")
            if len(lines) > MAX_TEXT_LINES:
                lines = lines[:MAX_TEXT_LINES]
                truncated = True
            text = "\n".join(lines)
        except Exception as e:
            self._hint("Konnte Datei nicht lesen: %s" % e)
            return

        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.override_font(Pango.FontDescription("Monospace 9"))
        # Innenabstand, damit der Text nicht am Rand klebt
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)
        if truncated:
            self._hint("Vorschau gekürzt (lange Datei).")

    def _render_markdown(self, path):
        """
        Markdown mit sichtbaren Formatierungen: Überschriften, Fett/
        Kursiv, Code, Listen, Zitate und Links werden über Pango-Markup
        dargestellt (kein Webview, keine neuen Pakete). Schlägt die
        Markup-Erzeugung ausnahmsweise fehl, erscheint der Rohtext.
        """
        try:
            with open(path, "rb") as fh:
                data = fh.read(MAX_TEXT_BYTES)
            text = data.decode("utf-8", "replace")
            truncated = False
            if len(data) == MAX_TEXT_BYTES:
                truncated = True
            lines = text.split("\n")
            if len(lines) > MAX_TEXT_LINES:
                lines = lines[:MAX_TEXT_LINES]
                text = "\n".join(lines)
                truncated = True
        except Exception as e:
            self._hint("Konnte Datei nicht lesen: %s" % e)
            return
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.override_font(Pango.FontDescription("9"))
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        markup = _markdown_to_pango(text)
        valid = True
        try:
            # Markup VOR dem Einfügen validieren: GTK bricht bei
            # ungültigem Markup STILL ab (keine Ausnahme!) und die
            # Vorschau bliebe leer. Jetzt: prüfen und im Zweifel
            # den Rohtext zeigen statt gar nichts.
            Pango.parse_markup(markup, -1, "\x00")
        except Exception as exc:
            valid = False
            dbg("Markdown-Markup ungültig (%s) – zeige Rohtext" % exc)
        buf = view.get_buffer()
        if valid:
            buf.insert_markup(buf.get_end_iter(), markup, -1)
        else:
            buf.set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)
        if truncated:
            self._hint("Vorschau gekürzt (lange Datei).")

    def _render_eml(self, path):
        """
        EML-Dateien (RFC 822): Kopfzeilen (Betreff, Von, An, Cc, Datum)
        als Tabelle, darunter der Textkörper. Bevorzugt text/plain;
        fehlt er, wird der HTML-Teil zu lesbarem Text bereinigt. Alles
        mit Python-Bordmitteln (email-Modul).
        """
        try:
            with open(path, "rb") as fh:
                msg = email.message_from_binary_file(
                    fh, policy=policy.default)
        except Exception as e:
            self._hint("E-Mail konnte nicht geöffnet werden: %s" % e)
            return

        rows = []
        for key, label in (("subject", "Betreff"), ("from", "Von"),
                           ("to", "An"), ("cc", "Cc"),
                           ("date", "Datum")):
            try:
                val = msg.get(key)
            except Exception:
                val = None
            if val:
                rows.append((label, str(val)[:160]))
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
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
        self._content.pack_start(grid, False, False, 0)

        body = self._eml_body(msg)
        if not body.strip():
            self._hint("Kein lesbarer Textkörper gefunden – Datei "
                       "über den Öffnen-Knopf betrachten.")
            return
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.override_font(Pango.FontDescription("9"))
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        view.get_buffer().set_text(body)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)

    def _eml_body(self, msg):
        """Textkörper einer E-Mail: text/plain bevorzugt, sonst HTML."""
        text = ""
        part = None
        try:
            part = msg.get_body(preferencelist=("plain", "html"))
        except Exception:
            part = None
        if part is not None:
            try:
                text = part.get_content()
            except Exception:
                try:
                    raw = part.get_payload(decode=True)
                    if raw:
                        text = raw.decode(
                            part.get_content_charset() or "utf-8",
                            "replace")
                except Exception:
                    text = ""
            try:
                if "html" in (part.get_content_type() or "").lower():
                    text = _html_to_text(text)
            except Exception:
                pass
        if not text.strip():
            # Fallback: erster text/plain-Teil, falls get_body versagte.
            try:
                for p in msg.walk():
                    if p.get_content_type() == "text/plain":
                        raw = p.get_payload(decode=True)
                        if raw:
                            text = raw.decode("utf-8", "replace")
                            break
            except Exception:
                text = ""
        return text[:MAX_TEXT_BYTES]

    # --- E-Books: EPUB, FictionBook, MOBI -----------------------------------

    def _meta_grid(self, rows):
        """Schlüssel-Wert-Tabelle (wie beim EML-Kopf) für E-Book-Metadaten."""
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
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
        self._content.pack_start(grid, False, False, 0)

    def _render_ebook(self, path, loader, fmt):
        """
        Gemeinsamer E-Book-Ablauf: Metadaten-Kopf, Cover-Bild (lebt mit
        der Panelbreite) und der Textanfang in einem scrollbaren TextView.
        Lässt sich das Buch nicht lesen (kaputt oder HUFF-Kompression),
        erscheint ein Hinweis plus generische Vorschau.
        """
        try:
            rows, cover, text = loader(path)
        except Exception as e:
            dbg("E-Book konnte nicht gelesen werden (%s): %s" % (path, e))
            self._hint("E-Book konnte nicht gelesen werden: %s" % e)
            self._render_generic()
            return
        if not rows:
            rows = [("Format", fmt)]
        self._meta_grid(rows)
        if cover:
            try:
                pb = _pixbuf_from_bytes(cover)
                scroll = self._scaled_image(
                    pb, MAX_IMAGE_HEIGHT, upscale=True, keep_height=True,
                    max_upscale=2.0)
                self._content.pack_start(scroll, False, False, 0)
            except Exception as exc:
                dbg("E-Book-Cover nicht darstellbar: %s" % exc)
        if not text.strip():
            self._hint("Kein lesbarer Text gefunden – Datei über den "
                       "Öffnen-Knopf betrachten.")
            return
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.override_font(Pango.FontDescription("9"))
        view.set_left_margin(10)
        view.set_right_margin(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)

    def _render_epub(self, path):
        """EPUB-Vorschau (Titel, Autor, Cover, Textanfang)."""
        self._render_ebook(path, _epub_data, "EPUB")

    def _render_fb2(self, path):
        """FictionBook-2-Vorschau (Titel, Autor, Cover, Textanfang)."""
        self._render_ebook(path, _fb2_data, "FictionBook")

    def _render_mobi(self, path):
        """MOBI/PRC/AZW-Vorschau (Titel, Autor, Textanfang)."""
        self._render_ebook(path, _mobi_data, "MOBI")

    def _render_font(self, path):
        """
        Schriftarten-Wasserfall (TrueType, OpenType, Collections): die
        Datei wird nur für diesen Prozess in Fontconfig aufgenommen
        (nichts wird installiert). Der Wasserfall wird mit einem
        FRISCHEN Pango-FontMap in eine Pixbuf vorgerendert – GTKs
        Standard-FontMap wird beim Start gebaut und überliest zur
        Laufzeit hinzugefügte Schriften (Labels würden still die
        Ersatzschrift zeigen). Das fertige Bild nutzt die übliche
        Live-Skalierung mit der Panelbreite.
        """
        try:
            fmt, family, style = _font_info(path)
        except Exception as e:
            dbg("Schrift konnte nicht gelesen werden (%s): %s" % (path, e))
            self._hint("Konnte Schrift nicht lesen: %s" % e)
            self._render_generic()
            return
        if not HAVE_PANGOCAIRO:
            self._hint("Schriftvorschau nicht verfügbar – Pakete "
                       "python3-cairo und gir1.2-pango installieren.")
            self._render_generic()
            return
        self._meta_grid([("Format", fmt), ("Familie", family),
                         ("Stil", style)])
        if not _fc_add_font_file(path):
            dbg("Schrift konnte Fontconfig nicht hinzugefügt werden: %s"
                % path)

        # Frischer FontMap + eigener Kontext: sieht die neue Familie.
        try:
            fctx = PangoCairo.FontMap.new().create_context()
        except Exception as e:
            dbg("Pango-Kontext fehlgeschlagen: %s" % e)
            self._hint("Schriftvorschau nicht verfügbar.")
            self._render_generic()
            return
        if not _font_known(fctx.get_font_map(), family):
            dbg("Pango kennt die Familie nicht: %s" % family)
            self._hint("Schrift konnte nicht eingebunden werden – der "
                       "Wasserfall zeigt die Ersatzschrift.")

        # Textfarbe aus dem Theme übernehmen
        fg = (0.13, 0.13, 0.13)
        try:
            c = self.get_style_context().get_color()
            fg = (c.red, c.green, c.blue)
        except Exception:
            pass

        # Doppelt vorrendern und live herunterskalieren: bleibt auch
        # beim Verziehen des Trenners scharf.
        s = 2
        surf_w = max(200, self._preview_width() * s)
        pad = 8 * s
        tag_fd = Pango.FontDescription()
        tag_fd.set_size(9 * Pango.SCALE * s)
        pairs = []
        total_h = 2 * pad
        for size in _FONT_SIZES:
            tag_l = Pango.Layout.new(fctx)
            tag_l.set_font_description(tag_fd)
            tag_l.set_text("%d pt" % size, -1)
            text_fd = Pango.FontDescription()
            text_fd.set_family(family)
            text_fd.set_size(size * Pango.SCALE * s)
            text_l = Pango.Layout.new(fctx)
            text_l.set_font_description(text_fd)
            text_l.set_text(_FONT_SAMPLE_TEXT, -1)
            text_l.set_width(surf_w * Pango.SCALE)
            text_l.set_wrap(Pango.WrapMode.WORD_CHAR)
            pairs.append((tag_l, text_l))
            total_h += tag_l.get_pixel_size()[1]
            total_h += text_l.get_pixel_size()[1]
            total_h += 6 * s

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, surf_w, total_h)
        cr = cairo.Context(surf)
        y = pad
        for tag_l, text_l in pairs:
            cr.set_source_rgba(fg[0], fg[1], fg[2], 0.55)
            cr.move_to(pad, y)
            PangoCairo.show_layout(cr, tag_l)
            y += tag_l.get_pixel_size()[1]
            cr.set_source_rgba(fg[0], fg[1], fg[2], 1.0)
            cr.move_to(pad, y)
            PangoCairo.show_layout(cr, text_l)
            y += text_l.get_pixel_size()[1] + 6 * s

        pb = Gdk.pixbuf_get_from_surface(surf, 0, 0, surf_w, total_h)
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=False)
        self._content.pack_start(scroll, True, True, 0)

    def _pdf_page_pixbuf(self, page, target_w):
        """Eine PDF-Seite auf target_w Pixel Breite rendern (weiße Unterlage)."""
        pw, ph = page.get_size()
        # Mit doppelter Zielbreite rendern, damit die Live-Skalierung
        # auch beim Ziehen des Trenners scharf bleibt; extrem hohe
        # Seiten werden gedeckelt (Platz und Speicher).
        scale = min(float(target_w) / max(pw, 1.0),
                    2.0 * MAX_IMAGE_HEIGHT / max(ph, 1.0))
        scale = max(0.2, min(3.0, scale))
        w, h = max(1, int(pw * scale)), max(1, int(ph * scale))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        # Weiße Unterlage: PDF-Seiten dürfen transparente Flächen haben –
        # ohne Unterlage sähen sie auf dunklen Themes unleserlich schwarz aus.
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.paint()
        cr.scale(scale, scale)
        page.render(cr)
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)

    def _render_pdf(self, path):
        """
        PDF-Vorschau scrollbar: alle Seiten (bis MAX_PDF_PAGES) werden
        untereinander in einem scrollbaren Bereich gestapelt. Jede Seite
        wird in doppelter Panelbreite gerendert und bei Breitenänderung
        – wie bei der Bild-Vorschau – nur neu skaliert, nicht neu
        gerendert.
        """
        doc = Poppler.Document.new_from_file(GLib.filename_to_uri(path), None)
        n = doc.get_n_pages()
        if n == 0:
            self._hint("PDF enthält keine Seiten.")
            return
        count = min(n, MAX_PDF_PAGES)
        dbg("PDF geöffnet: %d Seite(n), zeige %d untereinander (scrollbar)"
            % (n, count))
        src_w = max(300, self._preview_width() * 2)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._pdf_src = []
        self._pdf_imgs = []
        for i in range(count):
            try:
                pb = self._pdf_page_pixbuf(doc.get_page(i), src_w)
            except Exception as exc:
                dbg("PDF-Seite %d nicht renderbar: %s" % (i + 1, exc))
                continue
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            box.pack_start(img, False, False, 0)
            self._pdf_src.append(pb)
            self._pdf_imgs.append(img)
        if not self._pdf_src:
            self._hint("PDF konnte nicht gerendert werden.")
            return
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(box)
        self._content.pack_start(scroll, True, True, 0)
        self._apply_pdf_scale()
        if n > count:
            self._hint("Erste %d von %d Seiten – ganze Datei über den "
                       "Öffnen-Knopf betrachten." % (count, n))
        elif n > 1:
            self._hint("%d Seiten – Vorschau nach unten scrollen." % n)

    def _apply_pdf_scale(self):
        """Alle PDF-Seiten an die aktuelle Panelbreite anpassen."""
        srcs = self._pdf_src
        imgs = self._pdf_imgs
        if not srcs or not imgs:
            return
        target = self._preview_width()
        if abs(target - self._pdf_last_w) < 8:
            return
        self._pdf_last_w = target
        try:
            for src, img in zip(srcs, imgs):
                sw, sh = src.get_width(), src.get_height()
                f = min(float(target) / sw, 1.0)   # nicht hochskalieren
                w = max(1, int(sw * f))
                h = max(1, int(sh * f))
                img.set_from_pixbuf(
                    src.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
        except Exception:
            pass

    def _render_folder(self, path):
        try:
            with os.scandir(path) as it:
                n = sum(1 for _ in it)
            self._hint("Ordner mit %d Einträgen." % n)
        except Exception:
            self._hint("Ordner")
        big = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
        big.set_pixel_size(128)
        self._content.pack_start(big, True, True, 0)

    def _render_audio(self, path, uri):
        tags = {}
        duration = -1
        cover = None
        try:
            try:
                disc = GstPbutils.Discoverer.new(10 * Gst.SECOND)
            except (AttributeError, TypeError):
                # Neuere PyGObject-Builds mappen gst_discoverer_new NICHT
                # als Konstruktor ('GObject.__init__() takes exactly 0
                # arguments (1 given)') – deshalb explizit .new(), mit
                # Fallback für ältere Builds.
                disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            info = disc.discover_uri_sync(uri)
            duration = info.get_duration() // Gst.SECOND
            taglist = info.get_tags()
            if taglist:
                for key, gst_tag in (("title", Gst.TAG_TITLE),
                                     ("artist", Gst.TAG_ARTIST),
                                     ("album", Gst.TAG_ALBUM)):
                    ok, val = taglist.get_string(gst_tag)
                    if ok and val:
                        tags[key] = val
                ok, sample = taglist.get_sample(Gst.TAG_IMAGE)
                if not (ok and sample):
                    ok, sample = taglist.get_sample(Gst.TAG_PREVIEW_IMAGE)
                if ok and sample:
                    cover = self._pixbuf_from_sample(sample)
        except Exception as e:
            dbg("Discoverer-Fehler: %s" % e)

        if cover:
            scroll = self._scaled_image(cover, 320, upscale=False,
                                        keep_height=True)
            self._content.pack_start(scroll, False, False, 0)

        rows = []
        if "title" in tags and tags["title"] != os.path.basename(path):
            rows.append(("Titel", tags["title"]))
        rows.append(("Datei", os.path.basename(path)))
        if "artist" in tags:
            rows.append(("Interpret", tags["artist"]))
        if "album" in tags:
            rows.append(("Album", tags["album"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))

        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(label=k)
            kl.set_halign(Gtk.Align.END)
            kl.get_style_context().add_class("dim-label")
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            vl.set_ellipsize(Pango.EllipsizeMode.END)
            vl.set_hexpand(True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._content.pack_start(grid, False, False, 0)

        # --- Player-Leiste ---
        if self._playbin is None:
            self._playbin = Gst.ElementFactory.make("playbin", "previewer-playbin")
        self._playbin.set_property("uri", uri)

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
        self._content.pack_start(player_box, False, False, 0)

        if self._progress_timer:
            GLib.source_remove(self._progress_timer)
        self._progress_timer = GLib.timeout_add(400, self._tick_player)

    def _pixbuf_from_sample(self, sample):
        buf = sample.get_buffer()
        data = buf.extract_dup(0, buf.get_size())
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        return loader.get_pixbuf()

    def _scale_pixbuf(self, pb, max_w, max_h):
        w, h = pb.get_width(), pb.get_height()
        if w <= max_w and h <= max_h:
            return pb
        scale = min(max_w / w, max_h / h)
        return pb.scale_simple(max(1, int(w * scale)),
                               max(1, int(h * scale)),
                               GdkPixbuf.InterpType.BILINEAR)

    def _render_video(self, path, uri):
        duration = -1
        frame = None
        tags = {}
        try:
            try:
                disc = GstPbutils.Discoverer.new(10 * Gst.SECOND)
            except (AttributeError, TypeError):
                # Siehe _render_audio: Konstruktor-Mapping je nach
                # PyGObject-Build unterschiedlich.
                disc = GstPbutils.Discoverer(10 * Gst.SECOND)
            info = disc.discover_uri_sync(uri)
            duration = info.get_duration() // Gst.SECOND
            taglist = info.get_tags()
            if taglist:
                for key, gst_tag in (("title", Gst.TAG_TITLE),
                                     ("artist", Gst.TAG_ARTIST)):
                    ok, val = taglist.get_string(gst_tag)
                    if ok and val:
                        tags[key] = val
            ok, sample = taglist.get_sample(Gst.TAG_PREVIEW_IMAGE) if taglist else (False, None)
            if ok and sample:
                frame = self._pixbuf_from_sample(sample)
        except Exception as e:
            dbg("Discoverer-Fehler: %s" % e)

        if frame:
            scroll = self._scaled_image(frame, 320, upscale=False,
                                        keep_height=True)
            self._content.pack_start(scroll, False, False, 0)
        else:
            self._hint("Kein Standbild verfügbar – Video im Player öffnen.")

        rows = [("Datei", os.path.basename(path))]
        if "title" in tags:
            rows.append(("Titel", tags["title"]))
        if duration >= 0:
            rows.append(("Länge", format_seconds(duration)))
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(label=k)
            kl.set_halign(Gtk.Align.END)
            kl.get_style_context().add_class("dim-label")
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            vl.set_ellipsize(Pango.EllipsizeMode.END)
            vl.set_hexpand(True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._content.pack_start(grid, False, False, 0)

    def _render_office(self, path):
        """
        Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX) – scharfe Route:
        Ist ein frisches LibreOffice-Konvertierungs-PDF im Cache, wird
        dessen Seiten per Poppler scharf und in voller Panelbreite
        gerendert (identisch zur PDF-Vorschau, scrollbar). Sonst
        erscheint zunächst die eingebettete Miniaturansicht mit
        Hinweis, und die Konvertierung läuft im Hintergrund los – das
        scharfe Ergebnis zeigt sich automatisch, sobald es fertig ist.
        Ohne LibreOffice/Poppler bleibt es bei der Miniaturansicht.
        """
        if HAVE_POPPLER and SOFFICE:
            cached = self._office_cached_pdf(path)
            if cached:
                try:
                    self._render_pdf(cached)
                    return
                except Exception as exc:
                    dbg("Office-PDF-Vorschau fehlgeschlagen (%s): %s"
                        % (path, exc))
                    # Halb gepackte Reste der PDF-Ansicht entfernen,
                    # bevor die Miniaturansicht gepackt wird.
                    self._clear_content()
                    # Ungültiges Cache-PDF: als gescheitert merken, sonst
                    # würde jede Neudarstellung erneut konvertieren.
                    self._office_failed.add(path)
            failed = path in self._office_failed
            self._render_office_thumb(path, converting=not failed)
            self._office_start_job(path)
            return
        self._render_office_thumb(path, converting=False)

    def _render_office_thumb(self, path, converting=False):
        """
        Übergangs-Ansicht für Office-Dokumente: die vom Dokument selbst
        eingebettete Miniaturansicht (Thumbnails/thumbnail.png bzw.
        docProps/thumbnail.*). Nur wenn KEINE Miniaturansicht vorhanden
        ist, wird ersatzweise ein Textauszug gezeigt. Bei converting=True
        läuft parallel die LibreOffice-Konvertierung – dann mit Hinweis.
        """
        thumb = None
        text = ""
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                for member in _OFFICE_THUMBS:
                    if member in names:
                        try:
                            thumb = zf.read(member)
                        except Exception:
                            thumb = None
                        break
                text = _extract_office_text(zf, names)
        except Exception as e:
            self._hint("Office-Dokument konnte nicht geöffnet werden: %s" % e)
            return
        shown = False
        if thumb:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(thumb)
                loader.close()
                pb = loader.get_pixbuf()
                if pb is not None:
                    # Upscale: Office-Miniaturansichten sind oft nur
                    # 256 px breit – sie wachsen mit der Panelbreite mit,
                    # statt klein in der Ecke zu kleben.
                    # Office-Miniaturansichten NATIV und scharf zeigen:
                    # Die eingebettete Miniatur hat nur ~256 px – jede
                    # Vergrößerung macht sie unleserlich schwammig.
                    scroll = self._scaled_image(pb, 1600, upscale=True,
                                                keep_height=True,
                                                max_upscale=1.0)
                    self._content.pack_start(scroll, False, False, 0)
                    shown = True
            except Exception:
                pass
        # Text nur als Ersatzvorschau, wenn keine Miniaturansicht
        # eingebettet war.
        if not shown and text.strip():
            view = Gtk.TextView()
            view.set_editable(False)
            view.set_cursor_visible(False)
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            view.override_font(Pango.FontDescription("Monospace 9"))
            view.set_left_margin(10)
            view.set_right_margin(10)
            view.set_top_margin(8)
            view.set_bottom_margin(8)
            view.get_buffer().set_text(text)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(view)
            self._content.pack_start(scroll, True, True, 0)
            shown = True
        if not shown:
            self._hint("Keine eingebettete Vorschau und kein Text "
                       "gefunden – Datei über den Öffnen-Knopf betrachten.")
        if converting:
            self._hint("Scharfe Vorschau wird im Hintergrund erstellt "
                       "(LibreOffice) – einen Moment …")

    # --- Office: scharfe Vorschau via LibreOffice --------------------------

    def _office_cached_pdf(self, path):
        """Frisch konvertiertes PDF aus dem Cache oder None."""
        try:
            cache_pdf = office_cache_path(path)
            if (os.path.exists(cache_pdf)
                    and os.path.getmtime(cache_pdf)
                    >= os.path.getmtime(path)):
                return cache_pdf
        except Exception:
            pass
        return None

    def _office_start_job(self, path):
        """LibreOffice-Konvertierung im Hintergrund starten."""
        if self._office_job is not None:
            return          # es läuft bereits eine Konvertierung
        if not SOFFICE or not HAVE_POPPLER:
            return
        if path in self._office_failed:
            return          # bereits gescheitert – nicht endlos erneut
        self._office_job = path
        tmpdir = tempfile.mkdtemp(prefix="previewer-office-")
        out_pdf = os.path.join(
            tmpdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        try:
            pid = GLib.spawn_async(
                [SOFFICE, "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, path],
                flags=GLib.SpawnFlags.SEARCH_PATH
                | GLib.SpawnFlags.DO_NOT_REAP_CHILD)[0]
        except Exception as exc:
            dbg("LibreOffice-Konvertierung nicht gestartet (%s): %s"
                % (path, exc))
            shutil.rmtree(tmpdir, ignore_errors=True)
            self._office_job = None
            return
        GLib.child_watch_add(pid, self._office_job_done,
                             (path, tmpdir, out_pdf))

    def _office_job_done(self, pid, status, data):
        """Konvertierung beendet: Ergebnis cachen, Vorschau auffrischen."""
        path, tmpdir, out_pdf = data
        self._office_job = None
        try:
            if os.path.exists(out_pdf):
                try:
                    # shutil.move statt os.replace: /tmp liegt häufig auf
                    # einem eigenen Gerät (tmpfs) – rename(2) scheitert dann
                    # mit EXDEV, move kopiert in dem Fall.
                    shutil.move(out_pdf, office_cache_path(path))
                except Exception as exc:
                    dbg("Office-Cache konnte nicht geschrieben werden: %s"
                        % exc)
                if self._path == path:
                    self._render()   # scharfe Seitenansicht zeigen
            else:
                # Gescheiterte Konvertierung merken – verhindert eine
                # Endlosschleife aus erneuten Konvertierungsversuchen.
                self._office_failed.add(path)
                if len(self._office_failed) > 256:
                    self._office_failed.clear()
                if self._path == path:
                    dbg("LibreOffice-Konvertierung ohne Ergebnis "
                        "(Status %s) – Miniaturansicht bleibt" % status)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        # Wartet die aktuelle Auswahl auf ihre Konvertierung, direkt die
        # nächste starten (es läuft ja keine mehr).
        try:
            cur = self._path
            if (cur and os.path.splitext(cur.lower())[1] in _OFFICE_EXTS
                    and cur not in self._office_failed
                    and self._office_cached_pdf(cur) is None
                    and self._office_job is None):
                self._office_start_job(cur)
        except Exception:
            pass

    def _render_generic(self):
        mime, size, mtime = query_file_info(self._path)
        big = Gtk.Image()
        try:
            icon = Gio.content_type_get_icon(mime or "text-x-generic")
            big.set_from_gicon(icon, Gtk.IconSize.DIALOG)
            big.set_pixel_size(96)
        except Exception:
            big.set_from_icon_name("text-x-generic", Gtk.IconSize.DIALOG)
        self._content.pack_start(big, True, True, 0)

    def _hint(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_line_wrap(True)
        lbl.get_style_context().add_class("dim-label")
        lbl.set_halign(Gtk.Align.START)
        self._content.pack_start(lbl, False, False, 0)

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
        """Positionsanzeige aktualisieren; Timer läuft, solange Panel lebt."""
        if self._playbin is None:
            self._progress_timer = 0
            return False
        try:
            ok, pos = self._playbin.query_position(Gst.Format.TIME)
            ok2, dur = self._playbin.query_duration(Gst.Format.TIME)
            if ok and pos >= 0:
                self._pos_label.set_text(format_seconds(pos // Gst.SECOND))
                if ok2 and dur > 0:
                    # Slider-Bereich muss die GESAMTE Länge umfassen. War
                    # die Dauer beim Anlegen noch unbekannt (z.B. wenn der
                    # Discoverer versagte), wurde der Slider mit dem
                    # Bereich 0–1 angelegt – der Timer konnte ihn dann
                    # nie sichtbar bewegen. Der Bereich wird deshalb hier
                    # aus der echten Abspiel-Dauer einmalig nachgezogen.
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
        if self._playbin is not None:
            try:
                self._playbin.set_state(Gst.State.NULL)
            except Exception:
                pass

    # --- Aktionen -----------------------------------------------------------

    def _on_open_clicked(self, *a):
        if not self._path or not os.path.exists(self._path):
            return
        try:
            Gio.AppInfo.launch_default_for_uri(
                GLib.filename_to_uri(self._path), None)
        except Exception as e:
            dbg("Öffnen fehlgeschlagen: %s" % e)

    def _on_toggle_accel(self, group, accelerable, key, mods):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
        return True


# Version: Der Einstieg (previewer.py) prüft beim Laden, ob alle Module
# diese Version tragen – veraltete Dateien im Extension-Ordner werden
# so im Terminal-Log sofort sichtbar.
PREVIEWER_VERSION = "0.4.1"
dbg("previewer_panel %s geladen (scrollbare PDFs, E-Books, "
    "Schrift-Wasserfall, Slider-Fix, Discoverer-Fix)" % PREVIEWER_VERSION)