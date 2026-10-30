#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer
=========

STAND: Version 0.28.1 – F40 (Nutzer-Wunsch): Umschalt-Knopf für die
Vorschau-Seitenleiste in Nemos Werkzeugleiste (rechts, neben der
Ansichtenauswahl; CSD-Titelleiste oder klassische Toolbar),
synchron mit Strg+Alt+P (→ REF ENT-TOGGLE-1).
Dies ist die EINSTIEGS-Datei der acht zusammengehörigen Dateien
(previewer.py, previewer_panel.py, previewer_select.py,
previewer_util.py, previewer_toolbar.py, previewer_render_media.py,
previewer_render_docs.py, previewer_render_text.py) – alle müssen im
gleichen Ordner liegen und die gleiche Version tragen.
Projekt-Repository: https://github.com/NBoESFWbVaf/nemo-previewer
(Versionsverlauf: changelog.md im Repository).

Eine Nemo-Python-Extension namens "Previewer": dockt rechts im Nemofenster
ein Panel an und zeigt eine gerenderte Vorschau der aktuell selektierten
Datei.

Unterstützte Vorschauen
-----------------------
- Bilder (JPEG, PNG, WebP, GIF, TIFF, ... alles, was Gdk-Pixbuf kennt)
- Text/Quellcode (read-only, monospace; endungslose Textdateien werden
  über eine Inhaltsprüfung erkannt)
- Markdown (.md): gerendert – Überschriften, Fett/Kursiv, Code, Listen
- E-Mail-Dateien (.eml): Kopfzeilen und Textkörper
- PDF (alle Seiten scrollbar untereinander; benötigt gir1.2-poppler)
- Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX): scharfe Seitenansicht
  über LibreOffice-Hintergrundkonvertierung nach PDF (Cache in
  ~/.cache/previewer); ohne LibreOffice die eingebettete Miniaturansicht
- Audio (Tags, Cover, Play/Pause mit Seek-Leiste; via GStreamer)
- Video (Kachel mit Tags und Dauer; Abspielen über den Öffnen-Knopf)
- Ordner und alles andere: Icon + Dateiinformationen

Installation
------------
Siehe INSTALL.md im Repository (Anleitung in Englisch).

Bedienung
---------
- Panel ein-/ausblenden: Strg+Alt+P oder den Umschalt-Knopf in Nemos
  Werkzeugleiste (neben der Ansichtenauswahl)
- Trenner zwischen Dateiansicht und Panel ist verschiebbar (Gtk.Paned)
- Play/Pause & Seek bei Audio über die Bedienelemente im Panel
- PDF: alle Seiten untereinander, im Vorschau-Bereich scrollbar

Technik (für Interessierte)
---------------------------
Das offizielle Nemo-Extension-API bietet keinen "Side-Panel-Provider".
Das Panel nutzt deshalb die bewährte Crowbar-Technik von nemo-terminal:
Über Nemo.LocationWidgetProvider erhält man ein Referenz-Widget im Slot,
steigt im Widget-Baum auf und verpackt den Fenster-Inhaltsbereich (den
Nemo-Pane) in ein horizontales Gtk.Paned, dessen zweite Hälfte das
Vorschau-Panel ist – es sitzt damit fest an der rechten Fensterrandkante.

Die Auswahl wird ermittelt über (previewer_select.py):
- direkte Auswahl über NemoView.peek_selection: der Funktionszeiger
  wird aus dem Klassen-VTable von NemoView gelesen (libnemo-private
  ist auf Mint 22 statisch gelinkt, es gibt keine ladbare .so); die
  NemoFile-Einträge werden über ihr NemoFileInfo-Interface befragt,
- Auswahl-Signale, die zur Laufzeit entdeckt und verbunden werden –
  im Widget-Teilbaum der Ansicht und auf den ATK-Objekten; so ist es
  egal, wie Nemo seine Signale genau benennt,
- Gtk.IconView-/Gtk.TreeView-Auswahl als Fallback (das Nemo-Listenmodell
  trägt den Dateinamen erst in den Attribut-Spalten; Spalte 0 enthält
  das NemoFile-Objekt),
- ATK-Selection, ATK-Zustände und Fokus nur als Fallback,
- als Sicherheitsnetz einen leichtgewichtigen Timer.

