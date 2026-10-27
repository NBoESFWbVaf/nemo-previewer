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

- [ ] **F12 – Konfigurationsdatei** (`~/.config/previewer/previewer.conf`):

  Panelbreite, Sichtbarkeit, MAX\_PDF\_PAGES, Wasserfall-Probetext. **M**
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
  streuen. Basis für F13 (Pfad kopieren), F20 (OCR) und F21  
  (Office→PDF). **M** – *Skizze:* Gtk.ActionBar (oder ButtonBox) als  
  fester Fuß der Spalte unter `self._content`; je Renderer Liste von  
  (Icon, Tooltip, Callback)-Tripeln; ohne Aktionen bleibt die Leiste  
  ausgeblendet.
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


| Schritt | Inhalt                                                                                                                                                           | Zielversion                                                           |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1       | 🔴 B1–B5 (Bug-Paket)                                                                                                                                             | ✅ 0.4.2 (Patch)                                                       |
| 2+3     | 🟡 R1–R8 (Robustheits-Paket, zusammengezogen)                                                                                                                    | ✅ 0.4.3 (Patch)                                                       |
| 4       | F18 – Audio-Platzhalter-Cover (vorgezogen)                                                                                                                       | ✅ 0.5.0 (Minor)                                                       |
| 5       | K1 – Ordnerzählung transparent (Kompromiss, vorgezogen)                                                                                                          | ✅ 0.5.1 (Patch)                                                       |
| 6       | F22 Teil 1 – Video-Standbild-Extraktion (vorgezogen)                                                                                                             | ✅ 0.6.0 (Minor; in 0.7.0 wieder entfernt)                             |
| 7       | F22 – generische Video-Kachel + Wiedergabe im Panel (vorgezogen)                                                                                                 | Kachel ✅ 0.7.0 (Minor); Wiedergabe 0.7.0–0.7.2, in 0.8.0 zurückgebaut |
| 8       | F14 – PDF-Seitenanzeige beim Scrollen (vorgezogen)                                                                                                               | ✅ 0.9.0 (Minor)                                                       |
| 8a      | Sicherheits- + Redundanz-Audit (3 Lebenszyklus-Fixes: Crowbar-Race, Poll-Timer-Leck, Office-Kind-Watch; TextView-/Lese-/Tabellen-/Name-Helfer gegen Redundanzen) | ✅ 0.9.1 (Patch)                                                       |
| 8b      | Audit 2 „Pufferüberlauf/OOM“ (Decode-/Lese-Deckel gegen Bild-/PDF-/EPUB-/DOCX-/EML-Bomben, Wildcall-Schutz für VTable-Funktionszeiger)                           | ✅ 0.9.2 (Patch)                                                       |
| 8c      | F23 – Text-Vorschau für endungslose Dateien (Inhalts-Sniffing, vorgezogen)                                                                                       | ✅ 0.10.0 (Minor)                                                      |
| 9       | K2, K5 (Kosmetik-Rest) + F3, F5, F12 (Favoriten: Archiv, GIF, Konfiguration)                                                                                     | später (vorher 0.10.0)                                                |
| 10      | F4, F6–F11 nach Bedarf                                                                                                                                           | später                                                                |
| 11      | F13, F15–F17 + K3, K4, K6, K7 nach Bedarf                                                                                                                        | später                                                                |
| 12      | F19–F21 (Toolbar-Paket: Vorschau-Toolbar, OCR-Knopf bei PDFs, Office→PDF-Knopf; F19 zuerst, F20/F21 bauen darauf auf) + Neuversuch F22-Wiedergabe                | später                                                                |


Die Reihenfolge ist ein Vorschlag – nichts ist in Stein gemeißelt.