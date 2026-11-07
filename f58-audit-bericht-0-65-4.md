# F58 Audit-Bericht — Nemo Previewer

**Stand:** 2026-11-07 · **Auditiert:** 0.65.4 (statische Code-Scans) · **Befund-Fixes:** F70–F73 umgesetzt in **0.65.5** (Deploy-Test offen) · **Dokumentierte Details:** REFERENCE-Abschnitte AUDIT-GTK4 / AUDIT-PERF / AUDIT-MEM / AUDIT-REENTR / AUDIT-A11Y / AUDIT-ENV

## Kurzfazit

Alle geplanten Audits des F58-Pakets sind abgeschlossen. **Kein Code-Fund ist release-blockierend.** Die Architektur zeigt sich in allen sechs Bereichen konsistent und diszipliniert; die zwei Live-Inzidente der 0.65.x-Deploys (Sync-Rescale, Spin-Storm) sind seit 0.65.3 gefixt und werden von den Audits als Referenzfälle bestätigt. Vier kleine Befunde waren als planned-Items **F70–F73** eingeplant (alle Größe **S**) — **alle vier sind in 0.65.5 umgesetzt.**

## Die Audits im Einzelnen

### 1. GTK4-Erstprüfung (F57) — ERLEDIGT 2026-11-06

- **Methode:** Struktur-Check des GTK3-Konsums gegen GTK4-Brecher (Signals, APIs, Theming).
- **Kernaussagen:** GTK3.24-Konsum ist schmal und portierbar; bekannte GTK4-Brecher identifiziert; Empfehlung eines GTK4-Branches erst nach Release 1.0.0.
- **Verdict:** Kein aktueller Handlungsbedarf; Port-Arbeitsschätzung dokumentiert.

### 2. i18n — ERLEDIGT 2026-11-07 (0.65.0/0.65.1)

- **Methode:** Vollständige Markierung aller UI-Strings, gettext-Infrastruktur, Deploy-Test.
- **Kernaussagen:** 227 `_()`-Marker in 6 UI-Modulen, 189 msgids komplett Deutsch übersetzt; de.po wird mitdeployt und beim Start geparst — **kein Kompilieren durch den Endbenutzer**; Sprachwahl automatisch über die System-Sprache, `.mo` nur optionaler Override. Live bestätigt vom Deploy-Test des Nutzers.
- **Verdict:** Wunsch-Anforderung voll erfüllt; kein Folgeschritt nötig (Einstellungs-Dropdown optional möglich).

### 3. Performance — ERLEDIGT 2026-11-07 (AUDIT-PERF-1…9)

- **Methode:** Statischer Hot-Pfad-Scan aller Renderer (große PDFs, Office-Konvertierung, volle Ordner, Live-Resizes).
- **Kernaussagen:** Die 0.65.3-Fixes (generation-gebremste Idle-Schritte für Bild-Rescale, Gleichheits-Guard + 400-ms-Quiet-Timer beim Zeilenabstand) sind die korrekten Muster — beide Live-Inzidente waren exakt Verstöße gegen die Standing Rules. Office-Konvertierung mit Single-Flight, Cache-Hits bei Wiederholungsauswahl. Kein neuer Hot-Pfad-Defekt.
- **Verdict:** Keine Code-Änderung erforderlich; Laufzeit-Messwerte sind Deploy-Seite (NEMO_PREVIEWER_DEBUG=1 liefert Zeitstempel).

### 4. Speicher/Leaks — ERLEDIGT 2026-11-07 (AUDIT-MEM-1…6)

- **Methode:** Inventur der Signal-Wiring-Teardowns, der Großobjekte pro Live-Re-Render, aller Prozess-Lebensdauer-Strukturen und der Timer-vs-Destroy-Rennen.
- **Kernaussagen:** Kein klassisches Leak — Handler sterben mit ihren Widgets, `_clear_content` räumt jede Original-Pixbuf/PDF-Seite/Font-Surface bei jedem Render-Wechsel, Playbin wird pro Panel wiederverwendet, `_office_failed` gedeckelt (256), Debug-Log rotiert (512 KB + 7-Tage-Cleanup).
- **Verdict:** **Befund F70** (Office-Cache unbegrenzt) und **F71** (Timer/Idle können bis 400 ms nach Panel-Zerstörung feuern — Warnungs-Klasse, kein Leak).

### 5. Reentrancy/Threading — ERLEDIGT 2026-11-07 (AUDIT-REENTR-1…5)

- **Methode:** Prüfung der Klick-/Wechsel-Pfade während laufender LibreOffice-Konvertierung plus vollständige Timeout-ID-Inventur.
- **Kernaussagen:** Office-Pipeline ist sauber (Single-Flight, `_destroyed`, Stale-Auswahl-Guard `_path == path`, Auto-Next-Job, `finally: rmtree`); Worker-Threads fassen GTK nie an und liefern per idle mit Path-Checks. Zwei saubene Disziplinen koexistieren: ID-mit-Owner bei Timern, Generationszähler bei Idlern.
- **Verdict:** OK; ein Hardening-Item (geteilt mit F71, Destroy-Guards).

