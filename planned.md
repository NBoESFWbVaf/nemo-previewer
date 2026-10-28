# Nemo Previewer – Planung ([planned.md](http://planned.md))

Arbeitsdatei zur systematischen Ablage. Stand der Analyse: **Version 0.4.1**,  
2026-10-27. Abgearbeitetes wird abgehakt; erledigte Punkte wandern mit der  
zugehörigen Version in die `changelog.md`.

Legende: 🔴 echter Bug · 🟡 Risiko (situationsabhängig) · ⚪ Kosmetik ·  
Aufwand **S** = klein, **M** = mittel, **L** = groß

---

## Teil 1: Schwachstellen abarbeiten

### 🔴 Echte Bugs (zunächst als Patch-Paket 0.4.2 vorgesehen)

- [x] **B1 – Font-Basename-Kollision** (`_fc_add_font_file`, panel)

  Zwei Schriften mit gleichem Dateinamen aus verschiedenen Ordnern → das  
  zweite `os.path.exists(dest)` verhindert das Kopieren, Fontconfig sieht  
  die zweite Schrift nie (Wasserfall zeigt die erste).  
  *Skizze:* Zielname um Hash des Quellpfads ergänzen  
  (`<name>-<sha1(path)[:8]>.ttf`), Existenzprüfung entfällt.
- [x] **B2 – Audio: kein Bus-Watch** (`_render_audio`, panel)

  Nach Trackende (EOS) bleibt das Pause-Icon stehen, die Position friert  
  ein; Fehler des playbin bleiben unsichtbar.  
  *Skizze:* `playbin.get_bus().add_signal_watch()` + `message::eos` /  
  `message::error` Handler: zurückspulen, Icon auf Play, Hint bei Fehler.
- [x] **B3 – Tick-Timer läuft ewig** (`_tick_player`, panel)

  Der 400-ms-Timer wird nie abgeräumt; nach Fensterabbau läuft er gegen  
  zerstörte Widgets. playbin wird bei Auswahlwechsel nur auf NULL  
  gesetzt, nie freigegeben.  
  *Skizze:* In `_clear_content()` / beim Panel-Abbau (entry `_detach`):  
  `GLib.source_remove(timer)` + `playbin.set_state(NULL)`; Timer nur  
  laufen lassen, solange wirklich abgespielt wird.
- [x] **B4 – Office-Cache-Schreibfehler** (`_office_job_done`, panel)

  Ist der Cache unbeschreibbar (Disk voll, `~/.cache` read-only), schlägt  
  `shutil.move` fehl – `_office_failed` wird aber nur bei fehlendem  
  out\_pdf gesetzt. Folge: jede Auswahl desselben Dokuments konvertiert  
  erneut (gleiche Symptomatik wie der alte EXDEV-Bug).  
  *Skizze:* Bei Schreibfehler ebenfalls in `_office_failed` aufnehmen und  
  einmalig dbggen; die Vorschau zeigt dann das fertige PDF aus dem  
  Temp-Ordner direkt, ohne Cache.
- [x] **B5 – MOBI ohne Größendeckelung** (`_mobi_data`, panel)

  `fh.read()` liest die ganze Datei in den RAM – ein 500-MB-AZW3 friert  
  Nemo ein.  
  *Skizze:* Nur Datensatz-Tabelle + erste n Text-Datensätze lesen  
  (Anzahl begrenzen, z. B. 32 MB Deckel); Rest nicht mehr anfassen.
- [x] **B6 – Markdown kleiner als die System-Schriftgröße**

  (`_render_markdown`, panel; aus dem Testfeld gemeldet)  
  Der Textkörper wurde mit hartcodierter Standardschrift in 9 pt  
  überschrieben und erschien damit kleiner als die Text-Vorschau  
  (Monospace), die der Nutzer als „System-Schriftgröße" wahrnimmt.  
  *Skizze:* override\_font für Markdown wegfallen lassen – der  
  TextView nutzt dann die System-Schrift des GTK-Themes.  
  ✅ 0.10.1: umgesetzt; Überschriften skalieren mit (relative  
  size-Angaben im Markup). EML/E-Book bleiben vorerst bei 9 pt  
  (gleiches Muster, gleiche Lösung möglich – bewusst nicht  
  mitgerissen, da nicht gemeldet).
