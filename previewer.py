#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Previewer
=========

STAND: Version 0.2.1 – aktuelle Fassung. Dies ist die EINSTIEGS-Datei der
vier zusammengehörigen Dateien (previewer.py, previewer_panel.py,
previewer_select.py, previewer_util.py) – alle vier müssen im gleichen
Ordner liegen und die gleiche Version tragen.
Projekt-Repository: https://github.com/NBoESFWbVaf/nemo-previewer
(Versionsverlauf: changelog.md im Repository).

Eine Nemo-Python-Extension namens "Previewer": dockt rechts im Nemofenster
ein Panel an und zeigt eine gerenderte Vorschau der aktuell selektierten
Datei.

Unterstützte Vorschauen
-----------------------
- Bilder (JPEG, PNG, WebP, GIF, TIFF, ... alles, was Gdk-Pixbuf kennt)
- Text/Quellcode (read-only, monospace)
- Markdown (.md): gerendert – Überschriften, Fett/Kursiv, Code, Listen
- E-Mail-Dateien (.eml): Kopfzeilen und Textkörper
- PDF (alle Seiten scrollbar untereinander; benötigt gir1.2-poppler)
- Office-Dokumente (ODT/ODS/ODP, DOCX/XLSX/PPTX): scharfe Seitenansicht
  über LibreOffice-Hintergrundkonvertierung nach PDF (Cache in
  ~/.cache/previewer); ohne LibreOffice die eingebettete Miniaturansicht
- Audio (Tags, Cover, Play/Pause mit Seek-Leiste; via GStreamer)
- Video (Erstframe als Standbild, Tags, Dauer)
- Ordner und alles andere: Icon + Dateiinformationen

Installation
------------
1) DIESE VIER DATEIEN zusammen in den Nemo-Extension-Ordner kopieren:
       ~/.local/share/nemo-python/extensions/
     previewer.py           (Einstieg – diese Datei)
     previewer_panel.py     (Panel & Renderer)
     previewer_select.py    (Auswahl-Erkennung)
     previewer_util.py      (Helfer & Konstanten)
   (Ordner ggf. anlegen: mkdir -p ~/.local/share/nemo-python/extensions)

2) Pakete, falls nicht vorhanden:
       sudo apt install nemo-python python3-gi \
            gir1.2-gst-plugins-base-1.0 gir1.2-poppler-0.18 python3-cairo \
            libreoffice-core    (nur für die scharfe Office-Vorschau)

3) Nemo neu starten:
       nemo -q && nemo

Bedienung
---------
- Panel ein-/ausblenden: Strg+Alt+P (oder den Knopf oben rechts im Panel)
- Trenner zwischen Dateiansicht und Panel ist verschiebbar (Gtk.Paned)
- Play/Pause & Seek bei Audio über die Bedienelemente im Panel
- PDF: alle Seiten untereinander, im Vorschau-Bereich scrollbar

Deinstallation: alle vier Dateien aus dem extensions-Ordner löschen,
Nemo neu starten. Optional den Cache leeren: rm -rf ~/.cache/previewer

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
die erste Seite scharf und live skalierbar. Während der Konvertierung
zeigt das Panel die eingebettete ZIP-Miniaturansicht mit Hinweis.

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
)
from previewer_select import (
    find_view, selection_signals, SelectionReader,
    _atk_children, _dump_widget_tree,
)
from previewer_panel import PreviewPanel

# PREVIEWER_VERSION muss in ALLEN vier Dateien identisch sein. Der Einstieg
# prüft die geladenen Module: Liegt im Extension-Ordner noch eine veraltete
# Fassung, erscheint im Terminal sofort eine klare Achtung-Meldung.
PREVIEWER_VERSION = "0.2.1"
import previewer_util
import previewer_select
import previewer_panel

for _mod in (previewer_util, previewer_select, previewer_panel):
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
        self.hpaned.connect("size-allocate", self._on_size_allocate)

    def _on_size_allocate(self, paned, alloc):
        if not self.pos_pending:
            return
        if alloc.width > PANEL_WIDTH + 200:
            paned.set_position(alloc.width - PANEL_WIDTH)
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


def _get_state(window):
    st = getattr(window, "_previewer_state", None)
    if st is None:
        st = PanelState(window)
        window._previewer_state = st
        st.poll_id = GLib.timeout_add(POLL_MS, _poll, st)
        dbg("PanelState für Fenster angelegt")
    return st


def _on_crowbar_placed(crowbar, window, uri, tries):
    """
    Idle-Callback: crowbar ist jetzt im Baum → Panel injizieren.
    Der Ordnerpfad wird erst übernommen, wenn die crowbar tatsächlich
    platziert ist – ein überholter Aufruf einer alten crowbar würde
    sonst den aktuellen Pfad mit einem ALTEN Pfad überschreiben.
    """
    st = _get_state(window)
    if crowbar.get_parent() is None:
        tries[0] += 1
        return tries[0] < 40  # noch nicht platziert → weiter zuwarten
    st.dir_path = _uri_to_dir(uri)
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
#
# Beim Ordnerwechsel baut Nemo den alten Slot ab. GTK druckt dabei
# teilweise die Meldung
#   gtk_container_foreach: assertion 'GTK_IS_CONTAINER (container)' failed
# für Widgets, die bereits halb zerstört sind – auch wenn fremder Code
# (wie diese Extension) den Baum nur liest. Genau DIESE eine Meldung
# wird unterdrückt; alle anderen Gtk-Meldungen bleiben sichtbar.

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