# REFERENZ.md – Kommentar-Referenz der Nemo-Extension „Previewer“

**Zweck.** Seit dem Struktur-Release 0.15.0 (F28) stehen lange Kommentar-  
und Historienblöcke nicht mehr im Code. An ihrer Stelle trägt der Code genau  
einen Marker der Form `# → REF <MODUL>-<THEMA>-<NNN>`; der ausgelagerte Text  
liegt hier, zusammen mit Modul, Ort und Anlass. Der Code bleibt damit  
schlank und lesbar, die Projekthistorie geht nicht verloren.

**Konventionen.**

- Marker-Format: `# → REF <MODUL>-<THEMA>-<NNN>` – Modul-Kürzel, Themen-  
Kürzel (B/R/K/F-Nummer oder sprechender Name), fortlaufende Nummer je  
Thema, z. B. `# → REF PAN-R9-1`.
- Modul-Präfixe: `ENT` (previewer.py), `PAN` (previewer\_panel.py),  
`SEL` (previewer\_select.py), `UT` (previewer\_util.py),  
`TB` (previewer\_toolbar.py), `MED` (previewer\_render\_media.py),  
`DOC` (previewer\_render\_docs.py), `TXT` (previewer\_render\_text.py).
- Ausgelagert werden Kommentar-Runs ab 5 zusammenhängenden Zeilen. Was  
NICHT wandert: STAND-/Versions-Zeilen, PREVIEWER\_VERSION, Docstrings,  
einzeilige Abschnittstitel und kurze Inline-Hinweise.
- Einträge hier: ID, Modul, Ort (Funktion/Block), Anlass in einem Satz,  
Originaltext verbatim in einem Text-Block.
- Diese Datei ist ein LEBENDES Projektdokument: Sie wird laufend gepflegt  
und mit jedem Kommentar-Umbau erweitert. Sie wird bewusst NICHT mit-  
deployt – die Extension braucht sie nicht zur Laufzeit; das Deployment  
kopiert nur die \*.py-Dateien.

**Themen-Kürzel in diesem Dokument:** B (Bugfix), R (Robustheit),  
K (Kosmetik), F (Feature) plus sprechende Kürzel für Code-Themen ohne  
Ticket-Nummer (z. B. FILTER, VTABLE, HR).

---

## Einstieg (ENT)

### ENT-FILTER-1 – Gtk-Protokoll-Filter

- **Modul:** previewer.py
- **Ort:** Modul-Ebene, unter dem Abschnittstitel „Gtk-Protokoll-Filter“, über `_GTK_FOREACH_MSG` / `_install_log_filter()`
- **Anlass:** Gtk druckt beim Ordnerwechsel eine kritische Meldung für bereits halb zerstörte Widgets – genau diese eine Meldung wird gefiltert.

```text
#
# Beim Ordnerwechsel baut Nemo den alten Slot ab. GTK druckt dabei
# teilweise die Meldung
#   gtk_container_foreach: assertion 'GTK_IS_CONTAINER (container)' failed
# für Widgets, die bereits halb zerstört sind – auch wenn fremder Code
# (wie diese Extension) den Baum nur liest. Genau DIESE eine Meldung
# wird unterdrückt; alle anderen Gtk-Meldungen bleiben sichtbar.
```

### ENT-TOGGLE-1 – Vorschau-Umschalter in Nemos Werkzeugleiste (F40)

- **Modul:** previewer.py
- **Ort:** `PanelState._install_toolbar_toggle` (nachgerüstet in `_view_ok`), Rückkanäle `_on_toolbar_toggle`/`_on_panel_visibility`, Helfer `_pack_toggle`/`_find_first_widget`/`_pos_after_view_buttons`/`_has_view_icon`
- **Anlass:** Der Nutzer wollte den Ein-/aus-Schalter nicht mehr im Panel-Kopf, sondern in Nemos Werkzeugleiste neben der Ansichtenauswahl. Die erste Annahme, Nemos Toolbar sei eine GtkHeaderBar-Unterklasse, bewahrheitete sich auf klassischem Nemo (Cinnamon) nicht: get\_titlebar() liefert NULL, der Knopf erschien nie. Nemo bietet keine offizielle Erweiterungs-API für die Toolbar – aber NemoToolbar ist nur ein GtkBox, und die Ansichts-Knöpfe stecken in einer GtkToolbar aus dem UIManager. Deshalb zwei Installations-Routen: Route 1 bei CSD (Titelleiste ist GtkHeaderBar) – GtkToggleButton per pack\_end; pack\_end nimmt in GTK3 NUR das Kind-Argument, mehr Argumente werfen einen TypeError. Route 2 klassisch – \_find\_first\_widget durchsucht den Widget-Baum nach der ersten GtkToolbar, \_pos\_after\_view\_buttons setzt den GtkToggleToolButton direkt hinter den letzten Ansichts-Knopf (erkannt am view-…-Icon seiner Gtk.Image), ohne Fund hängt insert(-1) hinten an. Zwei Synchronisations-Fälle: der Knopf schaltet dasselbe Panel wie Strg+Alt+P (toggled → show/hide), und umgekehrt zieht notify::visible am Panel den Knopf nach (Show-at-Start-Einstellung, Tastenkürzel) – beide Richtungen konvergieren, da set\_active auf den gleichbleibenden Wert kein toggled mehr auslöst.

```text
        # PanelState entsteht genau einmal pro Fenster, aber die
        # Versöhnung (_reconcile) läuft mehrfach – der Knopf wird am
        # Fenster-Objekt gemerkt (Python-Attribut, nicht GObject-
        # set_data – PyGObject blockiert die Daten-Methoden) und nie
        # doppelt gepackt. Die Installation geschieht nachgereicht in
        # _view_ok, weil die Werkzeugleiste beim ersten PanelState-Bau
        # theoretisch noch nicht stehen muss.
        # Zwei Installations-Routen: GtkHeaderBar als Titelleiste
        # (CSD) bekommt einen GtkToggleButton per pack_end (nur das
        # Kind-Argument!); klassisches Nemo bekommt die GtkToolbar im
        # Widget-Baum markiert und einen GtkToggleToolButton direkt
        # hinter die Ansichts-Knöpfe.
        # Die Icon-Wahl läuft über pick_icon: Nicht jedes Mint-/Nemo-
        # Theme liefert jeden Namen – der erste vorhandene gewinnt,
        # der letzte Fallback (pan-end-symbolic) existiert immer in
        # GTK selbst. Ohne HeaderBar und GtkToolbar bleibt Strg+Alt+P
        # (dbg-Hinweis).
```

