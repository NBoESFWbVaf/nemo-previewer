# Changelog

Alle nennenswerten Änderungen am Nemo-Previewer werden in dieser Datei  
dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),  
Versionierung: [Semantic Versioning](https://semver.org/lang/de/).

## \[Unreleased\]

## \[0.22.0\] – 2026-10-30

### Added (Hinzugefügt)

- Vorschau-Umschalter in Nemos Werkzeugleiste (F40, Nutzer-Wunsch):  
Neben der Ansichtenauswahl sitzt ein Knopf, der die Vorschau-  
Seitenleiste ein- und ausblendet – bei CSD in der Titelleiste,  
klassisch als Umschalter direkt hinter den Ansichts-Knöpfen der  
Nemo-Toolbar; das Icon ist builder-view-right-pane-symbolic (Icon-  
Helfer mit Theme-Fallbacks), und der Zustand bleibt mit Strg+Alt+P  
synchron
- Alte MS-Office-Formate in der Vorschau (F39, Nutzer-Wunsch):  
Binäre .doc-, .xls- und .ppt-Dateien sowie RTF-Dateien laufen über  
die LibreOffice-Hintergrund-Konvertierung wie die OOXML-Formate  
scharf ins PDF; da sie keine ZIP-Archive sind, gibt es keine  
eingebettete Miniaturansicht – die Übergangsansicht zeigt Hinweise  
zu Konvertierung, fehlendem LibreOffice oder gescheiterter  
Konvertierung
- „Location“ und benutzerdefinierte Felder in der Bild-Info-Tabelle  
(F38, Nutzer-Wunsch): Falls vorhanden, zeigt die Tabelle die XMP-  
„Location“ (IPTC Core, direkt nach dem Aufnahmeort) sowie beliebige  
XMP-Felder aus nicht-standardisierten Namensräumen („Präfix:Name“)  
– geparst mit Python-Bordmitteln im Worker-Thread, maximal zehn  
Zusatzzeilen, jede nur mit vorhandenem Wert

### Changed (Geändert)

- Bild-Vorschau in 60/40-Aufteilung (F38, Nutzer-Wunsch): Die Spalte  
teilt sich in einen 60-%-Bereich für das Bild (vertikal und horizon-  
tahl mittig, über die volle Spaltenbreite) und einen 40-%-Bereich  
für die Bildinformationen; die EXIF-/Maß-Tabelle (F36) läuft dort  
hinein, die Aufteilung bleibt beim Fenster-Resize über einen Live-  
Nachzug erhalten. SVG-Vorschauen nutzen dieselbe Aufteilung, ihre  
Maß-Zeile steht im Info-Bereich
- Neues Symbol für den Öffnen-Knopf (F40, Nutzer-Wunsch): Das Öffnen  
der Datei in der Standardanwendung trägt jetzt das Stift-Symbol  
(document-edit), nicht mehr das Dokument-Öffnen-Symbol; fehlt es  
im Icon-Theme, greift der bisherige Name als Fallback

### Removed (Entfernt)

- Ausblenden-Knopf in der Panel-Kopfzeile (F40, Nutzer-Wunsch): Der  
Schalter ist als Vorschau-Umschalter in Nemos Titelleiste aufge-  
wacht (siehe Hinzugefügt) – Strg+Alt+P funktioniert unverändert

### Fixed (Behoben)

- Kaputte Office-Dateien zeigen ein Icon (K2): Statt einer nackten  
Hinweiszeile sitzt die generische Icon-Ansicht als visueller Anker  
über der Fehlermeldung  
- SVG-Vorschau über die Cairo-Route (K3): Intrinsisch kleine SVGs  
füllen jetzt die Panelbreite (DPI-Rendern, Vektor bleibt scharf),  
und der Aufruf nutzt die aktuelle librsvg-API statt des deprecated  
get\_pixbuf(); ohne pycairo oder mit altem librsvg greift der  
bisherige Pfad als Fallback

## \[0.21.0\] – 2026-10-30

### Added (Hinzugefügt)

- Foto-Info-Tabelle mit EXIF-Daten (F36, Nutzer-Wunsch): Unter Bild-  
Vorschauen steht eine Tabelle mit Höhe, Breite, Aufnahmedatum, Aufnahme-  
ort (GPS in Dezimalgrad), Kameramodell, Belichtungszeit, Brennweite  
mit 35-mm-Äquivalent, Blende und ISO-Wert – jede Zeile nur, wenn der  
Wert vorhanden ist; Höhe/Breite folgen der EXIF-Drehung. Der EXIF-  
Parser läuft mit Python-Bordmitteln im Worker-Thread (keine neue  
Abhängigkeit); herstellerspezifische Unterschiede fangen Standard-  
Fallbacks ab: Belichtungszeit/Blende notfalls aus den APEX-Werten,  
Datum als Kaskade Original → Digitalisiert → Datei, Kameramodell ohne  
Hersteller-Dopplung. Das bisherige Maße-Label ist in der Tabelle  
aufgegangen

## \[0.20.0\] – 2026-10-29

### Added (Hinzugefügt)

- Genre in der Musik-Vorschau (F35, Nutzer-Wunsch): Der Discoverer liest  
das Genre-Tag mit; die Zeile erscheint nur, wenn das Tag vorhanden ist

### Changed (Geändert)

- Cover-Schatten neu ausgerichtet (F35, Nutzer-Wunsch): Der Schlags-  
schatten der Cover sitzt jetzt rechts und unten, reicht dort 3 px  
weiter und ist insgesamt transparenter (4 % Deckkraft je Stufe  
statt 5,5 %)
- Musik-Infos umgestellt (F35, Nutzer-Wunsch): Das Jahr steht nicht mehr  
in der Album-Zeile, sondern als eigene Zeile darunter – Bezeichnung  
„Zuerst erschienen“
- Doppelpunkte (F35, Nutzer-Wunsch): Alle Bezeichnungen der Info-  
Tabellen (Musik, Video, EML, E-Book, Schrift) enden auf einen  
Doppelpunkt – zentral im Tabellen-Helfer gesetzt
- Kopfzeile ausgedünnt (F35, Nutzer-Wunsch): Icon, Dateiname, Typ, Größe  
und Änderungsdatum sind aus dem Kopfbereich der Vorschau-Spalte  
entfernt – all das zeigt die Nemo-Liste bereits. Übrig bleiben die  
Öffnen- und Ausblenden-Knöpfe; der Hinweis „(Datei nicht gefunden)“  
steht jetzt im Inhaltsbereich

## \[0.19.0\] – 2026-10-29

### Added (Hinzugefügt)

- Cover-Rahmen in der Musik-Vorschau (F34, Nutzer-Wunsch): Eingebettete  
Cover bekommen dieselben abgerundeten Ecken wie die Platzhalter-  
Kachel (56/640 der Kantenlänge – die Rundung skaliert mit der Anzeige  
mit), und jeder Cover – eingebettet wie Platzhalter – trägt einen  
kleinen Schlagschatten. Der Schatten entsteht gestapelt in Cairo aus  
sechs halbtransparenten Kacheln, ohne Blur-Filter; ohne PangoCairo  
bleibt das Cover ungerahmt. Video-Kacheln und Bild-Vorschauen sind  
unberührt

## \[0.18.0\] – 2026-10-29

### Added (Hinzugefügt)

- Erweiterte Musik-Informationen (F33, Nutzer-Wunsch): Die Audio-  
Vorschau ermittelt jetzt Titel, Interpret, Länge, Titelnummer  
(„x von y“), Album mit Jahr, Albuminterpret, CD-Nummer („x von y“)  
und Codec und zeigt jede Zeile nur bei Verfügbarkeit. Beim Jahr hat  
die Originalveröffentlichung Vorrang (original-date), sonst wird das  
Datums-Tag als Jahr gelesen. Besonderheiten der Tag-Formate werden  
defensiv abgefangen: ID3 (MP3) und MP4 melden Titel-/CD-Nummern als  
Zahlenpaar, Vorbis-Kommentare (FLAC, Ogg) teils als String „n/m“ –  
beides wird verstanden; der Codec kommt aus dem Audio-Codec-Tag,  
notfalls aus dem Container-Format

### Changed (Geändert)

- Audio-Vorschau umgeordnet: Die Abspielleiste (Play/Pause, Slider,  
Position) sitzt mit etwas Abstand UNTER dem Cover, die Informationen  
folgen darunter. Die bisherige Datei-Zeile entfällt – der Dateiname  
steht im Nemo ohnehin nebenan

## \[0.17.0\] – 2026-10-29

### Changed (Geändert)

- Bild-Vorschau mit Höhenkappe (F32, Bauabschnitt 1, Nutzer-  
Wunsch): Bild-Vorschauen – Rasterbilder wie SVG – füllen  
höchstens noch 60 % der Spaltenhöhe. Die Anzeige-Höhe koppelt  
live an die aktuelle Spaltenhöhe: Beim Fenster-Resize zieht die  
Live-Skalierung die Kappe nach (neues Höhen-Tracking im  
size-allocate plus \_preview\_height). Das Bild wird nicht mehr  
expandiert gepackt; der Container hält über keep\_height exakt  
die (gekappelte) Bildhöhe. Direkt unter dem Bild sitzt ein  
horizontaler Trenner mit 8 px Abstand oben und unten – der  
Bereich darunter ist für zusätzliche Informationen zum Bild  
reserviert und bleibt vorerst leer; das bestehende Maße-Label  
(„W × H px") steht nun unter dem Trenner. Eingebettete Bilder  
(Audio-Cover, Office-Miniaturansicht, Video-Frame) und alle  
übrigen Vorschauen sind unberührt. Umgesetzt im Medien-Renderer  
mit dem neuen Pack-Helfer \_pack\_image\_capped; die Erweiterung  
\_scaled\_image um frac\_h sitzt im Panel-Kern und steht damit  
allen Renderern offen

## \[0.16.3\] – 2026-10-29

### Changed (Geändert)

- F24-Optik (Nutzer-Wunsch „zur besseren Unterscheidbarkeit“): Die  
Zeilennummern erscheinen jetzt etwas dunkler und kleiner. Die  
Deckkraft steigt von 60 % auf 75 % der Theme-Textfarbe – auf  
hellem Grund waren die Nummern zu verwaschen –, und die Nummern-  
schchrift skaliert auf 80 % der Textschriftgröße (mit Floor auf  
1 pt, damit winzige Größenangaben nicht auf 0 rutschen). Die  
gleiche verkleinerte Probe misst die Randbreite, sodass Rand  
und Nummern-Schrift zusammenpassen; Kopier-Verhalten und alle  
übrigen F24-Eigenschaften (Randzeichnung außerhalb des Buffers,  
nur sichtbare Zeilen, Live-Toggle) bleiben unverändert

## \[0.16.2\] – 2026-10-28

### Fixed (Behoben)

- F24-Feld-Fix 2, erster Befund (Testfeld 0.16.1): Der Platz für  
die Zeilennummern war da, die Nummern blieben aber unsichtbar.  
„draw“ ist ein RUN\_LAST-Signal – der per connect() angemeldete  
Handler lief VOR der TextView-Standardzeichnung, die danach den  
Hintergrund füllt und die Randzeichnung übermalt. Der Handler  
wird jetzt per connect\_after() angemeldet und zeichnet ÜBER der  
Standardzeichnung (klassische Overlay-Ordnung)
- F24-Feld-Fix 2, zweiter Befund: Deaktivierte Zeilennummern in  
den Einstellungen wirkten sofort (der Text rückte vor), das  
erneute Aktivieren tat aber nichts. Der Merker \_last\_textish  
speicherte den linenumbers-Schalter statt „aktuelle Vorschau  
ist TextView-basiert“ – nach dem Deaktivieren stand er auf  
False, sodass der Toggle beim Re-Aktivieren nicht neu renderte.  
Der Merker markiert jetzt TextView-basierte Vorschauen generell;  
der Toggle wirkt damit live in beide Richtungen. Teure Renderer  
(PDF, Office, Audio, Video, Bild, Ordner) bleiben wie bisher  
unberührt
- Härtung: Scheitert die Zeilennummern-Zeichnung ausnahmsweise  
(künftige Nemo-/GTK-Änderungen), meldet der draw-Handler den  
Fehler jetzt einmalig per dbg statt still – draw feuert oft,  
ein Closure-Flag verhindert Log-Spam

## \[0.16.1\] – 2026-10-28

### Fixed (Behoben)

- F24-Feld-Fix (Testfeld 0.16.0): Der Zeilennummern-Rand riss beim  
ersten Anklicken einer Textdatei mit AttributeError ab – die  
GI-Bindung von Pango.Layout bietet get\_pixel\_width() nicht an.  
Die Randbreiten-Messung nutzt jetzt get\_pixel\_size(); der Fallback  
auf die generische Kachel hatte den Absturz abgefangen, die Text-  
Vorschau selbst blieb aber leer. Mit dem Fix erscheinen die  
Zeilennummern wie in 0.16.0 vorgesehen

## \[0.16.0\] – 2026-10-28

### Added (Hinzugefügt)

- Zeilennummern in der reinen Text-Vorschau (F24, Nutzer-Wunsch):  
Textdateien und endungslose Textdateien zeigen ihre Zeilen-  
nummern am linken Rand. Die Nummern sind eine Randzeichnung  
AUSSERHALB des Textbuffers – Auswahl und Kopie (Strg+C)  
erfassen ausschließlich den Text selbst, die Nummern werden  
nie mitkopiert. Umgebrochene Zeilen behalten ihre Nummer an  
der ersten visuellen Zeile; gezeichnet werden nur die  
sichtbaren Zeilen
- Neue Rubrik „Textdateien“ im Einstellungsfenster: CheckButton  
„Zeilennummern anzeigen (nicht kopierbar)“ – standardmäßig  
aktiviert, sofort gespeichert (Schlüssel text\_line\_numbers in  
der conf) und live auf die aktuell angezeigte Text-Vorschau  
angewendet. Nur reine Textvorschauen werden beim Umschalten  
neu aufgebaut; Markdown, E-Mail, E-Book und Font-Wasserfall  
bleiben ohne Nummern und unberührt
- Bewusst ohne GtkSourceView umgesetzt (kein neues Paket): Die  
Nummern entstehen im draw-Handler des bestehenden TextView

## \[0.15.0\] – 2026-10-28

### Changed (Geändert)

- Struktur-Release (F28/F29/F31): Die Extension besteht aus acht  
Modulen – der Panel-Kern (previewer\_panel.py) bleibt das Herz,  
aber die Renderer für Medien (previewer\_render\_media.py),  
Dokumente (previewer\_render\_docs.py) und Text  
(previewer\_render\_text.py) sind als Mixin-Klassen ausgelagert,  
ebenso die Toolbar samt Einstellungsfenster  
(previewer\_toolbar.py). Zwei gemeinsame Basis-Helfer  
(\_pixbuf\_from\_bytes, \_zf\_read\_capped) leben jetzt in  
previewer\_util.py, wo sie allen Renderern zur Verfügung stehen
- Der Einstieg (previewer.py) prüft beim Laden jetzt alle acht  
Module auf identische PREVIEWER\_VERSION – liegt im Extension-  
Ordner noch eine alte Fassung, warnt das Terminal sofort
- F29: Die Toolbar ist – wie vom Nutzer angefragt als „sinnvoll  
erachtet: umgesetzt“ – ein eigenes Mixin-Modul; die ActionBar,  
das Einstellungsfenster (F12) und das Tastenkürzel Strg+Alt+P  
verhalten sich unverändert
- F28: Lange Kommentar- und Historienblöcke sind aus dem Code in  
die neue REFERENZ.md ausgelagert; der Code trägt an ihrer Stelle  
Marker der Form `# → REF PAN-R9-1` (Modul-Kürzel + Thema +  
Nummer). REFERENZ.md ist ein lebendes Projektdokument im  
Repository und wird bewusst NICHT mitdeployt – das Deployment  
kopiert nur die \*.py-Dateien
- Verhalten unverändert: Es gibt keine neuen Features und keinen  
Bugfix – alle Renderer, Deckel (0.9.2), Thread-Disziplinen  
(R1/B7) und Einstellungen (F12) wirken exakt wie in 0.14.1

## \[0.14.1\] – 2026-10-28

### Fixed (Behoben)

- Markdown-Tabellen waren so breit wie ihre längste Zelle und  
zerfielen dann im TextView in wilden Umbruch (Feldtest 0.14.0  
mit der Reihenfolge-Tabelle der planned.md): Tabellen halten  
jetzt ein Gesamtbudget in Anzeigespalten – ausgelegt auf das  
300-px-Standardpanel –, schmale Spalten behalten ihre volle  
Breite, und überlange Zellen brechen mehrzeilig INNERHALB  
ihrer Spalte um, wie im Browser. Die Spalten bleiben bündig,  
Kopfzeile und graue Trennzeile laufen über alle Zeilen der  
logischen Tabellenzeile. Zellen-Markup, das über einen  
Zell-Umbruch hinwegläuft, wird bewusst nicht zusammengefügt –  
gültiges Markup geht vor, der Rohtext-Fallback darf nie  
wegen einer Tabelle greifen
- Emoji-Breite: 🔴 ✅ ☑ und ähnliche Symbole belegen im TextView  
zwei Anzeigespalten – die Breitenmessung der Tabellen zählt sie  
jetzt doppelt (und den Variation-Selector FE0F gar nicht),  
sonst standen Emoji-Zellen sichtbar daneben
- Backslash-Escapes nach CommonMark (\[ wird zu \[) – 0.14.0  
zeigte sie als Rohtext an, z.B. bei Überschriften wie
  $$
  0.14.0
  $$
- Maskierte Balken in Tabellen: `\|` ist in GFM ein literaler  
Balken und kein Spaltentrenner

## \[0.14.0\] – 2026-10-28

### Changed (Geändert)

- Markdown-Vorschau deutlich browserähnlicher (K4): Der Konverter  
deckt jetzt die verbreiteten Markdown-Varianten (GitHub Flavored)  
ab, statt nur den Standard-Kern. Neu sind GFM-Tabellen (Kopfzeile  
fett, graue Trennzeile mit Box-Zeichen, Spalten bündig im  
Monospace-Satz, Rechtsausrichtung bei `---:`), Task-Listen  
(`[x]`/`[ ]` werden zu ☑/☐, erledigte Punkte erscheinen  
durchgestrichen wie im Browser), sortierte Listen (1./1)),  
eingerückte und verschachtelte Listen mit Ebenen-Zeichen  
(•/◦/▪), Setext-Überschriften (`===`/`---` unter der Zeile),  
fett+kursiv (`***…***`), `~~Durchstreichen~~`, mehrfach  
verschachtelte Zitate (`> >`), Autolinks in spitzen Klammern,  
Trennlinien auch mit Leerzeichen (`- - -`) sowie Links mit  
runden Klammern in der URL (brachen bisher die Regex).  
Überschriften der Ebenen 1 und 2 bekommen einen Unterstrich  
(nähert den farbigen Balken der Browser-Darstellung an), und  
Überschriften, Linien und Tabellen erhalten Luft nach oben –  
Dokumente wie planned.md oder changelog.md erscheinen damit so  
aufgebaut wie im Browser. Bewusst unverändert: kein Webview,  
keine neuen Paket-Abhängigkeiten; breite Tabellen brechen im  
Panel um, statt horizontal zu scrollen; 4-Spaces-Codeblöcke  
bleiben unberücksichtigt (kollidiert mit Listeneinrückungen).  
Die bestehende Sicherheitslinie bleibt: Ungültiges Markup führt  
zur dbg-Meldung und zur Anzeige des Rohtexts

## \[0.13.0\] – 2026-10-28

### Added (Hinzugefügt)

- Einstellung „Standardbreite beim Start" (F12, Teil 2): Unter  
„Allgemein" im Einstellungsfenster kann die Breite eingestellt  
werden, mit der die Vorschauspalte nach dem Start von Nemo  
geöffnet wird. Der SpinButton trägt den AKTUELLEN Wert vorab  
(mindestens 260 px, dem kleinsten erlaubten Wert), daneben nennt  
eine dezente Zeile den Standard (300 px) und kennzeichnet den  
Ist-Zustand als „aktuell". Zieht der Nutzer die Vorschauspalte am  
Trenner, wird die gewählte Breite automatisch zur künftigen  
Startbreite: Sie landet – entprellt, erst wenn der Trenner  
stillsteht – in der Konfigurationsdatei und beim nächsten Start  
genau so angewendet. Änderungen im Einstellungsfenster greifen  
sofort: Das Panel zieht live auf die neue Breite, ohne dass  
gespeichert oder neu gestartet werden muss. Ist das  
Einstellungsfenster offen, während am Trenner gezogen wird,  
zieht der SpinButton mit (außer der Nutzer tippt dort gerade)

### Changed (Geändert)

- Standard-Startbreite des Panels von 340 px auf 300 px geändert  
(Nutzer-Wunsch); ohne Konfigurationsdatei gilt jetzt 300 px

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