- [x] **B7 – R9-Regression: Bild-Vorschau erschien gar nicht mehr**

  (`_render_image`/`_image_probe_done`, panel; aus dem Testfeld  
  gemeldet, nur in 0.10.2)  
  0.10.2 dekodierte die Bilder im Daemon-Thread und erzeugte dort  
  Gdk-Objekte (PixbufLoader) – gegen das R1-Muster „keine Gdk-  
  Objekte im Worker". Im Feld scheiterte der Worker still: keine  
  Vorschau, kein Traceback, kein Fehlerhinweis; im Log tauchte nur  
  die GdkPixbuf-Warnung „Loader finalized without close" auf (sie  
  stammte vom \_image\_gi\_warmup-Loader, den niemand schloss, und  
  war Symptom-Anzeiger, nicht Ursache).  
  *Skizze:* Worker liest nur die Datei (reines Python-I/O) und  
  reicht die Bytes per GLib.idle\_add zurück; Dekodierung, EXIF-  
  Drehung und Skalierung laufen im GTK-Thread (wie bei den  
  Medien-Covern); \_image\_gi\_warmup/\_IMAGE\_STATE entfernen.  
  ✅ 0.10.3: umgesetzt wie skizziert – aber im Feldtest blieb die  
  Vorschau unsichtbar. Zweite, eigentliche Ursache (seit 0.10.2):  
  Die im Idle-Callback gepackten Widgets liegen NACH dem show\_all()  
  des Render-Durchlaufs und wurden nie sichtbar – das R1-Muster  
  \_media\_probe\_done endet genau deshalb mit einem eigenen  
  show\_all (mit Kommentar!), im R9-Umbau aber übersehen. Symptom  
  passte perfekt: kein Traceback, kein Fehlerhinweis, der  
  „Lade Bild"-Zettel blieb stehen, der Fehler-Fallback wäre  
  ebenso unsichtbar gewesen.  
  ✅ 0.10.4: show\_all am Ende von \_image\_probe\_done an BEIDEN  
  Exit-Pfaden (Vorschau und Fehler-Fallback); zusätzlich dbg-  
  Diagnosezeilen (Bild gelesen/dekodiert/verworfen), damit der  
  Log den Bild-Weg ab jetzt nachvollziehbar zeigt.
- [x] **B8 – Konfiguration nicht speicherbar: Gio.Keyfile**

  (F12/\_config\_save, panel; aus dem Testfeld gemeldet, nur in  
  0.12.0)  
  0.12.0 adressierte die Keyfile-Klasse als Gio.Keyfile –  
  PyGObject bindet GKeyFile aber als GLib.KeyFile (GLib, nicht  
  Gio). Die Defensiv-Blöcke fingen den AttributeError, dbg  
  meldete „Konfiguration nicht speicherbar", Fenster und Defaults  
  blieben benutzbar – nur die Persistenz war tot.  
  *Skizze:* GLib.KeyFile verwenden, mit Kompatibilitäts-Auflösung  
  für den alten Alias GLib.Keyfile (Muster wie beim Discoverer  
  in \_media\_probe\_async); fehlt die Klasse ganz, dbggen statt  
  still.  
  ✅ 0.12.1: umgesetzt wie skizziert (Resolver \_KEYFILE\_CLS +  
  \_KEYFILE\_FLAGS\_NONE auf Modulebene, dbg in beiden Pfaden).

### 🟡 Risiken

- [x] **R1 – Discoverer synchron** (`_render_audio`, `_render_video`)

  `discover_uri_sync` blockiert bei kaputtem Medium / NFS / SMB bis zu  
  10 s die komplette UI. **M** – *Skizze:* `discover_uri_async` mit  
  Callback oder Discoverer in Idle/Thread; bis dahin Timeout senken.
- [x] **R2 – PDF rendert synchron alle Seiten** (`_render_pdf`)

  Bis zu 20 Seiten in 2-facher Breite bei der Auswahl – UI-Ruckler bei  
  gescannten PDFs. **M** – *Skizze:* Seite 1 sofort, Rest per  
  `GLib.idle_add` in kleinen Schritten nachschieben.
- [x] **R3 – Einzel-Slot-Design der Live-Skalierung** (`_scaled_image`)

  `self._scale_src` wird pro Renderzyklus überschrieben – nur EIN  
  live-skaliertes Bild ist möglich; ein zweiter `_scaled_image`-Aufruf  
  im selben Renderer verliert still die Skalierung des ersten. Heute  
  unkritisch, aber Designfalle. **M** – *Skizze:* Skalier-Status als  
  Attach-Daten ans Widget (`set_data`) statt Einzelattribute.
- [x] **R4 – EPUB-Kapitel ohne Chunk-Deckel** (`_epub_data`)

  Ein einzelnes riesiges XHTML (ZIP-Bombe) landet vollständig im RAM,  
  bevor auf 30 000 Zeichen gekürzt wird. **S** – *Skizze:* `zf.open(...)`  
  mit begrenztem `read(cap)` je Kapitel.
- [x] **R5 – Font-Temp-Ordner wächst unbegrenzt** (`_FONT_STATE`, panel)

  Kopien jeder angesehenen Schrift bleiben bis Reboot liegen; der Ordner  
  wird je Schrift komplett neu an Fontconfig übergeben. **S** – *Skizze:*  
  Deckel (z. B. 64 Dateien, älteste löschen) oder pro Sitzung einen  
  Unterordner je Hash anlegen und nur diesen übergeben.
- [x] **R6 – EPUB zeigt Inhaltsverzeichnis statt Textanfang**

  Steht `nav.xhtml`/TOC als erster Spine-Eintrag, dominiert das  
  Inhaltsverzeichnis die Vorschau. **S** – *Skizze:* Spine-Einträge mit  
  `properties="nav"` überspringen; Text erst ab erstem Inhalts-Kapitel.