---

## Panel-Kern (PAN)

### PAN-B8-1 – KeyFile-Resolver (B8)

- **Modul:** previewer\_panel.py
- **Ort:** Modul-Ebene, vor dem try-Block um `_KEYFILE_CLS` / `_KEYFILE_FLAGS_NONE`
- **Anlass:** B8 (0.12.1): Gio.Keyfile existiert nicht – GKeyFile heißt in PyGObject GLib.KeyFile; defensiver Resolver mit dbg statt still.

```text
# B8 (0.12.1): GKeyFile wird von PyGObject als GLib.KeyFile gebunden
# (GLib, NICHT Gio – 0.12.0 griff auf Gio.Keyfile zu und scheiterte
# laut Testfeld mit „'gi.repository.Gio' object has no attribute
# 'Keyfile'“). Defensiv beide Namen auflösen (gleiche Begründung wie
# beim Discoverer in _media_probe_async); fehlt die Klasse ganz,
# dbggen Lade-/Speicherpfad und die Defaults bleiben stehen.
```

### PAN-R2-1 – Render-Generation (R2)

- **Modul:** previewer\_panel.py
- **Ort:** `__init__`, über `self._pdf_gen = 0`
- **Anlass:** Render-Generation zählt `_clear_content` hoch; Idle-Nachträge erkennen daran veraltete Vorschauen (ein `self._path`-Vergleich würde beim Office-Cache falsch greifen).

```text
        # R2: Render-Generation – _clear_content zählt sie hoch; die
        # Idle-Nachschub-Schritte erkennen daran, ob ihre Vorschau noch
        # aktuell ist. (Ein self._path-Vergleich würde FALSCH greifen:
        # Office rendert seine PDF aus dem Cache, während self._path
        # weiterhin das ODT/DOCX ist.)
```

### PAN-F12-1 – Konfig-Defaults im Konstruktor (F12)

- **Modul:** previewer\_panel.py
- **Ort:** `__init__`, über `self._conf_show_at_start = True`
- **Anlass:** F12 (0.12.0/0.13.0): Defaults zuerst setzen, dann conf-Datei drüberlesen; angewendet bei jedem Start. 0.27.0 (F12 Teil 3): dockt hier an – Schlüssel doc\_page\_limit (Begrenzung ja/nein) und doc\_max\_pages (1–999, Default 20 = bisheriges MAX\_PDF\_PAGES); der Merker \_last\_docview lässt Änderungen live auf die angezeigte Dokument-Vorschau wirken.

```text
        # F12 (0.12.0/0.13.0): Konfiguration der Vorschauspalte –
        # Werte aus ~/.config/nemo-previewer/nemo-previewer.conf,
        # angewendet bei jedem Start (siehe _config_load/
        # apply_start_settings). Defaults zuerst setzen, dann Datei
        # drüberlesen.
```

### PAN-F23-1 – Schnüffler-Aufruf im Dispatch (F23)

- **Modul:** previewer\_panel.py
- **Ort:** `_render_inner`, über `self._render_text(path)`
- **Anlass:** Endungslose Dateien sind meist Text; der Gio-MIME-Rater kennt nur bekannte Namen – der Schnüffler entscheidet über den Inhalt.

```text
            # F23: endungslose Dateien sind in der Regel Text (Notizen,
            # Dotfiles, Skripte ohne Suffix) – der MIME-Typ-Rater von Gio
            # errät nur bekannte Namen wie README/Makefile. Der Schnüffler
            # entscheidet über den Inhalt; Binärdateien ohne Endung
            # (Executables, Core-Dumps) fallen durch und bleiben generisch.
```

### PAN-BILD-1 – Mindesthöhe bei keep\_height

- **Modul:** previewer\_panel.py
- **Ort:** `_apply_scale`, über `if item["keeph"]:`
- **Anlass:** Mindesthöhe hält den Container auf Bildhöhe; die Scrollposition wird nach dem Aufziehen/Zurückschieben-Zyklus zurückgesetzt.

```text
                # Mindesthöhe nur bei keep_height: hält den Container auf
                # Bildhöhe, wenn er nicht expandiert gepackt ist (sonst
                # würde das Bild unten abgeschnitten). Zusätzlich die
                # Scrollposition zurücksetzen – nach einem Aufziehen-/
                # Zurückschieben-Zyklus stünde das Bild sonst versetzt.
```

### PAN-FOLDER-1 – Ordner-Vorschau als Inhalts-Liste (F43)

- **Modul:** previewer\_panel.py
- **Ort:** `_render_folder`
- **Anlass:** Nutzer-Wunsch: Statt eines Ordner-Icons zeigt die Vorschau den Inhalt in Listenform. os.scandir trennt Ordner und Dateien; angezeigt werden Ordner zuerst (fett, rechte Spalte „Ordner“), dann Dateien (rechte Spalte Größe via human\_size), je alphabetisch case-insensitiv. K1 bleibt: ALLE Einträge zählen, Versteckte weist der Kopf-Hinweis separat aus; seit 0.30.0 stehen sie nur dann gedimmt in der Liste, wenn Nemo sie anzeigt. Deckel: Nur die ersten 300 Zeilen werden als Widgets gebaut (Gtk.ListBox im ScrolledWindow), der Rest als dim-Fußzeile „… und N weitere“. Namen mit MIDDLE-Ellipsize plus Tooltip; Ordner-Namen via markup\_escape\_text fett gesetzt. Seit 0.29.0 (Nutzer-Wunsch): Vor jedem Namen sitzt ein Gtk.Image mit dem Eintrags-Icon – Ordner über inode/directory, Dateien über Gio.content\_type\_guess zum Namen und content\_type\_get\_icon, MENU-Größe, Fallback folder bzw. text-x-generic –, und die ListBox trägt den Innenabstand der Text-Vorschauen als Rand (10/10/8/8 px). Seit 0.30.0 (Nutzer-Wunsch): Die Icons sind symbolisch – Gio.content\_type\_get\_symbolic\_icon, Fallback folder-symbolic bzw. text-x-generic-symbolic – und folgen damit dem System-Theme (Darkmode hell, Lightmode dunkel); die Liste zeigt Versteckte nur, wenn Nemo sie anzeigt (org.nemo.preferences show-hidden-files, Strg+H).

