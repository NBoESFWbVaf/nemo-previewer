#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Renderer-Modul Text (previewer_render_text.py)
==========================================================

STAND: Version 0.23.0 – F38/F43: Nur Versions-Sync. _render_text reicht
die Zeilennummern-Einstellung an den TextView weiter (Rubrik
„Textdateien“, Default an; die Nummern sind nicht kopierbar, der
Text schon). Markdown, EML, E-Books und Font-Wasserfall bleiben
ohne Nummern.

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
"""

import os
import sys
import re
import base64
import ctypes
import ctypes.util
import hashlib
import html
import shutil
import struct
import tempfile
import zipfile
import email
from email import policy
import xml.etree.ElementTree as ElementTree

import gi

gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')

from gi.repository import Gdk, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    MAX_TEXT_BYTES, MAX_TEXT_LINES, MAX_IMAGE_HEIGHT,
    MAX_EBOOK_CHARS,
    _zf_read_capped, _pixbuf_from_bytes,
)

# --- Optionale Module (Fehlen ist kein Fehler, nur weniger Vorschau) ---

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

# 0.9.2 (Audit „Pufferüberlauf/OOM“): Deckel gegen Dekompressions- und
# Dekodierbomben – ein präpariertes Bild/PDF/EPUB/DOCX/EML darf Nemo
# niemals durch Riesen-Allokationen abschießen.
_EML_FILE_CAP = 2 * 1024 * 1024      # .eml: Kopfzeilen + Körper-Anfang

# --- Markdown -> Pango-Markup (Vorschau-Qualität, kein voller Parser) ---

def _pango_escape(s):
    """Text für Pango-Markup entschärfen (& < >)."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_MD_BULLETS = ("\u2022", "\u25e6", "\u25aa")   # • ◦ ▪ je Listenebene

# GFM-Tabellen: Gesamtbudget in Anzeigespalten – ausgelegt aufs
# 300-px-Standardpanel (Monospace). Kürzere Spalten bleiben ggf.
# unter dem Budget, breite Tabellen brechen innerhalb der Spalten
# mehrzeilig um, statt das TextView zum Zeilenumbruch zu zwingen.
_MD_TABLE_BUDGET = 44
_MD_TABLE_MIN = 4      # Mindestbreite je Spalte
_MD_TABLE_FIT = 24    # Spalten bis hierher werden bevorzugt NICHT umgebrochen


def _md_inline(t):
    """Inline-Formatierung: ***fett+kursiv***, **fett**, __fett__,
    *kursiv*, _kursiv_, ~~durchgestrichen~~ (GFM), `code`,
    [Link](url) – auch mit runden Klammern in der URL –,
    <https://Autolink>, ![Bild](url)."""
    # Backslash-Escapes zuerst (CommonMark): \[ wird zu [ – der
    # Rest dieser Funktion läuft ohnehin auf gescapetem Text
    t = re.sub(r"\\(\W)", r"\1", t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    t = re.sub(r"___(.+?)___", r"<b><i>\1</i></b>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"__(.+?)__", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"~~(.+?)~~", r"<s>\1</s>", t)
    t = re.sub(r"`([^`]+?)`", r"<tt>\1</tt>", t)
    t = re.sub(r"!\[([^\]]*)\]\(((?:[^()\s]|\([^()\s]*\))+)\)",
               r"<span size='small'>[Bild: \1]</span>", t)
    t = re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)",
               r"\1 <span size='small' foreground='grey'>\2</span>", t)
    t = re.sub(r"&lt;(https?://[^&\s]+)&gt;",
               r"\1 <span size='small' foreground='grey'>[Link]</span>", t)
    return t


def _md_heading(depth, text):
    """Überschrift (ATX oder Setext): Größe nach Tiefe, H1/H2 mit
    Unterstrich – nähert den farbigen Balken der Browser-Darstellung
    an, ohne extra Widgets."""
    if depth == 1:
        tag = ("<span size='x-large' weight='bold' "
               "underline='single'>", "</span>")
    elif depth == 2:
        tag = ("<span size='large' weight='bold' "
               "underline='single'>", "</span>")
    else:
        tag = "<span weight='bold'>", "</span>"
    return tag[0] + _md_inline(_pango_escape(text)) + tag[1]