### 6. Barrierefreiheit — ERLEDIGT 2026-11-07 (AUDIT-A11Y-1…4)

- **Methode:** Systematische Inventur des Widget-Bestands nach Klassen (Namen, Tooltips, Zustände, Volltext bei Ellipsierung).
- **Kernaussagen:** Versorgungsseite gut — Texte liegen in Widgets, Tooltips tragen Vollinhalte überall dort, wo die Anzeige kürzt (Info-Tabellen, ICS-Karten, Ordnerzeilen), Einstellungen und Toolbar komplett benannt, Zustände fahren auf Widget-States.
- **Verdict:** **Befund F72**: Die Medien-Leiste (Play/Pause-Knopf nur mit Icon, Seek-Skala) hat weder Tooltips noch zugängliche Namen — ein kleiner, isolierter Fix; Rest versorgt.

### 7. Umgebungs-Matrix — ERLEDIGT 2026-11-07 (AUDIT-ENV-1…5)

- **Methode:** Statische Bestimmung von API-Pins, Sprach-Floor und Windowing-Abhängigkeiten; getestete Zellen aus INSTALL.md.
- **Kernaussagen:** Nemo 3.x-Pin mit defensivem `hasattr`-Guard; Python-Syntax-Floor ~3.5 (keine f-strings), getestet 3.12/3.13 → Empfehlung, **„Python 3.8+"** zu deklarieren; kein X11-API im Code (Crowbar und Geometrie sind Widget-/Monitor-Ebene), Wayland ist kein Code-Blocker.
- **Verdict:** Kein Code-Blocker; **Befund F73** (Doku) plus eine offene Deploy-Matrix-Zelle (Wayland-Session).

## Befunde und Empfehlungen (alle umgesetzt in 0.65.5)

| Item | Befund | Umsetzung in 0.65.5 | Priorität |
| --- | --- | --- | --- |
| **F70** | Office-Cache `~/.cache/previewer` wächst unbegrenzt | Deckel 256 MB (`_OFFICE_CACHE_MAX`), `office_cache_evict()` räumt nach jeder erfolgreichen Konvertierung älteste Dateien zuerst | Mittel — ✅ erledigt |
| **F71** | `_pending_render_id`/`_spacing_render_id` werden bei Panel-Zerstörung nicht gecancelt; Probe-Callbacks prüfen `_destroyed` nicht | Destroy-Handler cancelt beide Timer; `_image_probe_done`/`_media_probe_done` kehren bei `_destroyed` sofort zurück | Niedrig — ✅ erledigt |
| **F72** | Medien-Leiste ohne Tooltips/zugängliche Namen | Zustandsfolgende Tooltips Play/Pause + „Seek position"; drei neue msgids (pot + de.po) | Mittel — ✅ erledigt |
| **F73** | Vage Python-Mindestversions-Angabe | INSTALL deklariert „Python 3.8 or newer" mit Begründung | Niedrig — ✅ erledigt |

## Deploy-seitige Checks (Feldtests am System)

1. `NEMO_PREVIEWER_DEBUG=1 nemo --no-desktop` — Debug-Log mit Zeitstempeln für alle Renderer.
2. **Performance-Zellen:** 1000-Seiten-PDF, 100-MB-DOCX, 40-MP-Foto, voller Ordner.
3. **a11y:** orca (oder AT-SPI-Client) über Bild-, Text- und Audio-Vorschau fahren — alles außer der Medien-Leiste (F72) sollte sinnvoll ansagen.
4. **Umgebungs-Matrix:** eine ältere Nemo-Zelle (z. B. Mint 21.x), eine Wayland-Session (Mint 22 experimentell), Python-Angabe gegen älteste Zieldistro prüfen.
5. Sprachtest: `LANG=de_DE.UTF-8` zeigt deutsche UI; ohne deployte de.po Englisch (bereits bestätigt).

## Fazit: Release-Reife (F51)

Die Audit-Phase liefert ein klares Bild: **der Previewer ist auf dem Weg zu 1.0.0 architektonisch reif.** Die vier Befunde waren kleine, gut umrissene Items (alle S) — **alle vier sind in 0.65.5 umgesetzt** (F70 Cache-Deckel, F71 Destroy-Guards, F72 Player-Tooltips, F73 Python-3.8+-Deklaration). Offen im F58-Paket bleibt nur der **Lizenz-/Abhängigkeits-Audit**, der bewusst in F51 verankert bleibt und dort mit der Release-Verpackung (Debian-Paketlage, Abhängigkeitsdeklarationen) zusammenläuft. Nach dem Deploy-Test von 0.65.5 steht F51 (Release 1.0.0) als nächster Meilenstein.