```text
        # Gtk.ListBox ist nicht selbst scrollbar – ScrolledWindow.add
        # legt in GTK3 automatisch einen Viewport darunter. Selection
        # NONE: Die Liste ist eine Vorschau, kein Navigator – Klicks
        # bleiben bei Nemos Dateiansicht, nicht im Panel.
        # Die 300-Zeilen-Grenze ist ein reiner Widget-Deckel: Sortier-
        # reihenfolge und Zählung (K1) erfassen ALLE Einträge, nur
        # der Widget-Bau stoppt – dieselbe Disziplin wie der Bomben-
        # Deckel bei Bildern.
```

### PAN-VCARD-1 – Visitenkarten-Dispatch (F7)

- **Modul:** previewer\_panel.py
- **Ort:** Typ-Kette in `_render`, direkt nach dem `.eml`-Zweig
- **Anlass:** Nutzer-Wunsch: ALLE bekannten Visitenkartenformate werden als Visitenkarte gerendert, nicht als Textdatei – vCard (.vcf/.vcard, MIME text/vcard), LDIF (.ldif) und Windows-Contact (.contact); die Endungs-Prüfung fängt auch die Formate ab, die shared-mime-info nur als text/plain bzw. XML einstufen würde. Der Renderer \_render\_vcard lebt im Text-Modul; der Dispatch zweigt VOR dem generischen text/-Zweig ab, damit die MIME-Erkennung die Karte nicht als Klartext wegschluckt.

```text
        elif (lower.endswith((".vcf", ".vcard", ".ldif", ".contact"))
              or mime == "text/vcard"):
            # F7: Visitenkartenformate – vCard, LDIF, Windows-Contact
            # (Renderer im Text-Modul).
            # → REF PAN-VCARD-1
            self._render_vcard(path)
```

### PAN-F44-1 – Optionales GtkSource-Binding (F44)

- **Modul:** previewer\_panel.py
- **Ort:** Modulkopf, unterhalb der Mixin-Importe
- **Anlass:** 0.28.0 (Nutzer-Wunsch): Syntax-Hervorhebung in der Text-Vorschau. GtkSourceView wird wie Poppler im Docs-Modul als OPTIONALES Binding geladen; fehlt es (Paket gir1.2-gtksource-4), bleibt alles beim bisherigen TextView. \_source\_language rät die Sprache über den Dateinamen, \_source\_scheme wählt bei dunklem GTK-Theme oblivion (ersatzweise solarized-dark), sonst classic. 0.28.1 (Nutzer-Wunsch): über die Einstellung text\_syntax an/aus schaltbar (Rubrik „Textdateien“), Default an.

```text
# → REF PAN-F44-1
HAVE_GTKSOURCE = False
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAVE_GTKSOURCE = True
except Exception:
    pass
```

---

## Auswahl (SEL)

### SEL-VTABLE-1 – Klassen-VTable peek\_selection

- **Modul:** previewer\_select.py
- **Ort:** Modul-Ebene, unter dem Abschnittstitel „Native Auswahl über den Klassen-VTable von NemoView (peek\_selection)“
- **Anlass:** libnemo-private ist auf Mint 22 statisch – peek\_selection wird als Funktionszeiger aus dem NemoView-Klassen-VTable gelesen, Indizes aus nemo-view.h verifiziert.

```text
#
# Auf Linux Mint 22 ist libnemo-private eine STATISCHE Bibliothek – es gibt
# keine .so, deren Symbole man laden könnte (der dlopen-Versuch oben bleibt
# als Fallback für ältere Systeme). Nemos Auswahl ist trotzdem erreichbar:
# NemoView hält 'peek_selection' als Funktionszeiger im Klassen-VTable
# (nemo-view.h, NemoViewClass: Index 12 nach GtkScrolledWindowClass), und
# NemoFile implementiert das Interface NemoFileInfo, dessen VTable laut
# nemo-file-info.h 'get_name' (Index 1) und 'get_uri' (Index 2) enthält.
# Die Größe der Eltern-Klasse wird zur LAUFZEIT über GObject.type_query()
# vom tatsächlich gelinkten GTK erfragt – nichts wird geraten. Die Indizes
# sind aus den Mint-22- und Master-Zweigen von nemo-view.h verifiziert.
# ----------------------------------------------------------------------------
```

### SEL-GTYPE-1 – GType-IDs über libgobject

- **Modul:** previewer\_select.py
- **Ort:** `_native_vtable_api`, über den CDLL-Zugriff
- **Anlass:** PyGObject liefert bei type\_from\_name() ein GType-OBJEKT, das ctypes nicht akzeptiert – deshalb g\_type\_from\_name aus libgobject.

```text
        # GType-IDs DIREKT über libgobject holen: PyGObject liefert bei
        # type_from_name() neuerdings ein GType-OBJEKT, das ctypes nicht
        # als Argument akzeptiert ('cannot be interpreted as an integer'
        # – ArgumentError, der die ganze Route lautlos tötete). Der Weg
        # über g_type_from_name aus libgobject liefert garantiert die
        # rohe numerische ID aus derselben GLib-Laufzeit.
```

### SEL-WILDCALL-1 – Wildcall-Schutz (0.9.2)

- **Modul:** previewer\_select.py
- **Ort:** Modul-Ebene, unter dem Abschnittstitel „Wildcall-Schutz (0.9.2, Audit „Pufferüberlauf/OOM“)“, über `_NEMO_TEXT_RANGES`
- **Anlass:** VTable-Funktionszeiger dürfen nur innerhalb einer Nemo-Bibliothek liegen, bevor sie gerufen werden; sonst wird die Route fail-closed abgeschaltet.