- [x] **R7 – PalmDoc-Trailing-Entries** (`_palmdoc_decompress`)

  Gelegentliche Schmutzbytes zwischen MOBI-Datensätzen (kosmetisch).  
  **S** – *Skizze:* Trailing-Entry-Dekodierung ergänzen.  
  ✅ 0.4.3: umgesetzt als SICHERE Randbereinigung je Datensatz (Steuer-  
  und Ersatz-Zeichen am Datensatzrand entfernen). Die vollständige  
  Rückwärts-Dekodierung der Trailer-Größen wurde bewusst zurückgestellt:  
  Ohne Referenzmaterial wäre ein Dekodierfehler schlimmer als der  
  kosmetische Fehler.
- [x] **R8 – Nemo-Update verschiebt VTable-Offsets** (`previewer_select`)

  Validierungen fangen Layout-Brüche meist ab; Restrisiko bleibt.  
  **Beobachtungspunkt:** nach jedem Nemo-Update Log auf die bekannten  
  Zeilen prüfen (`VTable-API bereit` vs. Fallback-Meldungen).  
  ✅ 0.4.3: dokumentiert (kein Code-Fix möglich/sinnvoll) – Checkliste:  
  (1) vier geladen/bereit-Zeilen mit gleicher Version, (2) „VTable-API  
  bereit" ODER Fallback-Meldung, (3) „Auswahl geändert: …"-Zeilen beim  
  Anklicken. Alles da → keine Handlung nötig.
