# Changelog

All notable changes to the Nemo Previewer are documented in this file. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [Semantic Versioning](https://semver.org/).

## \[Unreleased\]

## \[0.65.6\] – 2026-11-07

### Fixed

- Deploy feedback (Linux Mint 22.3): the reset-width button showed no icon – the fallback name arrow-right is not part of the preinstalled Mint-Y icon theme, and pick\_icon returned that name unchecked. The button's icon chain gains the standard navigation icons go-next-symbolic/go-next, and pick\_icon now verifies its fallback too – if the theme lacks that name as well, GTK's built-in image-missing is returned instead, so no button is ever left blank.

## \[0.65.5\] – 2026-11-07

### Fixed

- Audit finding F71: the debounced render timer (F2) and the line-spacing quiet timer (0.65.4) were not cancelled when the panel was destroyed – the one-shot callbacks could fire into the dead widget tree for up to 400 ms and produce GTK warnings on stderr. The destroy handler now cancels both timers, and the worker deliveries (image/media probe) test \_destroyed before packing anything.
- Audit finding F72: the media player bar was the only area of the widget inventory without tooltips – the icon-only play/pause button and the seek slider read as two nameless controls to screen-reader users. Both carry tooltips now; the play button tooltip follows the state (Play/Pause). Three new msgids in po/nemo-previewer.pot and po/de.po (German: Wiedergeben, Pausieren, Wiedergabeposition).

### Changed

- Audit finding F70: the LibreOffice conversion cache (\~/.cache/previewer) grew without limit – every distinct office document left a permanent PDF. The cache is now capped at 256 MB in total: after every successful conversion office\_cache\_evict() removes the oldest cache files first.
- Audit finding F73: the installation guide now declares Python 3.8 or newer as the minimum (the syntax floor is lower; every distribution that ships Nemo 3.x already carries a newer Python).

## \[0.65.4\] – 2026-11-07

### Fixed

- ICS event cards stood at odds: the label column (Start/End/Location/Description) had only a minimum width, so cards with fewer rows – e.g. without a description – shifted their table. One size group per file now gives every card the same label column; the widest label wins.

## \[0.65.3\] – 2026-11-07

### Fixed

- Image previews fell behind when the panel width changed fast (divider drag, the reset arrow): all registered images were rescaled synchronously on every resize event. The rescale now runs generation-guarded in idle steps like the PDF path – a newer resize cancels older passes instead of queueing scale calls.
- The line spacing setting froze the UI and could crash the settings window: every spin tick wrote the config file and fully re-rendered the text preview. The value now lands in memory at once; config write and re-render happen once, after the spin goes quiet (400 ms).

## \[0.65.2\] – 2026-11-07

### Fixed

- Startup crash: the provider description in previewer.py (\_get\_name\_and\_desc) lost its concatenation operator when the string was marked for translation in 0.65.0 – Python raised a SyntaxError and Nemo never loaded the extension. The list is built with explicit + again.

## \[0.65.1\] – 2026-11-07

### Changed

- Translations without compiling: po/de.po ships with the deployment (copied to nemo-previewer-modules/po/) and is parsed automatically at startup – the language follows the system locale via GLib.get_language_names(), so a German desktop shows the German UI out of the box. A compiled .mo in locale/<lang>/LC_MESSAGES is now an optional override; without po/de.po the UI stays English.

## \[0.65.0\] – 2026-11-07

### Added

- Translations: GNU gettext infrastructure – all user-visible strings (labels, tooltips, hints, window and dialog titles, buttons) are marked for translation; without a compiled catalog the UI stays English.
- German translation: po/nemo-previewer.pot (template) and po/de.po with all 189 msgids; compiled with msgfmt into locale/de/LC_MESSAGES (see INSTALL.md "Translations").

### Changed

- Pre-i18n German leftovers became English msgids: the vCard TEL fallback "Telefon" is now "Phone" (with "Telefon" as its German translation), the EPUB guard exception "DOCTYPE im OPF" is now "DOCTYPE in the OPF (R10 entity guard)".

## \[0.64.0\] – 2026-11-07

### Changed

- EML attachments: each row gets a checkbox before the name and the button extracts only the checked attachments ("Extract selected attachments"; without a selection it shows a hint instead of the folder chooser).
- EML attachments: the list keeps at most five rows visible; longer lists scroll inside the attachment box.

## \[0.63.0\] – 2026-11-07

### Changed

- Multi-selection (K6) no longer previews the first selected file: the preview column only shows the number of selected items ("N items selected"); a single selection previews as usual.

## \[0.62.1\] – 2026-11-06

### Fixed

- The two font size spins (F69, 0.62.0) started at 0: one step up to 1 made the preview jump from the system default size to 1 px, which looked like a bug. Both spins now start pre-filled with the detected system font size (`\_system\_font\_size\_px`, measured from a fresh TextView, points converted at 96 dpi); 0 stays selectable as the explicit "theme default".

## \[0.62.0\] – 2026-11-06

### Added

- Two font size settings (F69): "Preview font size" scales the text previews (plain text, Markdown, source code) and "Info table font size" scales the metadata tables in the preview and in the "more" windows (EXIF/audio/video tags, packages) – both as px spins in the settings, 0 keeps the theme's normal size. Applied via CSS classes (`\_apply\_font\_size\_css`), so a change restyles open previews and windows live, without re-rendering.

## \[0.61.0\] – 2026-11-06

### Added

- Parser selftest without Nemo (F1): `python3 previewer\_panel.py --selftest` builds four synthetic fixtures in a temp dir (Markdown, EPUB, MOBI, TrueType) and checks them against the parsers – one PASS/FAIL line per test, a summary line and exit code 0/1. Regression base for md/epub/mobi/font changes.

### Fixed

- `\_mobi\_records` read the PalmDB record offsets as three bytes instead of four: on real MOBI files record 0 started at offset >> 8, so the MOBI header and with it the EXTH author were never parsed – MOBI previews showed the title (it comes from the PalmDB name field) but never an author. The first selftest fixture exposed this.

## \[0.60.1\] – 2026-11-06

### Fixed

- PDF and office previews lagged while dragging the preview column back to a smaller size: every page re-scaled synchronously on each width change, starving the main loop, and the still-too-wide pages wobbled in the viewport. Page 1 now scales synchronously and the remaining pages follow in idle packets (`_pdf_scale_step`, K12).

## \[0.60.0\] – 2026-11-05

### Changed

- ICS events render as vCard-style cards with frame and drop shadow (`_vcard_card_draw` reused); event details appear as a title/value table with the title column pinned to 75 px via the new `title_width` parameter of `pack_meta_grid`.

## \[0.59.2\] – 2026-11-05

### Fixed

- K11 (nachgelegt) – the dashed undershoot lines are REALLY gone now: the first attempt (0.59.1) put the CSS provider on the panel's own style context, but a provider there never reaches the scrolled windows' contexts – the rule simply never applied. The provider now goes to the screen (add\_provider\_for\_screen), and the rule is scoped to the previewer panel by widget name: `#previewer-panel undershoot, #previewer-panel .undershoot { background-image: none; background-color: transparent; }`. It is installed once per process; Nemo's own windows keep the theme look.

## \[0.59.1\] – 2026-11-05

### Fixed

- K11 – no more dashed undershoot lines at the edges of scrollable previews (user finding): GTK adds undershoot hint nodes at every edge where content can still be scrolled into view, and the active theme paints them as dashed lines – at the start only below, in the middle above and below, at the end only above. A CSS rule on the panel (background-image: none / background-color: transparent for undershoot.top/right/bottom/left) hides them preview-wide; Nemo itself and the extension's separate windows keep the theme look.

## \[0.59.0\] – 2026-11-05

### Added

- F11 – WOFF1 fonts (.woff) in the font preview: the zlib-compressed tables are unpacked and rebuilt into a plain sfnt (pure byte work, no web toolkit), parked in the font temp dir and registered with Fontconfig for this process – the waterfall shows the real family. WOFF2 (.woff2, Brotli-compressed) is deliberately not supported; it gets a clear hint instead of a preview.
- F11 – TTC collections show EVERY font: each face of the collection gets its own bold header (family – style) and its own waterfall, re-wrapping live on column resize like the single fonts (F68); capped at 8 faces with a remainder hint. Before, a .ttc only showed the first face. The panel dispatch routes .woff to the font renderer, and the sample-text setting applies to it as well.

## \[0.58.3\] – 2026-11-05

### Fixed

- F68 – font waterfall re-renders LIVE while the column divider is dragged (user bug report): the sample text re-wraps at the new width immediately and the point sizes on screen stay constant. Before, the surface was rendered once at the width the preview had when the font was selected and only scaled afterwards – dragging the column wider grew the font faces while the line wrap kept the old width until the font was re-selected. The panel's size-allocate handler now calls \_apply\_font\_scale (like the PDF pages), which rebuilds the waterfall via the new helper \_font\_waterfall\_pixbuf.

## \[0.58.2\] – 2026-11-05

### Changed

- F54 – e-mail headers restyled (user request): the labels are bold, the values italic, and the subject row sits BELOW the date row (order: from, to, Cc, date, subject). The central table helper pack_meta_grid grew the optional bold_keys/italic_values parameters for that – the other info tables keep their dim look.
- F54 – mails WITHOUT a readable text body now render like a mail with text: the body area is always built (empty if need be), the "No readable text body found" hint is gone.
- F54 – the attachment list is a two-column table now (user request): column 1 the file name (ellipsized in the middle, tooltip with the full name), column 2 the human-readable size (dim, END-aligned; "unknown" if undecodable) – icon and content type are deliberately not shown anymore.

## \[0.58.1\] – 2026-11-05

### Fixed

- F54 – no more "File trimmed" on large e-mails: the whole .eml is parsed (user request: a big mail stays big) – the attachment list is complete, the sizes are exact, and the extraction reads the whole file as well. The 0.9.2 EML read cap is gone.
- F54 – the attachment list now sits directly above the toolbar in EVERY mail (packed from the bottom of the preview) – HTML-only mails no longer push the list to the top of the preview.

## \[0.58.0\] – 2026-11-05

### Added

- F52 – ICS calendar files (.ics) as an event list: every VEVENT becomes its own card with a bold summary and Start/End/Location/Description rows, stacked scrollable below each other with a 50-event cap and a remainder hint. The parser unfolds RFC 5545 continuation lines and formats DATE and DATE-TIME values readably (all-day events show the date only; times appear exactly as stored, no timezone conversion).
- F54 – EML attachments: the e-mail preview lists every attachment with name, size and type and offers an "Extract all attachments" button. It opens a folder chooser and writes the files with conflict-free names (existing files get a numbered suffix); the extraction re-reads the file with a 64 MB budget, and oversized files produce a warning that the last attachment may be incomplete.

## \[0.57.0\] – 2026-11-05

### Changed

- K5 – lazy GStreamer initialization: Gst.init and the GStreamer import no longer run when the extension loads at Nemo start – they run on the FIRST audio/video preview and are cached afterwards. Nemo starts measurably faster on systems with GStreamer installed, and sessions that never preview media never touch GStreamer at all. The audio/video preview branches behave exactly as before, including the install hint when gir1.2-gst-plugins-base-1.0 is missing.

## \[0.56.1\] – 2026-11-05

### Fixed

- F2 – deploy fix: \_is\_heavy crashed with "TypeError: can only concatenate tuple (not set) to tuple" on EVERY selection, leaving the preview dead – \_OFFICE\_EXTS is a set (built for the "in" lookups of the render switch) and cannot be concatenated with a tuple. The set is now wrapped with tuple() before the endswith concatenation. Lesson recorded: check the type of imported constants before concatenating them.

## \[0.56.0\] – 2026-11-05

### Added

- F2 – render debounce for heavy previews: PDF, Office, audio and video files no longer start their render on every selection change. The render waits 400 ms of selection quiet, and every new selection restarts that window – fast browsing through the file list therefore never fires renders whose result is thrown away immediately (full PDF parses, LibreOffice conversions, GStreamer pipelines). Light formats (text, images, folders …) keep their immediate preview, and the panel keeps the previous preview visible during the short quiet window.

## \[0.55.1\] – 2026-11-05

### Fixed

- F24 – the line numbers sat slightly too high: they are drawn in 80 % of the text font size but were placed at the top edge of the line box, so the smaller glyphs were offset upward against the text. Every number is now centered vertically on the text area of its line. With F25 line spacing active the centering accounts for the extra space (get\_line\_yrange counts the pixels-above space at the top of the line box) – the numbers stay centered on the text, not on the enlarged box, at every spacing value.

## \[0.55.0\] – 2026-11-05

### Added

- F25 – line spacing for text previews: the settings "Text files" frame gains a "Line spacing (px)" spin (0–12, step 1). The value is saved immediately and applied live to the current text preview – no restart, no re-open needed. Technically a GtkTextTag (pixels-above-lines) applied over the whole buffer via build\_text\_view's new spacing parameter; the clipboard stays untouched. 0 keeps the normal line height. Unlike the line numbers the spacing applies to ALL TextView previews (plain text, Markdown, e-mail, e-book, font), because \_text\_view passes the config value centrally.

## \[0.54.1\] – 2026-11-05

### Fixed

- F65 – debug output was written to stdout even with the toggle off: "debug logging" now gates ALL debug output. With the toggle and NEMO\_PREVIEWER\_DEBUG off, dbg writes NOTHING – neither the log file nor the terminal; the terminal deploy test therefore runs as NEMO\_PREVIEWER\_DEBUG=1 nemo. The entry point's version-mismatch warning stays visible in every mode (plain print, not dbg).
- F65 – the recording dot did not appear in the header: \_update\_rec\_dot now uses show()/hide() instead of set\_visible, and the icon is resolved via pick\_icon with the media-record fallback so the dot renders even in themes without media-record-symbolic.

## \[0.54.0\] – 2026-11-05

### Fixed

- F65 – the debug logging toggle could not switch logging OFF during the session: the flag OR-ed in its own old state, so once on it stayed on until the next Nemo start. set\_debug\_log now recomputes live from the env var and the toggle – OFF stops the file logging immediately; only NEMO\_PREVIEWER\_DEBUG=1 still overrides the toggle.

### Added

- F65 – red recording dot in the preview header: visible exactly while debug logging is active (standard media-record-symbolic icon, recolored red via CSS), switches live with the toggle in both directions. With the env var set it stays visible even when the toggle goes OFF – logging is still on then.
- F65 – log retention: previewer.log and previewer.log.old are deleted at every panel start once their mtime is older than 7 days (DEBUG\_LOG\_MAX\_AGE) – logs never linger on disk forever, even with logging off afterwards.

## \[0.53.0\] – 2026-11-05

### Added

- F65 – debug logging as a setting: a new "Debug logging (write log file)" toggle in the settings "General" frame (config key debug\_log). When on, every dbg line is mirrored into ~/.local/state/nemo-previewer/previewer.log (XDG\_STATE\_HOME honored) with a timestamp and a per-session version header; the file rotates at 512 KB, keeping exactly one .old backup. The environment variable NEMO\_PREVIEWER\_DEBUG=1 always wins over the toggle – a power-user one-shot without touching the settings. dbg keeps writing to stdout in every mode, so terminal deploy tests stay identical.

## \[0.52.4\] – 2026-11-04

### Removed

- Dead code (cleanup round, behavior unchanged): the unused constant MAX\_EBOOK\_CHARS in previewer\_util.py (leftover from the e-book cap rework – the e-book renderers cap via MAX\_TEXT\_LINES/MAX\_TEXT\_BYTES); the unused import PANEL\_MIN\_WIDTH in the entry module previewer.py (the constant itself stays – panel and toolbar use it); the unused Gdk import in previewer\_panel.py including its gi.require\_version line.

## \[0.52.3\] – 2026-11-04

### Fixed

- F63 – the reset-width button jumped back to the hardcoded default width (350 px) instead of the width configured in the settings. \_panel\_width holds exactly that configured value (set by the settings spin button and the config load; dragging never updates it), so the handler now restores the live width to \_panel\_width without overwriting it – no config write, and the tooltip now reads "Reset preview column to configured width".

## \[0.52.2\] – 2026-11-04

### Changed

- F63 – icon fallback chain (user hint): sidebar-collapse-right is not part of the standard icon themes. The chain now runs sidebar-collapse-right-symbolic → arrow-right-symbolic (nearest equivalent, keeps the symbolic icon discipline) → arrow-right as the absolute last resort.

## \[0.52.1\] – 2026-11-04

### Fixed

- F63 – the reset-width button did nothing: the no-op guard compared \_panel\_width, which dragging the divider has not updated since 0.41.0 – so the guard always saw the default and returned. It now measures the live column width (window width minus divider position) and logs the jump via dbg.

### Changed

- F63 – icon (user wish): sidebar-collapse-right-symbolic instead of zoom-fit-best-symbolic; fallback sidebar-collapse-right, then zoom-fit-best-symbolic.

## \[0.52.0\] – 2026-11-04

### Added

- F63 – Header: new button right next to "Open with the default application" that resets the preview column to the default width (350 px) with a single click – saved to the config (persists across restarts) and applied live. Symbolic system icon via pick\_icon: zoom-fit-best-symbolic, fallback view-restore-symbolic, then edit-undo-symbolic; tooltip "Reset preview column to default width".

## \[0.51.3\] – 2026-11-04

### Changed

- F50/F61/F62 – "more" window follows the selection (user wishes): the window is kept above the file window (set\_transient\_for – it can no longer sink behind Nemo); while it is open, selecting another media file refreshes it automatically, without clicking "more" again. Manual clicks still focus the window, the automatic refresh never steals focus. Non-media selections leave the window as it is.

## \[0.51.2\] – 2026-11-04

### Changed

- F50/F61/F62 – One "more" window only (user wish): while the tag window is open, a "more" click on another file updates it (new title, cleared store, "collecting" placeholder, brought to the front) instead of opening a second window. A generation counter discards results of outdated workers, so fast clicking never mixes rows of two files; after closing the window, the next click builds a fresh one.

## \[0.51.1\] – 2026-11-04

### Changed

- F50/F61/F62 – Tag table design (user wishes): subtle vertical separator between the tag and value columns as well (grid lines BOTH); tag names bold (weight 700 = PANGO\_WEIGHT\_BOLD), values italic (style 2 = PANGO\_STYLE\_ITALIC) – both via renderer properties, no extra Pango import. Applies to all three media "more" windows.

## \[0.51.0\] – 2026-11-04

### Added

- F62 – Video preview: "more" button below the info table opens the shared tag table window with ALL tags of the video file. exiftool delivers the raw tag set per container – QuickTime/MP4 atoms, Matroska, AVI RIFF, WebM – so the tags differ between formats by design, like with photos (F50) and music (F61).

### Changed

- F50/F61/F62 – The window-and-worker twins \_on\_exif\_more/\_on\_id3\_more became one-line delegates; the shared logic lives in the generic \_on\_tags\_more handler now (photo, audio and video differ only in their window title).

## \[0.50.2\] – 2026-11-03

### Fixed

- F61/F50 – Media "more" windows crashed on open: the PyGObject build on the deploy system does not map Gtk.TreeView.set\_enable\_grid\_lines (AttributeError). The grid lines go through set\_property("enable-grid-lines") now; if the property is missing too, set\_rules\_hint(True) adds subtle alternating row banding instead – every step dbg-logged.

## \[0.50.1\] – 2026-11-03

### Changed

- F61/F50 – Media "more" windows: both windows share one two-column tag table now (helpers \_tags\_table\_window and \_exiftool\_tag\_rows). The EXIF window of the photo preview renders tabular too – the monospace TextView variant is gone; unified 500-row cap (was 2000 lines). Design (user wishes): subtle horizontal grid lines, 10px inner padding, colons after the tag names; a "collecting" placeholder row shows until the worker delivers.

## \[0.50.0\] – 2026-11-03

### Added

- F61 – Audio preview: "more" button below the info table opens a window with ALL tags of the music file in tabular form (two-column Gtk.TreeView: tag/value; value cells wrap, columns resizable). exiftool delivers the raw tag set per format – ID3 (MP3), Vorbis comments (FLAC/OGG), QuickTime atoms (M4A), RIFF INFO (WAV) – so the tags differ between file formats by design. Without exiftool the preview shows an install hint (Debian package libimage-exiftool-perl) instead of the button.

## \[0.49.1\] – 2026-11-03

### Fixed

- Window rule: the windows came out full-height – set\_default\_size was overridden by the content's natural size. center\_window now reads the height from the primary monitor's geometry (current resolution, minus 40 %; fallback: monitor 0) and enforces it after mapping via GLib.idle\_add + resize (one-shot); the detected monitor resolution is dbg-logged.

## \[0.49.0\] – 2026-11-03

### Added

- Window rule (user request 2026-11-03): all opening windows of the extension appear centered on the screen and carry ~60 % of the screen height as their height – central helper center\_window(win, width) in previewer\_util.py (height = int(0.6 × Gdk.Screen height), Gtk.WindowPosition.CENTER, defensive try/except); REFERENCE.md gains the UT-DOC-15 entry.

### Changed

- Settings window and EXIF "more" window use the helper (420 / 560 wide) instead of their fixed default sizes.

## \[0.48.3\] – 2026-11-02

### Changed

- F50 – EXIF details window: 10px inner padding via the TextView left/right/top/bottom margins – the scrollbar stays flush at the window edge (padding, not margins).

## \[0.48.2\] – 2026-11-02

### Fixed

- F50 – exiftool window: replace the GLib spawn with a worker thread and subprocess.Popen (ARGV list, no shell; stderr merged in; buffer fed via GLib.idle_add) – PyGObject's spawn_async_with_pipes return tuple varies by version (first a ValueError on unpack, then EBADF from indexed fd fields).

### Changed

- F50 – The "more" button sits 10px down and 10px right of the table edge (margins).

## \[0.48.1\] – 2026-11-02

### Fixed

- F50 – The "more" button keeps its button frame (NORMAL relief) – before, it looked like plain text until hover.
- F50 – exiftool spawn: index the spawn result (res[0]..res[3]) instead of a 4-value unpack – PyGObject tuples vary in size and the unpack raised "too many values to unpack (expected 4)".

## \[0.48.0\] – 2026-11-02

### Added

- F50 – Photo preview: "more" button in the 40% info area opens a window with ALL EXIF details via exiftool, raw but formatted (monospace read-only view, capped at 2000 lines); without exiftool the info area shows an install hint (Debian package libimage-exiftool-perl) instead of the button.

### Changed

- F50 – Photo info table ends at ISO: the XMP custom fields leave the table (Location stays); all details live in the "more" window now.

## \[0.47.0\] – 2026-11-02

### Changed

- F49 – All files in English: every remaining German UI string, exception, dbg message and comment translated across all eight modules; the German identifier farbe/\_surface\_css\_farbe in previewer\_panel.py became color/\_surface\_css\_color, and the EXIF dict keys in previewer\_render\_media.py were renamed producer and consumer side (Camera, Date taken, Exposure time, Aperture, Focal length, Coordinates, Dimensions); planned.md stays German deliberately (user decision 2026-11-02).
- F49 – All 250 function and class docstrings migrated from the code into REFERENZ.md (English translations): each def/class now carries a `# → REF <MODULE>-DOC-n` marker above it, only the module head docstrings stay in the code (version anchors). New entries: ENT-DOC-1…20, UT-DOC-1…14, TB-DOC-1…15, DOC-DOC-1…19, SEL-DOC-1…26, TXT-DOC-1…86, PAN-DOC-1…30 and MED-DOC-1…40 – REFERENZ.md grows from 144 to 300 entries.

### Added

- previewer\_render\_text.py: \_render\_sqlite now logs the table count on success (dbg "%d tables") – previously only the error path had a message.

## \[0.46.0\] – 2026-11-02

### Added

- F8 – CSV as a real table (Gtk.TreeView): the module detects the delimiter AND the header row itself (user requirement – the column/cell separator is never guessed from the file name); csv.Sniffer tries comma, semicolon, TAB and pipe against the first lines; 4-MB read cap, 1000-row preview, columns sortable by click and resizable.
- F6 – SQLite databases (.db/.sqlite): table list with columns and row counts; the structure comes from the schema (sqlite_master, PRAGMA table\_info), opened guaranteed read-only (PRAGMA query\_only); a magic check sends foreign .db files to the open hint; a progress cap stops endless COUNT scans (F60 lesson) – such counters show "…".

## \[0.45.1\] – 2026-11-02

### Fixed

- F60.1 – Package preview sharpened (user test of 0.45.0): (1) invalid header on some .deb – the compression used to be guessed from the ar member NAME; depending on the tool, those names carry IEEE slashes ('control.tar.gz/'), and zst names escaped the switch entirely. \_tar\_sniff\_mode now sniffs the magic bytes (gzip/xz/zstd) of the member itself, and ar names are stripped of trailing slashes. (2) Large packages took long to appear because the icon hunt ran before the info table and decompressed up to 48 MB of payload – the budget now sits at 8 MB: the preview arrives within fractions of a second, the icon stays best effort (huge payloads show the placeholder).

## \[0.45.0\] – 2026-11-02

### Added

- F60 – Package preview (DEB, RPM, Arch): package files get their own preview – 40 % icon on top, 60 % info table below, scrollable, because package info (description, dependencies) easily outgrows the area. All with built-ins: .deb is read as an ar archive (control file from control.tar.gz/xz), .rpm via struct (lead, signature and main header at the start of the file), Arch packages (.pkg.tar.xz, AUR builds) via .PKGINFO in the tarball. Only set fields are shown: package name, version, architecture, section/group, short and long description or summary, installed size, dependencies (RPM without rpmlib/config/rtld internals), recommends or optional dependencies, license, maintainer, homepage. The icon on top comes best effort from the payload (first matching app icon, 48 MB decompression budget), otherwise a drawn package placeholder shows the format signet (DEB/RPM/PKG). pack\_meta\_grid packs values multi-line since F60 (wrap=True) instead of ellipsize. Limits (built-ins): zstd is off limits – control.tar.zst and .pkg.tar.zst as well as the RPM cpio payload stay out; the preview then shows the open hint or the placeholder. PKGBUILD/.SRCINFO are text files and run through the text preview.
## \[0.44.0\] – 2026-11-02

### Changed

- F59 – E-book preview rebuilt (user request): The preview column splits like images into 60 % top / 40 % bottom. The top shows only the embedded cover (EPUB from the manifest, FB2 from the base64 binary); without a cover \_ebook\_placeholder draws a portrait image (book cover skeleton, theme-neutral like the vCard placeholder). Below sits the info table as for image files – only rows with set tags: book title, author, part of a series (EPUB: calibre:series or EPUB3 belongs-to-collection with group-position; FB2: sequence with number), page count (only if the OPF carries a page-count meta – not a standard tag), e-book format, language. The text preview is gone: it rendered poorly, the book info is fully sufficient. Side effect: without text extraction HUFF/CDIC no longer blocks – title and author now show for AZW files too (the preview shows the placeholder cover; MOBI covers sit as a REC entry and are addressed differently).

## \[0.43.0\] – 2026-11-02

### Fixed

- R10 – XML entity guard (security audit): \_xml\_dtd\_rejected in previewer\_util checks the first 64 KB for DOCTYPE/ENTITY declarations before any xml.etree parsing and rejects them – a "Billion Laughs" document can no longer freeze the preview or blow up memory. Protected: EPUB-OPF, FB2, .contact (previewer\_render\_text.py) and Office XML (previewer\_render\_ docs.py); EPUB container.xml is read via regex and was never affected; defusedxml deliberately not pulled in (built-ins).
- R11 – FB2 read cap (security audit): \_fb2\_data reads at most \_FB2\_FILE\_CAP (8 MB) instead of ElementTree.parse(path) (whole file) and parses from the buffer – like EML/vCard, every format now has a cap; truncated giant files run into the open hint instead of memory pressure.

## \[0.42.2\] – 2026-11-02

### Fixed

- B10 – Reliable text-file detection (user finding): The sniffer now decides as the last instance before the generic preview based on CONTENT – readable files with extensions whose guessed MIME was neither text/\* nor "opaque" (.pub, .crt, .csr, .pref …) now see the text preview instead of just an icon; \_OPAQUE\_TYPES is gone, known binary types (zip, gzip, x-tar, x-7z, x-rar, x-executable, x-sharedlib …) sit in the blacklist \_SNIFF\_BINARY\_MIMES; \_sniff\_is\_text gained the UTF-8 decoding probe as a second criterion (8-bit density without valid UTF-8 ≥ 30 % → binary); each sniffer hit logs a dbg line with the guessed MIME.

## \[0.42.1\] – 2026-11-01

### Fixed

- SyntaxWarning on loading previewer\_render\_text.py removed: The docstring of \_md\_split\_cells named the backslash-masked table bar as an escape sequence in plain text; the note is now spelled out.
- Log flood of the selection diagnostics tamed (user decision): The ATK probes of the fallback chain (collect, \_read\_atk\_ states, \_read\_atk\_focused in previewer\_select.py; rec in previewer.py) are silent (pass) again as up to 0.41.0. Nemo 6 does not provide the ATK selection API on ScrolledWindowAccessible – the exceptions are expected and repeated on every selection-changed. All other suppressed messages from 0.42.0 remain.

## \[0.42.0\] – 2026-11-01

### Changed

- Spaghetti audit round 2 (refactoring, behavior unchanged): The four remaining god functions are decomposed – folder preview (\_render\_folder into icon, row and scroll helpers), e-book trio (EPUB/FB2/MOBI one parse helper each), EXIF formatting (one helper per topic block) and the markdown tables (cell/row/width helpers). The cross-mixin helpers pack\_hint, pack\_meta\_grid, cover\_round\_path, build\_scaled\_image and build\_text\_view now live in previewer\_util instead of the panel mixin. Silent pass swallowers in except blocks now log the suppressed exception via dbg() – broken files give themselves away in the log instead of staying silent.

## \[0.41.0\] – 2026-11-01

### Changed

- Column width (user request, release polish): The default width of the preview column is now 350 px instead of 300 px. Dragging the divider now applies to the running session only and no longer changes the start width – the value entered in the settings dialog is the only authority, applied at every start. The "default/current" hint line next to the width field is gone.

## \[0.40.0\] – 2026-11-01

### Changed

- Spaghetti audit round 1 (user assignment "check the entire code for spaghetti code"): God functions decomposed – the settings dialog builds from four section helpers (general, text files, documents, fonts) instead of one 171-line function, \_render\_office\_thumb reads package data and the no-ZIP hint via two helpers with early returns instead of 13 nesting levels, and \_apply\_scale scales through the new per-image helper \_scale\_item (depth 12 → 5). The F46 diagnostics machinery is removed (\_dbg\_pixels with pixel probes and panel scan, \_dbg\_list\_margins, GdkWindow flag in the folder log line) – F46 has been solved since 0.31.11; the functional background painters, the CSS rule and the folder icons diagnostics line remain. Behavior unchanged.

## \[0.39.0\] – 2026-11-01

### Changed

- Tightening round (user request "tighten the code without breaking functions"): Dead code removed – the Nemo C selection API (dlopen of libnemo-private, doomed on Nemo 6 because it is statically linked) including the GI cascade (route 2), four unused functions (\_read\_size, find\_paned\_above, find\_slot\_box, content\_type\_description) and repeated blank lines; ATK guard and office error note consolidated into shared helpers, the remaining diag() lines translated to English (K8 done). 321 lines saved – behavior unchanged: the class vtable remains the primary selection source.

## \[0.38.1\] – 2026-11-01

### Fixed

- Light mode edge on the left fixed (F46 XI, user finding): Two color bugs in previewer\_panel.py – the fallback derivation in \_paint\_background was inverted (light foreground produced a light instead of a dark base and vice versa – in light mode the fallback painted almost black), and the CSS fallback in \_apply\_surface\_css was hardcoded to rgb(56,56,56); both derivations are now contrast-correct and FG-derived.

## \[0.38.0\] – 2026-11-01

### Changed

- Debug log in English (user request): All debug output (dbg lines) of the eight Python files is translated to English and slightly shortened – technical terms, version and F markers as well as the TRACE prefixes remain; docstrings and UI texts untouched.

## \[0.37.0\] – 2026-11-01

### Changed

- Comment cleanup (user request): All # comments of the eight Python files are trimmed to the essentials (at most two lines per block) and translated to English – function and bug markers (F numbers), version notes and REF references remain; docstrings and module headers untouched.

## \[0.36.0\] – 2026-11-01

### Changed

- Module headers cleaned up (user request): The docstrings of all eight Python files now contain only the extension name (nemo-previewer), the file name with version number and an at-most-three-line short description in English. The previous STAND histories (some over 90 lines: version and F notes, usage and technique sections) are removed from the files – the version history lives in changelog.md, the technical notes in REFERENZ.md.
## \[0.35.0\] – 2026-11-01

### Changed

- Module subfolder nemo-previewer-modules (user request): The extension folder is tidied up – the seven module files (previewer\_panel, previewer\_select, previewer\_util, previewer\_toolbar, previewer\_render\_media, previewer\_render\_docs, previewer\_render\_text) now live in the subfolder nemo-previewer-modules; only the entry file previewer.py stays directly in the extension folder (Nemo loads only there). The entry puts the subfolder on the import path before the imports – and AHEAD of the extension folder, so flat old copies never win; a new log line "Module dir: …" confirms the path. INSTALL documents copying, upgrading (including cleaning up flat old copies) and uninstalling in the new layout (→ REF ENT-MODDIR-1).

## \[0.34.1\] – 2026-10-31

### Fixed

- Black left edge of the preview column in light mode (F46 X, user finding): The narrow strip between file view and preview belongs to the handle window of the injected Gtk.Paned – GTK paints no background there by itself; in dark mode black sat on dark gray (invisible), in light mode a black frame showed. A draw hook on the Paned now paints the area with the same chain color as the panel (→ REF PAN-BG-2).
- Preview toggle inactive at startup (F40 follow-up, user finding): The button for the preview column in Nemo's toolbar did not reflect the open state. notify::visible only fires on changes – but the panel is already visible when the button is packed (the injection calls show all), so the button never caught up. It now synchronizes directly when packed (set active before connecting, fires nothing) (→ REF ENT-TOGGLE-1).

## \[0.34.0\] – 2026-10-31

### Fixed

- Waterfall text color follows the theme (F12, user finding): In the font preview the waterfall text was black – also in dark mode, where black text on dark gray was barely readable. Cause: StyleContext.get\_color() requires the state argument in GTK3; the old argumentless call ALWAYS raised a TypeError that the surrounding except block swallowed, so the fallback (almost black) stayed. The call now reads get\_color(Gtk.StateFlags.NORMAL), the same theme color as the folder icons (→ REF TXT-FONT-2).

### Added

- Configurable waterfall sample text (F12, user request): The text of the font waterfall is no longer hardwired in the source. New "Fonts" section in the settings dialog with a text field – entries save immediately (config key font\_sample\_text, default remains the classic sentence) and rebuild a just-displayed font live; empty text stays unsaved (→ REF TXT-FONT-2).

## \[0.33.0\] – 2026-10-31

### Added

- Folder content list configurable (F48, user request): The folder preview with content list remains the mandatory default; the new toggle "Show folder contents in the preview" in the "General" section (default on, config key folder\_contents) shows the plain folder icon with file information when deselected (the behavior before 0.23.0). Toggling saves immediately and rebuilds a currently highlighted folder live; file previews remain untouched (→ REF PAN-FOLDER-2).

## \[0.32.0\] – 2026-10-31

### Added

- Text preview for "opaque" file types (F47, user finding): The type guesser reads only the NAME – index.theme counted as application/x-theme, .xsession-errors.old as application/x-trash ("backup"), both without text preview although their content is plain text; extensionless dotfiles such as .xsession-errors already came through the F23 sniffer to the preview. Now: (1) .theme/.old/.bak/.orig in the extension whitelist \_TEXT\_EXTRAS (.swp stays out, Vim swap is binary); (2) for opaque types (backup, theme, unknown/application/octet-stream) the sniffer decides on the content before the preview gives up – readable text is shown, binary files fall at the control-character threshold (→ REF PAN-F47-1).

## \[0.31.11\] – 2026-10-31

### Changed

- Folder list IX (F46 IX, user description): The 10/10/8/8 inner padding now sits INSIDE the slab – the margins hang on the row contents (10 px at the sides, 8 px on top of the first and below the last row) instead of as margins in front of the ListBox. The theme surface of the slab fills the viewport edge to edge; the black carrier of the list (parent level), which the user only saw with an overlong list, has no exposed area left. The scrollbar itself was already theme-colored (→ REF PAN-FOLDER-1, PAN-BG-2).

### Added

- Panel scan (F46 IX): The pixel probes additionally read a complete horizontal color profile at panel height – the log prints color runs compressed with a black-pixel counter and thus also shows stripes between which no fixed probe sits (→ REF PAN-BG-2).

## \[0.31.10\] – 2026-10-31

### Fixed

- Panel background VIII (F46 VIII, pixel probe finding): The probes from 0.31.9 caught the black exclusively at column 2 (pw-12) – in the strip between slab edge and scrollbar column, and only while the scrollbar is visible; viewport, scroll window and panel are painted everywhere. Cause: Overlay scrolling lets the bar float in its own GdkWindow above the viewport, whose unpainted parts stay black. The folder list therefore gets a classic inline bar (set\_overlay\_scrolling(False)); painters and CSS now bite reliably. The pixel probes stay in as verification (→ REF PAN-BG-2).
- SyntaxWarning in previewer\_panel.py fixed: The STAND line carried \_-escapes in the module docstring; Python warned "invalid escape sequence" on every start – identifiers there now stand without backslash.

## \[0.31.9\] – 2026-10-31

### Added

- Pixel probe diagnostics (F46 VII, user finding): 0.31.8 ran cleanly and dbg showed ALL surfaces painted – the scroll window now also resolves rgba(56,56,56,0.999) (previously transparent) – yet the black strip remained. The image contradicts the widget model; the new diagnostics \_dbg\_ pixels therefore reads real pixels at nine points after painting (edge, scrollbar column at two depths, slab edge, column top/bottom, panel edge, slab center, in front of the panel) and logs the colors as a "Panel pixels:" line – the log thus shows WHERE black really sits (→ REF PAN-BG-2).

## \[0.31.8\] – 2026-10-31

### Fixed

- Panel background VI (F46 VI, user finding): The black background of the folder preview first appeared with the borderless request from 0.31.4 – only without the 8-px outer margin did the scroll window's own transparent GdkWindow reach the slab edge. The folder branch therefore no longer zeroes the outer margin (the margin of \_render\_inner remains). In addition: The CSS rule now also covers the scroll window itself and the junction, the dbg marker of the background painter is per widget now (a single marker let the lines of the four widgets pendulate endlessly – log flood), and the CSS dbg line prints only on color change (→ REF PAN-BG-2, PAN-FOLDER-1).

## \[0.31.7\] – 2026-10-31

### Fixed

- Panel background V (F46 V, user finding): 0.31.6 proved in the dbg lines working painters and set margins (all four widgets paint with source=Panel; ListBox margins 10/10/8/8) – yet the black strip remained and the padding was visually missing. Cause suspicion: The draw painter runs before the widget's standard draw – theme surfaces (trough, viewport) cover it; and the margin strips of the list show the viewport background instead of the slab. The background color therefore now also sits as a CSS rule on viewport and scrollbars (class pvw-surface, application priority above the theme; the scrollbars are re-applied on realize), and dbg names the own color of each widget's context per widget – showing what the theme itself paints there (→ REF PAN-BG-2).
## \[0.31.6\] – 2026-10-31

### Fixed

- Panel background IV (F46 IV, user finding): The black scrollbar layer remained in 0.31.5 too – the painter therefore now additionally covers viewport and scrollbars (more own GdkWindows; the scrollbars are only created on realize and are hooked there). dbg "Panel background (widget):" now names per widget where painting happened and reads back the ListBox margins after realize – if theme CSS overrides the widget margins (suspicion regarding the vanished list padding), it shows in the log (→ REF PAN-BG-2).
- Repo cleanup (user finding): On the 0.31.5 push the entry had accidentally landed in the repo as previewer-py.py while previewer.py stayed at 0.31.4 – Nemo loaded two providers (WARNING flood). Cleanup: delete previewer-py.py in repo and extension folder, previewer.py carries the current version.

## \[0.31.5\] – 2026-10-31

### Fixed

- Panel background III (F46 III, user finding): The 0.31.4 approach painted nothing under WhiteSur – the toplevel style context resolves no background color there, and the scrollbar region lies in the scroll window's own GdkWindow which the panel painting never reaches; black edges thus remained as soon as the folder list scrolled (both modes, while Nemo's own list shows dark gray there). The background painter now runs as a chain – panel context, toplevel, content slab, otherwise a base derived from the foreground color – and additionally on the scroll window itself. dbg "Panel background:" names the source and all candidate colors, the folder diagnostics reveals whether the scroll window carries its own GdkWindow (→ REF PAN-BG-2). Side note: the accidentally duplicated 0.31.3 line in the panel module header is removed.