```text
# Die ctypes-Routen lesen Funktionszeiger aus berechneten VTable-Offsets
# (peek_selection, get_name, get_uri) und rufen sie auf. Verschiebt ein
# Nemo-Update das Klassen-/Interface-Layout, könnte ein Slot auf einen
# falschen, aber nicht-NULL Zeiger zeigen – sein Aufruf wäre ein
# Wildcall und würde Nemo schlagartig beenden (try/except wirkt bei
# Speicherzugriffsverletzungen nicht). Jedes Call-Ziel muss deshalb
# innerhalb einer Nemo-Bibliothek liegen, bevor es gerufen wird;
# andernfalls wird die Route abgeschaltet (fail-closed – die anderen
# Auswahl-Strategien übernehmen).
```

---

## Toolbar (TB)

### TB-F19-1 – Statische ActionBar (F19)

- **Modul:** previewer\_toolbar.py
- **Ort:** `_build_toolbar`, unter dem Titel „F19: Toolbar am unteren Rand der Vorschauspalte (0.11.0)“
- **Anlass:** Statisch laut Nutzer-Entscheid – immer sichtbar, kein Ein-/Ausblenden je Renderer; Renderer-Aktionen melden sich später per pack\_start an.

```text
        # Statisch laut Nutzer-Entscheid: Sie ist IMMER zu sehen, solange
        # das Panel aktiv ist – kein Ein-/Ausblenden je Renderer. Die
        # Renderer-Aktionen (F13, F20, F21, F24–F27) melden sich später
        # per pack_start hier an; rechts außen sitzt bereits fest der
        # Einstellungs-Knopf (Zahnrad aus den Systemicons), an dem die
        # Konfiguration (F12) andocken wird.
```

### TB-CSS-1 – Innenabstand der Leiste

- **Modul:** previewer\_toolbar.py
- **Ort:** `_build_toolbar`, über dem CSS-try-Block
- **Anlass:** Nutzer-Wunsch (0.12.0): Leiste etwa 5 px schmaler; kann ein Theme die Regel nicht, bleibt es beim Standard.

```text
        # Nutzer-Wunsch (0.12.0): Leiste etwa 5 px schmaler – der
        # Innenabstand oben/unten liegt unter dem Themen-Standard
        # (Adwaita-Standard ist 6+6 px, hier 3+4 px). Kann ein Theme
        # die Regel nicht, bleibt es einfach beim Standard – kein
        # Fehler, kein Absturz.
```

### TB-F12-1 – SpinButton vorab befüllen (F12 Teil 2)

- **Modul:** previewer\_toolbar.py
- **Ort:** `_open_settings_window`, über der wrow-Box
- **Anlass:** Der SpinButton trägt den aktuellen Wert vorab; der Default wird daneben genannt, der Ist-Wert als „aktuell“ gekennzeichnet (Nutzer-Wunsch).

```text
        # Standardbreite beim Start: Der SpinButton trägt den
        # AKTUELLEN Wert vorab (gezogene Breite schlägt sich ja in
        # _panel_width nieder und liegt schon in der conf); der
        # Default wird daneben genannt, der Ist-Wert als „aktuell“
        # gekennzeichnet (Nutzer-Wunsch).
```

---

## Medien (MED)

### MED-B7-1 – Eigenes show\_all im Bild-Idle-Callback (B7)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_image_probe_done`, über `self._content.show_all()`
- **Anlass:** R1-Muster aus \_media\_probe\_done (0.10.4) – das fehlende show\_all war die eigentliche Feld-Ursache der B7-Regression.

```text
        # R1-Muster aus _media_probe_done (0.10.4): Erst hier gepackte
        # Widgets liegen NACH dem show_all() des Render-Durchlaufs –
        # sie brauchen ihr eigenes show_all, sonst bleibt die Vorschau
        # unsichtbar. Genau dieses fehlende show_all war die eigent-
        # liche Feld-Ursache der B7-Regression.
```

### MED-SEEK-1 – Slider-Bereich nachziehen

- **Modul:** previewer\_render\_media.py
- **Ort:** `_tick_player`, über `self._ensure_seek_range(dur)`
- **Anlass:** Der Slider muss die gesamte Abspiel-Dauer umfassen; bei anfangs unbekannter Dauer war der Bereich 0–1 und der Timer bewegte nichts.

```text
                    # Slider-Bereich muss die GESAMTE Länge umfassen. War
                    # die Dauer beim Anlegen noch unbekannt (z.B. wenn der
                    # Discoverer versagte), wurde der Slider mit dem
                    # Bereich 0–1 angelegt – der Timer konnte ihn dann
                    # nie sichtbar bewegen. Der Bereich wird deshalb hier
                    # aus der echten Abspiel-Dauer einmalig nachgezogen.
```

### MED-AUDTAG-1 – Titel-/CD-Nummern in UINT und String „n/m“ (F33)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_tag_number_pair`, aufgerufen aus `_media_probe_async`
- **Anlass:** Je Codec laufen Nummern-Tags unterschiedlich auf: ID3 (MP3) und MP4 zerlegen TRCK/TPOS bzw. trkn/disk in getrennte UINTs (track-number/track-count, album-volume-number/-count); Vorbis-Kommentare (FLAC, Ogg) tragen „3/12“ gern als EINEN String, teils ganz ohne eigenen Gesamtzahl-Tag.

```text
        # F33: Zahlen-Paar aus der Tag-Liste – UINTs sind der Normalfall
        # (GStreamers ID3-/MP4-Mapper liefern Nummer und Gesamtzahl
        # getrennt), aber Vorbis-Fassungen melden die Zahl als String
        # „n/m“, teils ohne eigenen Gesamtzahl-Tag: partition("/") holt
        # dann beides aus einem Wert. Jede Lesart einzeln gekapselt –
        # ein Ausreißer-Tag versteckt nur seine Zeile, nie das Cover.
```

### MED-AUDTAG-2 – Veröffentlichungs-Jahr über drei Datums-Formen (F33)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_tag_year`, aufgerufen aus `_media_probe_async`
- **Anlass:** Originalveröffentlichung vor Datums-Jahr (Nutzer-Wunsch): original-date hat Vorrang, sonst datetime bzw. date als Jahr. Der Wert-Typ hängt am Codec – Gst.DateTime, GDate oder String –, deshalb je Kandidat drei Lesarten in eigener Kapselung.

```text
        # F33: Jahr – Kandidaten sind original-date (Originalver-
        # öffentlichung), dann datetime (z. B. ID3v2.4 TDRC, Gst.DateTime)
        # und date (älterer GDate-Tag, z. B. ID3v2.3 TYER). Jeder Codec
        # meldet einen anderen Typ, je Kandidat werden deshalb alle drei
        # Lesarten probiert: DateTime.get_year(), GDate.get_year() und
        # der String-Anfang („2020-…“). Das erste echte Jahr gewinnt.
```

