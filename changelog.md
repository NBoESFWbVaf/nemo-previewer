# Changelog

Alle nennenswerten Änderungen am Nemo-Previewer werden in dieser Datei  
dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),  
Versionierung: [Semantic Versioning](https://semver.org/lang/de/).

## \[Unreleased\]

## \[0.7.0\] – 2026-10-27

### Added (Hinzugefügt)

- Video-Vorschau (F22, Abschluss): Dateien ohne eingebettetes Vor-  
schaubild zeigen jetzt eine generische Kachel wie bei Musik –  
dunkler Petrol-Verlauf, halbtransparentes Abspiel-Dreieck und  
Filmperforation am oberen und unteren Rand, in doppelter Auflösung  
gezeichnet (HiDPI-scharf); fehlt PangoCairo, greift ein  
video-x-generic-Icon-Fallback
- Video-Vorschau (F22, Abschluss): Videos sind im Panel abspielbar –  
der Playbin steckt seinen Bildausgang in ein gtksink-Widget, das  
unter der Kachel erscheint; die Player-Leiste (Play/Pause, Slider,  
Position) ist mit der Musik-Vorschau geteilt. Fehlt gtksink (Paket  
gstreamer1.0-gtk3), läuft die Wiedergabe nur mit Ton, mit Hinweis
- planned.md: Arbeitsdatei mit Schwachstellen-Analyse (Stand 0.4.1) und  
Feature-Vorschlägen inklusive Lösungsskizzen, Aufwandsschätzung und  
empfohlener Abarbeitungs-Reihenfolge
- planned.md: F19–F22 ergänzt (Vorschau-Toolbar am unteren Rand,  
OCR-Knopf bei PDFs, Office→PDF-Knopf, Video-Platzhalterbild und  
Wiedergabe im Panel) inklusive Roadmap-Erweiterung

### Changed (Geändert)

- INSTALL.md: Debian-13-Hinweise ergänzt – es gibt dort kein Paket  
„python-gi“ (die Python-3-Bindings heißen python3-gi und werden von  
nemo-python mitgezogen, das Cinnamon auf Debian nicht vorinstalliert);  
SVG-Paketname auf gir1.2-rsvg-2.0 vereinheitlicht (gültig auf Mint  
und Debian); getestet auf Debian 13 (Trixie)

### Removed (Entfernt)

- Video-Vorschau: die in 0.6.0 eingeführte Standbild-Extraktion aus der  
Videospur (Playbin + videoconvert ! jpegenc ! appsink im Worker-Thread)  
ist wieder entfernt – sie lieferte in der Praxis kein Bild, und der  
Kontakt mit dem im Mint-22-Binding fehlenden Gst.PlayFlags ließ das  
GI-Warm-up (und damit jede Video-Vorschau) mit AttributeError  
abstürzen. Eingebettete Vorschaubilder aus den Tags werden weiterhin  
angezeigt, wenn vorhanden

## \[0.6.0\] – 2026-10-27

### Added (Hinzugefügt)

- Video-Vorschau: Standbilder werden jetzt selbst aus der Videospur  
extrahiert, wenn die Datei kein eingebettetes Vorschaubild im Tag  
trägt – was bei Serien- und Filmdateien fast immer der Fall ist  
(der bisherige Weg über TAG\_PREVIEW\_IMAGE lief daher praktisch nie  
auf ein Ergebnis, sichtbar nach dem Discoverer-Fix in 0.5.0). Ein  
Playbin mit einer videoconvert ! jpegenc ! appsink-Kette wird im  
Erkundungs-Hintergrundthread in den PAUSED-Zustand versetzt; nach  
dem Preroll fließt genau ein JPEG als Bytes zurück und wird im  
GTK-Thread dekodiert – die UI blockiert nicht (max. 8 s Wartezeit,  
dann greift der Hinweis). Voraussetzung: gstreamer1.0-plugins-good  
(jpegenc); Audio wird weggeworfen, nur die Videospur wird dekodiert.  
F22 aus planned.md, Teil 1 (Platzhalter-Kachel und Wiedergabe im  
Panel folgen später)

## \[0.5.1\] – 2026-10-27

### Changed (Geändert)

- Ordner-Vorschau (K1, bewusst als Kompromiss gelöst): Versteckte  
Einträge werden weiterhin mitgezählt, aber jetzt transparent  
ausgewiesen – der Hinweis lautet „Der Ordner enthält X Dateien,  
davon X versteckt" (bei einem Eintrag in der Einzahl; ohne  
versteckte Einträge entfällt der Zusatz, bei leeren bzw. nicht  
lesbaren Ordnern erscheint „Der Ordner ist leer." bzw. „Ordner").  
Vorher verschwieg „Ordner mit X Einträgen", ob versteckte Dateien  
enthalten sind – die Zahl stimmte dann auch nicht mit dem sichtbaren  
Bestand im Dateimanager überein