def _md_hr():
    # → REF TXT-HR-1
    return ("<span size='small' foreground='grey'>"
            + "\u2500" * 12 + "</span>")


def _md_w(s):
    """Anzeigebreite eines Strings schätzen: Emoji und Symbole
    belegen im TextView zwei Spalten (🔴 ✅ ☑ …), der Variation-
    Selector FE0F gar keine, alles Übrige genau eine. Ohne diese
    Schätzung standen Emoji-Zellen um die Emoji-Breite daneben."""
    w = 0
    for c in s:
        o = ord(c)
        if c == "\ufe0f":
            continue
        if (0x2600 <= o <= 0x27bf or 0x2b00 <= o <= 0x2bff
                or o >= 0x1f000):
            w += 2
        else:
            w += 1
    return w


def _md_table(lines, i):
    """
    GFM-Tabelle ab Zeile i einlesen: Kopfzeile, Trennzeile mit
    :--/--:/:-:, beliebig viele Zeilen. Rückgabe (Markup-Zeilen,
    nächster Index) oder None, wenn dort keine Tabelle steht.
    Wie im Browser gilt ein Gesamtbudget: schmale Spalten
    behalten ihre volle Breite, überlange Zellen brechen
    mehrzeilig INNERHALB ihrer Spalte um – die Spalten bleiben
    bündig, statt dass die längste Zelle alle Zeilen aufbläht
    (0.14.0-Feldtest: die Reihenfolge-Tabelle in planned.md war
    meterbreit und zerfiel im TextView). Kopfzeile fett, graue
    Trennzeile, rechtsbündig bei '---:'. Breiten werden an der
    ROHEN Zelle gemessen und VOR dem Escapen gepolstert, damit
    &amp; die Ausrichtung nicht verdirbt. Markup, das über einen
    Zell-Umbruch hinwegläuft, wird bewusst NICHT zusammengefügt –
    gültiges Markup ist wichtiger als Optik, der Rohtext-Fallback
    in _render_markdown darf niemals wegen einer Tabelle greifen.
    """
    def split_cells(row):
        s = row.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|") and not s.endswith("\\|"):
            s = s[:-1]
        # GFM: \| ist ein maskierter Balken, KEIN Spaltentrenner
        return [re.sub(r"\\(\|)", r"\1", c).strip()
                for c in re.split(r"(?<!\\)\|", s)]

    if i + 1 >= len(lines):
        return None
    if not re.search(r"(?<!\\)\|", lines[i]):
        return None
    sep_cells = split_cells(lines[i + 1])
    if not sep_cells:
        return None
    for c in sep_cells:
        if not re.fullmatch(r":?-{2,}:?", c):
            return None
    head = split_cells(lines[i])
    body = []
    j = i + 2
    while j < len(lines):
        s = lines[j]
        if not s.strip() or not re.search(r"(?<!\\)\|", s):
            break
        body.append(split_cells(s))
        j += 1
    cols = len(sep_cells)
    right = [c.endswith(":") and not c.startswith(":")
             for c in sep_cells]

    def plain(cell):
        s = re.sub(r"\[([^\]]+)\]\(([^()\s]+)\)", r"\1 (\2)", cell)
        return re.sub(r"[*_`~]", "", s)

    demand = [0] * cols
    for r in [head] + body:
        for k in range(cols):
            if k < len(r):
                demand[k] = max(demand[k], _md_w(plain(r[k])))

    # Spaltenbreiten: schmale Spalten voll bedienen, den Rest
    # nach Bedarf auf die breiten Spalten verteilen – im Rahmen
    # des Gesamtbudgets
    sep_w = 3 * (cols - 1)          # " │ " zwischen den Spalten
    avail = max(0, _MD_TABLE_BUDGET - sep_w)
    widths = [min(d, _MD_TABLE_MIN) for d in demand]
    bigs = [k for k in range(cols)
            if demand[k] > _MD_TABLE_MIN]
    if sum(demand[k] for k in range(cols)
           if demand[k] <= _MD_TABLE_FIT) <= avail:
        for k in range(cols):
            if demand[k] <= _MD_TABLE_FIT:
                widths[k] = demand[k]
        bigs = [k for k in bigs if demand[k] > _MD_TABLE_FIT]
    base = _MD_TABLE_MIN
    if bigs and base * len(bigs) > avail:
        base = 1
    if bigs:
        taken = sum(widths[k] for k in range(cols)
                    if k not in bigs)
        extra = max(0, avail - taken - base * len(bigs))
        rest = [demand[k] - base for k in bigs]
        rsum = sum(rest) or 1
        for pos, k in enumerate(bigs):
            widths[k] = base + rest[pos] * extra // rsum
        left = avail - taken - sum(widths[k] for k in bigs)
        order = sorted(bigs,
                       key=lambda k: (demand[k] - base) * extra
                       % rsum,
                       reverse=True)
        for k in order[:left]:
            widths[k] += 1
    for k in range(cols):
        widths[k] = min(widths[k], demand[k])
    # Sicherheitsnetz: selbst bei absurd vielen Spalten die
    # breiteste schrumpfen, bis das Budget hält
    while (sum(widths) + sep_w > _MD_TABLE_BUDGET
           and max(widths) > 1):
        widths[widths.index(max(widths))] -= 1

    def wrap_cell(cell, w):
        # Zelle in Anzeigesegmente der Breite w brechen (Wort-
        # Umbruch, überlange Wörter hart). Passt alles in eine
        # Zeile, bleibt die Zelle mitsamt ihrem Markup unangetastet.
        w = max(1, w)
        if _md_w(plain(cell)) <= w:
            return [cell]
        segs = []
        cur = ""
        for word in cell.split(" "):
            if _md_w(word) > w:
                if cur:
                    segs.append(cur)
                    cur = ""
                while _md_w(word) > w:
                    acc = ""
                    for ch in word:
                        if _md_w(acc + ch) > w:
                            break
                        acc += ch
                    if not acc:
                        acc = word[0]
                    segs.append(acc)
                    word = word[len(acc):]
                cur = word
                continue
            if cur and _md_w(cur + " " + word) <= w:
                cur = cur + " " + word
            else:
                if cur:
                    segs.append(cur)
                cur = word
        if cur or not segs:
            segs.append(cur)
        return segs

    def fmt_row(r, bold=False):
        wrapped = [wrap_cell(r[k] if k < len(r) else "",
                             widths[k])
                   for k in range(cols)]
        height = max(len(w) for w in wrapped)
        rows_out = []
        for y in range(height):
            cells = []
            for k in range(cols):
                seg = wrapped[k][y] if y < len(wrapped[k]) else ""
                pad = max(0, widths[k] - _md_w(plain(seg)))
                if right[k]:
                    seg = " " * pad + seg
                else:
                    seg = seg + " " * pad
                esc = _md_inline(_pango_escape(seg))
                if bold:
                    esc = "<b>%s</b>" % esc
                cells.append(esc)
            rows_out.append("<tt>%s</tt>" % " \u2502 ".join(cells))
        return rows_out

    rows = fmt_row(head, bold=True)
    rows.append("<tt><span foreground='grey'>%s</span></tt>"
                % "\u253c".join("\u2500" * (w + 2) for w in widths))
    for r in body:
        rows.extend(fmt_row(r))
    return rows, j