### MED-COVER-1 – Cover-Rundung und Schatten ohne Blur (F34, F35)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_cover_shadowed` (Helfer `_cover_round_path`), aufgerufen aus `_finish_audio`
- **Anlass:** Cairo hat keinen Blur-Filter. Der Schatten entsteht deshalb aus sechs gestapelten, nach außen wachsenden Kacheln à 4 % Deckkraft (F35: nach rechts und unten versetzt, dort 3 px mehr Raum – Kern ≈ 22 %, weicher Saum). Der Radius folgt der Platzhalter-Kachel (0.25.1, Nutzer-Wunsch: 56/960 der Kantenlänge – um ein Drittel dezenter als F34s 56/640), damit eingebettete Cover und Platzhalter deckungsgleich aussehen und beides mit der Live-Skalierung mitwächst.

```text
        # F34/F35: Gleiche Rundung wie die Platzhalter-Kachel: 56/960
        # der Kantenlänge (min(w, h), damit Hochformat nicht über-
        # dreht), skaliert mit, weil das gepaddete Pixbuf durch
        # dieselbe Live-Skalierung geht. Cairo kennt keinen Blur – der
        # Schatten entsteht aus sechs gestapelten, wachsenden Kacheln
        # (F35: nach rechts und unten versetzt, dort 3 px mehr Fläche,
        # insgesamt transparenter). Ohne PangoCairo bleibt das Cover
        # ungerahmt, die Vorschau läuft.
```

### MED-EXIF-1 – TIFF-IFD-Laufwerk mit Bomben-Deckel (F36)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_exif_read_ifd`, aufgerufen aus `_exif_parse`
- **Anlass:** EXIF ist ein TIFF-IFD-Geflecht: Werte stehen inline (bis 4 Bytes) oder hinter einem Offset, und die Spezial-Zeiger ExifIFD (0x8769) und GPSIFD (0x8825) hängen weitere IFDs an. Präparierte Dateien könnten mit Riesen-Eintragszahlen oder Zeigern ins Leere den Parser schikanieren – deshalb Eintrags-Deckel (512), Offset-Validierung gegen die Dateilänge und Rekursions-Tiefe 2 (B7, gleiche Disziplin wie der Dekodier-Deckel 0.9.2).

```text
        # Jeder IFD-Eintrag ist 12 Bytes: Tag, Typ, Anzahl, Wert oder
        # Offset. Alles defensiv: Eintragszahl gedeckelt, Offsets
        # gegen die Dateilänge geprüft, Zeiger-IFDs (ExifIFD/GPSIFD)
        # nur zwei Ebenen tief – ein kaputtes Tag darf nie den Parser
        # in die Knie zwingen, das Bild wird ja trotzdem gezeigt.
```

### MED-EXIF-2 – EXIF mit Bordmitteln und Hersteller-Fallbacks (F36)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_exif_parse`, aufgerufen im Worker von `_render_image`
- **Anlass:** Die gewünschten Felder sind Standard-EXIF, aber Hersteller füllen sie unterschiedlich: Belichtungszeit/Blende teils nur als APEX-Wert (ShutterSpeedValue/ApertureValue), das echte Datum teils nur als DateTimeDigitized statt DateTimeOriginal, das Kameramodell mit Hersteller-Dopplung („Canon Canon EOS …“), der Aufnahmeort als GPS-Gradminuten, teils auch Padding zwischen Exif-Marker und TIFF-Kopf (Samsung/Olympus). Der Parser liest JPEG-APP1- und TIFF-Köpfe mit Python-Bordmitteln (keine neue Pflicht-Abhängigkeit, passend zum Optional-Modul-Muster des Projekts) und formatiert jeden Wert erst nach seinen Fallbacks – fehlt alles, bleibt die Zeile weg („sofern vorhanden“).

```text
        # Reihenfolge bewusst: Der Direktwert gewinnt, der APEX-Wert
        # ist der herstellerspezifische Zweitweg (t = 2^-av,
        # N = 2^(av/2)), das Datum läuft als Kaskade Original →
        # Digitalisiert → Datei-Datum. GPS wird aus Grad/Minuten/
        # Sekunden in Dezimalgrade umgerechnet, die Referenz-Buch-
        # staben (N/S, E/W) liefert das jeweilige GPS-Tag. Ohne EXIF
        # (SVG, PNG ohne eXIf) bleibt die Tabelle bei Höhe/Breite.
```

### MED-EXIF-3 – EXIF-Kandidaten-Schleife für HEIC/HEIF und RAW (F41/F42)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_exif_bases` (mit `_exif_valid`), Kandidaten-Schleife in `_exif_parse` → `_exif_parse_at`, RAW-Fallback in `_image_probe_done` mit `_exif_rows`
- **Anlass:** Nutzer-Meldung: HEIC-Bilder zeigten keine Foto-Informationen – auch nach der ersten Korrektur (F41) nicht. F41s Ursachen-Analyse war unvollständig: Die alte Einzelsuche ließ den frühesten „Exif“-Treffer allein entscheiden, ob und wo gesucht wurde – und in der HEIC-Meta-Box steht der Item-Typ „Exif“ wörtlich, ein falscher Treffer brach die Suche vorzeitig ab. Dazu waren die Suchfenster (256 KB für den Marker, 4 MB für den TIFF-Kopf) zu klein: HEIC-Exif-Items liegen teils mitten oder am Ende der Datei. F42 löst das strukturell: \_exif\_bases sammelt Kandidaten im GANZEN Puffer (64-MB-Lesedeckel) aus drei Quellen – „Exif“-Marker (APP1-artige Vorspanne, auch in RAWs mit eingebettetem JPEG wie RAF/RW2), direkte TIFF-Köpfe II\*/MM\* (Plain-TIFF und TIFF-basierte RAWs wie NEF, CR2, ARW, DNG, PEF tragen ihn ab Byte 0) und Olympus-ORF-Köpfe IIRO/IIRS (TIFF-artig, aber ohne die 42-Magie – der IFD0-Pointer liegt trotzdem bei Offset 4). Jeder Kandidat wird von \_exif\_valid strukturell geprüft (Magie optional, IFD0-Offset ≥ 8, Eintragszahl 1–4096, erster IFD komplett im Puffer), Duplikate aussortiert; \_exif\_parse probiert die Kandidaten der Reihe nach, bis einer EXIF hergibt (JPEG bevorzugt über den Marker-Treffer, der vorn steht). Falsche Treffer fallen also nicht mehr auf die ganze Suche durch. Der RAW-Fallback zeigt die Foto-Tabelle (Maße aus A002/A003) unter der Icon-Ansicht, wenn Gdk-Pixbuf nicht dekodieren kann; die Bild-Ansicht teilt sich die Zeilen-Logik mit \_exif\_rows.