## \[0.5.0\] – 2026-10-27

### Added (Hinzugefügt)

- Audio-Vorschau: Auch ohne eingebettetes Cover erscheint über den  
Mediaschaltflächen jetzt eine Platzhalter-Kachel – diagonaler  
Farbverlauf (dunkles Blaugrau nach dunklem Violett) mit halb-  
transparentem Notensymbol und abgerundeten Ecken, in Cairo/Pango in  
doppelter Auflösung gezeichnet (HiDPI-scharf); fehlt PangoCairo,  
greift ein Icon-Fallback auf dunklem Grund. Dateien mit und ohne  
Cover zeigen damit ein einheitliches Erscheinungsbild (aus  
planned.md vorgezogen, dort als F18 geführt)

### Fixed (Behoben)

- Audio/Video: Tags, Länge und Cover erschienen nie – auch nicht in  
früheren Versionen. Ursache war ein Binding-Fehler im Quellcode seit  
der ersten Audio-Vorschau: Die synchrone Erkundung heißt im  
Python-Binding discover\_uri() (C-Name gst\_discoverer\_discover\_uri,  
OHNE „\_sync“); ein discover\_uri\_sync existiert nicht, der  
AttributeError wurde still geschluckt. Das neue Platzhalter-Cover  
machte den Altfehler erstmals sichtbar. Die Erkundung ruft jetzt den  
korrekten Namen auf; zusätzlich werden die beteiligten GI-Klassen  
einmalig im GTK-Thread „warmgefahren“ (PyGObject löst Method-  
Tabellen lazy auf) und die Erkundung läuft im Worker als fertig  
aufgelöstes Callable

## \[0.4.3\] – 2026-10-27

### Changed (Geändert) — Robustheits-Paket aus planned.md (R1–R8)

- R1: Die Medien-Erkundung für Audio/Video (GStreamer-Discoverer)  
blockierte den GTK-Main-Loop – bei langsam erreichbaren Medien (USB,  
Netzlaufwerk) fror das Fenster bis zu 10 Sekunden ein. Sie läuft  
jetzt in einem Hintergrund-Thread; das Panel zeigt sofort einen  
„Lese Medien-Informationen"-Hinweis und bleibt bedienbar, das  
Ergebnis schwenkt per Idle zurück in den Main-Loop
- R2: PDF-Vorschau: Seite 1 wird sofort gerendert, die übrigen Seiten  
(bis MAX\_PDF\_PAGES) werden je eine pro Idle-Durchlauf nachgeschoben –  
auch große oder gescannte PDFs stehen augenblicklich im Panel
- R3: Skalier-Designfalle behoben: Die Live-Skalierung mit der  
Panelbreite kannte nur EIN Bild pro Vorschau (Einzel-Slot) – jedes  
weitere skalierte Bild (z.B. Cover plus eingebettete Bilder) hätte  
das erste überschrieben. Die Skalier-Parameter liegen jetzt als  
Python-Daten je Bild in einer Liste; beliebig viele Bilder skalieren mit
- R4: EPUB-Lesedeckel gegen Dekompressions-Bomben: Kapitel-Dokumente  
werden mit 2-MB-Deckel, Cover mit 16-MB-Deckel gelesen – ein  
winziges, riesig entpacktes XHTML im EPUB kann das Panel nicht mehr  
für Sekunden blockieren
- R6: EPUB3-Navigationsdateien (properties="nav") werden beim  
Textsammeln übersprungen – vorher konnte das Inhaltsverzeichnis als  
„Textanfang" angezeigt werden
- R7 (eingeschränkt): MOBI-Datensatzgrenzen werden bereinigt – halb  
zerrissene Mehrbyte-Sequenzen und Trailing-Entry-Reste am Datensatz-  
Rand erzeugten sichtbaren Zeichensalat zwischen Absätzen. Bewusst  
NICHT umgesetzt: die vollständige Rückwärts-Dekodierung der Trailer-  
Größen; ohne Referenzmaterial wäre ein Dekodierfehler schlimmer als  
der kosmetische Fehler (siehe planned.md)
- R5: Der Font-Temp-Ordner (\~/.local/share/nemo-python … Prozess-Temp)  
wuchs unbegrenzt – jede angesehene Schrift wurde bis zum Prozessende  
auf der Platte gehalten. Der Ordner ist jetzt auf 64 Kopien gedeckelt;  
fontconfig behält entfernte Schriften im Speicher, bereits gesehene  
Wasserfälle bleiben korrekt

