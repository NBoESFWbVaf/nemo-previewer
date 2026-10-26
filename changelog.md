# Changelog

Alle nennenswerten Änderungen am Nemo-Previewer werden in dieser Datei  
dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),  
Versionierung: [Semantic Versioning](https://semver.org/lang/de/).

## \[Unreleased\]

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