```text
        # Die Struktur-Validierung ist der Rettungsanker gegen Zu-
        # fallstreffer in Bild- oder Box-Daten: Ein II*/MM*-Muster
        # allein ist in komprimierten Bytes kein Wunder – aber zu-
        # sätzlich einen plausiblen IFD0-Offset UND eine Eintrags-
        # zahl zwischen 1 und 4096 UND einen kompletten ersten IFD
        # im Puffer zu fälschen, ist praktisch ausgeschlossen. Und
        # selbst ein struktur-gültiger Fehltreffer bleibt harmlos:
        # Er liefert kein EXIF, der nächste Kandidat gewinnt.
        # Quellcode-Note: bytes([0]) statt Null-Byte-Literale –
        # Escape-Fallen beim Übertragen in Canvases/Edits.
```

### MED-XMP-1 – XMP: Location und benutzerdefinierte Felder (F38)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_xmp_parse`/`_xmp_clean` mit Namensraum-Filter `_XMP_STD`, aufgerufen im Worker von `_render_image`
- **Anlass:** Die textliche „Location“ steht nicht im EXIF-, sondern im XMP-Teil des JPEG (IPTC Core, `Iptc4xmpCore:Location` – digikam/Lightroom füllen sie im Ort-Dialog), und vom Benutzer definierte Felder leben in eigenen XMP-Namensräumen. Adobe-Tools schreiben einfache Werte gern als Attribut der rdf:Description statt als eigenes Element, deshalb prüft der Parser beide Formen. Alles außerhalb der Standard-Namensräume (\_XMP\_STD) gilt als benutzerdefiniert und wird als „Präfix:Name“-Zeile übernommen – Werte werden von XML-Resten befreit, Entities dekodiert, auf 120 Zeichen gekürzt; maximal zehn Zusatzzeilen, damit Experimentier-Metadaten die Tabelle nicht fluten.

```text
        # XMP lebt im JPEG-APP1-Segment hinter der Adobe-URI; der
        # RDF-Block reicht von <x:xmpmeta> bis </x:xmpmeta>. Regex
        # statt XML-Parser: Bordmittel wie beim EXIF-Pfad, keine
        # neue Pflicht-Abhängigkeit. Element-Form UND Attribut-Form
        # prüfen – Adobe-Tools schreiben einfache Werte als Attribut
        # der rdf:Description, eigene Elemente nur bei verschachtel-
        # ten Werten (rdf:Bag/Seq). Falle bei der Element-Form: Ein
        # verschachtelter Gesamt-Match (Öffnung bis passendes
        # Schluss-Tag) lässt <x:xmpmeta> als ERSTEN Treffer bis zum
        # letzten </x:xmpmeta> aufzehren – die eigentlichen Felder
        # kämen nie dran. Deshalb werden nur Öffnungs-Tags gescannt
        # und je Feld das passende Schluss-Tag gezielt gesucht;
        # Standard-Wrapper (x, rdf) überspringt der Namensraum-
        # Filter, gescannt wird trotzdem weiter.
```

### MED-SPLIT-1 – Spalten-Aufteilung 60/40 mit Live-Nachzug (F38)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_pack_image_capped` mit Helfer `_image_split_sync`, genutzt von `_render_image` und `_render_svg`
- **Anlass:** Gtk.Box kennt keine Prozent-Aufteilung – expand ist ein Schalter, kein Verhältnis. Der Bildbereich trägt deshalb 60 % der Spaltenhöhe als Größenanforderung; ein size-allocate-Nachzug hält die Aufteilung beim Fenster-Resize aktuell. Mittig-Position macht halign/valign CENTER am Gtk.Image (NICHT am ScrolledWindow – der Streifen-Bug im 0.22.0-Test), der Info-Bereich expandiert und füllt den Rest (≈ 40 %).

```text
        # Gtk.Box teilt extra Raum nur gleichmäßig unter expandierenden
        # Kindern – 60/40 gibt es nicht als Schalter. Der Bildbereich
        # trägt deshalb 60 % der Spaltenhöhe als Request und zieht den
        # in size-allocate nach (nur bei relevanter Änderung, sonst
        # reißt der Anforderungs-Loop das Layout in Endlos-Schleifen).
        # Mittig-Zentrierung macht DAS BILD, nicht der ScrolledWindow:
        # Ein scrollbares Widget darf seine natürliche Breite auf ~0
        # senken – align=CENTER nimmt genau diese natürliche Größe,
        # der auf Spaltenbreite skalierte Scroll wäre also nur ein
        # schmaler Streifen, in dem das Bild geclippt wird. Das
        # Gtk.Image sitzt via Viewport im Scroll; sein halign/valign
        # CENTER zentriert es in beiden Richtungen im 60-%-Bereich.
        # Der Bereich selbst braucht expand=False gegen die Höhe –
        # expand/fill wirken in der vertikalen Box nur auf die HÖHE,
        # die Breite quer gibt die Box Kindern ohnehin voll.
```

### MED-SVG-DPI-1 – SVG DPI-Rendern über die Cairo-Route (K3)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_rsvg_cairo_pb`, genutzt von `_render_svg` (Fallback: `get_pixbuf`)
- **Anlass:** get\_pixbuf() rendert strikt in der intrinsischen Größe – ein 24×24-Icon-SVG bleibt ein Mini-Punkt in der Spalte, und seit librsvg 2.52 gilt der Aufruf ohnehin als deprecated. render\_document nimmt dagegen ein Rsvg.Rectangle als Zielfläche: dieselbe Vektor-Geometrie, beliebiger DPI-Maßstab. Scheitert die Route (kein pycairo, altes librsvg ohne render\_document, keine intrinsische Größe), greift der bisherige Pfad – die Vorschau ist also nie schlechter als vorher; das Maße-Label zeigt in beiden Fällen die intrinsische Größe.

