# Changelog

Alle nennenswerten Änderungen am Nemo-Previewer werden in dieser Datei  
dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),  
Versionierung: [Semantic Versioning](https://semver.org/lang/de/).

## \[Unreleased\]

## \[0.12.1\] – 2026-10-28

### Fixed (Behoben)

- Einstellungen wurden nicht gespeichert (B8, gemeldet aus dem  
Testfeld): 0.12.0 griff für die Konfigurationsdatei auf Gio.Keyfile  
zu – PyGObject bindet GKeyFile aber als GLib.KeyFile (GKeyFile ist  
eine GLib-Klasse, keine Gio-Klasse). Der Fehler wurde von den  
Defensiv-Blöcken gefangen („Konfiguration nicht speicherbar" im  
Terminal-Log), das Einstellungsfenster blieb benutzbar, nur die  
Persistenz war wirkungslos. Jetzt läuft die Datei über GLib.KeyFile  
mit Kompatibilitäts-Auflösung für den alten Alias GLib.Keyfile  
(gleiches Muster wie beim Discoverer in der Medien-Vorschau);  
fehlt die Klasse im Binding, meldet das Panel das per dbg und  
bleibt auf den Defaults, statt still zu scheitern

## \[0.12.0\] – 2026-10-28

### Added (Hinzugefügt)

- Einstellungsfenster (F12, Teil 1): Der Zahnrad-Knopf der Toolbar  
öffnet jetzt das Konfigurationsfenster „Nemo-Previewer –  
Einstellungen" – hier sammeln sich künftig ALLE Einstellungen der  
Vorschauspalte. Erste funktionierende Einstellung: „Vorschauspalte  
beim Start anzeigen" (abgehakt bleibt die Spalte nach dem Start von  
Nemo zunächst unsichtbar; Strg+Alt+P blendet sie jederzeit wieder  
ein). Jede Änderung wird sofort in  
\~/.config/nemo-previewer/nemo-previewer.conf gespeichert (GLib-  
natives INI-Format via Gio.Keyfile, keine neue Abhängigkeit,  
Verzeichnis wird bei Bedarf angelegt) und bei jedem Start von Nemo  
angewendet – der Einstieg wendet die Konfiguration erst NACH dem  
Einblenden des Panels an, sonst würde eine verlangte Unsichtbarkeit  
sofort wieder überschrieben. Kaputte oder halb geschriebene  
Konfigurationen fallen still auf die Defaults zurück und hindern  
Nemo nie am Start. Wiederholter Zahnrad-Klick holt das bestehende  
Fenster nach vorn statt ein zweites zu öffnen

### Changed (Geändert)

- Vorschau-Toolbar \~5 px schmaler (Nutzer-Wunsch): Der Innenabstand  
oben/unten der ActionBar liegt mit 3+4 px unter dem Adwaita-  
Standard von 6+6 px; kann ein Theme die Regel nicht umsetzen,  
bleibt es ohne Fehler beim Theme-Standard

## \[0.11.0\] – 2026-10-28

### Added (Hinzugefügt)

