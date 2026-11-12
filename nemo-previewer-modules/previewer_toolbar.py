#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_toolbar.py – Version 1.16.1

Panel toolbar and settings window: action bar, preview toggle,
Ctrl+Alt+P shortcut and all preference widgets.
"""

import sys
import os
import shutil
import stat

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib, Gio

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    _,
    dbg,
    set_debug_log,
    pick_icon,
    pack_hint,
    PANEL_MIN_WIDTH,
    TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
)
from previewer_render_docs import HAVE_POPPLER, SOFFICE, _OFFICE_EXTS
from previewer_render_text import HAVE_PANGOCAIRO, _PRINT_TEXT_EXTS

# F81: file types the archive button handles – office documents,
# PDF, EML and Markdown.
_ARCHIVE_EXTS = set(_OFFICE_EXTS) | {".pdf", ".eml", ".md", ".markdown"}


# =============================== Toolbar ====================================


# → REF TB-DOC-1
class PreviewToolbarMixin:

    def _build_toolbar(self, window):
        # --- F19: toolbar at the bottom of the preview column (0.11.0) ---
        # → REF TB-F19-1
        self._toolbar_sep = Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self._toolbar_sep, False, False, 0)
        self._toolbar = Gtk.ActionBar()
        # F74 (x-bit): owner execute-bit toggle at the LEFT end;
        # visibility and red state live in _update_xbit_button.
        self._btn_xbit = Gtk.Button.new_from_icon_name(
            pick_icon(("gtk-execute", "system-run-symbolic",
                       "system-run"), "system-run"),
            Gtk.IconSize.BUTTON)
        self._btn_xbit.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_xbit.set_no_show_all(True)
        self._btn_xbit.connect("clicked", self._on_xbit_clicked)
        self._toolbar.pack_start(self._btn_xbit)
        try:
            css = Gtk.CssProvider()
            css.load_from_data(
                b"button.pvw-xbit-set { background: rgba(246,97,81,0.45); }")
            self._btn_xbit.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            dbg("toolbar/_build_toolbar xbit css: suppressed: %s" % e)
        # F77: print button for office documents – opens the GTK
        # print dialog for the LibreOffice PDF of the file.
        self._btn_print = Gtk.Button.new_from_icon_name(
            "document-print-symbolic", Gtk.IconSize.BUTTON)
        self._btn_print.set_tooltip_text(_("Print document"))
        self._btn_print.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_print.set_no_show_all(True)
        self._btn_print.connect("clicked", self._on_print_clicked)
        self._toolbar.pack_start(self._btn_print)
        # F81: archive button – moves the previewed file to the
        # archive folder chosen in the settings; the icon prefers
        # an archive-specific symbolic name and falls back to the
        # standard list-add-symbolic (never a colored icon).
        self._btn_archive = Gtk.Button.new_from_icon_name(
            self._archive_icon_name(), Gtk.IconSize.BUTTON)
        self._btn_archive.set_tooltip_text(
            _("Move file to archive folder"))
        self._btn_archive.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_archive.set_no_show_all(True)
        self._btn_archive.connect("clicked", self._on_archive_clicked)
        self._toolbar.pack_start(self._btn_archive)
        self._btn_settings = Gtk.Button.new_from_icon_name(
            "preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self._btn_settings.set_tooltip_text(_("Settings"))
        self._btn_settings.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_settings.connect("clicked", self._on_settings_clicked)
        self._toolbar.pack_end(self._btn_settings)
        self.pack_start(self._toolbar, False, False, 0)
        # → REF TB-CSS-1
        try:
            css = Gtk.CssProvider()
            css.load_from_data(
                b"actionbar { padding-top: 3px; padding-bottom: 4px; }")
            self._toolbar.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            dbg("toolbar/_build_toolbar: suppressed: %s" % e)

        # keyboard shortcut to unhide the panel
        try:
            accel = Gtk.AccelGroup()
            window.add_accel_group(accel)
            accel.connect(TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
                          Gtk.AccelFlags.VISIBLE, self._on_toggle_accel)
        except Exception as e:
            dbg("toolbar/_build_toolbar: suppressed: %s" % e)

    # → REF TB-DOC-2
    def _on_settings_clicked(self, button):
        self._open_settings_aux()

    # → REF TB-DOC-3
    def _open_settings_aux(self):
        # F66 part 1: same frames and distances as the former
        # settings window, but in the aux column (→ REF PAN-AUX-1).
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(12)
        box.pack_start(self._settings_frame_general(), False, False, 0)
        box.pack_start(self._settings_frame_text(), False, False, 0)
        box.pack_start(self._settings_frame_docs(), False, False, 0)
        box.pack_start(self._settings_frame_fonts(), False, False, 0)
        box.pack_start(self._settings_frame_archive(), False, False, 0)
        self._open_aux("settings", _("Nemo-Previewer – Settings"), box,
                       trigger=self._btn_settings)

    # → REF TB-DOC-4
    def _settings_frame_general(self):
        frame = Gtk.Frame(label=_("General"))
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        chk = Gtk.CheckButton(label=_("Show preview side panel at launch"))
        chk.set_tooltip_text(
            _("Uncheck to keep the preview side panel hidden after "
              "Nemo starts (Ctrl+Alt+P shows it again at any time)"))
        chk.set_active(self._conf_show_at_start)
        chk.connect("toggled", self._on_show_at_start_toggled)
        fbox.pack_start(chk, False, False, 0)

        # F48: folder contents list on/off – default on; off shows the
        # plain folder icon with file info (→ REF PAN-FOLDER-2).
        chk = Gtk.CheckButton(
            label=_("Show folder contents in the preview"))
        chk.set_tooltip_text(
            _("Uncheck to show only the plain folder icon with file "
              "info instead of the contents list"))
        chk.set_active(self._conf_folder_contents)
        chk.connect("toggled", self._on_folder_contents_toggled)
        fbox.pack_start(chk, False, False, 0)

        # F65: debug logging – mirrors dbg into the log file under
        # XDG_STATE_HOME (env var NEMO_PREVIEWER_DEBUG always wins).
        chk = Gtk.CheckButton(
            label=_("Debug logging (write log file)"))
        chk.set_tooltip_text(
            _("Mirror the debug output into "
              "~/.local/state/nemo-previewer/previewer.log – rotates "
              "at 512 KB, keeps one backup; NEMO_PREVIEWER_DEBUG=1 "
              "switches it on without any setting"))
        chk.set_active(self._conf_debug_log)
        chk.connect("toggled", self._on_debug_log_toggled)
        fbox.pack_start(chk, False, False, 0)

        # F69: info table font size as a spin – metadata tables in
        # the preview and in the "more" windows.
        mrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        mrow.pack_start(Gtk.Label(label=_("Info table font size (px)")),
                        False, False, 0)
        adj = Gtk.Adjustment(value=self._conf_meta_font_size,
                             lower=0, upper=28, step_increment=1,
                             page_increment=2)
        self._settings_metasize_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_metasize_spin.set_tooltip_text(
            _("Font size of the info tables (file metadata in the "
              "preview and the tag windows) – 0 keeps the theme's "
              "normal size, applies immediately."))
        self._settings_metasize_spin.connect(
            "value-changed", self._on_meta_size_changed)
        mrow.pack_start(self._settings_metasize_spin, False, False, 0)
        fbox.pack_start(mrow, False, False, 0)

        # → REF TB-F12-1
        wrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_width = Gtk.Label(label=_("Default width at launch"))
        lbl_width.set_halign(Gtk.Align.START)
        wrow.pack_start(lbl_width, False, False, 0)
        adj = Gtk.Adjustment(value=self._panel_width,
                             lower=PANEL_MIN_WIDTH, upper=1600,
                             step_increment=10, page_increment=50)
        self._settings_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_spin.set_value(self._panel_width)
        self._settings_spin.set_tooltip_text(
            _("Width of the preview side panel Nemo opens with at "
              "every start – dragging the divider applies only to "
              "the current session"))
        self._settings_spin.connect("value-changed",
                                    self._on_start_width_changed)
        wrow.pack_start(self._settings_spin, False, False, 0)
        fbox.pack_start(wrow, False, False, 0)
        return frame

    # → REF TB-DOC-5
    def _settings_frame_text(self):
        frame = Gtk.Frame(label=_("Text files"))
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        ln = Gtk.CheckButton(
            label=_("Show line numbers (not copyable)"))
        ln.set_tooltip_text(
            _("Line numbers in the left margin of the text preview. "
              "The numbers are drawn outside the text – only the "
              "text itself is selected and copied."))
        ln.set_active(self._conf_text_linenumbers)
        ln.connect("toggled", self._on_linenumbers_toggled)
        fbox.pack_start(ln, False, False, 0)
        # F44: syntax highlighting as a switch – default on, saved
        # immediately and applied live.
        syn = Gtk.CheckButton(
            label=_("Syntax highlighting in source code files"))
        syn.set_tooltip_text(
            _("Colour source code (.py, .sh, .c …) in the text preview – "
              "requires the optional package gir1.2-gtksource-4; "
              "when unchecked, the plain text always shows."))
        syn.set_active(self._conf_text_syntax)
        syn.connect("toggled", self._on_syntax_toggled)
        fbox.pack_start(syn, False, False, 0)
        # F25: extra line spacing as a spin – 0 is the normal line
        # height, applies immediately to the text preview.
        srow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        srow.pack_start(Gtk.Label(label=_("Line spacing (px)")),
                        False, False, 0)
        adj = Gtk.Adjustment(value=self._conf_text_line_spacing,
                             lower=0, upper=12, step_increment=1,
                             page_increment=2)
        self._settings_spacing_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_spacing_spin.set_tooltip_text(
            _("Extra space between the lines of a text preview – 0 is "
              "the normal line height, applies immediately."))
        self._settings_spacing_spin.connect(
            "value-changed", self._on_line_spacing_changed)
        srow.pack_start(self._settings_spacing_spin, False, False, 0)
        fbox.pack_start(srow, False, False, 0)
        # F69: text preview font size as a spin – 0 keeps the theme
        # size; the CSS rule applies it live.
        trow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        trow.pack_start(Gtk.Label(label=_("Preview font size (px)")),
                        False, False, 0)
        adj = Gtk.Adjustment(value=self._conf_text_font_size,
                             lower=0, upper=28, step_increment=1,
                             page_increment=2)
        self._settings_textsize_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_textsize_spin.set_tooltip_text(
            _("Font size of the text previews (plain text, Markdown, "
              "source code) – 0 keeps the theme's normal size, "
              "applies immediately."))
        self._settings_textsize_spin.connect(
            "value-changed", self._on_text_size_changed)
        trow.pack_start(self._settings_textsize_spin, False, False, 0)
        fbox.pack_start(trow, False, False, 0)
        return frame

    # → REF TB-DOC-6
    def _settings_frame_docs(self):
        frame = Gtk.Frame(label=_("Documents (PDF and Office)"))
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        lim = Gtk.CheckButton(
            label=_("Limit preview pages (performance)"))
        lim.set_tooltip_text(
            _("Uncheck to display PDF and Office documents completely "
              "without a limit – with very large documents this "
              "costs more memory and time."))
        lim.set_active(self._conf_doc_page_limit)
        lim.connect("toggled", self._on_doc_limit_toggled)
        fbox.pack_start(lim, False, False, 0)

        prow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_pages = Gtk.Label(label=_("Maximum number of pages"))
        lbl_pages.set_halign(Gtk.Align.START)
        prow.pack_start(lbl_pages, False, False, 0)
        padj = Gtk.Adjustment(value=self._conf_doc_max_pages,
                              lower=1, upper=999,
                              step_increment=1, page_increment=10)
        self._settings_pages_spin = Gtk.SpinButton.new(padj, 1.0, 0)
        self._settings_pages_spin.set_value(self._conf_doc_max_pages)
        self._settings_pages_spin.set_sensitive(self._conf_doc_page_limit)
        self._settings_pages_spin.set_tooltip_text(
            _("Number of pages that PDF and Office previews show at "
              "most – applies live, also to the document currently "
              "displayed."))
        self._settings_pages_spin.connect(
            "value-changed", self._on_doc_max_pages_changed)
        prow.pack_start(self._settings_pages_spin, False, False, 0)
        fbox.pack_start(prow, False, False, 0)
        return frame

    # → REF TB-DOC-7
    def _settings_frame_fonts(self):
        frame = Gtk.Frame(label=_("Fonts"))
        frame.set_border_width(8)
        frow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        frame.add(frow)
        flabel = Gtk.Label(label=_("Waterfall sample text"))
        flabel.set_halign(Gtk.Align.START)
        frow.pack_start(flabel, False, False, 0)
        self._settings_font_entry = Gtk.Entry()
        self._settings_font_entry.set_text(self._conf_font_sample_text)
        self._settings_font_entry.set_tooltip_text(
            _("Text for the font preview – applies live to the font "
              "currently displayed. Empty text stays unsaved."))
        self._settings_font_entry.connect(
            "changed", self._on_font_sample_changed)
        frow.pack_start(self._settings_font_entry, True, True, 0)
        return frame

    # → REF TB-ARCHIVE-2
    def _settings_frame_archive(self):
        frame = Gtk.Frame(label=_("Archive"))
        frame.set_border_width(8)
        frow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        frame.add(frow)
        alabel = Gtk.Label(label=_("Archive folder"))
        alabel.set_halign(Gtk.Align.START)
        frow.pack_start(alabel, False, False, 0)
        self._settings_archive_chooser = Gtk.FileChooserButton.new(
            _("Archive folder"), Gtk.FileChooserAction.SELECT_FOLDER)
        self._settings_archive_chooser.set_tooltip_text(
            _("Folder that the archive button moves files to – for "
              "example a Paperless \"consume\" directory."))
        if self._conf_archive_dir and os.path.isdir(self._conf_archive_dir):
            self._settings_archive_chooser.set_filename(
                self._conf_archive_dir)
        self._settings_archive_chooser.connect(
            "file-set", self._on_archive_dir_set)
        frow.pack_start(self._settings_archive_chooser, True, True, 0)
        return frame

    def _on_archive_dir_set(self, chooser):
        # Save immediately – no separate save button needed.
        folder = chooser.get_filename()
        self._conf_archive_dir = folder or ""
        self._config_save()

    def _on_show_at_start_toggled(self, chk):
        # Save immediately – no separate save button needed.
        self._conf_show_at_start = chk.get_active()
        self._config_save()

    # → REF TB-DOC-16
    def _on_debug_log_toggled(self, chk):
        # F65: save immediately, then switch the util flag live and
        # refresh the header dot; the env var stays stronger.
        self._conf_debug_log = chk.get_active()
        self._config_save()
        set_debug_log(chk.get_active())
        self._update_rec_dot()
        dbg("settings: debug logging toggle -> %s" % chk.get_active())

    # → REF TB-DOC-8
    def _on_folder_contents_toggled(self, chk):
        self._conf_folder_contents = chk.get_active()
        self._config_save()
        if self._path and os.path.isdir(self._path):
            self._render()

    # → REF TB-DOC-9
    def _on_font_sample_changed(self, entry):
        t = entry.get_text()
        if t.strip():
            self._conf_font_sample_text = t
            self._config_save()
        if self._path and os.path.splitext(
                self._path.lower())[1] in (".ttf", ".otf", ".ttc",
                                            ".woff"):
            self._render()

    # → REF TB-DOC-10
    def _on_linenumbers_toggled(self, chk):
        self._conf_text_linenumbers = chk.get_active()
        self._config_save()
        if self._last_textish and self._path:
            self._render()

    # → REF TB-DOC-17
    def _on_line_spacing_changed(self, spin):
        # F25: the value lands in memory at once; saving and the
        # re-render wait for the spin to go QUIET (400 ms).
        value = int(spin.get_value())
        if value == self._conf_text_line_spacing:
            return
        self._conf_text_line_spacing = value
        if self._spacing_render_id is not None:
            GLib.source_remove(self._spacing_render_id)
        self._spacing_render_id = GLib.timeout_add(
            400, self._on_line_spacing_quiet)

    # → REF TB-DOC-17
    def _on_line_spacing_quiet(self):
        # F25: fires once after the spin is quiet – one config
        # write and ONE re-render of the open text preview.
        self._spacing_render_id = None
        self._config_save()
        if self._last_textish and self._path:
            self._render()
        return False

    # → REF TB-DOC-18
    def _on_text_size_changed(self, spin):
        # B12 (1.3.2): the text size also rides IN the font
        # descriptions of explicit fonts – the CSS reload alone no
        # longer restyles the open text preview. F25 pattern:
        # render once after the spin went QUIET (400 ms).
        value = int(spin.get_value())
        if value == self._conf_text_font_size:
            return
        self._conf_text_font_size = value
        if self._textsize_render_id is not None:
            GLib.source_remove(self._textsize_render_id)
        self._textsize_render_id = GLib.timeout_add(
            400, self._on_text_size_quiet)

    # → REF TB-DOC-18
    def _on_text_size_quiet(self):
        # B12: fires once after the spin is quiet – one config
        # write and ONE re-render of the open text preview.
        self._textsize_render_id = None
        self._config_save()
        if self._last_textish and self._path:
            self._render()
        return False

    def _on_meta_size_changed(self, spin):
        # F69: save only – the reloaded CSS rule restyles the
        # open info tables live (no re-render needed).
        self._conf_meta_font_size = int(spin.get_value())
        self._config_save()

    # → REF TB-DOC-11
    def _on_syntax_toggled(self, chk):
        self._conf_text_syntax = chk.get_active()
        self._config_save()
        if self._last_textish and self._path:
            self._render()

    # → REF TB-DOC-12
    def _on_doc_limit_toggled(self, chk):
        self._conf_doc_page_limit = chk.get_active()
        self._config_save()
        if self._settings_pages_spin is not None:
            self._settings_pages_spin.set_sensitive(chk.get_active())
        self._rerender_docs()

    # → REF TB-DOC-13
    def _on_doc_max_pages_changed(self, spin):
        try:
            value = max(1, min(999, int(spin.get_value())))
            if value == self._conf_doc_max_pages:
                return
            self._conf_doc_max_pages = value
            self._config_save()
            self._rerender_docs()
        except Exception as e:
            dbg("toolbar/_on_doc_max_pages_changed: suppressed: %s" % e)

    # → REF TB-DOC-14
    def _rerender_docs(self):
        if self._last_docview and self._path:
            self._render()

    # → REF TB-DOC-15
    def _on_start_width_changed(self, spin):
        try:
            value = int(spin.get_value())
            if value == self._panel_width:
                return
            self._panel_width = value
            self._config_save()
            self._apply_panel_width_live()
        except Exception as e:
            dbg("toolbar/_on_start_width_changed: suppressed: %s" % e)

    def _on_toggle_accel(self, group, accelerable, key, mods):
        # F66: the toggle hides the whole shell (column + aux),
        # never the panel alone.
        if self._aux_shell.get_visible():
            self._aux_shell.hide()
        else:
            self._aux_shell.show_all()
        return True

    # → REF TB-DOC-19
    def _xbit_candidate(self, path):
        # F74: only files the kernel can execute qualify: shebang
        # scripts and ELF binaries (first 4 bytes, capped read).
        try:
            if not path or not os.path.isfile(path):
                return False
            with open(path, "rb") as fh:
                head = fh.read(4)
            return head.startswith(b"\x7fELF") or head.startswith(b"#!")
        except Exception as e:
            dbg("toolbar/_xbit_candidate: suppressed: %s" % e)
            return False

    # → REF TB-DOC-20
    def _on_xbit_clicked(self, button):
        # F74: toggle ALL execute bits (u/g/o) – a file that stayed
        # executable through group/other looked unreliable.
        path = self._path
        if not path:
            return
        try:
            st = os.stat(path)
            mode = stat.S_IMODE(st.st_mode)
            if mode & 0o111:
                os.chmod(path, mode & ~0o111)
                dbg("toolbar/xbit: %s: x-bits removed (u/g/o)"
                    % os.path.basename(path))
            else:
                os.chmod(path, mode | 0o111)
                dbg("toolbar/xbit: %s: x-bits set (u/g/o)"
                    % os.path.basename(path))
            self._update_xbit_button()
        except Exception as e:
            dbg("toolbar/_on_xbit_clicked: suppressed: %s" % e)

    # → REF TB-DOC-21
    def _update_xbit_button(self):
        # F74: single refresh point (render/toggle/monitor):
        # visibility, tooltip, red state and the live file monitor.
        path = self._path
        on = False
        try:
            if (path and len(self._names) == 1
                    and self._xbit_candidate(path)):
                on = bool(os.stat(path).st_mode & 0o111)
                self._btn_xbit.show()
                self._xbit_watch(path)
            else:
                self._btn_xbit.hide()
                self._xbit_watch(None)
        except Exception as e:
            self._btn_xbit.hide()
            dbg("toolbar/_update_xbit_button: suppressed: %s" % e)
        ctx = self._btn_xbit.get_style_context()
        if on:
            ctx.add_class("pvw-xbit-set")
            self._btn_xbit.set_tooltip_text(_(
                "Executable – click to remove the executable bit"))
        else:
            ctx.remove_class("pvw-xbit-set")
            self._btn_xbit.set_tooltip_text(_(
                "Make the file executable"))

    # → REF TB-DOC-22
    def _xbit_watch(self, path):
        # F74: one Gio file monitor on the previewed file – a
        # permission flip from outside refreshes the button live.
        try:
            if getattr(self, "_xbit_mon", None) is not None:
                self._xbit_mon.cancel()
                self._xbit_mon = None
            if not path:
                return
            mon = Gio.File.new_for_path(path).monitor_file(
                Gio.FileMonitorFlags.NONE, None)
            mon.connect("changed", self._on_xbit_file_changed)
            self._xbit_mon = mon
        except Exception as e:
            dbg("toolbar/_xbit_watch: suppressed: %s" % e)

    # → REF TB-DOC-22
    def _on_xbit_file_changed(self, mon, gfile, other, event):
        # F74: inotify IN_ATTRIB path (permissions dialog) – the
        # refresh recreates the monitor safely inside its callback.
        self._update_xbit_button()

    # → REF TB-PRINT-1
    def _on_print_clicked(self, button):
        # F77: print the previewed office document – the docs
        # mixin converts/caches and runs the GTK print dialog.
        # F78: Markdown/EML print directly from the preview text.
        # F80: a PDF falls through to _print_document and prints
        # directly (poppler only).
        path = self._path
        if not path:
            return
        ext = os.path.splitext(path.lower())[1]
        if ext in _PRINT_TEXT_EXTS:
            self._print_text_document(path)
        else:
            self._print_document(path)

    # → REF TB-PRINT-1
    def _update_print_button(self):
        # F77: same refresh points as the x-bit button – visible
        # only for a SINGLE office file (and only when the
        # conversion stack exists: soffice + poppler). F78: also
        # for a single Markdown/EML file (text print path, needs
        # PangoCairo instead of the office stack). F80: also for
        # a single PDF (direct poppler print, no office stack).
        on = False
        try:
            if self._path and len(self._names) == 1:
                ext = os.path.splitext(self._path.lower())[1]
                if ext in _OFFICE_EXTS and SOFFICE and HAVE_POPPLER:
                    on = True
                elif ext == ".pdf" and HAVE_POPPLER:
                    # F80: PDF prints directly (poppler only).
                    on = True
                elif ext in _PRINT_TEXT_EXTS and HAVE_PANGOCAIRO:
                    on = True
        except Exception as e:
            dbg("toolbar/_update_print_button: suppressed: %s" % e)
        if on:
            self._btn_print.show()
        else:
            self._btn_print.hide()

    def _archive_icon_name(self):
        # F81: archive-specific symbolic icon when the theme has
        # one, else the standard list-add-symbolic – has_icon only
        # matches real symbolic names, so no colored icon appears.
        theme = Gtk.IconTheme.get_default()
        for name in ("archive-insert-symbolic",
                     "add-files-to-archive-symbolic"):
            if theme.has_icon(name):
                return name
        return "list-add-symbolic"

    # → REF TB-ARCHIVE-1
    def _on_archive_clicked(self, button):
        # F81: move the previewed file to the configured archive
        # folder; without a folder the settings open instead.
        path = self._path
        if not path:
            return
        target = self._conf_archive_dir
        if not target or not os.path.isdir(target):
            dbg("toolbar/_on_archive_clicked: no archive folder set")
            self._open_settings_aux()
            return
        try:
            dest = self._archive_target_path(path, target)
            shutil.move(path, dest)
            dbg("toolbar/_on_archive_clicked: %s -> %s" % (path, dest))
            # The file is gone – clear the preview; Nemo drops the
            # row on its own via its file monitor.
            self.set_selection([], None)
        except Exception as e:
            dbg("toolbar/_on_archive_clicked: failed: %s" % e)
            try:
                self._clear_content()
                pack_hint(self._content,
                          _("Move to archive folder failed."))
                self._content.show_all()
            except Exception as e2:
                dbg("toolbar/_on_archive_clicked hint: suppressed: %s" % e2)

    def _archive_target_path(self, path, target_dir):
        # F81: never overwrite – numeric suffix when it exists.
        base = os.path.basename(path)
        dest = os.path.join(target_dir, base)
        if not os.path.exists(dest):
            return dest
        root, ext = os.path.splitext(base)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(target_dir,
                                "%s-%d%s" % (root, n, ext))
            n += 1
        return dest

    # → REF TB-ARCHIVE-1
    def _update_archive_button(self):
        # F81: same refresh points as the print button – visible
        # only for a SINGLE office/PDF/EML/Markdown file. Without
        # a configured folder the click opens the settings.
        on = False
        try:
            if self._path and len(self._names) == 1:
                ext = os.path.splitext(self._path.lower())[1]
                if ext in _ARCHIVE_EXTS:
                    on = True
        except Exception as e:
            dbg("toolbar/_update_archive_button: suppressed: %s" % e)
        if on:
            self._btn_archive.show()
        else:
            self._btn_archive.hide()


PREVIEWER_VERSION = "1.16.1"
dbg("previewer_toolbar %s loaded (F29: action bar, settings dialog, "
    "Ctrl+Alt+P shortcut as its own mixin)"
    % PREVIEWER_VERSION)