## \[0.31.4\] – 2026-10-31

### Fixed

- Panel background II (F46 II, user finding/request): The style class background alone was not enough – GtkBox paints no CSS background color. The panel therefore draws the themed background in the draw signal FIRST, under all children – with the style context of the Nemo toplevel, because the panel context under WhiteSur-Dark may carry no resolved background color. And the folder list fills the column without borders – the outer margin of the content area is zeroed for that, the padding (10/10/8/8 px) sits INSIDE the list window (user request).

## \[0.31.3\] – 2026-10-31

### Fixed

- Black areas around the folder list (F46 + F43 fix III, user finding): Dark/light mode screenshots brought clarity – the black was never the icon but the unpainted background of the preview column (above/below the list, scrollbar region); the panel now paints it itself (style class background). And the silhouette icons now take their foreground color from the docked panel instead of the freshly built list that is not yet in the window – in light mode they were white and invisible because of that.

## \[0.31.2\] – 2026-10-31

### Fixed

- Icon silhouettes (F43, user finding): The 0.31.1 diagnostics showed that the loading course consistently picks -symbolic names – but the WhiteSur theme itself delivers colored icons under those names (dark slabs in dark mode). The folder preview therefore repaints every chosen symbol as a monochrome silhouette in the list's foreground color: alpha channel (shape) stays, RGB goes uniformly to the text color – bright in dark mode, dark in light mode, no matter what the theme smuggles in under the -symbolic name.