def _markdown_to_pango(text):
    """
    Markdown in Pango-Markup übersetzen – bewusst kein vollständiger
    Parser, aber mit den verbreiteten Varianten (GitHub Flavored
    Markdown): ATX- (#) und Setext-Überschriften (===/---) mit
    Unterstrich bei H1/H2, Fett/Kursiv/fett+kursiv, ~~Streichen~~,
    Inline- und Block-Code, unsortierte Listen mit Ebenen-Zeichen
    (•/◦/▪), sortierte (1./1)), Task-Listen ([x] → ☑ mit
    Durchstreichen wie im Browser, [ ] → ☐), eingerückte Listen,
    mehrfach verschachtelte Zitate, Trennlinien (auch mit
    Leerzeichen: - - -), Links (auch mit Klammern in der URL),
    Autolinks und GFM-Tabellen. Überschriften, Linien und Tabellen
    bekommen Luft nach oben – das wirkt wie im Browser. Kein
    Webview, keine neuen Paket-Abhängigkeiten; bewusst weg:
    4-Spaces-Codeblöcke (kollidiert mit Listeneinrückungen).
    """
    lines = text.split("\n")
    out = []
    in_code = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # --- Code-Zäune (``` … ```) ---
        if stripped.startswith("```"):
            in_code = not in_code
            out.append("")
            i += 1
            continue
        if in_code:
            out.append("<tt>%s</tt>" % _pango_escape(line))
            i += 1
            continue
        if not stripped:
            out.append("")
            i += 1
            continue
        # --- Setext-Überschriften: Textzeile + ===== / ------ ---
        # (\x29 = Hex-Escape für die schließende Klammer – hält die
        # Zeichenklasse aus der Paren-Diff-Bilanz heraus)
        if (i + 1 < n
                and not re.match(r"^(#|>|`|\||[-*+]\s|\d+[\x29.]\s)",
                                 stripped)
                and not re.fullmatch(r"(?:[-=*_]\s*){3,}", stripped)):
            nxt = lines[i + 1].strip()
            if re.fullmatch(r"=+\s*", nxt):
                if out and out[-1] != "":
                    out.append("")
                out.append(_md_heading(1, stripped))
                i += 2
                continue
            if re.fullmatch(r"-{2,}\s*", nxt):
                if out and out[-1] != "":
                    out.append("")
                out.append(_md_heading(2, stripped))
                i += 2
                continue
        # --- Trennlinien (auch mit Leerzeichen: - - - / * * *) ---
        if re.fullmatch(r"((?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})",
                        stripped):
            if out and out[-1] != "":
                out.append("")
            out.append(_md_hr())
            i += 1
            continue
        # --- ATX-Überschriften (# … ######, auch mit End-#) ---
        m = re.match(r"^(#{1,6})\s+(.*?)(?:\s+#+)?$", stripped)
        if m:
            if out and out[-1] != "":
                out.append("")
            out.append(_md_heading(len(m.group(1)), m.group(2)))
            i += 1
            continue
        # --- GFM-Tabellen ---
        tbl = _md_table(lines, i)
        if tbl is not None:
            if out and out[-1] != "":
                out.append("")
            out.extend(tbl[0])
            if tbl[1] < n and lines[tbl[1]].strip():
                out.append("")
            i = tbl[1]
            continue
        # --- Zitate (mehrfach verschachtelt: >, >>, > >) ---
        m = re.match(r"^(>+)(.*)$", stripped)
        if m:
            depth = len(m.group(1))
            body = m.group(2).strip()
            while body.startswith(">"):
                depth += 1
                body = body[1:].lstrip()
            out.append("    " * (depth - 1) + "<i>%s</i>"
                       % _md_inline(_pango_escape(body)))
            i += 1
            continue
        # --- Task-Listen (GFM): - [x] erledigt / - [ ] offen ---
        m = re.match(r"^(\s*)([-*+])\s+\[([ xX])\]\s+(.*)$", line)
        if m:
            lvl = len(m.group(1)) // 2
            done = m.group(3).strip().lower() == "x"
            body = _md_inline(_pango_escape(m.group(4)))
            if done:
                body = "<s>%s</s>" % body
            out.append("    " * lvl + ("\u2611" if done else "\u2610")
                       + " " + body)
            i += 1
            continue
        # --- Unsortierte Listen mit Ebenen ---
        m = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
        if m:
            lvl = len(m.group(1)) // 2
            out.append("    " * lvl
                       + _MD_BULLETS[lvl % len(_MD_BULLETS)] + " "
                       + _md_inline(_pango_escape(m.group(3))))
            i += 1
            continue
        # --- Sortierte Listen (1. / "1)" ) ---
        m = re.match(r"^(\s*)(\d{1,3})([\x29.])\s+(.*)$", line)
        if m:
            lvl = len(m.group(1)) // 2
            out.append("    " * lvl + m.group(2) + m.group(3) + " "
                       + _md_inline(_pango_escape(m.group(4))))
            i += 1
            continue
        out.append(_md_inline(_pango_escape(line)))
        i += 1
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