- [x] **R9 – Große Bilder blockieren die UI beim Laden**

  (`_render_image`, panel; aus dem Testfeld gemeldet)  
  20-MB-JPEGs (typisch 50–100 Megapixel) werden SYNCHRON im GTK-  
  Main-Loop bearbeitet: Datei lesen, Dekodieren, EXIF-Drehung und  
  Herunterskalieren laufen alle in einem Rutsch bei der Auswahl –  
  die UI steht in der Zeit still („laggy", spürbar mehr Ladezeit).  
  Erschwerend: Dekodiert wird bisher auf bis zu 4096 px Breite,  
  obwohl das Panel nur einige hundert Pixel zeigt – der Löwenanteil  
  der Dekodier-Arbeit ist verschenkt.  
  **M** – *Skizze:* zweistufig wie R1 (Medien) und R2 (PDF):  
  (1) sofort Hint „Lade Bild …" zeigen, (2) Lesen + Dekodieren +  
  EXIF-Drehung in einen Daemon-Thread verlagern (Pixbuf ist ein  
  reines Daten-Objekt ohne GTK-Bezug – die fertige Pixbuf per  
  GLib.idle\_add zurückreichen und gegen die aktuelle Auswahl  
  prüfen, veraltet = verwerfen). Zusätzlich Beschleunigung beim  
  Dekodieren selbst: den size-prepared-Deckel statt stur 4096 px  
  auf max(2 × Panelbreite, 1024) setzen – die Dekodierung wird  
  damit um ein Vielfaches billiger, und die Live-Skalierung  
  verliert nichts (Quelle bleibt größer als jede Panelbreite).  
  Rettungsanker: Schlägt der Thread-Pfad fehl, bleibt der  
  synchrone Weg als Fallback.  
  ✅ 0.10.2: umgesetzt wie skizziert – GI-Warm-up im GTK-Thread  
  (\_image\_gi\_warmup, wie R1), Dekodierung im Daemon-Thread mit  
  Idle-Rückgabe und Auswahl-Abgleich, Originalmaße aus  
  size-prepared fürs Info-Label (statt der Dekodiergröße); Thread-  
  Start-Fehler fallen auf den synchronen Weg zurück.  
  ⚠️ Feldtest 0.10.2: REGRESSION – die Dekodierung im Worker  
  erzeugte Gdk-Objekte (PixbufLoader) außerhalb des GTK-Threads  
  und scheiterte still (keine Vorschau, kein Traceback, nur die  
  GdkPixbuf-Finalize-Warnung des Warm-up-Loaders im Log); die  
  Annahme „Pixbuf im Thread ist ungefährlich" war falsch.  
  ✅ 0.10.3 korrigiert auf das R1-Muster: Der Thread liest NUR die  
  Datei (reines I/O), Dekodierung/EXIF/Skalierung laufen zurück im  
  GTK-Thread; \_image\_gi\_warmup entfiel komplett (Quelle der  
  GdkPixbuf-Warnung). Details siehe B7.  
  ⚠️ Feldtest 0.10.3: Vorschau blieb UNSICHTBAR – die eigentliche  
  Ursache war ein zweiter, seit 0.10.2 wirksamer Fehler (fehlendes  
  show\_all im Idle-Callback, siehe B7); ob die Worker-Dekodierung  
  zusätzlich scheiterte, war ohne Anzeige nicht unterscheidbar.  
  Die R1-Struktur (nur I/O im Thread) bleibt trotzdem die richtige  
  Basis. ✅ 0.10.4 zeigt das Ergebnis an.

### ⚪ Kosmetik

- [x] **K1** – Ordner-Vorschau zählt versteckte Dateien mit

  (`_render_folder`): nur sichtbare zählen. **S**  
  ✅ 0.5.1 – bewusst als KOMPROMISS gelöst statt nur-sichtbar-zählen:  
  Es wird weiterhin ALLES gezählt (stimmt mit `ls -A` überein), der  
  Nutzer aber informiert – „Der Ordner enthält X Dateien, davon  
  X versteckt." Versteckte verschwinden so nicht stillschweigend aus  
  der Zählung.
- [ ] **K2** – Kaputtes Office-ZIP zeigt nur Hinweiszeile, kein Icon:

  `_render_generic()` als Hintergrund dazu. **S**
- [ ] **K3** – SVG: intrinsisch kleine SVGs bleiben klein (kein

  DPI-Rendern); `Rsvg.Handle.get_pixbuf()` ist in neuerem librsvg  
  deprecated. **S–M**
- [ ] **K4** – Markdown: Tabellen, Setext-Überschriften, Task-Listen,

  tiefe Inline-Verschachtelungen; Links mit Klammern brechen die Regex.  
  **S–M**, priorisieren nach Bedarf.
- [ ] **K5** – `Gst.init(None)` beim Import verlangsamt den Nemo-Start

  minimal → GStreamer erst beim ersten Audio/Video-Rendering anfassen  
  (lazy init). **S**
- [ ] **K6** – Mehrfachauswahl zeigt nur „… und N weitere" → Icon-Raster

  der ersten \~8 Dateien. **S–M**
- [ ] **K7** – Variable Fonts zeigen nur die Default-Instanz (bekannt;

  ggf. named instances aus fvar-Tabelle anbieten). **M**

---

## Teil 2: Features (Vorschläge)

### Robustheit &amp; Qualität

- [ ] **F1 – Parser-Selbsttest**: `python3 previewer_panel.py --selftest`

  mit Fixtur-Dateien (md/epub/mobi/font) – Regressionstests ohne Nemo.  
  **M**
- [ ] **F2 – Render-Debounce**: Schwer-Renderer (PDF, Office, Audio)

  erst nach kurzer Auswahl-Ruhe starten. **S**
- [ ] **F28 – Kommentare auslagern: Marker statt Fließtext**

  (alle vier Module, Nutzer-Wunsch: „die \*.py sollen schlanker  
  werden"; HAUPTZWECK: die Referenz wird fortlaufend aktualisiert)  
  Die Module sind durch die ausführlichen Block-Kommentare und  
  Docstrings (R-/B-/F-Notizen, Skizzen, Historie) auf 128–2766  
  Zeilen gewachsen. Jede längere Kommentar-Stelle bekommt stattdes-  
  sen einen kurzen, stabilen Marker (Vorschlag: Modul-Kürzel +  
  Fortlaufnummer, z. B. `# → REF PAN-R9-1`); die vollständigen Texte  
  wandern nummeriert in eine Referenzdatei REFERENZ.md im Repo.  
  REFERENZ.md ist kein einmaliger Auszug, sondern das LEBENDIGE  
  Projektdokument: Sie wird bei jeder künftigen Änderung im selben  
  Zug mit aktualisiert (Nutzer-Entscheid) – genau wie changelog.md  
  und planned.md heute schon Teil jedes Fixes sind.  
  **M** – *Skizze:* Ehrliche Abwägung vorab: Kommentare kosten KEINE  
  Laufzeit – der Gewinn ist reine Lesbarkeit und kürzere Dateien,  
  kein Performance- oder Speichereffekt. Fortlaufende Pflege heißt  
  konsequent: Berührt ein Fix eine markierte Stelle, gehört die  
  REFERENZ.md-Aktualisierung zum Done-Zustand (eigenes Canvas wie  
  für jede Repo-Datei, eigene Commit-Zeile im Antwort-Schema);  
  Marker eindeutig und stabil nummerieren, NIE umbenennen. Was  
  NICHT wandert: STAND-/Versions-Zeilen und PREVIEWER\_VERSION  
  (Konvention!), einzeilige Helfer-Docstrings (help() bleibt  
  nützlich) und kurze Inline-Hinweise, wo Code sonst rätselhaft  
  bliebe – nur die langen Block-Kommentare und Historien-Docstrings.  
  REFERENZ.md wird NICHT mitdeployt (Kopierliste nimmt nur \*.py).  
  Canvas-Workflow: Die Soll-Zeilenzahlen ändern sich massiv → in  
  einem ruhigen Moment umsetzen, nicht mit laufenden Fixes  
  vermischt, danach neue Soll-Zeilen vereinbaren.

### Neue Formate

- [ ] **F3 – Archiv-Vorschau** (ZIP/TAR): Inhaltsliste, Anzahl,

  Gesamtgröße – reine `zipfile`/`tarfile`-Bordmittel. **S**
- [ ] **F4 – CBZ/CBR** (Comic = ZIP von Bildern): Seiten-Streifen wie

  bei der PDF-Vorschau; CBR nur bei vorhandenem unrar. **M**
- [ ] **F5 – Animated GIF/WebP abspielen**

  (`GdkPixbuf.PixbufAnimation` → `Gtk.Image` statt Pixbuf). **S**
- [ ] **F6 – SQLite-Datenbanken** (.db/.sqlite): Tabellenliste +

  Zeilenanzahl (stdlib `sqlite3`). **S**
- [ ] **F7 – vCard/ICS**: Kontakte &amp; Termine als Tabelle (wie EML-Kopf).

  **S**
- [ ] **F8 – CSV als echte Tabelle** (Gtk.TreeView). **M**
- [ ] **F9 – EXIF-Tabelle für Fotos** (Kamera, Datum, Belichtung). **M**
- [ ] **F10 – Torrent-Dateien** (bencode-Parser, \~40 Zeilen). **S**
- [ ] **F11 – WOFF1-Fonts** (zlib-entpackter sfnt → Wasserfall läuft

  mit). **S**

### Bedienung &amp; Komfort

- [ ] **F12 – Konfiguration der Vorschauspalte** (Nutzer-Wunsch;

  Pfad laut Nutzer-Entcheid: `~/.config/nemo-previewer/ nemo-previewer.conf`): Panelbreite, Sichtbarkeit, MAX\_PDF\_PAGES,  
  Wasserfall-Probetext. **M**  
  ✅ Teil 1 in 0.12.0: Zahnrad-Knopf öffnet das Einstellungsfenster  
  (eine Instanz, wiederholter Klick holt es nach vorn); jede Änderung  
  speichert sofort und wird bei jedem Start  
  angewendet (apply\_start\_settings im Einstieg, NACH dem show\_all  
  der Injizierung); erste Einstellung „Vorschauspalte beim Start  
  anzeigen" läuft damit komplett durch (Fenster → conf → Start).  
  Offen: die übrigen Einstellungen (Panelbreite, MAX\_PDF\_PAGES,  
  Wasserfall-Probetext …) andocken.
- [ ] **F13 – Knöpfe „Im Dateimanager zeigen" + „Pfad kopieren"** neben

  Öffnen. **S**
- [x] **F14 – PDF-Seitenanzeige** „Seite 3/47" beim Scrollen. **S**

  ✅ 0.9.0: dezentes dim-Label über dem scrollbaren Bereich; beim  
  Scrollen zählt es die Seite nach, deren Unterkante den oberen Rand  
  des Sichtfensters überschreitet; einseitige PDFs ohne Anzeige;  
  der frühere Hinweis „N Seiten – Vorschau nach unten scrollen."  
  entfiel als redundant.
- [ ] \*\*F15 – Audio: Lautstärke-Slider; bei Mehrfachauswahl Titel

  vor/zurück.\*\* **S–M**
- [ ] **F16 – Bild-Zoom**: Klick öffnet 1:1-Ansicht im Panel. **M**
- [ ] **F17 – Panel links/rechts umschaltbar** (Crowbar parametrisieren).

  **M**
- [x] **F18 – Audio-Platzhalter-Cover** (vorgezogen auf Wunsch)

  Musikdateien ohne eingebettetes Cover zeigten nur Textzeilen. **M**  
  *Skizze:* gezeichnete Kachel (Verlauf + Notensymbol) als Pixbuf,  
  Fallback über Theme-Icon. ✅ 0.5.0: umgesetzt – Cairo/Pango-Kachel  
  mit abgerundeten Ecken in 2-facher Auflösung, Icon-Fallback ohne  
  PangoCairo; angezeigt über der Player-Leiste wie echte Covers.
- [x] **F23 – Text-Vorschau für endungslose Dateien** (vorgezogen

  auf Wunsch). **S–M**  
  Der MIME-Typ-Rater von Gio errät nur bekannte Namen (README,  
  Makefile, LICENSE …) – frei benannte Dateien (notes, todo, Dotfiles  
  wie .bashrc) fielen auf application/octet-stream und zeigten nur  
  Icon + Infos. ✅ 0.10.0: \_sniff\_is\_text prüft die ersten 4 KB  
  (keine NULL-Bytes, unter 5 % Steuerzeichen); nur ohne Endung UND  
  bei bestandener Prüfung zeigt der Dispatcher die Text-Vorschau –  
  endungslose Binärdateien bleiben generisch. Nebeneffekt: Der  
  \_TEXT\_EXTRAS-Eintrag „.gitignore" konnte nie matchen (splitext  
  zählt führende Punkte zum Namen); das Sniffing deckt solche  
  Dotfiles jetzt generisch ab.
- [ ] **F19 – Vorschau-Toolbar am unteren Rand der Vorschauspalte**

  Kontextsensitive Knopfleiste unter dem Vorschaubereich; die  
  Renderer melden ihre Aktionen, statt Buttons frei im Inhalt zu  
  streuen. Basis für F13 (Pfad kopieren), F20 (OCR), F21  
  (Office→PDF) und F24–F27 (Zeilennummern, Zeilenabstand,  
  Bild→PNG-mit-Alpha, Mehrfachauswahl-Aktionen). **M** – *Skizze:*  
  Gtk.ActionBar (oder ButtonBox) als fester Fuß der Spalte unter  
  `self._content`; je Renderer Liste von (Icon, Tooltip, Callback)-  
  Tripeln. Nutzer-Entscheid (0.11.0): Die Leiste ist STATISCH –  
  immer sichtbar, solange das Panel aktiv ist; das ursprüngliche  
  „ohne Aktionen bleibt die Leiste ausgeblendet" ist damit  
  verworfen. ✅ Teil 1 in 0.11.0: ActionBar-Fuß mit eigener  
  Trennlinie unter dem Inhaltsbereich, rechts außen fester  
  Einstellungs-Knopf (preferences-system-symbolic, Zahnrad aus den  
  Systemicons, Tooltip „Einstellungen"). 0.12.0: Der Knopf öffnet  
  das F12-Einstellungsfenster; Leiste laut Nutzer-Wunsch \~5 px  
  schmaler (CSS, 3+4 px Innenabstand). Offen: Anmeldung der  
  Renderer-Aktionen (Icon, Tooltip, Callback) inkl.  
  Auswahlwechsel-Verwaltung.
- [ ] **F20 – OCR-Button bei PDFs** (in der Toolbar, F19)

  Bei PDF-Auswahl erscheint ein OCR-Knopf; Klick führt eine  
  Texterkennung auf die PDF durch und speichert das Ergebnis als  
  Kopie (z.B. `Name_OCR.pdf`) neben dem Original – Original bleibt  
  unangetastet. **M–L** – *Skizze:* Backend `ocrmypdf` (Paket, nutzt  
  tesseract; erhält durchsuchbare Textebene), Hintergrund-Job im  
  Muster `_office_start_job` (spawn\_async + child\_watch + Hinweis im  
  Panel, kein UI-Freeze); ohne ocrmypdf: Knopf grau mit Hinweis  
  „Paket ocrmypdf installieren". Gescannte PDFs = Hauptanwendungsfall.
- [ ] **F21 – Office→PDF-Knopf** (in der Toolbar, F19)

  Bei Office-Dokumenten (ODT/ODS/ODP, DOCX/XLSX/PPTX) bietet die  
  Toolbar „Als PDF speichern": konvertiert das Dokument nach PDF und  
  legt die Kopie neben dem Original ab. **S–M** – *Skizze:* Steht das  
  Cache-PDF schon bereit (`_office_cached_pdf`), ist es ein reiner  
  Kopierlauf; sonst LibreOffice-Konvertierung als Hintergrundjob im  
  bestehenden Muster (`soffice --headless --convert-to pdf`) und  
  danach kopieren. Zielname: gleicher Basisname + `.pdf`  
  (Kollision vermeiden: bei Existenz `_1`, `_2` … anhängen).
- [ ] **F24 – Zeilennummern ein-/ausblenden** (Text-Toolbar, F19)

  Bei Textdateien zeigt die Toolbar einen Knopf „Zeilennummern".  
  Die Nummern dürfen NICHT mitkopiert werden – Selektion/Kopie  
  erfassen ausschließlich den eigentlichen Inhalt (Nutzer-Wunsch).  
  **S–M** – *Skizze:* Text-Vorschau auf GtkSource.View umstellen  
  (Paket gir1.2-gtksourceview-4): Der Nummern-Gutter ist KEIN Teil  
  des TextBuffers, Selektion und Kopie greifen ihn nie an – genau  
  die geforderte Trennung. Ohne GtkSource: Knopf ausgegraut mit  
  Hinweis „Paket gir1.2-gtksourceview-4 installieren" (Alternative  
  ohne Paket wäre eine synchrone Nummern-Spalte als DrawingArea –  
  mehr Arbeit, lieber das fertige GtkSource-Gutter). Später ggf.  
  auch für die anderen TextView-Ansichten (EML-Kopf, E-Book)  
  anbieten.
- [ ] **F25 – Zeilenabstand einstellen** (Text-Toolbar, F19)

  Knopf „Zeilenabstand" in der Text-Toolbar, z. B. Durchschalten  
  zwischen normal / luftig / sehr luftig (Nutzer-Wunsch: „etwas  
  modifizieren"). **S** – *Skizze:* GtkTextTag „zeilenabstand" mit  
  pixels-above-lines (z. B. Stufen 0/3/6 px) über den gesamten  
  Buffer anwenden – nach jedem erneuten Laden/Neuaufbau der  
  Vorschau wiederholen; Zustand als Panel-Attribut, damit der  
  Knopf beim nächsten Öffnen die richtige Stufe anzeigt. Kopier-  
  Verhalten ändert sich nicht (Tag beteiligt sich nicht an der  
  Zwischenablage).
- [ ] **F26 – Bild als PNG mit Alphakanal speichern** (Toolbar, F19)

  Bei Bilddateien ein Knopf „Als PNG mit Alpha speichern": legt das  
  Bild als PNG MIT Alphakanal als Kopie neben dem Original ab –  
  Original unangetastet (Nutzer-Wunsch). **S–M** – *Skizze:* Pixbuf  
  im GTK-Thread laden (R1-Muster), EXIF-Ausrichtung anwenden,  
  `pb.add_alpha()` erzwingt den Alphakanal auch bei JPEG-Quellen,  
  `pb.savev()` als PNG; Zielname Basisname + `.png`, bei Existenz  
  `_1`, `_2` … (wie F21); ohne Schreibrechte im Ordner: Fehler-  
  Hinweis im Panel statt Traceback.
- [ ] **F27 – Aktionen bei Mehrfachauswahl** (Toolbar, F19)

  Bei Mehrfachauswahl (das Panel kennt bereits alle Namen über  
  `self._names`) bietet die Toolbar gemeinsame Aktionen für die  
  ausgewählten Dateien statt nur „… und N weitere" (Nutzer-Wunsch).  
  Erstes Beispiel: mehrere PDFs zu EINER Datei zusammenfügen.  
  **M–L** – *Skizze:* Toolbar prüft die Typen der Auswahl und  
  zeigt nur gemeinsame Aktionen. PDF-Zusammenfügen als Hintergrund-  
  job im `_office_start_job`-Muster (spawn\_async + child\_watch +  
  Hinweis im Panel, kein UI-Freeze); Backend-Reihenfolge  
  `pdfunite` (poppler-utils) → `qpdf` → Knopf grau mit Installations-  
  Hinweis; Ziel neben den Quellen (z. B. Basisname der ersten  
  Datei + „\_zusammen.pdf", Kollisions-Suffix `_1`, `_2` …).  
  Später denkbar: mehrere Bilder → Bildstreifen/Kontaktbogen,  
  mehrere Medien → Playlist.
- [ ] **F29 – Toolbar als eigene Datei** (previewer\_toolbar.py,

  Nutzer-Wunsch: „wenn möglich und sinnvoll")  
  Die F19-Toolbar ggf. als fünftes Modul führen statt als Teil von  
  previewer\_panel.py. **S–M** – *Skizze:* Wird sinnvoll, sobald der  
  Aktionen-Katalog wächst (F13, F20, F21, F24–F27): Eine eigene  
  Datei hält das Panel schlanker und die Toolbar isoliert testbar.  
  previewer\_toolbar importiert nur GTK + previewer\_util, NICHT das  
  Panel – das Panel instanziiert die Toolbar und meldet (Icon,  
  Tooltip, Callback)-Tripel an; so gibt es keine Zirkel-Imports.  
  Konsequenzen ehrlich mitdenken: PREVIEWER\_VERSION dann in FÜNF  
  Dateien identisch (Versions-Check im Einstieg erweitern!),  
  dbg-Zeile „previewer\_toolbar … geladen", neues Canvas pro  
  Repo-Datei; die Deploy-Kopierliste bleibt `cp *.py` (erfasst das  
  neue Modul automatisch). Erst ZUSAMMEN mit F19 anpacken – vorher  
  gibt es nichts auszulagern; bleibt die Toolbar am Ende klein,  
  ist sie im Panel besser aufgehoben („wenn sinnvoll" vor dem  
  Abspalten ehrlich abwägen).
- [ ] **F22 – Video-Platzhalterbild + Wiedergabe im Panel**

  Filmdateien ohne Standbild bekommen dieselbe generische Kachel wie  
  Musik ohne Cover (Symbol z.B. Filmstreifen/Kamera statt Noten);  
  wenn möglich soll der Film außerdem im Panel abspielbar sein wie  
  Musik (Player-Leiste mit Position/Slider). **M–L** – *Skizze:*  
  `_media_cover_placeholder` um ein Symbol-Parameter ergänzen;  
  Wiedergabe über den bestehenden Playbin mit Gtk-Video-Sink  
  (`Gst.ElementFactory.make("gtksink")` → `get_widget()` in eine  
  DrawingArea unter dem Standbild packen), Player-Leiste und  
  EOS/Timer-Logik aus `_finish_audio` wiederverwenden; ohne gtksink  
  nur Ton mit Hinweis. ✅ Kachel in 0.7.0 (Abspiel-Dreieck +  
  Filmperforation, Petrol-Verlauf) – besteht und bleibt. Die Standbild-  
  Extraktion aus 0.6.0 (Teil 1) wurde in 0.7.0 wieder entfernt – sie  
  lieferte nie ein Bild und ließ das GI-Warm-up am fehlenden  
  Gst.PlayFlags des Mint-22-Bindings abstürzen. Die Wiedergabe war  
  0.7.0–0.7.2 eingebaut (gtksink, Appsink-Eigenbau, Redraw-Fix) und  
  wurde in 0.8.0 VOLLSTÄNDIG zurückgebaut: gtksink fehlt ohne  
  gstreamer1.0-gtk3, der Eigenbau zeigte im Feld kein Bild. Später neu  
  angehen; \_playbin\_set\_uri/\_player\_bar bleiben als Bausteine.

---

## Empfohlene Reihenfolge


| Schritt | Inhalt                                                                                                                                                                                                                                                                                                                                                  | Zielversion                                                           |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1       | 🔴 B1–B5 (Bug-Paket)                                                                                                                                                                                                                                                                                                                                    | ✅ 0.4.2 (Patch)                                                       |
| 2+3     | 🟡 R1–R8 (Robustheits-Paket, zusammengezogen)                                                                                                                                                                                                                                                                                                           | ✅ 0.4.3 (Patch)                                                       |
| 4       | F18 – Audio-Platzhalter-Cover (vorgezogen)                                                                                                                                                                                                                                                                                                              | ✅ 0.5.0 (Minor)                                                       |
| 5       | K1 – Ordnerzählung transparent (Kompromiss, vorgezogen)                                                                                                                                                                                                                                                                                                 | ✅ 0.5.1 (Patch)                                                       |
| 6       | F22 Teil 1 – Video-Standbild-Extraktion (vorgezogen)                                                                                                                                                                                                                                                                                                    | ✅ 0.6.0 (Minor; in 0.7.0 wieder entfernt)                             |
| 7       | F22 – generische Video-Kachel + Wiedergabe im Panel (vorgezogen)                                                                                                                                                                                                                                                                                        | Kachel ✅ 0.7.0 (Minor); Wiedergabe 0.7.0–0.7.2, in 0.8.0 zurückgebaut |
| 8       | F14 – PDF-Seitenanzeige beim Scrollen (vorgezogen)                                                                                                                                                                                                                                                                                                      | ✅ 0.9.0 (Minor)                                                       |
| 8a      | Sicherheits- + Redundanz-Audit (3 Lebenszyklus-Fixes: Crowbar-Race, Poll-Timer-Leck, Office-Kind-Watch; TextView-/Lese-/Tabellen-/Name-Helfer gegen Redundanzen)                                                                                                                                                                                        | ✅ 0.9.1 (Patch)                                                       |
| 8b      | Audit 2 „Pufferüberlauf/OOM“ (Decode-/Lese-Deckel gegen Bild-/PDF-/EPUB-/DOCX-/EML-Bomben, Wildcall-Schutz für VTable-Funktionszeiger)                                                                                                                                                                                                                  | ✅ 0.9.2 (Patch)                                                       |
| 8c      | F23 – Text-Vorschau für endungslose Dateien (Inhalts-Sniffing, vorgezogen)                                                                                                                                                                                                                                                                              | ✅ 0.10.0 (Minor)                                                      |
| 8d      | B6 – Markdown in System-Schriftgröße (aus dem Testfeld gemeldet)                                                                                                                                                                                                                                                                                        | ✅ 0.10.1 (Patch)                                                      |
| 8e      | R9 – Große Bilder asynchron dekodieren + Dekodierung auf Anzeigegröße (vorgezogen, aus dem Testfeld gemeldet)                                                                                                                                                                                                                                           | ✅ 0.10.2 (Patch)                                                      |
| 8f      | B7 – R9-Regression: Dekodierung zurück in den GTK-Thread (Feldtest 0.10.2)                                                                                                                                                                                                                                                                              | ✅ 0.10.3 (Patch; Teil des Fixes)                                      |
| 8g      | B7 – fehlendes show\_all im Bild-Idle-Callback: eigentliche Feld-Ursache (R1-Muster nachgezogen)                                                                                                                                                                                                                                                        | ✅ 0.10.4 (Patch)                                                      |
| 9       | K2, K5 (Kosmetik-Rest) + F3, F5, F12 (Favoriten: Archiv, GIF, Konfiguration)                                                                                                                                                                                                                                                                            | später (vorher 0.10.0)                                                |
| 10      | F4, F6–F11 nach Bedarf                                                                                                                                                                                                                                                                                                                                  | später                                                                |
| 11      | F13, F15–F17 + K3, K4, K6, K7 nach Bedarf                                                                                                                                                                                                                                                                                                               | später                                                                |
| 12      | F19–F21 (Toolbar-Paket: Vorschau-Toolbar, OCR-Knopf bei PDFs, Office→PDF-Knopf; F19 zuerst, F20/F21 bauen darauf auf) + F24–F27 (Toolbar-Erweiterungen: Zeilennummern nicht kopierbar, Zeilenabstand, Bild→PNG-mit-Alpha, Mehrfachauswahl: PDFs zusammenfügen) + F29 (Toolbar ggf. als eigenes Modul previewer\_toolbar.py) + Neuversuch F22-Wiedergabe | später                                                                |
| 12a     | F19 Teil 1 – Toolbar-Grundgerüst: statische ActionBar am unteren Rand, Einstellungs-Knopf (Zahnrad-Systemicon) rechts                                                                                                                                                                                                                                   | ✅ 0.11.0 (Minor)                                                      |
| 12b     | F12 Teil 1 – Einstellungsfenster (öffnet über Zahnrad), Konfigurationsdatei \~/.config/nemo-previewer/nemo-previewer.conf mit sofortiger Speicherung + Anwendung bei jedem Start; erste Einstellung: Sichtbarkeit beim Start                                                                                                                            | ✅ 0.12.0 (Minor)                                                      |
| 12c     | B8 – F12-Feld-Fix: GLib.KeyFile statt Gio.Keyfile (Persistenz war wirkungslos)                                                                                                                                                                                                                                                                          | ✅ 0.12.1 (Patch)                                                      |
| 13      | F28 – Kommentar-Auslagerung (Marker + REFERENZ.md als laufend gepflegtes Projektdokument; Canvas-Soll-Zeilenzahlen danach neu vereinbaren)                                                                                                                                                                                                              | später (ruhiger Moment, nicht mit laufenden Fixes mischen)            |


Die Reihenfolge ist ein Vorschlag – nichts ist in Stein gemeißelt.