## \[0.31.1\] – 2026-10-31

### Added

- Folder icons diagnostics (F43, user finding): The dark slabs reappeared even under the strict symbol loading course (0.30.1) – the folder preview therefore logs the mapping content type → chosen symbol per render as a dbg line "Folder icons:", so the log shows which theme symbol actually loads per type.

## \[0.31.0\] – 2026-10-31

### Added

- Step trace for all functions (F45, user request): A central sys.settrace hook (install\_step\_trace, installed in the entry) logs every call with arguments, every return and every exception across all eight modules – without touching a single existing function. Activation via the environment variable NEMO\_PREVIEWER\_TRACE when starting Nemo: 1/call logs calls, line additionally every executed line; without the variable no hook runs (zero overhead)

## \[0.30.1\] – 2026-10-31

### Fixed

- Folder preview: icons strictly symbolic (F43 fix, user finding): GTK secretly loaded the colored full icon when the icon theme lacked a -symbolic variant – in dark mode dark slabs with black rim showed, sometimes on folders, sometimes on file types without symbol variant (such as SVG, archives). The symbol candidates are now checked against Gtk.IconTheme.has\_icon; if the theme variant is missing, the generic symbols step in (folder-symbolic respectively text-x-generic-symbolic) – never the full icon

## \[0.30.0\] – 2026-10-31

