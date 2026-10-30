#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer – Toolbar-Modul (previewer_toolbar.py)
================================================

STAND: Version 0.27.0 – F12 Teil 3 (Nutzer-Wunsch): Neue Rubrik
„Dokumente“ – Vorschauseiten von PDF- und Office-Dokumenten begrenzen
(Performance) oder unbegrenzt anzeigen, maximale Seitenzahl 1–999 frei
wählbar; Änderungen speichern sofort und wirken live über den Merker
_last_docview. Die ActionBar (F19), Strg+Alt+P und der 0.15.0-Stand
(F29: Mixin-Modul) bleiben unverändert.

Gehört zur jetzt achtteiligen Extension "Previewer" (siehe
previewer.py); PREVIEWER_VERSION muss in allen Modulen identisch
sein – der Einstieg prüft das beim Laden.
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
    PANEL_WIDTH, PANEL_MIN_WIDTH,
    TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
)


# =============================== Toolbar ====================================


class PreviewToolbarMixin:
    """Mixin: ActionBar (F19) + Einstellungsfenster (F12) des Panels."""

    def _build_toolbar(self, window):
        # --- F19: Toolbar am unteren Rand der Vorschauspalte (0.11.0) ---
        # → REF TB-F19-1
        self._toolbar_sep = Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self._toolbar_sep, False, False, 0)
        self._toolbar = Gtk.ActionBar()
        self._btn_settings = Gtk.Button.new_from_icon_name(
            "preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self._btn_settings.set_tooltip_text("Einstellungen")
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
        except Exception:
            pass

        # Tastenkürzel zum Wieder-Einblenden
        try:
            accel = Gtk.AccelGroup()
            window.add_accel_group(accel)
            accel.connect(TOGGLE_ACCEL_KEY, TOGGLE_ACCEL_MODS,
                          Gtk.AccelFlags.VISIBLE, self._on_toggle_accel)
        except Exception:
            pass

    def _on_settings_clicked(self, button):
        """
        F19/F12 (0.12.0): Einstellungs-Knopf der Toolbar öffnet das
        Konfigurationsfenster. Dort sammeln sich künftig ALLE Einstel-
        lungen der Vorschauspalte; Änderungen greifen sofort und
        landen ohne Extra-Knopf in der Konfigurationsdatei.
        """
        self._open_settings_window()

    def _open_settings_window(self):
        """
        F12 (0.12.0): Konfigurationsfenster der Vorschauspalte. Der
        Rahmen steht jetzt; hier sammeln sich künftig ALLE Einstel-
        lungen (F12-Katalog: Panelbreite, Dokument-Deckel, Wasser-
        fall-Probetext …) – jede mit sofortiger Speicherung via
        _config_save. Nur EINE Instanz: ein erneuter Klick auf das
        Zahnrad holt das bestehende Fenster nach vorn.
        """
        if self._settings_win is not None:
            try:
                self._settings_win.present()
                return
            except Exception:
                self._settings_win = None
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title("Nemo-Previewer – Einstellungen")
        try:
            win.set_transient_for(self._window)
        except Exception:
            pass
        win.set_default_size(420, -1)
        win.set_border_width(12)
        win.connect("destroy", self._on_settings_win_destroyed)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        win.add(box)

        frame = Gtk.Frame(label="Allgemein")
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_border_width(8)
        frame.add(fbox)

        chk = Gtk.CheckButton(label="Vorschauspalte beim Start anzeigen")
        chk.set_tooltip_text(
            "Abhaken, damit die Vorschauspalte nach dem Start von "
            "Nemo zunächst ausgeblendet bleibt (Strg+Alt+P blendet "
            "sie jederzeit wieder ein)")
        chk.set_active(self._conf_show_at_start)
        chk.connect("toggled", self._on_show_at_start_toggled)
        fbox.pack_start(chk, False, False, 0)

        # → REF TB-F12-1
        wrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_width = Gtk.Label(label="Standardbreite beim Start")
        lbl_width.set_halign(Gtk.Align.START)
        wrow.pack_start(lbl_width, False, False, 0)
        adj = Gtk.Adjustment(value=self._panel_width,
                             lower=PANEL_MIN_WIDTH, upper=1600,
                             step_increment=10, page_increment=50)
        self._settings_spin = Gtk.SpinButton.new(adj, 1.0, 0)
        self._settings_spin.set_value(self._panel_width)
        self._settings_spin.set_tooltip_text(
            "Breite der Vorschauspalte, mit der Nemo startet – "
            "Ziehen am Trenner übernimmt die gewählte Breite "
            "automatisch als neuen Wert")
        self._settings_spin.connect("value-changed",
                                    self._on_start_width_changed)
        wrow.pack_start(self._settings_spin, False, False, 0)
        self._settings_width_label = Gtk.Label()
        self._settings_width_label.get_style_context().add_class(
            "dim-label")
        self._settings_width_label.set_halign(Gtk.Align.START)
        wrow.pack_start(self._settings_width_label, False, False, 0)
        self._update_width_hint()
        fbox.pack_start(wrow, False, False, 0)
        box.pack_start(frame, False, False, 0)

        # --- F24 (0.16.0): Rubrik „Textdateien“ --------------------------
        # Nur die reine Text-Vorschau (Textdateien und endungslose
        # Textdateien) – gerenderte Vorschauen (Markdown, E-Mail,
        # E-Book, Font-Wasserfall) bleiben ohne Nummern.
        tframe = Gtk.Frame(label="Textdateien")
        tfbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tfbox.set_border_width(8)
        tframe.add(tfbox)
        ln = Gtk.CheckButton(
            label="Zeilennummern anzeigen (nicht kopierbar)")
        ln.set_tooltip_text(
            "Zeilennummern am linken Rand der Text-Vorschau. Die "
            "Nummern sind eine Randzeichnung außerhalb des Texts – "
            "ausgewählt und kopiert wird nur der Text selbst.")
        ln.set_active(self._conf_text_linenumbers)
        ln.connect("toggled", self._on_linenumbers_toggled)
        tfbox.pack_start(ln, False, False, 0)
        box.pack_start(tframe, False, False, 0)

        # --- F12 Teil 3 (0.27.0): Rubrik „Dokumente“ (PDF/Office) ----
        dframe = Gtk.Frame(label="Dokumente (PDF und Office)")
        dfbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dfbox.set_border_width(8)
        dframe.add(dfbox)
        lim = Gtk.CheckButton(
            label="Vorschauseiten begrenzen (Performance)")
        lim.set_tooltip_text(
            "Abhaken, damit PDF- und Office-Dokumente ohne Begrenzung "
            "komplett angezeigt werden – bei sehr großen Dokumenten "
            "kostet das mehr Speicher und Zeit.")
        lim.set_active(self._conf_doc_page_limit)
        lim.connect("toggled", self._on_doc_limit_toggled)
        dfbox.pack_start(lim, False, False, 0)
        prow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_pages = Gtk.Label(label="Maximale Seitenzahl")
        lbl_pages.set_halign(Gtk.Align.START)
        prow.pack_start(lbl_pages, False, False, 0)
        padj = Gtk.Adjustment(value=self._conf_doc_max_pages,
                              lower=1, upper=999,
                              step_increment=1, page_increment=10)
        self._settings_pages_spin = Gtk.SpinButton.new(padj, 1.0, 0)
        self._settings_pages_spin.set_value(self._conf_doc_max_pages)
        self._settings_pages_spin.set_sensitive(self._conf_doc_page_limit)
        self._settings_pages_spin.set_tooltip_text(
            "Anzahl der Seiten, die PDF- und Office-Vorschauen höchstens "
            "untereinander zeigen – greift live, auch für das gerade "
            "angezeigte Dokument.")
        self._settings_pages_spin.connect(
            "value-changed", self._on_doc_max_pages_changed)
        prow.pack_start(self._settings_pages_spin, False, False, 0)
        dfbox.pack_start(prow, False, False, 0)
        box.pack_start(dframe, False, False, 0)

        hint = Gtk.Label(
            label="Weitere Einstellungen (Wasserfall-Probetext …)\n"
                  "folgen hier in späteren Versionen.")
        hint.get_style_context().add_class("dim-label")
        hint.set_halign(Gtk.Align.START)
        box.pack_start(hint, False, False, 0)

        btn_close = Gtk.Button.new_with_label("Schließen")
        btn_close.connect("clicked", lambda *a: win.destroy())
        box.pack_start(btn_close, False, False, 0)

        win.show_all()
        self._settings_win = win

    def _on_settings_win_destroyed(self, *a):
        self._settings_win = None
        self._settings_spin = None
        self._settings_width_label = None
        self._settings_pages_spin = None

    def _on_show_at_start_toggled(self, chk):
        # Sofort speichern – kein separater Speichern-Knopf nötig.
        self._conf_show_at_start = chk.get_active()
        self._config_save()

    def _on_linenumbers_toggled(self, chk):
        """
        F24 (0.16.0): Zeilennummern sofort speichern und live
        anwenden. 0.16.2: Neu aufgebaut wird jede TextView-basierte
        Vorschau (Text, Markdown, EML, E-Book, Font – der Merker
        _last_textish steht im Kern jetzt generell auf True, wenn
        die aktuelle Vorschau TextView-basiert ist), damit der
        Toggle in BEIDE Richtungen wirkt – auch beim Re-Aktivieren.
        PDF, Office, Audio, Video, Bild und Ordner bleiben
        unberührt und werden nicht neu gerendert.
        """
        self._conf_text_linenumbers = chk.get_active()
        self._config_save()
        if self._last_textish and self._path:
            self._render()

    def _on_doc_limit_toggled(self, chk):
        """
        F12 Teil 3 (0.27.0): Dokument-Deckel an/aus – sofort speichern
        und live anwenden. Der SpinButton zur Seitenzahl ist nur bei
        aktivem Deckel bedienbar; eine angezeigte Dokument-Vorschau
        baut sich über den Merker _last_docview sofort neu auf.
        """
        self._conf_doc_page_limit = chk.get_active()
        self._config_save()
        if self._settings_pages_spin is not None:
            self._settings_pages_spin.set_sensitive(chk.get_active())
        self._rerender_docs()

    def _on_doc_max_pages_changed(self, spin):
        """
        F12 Teil 3 (0.27.0): Maximale Seitenzahl (1–999) – sofort
        speichern und live anwenden, wie der Zeilennummern-Toggle.
        """
        try:
            value = max(1, min(999, int(spin.get_value())))
            if value == self._conf_doc_max_pages:
                return
            self._conf_doc_max_pages = value
            self._config_save()
            self._rerender_docs()
        except Exception:
            pass

    def _rerender_docs(self):
        """
        F12 Teil 3 (0.27.0): Aktuelle PDF-/Office-Seitenansicht live
        neu aufbauen – das Gegenstück zum Merker _last_textish der
        Zeilennummern: Nur Dokument-Vorschauen reagieren, alles andere
        (Bild, Audio, Text …) bleibt unberührt.
        """
        if self._last_docview and self._path:
            self._render()

    def _on_start_width_changed(self, spin):
        """
        F12 (0.13.0): Neue Startbreite aus dem SpinButton – sofort
        übernehmen, live anwenden und speichern (kein Extra-Knopf).
        """
        try:
            value = int(spin.get_value())
            if value == self._panel_width:
                return
            self._panel_width = value
            self._panel_width_saved = value
            self._config_save()
            self._apply_panel_width_live()
            self._update_width_hint()
        except Exception:
            pass

    def _update_width_hint(self):
        """
        F12 (0.13.0): „Standard … · aktuell …"-Zeile im Einstellungs-
        fenster pflegen: genannter Default (PANEL_WIDTH) und der
        aktuelle Panelwert – genau die beiden Größen, die der Nutzer
        dort sehen will.
        """
        if self._settings_width_label is None:
            return
        try:
            self._settings_width_label.set_label(
                "Standard: %d px · aktuell: %d px"
                % (PANEL_WIDTH, self._panel_width))
        except Exception:
            pass

    def _on_toggle_accel(self, group, accelerable, key, mods):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
        return True




PREVIEWER_VERSION = "0.27.0"
dbg("previewer_toolbar %s geladen (F29: ActionBar, Einstellungs-"
    "fenster und Tastenkürzel Strg+Alt+P als eigenes Mixin)"
    % PREVIEWER_VERSION)