- Vorschau-Toolbar (F19, Teil 1): Am unteren Rand der Vorschauspalte  
läuft jetzt eine statische Toolbar (Gtk.ActionBar) mit eigener  
Trennlinie über dem Inhaltsbereich – immer sichtbar, solange das  
Panel aktiv ist (Nutzer-Entscheid: kein Ein-/Ausblenden je  
Renderer; die Renderer-Aktionen F13/F20/F21/F24–F27 melden sich  
später hier an). Rechts außen sitzt ein fester Einstellungs-Knopf  
mit Zahnrad aus den Systemicons (preferences-system-symbolic,  
Tooltip „Einstellungen"); im ersten Bauabschnitt bewusst ohne  
Funktion – die Konfiguration (F12) dockt dort an, bis dahin  
quittiert der Knopf Klicks nur im Terminal-Log

## \[0.10.4\] – 2026-10-28

### Fixed (Behoben)

- Bild-Vorschau erschien auch nach dem R9-Fix 0.10.3 weiterhin nicht  
(B7, zweiter Teil): Die im Idle-Callback gepackten Bild-Widgets  
liegen zeitlich NACH dem show\_all() des Render-Durchlaufs und  
wurden daher nie sichtbar – GTK3 zeigt ungezeigte Widgets nicht an.  
Die R1-Medien-Vorschau trägt deshalb am Ende von \_media\_probe\_done  
ein explizites eigenes show\_all (mit Kommentar); im R9-Bild-Umbau  
von 0.10.2 war genau dieses übersehen worden. Jetzt zeigt der  
Bild-Callback sein Ergebnis an beiden Exit-Pfaden (Vorschau UND  
Fehler-Fallback) mit eigenem show\_all. Der „Lade Bild"-Zettel,  
der bisher ewig stehen blieb, wird damit erstmals wirklich abgelöst.  
Neu sind außerdem dbg-Diagnosezeilen, damit der Terminal-Log den  
Bild-Weg jetzt nachvollziehbar zeigt: „Bild gelesen … (Bytes)",  
„Bild dekodiert … (Maße)" und „Bild-Ergebnis verworfen, Auswahl  
wechselte …" bei schnellem Weiterklicken

## \[0.10.3\] – 2026-10-28

### Fixed (Behoben)

- R9-Regression aus 0.10.2 (B7): Im Feldtest erschienen gar keine  
Bild-Vorschauen mehr. Ursache: 0.10.2 dekodierte die Bilder im  
Hintergrund-Thread und erzeugte damit Gdk-Objekte (PixbufLoader)  
außerhalb des GTK-Threads – gegen das bewährte R1-Muster der  
Medien-Vorschau („keine Gdk-Objekte im Worker"); der Worker  
scheiterte still, ohne Traceback oder Fehlerhinweis, und der  
„Lade Bild"-Zettel blieb stehen. Jetzt liest der Hintergrund-  
Thread nur noch die Datei (reines Python-I/O), Dekodierung,  
EXIF-Drehung und Skalierung laufen zurück im GTK-Thread –  
dieselbe Disziplin wie bei den Medien-Covern. Der unnötige  
GI-Warm-up für die Bild-Dekodierung (er erzeugte einen  
PixbufLoader, den niemand schloss – Quelle der GdkPixbuf-Warnung  
„finalized without calling gdk\_pixbuf\_loader\_close()" im  
Terminal-Log) entfiel komplett. Alle Beschleunigungs-Hebel aus  
0.10.2 bleiben: „Lade Bild"-Hinweis sofort, Decode-Deckel  
max(2 × Panelbreite, 1024), Originalmaße im Info-Label,  
Stale-Verwurf bei schnellem Weiterklicken

## \[0.10.2\] – 2026-10-27

### Changed (Geändert)

- Bild-Vorschau beschleunigt (R9 aus planned.md): Große Bilder  
(typisch 20-MB-JPEGs mit 50–100 Megapixeln) blockierten bisher die  
komplette UI, weil Lesen, Dekodieren und EXIF-Drehung synchron im  
GTK-Main-Loop liefen. Zweistufig wie bei der Medien-Vorschau:  
Sofort erscheint ein „Lade Bild"-Hinweis, die Dekodierung läuft in  
einem Hintergrund-Thread, und die fertige Pixbuf wird per Idle-  
Callback ins Panel gereicht (bei weitergewanderter Auswahl still  
verworfen). Zusätzlich dekodiert der size-prepared-Deckel statt  
stur auf 4096 px auf max(2 × Panelbreite, 1024) – die Dekodierung  
wird damit um ein Vielfaches billiger, die Live-Skalierung beim  
Trenner-Ziehen verliert nichts. Das Info-Label zeigt jetzt die  
ORIGINALMAßE aus dem Datei-Kopf statt der gedeckelten Dekodier-  
größe. Der Bomben-Schutz aus 0.9.2 bleibt vollständig erhalten;  
schlägt der Thread-Weg ausnahmsweise fehl, greift der bisherige  
synchrone Pfad als Rettungsanker

## \[0.10.1\] – 2026-10-27

### Fixed (Behoben)

- Markdown-Vorschau (B6): Der Textkörper wurde mit hartcodierter  
Standardschrift in 9 pt override\_font-überschrieben und erschien  
damit kleiner als die übrige Oberfläche – die Text-Vorschau  
(Monospace) wirkt dagegen wie die System-Schriftgröße. Die  
Markdown-Vorschau überschreibt die Schrift jetzt gar nicht mehr  
und nutzt die System-Schrift des GTK-Themes (also die  
Schriftgröße des Systems); Überschriften skalieren mit, da ihre  
Größenangaben relativ zur Basis-Schrift sind. EML- und E-Book-  
Vorschau bleiben vorerst bei 9 pt

## \[0.10.0\] – 2026-10-27

### Added (Hinzugefügt)

- Text-Vorschau für endungslose Dateien (F23 aus planned.md): Frei  
benannte Dateien (z.B. notes, todo, Dotfiles wie .bashrc) landeten  
über den MIME-Typ-Rater auf application/octet-stream und zeigten  
nur Icon und Datei-Infos. Dateien ohne Endung werden jetzt per  
Inhalts-Sniffing geprüft: Die ersten 4 KB dürfen keine NULL-Bytes  
und höchstens 5 % Steuerzeichen enthalten – nur dann zeigt der  
Dispatcher die normale Text-Vorschau. Endungslose Binärdateien  
(Executables, Core-Dumps) bleiben bei der generischen Ansicht;  
die üblichen Kappeln der Text-Vorschau (256 KB / 2000 Zeilen)  
greifen unverändert

## \[0.9.2\] – 2026-10-27

Härtungs-Paket aus dem zweiten Sicherheitsaudit (Schwerpunkt  
Pufferüberlauf/OOM): Klassische Überläufe sind auf Python-Ebene  
ausgeschlossen; ein präpariertes Bild, PDF, EPUB, DOCX oder EML konnte  
aber Nemo über Riesen-Allokationen abschießen. Keine neuen Funktionen,  
normale Dateien verhalten sich unverändert.

### Fixed (Behoben)

- Bild-Vorschau: GdkPixbuf dekodierte die VOLLE Auflösung, bevor die  
Deckelung griff – ein PNG, das nur im Header 30000×30000 deklariert,  
allozierte \~3,6 GB (OOM-Absturz). `_pixbuf_from_bytes` nutzt jetzt  
den size-prepared-Deckel (Verkleinerung zur Dekodierzeit) und ist  
jetzt auch die Primärroute der Bild-Vorschau (Rohdaten-Deckel  
64 MB, Fallback `new_from_file_at_scale`)
- PDF-Vorschau: Die untere Scale-Klammer (0.2) erzwang bei  
pathologisch riesigen Seiten (\~100000 pt) Rendern in  
20000×20000 px ≈ 1,6 GB je Seite – jetzt greift zusätzlich ein  
Pixel-Budget (4096²) je Seite, das nur im Extremfall  
flächentreu zurückrechnet
- EML-Vorschau: Der Parser las die GESAMTE Datei – mehr-GB-.eml  
fraßen Nemos Speicher; es werden jetzt die ersten 2 MB gelesen  
(Kopfzeilen stehen ohnehin oben)
- EPUB-Vorschau: `META-INF/container.xml` und die OPF-Datei wurden  
ungekappt gelesen (Dekompressionsbomben-Lücke neben den bestehenden  
R4-Deckeln für Kapitel und Cover) – beide jetzt über  
`_zf_read_capped`
- Office-Vorschau: Eingebettete Miniaturansicht (16-MB-Deckel) und  
content.xml/word/document.xml (2-MB-Deckel) werden nicht mehr  
ungekappt gelesen; Medien-Cover aus Tags mit 32-MB-Byte-Deckel

### Changed (Geändert)

- Auswahl-Erkennung (previewer\_select.py): Wildcall-Schutz – die per  
berechnetem VTable-Offset gelesenen Funktionszeiger (peek\_selection,  
get\_name, get\_uri) werden vor dem Aufruf gegen die ausführbaren  
Adressbereiche der Nemo-Bibliotheken geprüft (`/proc/self/maps`);  
ein Nemo-Update mit verschobenem Klassenlayout führt so zu einer  
sauber abgeschalteten Route statt zu einem Wildcall, der Nemo  
beenden würde

## \[0.9.1\] – 2026-10-27

Sicherheits- und Redundanz-Audit über alle vier Module; keine neuen  
Funktionen, Verhalten der Vorschauen unverändert.

### Fixed (Behoben)

- Crowbar-Race im Einstieg (previewer.py): Eine überholte  
Location-Widget-Crowbar konnte nach einem Ordnerwechsel noch platziert  
werden und den aktuellen Ordnerpfad mit dem alten Pfad überschreiben;  
der Pfad wird jetzt ausschließlich synchron in `get_widget` gesetzt
- Poll-Timer-Leck im Einstieg (previewer.py): Der 500-ms-Sicherheits-  
Timer lief nach dem Schließen des Nemo-Fensters als Zombie weiter;  
er wird jetzt am Fenster-„destroy"-Signal abgeräumt
- Office-Konvertierung nach Panel-Abbau (previewer\_panel.py): Der  
child-watch auf die LibreOffice-Konvertierung konnte noch auf das  
bereits abgebaute Panel treffen; das Ergebnis wird jetzt verworfen  
und nur der Temp-Ordner aufgeräumt

### Changed (Geändert)

- Redundanz-Aufräumung (previewer\_panel.py, Verhalten unverändert): Der  
TextView-Bau (zuvor fünf Mal identisch: Text, Markdown, EML-Körper,  
E-Book, Office-Textauszug), das gekappte Textdatei-Lesen (Text +  
Markdown) und die Info-Tabelle (zuvor inline in EML-Kopf, Audio und  
Video neben `_meta_grid`) nutzen jetzt die gemeinsamen Helfer  
`_text_view`, `_read_text_file` und `_meta_grid`
- Redundanz-Aufräumung (previewer\_select.py, Verhalten unverändert):  
VTable-Schleife und TreeView-Fallback lesen den Dateinamen jetzt über  
den gemeinsamen Helfer `_iface_file_name`; der Basename aus einer  
URI über `_name_from_uri` (zuvor jeweils mehrfach identisch  
implementiert)
- Modul-Kopf des Einstiegs aktualisiert: Video zeigt seit 0.7.0/0.8.0  
eine Kachel mit Öffnen-Knopf (nicht mehr „Erstframe als Standbild")  
und Poppler rendert alle Seiten scrollbar (nicht mehr „die erste  
Seite scharf")

## \[0.9.0\] – 2026-10-27

### Added (Hinzugefügt)

- PDF-Vorschau: Seitenanzeige „Seite X/Y" über dem scrollbaren  
Bereich (F14 aus planned.md) – beim Scrollen zählt sie auf die  
Seite nach, deren Unterkante den oberen Rand des Sichtfensters  
überschreitet, also die Seite, über der man gerade steht.  
Einseitige PDFs zeigen keine Anzeige; bei mehrseitigen PDFs mit  
mehr als MAX\_PDF\_PAGES Seiten bleibt zusätzlich der bestehende  
Hinweis „Erste X von Y Seiten"

### Changed (Geändert)

- PDF-Vorschau: Der Hinweis „N Seiten – Vorschau nach unten scrollen."  
ist entfallen – die neue Seitenanzeige vermittelt die Zahl inzwischen  
selbst

## \[0.8.0\] – 2026-10-27

### Removed (Entfernt)

- Video-Wiedergabe im Panel (0.7.0–0.7.2): vollständig zurückgebaut.  
Im Testfeld ließ sich das Bild nicht stabil in die Vorschauspalte  
binden – ohne das Paket gstreamer1.0-gtk3 fehlt gtksink (der Playbin  
öffnete dann sein eigenes Fenster), und der Appsink-Eigenbau zeigte  
trotz Fenster- und Neuzeichnen-Fixes (0.7.1, 0.7.2) im Feld kein  
Bild. Die Video-Vorschau zeigt wie gehabt die generische Kachel  
(Petrol-Verlauf, Abspiel-Dreieck, Filmperforation) samt Datei-  
Informationen; abgespielt wird über den Öffnen-Knopf im Medien-  
programm der Wahl. Die Player-Leiste bleibt exklusiv für Musik,  
die zentralen Bausteine (\_playbin\_set\_uri/\_player\_bar) bleiben für  
einen späteren Neuversuch erhalten

## \[0.7.2\] – 2026-10-27

### Fixed (Behoben)

- Video-Vorschau (Eigenbau-Ausgabe): Ton lief, aber das Bild blieb bei  
der Platzhalter-Kachel – die DrawingArea wurde nach ihrem ersten  
(leeren) Zeichnen nie wieder zum Neuzeichnen angestoßen. Der  
Frame-Timer ruft jetzt nach jedem gezogenen Bild explizit das  
Neuzeichnen (queue\_draw) auf

## \[0.7.1\] – 2026-10-27

### Fixed (Behoben)

- Video-Vorschau: Das Bild der Wiedergabe erschien in einem EIGENEN  
Fenster statt in der Vorschauspalte, wenn gtksink fehlt (Paket  
gstreamer1.0-gtk3) – der Playbin fällt in dem Fall auf seinen  
Standard-Videosink zurück, der eigenständig ein Fenster öffnet. Die  
Video-Ausgabe ist jetzt dreistufig: gtksink, wenn installiert; sonst  
eine eigene DrawingArea, die über einen appsink (videoconvert,  
Roh-Frames in RGBA, ca. 30 Bilder/s) die Frames selbst in die  
Vorschauspalte zeichnet – ohne Zusatzpaket, auf X11 wie auf Wayland;  
erst wenn beides nicht möglich ist, läuft die Wiedergabe nur mit  
Ton (fakesink). Ein separates Fenster öffnet sich nie wieder

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