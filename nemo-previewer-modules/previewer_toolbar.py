#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nemo-previewer
previewer_toolbar.py – Version 0.48.0

Panel toolbar and settings window: action bar, preview toggle,
Ctrl+Alt+P shortcut and all preference widgets.
"""

import sys
import os

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg,
    PANEL_MIN_WIDTH,
    TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
)


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
        self._btn_settings = Gtk.Button.new_from_icon_name(
            "preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self._btn_settings.set_tooltip_text("Settings")
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
        self._open_settings_window()

    # → REF TB-DOC-3
    def _open_settings_window(self):
        if self._settings_win is not None:
            try:
                self._settings_win.present()
                return
            except Exception:
                self._settings_win = None
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title("Nemo-Previewer – Settings")
        try:
            win.set_transient_for(self._window)
        except Exception as e:
            dbg("toolbar/_open_settings_window: suppressed: %s" % e)
        win.set_default_size(420, -1)
        win.set_border_width(12)
        win.connect("destroy", self._on_settings_win_destroyed)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        win.add(box)
        box.pack_start(self._settings_frame_general(), False, False, 0)
        box.pack_start(self._settings_frame_text(), False, False, 0)
        box.pack_start(self._settings_frame_docs(), False, False, 0)
        box.pack_start(self._settings_frame_fonts(), False, False, 0)

        btn_close = Gtk.Button.new_with_label("Close")
        btn_close.connect("clicked", lambda *a: win.destroy())
        box.pack_start(btn_close, False, False, 0)

        win.show_all()
        self._settings_win = win

    # → REF TB-DOC-4
    def _settings_frame_general(self):
        frame = Gtk.Frame(label="General")
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        chk = Gtk.CheckButton(label="Show preview side panel at launch")
        chk.set_tooltip_text(
            "Uncheck to keep the preview side panel hidden after "
            "Nemo starts (Ctrl+Alt+P shows it again at any time)")
        chk.set_active(self._conf_show_at_start)
        chk.connect("toggled", self._on_show_at_start_toggled)
        fbox.pack_start(chk, False, False, 0)

        # F48: folder contents list on/off – default on; off shows the
        # plain folder icon with file info (→ REF PAN-FOLDER-2).
        chk = Gtk.CheckButton(
            label="Show folder contents in the preview")
        chk.set_tooltip_text(
            "Uncheck to show only the plain folder icon with file "
            "info instead of the contents list")
        chk.set_active(self._conf_folder_contents)
        chk.connect("toggled", self._on_folder_contents_toggled)
        fbox.pack_start(chk, False, False, 0)

        # → REF TB-F12-1
        wrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_width = Gtk.Label(label="Default width at launch")
        lbl_width.set_halign(Gtk.Align.START)
        wrow.pack_start(lbl_width, False, False, 0)
        adj = Gtk.Adjustment(value=self._panel_width,
                             lower=PANEL_MIN_WIDTH, upper=1600,
                             step_increment=10, page_increment=50)
        self._settings_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_spin.set_value(self._panel_width)
        self._settings_spin.set_tooltip_text(
            "Width of the preview side panel Nemo opens with at "
            "every start – dragging the divider applies only to "
            "the current session")
        self._settings_spin.connect("value-changed",
                                    self._on_start_width_changed)
        wrow.pack_start(self._settings_spin, False, False, 0)
        fbox.pack_start(wrow, False, False, 0)
        return frame

    # → REF TB-DOC-5
    def _settings_frame_text(self):
        frame = Gtk.Frame(label="Text files")
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        ln = Gtk.CheckButton(
            label="Show line numbers (not copyable)")
        ln.set_tooltip_text(
            "Line numbers in the left margin of the text preview. "
            "The numbers are drawn outside the text – only the "
            "text itself is selected and copied.")
        ln.set_active(self._conf_text_linenumbers)
        ln.connect("toggled", self._on_linenumbers_toggled)
        fbox.pack_start(ln, False, False, 0)
        # F44: syntax highlighting as a switch – default on, saved
        # immediately and applied live.
        syn = Gtk.CheckButton(
            label="Syntax highlighting in source code files")
        syn.set_tooltip_text(
            "Colour source code (.py, .sh, .c …) in the text preview – "
            "requires the optional package gir1.2-gtksource-4; "
            "when unchecked, the plain text always shows.")
        syn.set_active(self._conf_text_syntax)
        syn.connect("toggled", self._on_syntax_toggled)
        fbox.pack_start(syn, False, False, 0)
        return frame

    # → REF TB-DOC-6
    def _settings_frame_docs(self):
        frame = Gtk.Frame(label="Documents (PDF and Office)")
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        lim = Gtk.CheckButton(
            label="Limit preview pages (performance)")
        lim.set_tooltip_text(
            "Uncheck to display PDF and Office documents completely "
            "without a limit – with very large documents this "
            "costs more memory and time.")
        lim.set_active(self._conf_doc_page_limit)
        lim.connect("toggled", self._on_doc_limit_toggled)
        fbox.pack_start(lim, False, False, 0)

        prow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_pages = Gtk.Label(label="Maximum number of pages")
        lbl_pages.set_halign(Gtk.Align.START)
        prow.pack_start(lbl_pages, False, False, 0)
        padj = Gtk.Adjustment(value=self._conf_doc_max_pages,
                              lower=1, upper=999,
                              step_increment=1, page_increment=10)
        self._settings_pages_spin = Gtk.SpinButton.new(padj, 1.0, 0)
        self._settings_pages_spin.set_value(self._conf_doc_max_pages)
        self._settings_pages_spin.set_sensitive(self._conf_doc_page_limit)
        self._settings_pages_spin.set_tooltip_text(
            "Number of pages that PDF and Office previews show at "
            "most – applies live, also to the document currently "
            "displayed.")
        self._settings_pages_spin.connect(
            "value-changed", self._on_doc_max_pages_changed)
        prow.pack_start(self._settings_pages_spin, False, False, 0)
        fbox.pack_start(prow, False, False, 0)
        return frame

    # → REF TB-DOC-7
    def _settings_frame_fonts(self):
        frame = Gtk.Frame(label="Fonts")
        frame.set_border_width(8)
        frow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=8)
        frame.add(frow)
        flabel = Gtk.Label(label="Waterfall sample text")
        flabel.set_halign(Gtk.Align.START)
        frow.pack_start(flabel, False, False, 0)
        self._settings_font_entry = Gtk.Entry()
        self._settings_font_entry.set_text(self._conf_font_sample_text)
        self._settings_font_entry.set_tooltip_text(
            "Text for the font preview – applies live to the font "
            "currently displayed. Empty text stays unsaved.")
        self._settings_font_entry.connect(
            "changed", self._on_font_sample_changed)
        frow.pack_start(self._settings_font_entry, True, True, 0)
        return frame

    def _on_settings_win_destroyed(self, *a):
        self._settings_win = None
        self._settings_spin = None
        self._settings_pages_spin = None

    def _on_show_at_start_toggled(self, chk):
        # Save immediately – no separate save button needed.
        self._conf_show_at_start = chk.get_active()
        self._config_save()

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
                self._path.lower())[1] in (".ttf", ".otf", ".ttc"):
            self._render()

    # → REF TB-DOC-10
    def _on_linenumbers_toggled(self, chk):
        self._conf_text_linenumbers = chk.get_active()
        self._config_save()
        if self._last_textish and self._path:
            self._render()

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
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
        return True


PREVIEWER_VERSION = "0.48.0"
dbg("previewer_toolbar %s loaded (F29: action bar, settings dialog, "
    "Ctrl+Alt+P shortcut as its own mixin)"
    % PREVIEWER_VERSION)