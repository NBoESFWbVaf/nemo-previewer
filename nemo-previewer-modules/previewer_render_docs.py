#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_render_docs.py – Version 1.2.0

Document renderers: PDF as scrollable pages, office documents
via LibreOffice background conversion with caching.
"""

import os
import sys
import hashlib
import shutil
import zipfile
import re
import tempfile
import xml.etree.ElementTree as ElementTree

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    _,
    dbg,
    MAX_IMAGE_HEIGHT,
    _zf_read_capped, _pixbuf_from_bytes,
    _xml_dtd_rejected,
    pack_hint,
)

# --- Optional modules (missing ones just reduce the previews) ---

# Poppler + pycairo for the PDF preview (pages as pixbufs).
HAVE_POPPLER = False
try:
    import cairo  # pycairo
    gi.require_version('Poppler', '0.18')
    from gi.repository import Poppler
    HAVE_POPPLER = True
except Exception as e:
    dbg("docs/module-level: suppressed: %s" % e)

# LibreOffice for the sharp office preview (background conversion
# to PDF); without it, the embedded thumbnail remains.
SOFFICE = None
try:
    SOFFICE = shutil.which("soffice")
except Exception:
    SOFFICE = None

# LibreOffice conversion cache: ~/.cache/previewer/<hash>.pdf
# → REF DOC-DOC-1
def office_cache_dir():
    d = os.path.join(GLib.get_user_cache_dir(), "previewer")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as e:
        dbg("docs/office_cache_dir: suppressed: %s" % e)
    return d


# → REF DOC-DOC-2
def office_cache_path(path):
    key = hashlib.sha1(
        os.path.abspath(path).encode("utf-8", "replace")).hexdigest()
    return os.path.join(office_cache_dir(), key + ".pdf")


# F70: total size cap of the conversion cache.
_OFFICE_CACHE_MAX = 256 * 1024 * 1024


def office_cache_evict():
    # F70: keep the conversion cache bounded – when the total
    # exceeds the cap, the oldest files go first.
    try:
        entries = []
        total = 0
        for name in os.listdir(office_cache_dir()):
            fp = os.path.join(office_cache_dir(), name)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            if os.path.isfile(fp):
                entries.append((st.st_mtime, st.st_size, fp))
                total += st.st_size
        if total <= _OFFICE_CACHE_MAX:
            return
        entries.sort()
        for mtime, size, fp in entries:
            if total <= _OFFICE_CACHE_MAX:
                break
            try:
                os.remove(fp)
                total -= size
                dbg("docs/office_cache_evict: removed: %s" % fp)
            except OSError:
                pass
    except Exception as e:
        dbg("docs/office_cache_evict: suppressed: %s" % e)


# Office documents are ZIP archives: show the embedded thumbnail
# and/or a text excerpt – no new packages needed (stdlib only).
_OFFICE_EXTS = {
    ".odt", ".ods", ".odp", ".odg", ".odf",          # OpenDocument
    ".docx", ".xlsx", ".pptx",                        # MS Office (OOXML)
    ".doc", ".xls", ".ppt",                           # MS Office (F39)
    ".rtf",                                           # RTF (F39)
}
# F39: office formats WITHOUT a ZIP part – no embedded thumbnail;
# only LibreOffice can preview these (binary MS formats and RTF).
_OFFICE_NOZIP_EXTS = {".doc", ".xls", ".ppt", ".rtf"}
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


# → REF DOC-DOC-3
def _extract_office_text(zf, names):
    entry = next((n for n in _OFFICE_TEXT_ENTRIES if n in names), None)
    if not entry:
        return ""
    try:
        # 0.9.2: read caps against decompression bombs – the text
        # excerpt only needs the document start anyway.
        raw = _zf_read_capped(zf, entry, _OFFICE_XML_CAP)
        # R10: Office XML comes without a DTD – entity guard
        # before parsing; on rejection the text excerpt stays empty.
        if _xml_dtd_rejected(raw, "Office XML " + entry):
            return ""
        root = ElementTree.fromstring(raw)
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


# PDF: pages up to this default limit stay scrollable – the
# doc_max_pages setting is effective (page limit off = unlimited).
MAX_PDF_PAGES = 20
# 0.9.2 (audit "buffer overflow/OOM"): caps against decompression
# and decoding bombs – crafted files must never blow up Nemo.
_PDF_PIXEL_BUDGET = 4096 * 4096      # area per PDF page (else ~1.6 GB)
_OFFICE_THUMB_CAP = 16 * 1024 * 1024  # embedded office thumbnail
_OFFICE_XML_CAP = 2 * 1024 * 1024     # content.xml / word/document.xml


# ========================= Renderer: documents ==============================


# → REF DOC-DOC-4
class DocsRendererMixin:

    # → REF DOC-DOC-5
    def _pdf_page_pixbuf(self, page, target_w):
        pw, ph = page.get_size()
        # Render at double target width so live scaling stays sharp
        # while dragging; extreme pages get capped (space, memory).
        scale = min(float(target_w) / max(pw, 1.0),
                    2.0 * MAX_IMAGE_HEIGHT / max(ph, 1.0))
        scale = max(0.2, min(3.0, scale))
        w, h = max(1, int(pw * scale)), max(1, int(ph * scale))
        # → REF DOC-BUDGET-1
        if w * h > _PDF_PIXEL_BUDGET:
            f = (_PDF_PIXEL_BUDGET / float(w * h)) ** 0.5
            w, h = max(1, int(w * f)), max(1, int(h * f))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        # White backing: PDF pages may have transparent areas –
        # without it they would look unreadably black on dark themes.
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.paint()
        cr.scale(scale, scale)
        page.render(cr)
        return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)

    # → REF DOC-DOC-6
    def _pdf_page_cap(self):
        try:
            if not self._conf_doc_page_limit:
                return 0
            return max(1, min(int(self._conf_doc_max_pages), 999))
        except Exception:
            return MAX_PDF_PAGES

    # → REF DOC-DOC-7
    def _render_pdf(self, path):
        doc = Poppler.Document.new_from_file(GLib.filename_to_uri(path), None)
        n = doc.get_n_pages()
        if n == 0:
            pack_hint(self._content, _("The PDF contains no pages."))
            return
        cap = self._pdf_page_cap()
        count = n if cap == 0 else min(n, cap)
        self._pdf_count = count
        # F12 part 3: the current preview is a document page view –
        # cap changes from the settings apply live (marker _last_docview).
        self._last_docview = True
        dbg("PDF opened: %d page(s), showing %d (scrollable; "
            "cap %s)"
            % (n, count, ("%d pages" % cap) if cap else "off"))
        src_w = max(300, self._preview_width() * 2)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._pdf_src = []
        self._pdf_imgs = []
        self._pdf_scaled = []
        self._pdf_box = box
        # Page 1 immediately – only then is the panel usable.
        try:
            pb = self._pdf_page_pixbuf(doc.get_page(0), src_w)
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            box.pack_start(img, False, False, 0)
            self._pdf_src.append(pb)
            self._pdf_imgs.append(img)
            self._pdf_scaled.append(0)
        except Exception as exc:
            dbg("PDF page 1 not renderable: %s" % exc)
        if not self._pdf_src:
            pack_hint(self._content, _("The PDF could not be rendered."))
            self._pdf_box = None
            return
        # F14: page indicator above the scrollable area – ALWAYS, even
        # one-page documents show "Page 1 of 1"; counts while scrolling.
        self._pdf_page_label = Gtk.Label(label=_("Page 1 of %d") % count)
        self._pdf_page_label.get_style_context().add_class("dim-label")
        self._content.pack_start(self._pdf_page_label, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(box)
        scroll.get_vadjustment().connect("value-changed",
                                         self._on_pdf_scrolled)
        self._content.pack_start(scroll, True, True, 0)
        self._pdf_scroll = scroll
        # K15: force the opening pass – a re-render at an unchanged
        # width must still fit page 1 (office PDF arriving later).
        self._pdf_last_w = 0
        self._apply_pdf_scale()
        # R2: feed the remaining pages one per idle cycle. The
        # generation is passed along so each step knows its render pass.
        if count > 1:
            GLib.idle_add(self._pdf_idle_step, doc, path, src_w, count, 1,
                          self._pdf_gen)
        if n > count:
            pack_hint(self._content, _("First %d of %d pages – view the "
                       "whole file via the open button.")
                      % (count, n))
        # → REF DOC-F14-1
        self._content.show_all()

    # → REF DOC-DOC-8
    def _pdf_idle_step(self, doc, path, src_w, count, i, gen):
        try:
            # Abort if a newer render pass ran meanwhile (generation
            # bumped) or the PDF view was disposed (stale check).
            if gen != self._pdf_gen or self._pdf_box is None:
                return False
            pb = self._pdf_page_pixbuf(doc.get_page(i), src_w)
            img = Gtk.Image()
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.START)
            self._pdf_box.pack_start(img, False, False, 0)
            img.show()
            self._pdf_src.append(pb)
            self._pdf_imgs.append(img)
            self._pdf_scaled.append(0)
            # Scale only the new page – _apply_pdf_scale returns early
            # via its width threshold if the panel width did not change.
            self._pdf_scale_one(i, self._preview_width())
        except Exception as exc:
            dbg("PDF page %d not renderable: %s" % (i + 1, exc))
        i += 1
        if i >= count:
            return False
        GLib.idle_add(self._pdf_idle_step, doc, path, src_w, count, i, gen)
        return False

    # → REF DOC-DOC-9
    def _on_pdf_scrolled(self, adj):
        imgs = self._pdf_imgs
        if not imgs or self._pdf_page_label is None:
            return False
        value = adj.get_value()
        page = 1
        for i, img in enumerate(imgs):
            alloc = img.get_allocation()
            if alloc.y + alloc.height > value:
                page = i + 1
                break
        self._pdf_page_label.set_text(
            _("Page %d of %d") % (page, max(1, self._pdf_count)))
        # K14: pages scrolled into view scale right away when the
        # background pass has not reached them yet.
        try:
            target = self._pdf_last_w or self._preview_width()
            lo, hi = self._pdf_visible_range()
            hooked = 0
            for i in range(lo, hi + 1):
                if (i < len(self._pdf_scaled)
                        and self._pdf_scaled[i] != target):
                    self._pdf_scale_one(i, target)
                    hooked += 1
            dbg("docs/_on_pdf_scrolled: pos %d, page %d, scaled %d "
                "page(s) -> %d px" % (value, page, hooked, target))
        except Exception as e:
            dbg("docs/_on_pdf_scrolled: suppressed: %s" % e)
        return False

    # → REF DOC-DOC-10
    def _pdf_scale_one(self, idx, target):
        # K14: index-based – the passes record each page's width,
        # so scroll-triggered scaling skips finished pages.
        src = self._pdf_src[idx]
        img = self._pdf_imgs[idx]
        sw, sh = src.get_width(), src.get_height()
        f = min(float(target) / sw, 1.0)   # never upscale
        w = max(1, int(sw * f))
        h = max(1, int(sh * f))
        img.set_from_pixbuf(
            src.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR))
        # K16: scaling inside the resize pass paints stale – force it.
        img.queue_draw()
        self._pdf_scaled[idx] = target

    # → REF DOC-DOC-11
    def _apply_pdf_scale(self):
        srcs = self._pdf_src
        imgs = self._pdf_imgs
        if not srcs or not imgs:
            return
        target = self._preview_width()
        if abs(target - self._pdf_last_w) < 8:
            return
        old = self._pdf_last_w
        self._pdf_last_w = target
        self._pdf_scale_gen += 1
        gen = self._pdf_scale_gen
        dbg("docs/_apply_pdf_scale: %d px -> %d px, %d page(s)"
            % (old, target, len(srcs)))
        try:
            lo, hi = self._pdf_visible_range()
            # K15: after a big jump (reset button) the first pages
            # scale synchronously; drag crossings stay light (K12).
            wide = abs(target - old) >= 40
            sync_max = 6 if wide else 1
            for i in range(len(srcs)):
                if self._pdf_scaled[i] == target:
                    continue
                if i < sync_max or (wide and lo <= i <= hi):
                    self._pdf_scale_one(i, target)
                else:
                    break
        except Exception as e:
            dbg("docs/_apply_pdf_scale: suppressed: %s" % e)
        GLib.idle_add(self._pdf_relayout)
        if len(srcs) > 1:
            GLib.idle_add(self._pdf_scale_step, target, gen)

    # → REF DOC-DOC-20
    def _pdf_visible_range(self):
        # K14: page indices inside the scroll viewport.
        lo, hi = 0, 0
        try:
            adj = self._pdf_scroll.get_vadjustment()
            top = adj.get_value()
            bottom = top + adj.get_page_size()
            first = None
            last = 0
            for i, img in enumerate(self._pdf_imgs):
                a = img.get_allocation()
                if a.y + a.height > top and a.y < bottom:
                    if first is None:
                        first = i
                    last = i
            if first is not None:
                lo, hi = first, last
        except Exception as e:
            dbg("docs/_pdf_visible_range: suppressed: %s" % e)
        return lo, hi

    def _pdf_relayout(self):
        # K18: the follow-up allocation pass never runs (queue_resize
        # is absorbed) – reallocate the viewport as a scroll does.
        try:
            box = self._pdf_box
            scroll = self._pdf_scroll
            if box is not None:
                box.queue_resize()
            if scroll is not None:
                adj = scroll.get_hadjustment()
                old_box = (box.get_allocated_width()
                           if box is not None else -1)
                old_upper = adj.get_upper()
                vp = scroll.get_child()
                if vp is not None:
                    vp.queue_resize()
                    vp.size_allocate(vp.get_allocation())
                scroll.queue_draw()
                win = scroll.get_window()
                if win is not None:
                    win.invalidate_rect(None, True)
                    win.process_updates(True)
                if box is not None and self._pdf_imgs:
                    dbg("docs/_pdf_relayout: box %d -> %d px, "
                        "h.upper %d -> %d px, page 1 alloc %d px"
                        % (old_box, box.get_allocated_width(),
                           old_upper, adj.get_upper(),
                           self._pdf_imgs[0].get_allocated_width()))
        except Exception as e:
            dbg("docs/_pdf_relayout: suppressed: %s" % e)
        return False

    def _pdf_scale_step(self, target, gen):
        # K12: stale pass – a newer resize or a clear ran.
        if gen != self._pdf_scale_gen or self._pdf_box is None:
            dbg("docs/_pdf_scale_step: stale (gen %d/%d, box %s)"
                % (gen, self._pdf_scale_gen,
                   "gone" if self._pdf_box is None else "live"))
            return False
        done = 0
        lo = hi = 0
        try:
            # K14: visible pages jump the queue – the column fits
            # right after a width jump (reset button); the rest
            # follows in idle batches as before.
            lo, hi = self._pdf_visible_range()
            batch = 0
            for i in range(len(self._pdf_src)):
                if self._pdf_scaled[i] == target:
                    continue
                visible = lo <= i <= hi
                if not visible and batch >= 4:
                    break
                self._pdf_scale_one(i, target)
                done += 1
                if not visible:
                    batch += 1
        except Exception as e:
            dbg("docs/_pdf_scale_step: suppressed: %s" % e)
        dbg("docs/_pdf_scale_step: %d page(s) -> %d px (lo %d, hi %d)"
            % (done, target, lo, hi))
        for w in self._pdf_scaled:
            if w != target:
                GLib.idle_add(self._pdf_scale_step, target, gen)
                break
        return False

    # → REF DOC-DOC-12
    def _render_office(self, path):
        if HAVE_POPPLER and SOFFICE:
            cached = self._office_cached_pdf(path)
            if cached:
                try:
                    self._render_pdf(cached)
                    return
                except Exception as exc:
                    dbg("Office PDF preview failed (%s): %s"
                        % (path, exc))
                    # Remove half-packed leftovers of the PDF view
                    # before packing the thumbnail.
                    self._clear_content()
                    # Invalid cache PDF: remember it as failed, or
                    # every redraw would convert again.
                    self._office_failed.add(path)
            failed = path in self._office_failed
            self._render_office_thumb(path, converting=not failed)
            self._office_start_job(path)
            return
        self._render_office_thumb(path, converting=False)

    # → REF DOC-DOC-13
    def _render_office_thumb(self, path, converting=False):
        # F39: office formats without a ZIP part (binary + RTF) – the
        # thumbnail/text route leads nowhere here (→ REF DOC-LEGACY-1).
        if os.path.splitext(path)[1].lower() in _OFFICE_NOZIP_EXTS:
            self._office_nozip_hint(converting)
            return
        try:
            thumb, text = self._office_package_data(path)
        except Exception as e:
            # K2 (2026-10-30): only the hint line looks empty – the
            # file icon gives the error message a visual anchor.
            self._render_generic()
            pack_hint(self._content,
                      _("The office document could not be opened: %s") % e)
            return
        shown = False
        if thumb:
            try:
                # 0.9.2: guarded loader with a decode cap.
                pb = _pixbuf_from_bytes(thumb)
                if pb is not None:
                    # → REF DOC-UPSCALE-1
                    scroll = self._scaled_image(pb, 1600, upscale=True,
                                                keep_height=True,
                                                max_upscale=1.0)
                    self._content.pack_start(scroll, False, False, 0)
                    shown = True
            except Exception as e:
                dbg("docs/_render_office_thumb: suppressed: %s" % e)
        # Text only as a fallback preview if no thumbnail was embedded.
        if not shown and text.strip():
            # 0.9.1: via the shared TextView helper (previously
            # built identically inline).
            self._text_view(text, font="Monospace 9")
            shown = True
        if not shown:
            pack_hint(self._content, _("No embedded preview and no text "
                       "found – view the file via the open button."))
        if converting:
            pack_hint(self._content, _("Sharp preview is being created in "
                       "the background (LibreOffice) – one moment …"))

    # → REF DOC-DOC-14
    def _office_nozip_hint(self, converting):
        if converting:
            pack_hint(self._content, _("Sharp preview is being created in "
                       "the background (LibreOffice) – one moment …"))
        elif SOFFICE and HAVE_POPPLER:
            # F39: conversion ran but produced no result (broken
            # file) – do not retry endlessly.
            pack_hint(self._content, _("The sharp preview could not be "
                       "created – view the file via the open button."))
        else:
            pack_hint(self._content, _("No preview possible – install "
                       "LibreOffice (package libreoffice-core), then the "
                       "preview converts in sharp quality."))

    # → REF DOC-DOC-15
    def _office_package_data(self, path):
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            thumb = None
            for member in _OFFICE_THUMBS:
                if member in names:
                    # 0.9.2: read cap – a crafted DOCX
                    # could pack a giant thumbnail bomb.
                    try:
                        thumb = _zf_read_capped(zf, member,
                                                _OFFICE_THUMB_CAP)
                    except Exception:
                        thumb = None
                    break
            return thumb, _extract_office_text(zf, names)

    # --- Office: sharp preview via LibreOffice ------------------------------

    # → REF DOC-DOC-16
    def _office_cached_pdf(self, path):
        try:
            cache_pdf = office_cache_path(path)
            if (os.path.exists(cache_pdf)
                    and os.path.getmtime(cache_pdf)
                    >= os.path.getmtime(path)):
                return cache_pdf
        except Exception as e:
            dbg("docs/_office_cached_pdf: suppressed: %s" % e)
        return None

    # → REF DOC-DOC-17
    def _office_fail(self, path):
        self._office_failed.add(path)
        if len(self._office_failed) > 256:
            self._office_failed.clear()

    # → REF DOC-DOC-18
    def _office_start_job(self, path):
        if self._office_job is not None:
            return          # a conversion is already running
        if not SOFFICE or not HAVE_POPPLER:
            return
        if path in self._office_failed:
            return          # already failed – no endless retries
        self._office_job = path
        tmpdir = tempfile.mkdtemp(prefix="previewer-office-")
        out_pdf = os.path.join(
            tmpdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        try:
            pid = GLib.spawn_async(
                [SOFFICE, "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, path],
                flags=GLib.SpawnFlags.SEARCH_PATH
                | GLib.SpawnFlags.DO_NOT_REAP_CHILD
                | GLib.SpawnFlags.STDOUT_TO_DEV_NULL
                | GLib.SpawnFlags.STDERR_TO_DEV_NULL)[0]
        except Exception as exc:
            dbg("LibreOffice conversion not started (%s): %s"
                % (path, exc))
            shutil.rmtree(tmpdir, ignore_errors=True)
            self._office_job = None
            return
        GLib.child_watch_add(pid, self._office_job_done,
                             (path, tmpdir, out_pdf))

    # → REF DOC-DOC-19
    def _office_job_done(self, pid, status, data):
        path, tmpdir, out_pdf = data
        self._office_job = None
        # 0.9.1: panel already torn down (window closed, tab gone) –
        # drop the result and just clean up the temp dir.
        if getattr(self, "_destroyed", False):
            shutil.rmtree(tmpdir, ignore_errors=True)
            return
        try:
            if os.path.exists(out_pdf):
                cache_ok = False
                try:
                    # shutil.move instead of os.replace: /tmp often
                    # sits on its own device (tmpfs) – rename(2)
                    # would fail with EXDEV, move copies instead.
                    shutil.move(out_pdf, office_cache_path(path))
                    # F70: bound the cache right where it grows.
                    office_cache_evict()
                    cache_ok = True
                except Exception as exc:
                    dbg("Office cache write failed: %s"
                        % exc)
                if not cache_ok:
                    # → REF DOC-B4-1
                    self._office_fail(path)
                    if self._path == path:
                        try:
                            # Remove the transitional thumbnail with
                            # its hint – it would cover the sharp view.
                            self._clear_content()
                            self._render_pdf(out_pdf)
                        except Exception as exc:
                            dbg("Office PDF from temp dir not "
                                "displayable (%s): %s" % (path, exc))
                elif self._path == path:
                    self._render()   # show the sharp page view
            else:
                # Remember a failed conversion – prevents an
                # endless loop of retry attempts.
                self._office_fail(path)
                if self._path == path:
                    dbg("LibreOffice conversion without result "
                        "(status %s) – thumbnail stays" % status)
                    dbg("Hint: LibreOffice component packages "
                        "installed? (writer/calc/impress)")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        # If the current selection is waiting for its conversion,
        # start the next one right away (none is running anymore).
        try:
            cur = self._path
            if (cur and os.path.splitext(cur.lower())[1] in _OFFICE_EXTS
                    and cur not in self._office_failed
                    and self._office_cached_pdf(cur) is None
                    and self._office_job is None):
                self._office_start_job(cur)
        except Exception as e:
            dbg("docs/_office_job_done: suppressed: %s" % e)


PREVIEWER_VERSION = "1.2.0"
dbg("previewer_render_docs %s loaded (F31: PDF/office renderer; "
    "page caps and LibreOffice cache stay)"
    % PREVIEWER_VERSION)