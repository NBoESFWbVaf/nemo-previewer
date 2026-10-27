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

- [ ] **K1** – Ordner-Vorschau zählt versteckte Dateien mit

  (`_render_folder`): nur sichtbare zählen. **S**
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
- [ ] **F14 – PDF-Seitenanzeige** „Seite 3/47" beim Scrollen. **S**
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

---

## Empfohlene Reihenfolge


| Schritt | Inhalt                                                                           | Zielversion     |
| ------- | -------------------------------------------------------------------------------- | --------------- |
| 1       | 🔴 B1–B5 (Bug-Paket)                                                             | ✅ 0.4.2 (Patch) |
| 2+3     | 🟡 R1–R8 (Robustheits-Paket, zusammengezogen)                                    | ✅ 0.4.3 (Patch) |
| 4       | F18 – Audio-Platzhalter-Cover (vorgezogen)                                       | ✅ 0.5.0 (Minor) |
| 5       | K1, K2, K5 (Kosmetik-Rest) + F3, F5, F12 (Favoriten: Archiv, GIF, Konfiguration) | 0.6.0           |
| 6       | F4, F6–F11 nach Bedarf                                                           | 0.7.0           |
| 7       | F13–F17 + K3, K4, K6, K7 nach Bedarf                                             | später          |


Die Reihenfolge ist ein Vorschlag – nichts ist in Stein gemeißelt.