```text
        # Die intrinsische Größe (get_intrinsic_size_in_pixels) ist die
        # Rechengrundlage: Die Panelbreite ist das Render-Ziel, kleine
        # SVGs wachsen scharf mit (Vektor statt Raster-Upcast, kein
        # Blur), die Deckelhöhe begrenzt die Zielfläche nach oben. Die
        # gerenderte Pixbuf wandert wie bisher durch _scaled_image in
        # die 60/40-Aufteilung – die Live-Skalierung bei Fenster-Resize
        # greift dann allerdings auf die Raster-Pixbuf zurück.
```

---

## Dokumente (DOC)

### DOC-BUDGET-1 – PDF-Pixel-Budget (0.9.2)

- **Modul:** previewer\_render\_docs.py
- **Ort:** `_pdf_page_pixbuf`, über der Budget-Abfrage `if w * h > _PDF_PIXEL_BUDGET:`
- **Anlass:** Riesige PDF-Seiten würden sonst ≈ 1,6 GB je Seite erzwingen; das Ergebnis wird flächentreu zurückgerechnet, normale Seiten bleiben unberührt.

```text
        # 0.9.2: Pixel-Budget – die untere Scale-Klammer (0.2) erzwingt
        # bei pathologisch riesigen PDF-Seiten (z.B. 100000 pt) sonst
        # 20000×20000 px ≈ 1,6 GB je Seite. Übersteigt das Ergebnis das
        # Budget, wird es flächentreu zurückgerechnet; normale Seiten
        # (auch doppelt so breite Panel) bleiben unberührt.
```

### DOC-F14-1 – Seiten-Label statt Scroll-Hinweis (F14)

- **Modul:** previewer\_render\_docs.py
- **Ort:** `_render_pdf`, über `self._content.show_all()`
- **Anlass:** Das Seiten-Label zeigt die Seitenzahl inzwischen selbst; der Office-Rückruf ruft \_render\_pdf direkt und braucht deshalb eigenes show\_all. 0.27.0 (Nutzer-Wunsch): Das Label steht jetzt über JEDEM Dokument – auch einseitige zeigen „Seite 1 von 1“ – und zählt einheitlich im Format „Seite X von Y“; der Deckel selbst ist einstellbar (F12 Teil 3).

```text
        # F14: Das Seiten-Label zeigt die Seitenzahl inzwischen selbst –
        # der frühere Hinweis „N Seiten – Vorschau nach unten
        # scrollen.“ ist damit entfallen.
        # Der Office-Rückruf ruft _render_pdf DIREKT (ohne den show_all-
        # Nachlauf von _render) – deshalb hier selbst sorgen.
```

### DOC-UPSCALE-1 – Miniatur mit Panelbreite skalieren

- **Modul:** previewer\_render\_docs.py
- **Ort:** `_render_office_thumb`, über `self._scaled_image(...)`
- **Anlass:** Office-Miniaturen (oft nur 256 px) wachsen mit der Panelbreite mit, statt klein in der Ecke zu kleben.

```text
                    # Upscale: Office-Miniaturansichten sind oft nur
                    # 256 px breit – sie wachsen mit der Panelbreite mit,
                    # statt klein in der Ecke zu kleben.
                    # Office-Miniaturansichten NATIV und scharf zeigen:
                    # Die eingebettete Miniatur hat nur ~256 px – jede
                    # Vergrößerung macht sie unleserlich schwammig.
```

### DOC-B4-1 – Gescheiterte Konvertierung cachen (B4)

- **Modul:** previewer\_render\_docs.py
- **Ort:** `_office_job_done`, über `self._office_failed.add(path)`
- **Anlass:** Ohne Cache würde jede Auswahl erneut konvertieren (Endlosschleife); die fertige PDF wird direkt aus dem Temp-Ordner gerendert.

```text
                    # B4: Ohne Cache würde JEDE Auswahl erneut konvertieren
                    # (Endlosschleife, gleiche Symptomatik wie der alte
                    # EXDEV-Bug). Deshalb: als gescheitert vermerken, aber
                    # die fertige PDF nicht wegwerfen – die scharfe Ansicht
                    # wird direkt aus dem Temp-Ordner gerendert (Poppler
                    # liest die Seiten sofort, danach ist die Datei egal).
```

### DOC-LEGACY-1 – Office-Formate ohne ZIP-Anteil (F39)

- **Modul:** previewer\_render\_docs.py
- **Ort:** `_render_office_thumb`, Absicherung über `_OFFICE_NOZIP_EXTS`
- **Anlass:** Die Übergangs-Ansicht liest aus Office-Dateien die eingebettete Miniaturansicht und den Textauszug – beides steckt nur in ZIP-Archiven (ODF/OOXML). Die alten binären Formate (.doc/.xls/.ppt) und RTF sind keine ZIP-Archive: zipfile scheitert, und ohne den eigenen Zweig stünde die irreführende Fehlermeldung „Office-Dokument konnte nicht geöffnet werden“ in der Vorschau. Der Zweig unterscheidet drei Fälle: Konvertierung läuft (Hinweis wartet auf das scharfe PDF), Konvertierung gescheitert (kaputte Datei, per \_office\_failed nicht endlos erneut) und LibreOffice/Poppler fehlen (Installations-Hinweis).

```text
        # Die scharfe Route ist für alle Office-Formate gleich (LibreOffice
        # --convert-to pdf frisst auch die binären Formate und RTF), nur der
        # Übergang bis dahin ist bei ihnen LEER: kein ZIP, keine Miniatur-
        # ansicht, kein Textauszug. Deshalb endet der No-ZIP-Zweig im
        # Hinweis statt im Fehler – und ohne LibreOffice/Poppler im
        # Installations-Tipp statt in der Diagnose einer kaputten Datei.
```

---

## Text (TXT)

### TXT-HR-1 – „+“-Verkettung in \_md\_hr

- **Modul:** previewer\_render\_text.py
- **Ort:** `_md_hr`, über dem return
- **Anlass:** Implizite String-Verkettung mit \* ist eine Rangfolge-Falle; YAML-Front-Matter blieb sonst ohne Vorschau.