Office-Dokumente: LibreOffice konvertiert im Hintergrund (soffice
--headless --convert-to pdf) einmalig nach PDF; das Ergebnis wird unter
~/.cache/previewer gecacht (Key = Hash des Dateipfads; gültig, solange
die Quelldatei nicht neuer ist als das Cache-PDF). Poppler rendert daraus
alle Seiten scharf, untereinander scrollbar und live skalierbar. Während
der Konvertierung zeigt das Panel die eingebettete ZIP-Miniaturansicht
mit Hinweis.

Alle Zugriffe sind defensiv gekapselt (try/except), damit die Extension
Nemo niemals zum Absturz bringen kann. Alles läuft im Nemo-Prozess.

Getestet gegen Nemo 6.x unter Linux Mint 22. Da interne Widget-Strukturen
von Nemo-Updates geändert werden könnten, ist die Injektion mit Fallbacks
und Reconciliation (Prüfung pro Timer-Tick) abgesichert.

Autor: für Mirakuli Teebaum, 2026. Lizenz: GPLv3 oder später.
"""

import sys
import traceback
import urllib.parse

import gi

gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Atk', '1.0')

from gi.repository import GObject, Nemo, Gtk, GLib, Atk

# Geschwister-Module finden, egal wie nemo-python diese Datei geladen hat.
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from previewer_util import (
    dbg, diag, VERBOSE_DIAG,
    walk, type_name,
    PANEL_WIDTH, PANEL_MIN_WIDTH, POLL_MS,
    pick_icon,
)
from previewer_select import (
    find_view, selection_signals, SelectionReader,
    _atk_children, _dump_widget_tree,
)
from previewer_panel import PreviewPanel

# PREVIEWER_VERSION muss in ALLEN acht Modulen identisch sein. Der Einstieg
# prüft die geladenen Module: Liegt im Extension-Ordner noch eine veraltete
# Fassung, erscheint im Terminal sofort eine klare Achtung-Meldung.
PREVIEWER_VERSION = "0.28.1"
import previewer_util
import previewer_select
import previewer_panel
import previewer_toolbar
import previewer_render_media
import previewer_render_docs
import previewer_render_text

for _mod in (previewer_util, previewer_select, previewer_panel,
             previewer_toolbar, previewer_render_media,
             previewer_render_docs, previewer_render_text):
    _ver = getattr(_mod, "PREVIEWER_VERSION", None)
    if _ver != PREVIEWER_VERSION:
        dbg("ACHTUNG: %s.py hat Version %r, erwartet wird %r – Datei im "
            "Extension-Ordner durch die aktuelle Fassung ersetzen!"
            % (_mod.__name__, _ver, PREVIEWER_VERSION))

# ============================== Provider ===================================

class PanelState:
    """Zustand pro Nemo-Fenster (am Fenster-Objekt gespeichert)."""

    def __init__(self, window):
        self.window = window
        self.panel = PreviewPanel(window)
        self.hpaned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        self.dir_path = None
        self.view = None
        self.view_handlers = []
        self.poll_id = 0
        self.last_sel = None
        self.pos_pending = True
        self.none_dbg_at = 0
        self._a11y_dumps = 0
        self.toggle_btn = None
        self.hpaned.connect("size-allocate", self._on_size_allocate)

    def _install_toolbar_toggle(self):
        """
        F40 (Nutzer-Wunsch): Ein-/aus-Knopf für die Vorschau-Seiten-
        leiste in Nemos Werkzeugleiste, neben der Ansichtenauswahl.
        Der Zustand bleibt synchron: Strg+Alt+P und der Knopf
        schalten dasselbe Panel, notify::visible zieht nach.
        """
        # → REF ENT-TOGGLE-1
        # Idempotent: Die Versöhnung läuft mehrfach – ein bereits
        # gepackter Knopf (am Fenster-Objekt gemerkt) wird nicht
        # doppelt hinzugefügt.
        if self.toggle_btn is not None or getattr(
                self.window, "_previewer_toggle", None) is not None:
            return
        icon = pick_icon(("builder-view-right-pane-symbolic",
                          "view-right-pane", "sidebar-show-symbolic",
                          "sidebar-symbolic"), "pan-end-symbolic")
        # Route 1: Titelleiste als GtkHeaderBar (Desktops mit CSD) –
        # Knopf per pack_end rechts hinten anfügen.
        try:
            bar = self.window.get_titlebar()
        except Exception:
            bar = None
        if isinstance(bar, Gtk.HeaderBar):
            btn = Gtk.ToggleButton()
            btn.set_image(Gtk.Image.new_from_icon_name(
                icon, Gtk.IconSize.BUTTON))
            btn.set_relief(Gtk.ReliefStyle.NONE)
            self._pack_toggle(btn, icon, "Titelleiste",
                              lambda b: bar.pack_end(b))
            return
        # Route 2: klassisches Nemo – die Ansichts-Knöpfe sitzen in
        # einer GtkToolbar (NemoToolbar ist ein GtkBox drumherum).
        # Diese im Widget-Baum suchen und den Umschalter als ToolItem
        # direkt hinter die Ansichts-Knöpfe setzen.
        toolbar = self._find_first_widget(
            self.window, lambda w: isinstance(w, Gtk.Toolbar))
        if toolbar is None:
            dbg("Vorschau-Knopf: weder HeaderBar noch GtkToolbar "
                "gefunden – nur Strg+Alt+P")
            return
        btn = Gtk.ToggleToolButton()
        btn.set_icon_name(icon)
        pos = self._pos_after_view_buttons(toolbar)
        self._pack_toggle(btn, icon, "Toolbar",
                           lambda b: toolbar.insert(b, pos))

    def _pack_toggle(self, btn, icon, where, pack):
        """F40: Knopf fertigmachen, einpacken, verkabeln, loggen."""
        btn.set_tooltip_text("Vorschau-Seitenleiste (Strg+Alt+P)")
        btn.connect("toggled", self._on_toolbar_toggle)
        self.toggle_btn = btn
        pack(btn)
        # Zustand nachziehen, wenn das Panel woanders umgeschaltet
        # wird (Strg+Alt+P, Start-Einstellung show_at_start).
        self.panel.connect("notify::visible", self._on_panel_visibility)
        try:
            self.window._previewer_toggle = btn
        except Exception:
            pass
        btn.show()
        dbg("Vorschau-Knopf in Nemos %s gesetzt (Icon: %s)"
            % (where, icon))

    def _find_first_widget(self, widget, pred):
        """F40: Widget-Baum rekursiv durchsuchen, erstes Match liefern."""
        if pred(widget):
            return widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                found = self._find_first_widget(child, pred)
                if found is not None:
                    return found
        return None

    def _pos_after_view_buttons(self, toolbar):
        """
        F40: Position direkt hinter dem letzten Ansichts-Knopf der
        Toolbar (dessen Icon heißt view-…-symbolic). Ohne Fund -1,
        dann hängt insert() hinten an.
        """
        pos = -1
        for item in toolbar.get_children():
            child = item.get_child()
            if child is not None and self._has_view_icon(child):
                pos = toolbar.get_item_index(item)
        return -1 if pos < 0 else pos + 1

    def _has_view_icon(self, widget):
        """F40: Hat das Widget (rekursiv) ein view-…-Icon? (Gtk.Image)."""
        if isinstance(widget, Gtk.Image):
            try:
                name = widget.get_icon_name()[0]
            except Exception:
                name = None
            if name and name.startswith("view-"):
                return True
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                if self._has_view_icon(child):
                    return True
        return False

    def _on_toolbar_toggle(self, btn):
        """F40: Knopf schaltet dieselbe Route wie Strg+Alt+P."""
        if btn.get_active():
            self.panel.show_all()
        else:
            self.panel.hide()

    def _on_panel_visibility(self, panel, prop):
        """F40: Panel woanders umgeschaltet – Knopf-Zustand nachziehen."""
        try:
            self.toggle_btn.set_active(panel.get_visible())
        except Exception:
            pass

    def _on_size_allocate(self, paned, alloc):
        if not self.pos_pending:
            return
        # F12 (0.13.0): Startbreite aus der Konfiguration (das Panel
        # liest sie im Konstruktor aus nemo-previewer.conf, inklusive
        # der per Ziehen gewählten Breite als künftige Startbreite);
        # ohne Konfiguration gilt der Default PANEL_WIDTH (300 px).
        width = getattr(self.panel, "_panel_width", None) or PANEL_WIDTH
        if alloc.width > width + 200:
            paned.set_position(alloc.width - width)
            self.pos_pending = False


def _uri_to_dir(uri):
    try:
        path, _ = GLib.filename_from_uri(uri)
        return path
    except Exception:
        try:
            parsed = urllib.parse.urlparse(uri)
            return urllib.parse.unquote(parsed.path)
        except Exception:
            return None


def _reconcile(st):
    """
    Panel an der rechten Kante des Nemo-Fensters verankern.
    Technik: Das direkte Kindelement der Fenster-Hauptbox, das die
    Dateiansicht enthält (der Nemo-'Pane'), wird in unser HPaned
    verpackt: [ Pane | Panel ]. Das Panel sitzt damit zuverlässig am
    rechten Rand und behält seine Position über Reiterwechsel hinweg.
    """
    window = st.window
    view = find_view(window)
    if view is None:
        return

    try:
        kids = window.get_children()
    except Exception:
        return
    top_box = kids[0] if kids else None
    if not isinstance(top_box, Gtk.Container):
        dbg("Injektion: unerwartete Fensterstruktur (%s)"
            % type_name(top_box))
        return

    # Injektionsziel: das Widget, das DIREKT unter der Hauptbox auf dem
    # Pfad von der Ansicht nach oben liegt. Wir folgen dazu schlicht den
    # Eltern-Zeigern – das ist deterministisch und unabhängig von
    # is_ancestor-Semantik-Spezialitäten.
    target = None
    node = view
    while node is not None:
        parent = node.get_parent()
        if parent is top_box:
            target = node
            break
        node = parent

    if target is None:
        chain = []
        node = view
        while node is not None:
            chain.append(type_name(node))
            node = node.get_parent()
        dbg("Injektion: Ansicht hängt nicht unter der Hauptbox – "
            "Kette nach oben: %s" % " < ".join(chain))
        return

    # Wichtig: Hängt die Ansicht bereits unter unserem HPaned, ist der
    # gefundene Ziel-Knoten unser EIGENES HPaned – dann ist bereits
    # alles injiziert und es darf NICHT nochmal passieren (sonst
    # verpacken wir das Paned in sich selbst und zerstören den Baum).
    if target is st.hpaned:
        st._view_ok(view)
        return

    # Bereits korrekt injiziert?
    if (st.hpaned.get_parent() is top_box
            and st.hpaned.get_child1() is target):
        st._view_ok(view)
        return

    # Neu injizieren: alten Zustand rückgängig machen
    _detach(st)

    try:
        if isinstance(top_box, Gtk.Box):
            pos = top_box.child_get_property(target, "position")
            top_box.remove(target)
            st.hpaned.pack1(target, True, False)
            st.hpaned.pack2(st.panel, False, False)
            top_box.pack_start(st.hpaned, True, True, 0)
            top_box.reorder_child(st.hpaned, pos)
        elif isinstance(top_box, Gtk.Grid):
            left = top_box.child_get_property(target, "left-attach")
            top = top_box.child_get_property(target, "top-attach")
            width = top_box.child_get_property(target, "width")
            height = top_box.child_get_property(target, "height")
            # Validieren, BEVOR wir etwas entfernen – sonst droht ein
            # irreparabel zerstörter Widget-Baum
            if (not all(isinstance(v, int) and v >= 0 for v in (left, top))
                    or not all(isinstance(v, int) and v >= 1
                               for v in (width, height))):
                dbg("Injektion: Grid-Eigenschaften nicht lesbar "
                    "(%r, %r, %r, %r) – Vorgang abgebrochen, "
                    "Nemo bleibt unangetastet" % (left, top, width, height))
                return
            top_box.remove(target)
            st.hpaned.pack1(target, True, False)
            st.hpaned.pack2(st.panel, False, False)
            top_box.attach(st.hpaned, left, top, width, height)
        else:
            dbg("Injektion: Hauptbox ist weder Box noch Grid (%s)"
                % type_name(top_box))
            return
        st.pos_pending = True
        st.hpaned.show()
        st.panel.show_all()
        # F12 (0.12.0): Konfiguration erst NACH dem show_all anwenden
        # – sonst würde eine verlangte Unsichtbarkeit beim Start
        # sofort wieder überschrieben. getattr-Schutz, damit nicht
        # passende Dateiversionen nie abstürzen können.
        _apply = getattr(st.panel, "apply_start_settings", None)
        if callable(_apply):
            _apply()
        dbg("Panel an Fensterrand injiziert (Ziel: %s)"
            % type_name(target))
    except Exception:
        traceback.print_exc()
        return

    st._view_ok(view)


def _detach(st):
    """Panel aus dem Widget-Baum lösen und Originalstruktur wiederherstellen."""
    parent = st.hpaned.get_parent()
    if parent is None:
        return
    try:
        child1 = st.hpaned.get_child1()
        if child1 is None:
            parent.remove(st.hpaned)
            return
        if isinstance(parent, Gtk.Box):
            pos = parent.child_get_property(st.hpaned, "position")
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.pack_start(child1, True, True, 0)
            parent.reorder_child(child1, pos)
        elif isinstance(parent, Gtk.Grid):
            left = parent.child_get_property(st.hpaned, "left-attach")
            top = parent.child_get_property(st.hpaned, "top-attach")
            width = parent.child_get_property(st.hpaned, "width")
            height = parent.child_get_property(st.hpaned, "height")
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.attach(child1, left, top, width, height)
        else:
            parent.remove(st.hpaned)
            st.hpaned.remove(child1)
            parent.add(child1)
    except Exception:
        traceback.print_exc()


def _connect_view_signals(st, view):
    """
    Auswahl-Signale dynamisch entdecken und verbinden. Statt einen
    festen Signalnamen zu raten, werden im Teilbaum der Ansicht und
    auf den AtkSelection-Objekten alle void-Signale mit 'select' im
    Namen verbunden – so ist es egal, ob Nemo Striche oder Unter-
    striche benutzt. Verbunden wird pro Widget; die Handler-IDs
    landen als (Objekt, ID)-Paare in st.view_handlers.
    """
    names_found = set()

    for w in walk(view):
        try:
            if not isinstance(w, Gtk.Widget) or not w.get_mapped():
                continue
        except Exception:
            continue
        for sig in selection_signals(w):
            try:
                hid = w.connect(
                    sig,
                    lambda *a, _w=w, _s=sig: (
                        diag("Signal %s empfangen (%s)" % (_s, type_name(_w))),
                        _dump_a11y_once(st),
                        _refresh_soon(st))[-1])
            except Exception:
                continue
            st.view_handlers.append((w, hid))
            names_found.add(sig)

    # Keine Signalhandler an ATK-Objekten registrieren. Diese Objekte sind
    # beim Ordnerwechsel häufig kurzlebig und führten zu disconnect-Warnungen.

    diag("Ansicht verbunden: %s – Auswahl-Signale: %s"
        % (type_name(view), ", ".join(sorted(names_found)) or "KEINE"))


def _dump_a11y_once(st):
    """
    Den a11y-Baum der Ansicht bis zu zweimal ausgeben: einmal nach dem
    Verbinden (Grundzustand) und einmal beim ersten Auswahl-Signal
    (Zustand nach dem Klick). Die Zeilen zeigen Tiefe, Kinderzahl,
    Rolle, Namen, AtkSelection-Zähler sowie SELECTED/FOCUSED – damit
    ist sichtbar, wo Nemo die Auswahl tatsächlich hergibt.
    Nur bei VERBOSE_DIAG – im Alltagsbetrieb still.
    """
    if not VERBOSE_DIAG:
        return
    if st._a11y_dumps >= 2 or st.view is None:
        return
    st._a11y_dumps += 1
    view = st.view
    tag = "a11y[%s]" % type_name(view)
    try:
        if not isinstance(view, Gtk.Widget) or not view.get_mapped():
            return
        root = view.get_accessible()
        if root is None:
            dbg("%s: kein Accessible verfügbar" % tag)
            return
    except Exception:
        dbg("%s: kein Accessible verfügbar" % tag)
        return
    budget = [45]

    def rec(acc, depth):
        if acc is None or depth > 10 or budget[0] <= 0:
            return
        n = -1
        try:
            n = acc.get_n_children()
        except Exception as exc:
            n = -1
            # Ursache des scheinbar leeren a11y-Baums einmalig ausgeben.
            if not getattr(_dump_a11y_once, "_n_children_err", None):
                _dump_a11y_once._n_children_err = repr(exc)
                dbg("%s: get_n_children() schlug fehl: %r – "
                    "weitere Kinder werden blind über ref_child() probiert"
                    % (tag, exc))
        try:
            role = acc.get_role()
            try:
                role = role.value_nick
            except Exception:
                role = str(role)
        except Exception:
            role = "?"
        try:
            name = acc.get_name() or ""
        except Exception:
            name = ""
        extra = []
        try:
            extra.append("AtkSel=%d" % acc.get_selection_count())
        except Exception:
            pass
        try:
            ss = acc.get_state_set()
            if ss is not None:
                if ss.contains_state(Atk.StateType.SELECTED):
                    extra.append("SELECTED")
                if ss.contains_state(Atk.StateType.FOCUSED):
                    extra.append("FOCUSED")
                if ss.contains_state(Atk.StateType.ACTIVE):
                    extra.append("ACTIVE")
        except Exception:
            pass
        budget[0] -= 1
        dbg("%s d%d kinder=%d rolle=%s name=%r %s"
            % (tag, depth, n, role, name, " ".join(extra)))
        for child in _atk_children(acc, max_children=60):
            rec(child, depth + 1)

    rec(root, 0)
    dbg("%s – Ende der Diagnose" % tag)


def _view_ok(self, view):
    """Signal-Anmeldung (self ist hier ein PanelState via Erweiterung unten)."""
    if self.view is not view:
        for obj, hid in self.view_handlers:
            try:
                if obj.handler_is_connected(hid):
                    obj.disconnect(hid)
            except Exception:
                # Objekt/Handler kann durch Nemo bereits abgebaut sein.
                pass
        self.view_handlers = []
        self.view = view
        self._a11y_dumps = 0
        try:
            _connect_view_signals(self, view)
        except Exception:
            traceback.print_exc()
        _dump_a11y_once(self)
        _refresh_soon(self)
        # F40: Knopf nachrüsten (falls die Toolbar beim ersten Versuch
        # noch nicht stand) – idempotent, kein Doppel-Packen.
        self._install_toolbar_toggle()


PanelState._view_ok = _view_ok


def _refresh(st):
    try:
        # Immer die LIVE-Ansicht suchen: st.view kann nach einem
        # Ordnerwechsel auf einen bereits abgebauten Slot zeigen.
        view = find_view(st.window)
        if view is None:
            return
        names, strategy = SelectionReader.read(view, st.dir_path)
        # Diagnose pro konkretem Ansichtstyp, nicht nur einmal pro Fenster:
        # Nemo kann beim Ansichtswechsel ListView gegen IconView austauschen.
        diag_key = "_selection_diag_" + type_name(view)
        if not getattr(st, diag_key, False):
            setattr(st, diag_key, True)
            diag("Auswahl-Diagnose: View=%s, Instanz.get_selection=%s, Instanz.peek_selection=%s, Nemo.view_get_selection=%s, Nemo.view_peek_selection=%s" % (
                type_name(view),
                callable(getattr(view, "get_selection", None)),
                callable(getattr(view, "peek_selection", None)),
                callable(getattr(Nemo, "view_get_selection", None)),
                callable(getattr(Nemo, "view_peek_selection", None))))
            _dump_widget_tree(view)
        if names is None:
            # Keine Strategie konnte lesen – gedrosselte Debug-Meldung
            now = GLib.get_monotonic_time()
            if now - st.none_dbg_at > 5000000:  # max. alle 5 Sekunden
                st.none_dbg_at = now
                dbg("Auswahl nicht lesbar (Ansicht: %s)" % type_name(view))
            return
        if names != st.last_sel:
            dbg("Auswahl geändert: %r (via %s)" % (names, strategy))
            st.last_sel = names
            st.panel.set_selection(names, st.dir_path)
    except Exception:
        traceback.print_exc()


def _refresh_soon(st):
    """Auswahl-Refresh in den Main-Loop einplanen (Signal-Kontext verlassen)."""
    GLib.idle_add(lambda: (_refresh(st), False)[1])


def _poll(st):
    """Timer: Reconciliation + Auswahl-Abgleich als Sicherheitsnetz."""
    try:
        _reconcile(st)
        _refresh(st)
    except Exception:
        traceback.print_exc()
    return True


def _on_window_destroyed(window, st):
    """
    Fenster wird abgebaut (0.9.1): den 500-ms-Poll-Timer abräumen –
    sonst liefe er als Zombie nach dem Fensterende ewig weiter.
    """
    try:
        if st.poll_id:
            GLib.source_remove(st.poll_id)
        st.poll_id = 0
    except Exception:
        pass
    return False


def _get_state(window):
    st = getattr(window, "_previewer_state", None)
    if st is None:
        st = PanelState(window)
        window._previewer_state = st
        # 0.9.1: Timer wieder abbauen, wenn das Fenster verschwindet.
        try:
            window.connect("destroy", _on_window_destroyed, st)
        except Exception:
            pass
        st.poll_id = GLib.timeout_add(POLL_MS, _poll, st)
        dbg("PanelState für Fenster angelegt")
    return st


def _on_crowbar_placed(crowbar, window, uri, tries):
    """
    Idle-Callback: crowbar ist jetzt im Baum → Panel injizieren.
    0.9.1: Der Ordnerpfad wird hier NICHT mehr aus dem (eventuell
    überholten) uri gesetzt – _get_widget schreibt st.dir_path bereits
    synchron beim Anfordern der Crowbar. Eine alte Crowbar, die erst
    NACH einer neueren platziert wird, konnte sonst den aktuellen
    Pfad mit einem ALTEN Pfad überschreiben.
    """
    st = _get_state(window)
    if crowbar.get_parent() is None:
        tries[0] += 1
        return tries[0] < 40  # noch nicht platziert → weiter zuwarten
    _reconcile(st)
    _refresh(st)
    return False


# ------- Provider-Klasse (dynamisch, damit NameAndDescProvider optional) ----

def _is_desktop_window(window):
    """Erkennt Desktop-Fenster, damit dort kein Vorschau-Panel landet."""
    name = type_name(window)
    # Cinnamon/Nemo-Versionen unterscheiden sich bei den konkreten Typnamen.
    if "desktop" in name.lower():
        return True
    # Zusätzliche Prüfung des Widget-Baums: Desktop-Icon-Ansichten dürfen
    # niemals als Anker für die Injektion dienen.
    try:
        for child in walk(window):
            if type_name(child) == "NemoDesktopIconView":
                return True
    except Exception:
        pass
    return False


def _get_widget(self, uri, window):
    """LocationWidgetProvider: liefert die unsichtbare 'Brechstange'."""
    window_type = type_name(window)
    dbg("get_widget aufgerufen für %s (Fenstertyp: %s)" % (uri, window_type))
    if _is_desktop_window(window):
        dbg("Desktop-Fenster erkannt – kein Vorschau-Panel")
        return None
    st = _get_state(window)
    new_dir = _uri_to_dir(uri)
    if new_dir != st.dir_path:
        st.last_sel = None
        st.panel.set_selection([], new_dir)
    st.dir_path = new_dir   # sofort: neuer Ordner ist bekannt
    crowbar = Gtk.Box()
    crowbar.set_size_request(-1, 0)
    crowbar.set_no_show_all(True)
    tries = [0]
    GLib.idle_add(_on_crowbar_placed, crowbar, window, uri, tries)
    return crowbar


def _get_name_and_desc(self):
    return ["previewer:::"
            "Angedockte Vorschau der ausgewählten Datei:::"]


_bases = [GObject.GObject, Nemo.LocationWidgetProvider]
if hasattr(Nemo, "NameAndDescProvider"):
    _bases.append(Nemo.NameAndDescProvider)

_provider_dict = {
    "get_widget": _get_widget,
    "get_name_and_desc": _get_name_and_desc,
}

Provider = type("NemoPreviewerProvider", tuple(_bases), _provider_dict)


# ------------------------- Gtk-Protokoll-Filter ------------------------------
# → REF ENT-FILTER-1

_GTK_FOREACH_MSG = "gtk_container_foreach: assertion 'GTK_IS_CONTAINER"


def _install_log_filter():
    def handler(domain, level, message, *user_data):
        if message and _GTK_FOREACH_MSG in message:
            return
        try:
            GLib.log_default_handler(domain, level, message)
        except Exception:
            pass
    try:
        GLib.log_set_handler("Gtk",
                             GLib.LogLevelFlags.LEVEL_CRITICAL, handler)
    except Exception:
        pass


_install_log_filter()

dbg("previewer (Einstieg) v%s bereit" % PREVIEWER_VERSION)