### Changed

- Folder preview: icons follow the system theme (F43 polish II, user request): Symbolic icons instead of fixed symbols – bright in dark mode, dark in light mode. Folders stay ahead of files as before (F43), hidden entries only appear in the list if Nemo shows them (Ctrl+H, org.nemo.preferences show-hidden-files) – otherwise the header hint counts them out (K1)

## \[0.29.0\] – 2026-10-31

### Changed

- Folder preview with icons and padding (F43 polish, user request): Every entry is preceded by the type icon from the icon theme – folder symbol or Gio-guessed file symbol in menu size, with fallback – and the list carries the same padding as the text previews (10/10/8/8 px)
- INSTALL.md: Installation switched to git clone (user rework adopted): git in the required packages, own sections "Change directory and clone git" and "Create the needed directory …", combined line "All packages at once" with all packages in one go; three blemishes fixed along the way: cd continuation with && instead of backslash (produced broken bash), step numbering 1./2./3. instead of 2./3./4., heading extended by "directory"; log example in the Install section brought from 0.3.1 to 0.29.0
- INSTALL.md: gir1.2-gtksource-4 (syntax highlighting in the text preview, new since 0.28.0) added to the optional packages block – Mint 22 virtually always ships it via xed, Debian 13 carries the same name; plus the note that audio playback (autoaudiosink) needs the plugin set gstreamer1.0-plugins-good, which Mint/Cinnamon brings along and minimal Debian does not