### Beobachtungspunkt (kein Code-Fix)

- R8: Die Auswahl-Erkennung greift auf interne Nemo-Strukturen zu  
(Klassen-VTable-Offsets). Nach Nemo-Updates das Log prüfen: Melden  
alle vier Module ihre Version und erscheinen „Auswahl geändert …"-Zeilen,  
ist alles gut; die Fallback-Kaskade (VTable → GI → ATK) fängt  
Abweichungen ab. Dauerhaft in planned.md beobachtet

## \[0.4.2\] – 2026-10-27

### Fixed (Behoben) — Bug-Paket aus planned.md (B1–B5)

- B1: Zwei Schriften mit gleichem Dateinamen aus verschiedenen Ordnern  
überschrieben sich gegenseitig bei der Fontconfig-Übernahme – der  
Zielname enthält jetzt einen Hash des Quellpfads, der Wasserfall  
zeigt immer die angewählte Datei
- B2: Der Audio-Player kannte sein Trackende nicht (kein Bus-Watch):  
nach dem Ende blieb das Pause-Icon stehen und die Position fror ein;  
jetzt springt die Anzeige auf 0:00 zurück, und Abspielfehler  
erscheinen als Hinweis im Panel statt unsichtbar zu bleiben
- B3: Der Positionstimer lief ewig weiter (auch nach Fensterabbau) und  
wurde nie aufgeräumt – er läuft jetzt nur während der Wiedergabe und  
wird beim Wechseln, Stoppen und Abbauen sauber entfernt
- B4: War der Office-Cache unbeschreibbar (Disk voll, \~/.cache  
read-only), konvertierte LibreOffice bei jeder Auswahl erneut – das  
Dokument wird nun als gescheitert vermerkt und die fertige PDF wird  
direkt aus dem Temp-Ordner angezeigt (nicht weggeworfen)
- B5: MOBI-Dateien wurden vollständig in den Speicher gelesen – eine  
500-MB-AZW3 konnte Nemo einfrieren; es wird nur der Kopf bis 8 MB  
gelesen, die Text-Datensätze stehen ohnehin am Dateianfang

## \[0.4.1\] – 2026-10-27

### Fixed (Behoben)

- Schrift-Wasserfall zeigte die Ersatzschrift statt der eigentlichen  
Familie: GTKs Standard-Pango-FontMap wird beim Start gebaut und  
überliest Schriften, die später über Fontconfig hinzugefügt werden.  
Der Wasserfall wird jetzt mit einem eigenen, frischen FontMap in  
eine Pixbuf vorgerendert (Textfarbe aus dem Theme, doppelt  
vorgerendert und mit der Panelbreite live herunterskaliert).

### Changed (Geändert)

- Größte Wasserfall-Größe von 48 pt auf 36 pt reduziert

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