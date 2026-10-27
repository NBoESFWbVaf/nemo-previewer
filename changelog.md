# Changelog

Alle nennenswerten Änderungen am Nemo-Previewer werden in dieser Datei  
dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),  
Versionierung: [Semantic Versioning](https://semver.org/lang/de/).

## \[Unreleased\]

## \[0.4.0\] – 2026-10-27

### Added (Hinzugefügt)

- Schriftarten-Vorschau als Wasserfall (.ttf, .otf, .ttc): Die Datei  
wird nur für den laufenden Prozess über Fontconfig eingebunden  
(FcConfigAppFontAddDir via ctypes – nichts wird installiert), der  
Familien- und Stilname wird direkt aus der sfnt-Namens-Tabelle  
gelesen, und ein Probetext zeigt die Schrift in den Größen 8 bis  
48 pt. Kann Pango die Familie nicht finden, erscheint ein Hinweis  
und der Wasserfall läuft mit der Ersatzschrift. Keine neuen  
Paket-Abhängigkeiten.

## \[0.3.1\] – 2026-10-27

### Changed (Geändert)

- Installationsanleitung als eigene Datei INSTALL.md (Englisch) im  
Repository: Voraussetzungen, optionale Pakete je Vorschautyp,  
Installation, Upgrade, Deinstallation und Fehlerbehebung. Die  
entsprechenden Installations- und Deinstallations-Passagen wurden  
aus den Modul-Docstrings entfernt; sie verweisen nun auf INSTALL.md.

## \[0.3.0\] – 2026-10-26

### Added (Hinzugefügt)

- E-Book-Vorschau (nur Python-Bordmittel, keine neuen Pakete):
  - EPUB (.epub): Titel, Autor und Sprache aus der OPF-Inhaltsdatei,  
  eingebettetes Cover (Manifest-Verweis oder Heuristik) und der  
  Textanfang in Lesereihenfolge (Spine)
  - FictionBook 2 (.fb2): Titel und Autor, Cover aus der eingebetteten  
  base64-Ressource, Textanfang des Hauptkörpers
  - MOBI (.mobi, .prc, .azw, .azw3): Titel, Autor aus dem EXTH-Header  
  und Textanfang; PalmDoc-Entpackung in reinem Python; Dateien mit  
  HUFF/CDIC-Kompression werden mit Hinweis abgelehnt
  - unlesbare/kaputte E-Books zeigen einen Hinweis statt einer leeren  
  Vorschau
- Neue Konstante MAX\_EBOOK\_CHARS (30 000 Zeichen Textanfang je Buch)

## \[0.2.2\] – 2026-10-26

### Fixed (Behoben)

- SVG-Dateien wurden nicht angezeigt (GdkPixbuf-Fehler „Format konnte  
nicht erkannt werden"): GdkPixbuf bringt seit Version 2.42 keinen  
SVG-Loader mehr mit. SVGs werden jetzt über librsvg gerendert, falls  
vorhanden (Paket gir1.2-rsvg); andernfalls erscheint ein Hinweis  
statt einer Fehlermeldung. Auch nicht ladende Rasterbilder zeigen  
nun einen Hinweis statt einer leeren Vorschau.
- Der Office-Cache wurde nie geschrieben: os.replace scheitert still  
mit „Ungültiger Link über Gerätegrenzen hinweg" (EXDEV), wenn /tmp  
ein tmpfs auf einem eigenen Gerät liegt. Dadurch konvertierte  
LibreOffice dasselbe Dokument bei jeder Auswahl erneut. Der Cache  
nutzt jetzt shutil.move, das geräteübergreifend kopiert – jede  
Konvertierung läuft nur noch einmal pro Dokument-Version.

## \[0.2.1\] – 2026-10-26

### Fixed (Behoben)

- Markdown-Vorschau blieb bei Dateien mit `---`-Linien (YAML-Front-Matter,  
Trennlinien) leer: ein Operator-Rangfolge-Fehler erzeugte ungültige  
Pango-Markup-Tags, die GTK beim Einfügen still verwarf. Korrigiert;  
zusätzlich wird das Markup vor dem Einfügen validiert – im Zweifel  
erscheint nun der Rohtext statt einer leeren Vorschau.

## \[0.2.0\] – 2026-10-26

### Added (Hinzugefügt)

- Markdown-Vorschau (.md) gerendert: Überschriften, Fett-/Kursivschrift,  
Inline- und Block-Code, Listen, Zitate, Trennlinien und Links als  
formatierter Text (Pango-Markup, ohne neue Paket-Abhängigkeiten)
- EML-Vorschau (.eml): Kopfzeilen (Betreff, Von, An, Cc, Datum) als  
Tabelle plus Textkörper – bevorzugt text/plain, andernfalls wird der  
HTML-Teil zu lesbarem Text bereinigt (Python-Bordmittel)

### Fixed (Behoben)

- EXIF-Ausrichtung von Bildern wird jetzt immer angewendet: Fotos, die  
die Drehung nur im Orientation-Tag tragen, wurden zuvor quer bzw. im  
falschen Format dargestellt; die Pixel-Maße unter der Vorschau  
zeigen jetzt die tatsächlich angezeigte Orientierung

## \[0.1.0\] – 2026-10-26

Erste versionierte Fassung der Nemo-Extension „Previewer“.

### Added (Hinzugefügt)

- Angedocktes Vorschau-Panel rechts im Nemo-Fenster (Crowbar-Technik über  
Nemo.LocationWidgetProvider und Gtk.Paned), Trenner frei verschiebbar
- Vorschauen: Bilder, Text/Quellcode, PDF (alle Seiten untereinander  
scrollbar, bis 20 Seiten), Audio (GStreamer-Player mit Play/Pause,  
Positions-Slider und Seek), Video (Standbild, Tags, Dauer), Ordner und  
Dateiinformationen für alles andere
- Office-Dokumente scharf: LibreOffice-Konvertierung im Hintergrund nach  
PDF, gecacht in \~/.cache/previewer; während der Konvertierung die  
eingebettete Miniaturansicht mit Hinweis, das scharfe Ergebnis erscheint  
automatisch; ohne LibreOffice Miniaturansicht aus dem Dokument-ZIP
- Auswahl-Erkennung über NemoView.peek\_selection (Klassen-VTable), die  
Nemo-Auswahl-API, Gtk.IconView/TreeView und ATK-Fallbacks; Auswahl-  
Signale werden zur Laufzeit entdeckt und verbunden
- Live-Skalierung der Vorschau mit der Panelbreite ohne Neu-Rendern
- Panel ein-/ausblenden per Strg+Alt+P
- Vier-Module-Struktur (previewer.py, previewer\_panel.py,  
previewer\_select.py, previewer\_util.py) mit Versionsabgleich beim Start:  
veraltete Dateien im Extension-Ordner werden im Terminal-Log sofort  
als ACHTUNG-Meldung sichtbar
- changelog.md und semantische Versionierung ab 0.1.0

### Fixed (Behoben)

- Audio-Positions-Slider zog beim Abspielen nicht mit: Bei unbekannter  
Stücklänge (Discoverer versagte) war der Slider-Bereich nur 0–1 und der  
Timer konnte ihn nie bewegen; der Bereich wird jetzt aus der echten  
Abspiellänge nachgezogen, und während der Nutzer am Slider zieht,  
schiebt der Timer ihn nicht mehr weg
- GstPbutils.Discoverer-Konstruktor auf neueren PyGObject-Builds ungültig  
(jetzt Discoverer.new mit Fallback) – dadurch erscheinen jetzt  
Titel/Interpret/Album, Stücklänge und Cover bei Audio und Video