## \[0.28.1\] – 2026-10-30

### Added

- Syntax highlighting as a setting (F44 follow-up, user request): Toggleable in the "Text files" section (key text\_syntax), default on – unchecked, source code files always show the plain text; the toggle applies to the running preview immediately

## \[0.28.0\] – 2026-10-30

### Added

- Syntax highlighting in the text preview (F44, user request): Source code files (.py, .sh, .c, .js, .json, .xml …) appear colored as in an editor – GtkSourceView (optional package gir1.2-gtksource-4, the same module as xed) guesses the language from the file name; without the binding or without a recognized language the preview stays unchanged. Dark GTK themes get a dark color scheme (oblivion), light ones the classic; line numbers (F24) remain margin drawing and are not copyable

## \[0.27.0\] – 2026-10-30

### Added

- Configurable document cap (F12 part 3, user request): In the new "Documents" section of the settings dialog choose whether PDF and office previews are capped (performance) or show all pages unlimited; the maximum page count is freely selectable (1–999, default 20 as before), changes apply immediately – also to the currently displayed document
- Page indicator above every document (F14, user request): Even single-page PDF and office documents show "Page 1 of 1"

### Changed

- Page indicator unified as "Page X of Y" (previously "Page X/Y")
## \[0.26.0\] – 2026-10-30

### Added

- LDIF address books and Windows contacts as contact cards (F7, user request): .ldif files (Thunderbird/Mozilla/Outlook exports, RFC 2849 with Base64 values and jpegPhoto) and .contact files (Windows XML, namespace-agnostic) render the same contact card as .vcf/.vcard

### Changed

- Contact cards without quantity limit (F7, user request): The 50-card cap is gone – all contacts of the file are built and shown scrollable; with a single contact no scrollbar appears

## \[0.25.1\] – 2026-10-30

### Changed

- Contact cards without card background (F7, user request): The card frame stays transparent – in dark mode a white tile hurts the eyes; shadow and hairline border remain
- More subtle corner radius (user request): Reduced by a third – contact cards like music covers (placeholder tile and cover frame with shadow) now round with 56/960 instead of 56/640 of the smaller edge

## \[0.25.0\] – 2026-10-30

### Changed

- vCard polish (F7, user request): Every contact card carries a rectangular frame with the corner radius of the embedded music covers (F34 formula) and the same drop shadow; files with several contacts now show ALL cards stacked, scrollable – no longer only the first (50-card cap with remainder hint)

## \[0.24.0\] – 2026-10-30

### Added

- vCard contact card (F7, part 1, user request): .vcf/.vcard files (vCard 2.1, 3.0, 4.0) appear as a real contact card – the contact photo circular (inline Base64 or local URI), without photo a circular placeholder; below name, position/company and the contact data (phone, e-mail, web, address, birthday) as a table. If the file contains several contacts, the first is shown; ICS (events as table) remains open

## \[0.23.0\] – 2026-10-30

### Added

- Folder preview as content list (F43, user request): Instead of the folder icon the panel shows the content – folders first (bold), then files with size, each alphabetically; hidden entries dimmed alongside, giant folders the first 300 rows with remainder hint

## \[0.22.0\] – 2026-10-30

### Added

- Preview toggle in Nemo's toolbar (F40, user request): Next to the view selector sits a button that shows and hides the preview sidebar – with CSD in the title bar, classically as a toggle right behind the view buttons of the Nemo toolbar; the icon is builder-view-right-pane-symbolic (icon helper with theme fallbacks), and the state stays in sync via Ctrl+Alt+P
- Photo information for RAW files (F42, user request): NEF, CR2, CR3, ARW, ORF, DNG & Co. usually cannot be decoded by Gdk-Pixbuf – the panel now shows the photo table (camera, date, aperture & Co.) below the icon view when EXIF sits in the buffer
- Old MS Office formats in the preview (F39, user request): Binary .doc, .xls and .ppt files as well as RTF files run through the LibreOffice background conversion into sharp PDF like the OOXML formats; since they are no ZIP archives there is no embedded thumbnail – the transitional view shows hints about conversion, missing LibreOffice or failed conversion
- "Location" and custom fields in the image info table (F38, user request): If present, the table shows the XMP "location" (IPTC Core, right after the shooting location) as well as arbitrary XMP fields from non-standardized namespaces ("prefix:name") – parsed with Python built-ins in the worker thread, at most ten extra rows, each only with an existing value

### Changed

- Image preview in a 60/40 split (F38, user request): The column splits into a 60 % area for the image (centered vertically and horizontally, across the full column width) and a 40 % area for the image information; the EXIF/size table (F36) runs in there, the split survives window resizing via a live follow-up. SVG previews use the same split, their size row sits in the info area
- New icon for the open button (F40, user request): Opening the file in the default application now carries the pencil icon (document-edit), no longer the document-open icon; if it is missing in the icon theme, the previous name steps in as fallback

### Removed

- Hide button in the panel header (F40, user request): The toggle has moved into Nemo's toolbar as the preview toggle (see Added) – Ctrl+Alt+P keeps working unchanged

### Fixed

- Photo information from HEIC/HEIF (F41/F42, user report): The EXIF sits there as an "Exif" item in the middle of the container – sometimes with, sometimes without APP1 prefix, sometimes only at the end of the file. An accidental early "Exif" hit in the meta box aborted the old single search; the parser now collects validated candidates across the whole buffer and takes the first with EXIF
- Broken office files show an icon (K2): Instead of a bare hint line the generic icon view sits as a visual anchor above the error message
- SVG preview via the Cairo route (K3): Intrinsically small SVGs now fill the panel width (DPI rendering, vector stays sharp), and the call uses the current librsvg API instead of the deprecated get\_pixbuf(); without pycairo or with an old librsvg the previous path steps in as fallback
## \[0.21.0\] – 2026-10-30

### Added

- Photo info table with EXIF data (F36, user request): Below image previews sits a table with height, width, shooting date, shooting location (GPS in decimal degrees), camera model, exposure time, focal length with 35-mm equivalent, aperture and ISO – each row only if the value exists; height/width follow the EXIF rotation. The EXIF parser runs with Python built-ins in the worker thread (no new dependency); vendor differences are caught by standard fallbacks: exposure time/aperture from APEX values if needed, date as a cascade original → digitized → file, camera model without vendor duplication. The previous size label has been absorbed into the table

## \[0.20.0\] – 2026-10-29

### Added

- Genre in the music preview (F35, user request): The Discoverer reads the genre tag along; the row appears only if the tag exists

### Changed

- Cover shadow re-aligned (F35, user request): The drop shadow of the covers now sits right and bottom, extends 3 px further there and is more transparent overall (4 % opacity per step instead of 5.5 %)
- Music info rearranged (F35, user request): The year no longer sits in the album row but as its own row below – label "First released"
- Colons (F35, user request): All labels of the info tables (music, video, EML, e-book, font) end with a colon – set centrally in the table helper
- Header thinned out (F35, user request): Icon, file name, type, size and modification date are removed from the header area of the preview column – Nemo's list shows all of that already. What remains are the open and hide buttons; the hint "(file not found)" now sits in the content area

