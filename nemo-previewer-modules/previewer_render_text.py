#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_render_text.py – Version 1.16.0

Text renderers: plain text and source code, Markdown, e-mail,
e-books, vCards and the font waterfall preview.
"""

import os
import sys
import re
import base64
import csv
import ctypes
import ctypes.util
import hashlib
import html
import io
import shutil
import sqlite3
import struct
import tarfile
import tempfile
import zipfile
import zlib
import email
import math
import quopri
from email import policy
import xml.etree.ElementTree as ElementTree

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Pango', '1.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    _,
    dbg,
    MAX_TEXT_BYTES, MAX_TEXT_LINES, MAX_IMAGE_HEIGHT,
    pick_icon, human_size,
    _zf_read_capped, _pixbuf_from_bytes,
    _xml_dtd_rejected,
    pack_hint,
    pack_meta_grid,
    META_SIZE_CSS_CLASS,
    center_window,
    cover_round_path,
    effective_text_font,
)

# --- Optional modules (missing ones just reduce the previews) ---

# PangoCairo + pycairo to pre-render the font waterfall with its own
# FRESH Pango font map – GTK's default map is built at startup.
HAVE_PANGOCAIRO = False
try:
    import cairo  # pycairo
    gi.require_version('PangoCairo', '1.0')
    from gi.repository import PangoCairo
    HAVE_PANGOCAIRO = True
except Exception as e:
    dbg("text/module-level: suppressed: %s" % e)

# F67: markdown-it-py – CommonMark/GFM engine for the Markdown
# preview (→ REF TXT-DOC-101). Pure Python; missing packages keep
# the built-in line parser below as the fallback.
HAVE_MDIT = False
try:
    from markdown_it import MarkdownIt
    from mdit_py_plugins.dollarmath import dollarmath_plugin
    from mdit_py_plugins.footnote import footnote_plugin
    from mdit_py_plugins.front_matter import front_matter_plugin
    HAVE_MDIT = True
except Exception as e:
    dbg("text/module-level: markdown-it-py missing (%s) - "
        "legacy Markdown parser stays" % e)

HAVE_LINKIFY = False
try:
    from linkify_it import LinkifyIt
    HAVE_LINKIFY = True
except Exception:
    pass

# Isolated import: a missing single plugin may not kill the whole
# engine (1.12.1 – definitions lists via the deflist plugin).
HAVE_DEFLIST = False
try:
    from mdit_py_plugins.deflist import deflist_plugin
    HAVE_DEFLIST = True
except Exception:
    pass

# F83: WebKit2 (GTK3, API 4.1) renders the Markdown preview as a
# real HTML document – a missing GIR keeps the Pango text
# approximation below (→ REF TXT-DOC-110).
HAVE_WEBKIT = False
try:
    gi.require_version('WebKit2', '4.1')
    from gi.repository import WebKit2
    HAVE_WEBKIT = True
except Exception as e:
    dbg("text/module-level: WebKit2 missing (%s) - Markdown "
        "preview stays Pango text" % e)

# 1.13.1 (B15, deploy feedback): VirtualBox guests hit a known
# WebKit2GTK rendering bug – the page paints once and scrolling
# never repaints (stale DMABUF frames). The switches force the
# classic painting path; setdefault keeps a user override possible.
if HAVE_WEBKIT:
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

# F83: Pygments colors the fenced code blocks in the HTML preview
# (optional – without it the blocks stay plain).
HAVE_PYGMENTS = False
try:
    from pygments import highlight as _pyg_highlight
    from pygments.lexers import get_lexer_by_name as _pyg_lexer
    from pygments.formatters import HtmlFormatter as _PygFormatter
    HAVE_PYGMENTS = True
except Exception as e:
    dbg("text/module-level: pygments missing (%s) - code blocks "
        "stay plain" % e)

# Built once per process. The "gfm-like" preset needs linkify-it-py;
# without it the commonmark preset plus the built-in table and
# strikethrough rules cover the same ground minus link detection.
_MDIT = None
if HAVE_MDIT:
    try:
        if HAVE_LINKIFY:
            _MDIT = MarkdownIt("gfm-like")
        else:
            _MDIT = MarkdownIt("commonmark")
            _MDIT.enable(["table", "strikethrough"])
        _MDIT.use(front_matter_plugin)
        _MDIT.use(footnote_plugin)
        _MDIT.use(dollarmath_plugin)
        if HAVE_DEFLIST:
            _MDIT.use(deflist_plugin)
    except Exception as e:
        dbg("text/module-level: markdown-it init failed (%s) - "
            "legacy Markdown parser stays" % e)
        _MDIT = None

# 0.9.2 (audit "buffer overflow/OOM"): caps against decompression
# and decoding bombs – crafted files must never blow up Nemo.
# The .eml caps are GONE (user request: a big mail stays big) –
# the whole file is parsed (→ REF TXT-EML-ATT-1).
_VCARD_FILE_CAP = 8 * 1024 * 1024    # vCard: properties + base64 photo
_FB2_FILE_CAP = 8 * 1024 * 1024      # R11: FB2 read cap – the cover sits
                                     # as base64 in the file; oversized
                                     # FB2s get truncated and are then
                                     # not parsed at all

# --- Markdown -> Pango markup (preview quality, not a full parser) ---

# → REF TXT-DOC-1
def _pango_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_MD_BULLETS = ("\u2022", "\u25e6", "\u25aa")   # • ◦ ▪ per list level

# GFM tables: total budget in display columns – sized for the
# 300 px default panel (monospace); wide tables wrap inside cells.
_MD_TABLE_BUDGET = 44
_MD_TABLE_MIN = 4      # minimum width per column
_MD_TABLE_FIT = 24    # columns up to here preferably stay unwrapped


# → REF TXT-DOC-2
def _md_inline(t):
    # Backslash escapes first (CommonMark): \[ becomes [ – the
    # rest of this function runs on escaped text anyway.
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
               r"<span size='small'>[Image: \1]</span>", t)
    t = re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)",
               r"\1 <span size='small' foreground='grey'>\2</span>", t)
    t = re.sub(r"&lt;(https?://[^&\s]+)&gt;",
               r"\1 <span size='small' foreground='grey'>[Link]</span>", t)
    return t


# → REF TXT-DOC-3
def _md_heading_markup(depth, markup):
    if depth == 1:
        tag = ("<span size='x-large' weight='bold' "
               "underline='single'>", "</span>")
    elif depth == 2:
        tag = ("<span size='large' weight='bold' "
               "underline='single'>", "</span>")
    else:
        tag = "<span weight='bold'>", "</span>"
    return tag[0] + markup + tag[1]


def _md_heading(depth, text):
    return _md_heading_markup(depth, _md_inline(_pango_escape(text)))


def _md_hr():
    # → REF TXT-HR-1
    return ("<span size='small' foreground='grey'>"
            + "\u2500" * 12 + "</span>")


# → REF TXT-DOC-4
def _md_w(s):
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


# → REF TXT-DOC-5
def _md_split_cells(row):
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    # GFM: \| is an escaped bar, NOT a column separator
    return [re.sub(r"\\(\|)", r"\1", c).strip()
            for c in re.split(r"(?<!\\)\|", s)]


def _md_plain(cell):
    # Width measuring only: strip link syntax and emphasis – the
    # cell itself keeps its markup until _md_inline.
    s = re.sub(r"\[([^\]]+)\]\(([^()\s]+)\)", r"\1 (\2)", cell)
    return re.sub(r"[*_`~]", "", s)


# → REF TXT-DOC-6
def _md_wrap_cell(cell, w):
    w = max(1, w)
    if _md_w(_md_plain(cell)) <= w:
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


# → REF TXT-DOC-7
def _md_fmt_row(r, widths, right, bold=False):
    cols = len(widths)
    wrapped = [_md_wrap_cell(r[k] if k < len(r) else "", widths[k])
               for k in range(cols)]
    height = max(len(w) for w in wrapped)
    rows_out = []
    for y in range(height):
        cells = []
        for k in range(cols):
            seg = wrapped[k][y] if y < len(wrapped[k]) else ""
            pad = max(0, widths[k] - _md_w(_md_plain(seg)))
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


# → REF TXT-DOC-8
def _md_widths(demand):
    cols = len(demand)
    sep_w = 3 * (cols - 1)          # " │ " between the columns
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
    # Safety net: even with absurdly many columns, shrink the
    # widest until the budget holds.
    while (sum(widths) + sep_w > _MD_TABLE_BUDGET
           and max(widths) > 1):
        widths[widths.index(max(widths))] -= 1
    return widths


# → REF TXT-DOC-9
def _md_table(lines, i):
    if i + 1 >= len(lines):
        return None
    if not re.search(r"(?<!\\)\|", lines[i]):
        return None
    sep_cells = _md_split_cells(lines[i + 1])
    if not sep_cells:
        return None
    for c in sep_cells:
        if not re.fullmatch(r":?-{2,}:?", c):
            return None
    head = _md_split_cells(lines[i])
    body = []
    j = i + 2
    while j < len(lines):
        s = lines[j]
        if not s.strip() or not re.search(r"(?<!\\)\|", s):
            break
        body.append(_md_split_cells(s))
        j += 1
    cols = len(sep_cells)
    right = [c.endswith(":") and not c.startswith(":")
             for c in sep_cells]
    demand = [0] * cols
    for r in [head] + body:
        for k in range(cols):
            if k < len(r):
                demand[k] = max(demand[k], _md_w(_md_plain(r[k])))
    widths = _md_widths(demand)
    rows = _md_fmt_row(head, widths, right, bold=True)
    rows.append("<tt><span foreground='grey'>%s</span></tt>"
                % "\u253c".join("\u2500" * (w + 2) for w in widths))
    for r in body:
        rows.extend(_md_fmt_row(r, widths, right))
    return rows, j


# → REF TXT-DOC-102
def _mdit_tree(tokens):
    # Flat token stream -> node tree: {"open": tok, "children":
    # [...]} for containers, {"tok": tok} for atoms.
    root = []
    stack = [root]
    for tok in tokens:
        if tok.nesting == 1:
            node = {"open": tok, "children": []}
            stack[-1].append(node)
            stack.append(node["children"])
        elif tok.nesting == -1:
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append({"tok": tok})
    return root


# → REF TXT-DOC-103
def _mdit_text(t):
    # Obsidian dialect on plain text runs: wikilinks, embeds,
    # ==highlight== and %%comments%%. Code spans arrive as their
    # own token type and are never touched.
    t = _pango_escape(t)
    t = re.sub(r"!\[\[([^\]|]+)(?:\|([^\]]*))?\]\]",
               lambda m: "<span size='small'>[Embed: %s]</span>"
               % (m.group(2) or m.group(1)), t)
    t = re.sub(r"(?!!)\[\[([^\]|]+)(?:\|([^\]]*))?\]\]",
               lambda m: ("%s <span size='small' foreground='grey'>%s</span>"
                          % (m.group(2), m.group(1))) if m.group(2)
               else m.group(1), t)
    t = re.sub(r"==([^=\n]+)==",
               r"<span background='yellow'>\1</span>", t)
    t = re.sub(r"%%(.+?)%%", "", t)
    # Extended dialect: subscript/superscript (H~2~O, X^2^) –
    # double tildes/carets are strikethrough territory and never
    # reach this function as text (1.12.1).
    t = re.sub(r"(?<!~)~([^~\n]+)~(?!~)", r"<sub>\1</sub>", t)
    t = re.sub(r"(?<!\^)\^([^\^\n]+)\^(?!\^)", r"<sup>\1</sup>", t)
    return t


# → REF TXT-DOC-104
def _mdit_inline(children):
    # Inline token children -> Pango markup, same look as the
    # legacy parser: link targets in small grey after the text,
    # images as "[Image: alt]" placeholders.
    out = []
    links = []
    for tok in children:
        t = tok.type
        if t == "text":
            out.append(_mdit_text(tok.content))
        elif t == "code_inline":
            out.append("<tt>%s</tt>" % _pango_escape(tok.content))
        elif t == "strong_open":
            out.append("<b>")
        elif t == "strong_close":
            out.append("</b>")
        elif t == "em_open":
            out.append("<i>")
        elif t == "em_close":
            out.append("</i>")
        elif t == "s_open":
            out.append("<s>")
        elif t == "s_close":
            out.append("</s>")
        elif t == "link_open":
            href = ""
            try:
                href = str(tok.attrs.get("href") or "")
            except Exception:
                pass
            links.append(href)
        elif t == "link_close":
            if links:
                href = links.pop()
                if href:
                    out.append(" <span size='small' foreground='grey'>%s</span>"
                               % _pango_escape(href))
        elif t == "image":
            if tok.children:
                alt = _mdit_inline(tok.children)
            else:
                alt = _pango_escape(tok.content or "")
            out.append("<span size='small'>[Image: %s]</span>" % alt)
        elif t in ("softbreak", "hardbreak"):
            out.append("\n")
        elif t == "math_inline":
            out.append("<tt>%s</tt>" % _pango_escape(tok.content.strip()))
        elif t == "footnote_ref":
            n = 1
            try:
                n = int(tok.meta.get("id", 0)) + 1
            except Exception:
                pass
            out.append("[%d]" % n)
        elif t == "html_inline":
            m = re.fullmatch(r"<kbd>(.*?)</kbd>", tok.content.strip())
            if m:
                out.append("<tt>%s</tt>" % _pango_escape(m.group(1)))
            elif re.fullmatch(r"<br\s*/?>", tok.content.strip()):
                out.append("\n")
            else:
                out.append(_pango_escape(re.sub(r"<[^>]*>", "",
                                                tok.content)))
        elif t == "footnote_anchor":
            # Backref arrow of a footnote definition – noise in the
            # text preview; the "[n]" label comes from the block
            # renderer (1.12.1).
            pass
        else:
            # Unknown token shape: render children or content, so
            # plugin output degrades instead of vanishing.
            if tok.children:
                out.append(_mdit_inline(tok.children))
            elif tok.content:
                out.append(_pango_escape(tok.content))
    return "".join(out)


# → REF TXT-DOC-105
def _mdit_strip_task(children):
    # GFM task list: "[ ] "/"[x] " at the start of the item's
    # first paragraph -> checkbox symbol, done items struck
    # through. Returns None when the item is no task.
    for node in children:
        if "open" in node:
            if node["open"].type != "paragraph_open":
                return None
            if not node["children"]:
                return None
            inline = node["children"][0].get("tok")
            if inline is None:
                return None
            m = re.match(r"^\[([ xX])\]\s+", inline.content)
            if not m:
                return None
            done = m.group(1).lower() == "x"
            inline.content = inline.content[m.end():]
            if inline.children and inline.children[0].type == "text":
                c0 = inline.children[0]
                m2 = re.match(r"^\[([ xX])\]\s+", c0.content)
                if m2:
                    c0.content = c0.content[m2.end():]
            return done
        return None
    return None


# → REF TXT-DOC-106
def _mdit_table_lines(node):
    # Rebuild raw GFM table lines from the tokens and hand them to
    # the legacy ASCII table renderer (_md_table) - the column
    # budget, cell wrapping and alignment logic stay unchanged.
    head = None
    styles = []
    rows = []
    for sec in node["children"]:
        for tr in sec["children"]:
            cells = []
            aligns = []
            for cell in tr["children"]:
                st = ""
                op = cell.get("open")
                if op is not None and op.attrs:
                    st = str(op.attrs.get("style") or "")
                aligns.append(st)
                inline = (cell["children"][0].get("tok")
                          if cell["children"] else None)
                raw = inline.content if inline is not None else ""
                cells.append(raw.replace("|", "\\|"))
            if head is None:
                head = cells
                styles = aligns
            else:
                rows.append(cells)
    if head is None:
        return None
    sep = []
    for k in range(len(head)):
        st = styles[k] if k < len(styles) else ""
        if "center" in st:
            sep.append(":---:")
        elif "right" in st:
            sep.append("---:")
        else:
            sep.append("---")
    lines = ["| " + " | ".join(head) + " |",
             "| " + " | ".join(sep) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return lines


# → REF TXT-DOC-107
def _md_gap(out):
    if out and out[-1] != "":
        out.append("")


def _mdit_para_empty(node):
    if "open" not in node or node["open"].type != "paragraph_open":
        return False
    ch = node["children"]
    return (not ch or ch[0].get("tok") is None
            or not ch[0]["tok"].content.strip())


def _mdit_footnote_id(children):
    # Definition paragraphs end with a footnote_anchor token – its
    # id becomes the "[n]" label of the definition line (1.12.1).
    for tok in children or []:
        if tok.type == "footnote_anchor":
            try:
                return int(tok.meta.get("id", 0)) + 1
            except Exception:
                return None
    return None


def _mdit_blocks(nodes, out, lvl=0, quote=0, tight=False):
    # Block token tree -> Pango lines. tight=True (list items)
    # suppresses the blank line between blocks; quote>0 indents
    # and italicizes the lines like the legacy quote rendering.
    for node in nodes:
        seg = []
        if "tok" in node:
            tok = node["tok"]
            t = tok.type
            if t in ("fence", "code_block", "math_block"):
                if not tight:
                    _md_gap(seg)
                lines = tok.content.replace("\t", "    ").split("\n")
                if lines and lines[-1] == "":
                    lines.pop()
                for ln in lines:
                    seg.append("<tt>%s</tt>" % _pango_escape(ln))
            elif t == "hr":
                if not tight:
                    _md_gap(seg)
                seg.append(_md_hr())
            elif t == "front_matter":
                if not tight:
                    _md_gap(seg)
                for ln in tok.content.rstrip("\n").split("\n"):
                    seg.append("<tt><span foreground='grey'>%s</span></tt>"
                               % _pango_escape(ln))
            elif t == "html_block":
                # Raw HTML blocks (e.g. <details>): the summary line
                # renders bold, other tags are stripped (1.12.1).
                if not tight:
                    _md_gap(seg)
                content = tok.content or ""
                m = re.search(r"<summary>(.*?)</summary>", content,
                              re.DOTALL)
                if m:
                    seg.append("<b>%s</b>" % _pango_escape(m.group(1)))
                rest = re.sub(r"<[^>]*>", "", content).strip()
                for ln in rest.split("\n"):
                    if ln.strip():
                        seg.append(_pango_escape(ln))
            elif t == "inline":
                if not tight:
                    _md_gap(seg)
                seg.append(_mdit_inline(tok.children or []))
            else:
                # Unknown atom: keep the raw text visible.
                if tok.content:
                    seg.append(_pango_escape(tok.content))
        else:
            op = node["open"]
            ot = op.type
            if ot in ("bullet_list_open", "ordered_list_open"):
                ordered = ot == "ordered_list_open"
                num = 1
                if ordered and op.attrs:
                    try:
                        num = int(op.attrs.get("start", 1))
                    except Exception:
                        num = 1
                if not tight:
                    _md_gap(seg)
                for item in node["children"]:
                    done = _mdit_strip_task(item["children"])
                    body = []
                    _mdit_blocks(item["children"], body, lvl + 1,
                                 quote, tight=True)
                    if body:
                        if done is None:
                            if ordered:
                                mark = "%d." % num
                            else:
                                mark = _MD_BULLETS[lvl % len(_MD_BULLETS)]
                            body[0] = ("    " * lvl + mark + " "
                                       + body[0])
                        else:
                            sym = "\u2611" if done else "\u2610"
                            if done:
                                body[0] = ("    " * lvl + sym
                                           + " <s>" + body[0] + "</s>")
                            else:
                                body[0] = ("    " * lvl + sym + " "
                                           + body[0])
                    if ordered:
                        num += 1
                    seg.extend(body)
            elif ot == "blockquote_open":
                if not tight:
                    _md_gap(seg)
                kids = node["children"]
                body = []
                if kids and "open" in kids[0] \
                        and kids[0]["open"].type == "paragraph_open" \
                        and kids[0]["children"]:
                    inline = kids[0]["children"][0].get("tok")
                    if inline is not None:
                        m = re.match(r"^\[!(\w+)\]\s*([^\n]*)",
                                     inline.content)
                        if m:
                            # Obsidian callout: [!note] Title ->
                            # bold marker line, rest as quote body.
                            line = "<b>" + _pango_escape(m.group(1))
                            if m.group(2).strip():
                                line += ": " + _mdit_text(m.group(2).strip())
                            body.append(line + "</b>")
                            inline.content = inline.content[m.end():]
                            if inline.children \
                                    and inline.children[0].type == "text":
                                c0 = inline.children[0]
                                m2 = re.match(r"^\[!\w+\]\s*([^\n]*)",
                                              c0.content)
                                if m2:
                                    c0.content = c0.content[m2.end():]
                            if _mdit_para_empty(kids[0]):
                                kids = kids[1:]
                _mdit_blocks(kids, body, lvl, quote + 1, tight=tight)
                for ln in body:
                    if ln == "":
                        seg.append("")
                    else:
                        seg.append("    " * quote + "<i>%s</i>" % ln)
            elif ot == "heading_open":
                if not tight:
                    _md_gap(seg)
                depth = 6
                try:
                    depth = int(op.tag[-1])
                except Exception:
                    pass
                inline = (node["children"][0].get("tok")
                          if node["children"] else None)
                markup = (_mdit_inline(inline.children or [])
                          if inline is not None else "")
                seg.append(_md_heading_markup(depth, markup))
            elif ot == "paragraph_open":
                inline = (node["children"][0].get("tok")
                          if node["children"] else None)
                if inline is not None:
                    if not tight:
                        _md_gap(seg)
                    line = _mdit_inline(inline.children or [])
                    fid = _mdit_footnote_id(inline.children)
                    if fid is not None:
                        line = "[%d] %s" % (fid, line)
                    seg.append(line)
            elif ot == "table_open":
                if not tight:
                    _md_gap(seg)
                lines = _mdit_table_lines(node)
                if lines is not None:
                    tbl = _md_table(lines, 0)
                    if tbl is not None:
                        seg.extend(tbl[0])
            elif ot in ("deflist_open", "dl_open"):
                # Definitions list (1.12.1): the term renders bold,
                # the description indented; unknown token shapes
                # degrade to indented blocks.
                if not tight:
                    _md_gap(seg)
                for item in node["children"]:
                    for part in item["children"]:
                        pt = part["open"].type if "open" in part else ""
                        inline = (part["children"][0].get("tok")
                                  if part["children"] else None)
                        if inline is not None and (
                                pt in ("dt_open", "deflist_title_open")
                                or "title" in pt):
                            seg.append("<b>%s</b>" % _mdit_inline(
                                inline.children or []))
                        else:
                            body = []
                            _mdit_blocks(part["children"], body,
                                         lvl + 1, quote, tight=True)
                            for ln in body:
                                if ln == "":
                                    seg.append("")
                                else:
                                    seg.append("    " + ln)
            else:
                # Unknown container (e.g. the footnote block):
                # render the children like plain blocks.
                if not tight:
                    _md_gap(seg)
                _mdit_blocks(node["children"], seg, lvl, quote,
                             tight=tight)
        out.extend(seg)
    return out


# → REF TXT-DOC-108
def _markdown_mdit_to_pango(text):
    tree = _mdit_tree(_MDIT.parse(text))
    out = []
    _mdit_blocks(tree, out)
    return "\n".join(out)


# → REF TXT-DOC-10
def _markdown_to_pango(text):
    lines = text.split("\n")
    out = []
    in_code = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # --- Code fences (``` … ```) ---
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
        # --- Setext headings: text line + ===== / ------ ---
        # (\x29 = hex escape for the closing paren – keeps the
        # char class out of the paren-diff balance)
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
        # --- Horizontal rules (spaces allowed: - - - / * * *) ---
        if re.fullmatch(r"((?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})",
                        stripped):
            if out and out[-1] != "":
                out.append("")
            out.append(_md_hr())
            i += 1
            continue
        # --- ATX headings (# … ######, trailing # allowed) ---
        m = re.match(r"^(#{1,6})\s+(.*?)(?:\s+#+)?$", stripped)
        if m:
            if out and out[-1] != "":
                out.append("")
            out.append(_md_heading(len(m.group(1)), m.group(2)))
            i += 1
            continue
        # --- GFM tables ---
        tbl = _md_table(lines, i)
        if tbl is not None:
            if out and out[-1] != "":
                out.append("")
            out.extend(tbl[0])
            if tbl[1] < n and lines[tbl[1]].strip():
                out.append("")
            i = tbl[1]
            continue
        # --- Block quotes (nestable: >, >>, > >) ---
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
        # --- Task lists (GFM): - [x] done / - [ ] open ---
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
        # --- Unordered lists with levels ---
        m = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
        if m:
            lvl = len(m.group(1)) // 2
            out.append("    " * lvl
                       + _MD_BULLETS[lvl % len(_MD_BULLETS)] + " "
                       + _md_inline(_pango_escape(m.group(3))))
            i += 1
            continue
        # --- Ordered lists (1. / "1)") ---
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


# --- F83: HTML preview via WebKit2 (→ REF TXT-DOC-110) ---


# → REF TXT-DOC-110
def _md_html_render_front_matter(self, tokens, idx, options, env):
    # The front matter shows as a small monospace block – the
    # plugin alone renders nothing visible.
    return ("<pre class='md-frontmatter'>%s</pre>\n"
            % _pango_escape(tokens[idx].content))


# → REF TXT-DOC-110
def _md_html_render_math_inline(self, tokens, idx, options, env):
    # dollarmath ships no HTML render rules – without these the
    # built-in renderer would die on the token type.
    return "<code>%s</code>" % _pango_escape(
        tokens[idx].content.strip())


# → REF TXT-DOC-110
def _md_html_render_math_block(self, tokens, idx, options, env):
    return ("<pre><code>%s</code></pre>\n"
            % _pango_escape(tokens[idx].content.strip()))


# → REF TXT-DOC-110
_MD_HTML_CODE_RE = re.compile(
    r"(<pre[\s\S]*?</pre>|<code[\s\S]*?</code>)")
_MDIT_CALLOUT_RE = re.compile(r"\[!(\w+)\]\s*")
_MD_HTML_FENCE_RE = re.compile(
    r"<pre><code class=\"language-([\w#+.-]+)\">([\s\S]*?)"
    r"</code></pre>")
_MD_EMBED_IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp",
                      ".svg", ".bmp", ".avif")


# → REF TXT-DOC-110
def _md_html_file_uri(path):
    try:
        return GLib.filename_to_uri(path)
    except Exception:
        return None


# → REF TXT-DOC-110
def _md_html_wikilink(m):
    target = m.group(1).strip()
    label = m.group(2)
    if label is None:
        label = target
    return ("<span class='md-wikilink' title='%s'>%s</span>"
            % (target.replace("'", ""), label))


# → REF TXT-DOC-110
def _md_html_extras(markup, base_dir=None):
    # Obsidian dialect and Pandoc sub/sup on the RENDERED html –
    # the code-split keeps <pre>/<code> segments untouched.
    parts = _MD_HTML_CODE_RE.split(markup)

    def _embed(m):
        target = m.group(1).strip()
        if base_dir:
            full = os.path.join(base_dir, target)
            if (target.lower().endswith(_MD_EMBED_IMG_EXTS)
                    and os.path.exists(full)):
                uri = _md_html_file_uri(full)
                if uri:
                    return ("<img src='%s' alt='%s'>"
                            % (uri, target.replace("'", "")))
        return "<span class='md-embed'>%s</span>" % target

    def _local_img(m):
        src = m.group(1)
        if "://" in src or src.startswith(("data:", "#", "/")):
            return m.group(0)
        if not base_dir:
            return m.group(0)
        full = os.path.join(base_dir, src)
        if not os.path.exists(full):
            return m.group(0)
        uri = _md_html_file_uri(full)
        if not uri:
            return m.group(0)
        return "<img src=\"%s\"" % uri

    for i in range(0, len(parts), 2):
        seg = parts[i]
        seg = re.sub(r"!\[\[([^\]|]+)\]\]", _embed, seg)
        seg = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
                     _md_html_wikilink, seg)
        if base_dir:
            seg = re.sub(r"<img src=\"([^\"]+)\"", _local_img, seg)
        seg = re.sub(r"==([^=\n]+)==", r"<mark>\1</mark>", seg)
        seg = re.sub(r"%%[\s\S]*?%%", "", seg)
        seg = re.sub(r"(?<!~)~([^~\n]+)~(?!~)", r"<sub>\1</sub>", seg)
        seg = re.sub(r"(?<!\^)\^([^\^\n]+)\^(?!\^)",
                     r"<sup>\1</sup>", seg)
        parts[i] = seg
    return "".join(parts)


# → REF TXT-DOC-110
def _md_html_callouts(tokens):
    # GitHub/Obsidian alerts: a blockquote whose first OWN paragraph
    # starts with [!type] gets a class – the title comes from the
    # CSS ::before rule (no extra tokens needed).
    for i, tok in enumerate(tokens):
        if tok.type != "blockquote_open":
            continue
        depth = 0
        for j in range(i + 1, len(tokens)):
            t = tokens[j]
            if t.type == "blockquote_open":
                depth += 1
            elif t.type == "blockquote_close":
                if depth == 0:
                    break
                depth -= 1
            elif t.type == "inline":
                if depth:
                    continue
                m = _MDIT_CALLOUT_RE.match(t.content or "")
                if m and m.group(1).lower() in (
                        "note", "tip", "important", "warning",
                        "caution"):
                    tokens[i].attrSet(
                        "class",
                        "md-callout md-callout-"
                        + m.group(1).lower())
                    if t.children:
                        c0 = t.children[0]
                        if c0.type == "text":
                            c0.content = _MDIT_CALLOUT_RE.sub(
                                "", c0.content, count=1).lstrip()
                        if (len(t.children) > 1
                                and t.children[0].content == ""
                                and t.children[1].type == "softbreak"):
                            del t.children[1]
                break
    return tokens


# → REF TXT-DOC-110
def _md_html_highlight(body, dark):
    # Fenced code with a language gets Pygments colors (inline
    # styles, no external css); unknown languages stay as they are.
    if not HAVE_PYGMENTS:
        return body

    def _sub(m):
        code = html.unescape(m.group(2))
        try:
            lexer = _pyg_lexer(m.group(1), stripall=False)
            fmt = _PygFormatter(noclasses=True,
                                style="monokai" if dark
                                else "default")
            return _pyg_highlight(code, lexer, fmt)
        except Exception as e:
            dbg("text/_md_html_highlight: suppressed: %s" % e)
            return m.group(0)

    return _MD_HTML_FENCE_RE.sub(_sub, body)


# → REF TXT-DOC-110
# B21: this CSS goes through %-string formatting (border, codebg,
# mark, link) – a literal percent sign must be escaped as %% (the
# img max-width rule); raw % killed preview AND print in 1.15.2.
_MD_HTML_CSS = (
    "body{margin:12px;line-height:1.45;}"
    "h1,h2{border-bottom:1px solid %(border)s;padding-bottom:3px;}"
    "a{color:%(link)s;}"
    "code,pre,kbd{font-family:monospace;}"
    "code{background:%(codebg)s;border-radius:3px;padding:1px 4px;"
    "overflow-wrap:anywhere;}"
    "pre{background:%(codebg)s;border-radius:6px;padding:8px;"
    "white-space:pre-wrap;overflow-wrap:anywhere;}"
    "pre code{background:none;padding:0;}"
    "img{max-width:100%%;height:auto;}"
    "kbd{border:1px solid %(border)s;border-radius:3px;"
    "padding:0 4px;background:%(codebg)s;}"
    "blockquote{border-left:3px solid %(border)s;margin-left:0;"
    "margin-right:0;padding-left:10px;}"
    "table{border-collapse:collapse;}"
    "th,td{border:1px solid %(border)s;padding:4px 10px;}"
    "th{background:%(codebg)s;}"
    "li.task-list-item{list-style:none;}"
    "summary{font-weight:600;cursor:pointer;}"
    "mark{background:%(mark)s;}"
    ".md-frontmatter{font-size:0.85em;}"
    ".md-wikilink{color:%(link)s;}"
    ".md-embed{font-family:monospace;font-size:0.85em;"
    "background:%(codebg)s;border-radius:3px;padding:1px 4px;}"
    ".md-callout{border-left-width:4px;}"
    ".md-callout::before{display:block;font-weight:600;"
    "margin-bottom:2px;}"
    ".md-callout-note{border-left-color:#4493f8;}"
    ".md-callout-note::before{content:'NOTE';color:#4493f8;}"
    ".md-callout-tip{border-left-color:#3fb950;}"
    ".md-callout-tip::before{content:'TIP';color:#3fb950;}"
    ".md-callout-important{border-left-color:#ab7df8;}"
    ".md-callout-important::before{content:'IMPORTANT';"
    "color:#ab7df8;}"
    ".md-callout-warning{border-left-color:#d29922;}"
    ".md-callout-warning::before{content:'WARNING';"
    "color:#d29922;}"
    ".md-callout-caution{border-left-color:#f85149;}"
    ".md-callout-caution::before{content:'CAUTION';"
    "color:#f85149;}"
)


# → REF TXT-DOC-110
def _md_html_color(c):
    # Gdk.RGBA to #rrggbb for the css body rule.
    return "#%02x%02x%02x" % (int(round(c.red * 255)),
                              int(round(c.green * 255)),
                              int(round(c.blue * 255)))


# → REF TXT-DOC-110
# B17: the WebView default font is a serif fallback – preview and
# print follow the GTK theme font instead (sans-serif fallback).
_MD_FONT_CACHE = None


def _md_font_family():
    global _MD_FONT_CACHE
    if _MD_FONT_CACHE is None:
        fam = ""
        try:
            fam = Gtk.Settings.get_default().get_property(
                "gtk-font-name") or ""
        except Exception:
            fam = ""
        fam = re.sub(r"\s+[\d.]+$", "", fam.strip()).strip()
        if fam:
            _MD_FONT_CACHE = ("'" + fam.replace("'", "")
                              + "',sans-serif")
        else:
            _MD_FONT_CACHE = "sans-serif"
    return _MD_FONT_CACHE


def _md_html_shell(body, bg, fg, dark, size_px, extra_css=""):
    fgc = "%d,%d,%d" % (int(round(fg.red * 255)),
                        int(round(fg.green * 255)),
                        int(round(fg.blue * 255)))
    css = _MD_HTML_CSS % {
        "border": "rgba(%s,0.35)" % fgc,
        "codebg": "rgba(%s,0.07)" % fgc,
        "mark": "rgba(255,210,0,0.45)" if dark
                else "rgba(255,220,0,0.6)",
        "link": "#6ea8fe" if dark else "#0645ad",
    }
    css += "body{background:%s;color:%s;}" % (_md_html_color(bg),
                                              _md_html_color(fg))
    css += "body{font-family:%s;}" % _md_font_family()
    if size_px:
        css += "body{font-size:%dpx;}" % size_px
    if extra_css:
        css += extra_css
    return ("<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            "<style>%s</style></head><body>%s</body></html>"
            % (css, body))


# → REF TXT-DOC-110
def _markdown_html(text, base_dir=None, bg=None, fg=None, dark=False,
                   size_px=0, extra_css=""):
    # F83: markdown-it-py renders the document to HTML, the Obsidian
    # dialect, local images, code colors and the theme land on top –
    # WebKit only displays the result. F85: extra_css carries the
    # print additions (@page margins).
    if _MDIT_HTML is None:
        raise RuntimeError("markdown-it-py missing")
    env = {}
    tokens = _MDIT_HTML.parse(text)
    _md_html_callouts(tokens)
    body = _MDIT_HTML.renderer.render(tokens, _MDIT_HTML.options,
                                      env)
    body = _md_html_extras(body, base_dir)
    body = _md_html_highlight(body, dark)
    return _md_html_shell(body, bg, fg, dark, size_px, extra_css)


# F83: a SECOND engine for the HTML preview – html=True passes the
# raw HTML of the document through (kbd, br, details), tasklists
# renders the checkboxes. The Pango engine above stays untouched.
_MDIT_HTML = None
if HAVE_MDIT:
    tasklists_plugin = None
    try:
        from mdit_py_plugins.tasklists import tasklists_plugin
    except Exception as e:
        dbg("text/module-level: tasklists missing (%s)" % e)
    try:
        if HAVE_LINKIFY:
            _MDIT_HTML = MarkdownIt("gfm-like", {"html": True})
        else:
            _MDIT_HTML = MarkdownIt("commonmark", {"html": True})
            _MDIT_HTML.enable(["table", "strikethrough"])
        _MDIT_HTML.use(front_matter_plugin)
        _MDIT_HTML.use(footnote_plugin)
        _MDIT_HTML.use(dollarmath_plugin)
        if HAVE_DEFLIST:
            _MDIT_HTML.use(deflist_plugin)
        if tasklists_plugin is not None:
            _MDIT_HTML.use(tasklists_plugin)
        _MDIT_HTML.add_render_rule("front_matter",
                                   _md_html_render_front_matter)
        _MDIT_HTML.add_render_rule("math_inline",
                                   _md_html_render_math_inline)
        _MDIT_HTML.add_render_rule("math_block",
                                   _md_html_render_math_block)
    except Exception as e:
        dbg("text/module-level: markdown-it HTML init failed (%s) "
            "- Pango renderer stays" % e)
        _MDIT_HTML = None


# → REF TXT-DOC-109
def _markdown_markup(owner, text):
    # F67: markdown-it-py engine with the legacy line parser as
    # the fallback - on missing packages, the "legacy" config
    # switch (previewer/markdown_engine) or any render error.
    engine = "markdown-it"
    try:
        engine = getattr(owner, "_conf_markdown_engine",
                         "markdown-it") or "markdown-it"
    except Exception:
        pass
    if engine != "legacy" and _MDIT is not None:
        try:
            return _markdown_mdit_to_pango(text)
        except Exception as e:
            dbg("text/markdown-it: render failed (%s) - legacy "
                "parser" % e)
    return _markdown_to_pango(text)


# → REF TXT-DOC-11
def _html_to_text(text):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# → REF TXT-EML-HTML-1
# F86: EML HTML body – sanitizing and CID resolution. Mail HTML is
# UNTRUSTED: every remote reference (http/https in src/href/...,
# CSS url(), meta refresh, <base>, <script>) is neutralized BEFORE
# the document reaches WebKit – no network request can even start
# (tracking pixels render as empty space). Inline images ride as
# data: URIs resolved from the cid: map.

_EML_CID_TOTAL_CAP = 24 * 1024 * 1024   # R4: cap for all inline parts together


def _eml_cid_map(msg):
    cidmap = {}
    total = 0
    try:
        for part in msg.walk():
            cid = part.get("Content-ID")
            if not cid:
                continue
            cid = str(cid).strip().strip("<>").strip()
            if not cid:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                payload = None
            if not payload:
                continue
            total += len(payload)
            if total > _EML_CID_TOTAL_CAP:
                dbg("text/_eml_cid_map: inline cap reached")
                break
            try:
                mime = part.get_content_type() or "application/octet-stream"
            except Exception:
                mime = "application/octet-stream"
            cidmap[cid.lower()] = (mime, payload)
    except Exception as e:
        dbg("text/_eml_cid_map: suppressed: %s" % e)
    return cidmap


def _eml_cid_sub(match, cidmap):
    attr = match.group(1)
    quote = match.group(2)
    cid = match.group(3)
    entry = cidmap.get(cid.strip().lower())
    if entry is None:
        # Unknown inline part: a transparent placeholder instead of
        # a broken-image icon.
        return (attr + "=" + quote + "data:image/gif;base64,"
                "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
                + quote)
    mime, payload = entry
    return (attr + "=" + quote + "data:" + mime + ";base64,"
            + base64.b64encode(payload).decode("ascii") + quote)


def _eml_html_sanitize(html, cidmap=None):
    # 1) dead markup first: scripts, meta refresh, <base>.
    text = re.sub(r"(?is)<(script)\b[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<meta[^>]+http-equiv\s*=\s*[\"']?refresh"
                  r"[^>]*>", " ", text)
    text = re.sub(r"(?is)<base\b[^>]*>", " ", text)
    # 2) inline images: cid: -> data: URIs (before the remote pass,
    # both go over the same attribute pattern).
    if cidmap:
        text = re.sub(
            r"(?is)\b(src|href|background|poster|srcset)\s*=\s*"
            r"([\"'])cid:([^\"']+)\2",
            lambda m: _eml_cid_sub(m, cidmap), text)
    # 3) remote references: quoted and bare attribute values.
    text = re.sub(
        r"(?is)\b(src|href|background|poster|srcset|action|formaction)"
        r"\s*=\s*([\"'])\s*https?:[^\"']*\2", r"\1=\2\2", text)
    text = re.sub(
        r"(?is)\b(src|href|background|poster|srcset|action|formaction)"
        r"\s*=\s*https?:[^\s>]+", r'\1=""', text)
    # 4) remote CSS references inside <style> blocks and style
    # attributes.
    text = re.sub(r"(?i)url\(\s*[\"']?\s*https?:[^)\"']*[\"']?\s*\)",
                  "url()", text)
    return text


def _eml_html_doc(html, extra_css=""):
    # F86: the mail HTML renders AS THE MAIL built it – on white
    # ground (mails are designed for a light background), with the
    # sanitized body embedded in a minimal shell. A full-document
    # mail keeps its own <html>/<head>; the shell CSS is injected
    # before </head> in that case.
    css = ("body{background:#ffffff;color:#000000;}"
           "img,table{max-width:100%;height:auto;}"
           "p,li,td,th,dd,dt{overflow-wrap:anywhere;}"
           "pre{white-space:pre-wrap;overflow-wrap:anywhere;}")
    if extra_css:
        css += extra_css
    style = "<style>" + css + "</style>"
    if re.search(r"(?i)<html[\s>]", html):
        if re.search(r"(?i)</head\s*>", html):
            return re.sub(r"(?i)</head\s*>", style + "</head>",
                          html, count=1)
        return re.sub(r"(?i)(<html[^>]*>)",
                      lambda m: m.group(1) + style, html, count=1)
    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            + style + "</head><body>" + html + "</body></html>")


# --- E-books: EPUB, FictionBook, MOBI (stdlib only) -------------------------


# → REF TXT-DOC-12
def _xml_local(tag):
    return tag.rsplit("}", 1)[-1]


_EBOOK_CHUNK_CAP = 2 * 1024 * 1024     # R4: max bytes for OPF container documents
_EBOOK_COVER_CAP = 16 * 1024 * 1024    # R4: max bytes for cover images


# → REF TXT-DOC-13
def _meta_rows(pairs):
    return [(k, v) for k, v in pairs if v]


# → REF TXT-DOC-14
def _series_text(series, index):
    if not series:
        return None
    if index:
        return _("%s – Volume %s") % (series, index)
    return series


# → REF TXT-DOC-15
def _ebook_placeholder(w=240, h=360):
    if not HAVE_PANGOCAIRO:
        return None
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        pat = cairo.LinearGradient(0.0, 0.0, 0.0, h)
        pat.add_color_stop_rgba(0.0, 0.90, 0.90, 0.92, 1.0)
        pat.add_color_stop_rgba(1.0, 0.76, 0.76, 0.80, 1.0)
        cr.set_source(pat)
        cr.paint()
        cr.set_source_rgba(0.62, 0.62, 0.66, 1.0)
        cr.rectangle(0, 0, w * 0.09, h)
        cr.fill()
        cr.rectangle(w * 0.18, h * 0.16, w * 0.64, h * 0.075)
        cr.fill()
        for i in range(4):
            cr.rectangle(w * 0.18, h * (0.30 + i * 0.055),
                         w * (0.64 - i * 0.06), h * 0.018)
            cr.fill()
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)
    except Exception as e:
        dbg("E-book placeholder failed (%s)" % e)
        return None


# → REF TXT-DOC-16
def _epub_opf_path(zf, names):
    opf_path = None
    try:
        container = _zf_read_capped(
            zf, "META-INF/container.xml", _EBOOK_CHUNK_CAP).decode(
            "utf-8", "replace")
        m = re.search(r'full-path="([^"]+)"', container)
        if m:
            opf_path = m.group(1)
    except Exception as e:
        dbg("text/_epub_opf_path: suppressed: %s" % e)
    if not opf_path:
        for name in names:
            if name.lower().endswith(".opf"):
                opf_path = name
                break
    if not opf_path:
        raise ValueError("no OPF content file found")
    return opf_path


# → REF TXT-DOC-17
def _epub_metadata(root):
    title = author = lang = None
    manifest = {}          # id -> (href, media type)
    cover_id = None
    series = series_index = pages = None
    coll_id = None         # id of the belongs-to-collection meta (EPUB 3)
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
        elif tag == "meta":
            name = el.get("name") or ""
            prop = el.get("property") or ""
            if name == "cover" and cover_id is None:
                cover_id = el.get("content")
            elif name == "calibre:series" and series is None:
                series = (el.get("content") or "").strip()
            elif (name == "calibre:series_index"
                    and series_index is None):
                series_index = (el.get("content") or "").strip()
            elif prop == "belongs-to-collection" and series is None:
                series = (el.text or "").strip()
                coll_id = el.get("id")
            elif (prop == "group-position" and series_index is None
                    and (not el.get("refines") or not coll_id
                         or el.get("refines") == "#" + coll_id)):
                series_index = (el.text or "").strip()
            elif prop == "page-count" and pages is None:
                pages = (el.text or "").strip()
            elif name == "page-count" and pages is None:
                pages = (el.get("content") or "").strip()
    return (title, author, lang, manifest, cover_id,
            series, series_index, pages)


# → REF TXT-DOC-18
def _epub_cover(zf, names, base, manifest, cover_id):
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
                except KeyError as e:
                    dbg("text/_epub_cover: suppressed: %s" % e)
    return cover


# → REF TXT-DOC-19
def _epub_data(path):
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        # → REF TXT-EPUB-1
        opf_path = _epub_opf_path(zf, names)
        base = (opf_path.rsplit("/", 1)[0] + "/") if "/" in opf_path else ""
        opf_raw = _zf_read_capped(zf, opf_path, _EBOOK_CHUNK_CAP)
        # R10: OPF ships without DTD – entity guard before parsing.
        if _xml_dtd_rejected(opf_raw, "EPUB-OPF " + opf_path):
            raise ValueError("DOCTYPE in the OPF (R10 entity guard)")
        root = ElementTree.fromstring(opf_raw)
        (title, author, lang, manifest, cover_id,
         series, series_index, pages) = _epub_metadata(root)
        cover = _epub_cover(zf, names, base, manifest, cover_id)
    return (_meta_rows(((_("Book title"), title), (_("Author"), author),
                         (_("Part of a series"), _series_text(series,
                                                           series_index)),
                         (_("Number of pages"), pages),
                         (_("E-book format"), "EPUB"), (_("Language"), lang))),
            cover)


# → REF TXT-DOC-20
def _fb2_metadata(root):
    title = author = lang = None
    cover_ref = None
    series = seq_index = None
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
        elif tag == "lang" and lang is None:
            lang = (el.text or "").strip()
        elif tag == "coverpage" and cover_ref is None:
            for child in el:
                if _xml_local(child.tag) == "image":
                    cover_ref = (child.get("l:href") or
                                 child.get("href") or "").lstrip("#")
        elif tag == "sequence" and series is None:
            series = (el.get("name") or "").strip() or None
            seq_index = (el.get("number") or "").strip() or None
    return title, author, lang, cover_ref, series, seq_index


# → REF TXT-DOC-21
def _fb2_cover(root, cover_ref):
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
    return cover


# → REF TXT-DOC-22
def _fb2_data(path):
    with open(path, "rb") as fh:
        raw = fh.read(_FB2_FILE_CAP)
    # R10: FB2 ships without DTD – entity guard before parsing.
    if _xml_dtd_rejected(raw, "FB2 " + path):
        raise ValueError("DOCTYPE in the FB2 file (R10 entity guard)")
    root = ElementTree.fromstring(raw).getroot()
    title, author, lang, cover_ref, series, seq_index = _fb2_metadata(root)
    cover = _fb2_cover(root, cover_ref)
    return (_meta_rows(((_("Book title"), title), (_("Author"), author),
                         (_("Part of a series"), _series_text(series,
                                                           seq_index)),
                         (_("E-book format"), "FB2"), (_("Language"), lang))),
            cover)


_MOBI_MAX_BYTES = 8 * 1024 * 1024   # B5: title and EXTH data sit at the file
                                    # start anyway – read only up to here


# → REF TXT-DOC-23
def _mobi_records(data):
    num_rec = struct.unpack(">H", data[76:78])[0]
    rec_offs = []
    for i in range(num_rec):
        p = 78 + 8 * i
        if p + 4 > len(data):
            break
        # PDB record entries store the offset as four big-endian
        # bytes; attributes and unique id follow after them.
        rec_offs.append(struct.unpack(">I", data[p:p + 4])[0])
    if not rec_offs:
        raise ValueError(_("no records"))
    recs = []
    for i, off in enumerate(rec_offs):
        end = rec_offs[i + 1] if i + 1 < len(rec_offs) else len(data)
        if off < end <= len(data):
            recs.append(data[off:end])
    return recs


# → REF TXT-DOC-24
def _mobi_header(recs):
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
        # EXTH header: entry type 100 = author
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
    return compression, encoding, first_non_book, author


# → REF TXT-DOC-25
def _mobi_data(path):
    with open(path, "rb") as fh:
        data = fh.read(_MOBI_MAX_BYTES)
    if len(data) < 88 or data[60:68] not in (b"BOOKMOBI", b"TEXtREAd"):
        raise ValueError("not a MOBI container")
    title = data[0:32].split(b"\x00")[0].decode("utf-8", "replace").strip()
    recs = _mobi_records(data)
    author = _mobi_header(recs)[3]
    return (_meta_rows(((_("Book title"), title), (_("Author"), author),
                         (_("E-book format"), "MOBI"))), None)


# --- Packages: DEB, RPM, Arch/Pacman (stdlib only) --------------------------

_PKG_CONTROL_CAP = 2 * 1024 * 1024      # F60: max bytes from control member
_PKG_HEADER_CAP = 4 * 1024 * 1024       # F60: max bytes from an rpm head zone
_PKG_ICON_SCAN_CAP = 8 * 1024 * 1024    # F60: decompression budget icon hunt
                                        # 0.45.1: 48 MB slowed huge packages
                                        # down – the info table does not wait
                                        # for the payload; 8 MB suffice for
                                        # the best-effort icon
_PKG_ICON_BYTES = 2 * 1024 * 1024       # F60: max bytes of one icon member


# → REF TXT-DOC-26
class _WindowReader:

    def __init__(self, fh, offset, budget):
        self._fh = fh
        self._left = budget
        fh.seek(offset)

    def read(self, size=-1):
        if self._left <= 0:
            raise EOFError("F60: icon budget exhausted")
        if size < 0 or size > self._left:
            size = self._left
        data = self._fh.read(size)
        self._left -= len(data)
        return data

    def readable(self):
        return True


# → REF TXT-DOC-27
def _tar_sniff_mode(data, stream=False):
    if data[:2] == b"\x1f\x8b":
        return "r|gz" if stream else "r:gz"
    if data[:6] == b"\xfd7zXZ\x00":
        return "r|xz" if stream else "r:xz"
    if data[:4] == b"\x28\xb5\x2f\xfd":
        return None
    return "r|" if stream else "r:"


# → REF TXT-DOC-28
def _pkg_icon_score(name, size):
    low = name.lower()
    if size > _PKG_ICON_BYTES or not low.endswith(
            (".png", ".jpg", ".jpeg")):
        return None
    if "/icons/" not in low and "/pixmaps/" not in low:
        return None
    score = 0
    if "48x48" in low:
        score -= 2
    if "/apps/" in low:
        score -= 1
    return score


# → REF TXT-DOC-29
def _deb_control_fields(raw):
    fields = {}
    cur = None
    for line in raw.decode("utf-8", "replace").splitlines():
        if line[:1] in (" ", "\t"):
            if cur is not None:
                txt = line.strip()
                fields[cur] += "\n" + ("\n" if txt == "." else txt)
        elif ":" in line:
            key, _, val = line.partition(":")
            cur = key.strip()
            if cur:
                fields.setdefault(cur, val.strip())
    return fields


# → REF TXT-DOC-30
def _kb_size(kb):
    try:
        return human_size(int(kb) * 1024)
    except (TypeError, ValueError):
        return None


# → REF TXT-DOC-31
def _deb_rows(fields):
    short, sep, long = (fields.get("Description") or "").partition("\n")
    rows = [(_("Package name"), fields.get("Package")),
            (_("Version"), fields.get("Version")),
            (_("Architecture"), fields.get("Architecture")),
            (_("Package format"), "DEB"),
            (_("Section"), fields.get("Section")),
            (_("Short description"), short.strip()),
            (_("Description"), long.strip("\n").strip()),
            (_("Installed size"), _kb_size(fields.get("Installed-Size"))),
            (_("Dependencies"), fields.get("Depends")),
            (_("Recommendations"), fields.get("Recommends")),
            (_("Maintainer"), fields.get("Maintainer")),
            (_("Homepage"), fields.get("Homepage"))]
    return _meta_rows(rows)


# → REF TXT-DOC-32
def _deb_icon(path, member):
    offset, size, name = member
    with open(path, "rb") as fh:
        fh.seek(offset)
        mode = _tar_sniff_mode(fh.read(6), stream=True)
        if mode is None:
            return None
        tf = tarfile.open(fileobj=_WindowReader(fh, offset,
                                                _PKG_ICON_SCAN_CAP),
                          mode=mode)
        best = None
        for m in tf:
            score = _pkg_icon_score((m.name or "").lstrip("./"), m.size)
            if score is None or (best is not None and score >= best[0]):
                continue
            best = (score, tf.extractfile(m).read())
            if best[0] <= -3:
                break
        return best[1] if best else None


# → REF TXT-DOC-33
def _deb_data(path):
    control = None
    data_member = None
    with open(path, "rb") as fh:
        if fh.read(8) != b"!<arch>\n":
            raise ValueError("not a Debian package (ar magic missing)")
        while True:
            head = fh.read(60)
            if len(head) < 60:
                break
            # 0.45.1: IEEE ar names often end with a slash
            # ('control.tar.gz/') – rstrip("/") or no member
            # dispatch matches (compression: sniffing, not name).
            name = head[0:16].decode("ascii", "replace").strip()
            name = name.rstrip("/")
            try:
                size = int(head[48:58].decode("ascii", "replace").strip())
            except ValueError:
                raise ValueError("ar member header unreadable")
            body = fh.tell()
            if name.startswith("control.tar"):
                raw = fh.read(min(size, _PKG_CONTROL_CAP))
                mode = _tar_sniff_mode(raw)
                if mode is None:
                    raise ValueError("control.tar.zst – zstd is not a "
                                     "stdlib capability")
                tf = tarfile.open(fileobj=io.BytesIO(raw), mode=mode)
                for m in tf:
                    if (m.name or "").lstrip("./") == "control":
                        control = tf.extractfile(m).read()
                        break
                tf.close()
            elif name.startswith("data.tar"):
                data_member = (body, size, name)
            fh.seek(body + size + size % 2)
    if control is None:
        raise ValueError("no control file in the package")
    rows = _deb_rows(_deb_control_fields(control))
    icon = None
    if data_member is not None:
        try:
            icon = _deb_icon(path, data_member)
        except Exception as e:
            dbg("F60 deb icon: suppressed: %s" % e)
    return rows, icon


# → REF TXT-DOC-34
def _rpm_section(data, pos):
    if data[pos:pos + 3] != b"\x8e\xad\xe8":
        raise ValueError(_("RPM header magic missing at offset %d") % pos)
    n, size = struct.unpack(">II", data[pos + 8:pos + 16])
    i0 = pos + 16
    if i0 + 16 * n + size > len(data):
        raise ValueError(_("RPM header larger than the read buffer"))
    index = [struct.unpack(">IIII", data[i0 + 16 * i:i0 + 16 * i + 16])
             for i in range(n)]
    store = data[i0 + 16 * n:i0 + 16 * n + size]
    return index, store, i0 + 16 * n + size


# → REF TXT-DOC-35
def _rpm_value(index, store, tag):
    for (t, typ, off, cnt) in index:
        if t != tag or off >= len(store):
            continue
        chunk = store[off:]
        if typ in (7, 9):
            return chunk.split(b"\x00", 1)[0].decode("utf-8", "replace")
        if typ == 6:
            parts = chunk.split(b"\x00")
            if cnt and 0 < cnt <= len(parts):
                parts = parts[:cnt]
            out = [p.decode("utf-8", "replace") for p in parts if p]
            return out or None
        if typ == 4 and off + 4 <= len(store):
            return struct.unpack(">i", store[off:off + 4])[0]
    return None


# → REF TXT-DOC-36
def _rpm_rows(index, store):
    def s(tag):
        val = _rpm_value(index, store, tag)
        return val.strip() if isinstance(val, str) and val.strip() else None
    ver, rel = s(1001), s(1002)
    version = "%s-%s" % (ver, rel) if ver and rel else (ver or rel)
    size = _rpm_value(index, store, 1009)
    size = human_size(size) if isinstance(size, int) else None
    reqs = _rpm_value(index, store, 1049)
    if isinstance(reqs, list):
        reqs = ", ".join(r for r in reqs if not r.startswith(
            ("rpmlib(", "config(", "rtld(")))
    else:
        reqs = None
    rows = [(_("Package name"), s(1000)),
            (_("Version"), version),
            (_("Architecture"), s(1022)),
            (_("Package format"), "RPM"),
            (_("Summary"), s(1004)),
            (_("Description"), s(1005)),
            (_("Group"), s(1016)),
            (_("License"), s(1014)),
            (_("Installed size"), size),
            (_("Dependencies"), reqs),
            (_("Maintainer"), s(1015)),
            (_("Homepage"), s(1020))]
    return _meta_rows(rows)


# → REF TXT-DOC-37
def _rpm_data(path):
    with open(path, "rb") as fh:
        data = fh.read(_PKG_HEADER_CAP)
    if len(data) < 96 or data[0:4] != b"\xed\xab\xee\xdb":
        raise ValueError("not an RPM (lead magic missing)")
    _, _, end = _rpm_section(data, 96)
    pos = end + (-end) % 8
    try:
        index, store, _ = _rpm_section(data, pos)
    except ValueError:
        index, store, _ = _rpm_section(data, end + (-end) % 16)
    return _rpm_rows(index, store), None


# → REF TXT-DOC-38
def _pkginfo_fields(raw):
    single = {}
    multi = {"depend": [], "optdepend": [], "makedepend": [],
             "license": [], "group": []}
    for line in raw.decode("utf-8", "replace").splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if not key or not val:
            continue
        if key in multi:
            multi[key].append(val)
        else:
            single.setdefault(key, val)
    return single, multi


# → REF TXT-DOC-39
def _pkg_rows(single, multi):
    ver, rel = single.get("pkgver"), single.get("pkgrel")
    version = "%s-%s" % (ver, rel) if ver and rel else (ver or rel)
    try:
        size = human_size(int(single.get("size")))
    except (TypeError, ValueError):
        size = None
    rows = [(_("Package name"), single.get("pkgname")),
            (_("Version"), version),
            (_("Architecture"), single.get("arch")),
            (_("Package format"), "Pacman"),
            (_("Short description"), single.get("pkgdesc")),
            (_("Installed size"), size),
            (_("Dependencies"), ", ".join(multi["depend"])),
            (_("Optional dependencies"), ", ".join(multi["optdepend"])),
            (_("License"), ", ".join(multi["license"])),
            (_("Maintainer"), single.get("packager")),
            (_("Homepage"), single.get("url"))]
    return _meta_rows(rows)


# → REF TXT-DOC-40
def _pkg_data(path):
    if path.lower().endswith(".pkg.tar.zst"):
        raise ValueError("pkg.tar.zst – zstd is not a stdlib capability")
    single = None
    multi = {}
    best = None
    with open(path, "rb") as fh:
        tf = tarfile.open(fileobj=_WindowReader(fh, 0,
                                                _PKG_ICON_SCAN_CAP),
                          mode="r|xz")
        try:
            for m in tf:
                name = (m.name or "").lstrip("./")
                if name == ".PKGINFO" and single is None:
                    single, multi = _pkginfo_fields(
                        tf.extractfile(m).read())
                else:
                    score = _pkg_icon_score(name, m.size)
                    if (score is None or (best is not None
                                         and score >= best[0])):
                        continue
                    best = (score, tf.extractfile(m).read())
                    if best[0] <= -3 and single is not None:
                        break
        except Exception as e:
            dbg("F60 pkg stream: suppressed: %s" % e)
    if single is None:
        raise ValueError("no .PKGINFO in the package")
    return _pkg_rows(single, multi), (best[1] if best else None)


# → REF TXT-DOC-41
def _package_placeholder(fmt, w=240, h=200):
    if not HAVE_PANGOCAIRO:
        return None
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        pat = cairo.LinearGradient(0.0, 0.0, 0.0, h)
        pat.add_color_stop_rgba(0.0, 0.90, 0.90, 0.92, 1.0)
        pat.add_color_stop_rgba(1.0, 0.76, 0.76, 0.80, 1.0)
        cr.set_source(pat)
        cr.paint()
        cr.set_source_rgba(0.62, 0.62, 0.66, 1.0)
        cr.rectangle(w * 0.18, h * 0.22, w * 0.64, h * 0.10)
        cr.fill()
        cr.rectangle(w * 0.22, h * 0.32, w * 0.56, h * 0.46)
        cr.fill()
        pl = PangoCairo.create_layout(cr)
        pl.set_text(fmt, -1)
        pl.set_font_description(
            Pango.FontDescription.from_string("Sans Bold 28"))
        pw, ph = pl.get_size()
        cr.set_source_rgba(0.35, 0.35, 0.40, 1.0)
        cr.move_to((w - pw / 1024.0) / 2.0,
                   h * 0.55 - ph / 1024.0 / 2.0)
        PangoCairo.show_layout(cr, pl)
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)
    except Exception as e:
        dbg("Package placeholder failed (%s)" % e)
        return None


# --- Fonts: waterfall for TrueType/OpenType (stdlib) -------------------------

_FONT_SIZES = (8, 11, 14, 18, 24, 36)
_FONT_SAMPLE_TEXT = ("The quick brown fox jumps over the "
                     "lazy dog")
# Process state (no global keyword, project convention): temp dir
# for the fontconfig takeover, taken-over paths, ordered copy list.
_FONT_STATE = {"tmpdir": None, "added": set(), "copies": []}
# R5: cap the temp dir at 64 copies – fontconfig keeps deleted
# fonts in memory until the process ends; the dir must not grow forever.
_FONT_COPY_LIMIT = 64
# F11: collection cap – more faces would flood the preview.
_TTC_FACE_CAP = 8


# → REF TXT-DOC-99
def _woff1_to_sfnt(data):
    # F11: WOFF1 (wOFF) packs zlib-compressed sfnt tables –
    # rebuild a plain sfnt (WOFF2/wOF2 is NOT supported).
    if len(data) < 44 or data[0:4] != b"wOFF":
        raise ValueError("not a WOFF1 file")
    if data[4:8] == b"ttcf":
        raise ValueError("WOFF1 cannot wrap a collection")
    flavor = data[4:8]
    num_tables = int.from_bytes(data[12:14], "big")
    if num_tables == 0 or 44 + 20 * num_tables > len(data):
        raise ValueError("WOFF directory broken")
    tables = []
    for i in range(num_tables):
        p = 44 + 20 * i
        tag, toff, clen, olen, cks = struct.unpack(
            ">4sIIII", data[p:p + 20])
        if toff + clen > len(data):
            raise ValueError("WOFF table out of range")
        raw = data[toff:toff + clen]
        if clen != olen:
            raw = zlib.decompress(raw)
        if len(raw) != olen:
            raise ValueError("WOFF table broken")
        tables.append((tag, cks, raw))
    # Tables sorted by tag, data padded to 4 bytes each.
    tables.sort(key=lambda t: t[0])
    n = len(tables)
    sr = 1
    while sr * 2 <= n:
        sr *= 2
    out = bytearray(flavor)
    out += struct.pack(">HHHH", n, sr * 16, sr.bit_length() - 1,
                       n * 16 - sr * 16)
    pos = 12 + 16 * n
    entries = bytearray()
    body = bytearray()
    for tag, cks, raw in tables:
        entries += struct.pack(">4sIII", tag, cks, pos, len(raw))
        body += raw
        pad = (-len(raw)) % 4
        body += b"\x00" * pad
        pos += len(raw) + pad
    return bytes(out + entries + body)


# → REF TXT-DOC-100
def _sfnt_face_names(data, offset):
    # Name table of ONE sfnt face (TTC: every face has its own
    # directory at its own offset).
    if offset + 12 > len(data):
        raise ValueError("face offset broken")
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
        raise ValueError("name table missing")
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
            if plat in (0, 3):            # Unicode or Windows: UTF-16BE
                text = raw.decode("utf-16-be", "replace")
            else:                          # Mac etc.: roughly Latin-1
                text = raw.decode("latin-1", "replace")
        except Exception:
            continue
        text = text.strip("\x00 ").strip()
        if text:
            recs.setdefault(nid, text)
    family = recs.get(1) or recs.get(16) or recs.get(4)
    style = recs.get(2) or recs.get(17)
    if not family:
        raise ValueError("no family name in the file")
    return family, style or "Regular"


# → REF TXT-DOC-42
def _font_faces(path):
    # F11: WOFF1 rebuilt to sfnt, collections list EVERY face.
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 12:
        raise ValueError("file too small")
    tag = data[0:4]
    reg = path
    if tag == b"wOFF":
        # F11: Fontconfig cannot read WOFF – the rebuilt sfnt is
        # parked in the font temp dir (→ REF TXT-FONT-3).
        sfnt = _woff1_to_sfnt(data)
        state = _FONT_STATE
        if state["tmpdir"] is None:
            state["tmpdir"] = tempfile.mkdtemp(
                prefix="previewer-font-")
        stem = os.path.splitext(os.path.basename(path))[0]
        digest = hashlib.sha1(os.path.abspath(path).encode(
            "utf-8", "replace")).hexdigest()[:8]
        reg = os.path.join(state["tmpdir"],
                           "%s-%s.ttf" % (stem, digest))
        if not os.path.exists(reg):
            with open(reg, "wb") as fh:
                fh.write(sfnt)
            # → REF TXT-FONT-1 (R5 temp dir cap)
            state["copies"].append(reg)
            while len(state["copies"]) > _FONT_COPY_LIMIT:
                old = state["copies"].pop(0)
                try:
                    os.unlink(old)
                except Exception as e:
                    dbg("text/_font_faces: suppressed: %s" % e)
        data = sfnt
        tag = data[0:4]
        fmt = ("OpenType (CFF)" if tag == b"OTTO" else "TrueType")
        fmt += _(" (WOFF)")
        faces = [_sfnt_face_names(data, 0)]
    elif tag == b"wOF2":
        raise ValueError(_("WOFF2 is not supported"))
    elif tag == b"ttcf":
        num = int.from_bytes(data[8:12], "big")
        if num == 0:
            raise ValueError("collection without fonts")
        faces = []
        for i in range(num):
            p = 12 + 4 * i
            if p + 4 > len(data):
                raise ValueError("collection offset broken")
            off = int.from_bytes(data[p:p + 4], "big")
            try:
                faces.append(_sfnt_face_names(data, off))
            except Exception:
                pass          # one broken face does not kill all
        if not faces:
            raise ValueError("no readable font in the collection")
        first = int.from_bytes(data[12:16], "big")
        fmt = ("OpenType-Collection (CFF)"
               if data[first:first + 4] == b"OTTO"
               else "TrueType-Collection")
    elif tag == b"OTTO":
        fmt = "OpenType (CFF)"
        faces = [_sfnt_face_names(data, 0)]
    elif tag in (b"true", b"\x00\x01\x00\x00"):
        fmt = "TrueType"
        faces = [_sfnt_face_names(data, 0)]
    else:
        raise ValueError("not a TrueType/OpenType file")
    return reg, fmt, faces


# → REF TXT-DOC-43
def _fc_add_font_file(path):
    state = _FONT_STATE
    if path in state["added"]:
        return True
    try:
        if state["tmpdir"] is None:
            state["tmpdir"] = tempfile.mkdtemp(prefix="previewer-font-")
        # F11: rebuilt WOFF sfnts already live in the temp dir –
        # no second copy of them.
        if os.path.dirname(os.path.abspath(path)) != state["tmpdir"]:
            # Target name with a hash of the SOURCE path: two fonts
            # with the same file name must not clash (B1) – first
            # copy would win.
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
                    except Exception as e:
                        dbg("text/_fc_add_font_file: suppressed: %s" % e)
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


# → REF TXT-DOC-44
def _font_known(font_map, family):
    try:
        low = family.lower()
        for fam in font_map.list_families():
            if (fam.get_name() or "").lower() == low:
                return True
        return False
    except Exception:
        return True      # check impossible – do not block


# → REF TXT-DOC-97
def _font_waterfall_pixbuf(family, fctx, fg, text, target_w):
    # Waterfall surface at DOUBLE the current preview width –
    # scaled down for display; the wrap follows the column (F68).
    s = 2
    surf_w = max(200, target_w * s)
    pad = 8 * s
    tag_fd = Pango.FontDescription()
    tag_fd.set_size(9 * Pango.SCALE * s)
    pairs = []
    total_h = 2 * pad
    for size in _FONT_SIZES:
        tag_l = Pango.Layout.new(fctx)
        tag_l.set_font_description(tag_fd)
        tag_l.set_text(_("%d pt") % size, -1)
        text_fd = Pango.FontDescription()
        text_fd.set_family(family)
        text_fd.set_size(size * Pango.SCALE * s)
        text_l = Pango.Layout.new(fctx)
        text_l.set_font_description(text_fd)
        # F12: the sample text comes from the configuration –
        # editable in the "Fonts" section (→ REF TXT-FONT-2).
        text_l.set_text(text, -1)
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
    return Gdk.pixbuf_get_from_surface(surf, 0, 0, surf_w, total_h)


# ============================ Renderer: text ================================


# --- vCard (F7): parser and card helpers ------------------------------------

# → REF TXT-DOC-45
def _vcard_unfold(text):
    out = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not out:
            out.append(line)
        elif line[:1] in (" ", "\t"):
            out[-1] += line[1:]
        elif (out[-1].endswith("=")
                and "QUOTED-PRINTABLE" in out[-1].upper()):
            out[-1] = out[-1][:-1] + line
        else:
            out.append(line)
    return out


# → REF TXT-DOC-46
def _vcard_split(line):
    idx = line.find(":")
    if idx < 0:
        return None
    head, value = line[:idx], line[idx + 1:]
    parts = head.split(";")
    name = parts[0].strip().upper()
    if "." in name:
        # vCard 3.0 group prefix (item1.TEL): strip it
        name = name.split(".")[-1]
    params = {}
    for p in parts[1:]:
        p = p.strip()
        if not p:
            continue
        if "=" in p:
            key, raw = p.split("=", 1)
            params.setdefault(key.strip().upper(), []).extend(
                v.strip().upper() for v in raw.split(","))
        else:
            params.setdefault("TYPE", []).append(p.upper())
    return name, params, value


# → REF TXT-DOC-47
def _vcard_parse(text):
    cards, cur = [], None
    for line in _vcard_unfold(text):
        up = line.strip().upper()
        if up.startswith("BEGIN:VCARD"):
            cur = []
        elif up.startswith("END:VCARD"):
            if cur is not None:
                cards.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            prop = _vcard_split(line)
            if prop is None:
                continue
            name, params, value = prop
            if "QUOTED-PRINTABLE" in params.get("ENCODING", []):
                charset = (params.get("CHARSET", ["utf-8"])[0]
                           or "utf-8").lower()
                try:
                    value = quopri.decodestring(
                        value.encode("latin-1", "replace")
                    ).decode(charset, "replace")
                except Exception as e:
                    dbg("text/_vcard_parse: suppressed: %s" % e)
            cur.append((name, params, value))
    return cards


# → REF TXT-DOC-48
def _vcard_unescape(v):
    return (v.replace("\\n", "\n").replace("\\N", "\n")
             .replace("\\,", ",").replace("\\;", ";")
             .replace("\\\\", "\\"))


# → REF TXT-DOC-49
def _vcard_props(card, name):
    return [(params, value) for (n, params, value) in card
            if n == name]


# → REF TXT-DOC-50
def _vcard_first(card, name):
    for params, value in _vcard_props(card, name):
        v = _vcard_unescape(value).strip()
        if v:
            return v
    return ""


# → REF TXT-DOC-51
def _vcard_display_name(card):
    v = _vcard_first(card, "FN")
    if v:
        return v
    for params, value in _vcard_props(card, "N"):
        parts = [_vcard_unescape(p).strip() for p in value.split(";")]
        parts += [""] * (5 - len(parts))
        name = " ".join(x for x in (parts[3], parts[1], parts[0]) if x)
        if name:
            return name
    return _vcard_first(card, "NICKNAME") or _("(no name)")


_VCARD_TEL_LABELS = (("CELL", "Mobile"), ("HOME", "Home"),
                     ("WORK", "Work"), ("FAX", "Fax"),
                     ("VOICE", "Phone"))


# → REF TXT-DOC-52
def _vcard_tel_label(params):
    types = set(params.get("TYPE", []))
    for key, label in _VCARD_TEL_LABELS:
        if key in types:
            return _(label)
    return _("Phone")


# → REF TXT-DOC-53
def _vcard_adr(value):
    parts = [_vcard_unescape(p).strip() for p in value.split(";")]
    parts += [""] * (7 - len(parts))
    street, city = parts[1], parts[3]
    region, zipcode, country = parts[4], parts[5], parts[6]
    line = ", ".join(x for x in (street, " ".join(
        y for y in (zipcode, city) if y)) if x)
    tail = ", ".join(x for x in (region, country) if x)
    return " – ".join(x for x in (line, tail) if x)


# → REF TXT-DOC-54
def _vcard_bday(value):
    v = value.strip()
    if re.fullmatch(r"\d{8}", v):
        return "%s.%s.%s" % (v[6:8], v[4:6], v[0:4])
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "%s.%s.%s" % (v[8:10], v[5:7], v[0:4])
    return v


# → REF TXT-DOC-55
def _vcard_photo(card):
    for params, value in _vcard_props(card, "PHOTO"):
        encs = params.get("ENCODING", []) + params.get("TYPE", [])
        if "B" in encs or "BASE64" in encs:
            try:
                return base64.b64decode(re.sub(r"\s+", "", value))
            except Exception:
                continue
        raw = value.strip()
        vals = params.get("VALUE", [])
        looks_uri = ("URI" in vals or "URL" in vals or "URI" in encs
                     or raw[:5].upper() == "FILE:" or raw[:1] == "/")
        if not looks_uri:
            continue
        try:
            path = (GLib.filename_from_uri(raw)[0]
                    if raw[:5].upper() == "FILE:" else raw)
            if path and os.path.isfile(path):
                with open(path, "rb") as fh:
                    return fh.read(16 * 1024 * 1024)
        except Exception:
            continue
    return None


# → REF TXT-DOC-56
def _vcard_circle(pb, size=160):
    try:
        w, h = pb.get_width(), pb.get_height()
        if w < 1 or h < 1:
            return None
        side = min(w, h)
        pb = pb.new_subpixbuf((w - side) // 2, (h - side) // 2,
                              side, side)
        pb = pb.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        if pb is None or not HAVE_PANGOCAIRO:
            return pb
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        cr.arc(size / 2.0, size / 2.0, size / 2.0 - 1.0,
               0.0, 2 * math.pi)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        out = Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)
        return out if out is not None else pb
    except Exception as e:
        dbg("vCard circle mask failed (%s) – square photo" % e)
        return pb


# → REF TXT-DOC-57
def _vcard_placeholder(size=160):
    if not HAVE_PANGOCAIRO:
        return None
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        half = size / 2.0
        cr.arc(half, half, half, 0.0, 2 * math.pi)
        cr.clip()
        pat = cairo.LinearGradient(0.0, 0.0, 0.0, size)
        pat.add_color_stop_rgba(0.0, 0.90, 0.90, 0.92, 1.0)
        pat.add_color_stop_rgba(1.0, 0.76, 0.76, 0.80, 1.0)
        cr.set_source(pat)
        cr.paint()
        cr.set_source_rgba(0.62, 0.62, 0.66, 1.0)
        cr.arc(half, half - size * 0.10, size * 0.19,
               0.0, 2 * math.pi)
        cr.fill()
        cr.arc(half, half + size * 0.42, size * 0.34,
               math.pi, 2 * math.pi)
        cr.fill()
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)
    except Exception as e:
        dbg("vCard placeholder failed (%s) – icon fallback" % e)
        return None


# --- LDIF (F7): address book exports as cards --------------------------------

# → REF TXT-DOC-58
def _ldif_unfold(text):
    out = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not out:
            out.append(line)
        elif line[:1] == " ":
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


# → REF TXT-DOC-59
def _ldif_record(attrs):
    def vals(key):
        return [v for (k, v) in attrs if k == key]

    fn = (vals("cn") + vals("displayname") + vals("fullname"))[:1]
    given = vals("givenname")[:1]
    family = vals("sn")[:1]
    if not (fn or given or family or vals("mail")):
        return None
    card = []
    if fn:
        card.append(("FN", {}, fn[0]))
    elif given or family:
        card.append(("FN", {},
                     " ".join(x for x in (given[0] if given else "",
                                         family[0] if family else "")
                              if x)))
    org = (vals("o") + vals("organization") + vals("company"))[:1]
    if org:
        card.append(("ORG", {}, org[0]))
    title = vals("title")[:1]
    if title:
        card.append(("TITLE", {}, title[0]))
    for v in vals("mail"):
        card.append(("EMAIL", {}, v))
    for v in vals("telephonenumber"):
        card.append(("TEL", {}, v))
    for v in vals("mobile"):
        card.append(("TEL", {"TYPE": ["CELL"]}, v))
    for v in vals("homephone"):
        card.append(("TEL", {"TYPE": ["HOME"]}, v))
    for v in vals("facsimiletelephonenumber"):
        card.append(("TEL", {"TYPE": ["FAX"]}, v))
    for v in (vals("labeleduri") + vals("url") + vals("mozillaworkurl")
              + vals("mozillahomeurl")):
        card.append(("URL", {}, v))
    for v in (vals("homepostaladdress") + vals("postaladdress")
              + vals("mozillahomepostaladdress")
              + vals("mozillaworkpostaladdress")):
        card.append(("ADR", {}, ";" + v.replace("$", ", ")))
    for v in vals("description") + vals("notes"):
        card.append(("NOTE", {}, v))
    for v in vals("nickname") + vals("mozillanickname"):
        card.append(("NICKNAME", {}, v))
    for v in vals("birthday"):
        card.append(("BDAY", {}, v))
    # jpegPhoto: the LDIF value is base64 and stays RAW text – the
    # card photo decodes it (ENCODING=B, as in vCard inline).
    for v in vals("jpegphoto"):
        card.append(("PHOTO", {"ENCODING": ["B"]}, v))
    return card or None


# → REF TXT-DOC-60
def _ldif_parse(text):
    cards, attrs = [], []

    def flush():
        if attrs:
            card = _ldif_record(attrs)
            if card is not None:
                cards.append(card)
            del attrs[:]

    for line in _ldif_unfold(text):
        s = line.strip()
        if not s or s == "-":
            # Blank line or LDIF change separator: record boundary
            flush()
            continue
        if s.startswith("#") or s.lower().startswith("version:"):
            continue
        idx = s.find(":")
        if idx < 0:
            continue
        attr = s[:idx].strip().lower()
        rest = s[idx:]
        double = rest.startswith("::")
        value = rest[2:] if double else rest[1:]
        if double and attr != "jpegphoto":
            try:
                value = base64.b64decode(value.strip()).decode(
                    "utf-8", "replace")
            except Exception as e:
                dbg("text/flush: suppressed: %s" % e)
        value = value.strip()
        if value:
            attrs.append((attr, value))
    flush()
    return cards


# --- Windows contacts (F7): .contact XML as cards ----------------------------

_CONTACT_ADDR_TAGS = ("street", "city", "locality", "state", "region",
                      "postalcode", "zip", "countryregion", "country")

_CONTACT_ADDR_KEYS = {"region": "state", "country": "countryregion",
                      "locality": "city", "zip": "postalcode"}

_CONTACT_TEL_TYPES = {"mobile": "CELL", "cell": "CELL", "home": "HOME",
                       "business": "WORK", "work": "WORK", "fax": "FAX"}


# → REF TXT-DOC-61
def _contact_one(node):
    card, addr, name = [], {}, {}

    def flush_addr():
        if addr:
            value = ";".join(["", addr.get("street", ""), "",
                              addr.get("city", ""),
                              addr.get("state", ""),
                              addr.get("postalcode", ""),
                              addr.get("countryregion", "")])
            if value.strip(";"):
                card.append(("ADR", {}, value))
            addr.clear()

    for el in node.iter():
        tag = (el.tag.rsplit("}", 1)[-1]
               if isinstance(el.tag, str) else "").lower()
        value = el.get("Value") or (el.text or "").strip()
        if not tag or not value:
            continue
        if tag in _CONTACT_ADDR_TAGS:
            if tag == "street" and addr:
                flush_addr()
            addr[_CONTACT_ADDR_KEYS.get(tag, tag)] = value
            continue
        flush_addr()
        if tag == "formattedname":
            card.append(("FN", {}, value))
        elif tag == "familyname":
            name["family"] = value
        elif tag == "givenname":
            name["given"] = value
        elif tag == "middlename":
            name["middle"] = value
        elif tag == "nameprefix":
            name["prefix"] = value
        elif tag == "namesuffix":
            name["suffix"] = value
        elif tag == "nickname":
            card.append(("NICKNAME", {}, value))
        elif tag in ("company", "companyname"):
            card.append(("ORG", {}, value))
        elif tag == "title":
            card.append(("TITLE", {}, value))
        elif tag in ("emailaddress", "email"):
            card.append(("EMAIL", {}, value))
        elif tag in ("phonenumber", "phone"):
            ptype = _CONTACT_TEL_TYPES.get(
                (el.get("Type") or "").lower(), "")
            card.append(("TEL", {"TYPE": [ptype]} if ptype else {},
                         value))
        elif tag == "webaddress":
            card.append(("URL", {}, value))
        elif tag in ("birthdate", "birthday"):
            card.append(("BDAY", {}, value))
        elif tag in ("notes", "note"):
            card.append(("NOTE", {}, value))
    flush_addr()
    if (not any(prop[0] == "FN" for prop in card)
            and (name.get("given") or name.get("family"))):
        card.insert(0, ("FN", {},
                       " ".join(x for x in (name.get("prefix", ""),
                                           name.get("given", ""),
                                           name.get("family", ""))
                                if x)))
    return card


# → REF TXT-DOC-62
def _contact_parse(text):
    # R10: contact XML ships without DTD – entity guard before
    # parsing; on rejection the file counts as unreadable.
    if _xml_dtd_rejected(text, ".contact"):
        return []
    try:
        root = ElementTree.fromstring(text)
    except Exception:
        return []
    nodes = [el for el in root.iter()
             if isinstance(el.tag, str)
             and el.tag.rsplit("}", 1)[-1].lower() == "contact"]
    if not nodes:
        nodes = [root]
    cards = []
    for node in nodes:
        card = _contact_one(node)
        if card:
            cards.append(card)
    return cards


# F52: iCalendar – read cap like the other structured text formats,
# event cap like the contact cards (the rest shows as a hint).
_ICS_FILE_CAP = 8 * 1024 * 1024      # .ics: events + descriptions
_ICS_EVENT_CAP = 50                  # F52: rendered events max


# → REF TXT-DOC-87
def _ics_unfold(text):
    # RFC 5545: a line break followed by a space or tab continues
    # the previous line (folding).
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


# → REF TXT-DOC-88
def _ics_dt(value, params):
    # DATE or DATE-TIME into a readable string; all-day values
    # (VALUE=DATE or no "T") show the date only.
    if "VALUE=DATE" in params or "T" not in value.upper():
        all_day = True
    else:
        all_day = False
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) < 8:
        return value
    s = "%s-%s-%s" % (digits[0:4], digits[4:6], digits[6:8])
    if not all_day and len(digits) >= 13:
        s += " %s:%s" % (digits[8:10], digits[10:12])
    return s


# → REF TXT-DOC-89
def _ics_text(value):
    # Unescapes RFC 5545 text values for display.
    s = value.replace("\\n", " ").replace("\\N", " ")
    s = s.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    return re.sub(r"\s+", " ", s).strip()


# → REF TXT-DOC-90
def _ics_data(path):
    # VEVENT blocks into dicts of (params, value) pairs; the first
    # occurrence of a property wins (repeats stay unhandled).
    with open(path, "rb") as fh:
        raw = fh.read(_ICS_FILE_CAP)
    text = raw.decode("utf-8-sig", "replace")
    events, cur = [], None
    for line in _ics_unfold(text):
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        base = name.split(";", 1)[0].strip().upper()
        if base == "BEGIN" and value.strip().upper() == "VEVENT":
            cur = {}
        elif base == "END" and value.strip().upper() == "VEVENT":
            if cur is not None and (cur.get("SUMMARY")
                                    or cur.get("DTSTART")):
                events.append(cur)
            cur = None
        elif (cur is not None and base not in cur and base in
              ("SUMMARY", "DTSTART", "DTEND", "LOCATION", "DESCRIPTION")):
            cur[base] = (name.upper(), value.strip())
    return events


# → REF TXT-DOC-91
def _eml_attachment_rows(msg):
    # F54: every MIME part with a filename becomes a row of
    # (name, size); undecodable sizes stay None.
    rows = []
    for part in msg.walk():
        try:
            name = part.get_filename()
        except Exception:
            name = None
        if not name:
            continue
        name = os.path.basename(name.replace("\\", "/")).strip()
        if not name:
            continue
        try:
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else None
        except Exception:
            size = None
        rows.append((name, size))
    return rows


# → REF TXT-DOC-92
def _unique_target(folder, name):
    # Conflict-free target: an existing file gets _1, _2 …
    base, ext = os.path.splitext(name)
    cand = os.path.join(folder, name)
    n = 1
    while os.path.exists(cand):
        cand = os.path.join(folder, "%s_%d%s" % (base, n, ext))
        n += 1
    return cand


# --- F8: CSV as a real table (user request 2026-11-02) ---
# 0.46.0: the module detects the delimiter and header itself
# (user requirement) – csv.Sniffer guesses the delimiter AND
# the header from the content, never from the file name.

_CSV_FILE_CAP = 4 * 1024 * 1024     # F8: max bytes of a CSV file
_CSV_ROW_CAP = 1000                 # F8: max preview rows
_CSV_SNIFF_CAP = 64 * 1024          # F8: bytes for csv.Sniffer


# → REF TXT-DOC-63
def _csv_data(path):
    with open(path, "rb") as fh:
        raw = fh.read(_CSV_FILE_CAP)
    truncated = len(raw) == _CSV_FILE_CAP
    text = raw.decode("utf-8-sig", "replace")
    sample = text[:_CSV_SNIFF_CAP]
    delim = ","
    header = False
    try:
        sniffer = csv.Sniffer()
        delim = sniffer.sniff(sample, delimiters=",;\t|").delimiter
        header = sniffer.has_header(sample)
    except Exception as e:
        dbg("text/_csv_data: sniffer fallback (comma): %s" % e)
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delim):
        if len(rows) >= _CSV_ROW_CAP:
            truncated = True
            break
        rows.append(row)
    width = max(len(r) for r in rows) if rows else 0
    rows = [r + [""] * (width - len(r)) for r in rows]
    if header and rows:
        headers = rows.pop(0)
    else:
        headers = [_("Column %d") % (i + 1) for i in range(width)]
    return headers, rows, delim, truncated


# --- F6: SQLite databases (user request 2026-11-02) ---
# 0.46.0: structure from the schema, opened read-only – the
# preview detects columns and cell delimiters itself.

_SQLITE_MAGIC = b"SQLite format 3\x00"   # 16-byte header
_SQLITE_TABLE_CAP = 200                  # F6: max listed tables
_SQLITE_COUNT_STEPS = 2000000            # F6: COUNT(*) opcode budget


# → REF TXT-DOC-64
def _sqlite_data(path):
    with open(path, "rb") as fh:
        if fh.read(16) != _SQLITE_MAGIC:
            raise ValueError("not an SQLite database (magic missing)")
    rows = []
    truncated = False
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA query_only = 1")
        con.set_progress_handler(lambda: 1, _SQLITE_COUNT_STEPS)
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if len(tables) > _SQLITE_TABLE_CAP:
            truncated = True
            tables = tables[:_SQLITE_TABLE_CAP]
        for name in tables:
            q = '"%s"' % name.replace('"', '""')
            cols = ", ".join(
                r[1] for r in con.execute(
                    'PRAGMA table_info(%s)' % q))
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM %s" % q).fetchone()[0]
            except sqlite3.OperationalError as e:
                dbg("text/_sqlite_data: count aborted (%s): %s"
                    % (name, e))
                count = "…"
            rows.append((name, cols, str(count)))
    finally:
        con.close()
    return rows, truncated


# → REF TXT-DOC-65
# F78: extensions the print button accepts for the text print path
# (Markdown and e-mail) – the toolbar shows the button for a single
# file with one of these endings (plus the office path from docs).
_PRINT_TEXT_EXTS = (".md", ".markdown", ".eml")


def _print_page_setup_a4():
    # B23: shared A4 preset for BOTH text print paths (WebKit and
    # Pango) – explicit paper and 15 mm margins instead of the
    # platform defaults (B19, now defined in one place).
    ps = Gtk.PageSetup()
    # GTK_PAPER_NAME_A4 is "iso_a4"; getattr because the constant
    # is not guaranteed to be exported to Python.
    ps.set_paper_size(Gtk.PaperSize.new(
        getattr(Gtk, "PAPER_NAME_A4", "iso_a4")))
    ps.set_orientation(Gtk.PageOrientation.PORTRAIT)
    ps.set_top_margin(15, Gtk.Unit.MM)
    ps.set_bottom_margin(15, Gtk.Unit.MM)
    ps.set_left_margin(15, Gtk.Unit.MM)
    ps.set_right_margin(15, Gtk.Unit.MM)
    return ps


class TextRendererMixin:

    # --- Shared helpers for text views (audit 0.9.1): TextView building
    # was previously duplicated ~five times; capped file reading twice. ---

    # → REF TXT-DOC-66
    def _read_text_file(self, path):
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
            self._hint(_("Could not read the file: %s") % e)
            return
        # F24: line numbers per the "Text files" setting (default on);
        # margin drawing, not text buffer – only the text is copied.
        # F44: source_path passes the file name to _text_view – the
        # panel core infers the language and switches to GtkSourceView.
        self._text_view(text, font="Monospace 9",
                        linenumbers=self._conf_text_linenumbers,
                        source_path=path)
        if truncated:
            pack_hint(self._content, _("Preview trimmed (long file)."))

    # → REF TXT-DOC-67
    def _render_markdown(self, path):
        try:
            text, truncated = self._read_text_file(path)
        except Exception as e:
            self._hint(_("Could not read the file: %s") % e)
            return
        # F83: WebKit renders a real HTML document when available –
        # the Pango adapter stays for missing WebKit, the "legacy"
        # engine switch and any HTML failure (graceful degradation).
        engine = "markdown-it"
        try:
            engine = getattr(self, "_conf_markdown_engine",
                             "markdown-it") or "markdown-it"
        except Exception:
            pass
        if engine != "legacy" and HAVE_WEBKIT and _MDIT_HTML is not None:
            try:
                self._render_markdown_html(path, text, truncated)
                return
            except Exception as e:
                dbg("text/_render_markdown: HTML preview failed "
                    "(%s) - Pango adapter" % e)
        markup = _markdown_markup(self, text)
        valid = True
        try:
            # Validate markup BEFORE inserting: GTK silently bails
            # on invalid markup (no exception!) – show raw text instead.
            Pango.parse_markup(markup, -1, "\x00")
        except Exception as exc:
            valid = False
            dbg("Markdown markup invalid (%s) – showing raw text" % exc)
        # → REF TXT-B6-1
        self._text_view(text, font=None, markup=(markup if valid else None))
        if truncated:
            pack_hint(self._content, _("Preview trimmed (long file)."))

    # → REF TXT-DOC-110
    def _render_markdown_html(self, path, text, truncated):
        # F83: real HTML preview – the webview scrolls itself, links
        # stay DEAD (F84: decide-policy blocks every navigation
        # away from the own document), the theme colors come from
        # this widget's style context.
        ctx = self.get_style_context()
        bg = ctx.get_background_color(Gtk.StateFlags.NORMAL)
        fg = ctx.get_color(Gtk.StateFlags.NORMAL)
        dark = (0.299 * bg.red + 0.587 * bg.green
                + 0.114 * bg.blue) < 0.5
        size_px = 0
        try:
            fd = effective_text_font("9")
            # B12: only an EXPLICIT configured size (absolute) may
            # override the theme font in the HTML preview.
            if fd is not None and fd.get_size_is_absolute():
                size = fd.get_size()
                if size > 0:
                    size_px = int(round(float(size) / Pango.SCALE))
        except Exception as e:
            dbg("text/_render_markdown_html: font size suppressed:"
                " %s" % e)
        base_dir = os.path.dirname(path) or "."
        doc = _markdown_html(text, base_dir=base_dir, bg=bg, fg=fg,
                             dark=dark, size_px=size_px)
        view = WebKit2.WebView()
        # 1.13.1 (B15): set_property instead of the setter methods –
        # the GIR names differ between WebKit builds (deploy
        # feedback: 'Settings' object has no attribute
        # 'set_javascript_enabled').
        try:
            view.get_settings().set_property("enable-javascript",
                                             False)
        except Exception as e:
            dbg("text/_render_markdown_html: settings suppressed:"
                " %s" % e)
        try:
            view.get_settings().set_property("enable-plugins", False)
        except Exception as e:
            dbg("text/_render_markdown_html: plugins property "
                "gone: %s" % e)
        view.connect("decide-policy", self._md_webview_policy)
        view.set_hexpand(True)
        view.set_vexpand(True)
        self._content.pack_start(view, True, True, 0)
        base_uri = None
        try:
            base_uri = GLib.filename_to_uri(base_dir) + "/"
        except Exception:
            base_uri = None
        # B16/F84: the policy handler must recognize the OWN
        # document (programmatic load + same-document anchors)
        # against this base – everything else is blocked.
        self._md_base_uri = base_uri
        view.load_html(doc, base_uri)
        if truncated:
            pack_hint(self._content, _("Preview trimmed (long file)."))
        dbg("text/_render_markdown_html: %d bytes html%s"
            % (len(doc), " (trimmed)" if truncated else ""))

    # → REF TXT-DOC-110
    def _md_webview_policy(self, view, decision, decision_type):
        # F83/B16/F84: the preview never navigates away and never
        # opens anything outside itself (F84 security, all file
        # types): links stay visible but DEAD. Only the OWN document
        # proceeds – the programmatic load of the preview html
        # (WebKit fires a navigation decision for load_html with a
        # base_uri, its URI IS the base) and same-document anchor
        # jumps. Everything else – link clicks included, gesture or
        # not (e.g. a meta refresh in raw HTML) – is ignored: no
        # browser, no xdg-open. B15 ignored EVERYTHING, which
        # cancelled the own load (blank preview).
        try:
            if decision_type in (
                    WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                    WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                uri = None
                gesture = False
                try:
                    act = decision.get_navigation_action()
                    uri = act.get_request().get_uri()
                    gesture = act.is_user_gesture()
                except Exception as e:
                    dbg("text/_md_webview_policy: action "
                        "suppressed: %s" % e)
                base = getattr(self, "_md_base_uri", None) or ""
                own = (bool(base) and uri is not None
                       and uri.split("#", 1)[0].rstrip("/")
                       == base.rstrip("/"))
                if own or (not base and not gesture):
                    try:
                        decision.use()
                    except Exception as e:
                        dbg("text/_md_webview_policy: use "
                            "suppressed: %s" % e)
                else:
                    if uri:
                        dbg("text/_md_webview_policy: blocked:"
                            " %s" % uri)
                    try:
                        decision.ignore()
                    except Exception as e:
                        dbg("text/_md_webview_policy: ignore "
                            "suppressed: %s" % e)
                return True
        except Exception as e:
            dbg("text/_md_webview_policy: suppressed: %s" % e)
        return False

    # → REF TXT-DOC-68
    def _render_eml(self, path):
        try:
            with open(path, "rb") as fh:
                # The WHOLE mail is parsed (user request – a big
                # mail stays big), no read cap.
                raw = fh.read()
            msg = email.message_from_bytes(raw, policy=policy.default)
        except Exception as e:
            self._hint(_("Could not open the e-mail: %s") % e)
            return

        rows = []
        for key, label in (("from", _("From")), ("to", _("To")),
                           ("cc", _("Cc")), ("date", _("Date")),
                           ("subject", _("Subject"))):
            try:
                val = msg.get(key)
            except Exception:
                val = None
            if val:
                rows.append((label, str(val)[:160]))
        # Headers via the central table helper; F54: bold labels +
        # italic values, subject row BELOW date (user request).
        pack_meta_grid(rows, self._content, bold_keys=True,
                       italic_values=True)

        # F86: HTML mails render through the WebKit pipeline
        # (sanitized, cid: images inline); plain mails keep the
        # text view (→ REF TXT-EML-HTML-1).
        html = None
        if HAVE_WEBKIT:
            html = self._eml_html_body(msg)
        if html is not None:
            cidmap = _eml_cid_map(msg)
            doc = _eml_html_doc(_eml_html_sanitize(html, cidmap))
            self._eml_render_html(doc)
        else:
            body = self._eml_body(msg)
            # F54: mails WITHOUT text render like a mail with text (user
            # request) – the body area is always built.
            self._text_view(body)
        att_rows = _eml_attachment_rows(msg)
        if att_rows:
            # F54: attachments with name and size plus an
            # extract button (→ REF TXT-EML-ATT-1).
            self._pack_eml_attachments(path, att_rows)
        dbg("text/_render_eml: %d attachments listed" % len(att_rows))

    # → REF TXT-DOC-69
    def _eml_body(self, msg):
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
            except Exception as e:
                dbg("text/_eml_body: suppressed: %s" % e)
        if not text.strip():
            # Fallback: first text/plain part if get_body failed.
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

    # → REF TXT-EML-HTML-1
    def _eml_html_body(self, msg):
        # F86: the best HTML body part, decoded – None when the
        # mail has no HTML body.
        part = None
        try:
            part = msg.get_body(preferencelist=("html",))
        except Exception:
            part = None
        if part is None:
            return None
        try:
            ctype = (part.get_content_type() or "").lower()
            text = part.get_content()
        except Exception:
            try:
                raw = part.get_payload(decode=True)
                text = raw.decode(part.get_content_charset() or "utf-8",
                                  "replace") if raw else ""
            except Exception as e:
                dbg("text/_eml_html_body: decode failed: %s" % e)
                return None
        if "html" not in ctype or not text.strip():
            return None
        return text

    # → REF TXT-EML-HTML-1
    def _eml_render_html(self, doc):
        # F86: the sanitized mail HTML in a webview – same rules as
        # the markdown preview (F83): JavaScript/plugins off, own
        # policy handler (F84: NOTHING navigates), no base_uri
        # (about:blank) – remote references are already gone from
        # the markup, so nothing can load from the network.
        view = WebKit2.WebView()
        try:
            view.get_settings().set_property("enable-javascript", False)
            view.get_settings().set_property("enable-plugins", False)
        except Exception as e:
            dbg("text/_eml_render_html: settings suppressed: %s" % e)
        view.connect("decide-policy", self._eml_webview_policy)
        view.set_hexpand(True)
        view.set_vexpand(True)
        self._content.pack_start(view, True, True, 0)
        view.load_html(doc, None)
        dbg("text/_eml_render_html: %d bytes html" % len(doc))

    # → REF TXT-EML-HTML-1
    def _eml_webview_policy(self, view, decision, decision_type):
        # F86: mail HTML is untrusted – ONLY the programmatic load
        # and same-document anchor jumps (about:blank) proceed;
        # EVERY other navigation (link click, meta refresh, form)
        # is ignored (F84: dead links, no way out).
        try:
            if decision_type in (
                    WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                    WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                uri = ""
                try:
                    uri = (decision.get_navigation_action()
                           .get_request().get_uri()) or ""
                except Exception:
                    uri = ""
                if uri.startswith("about:blank"):
                    try:
                        decision.use()
                    except Exception as e:
                        dbg("text/_eml_webview_policy: use"
                            " suppressed: %s" % e)
                else:
                    dbg("text/_eml_webview_policy: blocked: %s"
                        % (uri or "?"))
                    try:
                        decision.ignore()
                    except Exception as e:
                        dbg("text/_eml_webview_policy: ignore"
                            " suppressed: %s" % e)
                return True
        except Exception as e:
            dbg("text/_eml_webview_policy: suppressed: %s" % e)
        return False

    # → REF TXT-EML-HTML-1
    def _eml_print_html(self, path):
        # F86: print an HTML mail through the SAME WebKit pipeline
        # as the Markdown print (TXT-PRINT-2) – sanitized mail HTML
        # (no remote references, cid: images as data: URIs) in
        # print clothing; the shared _md_print_loaded opens the
        # print dialog with the A4/15 mm preset (B19/B23/B24).
        # Returns True when this path took over, False to fall back
        # to the Pango text print.
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            msg = email.message_from_bytes(raw, policy=policy.default)
        except Exception as e:
            dbg("text/_eml_print_html: open failed: %s" % e)
            return False
        html = self._eml_html_body(msg)
        if html is None or not html.strip():
            return False
        cidmap = _eml_cid_map(msg)
        body = _eml_html_sanitize(html, cidmap)
        doc = _eml_html_doc(
            body,
            extra_css="body{margin:0;padding:0;}"
                      "h1,h2,h3,h4,h5,h6{break-after:avoid;}"
                      "p,li,pre,table,blockquote,img{break-inside:avoid;}"
                      "p{orphans:3;widows:3;}")
        view = WebKit2.WebView()
        view.set_size_request(800, 600)
        try:
            view.get_settings().set_property("enable-javascript", False)
            view.get_settings().set_property("enable-plugins", False)
        except Exception as e:
            dbg("text/_eml_print_html: settings suppressed: %s" % e)
        self._md_print_view = view
        self._md_print_op = None
        view.connect("load-changed", self._md_print_loaded)
        view.connect("decide-policy", self._eml_webview_policy)
        view.load_html(doc, None)
        dbg("text/_eml_print_html: %d bytes html" % len(doc))
        return True

    # → REF TXT-DOC-93
    def _pack_eml_attachments(self, path, rows):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        head = Gtk.Label()
        head.set_markup("<b>%s</b>"
                        % (_("Attachments (%d)") % len(rows)))
        head.set_halign(Gtk.Align.START)
        box.pack_start(head, False, False, 2)
        # F54: checkbox, file name and size per row; only checked
        # attachments extract, five rows stay visible.
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(10)
        checks = []
        for i, (name, size) in enumerate(rows):
            chk = Gtk.CheckButton()
            grid.attach(chk, 0, i, 1, 1)
            checks.append((chk, name))
            nl = Gtk.Label(label=name)
            nl.set_halign(Gtk.Align.START)
            nl.set_hexpand(True)
            nl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            nl.set_tooltip_text(name)
            grid.attach(nl, 1, i, 1, 1)
            sl = Gtk.Label(label=(human_size(size)
                                  if size is not None else _("unknown")))
            sl.get_style_context().add_class("dim-label")
            sl.set_halign(Gtk.Align.END)
            grid.attach(sl, 2, i, 1, 1)
        # Longer lists scroll – only five rows stay visible.
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(150)
        scroll.set_propagate_natural_height(True)
        scroll.add(grid)
        box.pack_start(scroll, False, False, 0)
        btn = Gtk.Button(label=_("Extract selected attachments"))
        btn.set_tooltip_text(_("Choose a folder – existing files get "
                              "a numbered suffix"))
        btn.set_halign(Gtk.Align.START)
        btn.set_margin_top(4)
        btn.connect("clicked", self._on_eml_extract, path, checks)
        box.pack_start(btn, False, False, 0)
        # Packed from the BOTTOM – the list always sits directly
        # above the toolbar (user request).
        self._content.pack_end(box, False, False, 8)

    # → REF TXT-DOC-94
    def _on_eml_extract(self, btn, path, checks):
        # Only CHECKED attachments extract; nothing checked means
        # a hint instead of a folder chooser.
        want = set()
        for chk, name in checks:
            try:
                if chk.get_active():
                    want.add(name)
            except Exception as e:
                dbg("text/_on_eml_extract: check read: %s" % e)
        dbg("text/_on_eml_extract: %d of %d attachments selected"
            % (len(want), len(checks)))
        if not want:
            pack_hint(self._content, _("No attachment selected"))
            return
        try:
            dlg = Gtk.FileChooserDialog(
                title=_("Extract attachments to folder"),
                action=Gtk.FileChooserAction.SELECT_FOLDER)
            toplevel = self.get_toplevel()
            if isinstance(toplevel, Gtk.Window):
                dlg.set_transient_for(toplevel)
            dlg.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL,
                            _("Extract"), Gtk.ResponseType.OK)
            center_window(dlg, 560)
            resp = dlg.run()
            folder = dlg.get_filename() \
                if resp == Gtk.ResponseType.OK else None
            dlg.destroy()
        except Exception as e:
            dbg("text/_on_eml_extract: chooser failed: %s" % e)
            folder = None
        if not folder:
            return
        saved, errors = 0, []
        try:
            with open(path, "rb") as fh:
                # The whole file (user request) – the render path
                # already parses it uncapped.
                raw = fh.read()
            msg = email.message_from_bytes(raw, policy=policy.default)
            for part in msg.walk():
                try:
                    name = part.get_filename()
                except Exception:
                    name = None
                if not name:
                    continue
                fname = os.path.basename(
                    name.replace("\\", "/")).strip()
                if not fname:
                    continue
                if fname not in want:
                    continue
                try:
                    data = part.get_payload(decode=True)
                except Exception as e:
                    errors.append("%s (%s)" % (fname, e))
                    continue
                if not data:
                    errors.append("%s (no data)" % fname)
                    continue
                target = _unique_target(folder, fname)
                try:
                    with open(target, "wb") as out:
                        out.write(data)
                    saved += 1
                except Exception as e:
                    errors.append("%s (%s)" % (fname, e))
        except Exception as e:
            errors.append(str(e))
        dbg("text/_on_eml_extract: %d saved, %d failed -> %s"
            % (saved, len(errors), folder))
        if errors:
            pack_hint(self._content, _("Extracted %d of %d selected "
                      "attachments – %s") % (saved, saved + len(errors),
                                            "; ".join(errors[:3])))
        else:
            pack_hint(self._content, _("Extracted %d attachments to %s")
                      % (saved, folder))

    # → REF TXT-PRINT-1
    def _print_text_document(self, path):
        # F78: print button for Markdown and EML – the GTK print
        # dialog opens for the preview text itself: Markdown via the
        # WebKit HTML pipeline (F85, Pango markup only as fallback),
        # EML as header block plus body, both paginated (WebKit
        # paginates its HTML itself, the Pango path uses a layout).
        if not HAVE_PANGOCAIRO:
            dbg("text/_print_text_document: no PangoCairo")
            return
        lower = path.lower()
        if lower.endswith(".eml"):
            # F86: an HTML mail prints through the WebKit pipeline
            # (same as Markdown, TXT-PRINT-2); the Pango text print
            # below stays the fallback (plain mails, no WebKit, or
            # any error).
            if HAVE_WEBKIT and self._eml_print_html(path):
                return
            text = self._print_eml_text(path)
            markup = None
        else:
            # F85: print Markdown through the SAME WebKit HTML
            # pipeline as the preview (user report: since the
            # markdown-it switch the print showed raw markdown).
            # With the "legacy" switch, without WebKit or on any
            # error the Pango print below stays the fallback.
            engine = "markdown-it"
            try:
                engine = getattr(self, "_conf_markdown_engine",
                                 "markdown-it") or "markdown-it"
            except Exception:
                pass
            if (engine != "legacy" and HAVE_WEBKIT
                    and _MDIT_HTML is not None
                    and self._md_print_html(path)):
                return
            try:
                text, _trunc = self._read_text_file(path)
            except Exception as e:
                dbg("text/_print_text_document: read failed: %s" % e)
                return
            markup = _markdown_markup(self, text)
            try:
                # Same validation as the preview: invalid markup
                # prints as plain text instead of nothing.
                Pango.parse_markup(markup, -1, "\x00")
            except Exception as exc:
                dbg("text/_print_text_document: markup invalid (%s) "
                    "- printing plain text" % exc)
                markup = None
        if not text.strip():
            dbg("text/_print_text_document: nothing to print")
            return
        op = Gtk.PrintOperation()
        op.set_job_name("nemo-previewer – " + os.path.basename(path))
        # B23: EML (and the Markdown fallback) print with the same
        # A4/15 mm preset as the WebKit path – defined margins
        # instead of the platform defaults.
        try:
            ps = _print_page_setup_a4()
            # B24: Gtk.PrintOperation has NO page-setup property
            # (that is the WebKit2.PrintOperation name) – the
            # documented GTK3 API is set_default_page_setup().
            op.set_default_page_setup(ps)
            op.set_property("print-settings", Gtk.PrintSettings())
            dbg("text/_print_text_document: page setup %s,"
                " %.0f x %.0f mm, margins 15 mm"
                % (ps.get_paper_size().get_display_name(),
                   ps.get_paper_width(Gtk.Unit.MM),
                   ps.get_paper_height(Gtk.Unit.MM)))
        except Exception as e:
            dbg("text/_print_text_document: page setup suppressed:"
                " %s" % e)
        data = (text, markup)
        op.connect("begin-print", self._print_text_begin, data)
        op.connect("draw-page", self._print_text_draw_page, data)
        try:
            op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                   self.get_toplevel())
        except Exception as exc:
            dbg("Print dialog failed (%s): %s" % (path, exc))

    # → REF TXT-PRINT-1
    def _print_eml_text(self, path):
        # F78: the printed mail mirrors the preview – header rows
        # first, then the body; plain text only (attachments stay
        # preview-only, they are files of their own).
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            msg = email.message_from_bytes(raw, policy=policy.default)
        except Exception as e:
            dbg("text/_print_eml_text: open failed: %s" % e)
            return ""
        lines = []
        for key, label in (("from", _("From")), ("to", _("To")),
                           ("cc", _("Cc")), ("date", _("Date")),
                           ("subject", _("Subject"))):
            try:
                val = msg.get(key)
            except Exception:
                val = None
            if val:
                lines.append("%s: %s" % (label, str(val)[:160]))
        body = self._eml_body(msg)
        if lines and body.strip():
            return "\n".join(lines) + "\n\n" + body
        return "\n".join(lines) if lines else body

    # → REF TXT-PRINT-1
    def _print_text_begin(self, operation, context, data):
        # F78: pagination – ONE Pango layout over the whole text,
        # wrapped to the printable width; a page break before every
        # line that no longer fits the page height. The line start
        # offsets (byte indices) are remembered per page.
        text, markup = data
        page_h = context.get_height() * Pango.SCALE
        layout = context.create_pango_layout()
        # F78/B12: the configured text size applies to the print
        # too – monospace for plain text and EML, default font for
        # Markdown (like the preview).
        fd = effective_text_font("Monospace 9" if markup is None
                                 else None)
        if fd is not None:
            layout.set_font_description(fd)
        layout.set_width(int(context.get_width() * Pango.SCALE))
        # 1.5.2: WORD alone cannot break a line without spaces
        # (typical EML body lines) – it ran off the paper.
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        if markup is not None:
            layout.set_markup(markup, -1)
        else:
            layout.set_text(text, -1)
        starts = [0]
        it = layout.get_iter()
        while True:
            _ink, log = it.get_line_extents()
            if log.y + log.height > len(starts) * page_h:
                starts.append(it.get_index())
                # A single line taller than a page still lands on
                # its own page – it is simply clipped there.
            if it.at_last_line():
                break
            it.next_line()
        self._print_text_pages = starts
        operation.set_n_pages(len(starts))

    # → REF TXT-PRINT-1
    def _print_text_draw_page(self, operation, context, page_nr, data):
        # F78: the whole layout is drawn once per page, shifted up
        # by page_nr page heights – the print surface clips to the
        # page, so only this page's lines appear. No slicing of the
        # text, so Pango markup stays valid across page breaks.
        text, markup = data
        layout = context.create_pango_layout()
        fd = effective_text_font("Monospace 9" if markup is None
                                 else None)
        if fd is not None:
            layout.set_font_description(fd)
        layout.set_width(int(context.get_width() * Pango.SCALE))
        # 1.5.2: same wrap mode as the pagination step – the drawn
        # layout must break lines EXACTLY like the paginated one.
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        if markup is not None:
            layout.set_markup(markup, -1)
        else:
            layout.set_text(text, -1)
        cr = context.get_cairo_context()
        cr.move_to(0, -page_nr * context.get_height())
        PangoCairo.show_layout(cr, layout)

    # → REF TXT-PRINT-2
    def _md_print_document(self, path, text):
        # F85: the preview HTML in print clothing – white paper,
        # black text (light Pygments style), @page margins; the B12
        # size applies when absolute, otherwise a print default.
        bg = Gdk.RGBA()
        bg.parse("#ffffff")
        fg = Gdk.RGBA()
        fg.parse("#000000")
        size_px = 0
        try:
            fd = effective_text_font("9")
            if fd is not None and fd.get_size_is_absolute():
                size = fd.get_size()
                if size > 0:
                    size_px = int(round(float(size) / Pango.SCALE))
        except Exception as e:
            dbg("text/_md_print_document: font size suppressed:"
                " %s" % e)
        if not size_px:
            size_px = 13
        base_dir = os.path.dirname(path) or "."
        # B17: the page margins come ONLY from the print dialog's
        # page setup (set in _md_print_loaded) – no @page rule, it
        # would stack on top. Break rules keep headings with their
        # text and stop elements from being cut mid-block. B20:
        # tables and long words never grow past the sheet edge –
        # overflowing content is simply clipped when printed.
        return _markdown_html(text, base_dir=base_dir, bg=bg, fg=fg,
                              dark=False, size_px=size_px,
                              extra_css="body{margin:0;padding:0;}"
                                        "h1,h2,h3,h4,h5,h6{break-after:"
                                        "avoid;page-break-after:avoid;}"
                                        "p,li,pre,table,blockquote,img,"
                                        ".md-callout{break-inside:avoid;"
                                        "page-break-inside:avoid;}"
                                        "p{orphans:3;widows:3;}"
                                        "table{max-width:100%;}"
                                        "p,li,td,th,dd,dt{overflow-wrap:"
                                        "anywhere;}")

    # → REF TXT-PRINT-2
    def _md_print_html(self, path):
        # F85: print Markdown through the SAME WebKit HTML pipeline
        # as the preview (user report: since the markdown-it switch
        # the print showed raw markdown). A print-styled document
        # (white paper, black text, page margins) loads into an
        # offscreen webview; once loaded, the WebKit print operation
        # opens the GTK print dialog. Returns True when this path
        # took over, False to fall back to the Pango print. The view
        # and operation stay referenced on self until the print
        # finishes – the garbage collector must never kill them
        # mid-print.
        try:
            text, _trunc = self._read_text_file(path)
        except Exception as e:
            dbg("text/_md_print_html: read failed: %s" % e)
            return False
        if not text.strip():
            return False
        try:
            doc = self._md_print_document(path, text)
        except Exception as e:
            dbg("text/_md_print_html: document failed: %s" % e)
            return False
        view = WebKit2.WebView()
        view.set_size_request(800, 600)
        try:
            view.get_settings().set_property("enable-javascript",
                                             False)
            view.get_settings().set_property("enable-plugins", False)
        except Exception as e:
            dbg("text/_md_print_html: settings suppressed: %s" % e)
        self._md_print_view = view
        self._md_print_op = None
        view.connect("load-changed", self._md_print_loaded)
        base_uri = None
        try:
            base_uri = GLib.filename_to_uri(
                os.path.dirname(path) or ".") + "/"
        except Exception:
            base_uri = None
        view.load_html(doc, base_uri)
        dbg("text/_md_print_html: %d bytes html" % len(doc))
        return True

    # → REF TXT-PRINT-2
    def _md_print_loaded(self, view, event):
        # F85: when the print document has fully loaded, open the
        # GTK print dialog from an idle callback (run_dialog runs
        # its own nested main loop).
        if event != WebKit2.LoadEvent.FINISHED:
            return
        try:
            op = WebKit2.PrintOperation.new(view)
        except Exception as e:
            dbg("text/_md_print_loaded: operation failed: %s" % e)
            self._md_print_view = None
            return
        self._md_print_op = op
        op.connect("finished", self._md_print_finished)
        # B19: explicit paper size and orientation – a bare page
        # setup carries the platform default paper (locale and
        # printer dependent) and the dialog then printed in
        # whatever format it started with. A4 portrait with 15 mm
        # margins all around is the preset; the user can change
        # everything in the dialog. B23: the preset lives in the
        # shared _print_page_setup_a4() – the Pango print uses it
        # too.
        try:
            ps = _print_page_setup_a4()
            op.set_property("page-setup", ps)
            op.set_property("print-settings", Gtk.PrintSettings())
            dbg("text/_md_print_loaded: page setup %s, %.0f x %.0f mm,"
                " margins 15 mm" % (ps.get_paper_size().get_display_name(),
                                    ps.get_paper_width(Gtk.Unit.MM),
                                    ps.get_paper_height(Gtk.Unit.MM)))
        except Exception as e:
            dbg("text/_md_print_loaded: page setup suppressed:"
                " %s" % e)
        GLib.idle_add(self._md_print_run, op)

    # → REF TXT-PRINT-2
    def _md_print_run(self, op):
        # F85: the print dialog itself; on cancel the references
        # are dropped here, on print the finished signal cleans up.
        ok = False
        try:
            top = self.get_toplevel()
            parent = top if isinstance(top, Gtk.Window) else None
            # B19: compare against the enum instead of bool() –
            # PRINT has the value 0, bool() would read it as
            # cancelled and drop the references mid-print.
            resp = op.run_dialog(parent)
            ok = resp == WebKit2.PrintOperationResponse.PRINT
            if ok:
                # B19: log the setup the dialog actually chose –
                # it replaces the preset and decides paper and
                # margins for the whole print.
                try:
                    eff = op.get_property("page-setup")
                    dbg("text/_md_print_run: printing %s, "
                        "%.0f x %.0f mm"
                        % (eff.get_paper_size().get_display_name(),
                           eff.get_paper_width(Gtk.Unit.MM),
                           eff.get_paper_height(Gtk.Unit.MM)))
                except Exception:
                    pass
        except Exception as e:
            dbg("text/_md_print_run: failed: %s" % e)
        if not ok:
            self._md_print_view = None
            self._md_print_op = None
        return False

    # → REF TXT-PRINT-2
    def _md_print_finished(self, op):
        # F85: the print job ended (or failed) – drop the
        # references so the offscreen webview can be collected.
        self._md_print_view = None
        self._md_print_op = None

    # → REF TXT-DOC-70
    def _render_vcard(self, path):
        # → REF TXT-VCARD-1
        try:
            with open(path, "rb") as fh:
                # Read cap: contact photos sit as base64 IN the
                # file – a few MB are normal, dozens would be a bomb.
                raw = fh.read(_VCARD_FILE_CAP)
        except Exception as e:
            self._hint(_("Could not open the contact card: %s")
                       % e)
            return
        text = raw.decode("utf-8", "replace")
        lower = path.lower()
        # Format by extension – all three parsers yield the same
        # card structure (→ REF TXT-VCARD-1).
        if lower.endswith(".ldif"):
            cards = _ldif_parse(text)
        elif lower.endswith(".contact"):
            cards = _contact_parse(text)
        else:
            cards = _vcard_parse(text)
        if not cards:
            pack_hint(self._content, _("No contact found – open the file "
                       "via the open button."))
            self._render_generic()
            return
        # No card cap (user request): ALL contacts are built and
        # scroll below each other; only the file read cap remains.
        stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        stack.set_margin_start(6)
        stack.set_margin_end(6)
        stack.set_margin_top(6)
        stack.set_margin_bottom(6)
        fotos = 0
        for card in cards:
            widget, has_photo = self._vcard_card_widget(card)
            if has_photo:
                fotos += 1
            stack.pack_start(widget, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(stack)
        self._content.pack_start(scroll, True, True, 0)
        dbg("Contact cards: %d built, %d with photo" % (len(cards), fotos))

    # → REF TXT-DOC-71
    def _vcard_card_widget(self, card):
        name = _vcard_display_name(card)
        title = _vcard_first(card, "TITLE")
        org = _vcard_first(card, "ORG").split(";")[0].strip()

        rows = []
        for params, value in _vcard_props(card, "TEL"):
            v = _vcard_unescape(value).strip()
            if v:
                rows.append((_vcard_tel_label(params), v))
        for params, value in _vcard_props(card, "EMAIL"):
            v = _vcard_unescape(value).strip()
            if v:
                rows.append((_("Email"), v))
        for params, value in _vcard_props(card, "URL"):
            v = _vcard_unescape(value).strip()
            if v:
                rows.append((_("Web"), v))
        for params, value in _vcard_props(card, "ADR"):
            v = _vcard_adr(value)
            if v:
                rows.append((_("Address"), v))
        for params, value in _vcard_props(card, "BDAY"):
            v = _vcard_bday(value)
            if v:
                rows.append((_("Birthday"), v))
        nick = _vcard_first(card, "NICKNAME")
        if nick:
            rows.append((_("Nickname"), nick))
        note = _vcard_first(card, "NOTE")
        if note:
            rows.append((_("Note"), note.replace("\n", " ")[:120]))
        # Line cap: address book exports love dozens of phone
        # numbers – stop after 14 lines with a hint.
        if len(rows) > 14:
            rows = rows[:14]
            rows.append((_("More"), _("… details in the file")))

        photo_bytes = _vcard_photo(card)
        pb, had_photo = None, False
        if photo_bytes is not None:
            try:
                pb = _pixbuf_from_bytes(photo_bytes)
                had_photo = pb is not None
            except Exception as e:
                dbg("vCard photo undecodable (%s) – placeholder "
                    "circle" % e)
        pb = _vcard_circle(pb) if pb is not None else None
        if pb is None:
            pb = _vcard_placeholder()
        if pb is not None:
            img = Gtk.Image.new_from_pixbuf(pb)
        else:
            # No Cairo, no photo: fallback icon from the theme.
            img = Gtk.Image.new_from_icon_name(
                pick_icon(("avatar-default-symbolic", "avatar-default",
                           "contact-new-symbolic"), "avatar-default"),
                Gtk.IconSize.DIALOG)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        # Padding: 8 px of air for the shadow (pad in _vcard_card_draw)
        # plus 10 px margin up to the card border.
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        inner.set_margin_top(16)
        inner.set_margin_bottom(19)
        img.set_halign(Gtk.Align.CENTER)
        inner.pack_start(img, False, False, 0)
        lbl = Gtk.Label()
        lbl.set_markup("<span size='x-large' weight='bold'>%s</span>"
                       % _pango_escape(name))
        lbl.set_halign(Gtk.Align.CENTER)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_max_width_chars(24)
        lbl.set_tooltip_text(name)
        inner.pack_start(lbl, False, False, 2)
        sub = " · ".join(x for x in (title, org) if x)
        if sub:
            slbl = Gtk.Label()
            slbl.set_markup("<span foreground='grey'>%s</span>"
                            % _pango_escape(sub))
            slbl.set_halign(Gtk.Align.CENTER)
            slbl.set_ellipsize(Pango.EllipsizeMode.END)
            slbl.set_max_width_chars(32)
            slbl.set_tooltip_text(sub)
            inner.pack_start(slbl, False, False, 0)
        pack_meta_grid(rows, inner)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.connect("draw", self._vcard_card_draw)
        outer.pack_start(inner, True, True, 0)
        return outer, had_photo

    # → REF TXT-DOC-72
    def _vcard_card_draw(self, widget, cr):
        # Border and shadow need NO pycairo – the draw callback
        # receives its Cairo context from GTK.
        try:
            w = widget.get_allocated_width()
            h = widget.get_allocated_height()
            pad = 8
            dx = dy = 4
            cw, ch = w - 2 * pad - 3, h - 2 * pad - 3
            if cw < 24 or ch < 24:
                return False
            r = max(4.0, min(cw, ch) * 56.0 / 960.0)
            for i in range(6, 0, -1):
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.04)
                cover_round_path(cr, pad + dx - i, pad + dy - i,
                                       cw + 2 * i, ch + 2 * i, r + i)
                cr.fill()
            # No fill – the card stays transparent, only the hairline
            # border marks it (0.25.1: white hurts in dark mode).
            cover_round_path(cr, pad, pad, cw, ch, r)
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.10)
            cr.set_line_width(1.0)
            cr.stroke()
        except Exception as e:
            dbg("vCard card background failed (%s)" % e)
        return False

    # → REF TXT-DOC-95
    def _render_ics(self, path):
        # → REF TXT-ICS-1
        try:
            events = _ics_data(path)
        except Exception as e:
            dbg("ICS unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("Could not open the calendar: %s") % e)
            self._render_generic()
            return
        if not events:
            pack_hint(self._content, _("No event found – open the file via "
                      "the open button."))
            self._render_generic()
            return
        count = len(events)
        events = events[:_ICS_EVENT_CAP]
        stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        stack.set_margin_start(6)
        stack.set_margin_end(6)
        stack.set_margin_top(6)
        stack.set_margin_bottom(6)
        # One group for ALL cards: the label column gets the width
        # of the widest label everywhere – never per card.
        sg = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        for ev in events:
            stack.pack_start(self._ics_event_widget(ev, sg), False, False, 0)
        if count > _ICS_EVENT_CAP:
            rest = Gtk.Label(label=_("… and %d more events")
                             % (count - _ICS_EVENT_CAP))
            rest.get_style_context().add_class("dim-label")
            stack.pack_start(rest, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(stack)
        self._content.pack_start(scroll, True, True, 0)
        dbg("text/_render_ics: %d events shown of %d"
            % (len(events), count))

    # → REF TXT-DOC-96
    def _ics_event_widget(self, ev, sg):
        # One event as a vCard-style card: frame and shadow via
        # _vcard_card_draw; sg keeps the label column identical.
        summary = _ics_text(ev.get("SUMMARY", ("", ""))[1]) or _("(no summary)")
        rows = []
        start = ev.get("DTSTART")
        end = ev.get("DTEND")
        if start:
            rows.append((_("Start"), _ics_dt(start[1], start[0])))
        if end:
            rows.append((_("End"), _ics_dt(end[1], end[0])))
        location = _ics_text(ev.get("LOCATION", ("", ""))[1])
        if location:
            rows.append((_("Location"), location))
        desc = _ics_text(ev.get("DESCRIPTION", ("", ""))[1])
        if desc:
            if len(desc) > 240:
                desc = desc[:240] + "…"
            rows.append((_("Description"), desc))
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        # Same air as on the vCards: shadow pad plus card margin.
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        inner.set_margin_top(16)
        inner.set_margin_bottom(19)
        lbl = Gtk.Label()
        lbl.set_markup("<span weight='bold' size='large'>%s</span>"
                       % _pango_escape(summary))
        lbl.set_halign(Gtk.Align.START)
        lbl.set_line_wrap(True)
        inner.pack_start(lbl, False, False, 0)
        pack_meta_grid(rows, inner, wrap=True, title_width=75, size_group=sg)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.connect("draw", self._vcard_card_draw)
        outer.pack_start(inner, True, True, 0)
        return outer

    # → REF TXT-DOC-73
    def _render_ebook(self, path, loader, fmt):
        try:
            rows, cover = loader(path)
        except Exception as e:
            dbg("E-book unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("Could not read the e-book: %s") % e)
            self._render_generic()
            return
        if not rows:
            rows = [(_("E-book format"), fmt)]
        pb = None
        if cover:
            try:
                pb = _pixbuf_from_bytes(cover)
            except Exception as exc:
                dbg("E-book cover not displayable: %s" % exc)
        if pb is None:
            pb = _ebook_placeholder()
        if pb is None:
            pack_hint(self._content, _("No cover available – open the file "
                       "via the open button."))
            pack_meta_grid(rows, self._content)
            return
        # 60/40 split like images (F38): _pack_image_capped sets
        # _image_info_box; the info rows end up in the lower part.
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=True,
                                    keep_height=True, max_upscale=2.0,
                                    frac_h=0.6)
        self._pack_image_capped(scroll)
        pack_meta_grid(rows, self._image_info_box)

    # → REF TXT-DOC-74
    def _render_epub(self, path):
        self._render_ebook(path, _epub_data, "EPUB")

    # → REF TXT-DOC-75
    def _render_fb2(self, path):
        self._render_ebook(path, _fb2_data, "FB2")

    # → REF TXT-DOC-76
    def _render_mobi(self, path):
        self._render_ebook(path, _mobi_data, "MOBI")

    # → REF TXT-DOC-77
    def _pack_package_capped(self, scroll):
        # → REF TXT-PKG-1
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        try:
            vp = scroll.get_child()
            img = vp.get_child() if vp is not None else None
            if img is not None:
                img.set_halign(Gtk.Align.CENTER)
                img.set_valign(Gtk.Align.CENTER)
        except Exception as e:
            dbg("text/_pack_package_capped: suppressed: %s" % e)
        top.pack_start(scroll, True, True, 0)
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_scroll = Gtk.ScrolledWindow()
        info_scroll.set_policy(Gtk.PolicyType.NEVER,
                               Gtk.PolicyType.AUTOMATIC)
        info_scroll.set_overlay_scrolling(False)
        info_scroll.add(bottom)
        self._package_info_box = bottom
        top.set_size_request(-1,
                             max(80, int(self._preview_height() * 0.4)))
        top.connect("size-allocate", self._package_split_sync)
        self._content.pack_start(top, False, True, 0)
        sep = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        self._content.pack_start(sep, False, True, 0)
        self._content.pack_start(info_scroll, True, True, 0)

    # → REF TXT-DOC-78
    def _package_split_sync(self, widget, allocation):
        # → REF TXT-PKG-1
        try:
            ch = self._content.get_allocated_height()
            if ch > 100:
                want = max(80, int(ch * 0.4))
                cur = widget.get_size_request()[1] or 0
                if abs(cur - want) > 2:
                    widget.set_size_request(-1, want)
        except Exception as e:
            dbg("text/_package_split_sync: suppressed: %s" % e)

    # → REF TXT-DOC-79
    def _render_package(self, path, loader, fmt):
        try:
            rows, icon = loader(path)
        except Exception as e:
            dbg("Package unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("Could not read the package: %s") % e)
            self._render_generic()
            return
        if not rows:
            rows = [(_("Package format"), fmt)]
        pb = None
        if icon:
            try:
                pb = _pixbuf_from_bytes(icon)
            except Exception as exc:
                dbg("Package icon not displayable: %s" % exc)
        if pb is None:
            pb = _package_placeholder(fmt)
        if pb is None:
            pack_hint(self._content, _("No icon available – open the file "
                       "via the open button."))
            pack_meta_grid(rows, self._content)
            return
        scroll = self._scaled_image(pb, MAX_IMAGE_HEIGHT, upscale=True,
                                    keep_height=True, max_upscale=2.0,
                                    frac_h=0.4)
        self._pack_package_capped(scroll)
        pack_meta_grid(rows, self._package_info_box, wrap=True)

    # → REF TXT-DOC-80
    def _render_deb(self, path):
        self._render_package(path, _deb_data, "DEB")

    # → REF TXT-DOC-81
    def _render_rpm(self, path):
        self._render_package(path, _rpm_data, "RPM")

    # → REF TXT-DOC-82
    def _render_pkg(self, path):
        self._render_package(path, _pkg_data, "PKG")

    # → REF TXT-DOC-83
    def _pack_table(self, headers, rows):
        # → REF TXT-CSV-1
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                          Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        view = Gtk.TreeView()
        # F69: class carries the configurable info table font size.
        view.get_style_context().add_class(META_SIZE_CSS_CLASS)
        view.set_hexpand(True)
        view.set_vexpand(True)
        view.set_headers_clickable(True)
        view.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)
        store = Gtk.ListStore(*([str] * len(headers)))
        for row in rows:
            store.append([str(c) for c in row])
        view.set_model(store)
        for i, title in enumerate(headers):
            col = Gtk.TreeViewColumn()
            col.set_title(title)
            col.set_resizable(True)
            col.set_clickable(True)
            col.set_sort_column_id(i)
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            col.pack_start(cell, True)
            col.add_attribute(cell, "text", i)
            view.append_column(col)
        scroll.add(view)
        self._content.pack_start(scroll, True, True, 0)

    # → REF TXT-DOC-84
    def _render_csv(self, path):
        # → REF TXT-CSV-1
        try:
            headers, rows, delim, truncated = _csv_data(path)
        except Exception as e:
            dbg("CSV unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("The table could not be "
                       "read: %s") % e)
            self._render_generic()
            return
        if not rows:
            pack_hint(self._content, _("The file contains no table "
                      "rows."))
            return
        self._pack_table(headers, rows)
        dbg("text/_render_csv: delimiter %r detected, %d rows"
            % (delim, len(rows)))
        if truncated:
            pack_hint(self._content,
                      _("Preview trimmed (max. %d rows).")
                      % _CSV_ROW_CAP)

    # → REF TXT-DOC-85
    def _render_sqlite(self, path):
        # → REF TXT-SQL-1
        try:
            rows, truncated = _sqlite_data(path)
        except Exception as e:
            dbg("SQLite unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("The database could not be "
                       "read: %s") % e)
            self._render_generic()
            return
        if not rows:
            pack_hint(self._content, _("The database contains no "
                      "tables."))
            return
        self._pack_table([_("Table"), _("Columns"), _("Rows")], rows)
        dbg("text/_render_sqlite: %d tables" % len(rows))
        if truncated:
            pack_hint(self._content,
                      _("Preview trimmed (max. %d tables).")
                      % _SQLITE_TABLE_CAP)

    # → REF TXT-DOC-86
    def _render_font(self, path):
        try:
            reg, fmt, faces = _font_faces(path)
        except Exception as e:
            dbg("Font unreadable (%s): %s" % (path, e))
            pack_hint(self._content, _("Could not read the font: %s") % e)
            self._render_generic()
            return
        if not HAVE_PANGOCAIRO:
            pack_hint(self._content, _("Font preview unavailable – install "
                       "the python3-cairo and gir1.2-pango packages."))
            self._render_generic()
            return
        # F11: single fonts show Family/Style in the info table,
        # collections keep the per-face header labels instead.
        if len(faces) == 1:
            pack_meta_grid([(_("Format"), fmt), (_("Family"), faces[0][0]),
                            (_("Style"), faces[0][1])], self._content)
        else:
            pack_meta_grid([(_("Format"), fmt),
                            (_("Fonts"), "%d" % len(faces))], self._content)
        if not _fc_add_font_file(reg):
            dbg("Font could not be added to Fontconfig: %s"
                % reg)

        # Fresh font map + own context: sees the new family.
        try:
            fctx = PangoCairo.FontMap.new().create_context()
        except Exception as e:
            dbg("Pango context failed: %s" % e)
            pack_hint(self._content, _("Font preview unavailable."))
            self._render_generic()
            return
        if not _font_known(fctx.get_font_map(), faces[0][0]):
            dbg("Pango does not know the family: %s" % faces[0][0])
            pack_hint(self._content, _("The font could not be registered – "
                       "the waterfall shows the fallback font."))

        # Theme text color. F12 fix (0.34.0): get_color() requires a
        # state in GTK3; StateFlags.NORMAL reads the theme color (→ REF TXT-FONT-2).
        fg = (0.13, 0.13, 0.13)
        try:
            c = self.get_style_context().get_color(
                Gtk.StateFlags.NORMAL)
            fg = (c.red, c.green, c.blue)
        except Exception as e:
            dbg("text/_render_font: suppressed: %s" % e)

        # F11: EVERY face of a collection gets its own waterfall
        # (capped); one live item per waterfall (F68).
        shown = faces[:_TTC_FACE_CAP]
        self._font_wf = []
        for family, style in shown:
            if len(faces) > 1:
                head = Gtk.Label()
                head.set_markup("<b>%s</b> – %s" % (
                    GLib.markup_escape_text(family),
                    GLib.markup_escape_text(style)))
                head.set_halign(Gtk.Align.START)
                head.set_margin_top(8)
                self._content.pack_start(head, False, False, 0)
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            scroll = Gtk.ScrolledWindow()
            # AUTOMATIC in both directions: stops the child minimum
            # width from propagating – the pane stays draggable.
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                              Gtk.PolicyType.AUTOMATIC)
            scroll.add(img)
            self._content.pack_start(scroll, True, True, 0)
            self._font_wf.append({"family": family, "fctx": fctx,
                                  "fg": fg,
                                  "text": self._conf_font_sample_text,
                                  "img": img, "last_w": -1})
        if len(faces) > _TTC_FACE_CAP:
            pack_hint(self._content,
                      _("First %d of %d fonts – the rest is not shown.")
                      % (_TTC_FACE_CAP, len(faces)))
        self._apply_font_scale()

    # → REF TXT-DOC-98
    def _apply_font_scale(self):
        # One live item per face (F11) – every waterfall of the
        # preview re-wraps on its own (F68).
        for wf in self._font_wf or ():
            try:
                target = self._preview_width()
                # Same 8 px threshold as the PDF pages: no re-render
                # per pixel while dragging the divider.
                if abs(target - wf["last_w"]) < 8:
                    continue
                wf["last_w"] = target
                pb = _font_waterfall_pixbuf(
                    wf["family"], wf["fctx"], wf["fg"], wf["text"],
                    target)
                sw, sh = pb.get_width(), pb.get_height()
                # Downscale to fit, never upscale; the height cap
                # keeps the old _scaled_image behavior (R3).
                f = min(float(target) / sw, 1.0)
                if f * sh > MAX_IMAGE_HEIGHT:
                    f = float(MAX_IMAGE_HEIGHT) / sh
                wf["img"].set_from_pixbuf(pb.scale_simple(
                    max(1, int(sw * f)), max(1, int(sh * f)),
                    GdkPixbuf.InterpType.BILINEAR))
            except Exception as e:
                dbg("text/_apply_font_scale: suppressed: %s" % e)


PREVIEWER_VERSION = "1.16.0"
dbg("previewer_render_text %s loaded (F31: text/markdown/EML/e-book/font; "
    "F7: vCard contact card; F44: syntax highlighting via source_path; "
    "F8: CSV table; F6: SQLite overview; F52: ICS events; "
    "F54: EML attachments; F78: Markdown/EML print; "
    "K4 markdown and read caps stay)"
    % PREVIEWER_VERSION)