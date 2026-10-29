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
- **Anlass:** F12 (0.12.0/0.13.0): Defaults zuerst setzen, dann conf-Datei drüberlesen; angewendet bei jedem Start.

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

### MED-COVER-1 – Cover-Rundung und Schatten ohne Blur (F34)

- **Modul:** previewer\_render\_media.py
- **Ort:** `_cover_shadowed` (Helfer `_cover_round_path`), aufgerufen aus `_finish_audio`
- **Anlass:** Cairo hat keinen Blur-Filter. Der Schatten entsteht deshalb aus sechs gestapelten, nach außen wachsenden Kacheln à 5,5 % Deckkraft (Kern ≈ 30 %, weicher Saum). Der Radius folgt der Platzhalter-Kachel (56/640 der Kantenlänge), damit eingebettete Cover und Platzhalter deckungsgleich aussehen und beides mit der Live-Skalierung mitwächst.

```text
        # F34: Gleiche Rundung wie die Platzhalter-Kachel: 56/640 der
        # Kantenlänge (min(w, h), damit Hochformat nicht überdrehen),
        # skaliert mit, weil das gepaddete Pixbuf durch dieselbe
        # Live-Skalierung geht. Cairo kennt keinen Blur – der Schatten
        # entsteht aus sechs gestapelten, wachsenden Kacheln. Ohne
        # PangoCairo bleibt das Cover ungerahmt, die Vorschau läuft.
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
- **Anlass:** Das Seiten-Label zeigt die Seitenzahl inzwischen selbst; der Office-Rückruf ruft \_render\_pdf direkt und braucht deshalb eigenes show\_all.

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