## \[0.19.0\] – 2026-10-29

### Added

- Cover frame in the music preview (F34, user request): Embedded covers get the same rounded corners as the placeholder tile (56/640 of the edge length – the radius scales with the display), and every cover – embedded or placeholder – carries a small drop shadow. The shadow is built stacked in Cairo from six semi-transparent tiles, without blur filter; without PangoCairo the cover stays unframed. Video tiles and image previews are untouched

## \[0.18.0\] – 2026-10-29

### Added

- Extended music information (F33, user request): The audio preview now determines title, artist, duration, track number ("x of y"), album with year, album artist, disc number ("x of y") and codec and shows each row only if available. For the year the original release wins (original-date), otherwise the date tag is read as year. Peculiarities of the tag formats are caught defensively: ID3 (MP3) and MP4 report track/disc numbers as number pairs, Vorbis comments (FLAC, Ogg) partly as string "n/m" – both are understood; the codec comes from the audio codec tag, if needed from the container format

### Changed

- Audio preview rearranged: The playback bar (play/pause, slider, position) sits with some distance UNDER the cover, the information follows below. The previous file row is gone – Nemo shows the file name right next door anyway

## \[0.17.0\] – 2026-10-29

### Changed

- Image preview with height cap (F32, construction stage 1, user request): Image previews – raster images as well as SVG – fill at most 60 % of the column height. The display height couples live to the current column height: On window resize the live scaling pulls the cap along (new height tracking in size-allocate plus \_preview\_height). The image is no longer packed expanded; the container holds exactly the (capped) image height via keep\_height. Directly below the image sits a horizontal separator with 8 px distance top and bottom – the area below is reserved for additional image information and stays empty for now; the existing size label ("W × H px") now sits below the separator. Embedded images (audio covers, office thumbnails, video frames) and all other previews are untouched. Implemented in the media renderer with the new pack helper \_pack\_image\_capped; the \_scaled\_image extension by frac\_h sits in the panel core and is thus available to all renderers
## \[0.16.3\] – 2026-10-29

### Changed

- F24 look (user request "for better distinguishability"): The line numbers now appear slightly darker and smaller. Opacity rises from 60 % to 75 % of the theme text color – on light ground the numbers were too washed out –, and the number font scales to 80 % of the text font size (with a floor at 1 pt so tiny sizes do not slip to 0). The same scaled probe measures the margin width so margin and number font match; copy behavior and all other F24 properties (margin drawing outside the buffer, only visible lines, live toggle) remain unchanged

## \[0.16.2\] – 2026-10-28

### Fixed

- F24 field fix 2, first finding (test field 0.16.1): The space for the line numbers was there, but the numbers stayed invisible. "draw" is a RUN\_LAST signal – the handler registered via connect() ran BEFORE the TextView standard drawing, which afterwards fills the background and paints over the margin. The handler is now registered via connect\_after() and draws ON TOP of the standard drawing (classic overlay order)
- F24 field fix 2, second finding: Deactivated line numbers in the settings took effect immediately (the text moved up), but re-activating did nothing. The marker \_last\_textish stored the linenumbers toggle instead of "current preview is TextView-based" – after deactivating it sat at False, so the toggle did not re-render on re-activation. The marker now marks TextView-based previews in general; the toggle thus works live in both directions. Expensive renderers (PDF, office, audio, video, image, folder) remain untouched as before
- Hardening: If the line number drawing ever fails (future Nemo/GTK changes), the draw handler now reports the error once via dbg instead of silently – draw fires often, a closure flag prevents log spam

## \[0.16.1\] – 2026-10-28

### Fixed

- F24 field fix (test field 0.16.0): The line number margin crashed with an AttributeError on the first click onto a text file – the GI binding of Pango.Layout does not offer get\_pixel\_width(). The margin width measurement now uses get\_pixel\_size(); the fallback onto the generic tile had caught the crash, but the text preview itself stayed empty. With the fix the line numbers appear as intended in 0.16.0

## \[0.16.0\] – 2026-10-28

### Added

- Line numbers in the plain text preview (F24, user request): Text files and extensionless text files show their line numbers in the left margin. The numbers are a margin drawing OUTSIDE the text buffer – selection and copy (Ctrl+C) capture only the text itself, the numbers are never copied along. Wrapped lines keep their number on the first visual line; only the visible lines are drawn
- New "Text files" section in the settings dialog: CheckButton "Show line numbers (not copyable)" – active by default, saved immediately (key text\_line\_numbers in the conf) and applied live to the currently shown text preview. Only plain text previews are rebuilt on toggling; markdown, e-mail, e-book and font waterfall stay without numbers and untouched
- Deliberately built without GtkSourceView (no new package): The numbers are drawn in the draw handler of the existing TextView

## \[0.15.0\] – 2026-10-28

### Changed

- Structure release (F28/F29/F31): The extension consists of eight modules – the panel core (previewer\_panel.py) remains the heart, but the renderers for media (previewer\_render\_media.py), documents (previewer\_render\_docs.py) and text (previewer\_render\_text.py) are outsourced as mixin classes, likewise the toolbar including the settings dialog (previewer\_toolbar.py). Two shared base helpers (\_pixbuf\_from\_bytes, \_zf\_read\_capped) now live in previewer\_util.py, where they are available to all renderers
- The entry (previewer.py) now checks at load time that all eight modules carry the identical PREVIEWER\_VERSION – if an old copy sits in the extension folder, the terminal warns immediately
- F29: The toolbar is – as the user asked, "considered useful: implemented" – its own mixin module; the action bar, the settings dialog (F12) and the shortcut Ctrl+Alt+P behave unchanged
- F28: Long comment and history blocks are moved out of the code into the new REFERENZ.md; the code carries markers of the form `# → REF PAN-R9-1` (module prefix + topic + number) in their place. REFERENZ.md is a living project document in the repository and is deliberately NOT deployed – the deployment copies only the \*.py files
- Behavior unchanged: There are no new features and no bug fix – all renderers, caps (0.9.2), thread disciplines (R1/B7) and settings (F12) work exactly as in 0.14.1

## \[0.14.1\] – 2026-10-28

### Fixed