```text
    # Wichtig: "+" statt impliziter String-Verkettung –
    # "a" "b" * 12 ergibt sonst ("ab") * 12 (Rangfolge-Falle):
    # 12 ungeöffnete <span>-Tags machten das Markup komplett
    # ungültig, und jede Datei mit einer ----Linie (YAML-
    # Front-Matter!) blieb ohne Vorschau.
```

### TXT-EPUB-1 – container.xml unter R4-Deckel

- **Modul:** previewer\_render\_text.py
- **Ort:** `_epub_data`, über `opf_path`
- **Anlass:** Auch kleine OPF-Einträge über den Lese-Deckel – ein präpariertes EPUB könnte sie als Dekompressionsbombe packen (0.9.2).

```text
        # OPF-Inhaltsdatei: steht in META-INF/container.xml.
        # 0.9.2: auch diese kleinen Einträge über den R4-Lese-Deckel –
        # ein präpariertes EPUB könnte sie als Dekompressionsbombe
        # packen (Kapitel und Cover waren längst gedeckelt, diese
        # beiden Lesevorgänge nicht).
```

### TXT-MOBI-1 – MOBI-Randbereinigung (R7)

- **Modul:** previewer\_render\_text.py
- **Ort:** `_mobi_data`, über `_mobi_edge`
- **Anlass:** MOBI-Datensätze tragen Schmutzbytes am Rand; eine vollständige Trailer-Dekodierung wäre ohne Referenzmaterial riskant.

```text
    # R7: MOBI-Datensätze können am Rand Schmutzbytes tragen – halb
    # zerrissene Mehrbyte-Sequenzen und Reste von Trailing Entries
    # (Index-/Steuerdaten am Datensatz-Ende), die der Dekompressor als
    # Zeichensalat interpretiert. Eine vollständige Rückwärts-Dekodierung
    # der Trailer-Größe wäre ohne Referenzmaterial riskant (ein Fehler
    # würde ALLE Bücher beschädigen); die sichere Randbereinigung je
    # Datensatz entfernt den sichtbaren Großteil des Mülls.
```

### TXT-FONT-1 – Font-Kopie-Register (R5)

- **Modul:** previewer\_render\_text.py
- **Ort:** `_fc_add_font_file`, über `state["copies"].append(dest)`
- **Anlass:** Fontconfig hat die Schriften im Speicher – das Register hält nur den Temp-Ordner klein.

```text
            # R5: Kopie registrieren und älteste entfernen, wenn der
            # Deckel erreicht ist. Fontconfig hat die Schriften beim
            # FcConfigAppFontAddDir bereits in den Speicher geladen –
            # bereits gesehene Wasserfälle bleiben also korrekt
            # dargestellt, nur die Festplatte/der Temp-Ordner atmet auf.
```

### TXT-B6-1 – System-Schriftgröße für Markdown (B6)

- **Modul:** previewer\_render\_text.py
- **Ort:** `_render_markdown`, über dem `_text_view`-Aufruf
- **Anlass:** Ohne Font-Override nutzt der TextView die System-Schrift; Markup nur nach Validierung, sonst Rohtext.

```text
        # B6 (0.10.1): OHNE Font-Override – der TextView nutzt die
        # System-Schrift des GTK-Themes und damit die Schriftgröße des
        # Systems. Die bisher hartcodierte "9" (Standardschrift in
        # 9 pt) war auf dem System sichtbar kleiner als die Text-
        # Vorschau (Monospace), die der Nutzer als Maßstab kennt.
        # Überschriften skalieren mit: ihre size='large'/'x-large'-
        # Angaben sind relativ zur Basis-Schrift.
        # Markup nur übernehmen, wenn es validiert wurde – sonst Rohtext.
```

### TXT-VCARD-1 – Visitenkarten-Renderer (F7)

- **Modul:** previewer\_render\_text.py
- **Ort:** `_render_vcard`, \_vcard\_card\_widget und \_vcard\_card\_draw samt Parse-Helfern (\_vcard\_unfold bis \_vcard\_placeholder, \_vcard\_circle, \_ldif\_parse, \_contact\_parse)
- **Anlass:** Nutzer-Wunsch: ALLE bekannten Visitenkartenformate als Karte rendern – Kontakt-Foto kreisförmig, sonst ein kreisförmiger Platzhalter. Drei Parser liefern dieselbe Karten-Tupel-Struktur: vCard (RFC-6350-Folding, 2.1-Quoted-Printable, Nackt-Parameter, Gruppenpräfix), LDIF (RFC 2849, Base64-Werte, jpegPhoto bleibt rohes Base64 für die Foto-Dekodierung) und Windows-Contact (.contact-XML, namensraum-agnostisch über lokale Element-Namen). 0.26.0 (Nutzer-Hinweis): KEIN Karten-Deckel – alle Kontakte der Datei erscheinen untereinander scrollbar, bei einem einzelnen Kontakt zeigt sich kein Scrollbalken. Feinschliff 0.25.0: Jede Karte trägt einen rechteckigen Rahmen mit dem Eckenradius der Musikcover samt gleichem Schlagschatten (F34/F35) – gezeichnet im draw-Signal HINTER die Widgets (Rundungspfad via \_cover\_round\_path aus dem Media-Modul). Dezenz 0.25.1: KEINE Füllung – die Karte bleibt transparent (weißer Grund schmerzt im Darkmode), Schatten und Haarlinien-Rand bleiben; Eckenradius um ein Drittel dezenter (56/960 statt 56/640 der kleineren Kante). Fotos nur inline Base64 oder lokale URI – Netz-URIs bleiben unbefragt, es greift der Platzhalter. Ohne pycairo bleibt das Foto eckig und der Platzhalter ein Theme-Icon; der Karten-Rahmen läuft ohne, der draw-Callback bekommt seinen Cairo-Kontext von GTK.

```text
        # Lese-Deckel: Kontakt-Fotos liegen als Base64 IN der
        # Datei – ein paar MB sind üblich, ein paar Dutzend
        # wären eine Bombe für Nemo.
```

```text
        # Rahmen und Schatten brauchen KEIN pycairo – der draw-
        # Callback bekommt seinen Cairo-Kontext von GTK geliefert.
```