_EBOOK_CHUNK_CAP = 2 * 1024 * 1024     # R4: max. Bytes je Spine-Dokument
_EBOOK_COVER_CAP = 16 * 1024 * 1024    # R4: max. Bytes für Cover-Bilder


def _epub_data(path):
    """
    EPUB öffnen: Metadaten (Titel, Autor, Sprache), Cover-Bytes und der
    Textanfang in Lesereihenfolge (Spine). Rückgabe (rows, cover, text).
    """
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        # → REF TXT-EPUB-1
        opf_path = None
        try:
            container = _zf_read_capped(
                zf, "META-INF/container.xml", _EBOOK_CHUNK_CAP).decode(
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
        root = ElementTree.fromstring(
            _zf_read_capped(zf, opf_path, _EBOOK_CHUNK_CAP))

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
                        item.get("href"), item.get("media-type"),
                        item.get("properties") or "")
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
                cover = _zf_read_capped(zf, base + manifest[cover_id][0],
                                        _EBOOK_COVER_CAP)
            except KeyError:
                cover = None
        if not cover:
            for name in names:
                low = name.rsplit("/", 1)[-1].lower()
                if "cover" in low and low.endswith(
                        (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                    try:
                        cover = _zf_read_capped(zf, name, _EBOOK_COVER_CAP)
                        break
                    except KeyError:
                        pass

        # Textanfang: Spine-Dokumente in Lesereihenfolge zu Text bereinigen
        parts = []
        total = 0
        for idref in spine:
            if total >= MAX_EBOOK_CHARS:
                break
            href, mtype, props = manifest.get(idref, (None, None, ""))
            if not href:
                continue
            # R6: EPUB3-Navigationsdatei (properties="nav") ist das
            # Inhaltsverzeichnis, nicht Buchtext – überspringen.
            if "nav" in props.split():
                continue
            if mtype and "html" not in mtype and "xml" not in mtype:
                continue
            try:
                raw = _zf_read_capped(zf, base + href, _EBOOK_CHUNK_CAP)
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


_MOBI_MAX_BYTES = 8 * 1024 * 1024   # MOBI: nur bis hier lesen – Text-Datensätze
                                     # stehen ohnehin am Dateianfang; Records
                                     # jenseits der Deckel überspringt der
                                     # Offset-Check unten still


def _mobi_data(path):
    """
    MOBI/PRC (Palm-Container): Titel, Autor (EXTH) und Textanfang.
    Unterstützt Kompressionsverfahren 1 (PalmDoc) und 2 (unkomprimiert);
    HUFF/CDIC (einige neuere AZW) wird abgelehnt – KF8-Dateien (AZW3)
    liefern bestenfalls HTML-Reste, sind aber lesbar, wenn PalmDoc
    komprimiert ist. Es wird nur der Dateikopf bis _MOBI_MAX_BYTES
    gelesen (B5): riesige AZW3-Dateien sollen Nemo nicht einfrieren.
    """
    with open(path, "rb") as fh:
        data = fh.read(_MOBI_MAX_BYTES)
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

    # → REF TXT-MOBI-1
    _mobi_edge = ("\ufffd\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c"
                  "\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19"
                  "\x1a\x1b\x1c\x1d\x1e\x1f")
    parts = []
    total = 0
    for rec in recs[1:first_non_book]:
        if compression == 1:
            rec = _palmdoc_decompress(rec)
        chunk = rec.decode(encoding, "replace").strip(_mobi_edge)
        if not chunk:
            continue
        parts.append(chunk)
        total += len(chunk)
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
# temporärer Ordner für die Fontconfig-Übernahme, bereits übernommene
# Pfade und die geordnete Liste der Kopien im Temp-Ordner (R5-Deckel)
_FONT_STATE = {"tmpdir": None, "added": set(), "copies": []}
# R5: Temp-Ordner auf 64 Kopien deckeln – fontconfig behält gelöschte
# Schriften im Speicher, bis der Prozess endet; der Ordner selbst
# darf aber nicht bis zum Reboot/Absturz unendlich wachsen.
_FONT_COPY_LIMIT = 64


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
        # Zielname mit Hash des QUELLPFADS: zwei Schriften mit gleichem
        # Dateinamen aus verschiedenen Ordnern dürfen sich nicht ins
        # Gehege kommen (B1) – sonst sähe der Wasserfall immer die
        # zuerst kopierte Datei.
        stem, ext = os.path.splitext(os.path.basename(path))
        digest = hashlib.sha1(os.path.abspath(path).encode(
            "utf-8", "replace")).hexdigest()[:8]
        dest = os.path.join(state["tmpdir"], "%s-%s%s" % (stem, digest, ext))
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
            # → REF TXT-FONT-1
            state["copies"].append(dest)
            while len(state["copies"]) > _FONT_COPY_LIMIT:
                old = state["copies"].pop(0)
                try:
                    os.unlink(old)
                except Exception:
                    pass
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


# ============================ Renderer: Text ================================


class TextRendererMixin:
    """Mixin: Renderer für Text, Markdown, EML, E-Book und Schrift."""

    # --- gemeinsame Helfer für Text-Ansichten (Audit 0.9.1) ---------------
    # Der TextView-Bau war zuvor FÜNF Mal nahezu identisch implementiert
    # (Text, Markdown, EML-Körper, E-Book, Office-Textauszug), das
    # gekappte Datei-Lesen zwei Mal (Text, Markdown).

    def _read_text_file(self, path):
        """Datei gekappt lesen: (Text, truncated) – Text und Markdown."""
        with open(path, "rb") as fh:
            data = fh.read(MAX_TEXT_BYTES)
        text = data.decode("utf-8", "replace")
        truncated = len(data) == MAX_TEXT_BYTES
        lines = text.split("\n")
        if len(lines) > MAX_TEXT_LINES:
            text = "\n".join(lines[:MAX_TEXT_LINES])
            truncated = True
        return text, truncated

    def _render_text(self, path):
        try:
            text, truncated = self._read_text_file(path)
        except Exception as e:
            self._hint("Konnte Datei nicht lesen: %s" % e)
            return
        # F24 (0.16.0): Zeilennummern laut Einstellung „Textdateien“
        # (Default an); sie sind Randzeichnung, nicht Textbuffer –
        # kopiert wird nur der Text selbst.
        self._text_view(text, font="Monospace 9",
                        linenumbers=self._conf_text_linenumbers)
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
            text, truncated = self._read_text_file(path)
        except Exception as e:
            self._hint("Konnte Datei nicht lesen: %s" % e)
            return
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
        # → REF TXT-B6-1
        self._text_view(text, font=None, markup=(markup if valid else None))
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
                # 0.9.2: Lese-Deckel – die Kopfzeilen stehen ohnehin
                # oben; ein mehr-GB-.eml würde die sonst ganze Datei
                # in den Speicher ziehen und Nemo einfrieren.
                raw = fh.read(_EML_FILE_CAP)
            msg = email.message_from_bytes(raw, policy=policy.default)
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
        # 0.9.1: Kopfzeilen über den zentralen Tabellen-Helfer
        # (zuvor identisch inline gebaut).
        self._meta_grid(rows)

        body = self._eml_body(msg)
        if not body.strip():
            self._hint("Kein lesbarer Textkörper gefunden – Datei "
                       "über den Öffnen-Knopf betrachten.")
            return
        self._text_view(body)

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
        # 0.9.1: Textanfang über den gemeinsamen TextView-Helfer
        # (zuvor identisch inline gebaut).
        self._text_view(text)

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



PREVIEWER_VERSION = "0.23.0"
dbg("previewer_render_text %s geladen (F31: Text/Markdown/EML/"
    "E-Book/Schrift-Renderer; K4-Markdown und Lese-Deckel bleiben)"
    % PREVIEWER_VERSION)