- Markdown tables were as wide as their longest cell and then fell apart into wild wrapping in the TextView (field test 0.14.0 with the schedule table of planned.md): Tables now keep an overall budget in display columns – laid out for the 300-px default panel –, narrow columns keep their full width, and overlong cells wrap multi-line INSIDE their column, as in the browser. The columns stay flush, header and gray separator line run across all lines of the logical table row. Cell markup spanning a cell wrap is deliberately not glued together – valid markup wins, the raw text fallback must never kick in because of a table
- Emoji width: 🔴 ✅ ☑ and similar symbols occupy two display columns in the TextView – the width measurement of the tables now counts them twice (and the variation selector FE0F not at all), otherwise emoji cells visibly stuck out
- Backslash escapes per CommonMark (\[ becomes \[) – 0.14.0 showed them as raw text, e.g. in headings like $$ 0.14.0 $$
- Masked bars in tables: `\\|` is a literal bar in GFM, not a column separator

## \[0.14.0\] – 2026-10-28

### Changed

- Markdown preview much more browser-like (K4): The converter now covers the widespread markdown variants (GitHub Flavored) instead of only the standard core. New: GFM tables (bold header, gray separator line with box characters, columns flush in monospace, right alignment with `---:`), task lists (`[x]`/`[ ]` become ☑/☐, checked items appear struck through as in the browser), ordered lists (1./1)), indented and nested lists with level characters (•/◦/▪), Setext headings (`===`/`---` below the line), bold+italic (`***…***`), `~~strikethrough~~`, multiply nested quotes (`> >`), autolinks in angle brackets, separator lines also with spaces (`- - -`) and links with parentheses in the URL (previously broke the regex). Headings of levels 1 and 2 get an underline (approximates the colored bar of the browser rendering), and headings, rules and tables get air above – documents like planned.md or changelog.md thus appear as structured as in the browser. Deliberately unchanged: no webview, no new package dependencies; wide tables wrap in the panel instead of scrolling horizontally; 4-space code blocks stay unconsidered (collides with list indentation). The existing safety line remains: invalid markup leads to the dbg message and to showing the raw text
## \[0.13.0\] – 2026-10-28

### Added

- Setting "Default width at startup" (F12, part 2): Under "General" in the settings dialog the width can be set with which the preview column opens after Nemo starts. The SpinButton carries the CURRENT value in advance (at least 260 px, the smallest allowed value); next to it a subtle line names the default (300 px) and marks the actual state as "current". If the user drags the preview column at the divider, the chosen width automatically becomes the future start width: it lands – debounced, only once the divider stands still – in the configuration file and is applied exactly like that on the next start. Changes in the settings dialog apply immediately: the panel pulls to the new width live, without saving or restarting. If the settings dialog is open while the divider is dragged, the SpinButton follows along (unless the user is typing in it right then)

### Changed

- Default start width of the panel changed from 340 px to 300 px (user request); without a configuration file 300 px now applies

## \[0.12.1\] – 2026-10-28

### Fixed

- Settings were not saved (B8, reported from the test field): 0.12.0 accessed Gio.Keyfile for the configuration file – but PyGObject binds GKeyFile as GLib.KeyFile (GKeyFile is a GLib class, not a Gio class). The error was caught by the defensive blocks ("configuration not saveable" in the terminal log), the settings dialog stayed usable, only the persistence was ineffective. The file now runs via GLib.KeyFile with a compatibility resolution for the old alias GLib.Keyfile (same pattern as with the Discoverer in the media preview); if the class is missing in the binding, the panel reports it via dbg and stays on the defaults instead of failing silently

## \[0.12.0\] – 2026-10-28

### Added

- Settings dialog (F12, part 1): The gear button of the toolbar now opens the configuration window "Nemo Previewer – Settings" – ALL settings of the preview column will gather here. First working setting: "Show preview column at startup" (unchecked, the column stays invisible after Nemo starts; Ctrl+Alt+P shows it again at any time). Every change is saved immediately to \\~/.config/nemo-previewer/nemo-previewer.conf (GLib-native INI format via Gio.Keyfile, no new dependency, directory created if needed) and applied on every start of Nemo – the entry applies the configuration only AFTER showing the panel, otherwise a requested invisibility would be overridden immediately. Broken or half-written configurations fall back to the defaults silently and never keep Nemo from starting. A repeated gear click brings the existing window to the front instead of opening a second one

### Changed

- Preview toolbar \\~5 px slimmer (user request): The inner padding top/bottom of the ActionBar sits at 3+4 px, below the Adwaita default of 6+6 px; if a theme cannot apply the rule, it stays with the theme default without error

## \[0.11.0\] – 2026-10-28

### Added

- Preview toolbar (F19, part 1): At the bottom edge of the preview column a static toolbar (Gtk.ActionBar) with its own separator line above the content area now runs – always visible while the panel is active (user decision: no show/hide per renderer; the renderer actions F13/F20/F21/F24–F27 will register here later). On the far right sits a fixed settings button with a gear from the system icons (preferences-system-symbolic, tooltip "Settings"); in the first construction stage deliberately without function – the configuration (F12) will dock there; until then the button only acknowledges clicks in the terminal log

## \[0.10.4\] – 2026-10-28

### Fixed

- Image preview still did not appear even after the R9 fix 0.10.3 (B7, second part): The image widgets packed in the idle callback lie temporally AFTER the show\_all() of the render pass and were therefore never shown – GTK3 does not display unshown widgets. The R1 media preview therefore carries an explicit own show\_all at the end of \_media\_probe\_done (with comment); exactly this had been overlooked in the R9 image rework of 0.10.2. The image callback now shows its result on both exit paths (preview AND error fallback) with its own show\_all. The "Loading image" note that previously stayed forever is thus truly replaced for the first time. Also new are dbg diagnostics lines so the terminal log can now trace the image path: "Image read … (bytes)", "Image decoded … (dimensions)" and "Image result discarded, selection moved on …" on fast clicking through

## \[0.10.3\] – 2026-10-28

### Fixed

- R9 regression from 0.10.2 (B7): In the field test no image previews appeared at all. Cause: 0.10.2 decoded the images in the background thread and thereby created Gdk objects (PixbufLoader) outside the GTK thread – against the proven R1 pattern of the media preview ("no Gdk objects in the worker"); the worker failed silently, without traceback or error hint, and the "Loading image" note stayed. The background thread now only reads the file (pure Python I/O); decoding, EXIF rotation and scaling run back in the GTK thread – the same discipline as with the media covers. The unnecessary GI warm-up for the image decoding (it created a PixbufLoader that nobody closed – source of the GdkPixbuf warning "finalized without calling gdk\_pixbuf\_loader\_close()" in the terminal log) is gone completely. All acceleration levers from 0.10.2 remain: "Loading image" hint immediately, decode cap max(2 × panel width, 1024), original dimensions in the info label, stale discard on fast clicking through
## \[0.10.2\] – 2026-10-27

### Changed

- Image preview accelerated (R9 from planned.md): Large images (typically 20-MB JPEGs with 50–100 megapixels) previously blocked the whole UI because reading, decoding and EXIF rotation ran synchronously in the GTK main loop. Two-stage as with the media preview: a "Loading image" hint appears immediately, the decoding runs in a background thread, and the finished pixbuf is handed into the panel via idle callback (silently discarded if the selection moved on). Additionally the size-prepared cap decodes to max(2 × panel width, 1024) instead of stubbornly at 4096 px – decoding becomes many times cheaper, the live scaling at divider dragging loses nothing. The info label now shows the ORIGINAL dimensions from the file header instead of the capped decode size. The bomb protection from 0.9.2 remains fully intact; if the thread path ever fails, the previous synchronous path steps in as a lifeline

## \[0.10.1\] – 2026-10-27

### Fixed

- Markdown preview (B6): The body was overridden with a hardcoded default font at 9 pt via override\_font and thus appeared smaller than the rest of the interface – the text preview (monospace) in contrast acts like the system font size. The markdown preview no longer overrides the font at all and uses the system font of the GTK theme (i.e. the system's font size); headings scale along since their size specs are relative to the base font. EML and e-book preview stay at 9 pt for now

## \[0.10.0\] – 2026-10-27

### Added

- Text preview for extensionless files (F23 from planned.md): Freely named files (e.g. notes, todo, dotfiles like .bashrc) landed on application/octet-stream via the MIME type guesser and showed only icon and file info. Files without extension are now checked by content sniffing: the first 4 KB must contain no NULL bytes and at most 5 % control characters – only then does the dispatcher show the normal text preview. Extensionless binary files (executables, core dumps) stay with the generic view; the usual caps of the text preview (256 KB / 2000 lines) apply unchanged

## \[0.9.2\] – 2026-10-27

Hardening package from the second security audit (focus buffer overflow/OOM): Classic overflows are ruled out at the Python level; a doctored image, PDF, EPUB, DOCX or EML could however shoot Nemo down via giant allocations. No new functions, normal files behave unchanged.

### Fixed

- Image preview: GdkPixbuf decoded the FULL resolution before the cap kicked in – a PNG declaring only 30000×30000 in its header allocated \\~3.6 GB (OOM crash). `_pixbuf_from_bytes` now uses the size-prepared cap (shrink at decode time) and is now also the primary route of the image preview (raw data cap 64 MB, fallback `new_from_file_at_scale`)
- PDF preview: The lower scale clamp (0.2) forced rendering at 20000×20000 px ≈ 1.6 GB per page for pathologically giant pages (\\~100000 pt) – an additional pixel budget (4096²) per page now applies, recalculating area-true only in the extreme case
- EML preview: The parser read the ENTIRE file – multi-GB .eml ate Nemo's memory; only the first 2 MB are read now (headers sit at the top anyway)
- EPUB preview: `META-INF/container.xml` and the OPF file were read uncapped (decompression bomb gap next to the existing R4 caps for chapters and covers) – both now via `_zf_read_capped`
- Office preview: Embedded thumbnail (16-MB cap) and content.xml/word/document.xml (2-MB cap) are no longer read uncapped; media covers from tags with a 32-MB byte cap

### Changed

- Selection detection (previewer\_select.py): Wildcall protection – the function pointers read via the computed vtable offset (peek\_selection, get\_name, get\_uri) are checked against the executable address ranges of the Nemo libraries before the call (`/proc/self/maps`); a Nemo update with a shifted class layout thus leads to a cleanly disabled route instead of a wildcall that would kill Nemo

## \[0.9.1\] – 2026-10-27

Security and redundancy audit across all four modules; no new functions, preview behavior unchanged.

### Fixed

- Crowbar race in the entry (previewer.py): An outdated location widget crowbar could still be placed after a folder change and overwrite the current folder path with the old path; the path is now set exclusively synchronously in `get_widget`
- Poll timer leak in the entry (previewer.py): The 500-ms safety timer kept running as a zombie after the Nemo window closed; it is now cleaned up on the window's "destroy" signal
- Office conversion after panel teardown (previewer\_panel.py): The child watch on the LibreOffice conversion could still hit the already dismantled panel; the result is now discarded and only the temp folder cleaned up

### Changed

- Redundancy cleanup (previewer\_panel.py, behavior unchanged): The TextView building (previously five times identical: text, markdown, EML body, e-book, office text excerpt), the capped text file reading (text + markdown) and the info table (previously inline in the EML header, audio and video next to `_meta_grid`) now use the shared helpers `_text_view`, `_read_text_file` and `_meta_grid`
- Redundancy cleanup (previewer\_select.py, behavior unchanged): The vtable loop and the TreeView fallback now read the file name via the shared helper `_iface_file_ name`; the basename from a URI via `_name_from_uri` (previously each implemented identically several times)
- Entry module header updated: Video shows a tile with an open button since 0.7.0/0.8.0 (no longer "first frame as still image") and Poppler renders all pages scrollable (no longer "the first page sharp")

## \[0.9.0\] – 2026-10-27

### Added

- PDF preview: Page indicator "Page X/Y" above the scrollable area (F14 from planned.md) – while scrolling it counts up to the page whose bottom edge crosses the top edge of the viewport, i.e. the page you are over. Single-page PDFs show no indicator; for multi-page PDFs with more than MAX\_PDF\_PAGES pages the existing hint "First X of Y pages" remains in addition

### Changed

- PDF preview: The hint "N pages – scroll down for the preview." is gone – the new page indicator conveys the number by now

## \[0.8.0\] – 2026-10-27

### Removed

- Video playback in the panel (0.7.0–0.7.2): Fully dismantled. In the test field the picture could not be bound stably into the preview column – without the package gstreamer1.0-gtk3 gtksink is missing (the playbin then opened its own window), and the custom appsink build showed no picture in the field despite window and redraw fixes (0.7.1, 0.7.2). The video preview shows the generic tile as before (dark petrol gradient, play triangle, film perforation) along with the file information; playback runs via the open button in the media program of choice. The player bar remains exclusively for music, the central building blocks (\_playbin\_set\_uri/\_player\_bar) remain preserved for a later retry

## \[0.7.2\] – 2026-10-27

### Fixed

- Video preview (custom sink output): Sound ran but the picture stayed at the placeholder tile – the DrawingArea was never prompted to redraw after its first (empty) draw. The frame timer now explicitly calls the redraw (queue\_draw) after each pulled frame

## \[0.7.1\] – 2026-10-27

### Fixed

- Video preview: The playback picture appeared in its OWN window instead of the preview column when gtksink was missing (package gstreamer1.0-gtk3) – the playbin falls back to its default video sink in that case, which opens a window on its own. The video output is now three-stage: gtksink if installed; otherwise an own DrawingArea that draws the frames into the preview column itself via an appsink (videoconvert, raw frames in RGBA, approx. 30 fps) – without an extra package, on X11 as on Wayland; only if both are impossible does playback run with sound only (fakesink). A separate window never opens again

## \[0.7.0\] – 2026-10-27

### Added

- Video preview (F22, conclusion): Files without an embedded thumbnail now show a generic tile as with music – dark petrol gradient, semi-transparent play triangle and film perforation at the top and bottom edge, drawn at double resolution (HiDPI-sharp); if PangoCairo is missing, a video-x-generic icon fallback applies
- Video preview (F22, conclusion): Videos are playable in the panel – the playbin puts its picture output into a gtksink widget that appears below the tile; the player bar (play/pause, slider, position) is shared with the music preview. If gtksink is missing (package gstreamer1.0-gtk3), playback runs with sound only, with a hint
- planned.md: Working file with weakness analysis (as of 0.4.1) and feature proposals including solution sketches, effort estimates and recommended order of processing
- planned.md: F19–F22 added (preview toolbar at the bottom edge, OCR button for PDFs, office→PDF button, video placeholder image and playback in the panel) including roadmap extension

### Changed

- INSTALL.md: Debian 13 notes added – there is no package "python-gi" there (the Python 3 bindings are called python3-gi and are pulled in by nemo-python, which Cinnamon does not preinstall on Debian); SVG package name unified to gir1.2-rsvg-2.0 (valid on Mint and Debian); tested on Debian 13 (Trixie)

### Removed

- Video preview: the still image extraction from the video track introduced in 0.6.0 (playbin + videoconvert ! jpegenc ! appsink in the worker thread) is removed again – in practice it produced no picture, and touching the Gst.PlayFlags missing in the Mint 22 binding crashed the GI warm-up (and with it every video preview) with an AttributeError. Embedded preview images from the tags keep showing if present
## \[0.6.0\] – 2026-10-27

### Added

- Video preview: Still images are now extracted from the video track itself if the file carries no embedded thumbnail in the tags – which is almost always the case for series and movie files (the previous route via TAG\_PREVIEW\_IMAGE therefore practically never produced a result, visible after the Discoverer fix in 0.5.0). A playbin with a videoconvert ! jpegenc ! appsink chain is put into the PAUSED state in the probing background thread; after the preroll exactly one JPEG flows back as bytes and is decoded in the GTK thread – the UI does not block (max. 8 s wait, then the hint applies). Requirement: gstreamer1.0-plugins-good (jpegenc); audio is discarded, only the video track is decoded. F22 from planned.md, part 1 (placeholder tile and playback in the panel follow later)

## \[0.5.1\] – 2026-10-27

### Changed

- Folder preview (K1, deliberately solved as a compromise): Hidden entries keep being counted but are now reported transparently – the hint reads "The folder contains X files, X of them hidden" (singular for one entry; without hidden entries the addition is omitted, for empty or unreadable folders "The folder is empty." respectively "Folder" appears). Previously "Folder with X entries" concealed whether hidden files are contained – the number then also did not match the visible stock in the file manager

## \[0.5.0\] – 2026-10-27

### Added

- Audio preview: Even without an embedded cover a placeholder tile now appears above the media controls – diagonal color gradient (dark blue-gray to dark violet) with a semi-transparent music note symbol and rounded corners, drawn in Cairo/Pango at double resolution (HiDPI-sharp); if PangoCairo is missing, an icon fallback on dark ground applies. Files with and without cover thus show a uniform appearance (pulled forward from planned.md, listed there as F18)

### Fixed

- Audio/video: Tags, duration and covers never appeared – not even in earlier versions. The cause was a binding error in the source code since the first audio preview: The synchronous probing is called discover\_uri() in the Python binding (C name gst\_discoverer\_discover\_uri, WITHOUT "\_sync"); a discover\_uri\_sync does not exist, the AttributeError was silently swallowed. The new placeholder cover made the old error visible for the first time. The probing now calls the correct name; additionally the involved GI classes are warmed up once in the GTK thread (PyGObject resolves method tables lazily) and the probing runs in the worker as a fully resolved callable

## \[0.4.3\] – 2026-10-27

### Changed — Robustness package from planned.md (R1–R8)

- R1: The media probing for audio/video (GStreamer Discoverer) blocked the GTK main loop – for slowly reachable media (USB, network drive) the window froze for up to 10 seconds. It now runs in a background thread; the panel immediately shows a "Reading media information" hint and stays operable, the result swings back into the main loop via idle
- R2: PDF preview: Page 1 renders immediately, the remaining pages (up to MAX\_PDF\_PAGES) are pushed in one per idle pass – even large or scanned PDFs stand in the panel instantly
- R3: Scaling design trap fixed: The live scaling with the panel width knew only ONE image per preview (single slot) – every additional scaled image (e.g. cover plus embedded images) would have overwritten the first. The scaling parameters now sit as Python data per image in a list; any number of images scale along
- R4: EPUB read caps against decompression bombs: chapter documents are read with a 2-MB cap, covers with a 16-MB cap – a tiny, hugely inflated XHTML inside the EPUB can no longer block the panel for seconds
- R6: EPUB3 navigation files (properties="nav") are skipped when collecting text – previously the table of contents could show up as the "text beginning"
- R7 (limited): MOBI record boundaries are cleaned – half-torn multibyte sequences and trailing entry remnants at the record edge produced visible character garbage between paragraphs. Deliberately NOT implemented: the full backward decoding of the trailer sizes; without reference material a decoding error would be worse than the cosmetic flaw (see planned.md)
- R5: The font temp folder (\\~/.local/share/nemo-python … process temp) grew unbounded – every viewed font was held on disk until the process ended. The folder is now capped at 64 copies; fontconfig keeps removed fonts in memory, already seen waterfalls stay correct

### Watch item (no code fix)

- R8: The selection detection accesses internal Nemo structures (class vtable offsets). After Nemo updates check the log: If all four modules report their version and "Selection changed …" lines appear, all is well; the fallback cascade (vtable → GI → ATK) catches deviations. Kept under observation in planned.md permanently

## \[0.4.2\] – 2026-10-27

### Fixed — Bug package from planned.md (B1–B5)

- B1: Two fonts with the same file name from different folders overwrote each other at the fontconfig pickup – the target name now contains a hash of the source path, the waterfall always shows the selected file
- B2: The audio player did not know its track end (no bus watch): after the end the pause icon stayed and the position froze; the display now jumps back to 0:00, and playback errors appear as a hint in the panel instead of staying invisible
- B3: The position timer ran forever (even after window teardown) and was never cleaned up – it now runs only during playback and is cleanly removed on switching, stopping and teardown
- B4: If the office cache was unwritable (disk full, \\~/.cache read-only), LibreOffice converted again on every selection – the document is now marked as failed and the finished PDF is shown directly from the temp folder (not thrown away)
- B5: MOBI files were read fully into memory – a 500-MB AZW3 could freeze Nemo; only the head up to 8 MB is read, the text records sit at the file start anyway

## \[0.4.1\] – 2026-10-27

### Fixed

- Font waterfall showed the fallback font instead of the actual family: GTK's default Pango font map is built at startup and misses fonts added later via fontconfig. The waterfall is now pre-rendered with its own fresh font map into a pixbuf (text color from the theme, pre-rendered at double size and scaled down live with the panel width).

### Changed

- Largest waterfall size reduced from 48 pt to 36 pt

## \[0.4.0\] – 2026-10-27

### Added

- Font preview as waterfall (.ttf, .otf, .ttc): The file is pulled into fontconfig only for the running process (FcConfigAppFontAddDir via ctypes – nothing is installed), the family and style name is read directly from the sfnt name table, and a sample text shows the font at sizes 8 to 48 pt. If Pango cannot find the family, a hint appears and the waterfall runs with the fallback font. No new package dependencies.

## \[0.3.1\] – 2026-10-27

### Changed

- Installation guide as its own file INSTALL.md (English) in the repository: requirements, optional packages per preview type, installation, upgrade, uninstallation and troubleshooting. The corresponding installation and uninstall passages were removed from the module docstrings; they now refer to INSTALL.md.

## \[0.3.0\] – 2026-10-26

### Added

- E-book preview (Python built-ins only, no new packages):
  - EPUB (.epub): title, author and language from the OPF content file, embedded cover (manifest reference or heuristic) and the text beginning in reading order (spine)
  - FictionBook 2 (.fb2): title and author, cover from the embedded base64 resource, text beginning of the main body
  - MOBI (.mobi, .prc, .azw, .azw3): title, author from the EXTH header and text beginning; PalmDoc decompression in pure Python; files with HUFF/CDIC compression are rejected with a hint
  - unreadable/broken e-books show a hint instead of an empty preview
- New constant MAX\_EBOOK\_CHARS (30 000 characters text beginning per book)

## \[0.2.2\] – 2026-10-26

### Fixed

- SVG files were not shown (GdkPixbuf error "format could not be recognized"): GdkPixbuf ships no SVG loader anymore since version 2.42. SVGs are now rendered via librsvg if present (package gir1.2-rsvg); otherwise a hint appears instead of an error message. Non-loading raster images also now show a hint instead of an empty preview.
- The office cache was never written: os.replace fails silently with "Invalid link across device boundaries" (EXDEV) when /tmp is a tmpfs on its own device. Because of that LibreOffice converted the same document again on every selection. The cache now uses shutil.move, which copies across devices – every conversion runs only once per document version.

## \[0.2.1\] – 2026-10-26

### Fixed

- Markdown preview stayed empty for files with `---` lines (YAML front matter, separators): an operator precedence error produced invalid Pango markup tags that GTK silently discarded on insert. Fixed; additionally the markup is validated before insertion – in doubt the raw text now appears instead of an empty preview.

## \[0.2.0\] – 2026-10-26

### Added

- Markdown preview (.md) rendered: headings, bold/italic, inline and block code, lists, quotes, separators and links as formatted text (Pango markup, without new package dependencies)
- EML preview (.eml): headers (subject, from, to, cc, date) as a table plus body – preferring text/plain, otherwise the HTML part is cleaned into readable text (Python built-ins)

### Fixed

- EXIF orientation of images is now always applied: photos that carry the rotation only in the orientation tag were previously shown sideways or in the wrong format; the pixel dimensions below the preview now show the orientation actually displayed

## \[0.1.0\] – 2026-10-26

First versioned release of the Nemo extension "Previewer".

### Added

- Docked preview panel on the right in the Nemo window (crowbar technique via Nemo.LocationWidgetProvider and Gtk.Paned), divider freely draggable
- Previews: images, text/source code, PDF (all pages scrollable, up to 20 pages), audio (GStreamer player with play/pause, position slider and seek), video (still image, tags, duration), folders and file information for everything else
- Office documents sharp: LibreOffice conversion in the background to PDF, cached in \\~/.cache/previewer; during the conversion the embedded thumbnail with hint, the sharp result appears automatically; without LibreOffice the thumbnail from the document ZIP
- Selection detection via NemoView.peek\_selection (class vtable), the Nemo selection API, Gtk.IconView/TreeView and ATK fallbacks; selection signals are discovered and connected at runtime
- Live scaling of the preview with the panel width without re-rendering
- Panel show/hide via Ctrl+Alt+P
- Four-module structure (previewer.py, previewer\_panel.py, previewer\_select.py, previewer\_util.py) with version check at startup: outdated files in the extension folder become visible in the terminal log immediately as a WARNING message
- changelog.md and semantic versioning from 0.1.0

### Fixed

- Audio position slider did not move along during playback: With unknown track length (Discoverer failed) the slider range was only 0–1 and the timer could never move it; the range is now pulled from the real playback length, and while the user drags the slider the timer no longer pushes it away
- GstPbutils.Discoverer constructor invalid on newer PyGObject builds (now Discoverer.new with fallback) – title/artist/album, track length and cover now appear for audio and video