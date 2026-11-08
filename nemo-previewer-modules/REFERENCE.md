# REFERENCE.md – Comment Reference of the Nemo Extension “Previewer”

**Purpose.** Since the structure release 0.15.0 (F28), long comment and history blocks no longer live in the code. In their place the code carries exactly one marker of the form `# → REF <MODULE>-<TOPIC>-<NNN>`; the out-sourced text lives here, together with module, location and reason. The code stays lean and readable, the project history is not lost. Since F49 (2026-11-02) this file is entirely English — the migrated text blocks are translations of the original German comments.

**Conventions.**

- Marker format: `# → REF <MODULE>-<TOPIC>-<NNN>` – module prefix, topic prefix (B/R/K/F number or a speaking name), running number per topic, e.g. `# → REF PAN-R9-1`.
- Module prefixes: `ENT` (previewer.py), `PAN` (previewer\_panel.py), `SEL` (previewer\_select.py), `UT` (previewer\_util.py), `TB` (previewer\_toolbar.py), `MED` (previewer\_render\_media.py), `DOC` (previewer\_render\_docs.py), `TXT` (previewer\_render\_text.py).
- Out-sourced are comment runs of 5 connected lines or more. What does NOT migrate: STAND-/version lines, PREVIEWER\_VERSION, one-line section titles and short inline hints. Since F49 (2026-11-02, user request) ALL function and class docstrings migrate as well – every docstring gets its own marker and its own entry (topic DOC, running number per module); only the module head docstring stays in the code (version anchor).
- Entries here: ID, module, location (function/block), reason in one sentence, the out-sourced comment text in a text block (English since F49 — the original German comments are preserved in the git history).
- This file is a LIVING project document: it is maintained continuously and extended with every comment rework. It is deliberately NOT deployed – the extension does not need it at runtime; deployment copies only the \*.py files.

**Topic prefixes in this document:** B (bugfix), R (robustness), K (cosmetics), F (feature) plus speaking prefixes for code topics without ticket number (e.g. FILTER, VTABLE, HR).

---

## Entry point (ENT)

### ENT-FILTER-1 – Gtk protocol filter

- **Module:** previewer.py
- **Location:** module level, below the section title “Gtk protocol filter”, above `_GTK_FOREACH_MSG` / `_install_log_filter()`
- **Reason:** When switching folders, Gtk prints a critical message for already half-destroyed widgets – exactly this one message is filtered.

```text
# When switching folders, Nemo tears down the old slot. While doing so, GTK sometimes prints the message gtk_container_foreach: assertion 'GTK_IS_CONTAINER (container)' failed for widgets that are already half-destroyed – even when foreign code (like this extension) only reads the tree. Exactly THIS one message is suppressed; all other Gtk messages stay visible.
```

### ENT-TOGGLE-1 – Preview toggle in Nemo's toolbar (F40)

- **Module:** previewer.py
- **Location:** `PanelState._install_toolbar_toggle` (retrofitted in `_view_ok`), feedback channels `_on_toolbar_toggle`/`_on_panel_visibility`, helpers `_pack_toggle`/`_find_first_widget`/`_pos_after_view_buttons`/`_has_view_icon`
- **Reason:** The user wanted the on/off toggle out of the panel header and into Nemo's toolbar, next to the view selector. The first assumption, that Nemo's toolbar is a GtkHeaderBar subclass, did not hold on classic Nemo (Cinnamon): get\_titlebar() returns NULL, the button never appeared. Nemo offers no official extension API for the toolbar – but NemoToolbar is just a GtkBox, and the view buttons sit in a GtkToolbar from the UIManager. Hence two installation routes: route 1 for CSD (title bar is a GtkHeaderBar) – GtkToggleButton via pack\_end; in GTK3 pack\_end takes ONLY the child argument, more arguments raise a TypeError. Route 2 classic – \_find\_first\_widget searches the widget tree for the first GtkToolbar, \_pos\_after\_view\_buttons places the GtkToggleToolButton directly behind the last view button (recognized by the view-… icon of its Gtk.Image), without a hit insert(-1) appends at the end. Two synchronisation cases: the button toggles the same panel as Ctrl+Alt+P (toggled → show/hide), and conversely notify::visible on the panel updates the button (show-at-start setting, keyboard shortcut) – both directions converge because set\_active on the unchanged value no longer fires toggled. Since 0.34.1 (F40 follow-up, user finding): the button did not show the open state at startup – notify::visible only fires on changes, but the panel is already visible when packing (the injection calls show all), so the button never caught up. \_pack\_toggle therefore synchronizes directly when packing: set\_active on the panel state, BEFORE the toggled connect (fires nothing).

```text
        # PanelState is created exactly once per window, but the reconciliation (_reconcile) runs several times – the button is remembered on the window object (Python attribute, not GObject set_data – PyGObject blocks the data methods) and never packed twice. The installation happens deferred in _view_ok, because the toolbar may theoretically not be in place yet during the first PanelState build. Two installation routes: a GtkHeaderBar as title bar (CSD) receives a GtkToggleButton via pack_end (ONLY the child argument!); classic Nemo gets the GtkToolbar in the widget tree marked and a GtkToggleToolButton directly behind the view buttons. The icon choice runs through pick_icon: not every Mint/Nemo theme provides every name – the first existing one wins, the last fallback (pan-end-symbolic) always exists in GTK itself. Without header bar and GtkToolbar, Ctrl+Alt+P remains (dbg hint).
```

### ENT-DOC-1 – Docstring: PanelState (class)

- **Module:** previewer.py
- **Location:** class `PanelState`
- **Reason:** Per-window state, stored on the window object.

```text
State per Nemo window (stored on the window object).
```

### ENT-DOC-2 – Docstring: \_install\_toolbar\_toggle

- **Module:** previewer.py
- **Location:** `PanelState._install_toolbar_toggle` (method)
- **Reason:** F40 – installs the preview on/off button in Nemo's toolbar.

```text
F40 (user request): on/off button for the preview side panel in Nemo's toolbar, next to the view selector. The state stays synchronized: Ctrl+Alt+P and the button toggle the same panel, notify::visible pulls it along.
```

### ENT-DOC-3 – Docstring: \_pack\_toggle

- **Module:** previewer.py
- **Location:** `PanelState._pack_toggle` (method)
- **Reason:** F40 – finishes, packs, wires and logs the toggle button.

```text
F40: finish the button, pack it, wire it up, log it.
```

### ENT-DOC-4 – Docstring: \_find\_first\_widget

- **Module:** previewer.py
- **Location:** `PanelState._find_first_widget` (method)
- **Reason:** F40 – recursive widget-tree search for the first match.

```text
F40: search the widget tree recursively, return the first match.
```

### ENT-DOC-5 – Docstring: \_pos\_after\_view\_buttons

- **Module:** previewer.py
- **Location:** `PanelState._pos_after_view_buttons` (method)
- **Reason:** F40 – insert position behind the last view button.

```text
F40: position directly behind the last view button of the toolbar (its icon is called view-…-symbolic). Without a match -1, insert() then appends at the end.
```

### ENT-DOC-6 – Docstring: \_has\_view\_icon

- **Module:** previewer.py
- **Location:** `PanelState._has_view_icon` (method)
- **Reason:** F40 – checks recursively for a view-… icon.

```text
F40: Does the widget (recursively) carry a view-…-icon? (Gtk.Image).
```

### ENT-DOC-7 – Docstring: \_on\_toolbar\_toggle

- **Module:** previewer.py
- **Location:** `PanelState._on_toolbar_toggle` (method)
- **Reason:** F40 – the button toggles the same panel as Ctrl+Alt+P.

```text
F40: the button toggles the same route as Ctrl+Alt+P.
```

### ENT-DOC-8 – Docstring: \_on\_panel\_visibility

- **Module:** previewer.py
- **Location:** `PanelState._on_panel_visibility` (method)
- **Reason:** F40 – keeps the button in sync when the panel is toggled elsewhere.

```text
F40: panel toggled elsewhere – pull the button state along.
```

### ENT-DOC-9 – Docstring: \_on\_hpaned\_draw

- **Module:** previewer.py
- **Location:** `PanelState._on_hpaned_draw` (method)
- **Reason:** F46 X – paints the unpainted Paned handle window.

```text
F46 X (0.34.1, user finding): the left edge of the preview column belongs to the handle window of the injected Gtk.Paned – unpainted, a black frame in light mode. The panel's painter paints the same area with the chain color (→ REF PAN-BG-2).
```

### ENT-DOC-10 – Docstring: \_reconcile

- **Module:** previewer.py
- **Location:** `_reconcile(st)` (module level)
- **Reason:** Core injection – anchors the panel at the right window edge.

```text
Anchor the panel at the right edge of the Nemo window. Technique: the direct child of the window's main box that contains the file view (the Nemo 'Pane') is wrapped into our HPaned: [ Pane | Panel ]. The panel thus sits reliably at the right edge and keeps its position across tab switches.
```

### ENT-DOC-11 – Docstring: \_detach

- **Module:** previewer.py
- **Location:** `_detach(st)` (module level)
- **Reason:** Reverse injection – restores the original widget structure.

```text
Detach the panel from the widget tree and restore the original structure.
```

### ENT-DOC-12 – Docstring: \_connect\_view\_signals

- **Module:** previewer.py
- **Location:** `_connect_view_signals(st, view)` (module level)
- **Reason:** Dynamically discovers and connects selection signals.

```text
Discover and connect selection signals dynamically. Instead of guessing a fixed signal name, all void signals with 'select' in the name are connected in the view's subtree and on the AtkSelection objects – so it does not matter whether Nemo uses hyphens or underscores. Connected per widget; the handler IDs land as (object, ID) pairs in st.view_handlers.
```

### ENT-DOC-13 – Docstring: \_dump\_a11y\_once

- **Module:** previewer.py
- **Location:** `_dump_a11y_once(st)` (module level)
- **Reason:** A11y tree dump, at most twice, only with VERBOSE_DIAG.

```text
Print the view's a11y tree at most twice: once after connecting (base state) and once at the first selection signal (state after the click). The lines show depth, child count, role, names, AtkSelection counters and SELECTED/FOCUSED – making it visible where Nemo actually serves the selection from. Only with VERBOSE_DIAG – silent in daily operation.
```

### ENT-DOC-14 – Docstring: \_view\_ok

- **Module:** previewer.py
- **Location:** `_view_ok(self, view)` (module level, patched onto PanelState)
- **Reason:** Signal registration after successful injection.

```text
Signal registration (self is a PanelState here via the extension below).
```

### ENT-DOC-15 – Docstring: \_refresh\_soon

- **Module:** previewer.py
- **Location:** `_refresh_soon(st)` (module level)
- **Reason:** Leaves the signal context before the refresh runs.

```text
Schedule the selection refresh into the main loop (leave the signal context).
```

### ENT-DOC-16 – Docstring: \_poll

- **Module:** previewer.py
- **Location:** `_poll(st)` (module level)
- **Reason:** Timer-driven reconciliation and selection sync.

```text
Timer: reconciliation + selection sync as a safety net.
```

### ENT-DOC-17 – Docstring: \_on\_window\_destroyed

- **Module:** previewer.py
- **Location:** `_on_window_destroyed(window, st)` (module level)
- **Reason:** 0.9.1 – tears down the poll timer with the window.

```text
The window is torn down (0.9.1): clear the 500 ms poll timer – otherwise it would keep running as a zombie forever after the window's end.
```

### ENT-DOC-18 – Docstring: \_on\_crowbar\_placed

- **Module:** previewer.py
- **Location:** `_on_crowbar_placed(crowbar, window, uri, tries)` (module level)
- **Reason:** Idle callback – injects the panel once the crowbar is in the tree.

```text
Idle callback: the crowbar is in the tree now → inject the panel. 0.9.1: the folder path is NOT set from the (possibly outdated) uri anymore – _get_widget already writes st.dir_path synchronously when requesting the crowbar. Otherwise an old crowbar placed only AFTER a newer one could overwrite the current path with an OLD path.
```

### ENT-DOC-19 – Docstring: \_is\_desktop\_window

- **Module:** previewer.py
- **Location:** `_is_desktop_window(window)` (module level)
- **Reason:** Keeps desktop windows free of a preview panel.

```text
Detects desktop windows so no preview panel lands there.
```

### ENT-DOC-20 – Docstring: \_get\_widget

- **Module:** previewer.py
- **Location:** `_get_widget(self, uri, window)` (module level)
- **Reason:** LocationWidgetProvider – returns the invisible crowbar box.

```text
LocationWidgetProvider: returns the invisible 'crowbar'.
```

---

## Panel core (PAN)

### ENT-MODDIR-1 – Module subfolder nemo-previewer-modules (0.35.0)

- **Module:** previewer.py (import path), INSTALL.md (instructions)
- **Location:** import block before `from previewer\_util import …`; dbg line after install\_step\_trace; WARNING message of the version check
- **Reason:** User request (2026-11-01): The extension folder shall be tidied up – only the entry file previewer.py stays directly under nemo-python/extensions (Nemo only loads there), the seven module files move into the subfolder nemo-previewer-modules. The entry point extends the existing \_HERE mechanism: \_MODDIR = subfolder next to the entry file; if it exists, it lands on the import path via sys.path.insert(0) BEFORE the extension folder – flat legacy copies (flat layout up to 0.34.1) therefore lose against the subfolder files, no matter in which order they were inserted. If the subfolder is missing, everything keeps running flat as before (backwards robustness). dbg “Module dir: …” confirms the active path at each start; the WARNING message of the version check now names both locations. The modules keep importing each other via their plain names – no package, no \_\_init\_\_, the import mechanism stays unchanged.

```text
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# 0.35.0 (user request): the seven module files live in the subfolder nemo-previewer-modules – it sits on the import path BEFORE the extension folder, so the new files win even if flat legacy copies were in the extension folder (→ REF ENT-MODDIR-1).
_MODDIR = os.path.join(_HERE, "nemo-previewer-modules")
if os.path.isdir(_MODDIR) and _MODDIR not in sys.path:
    sys.path.insert(0, _MODDIR)
```

### PAN-B8-1 – KeyFile resolver (B8)

- **Module:** previewer\_panel.py
- **Location:** module level, before the try block around `_KEYFILE_CLS` / `_KEYFILE_FLAGS_NONE`
- **Reason:** B8 (0.12.1): Gio.Keyfile does not exist – GKeyFile is bound in PyGObject as GLib.KeyFile; defensive resolver with dbg instead of silence.

```text
# B8 (0.12.1): PyGObject binds GKeyFile as GLib.KeyFile (GLib, NOT Gio – 0.12.0 reached for Gio.Keyfile and failed loudly in the field with "'gi.repository.Gio' object has no attribute 'Keyfile'"). Resolve both names defensively (same reasoning as for the Discoverer in _media_probe_async); if the class is missing entirely, dbg the load/save paths and the defaults stay in place.
```

### PAN-R2-1 – Render generation (R2)

- **Module:** previewer\_panel.py
- **Location:** `__init__`, above `self._pdf_gen = 0`
- **Reason:** The render generation is incremented by `_clear_content`; idle follow-ups use it to recognize stale previews (a `self._path` comparison would trigger falsely with the office cache).

```text
        # R2: render generation – _clear_content increments it; the idle supply steps use it to tell whether their preview is still current. (A self._path comparison would trigger FALSELY: office renders its PDF from the cache while self._path keeps pointing at the ODT/DOCX.)
```

### PAN-F12-1 – Config defaults in the constructor (F12)

- **Module:** previewer\_panel.py
- **Location:** `__init__`, above `self._conf_show_at_start = True`
- **Reason:** F12 (0.12.0/0.13.0): set defaults first, then read the conf file over them; applied at every start. 0.27.0 (F12 part 3) hooks in here – the keys doc\_page\_limit (limit yes/no) and doc\_max\_pages (1–999, default 20 = the former MAX\_PDF\_PAGES); the marker \_last\_docview lets changes act live on the displayed document preview.

```text
        # F12 (0.12.0/0.13.0): configuration of the preview column – values from ~/.config/nemo-previewer/nemo-previewer.conf, applied at every start (see _config_load/apply_start_settings). Set defaults first, then read the file over them.
```

### PAN-F23-1 – Sniffer call in the dispatch (F23)

- **Module:** previewer\_panel.py
- **Location:** `_render_inner`, above `self._render_text(path)`
- **Reason:** Files without extension are mostly text; the Gio MIME rater only knows popular names – the sniffer decides by content. 0.42.2 (B10): the extensionless special route merged into the unified B10 branch (→ PAN-B10-1).

```text
            # F23: files without extension are usually text (notes, dotfiles, scripts without a suffix) – Gio's MIME rater only guesses popular names like README/Makefile. The sniffer decides by content; binary files without an extension (executables, core dumps) fall through and stay generic.
```

### PAN-F47-1 – Sniffer fallback for opaque types (F47)

- **Module:** previewer\_panel.py
- **Location:** `_render_inner`, new branch before `self._render_generic()`; additionally .theme/.old/.bak/.orig in \_TEXT\_EXTRAS and the new \_OPAQUE\_TYPES at the module head (0.42.2/B10: \_OPAQUE\_TYPES removed, → PAN-B10-1)
- **Reason:** User finding (2026-10-31): plain text files got no text preview because the MIME database rater only reads the NAME – index.theme counted as application/x-theme, .xsession-errors.old as application/x-trash (“backup copy”); .xsession-errors on the other hand, as a dotfile, has NO extension (splitext counts the leading dot as part of the name) and ran straight into the F23 sniffer. Fix: (1) .theme/.old/.bak/.orig into the extension whitelist \_TEXT\_EXTRAS (.swp stays out – Vim swap is binary); (2) for “opaque” types (application/x-trash, application/x-theme, application/octet-stream) the dispatch lets the sniffer decide over the CONTENT before the preview gives up – readable text gets the text preview, binaries fail at the threshold (NULL bytes, ≥ 5 % control characters within the first 4 KB). From now on, unknown extensions with text content also get a preview.

```text
        elif mime in _OPAQUE_TYPES and _sniff_is_text(path):
            self._render_text(path)
```

0.42.2 (B10): The opaque special route merged into the B10 branch (→ PAN-B10-1); the binary blacklist \_SNIFF\_BINARY\_MIMES takes the place of \_OPAQUE\_TYPES.

### PAN-B10-1 – Sniffer as the last instance (B10)

- **Module:** previewer\_panel.py
- **Location:** `_render_inner`, last elif branch before `self._render_generic()`; additionally \_SNIFF\_BINARY\_MIMES at the module head and the UTF-8 decoding probe in \_sniff\_is\_text
- **Reason:** User finding (2026-11-02): readable text files with extensions whose guessed MIME type was neither text/* nor “opaque” (.pub, .crt, .csr, .pref …) fell through to the generic preview despite readable content – the sniffer only applied to extensionless files (F23) and opaque types (F47). Fix: The dispatch now consults \_sniff\_is\_text ALWAYS as the last instance before the generic fallback, regardless of extension and MIME; images/audio/video/PDF/fonts/office stay out via the earlier dispatch branches, known binary types (zip, gzip, x-tar, x-bzip2, x-xz, x-7z-compressed, x-rar, x-executable, x-sharedlib, x-ms-dos-executable) via the blacklist. \_sniff\_is\_text checks in two stages: NULL bytes and ≥ 5 % control characters within the first 4 KB, then the UTF-8 decoding probe – a head with ≥ 30 % 8-bit bytes that do not decode as valid UTF-8 counts as packed/encrypted (Latin-1 text stays allowed); on every sniffer hit a dbg line logs the guessed MIME.

```text
        elif mime not in _SNIFF_BINARY_MIMES and _sniff_is_text(path):
            dbg("panel/_render_inner: B10 sniff: %s -> text (mime %s)"
                % (os.path.basename(path), mime))
            self._render_text(path)
```

### PAN-BILD-1 – Minimum height with keep\_height

- **Module:** previewer\_panel.py
- **Location:** `_apply_scale`, above `if item["keeph"]:`
- **Reason:** The minimum height keeps the container at image height; the scroll position is reset after the grow/shrink cycle.

```text
                # Minimum height only with keep_height: keeps the container at image height when it is not packed expanding (otherwise the image would be cut off at the bottom). Also reset the scroll position – after a grow/shrink cycle the image would otherwise sit shifted.
```

### PAN-FOLDER-1 – Folder preview as a content list (F43)

- **Module:** previewer\_panel.py
- **Location:** `_render_folder`
- **Reason:** User request: instead of a folder icon, the preview shows the content as a list. os.scandir separates folders and files; folders are shown first (bold, right column “folder”), then files (right column size via human\_size), each alphabetically case-insensitive. K1 stays: ALL entries count, hidden ones are reported separately by the header hint; since 0.30.0 they appear dimmed in the list only when Nemo shows them. Cap: only the first 300 rows are built as widgets (Gtk.ListBox in a ScrolledWindow), the rest as a dim footer “… and N more”. Names with MIDDLE ellipsize plus tooltip; folder names set bold via markup\_escape\_text. Since 0.29.0 (user request): a Gtk.Image with the entry's icon sits in front of every name – folders via inode/directory, files via Gio.content\_type\_guess on the name and content\_type\_get\_icon, MENU size, fallback folder resp. text-x-generic –, and the ListBox carries the inner padding of the text previews as margin (10/10/8/8 px). Since 0.30.0/0.30.1 (user request/finding): the icons are strictly symbolic – candidates from Gio.content\_type\_get\_icon with a -symbolic suffix checked against Gtk.IconTheme.has\_icon (0.30.1: otherwise GTK secretly loaded the colored full icon when the variant was missing, dark plates in dark mode), fallback folder-symbolic resp. text-x-generic-symbolic – and therefore follow the system theme (light in dark mode, dark in light mode); the list shows hidden entries only when Nemo does (org.nemo.preferences show-hidden-files, Ctrl+H). Since 0.31.1 (user finding): the dark plates reappeared even under the strict symbol loading course; per render, dbg “Folder icons:” logs the map content type→chosen symbol to make the actually loaded theme symbols visible in the log. Since 0.31.2 (user finding): the 0.31.1 diagnosis was confirmed – the loading course consistently picks -symbolic names, but the WhiteSur theme itself provides colored icons under those names (dark plates) –, therefore \_render\_folder now redraws every chosen symbol as a monochrome silhouette in the list's foreground color: the alpha channel (shape) stays, RGB uniformly becomes the text color (helper \_silhouette, the redraw is cached once per symbol per render). Since 0.31.3 (user finding): the silhouette color now comes from the docked panel instead of the freshly built list that is not yet attached to the window – its context did not have a final theme yet, which made the icons white and invisible in light mode (F43 fix III); since then the dbg line additionally logs the extracted foreground color. Since 0.31.4 (user request): the list fills the column edge to edge – the outer margin of the content area (\_render\_inner resets it to 8 px per render, the folder branch zeroed it). Since 0.31.8 (F46 VI, user finding) the edge-to-edge request is withdrawn: only without the 8-px outer margin did the scroll window's own transparent GdkWindow reach the plate edge and show black; since then the margin stays in the folder branch too. Since 0.31.11 (F46 IX, user description): the 10/10/8/8 inner padding no longer sits as a ListBox margin in front of the plate (that exposed the list's black carrier, visible only with an overlong list), but as margins on the row contents – 10 px sideways per row, 8 px on top of the first and below the last; the plate fills the viewport edge to edge. Since 0.42.0 (spaghetti audit round 2, S2): \_render\_folder is only the flow – \_folder\_symbol picks and tints the icon, \_folder\_row builds one row, \_folder\_scroll wraps the scroll window including the F46 background safeguard; behaviour unchanged.

```text
        # Gtk.ListBox is not scrollable by itself – ScrolledWindow.add automatically puts a viewport underneath in GTK3. Selection NONE: the list is a preview, not a navigator – clicks stay with Nemo's file view, not in the panel. The 300-row limit is a pure widget cap: sort order and counting (K1) cover ALL entries, only the widget building stops – the same discipline as the bomb cap for images.
```

### PAN-FOLDER-2 – Folder content list configurable (F48)

- **Module:** previewer\_panel.py (dispatch + configuration), previewer\_toolbar.py (toggle)
- **Location:** `_render_inner` at the `is_dir` branch; defaults in `\_\_init\_\_`, load/save in \_config\_load/\_config\_save (key folder\_contents); settings window, section “General”
- **Reason:** User request (2026-10-31): the folder preview with content list (F43) stays the mandatory default – but switchable off. The toggle “Show folder contents in the preview” (default on, saved immediately) shows the plain folder icon with file information when deselected (the behaviour before 0.23.0); toggling rebuilds a currently selected folder live (os.path.isdir on \_path), file previews stay untouched. Unreadable and empty folders keep their hints (“Folder” / “The folder is empty.”), regardless of the toggle.

```text
        if is_dir:
            if self._conf_folder_contents:
                self._render_folder(path)
            else:
                self._render_generic()
```

### PAN-VCARD-1 – vCard dispatch (F7)

- **Module:** previewer\_panel.py
- **Location:** type chain in `_render`, directly after the `.eml` branch
- **Reason:** User request: ALL known contact card formats are rendered as a card, not as a text file – vCard (.vcf/.vcard, MIME text/vcard), LDIF (.ldif) and Windows-Contact (.contact); the extension check also catches the formats that shared-mime-info would only classify as text/plain resp. XML. The renderer \_render\_vcard lives in the text module; the dispatch branches off BEFORE the generic text/ branch so the MIME detection does not swallow the card as plain text.

```text
        elif (lower.endswith((".vcf", ".vcard", ".ldif", ".contact"))
              or mime == "text/vcard"):
            # F7: contact card formats – vCard, LDIF, Windows-Contact (renderer in the text module). → REF PAN-VCARD-1
            self._render_vcard(path)
```

### PAN-F44-1 – Optional GtkSource binding (F44)

- **Module:** previewer\_panel.py
- **Location:** module head, below the mixin imports
- **Reason:** 0.28.0 (user request): syntax highlighting in the text preview. GtkSourceView is loaded like Poppler in the docs module as an OPTIONAL binding; if it is missing (package gir1.2-gtksource-4), everything stays with the previous TextView. \_source\_language guesses the language from the file name, \_source\_scheme picks oblivion for a dark GTK theme (fallback solarized-dark), else classic. 0.28.1 (user request): switchable on/off via the setting text\_syntax (section “Text files”), default on.

```text
# → REF PAN-F44-1
HAVE_GTKSOURCE = False
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAVE_GTKSOURCE = True
except Exception:
    pass
```

### PAN-BG-1 – Panel paints its own background (F46)

- **Module:** previewer\_panel.py
- **Location:** `__init__`, directly after `set_size_request`
- **Reason:** User finding (0.31.3, screenshots dark/light mode): the black areas that had been taken for icon plates since 0.30.0 were the unpainted background of the preview column – above/below the folder list and in the scrollbar region no widget painted, and unpainted areas stay black; this only became visible with long lists (scrollbar present, margin areas empty), in light mode the theme happened to cover the areas. The style class background on the panel makes GTK paint the theme's normal window background color. Since 0.31.4 (user finding/request): the style class alone was not enough – GtkBox never calls gtk\_render\_background itself; the panel therefore paints the themed background in the draw signal (\_on\_panel\_draw) as the first thing, under all children – with the Nemo toplevel's style context, because the panel context might carry no resolved background color under WhiteSur-Dark. And the folder list fills the column edge to edge: \_render\_inner resets the content area's outer margin to 8 px per render, the folder branch zeroed it – the padding thus sits INSIDE the list window (user request).

```text
        # 0.31.3 (F46, user finding): style class background – the panel paints its own empty areas, otherwise they stay unpainted black (→ REF PAN-BG-1).
        self.get_style_context().add_class("background")
```

### PAN-BG-2 – Background chain instead of a fixed toplevel context (F46 III)

- **Module:** previewer\_panel.py
- **Location:** \_paint\_background / \_on\_panel\_draw; draw connect on the scroll window in \_render\_folder
- **Reason:** User finding (0.31.5, both modes): the 0.31.4 background via the toplevel style context stayed ineffective – first, WhiteSur apparently resolves no background color there, second, GtkScrolledWindow carries its own GdkWindow, so the panel painting never reaches the scrollbar region (Nemo's own list shows dark grey there, the panel showed black as soon as the folder list scrolled). The painter therefore runs as a chain: panel context (style class background), toplevel, context of the rendered content (Gtk.ListBox/Gtk.TextView – their plate is visibly painted after all), otherwise a base area derived from the foreground color (light in light mode, dark in dark mode). It additionally attaches to the folder list's scroll window – without its own GdkWindow the double painting would stay invisible. dbg “Panel bg:” logs the source and all candidate colors, but only on change (marker \_bg\_dbg\_key against a dbg flood in the draw signal); the folder diagnosis additionally reports scroll.get\_has\_window(). Since 0.31.6 (F46 IV, user finding): the black scrollbar layer stayed even under the chain – the painter therefore additionally attaches to the viewport and, after their realization (\_on\_scroll\_realized), to both scrollbars; dbg “Panel bg (widget):” names the widget painting each time, and \_dbg\_list\_margins reads back the ListBox margins after realization (CSS override suspicion against the vanished list padding). Since 0.31.7 (F46 V, user finding): dbg proved working painters (all four widgets, source=panel) and set margins (10/10/8/8) – the stripe stayed anyway; suspected causes: the draw painter runs before the widget's standard draw, theme areas (trough, viewport) cover it, and the margin stripes show the viewport background instead of the plate. The new method therefore additionally sets a CSS rule (class pvw-surface, application priority above the theme) on viewport and scrollbars (re-attached on realization), and the painter dbg names each widget's own context color in addition (“own=…”) – showing what the theme itself paints there. Since 0.31.8 (F46 VI, user finding): the user remembered correctly – before the edge-to-edge request from 0.31.4 there was no black background; only zeroing the outer margin let the scroll window's transparent GdkWindow reach the plate edge. The folder branch no longer zeroes the margin (the 8 px from \_render\_inner stay), the CSS rule additionally covers the scroll window itself and the junction, the dbg marker is per widget now (a single one made the lines pend endlessly – log flood), and the CSS dbg line only prints on color change. Since 0.31.9 (F46 VII, user finding): even under 0.31.8 the stripe stayed although all areas paint grey – \_dbg\_pixels (GLib.timeout\_add after the folder render) therefore reads real pixels at nine points (edge, scrollbar column at two depths, plate edge, column top/bottom, panel margin, plate center, in front of the panel) via Gdk.pixbuf\_get\_from\_window and dbg logs them as a “Panel pixels:” line – it reveals WHERE black actually sits. Since 0.31.10 (F46 VIII, pixel probe finding): the probes caught the black exclusively at column-2 (pw-12) – in the stripe between plate edge and scrollbar column, and only while the bar is visible (with short lists the spot is grey; the lower probe point shows rgb(48,48,48) – the undershoot fade ABOVE our grey – so the area is painted). Cause: overlay scrolling lets the bar float in its own Gdk window above the viewport, whose unpainted parts stay black. The folder list therefore switches to the classic inline bar via set\_overlay\_scrolling(False) – painter and CSS now bite reliably; the probes stay in as verification. The STAND line of previewer\_panel also carried \_-escapes in the module docstring (Python SyntaxWarning at every start) – removed. Since 0.31.11 (F46 IX, user description): the 0.31.10 test confirmed the inline bar (no probe point rgb(0,0,0) anymore; trough rgb(41,41,41), slider rgb(121,121,121) – the look of Nemo's own list), but the user kept seeing black and described the situation: the black layer is the CARRIER of the folder list (parent layer), visible only with an overlong list; the scrollbar itself is fine. Fix: the 10/10/8/8 padding now sits IN the plate – hbox margins (10 px sideways, 8 px on top of the first, below the last row content) instead of ListBox margins; the plate fills the viewport edge to edge and covers the carrier completely. Additionally \_dbg\_pixels reads a complete horizontal color profile at panel height as a panel scan (color runs compressed, black pixel counter) – it also shows stripes between the fixed probes. Since 0.34.1 (F46 X, user finding): the last unpainted area was the left margin of the preview column – the handle window of the injected Gtk.Paned (previewer.py), a black frame in light mode, invisible in dark mode. The painter therefore additionally attaches to the Paned (draw connect in PanelState, \_on\_hpaned\_draw paints the chain color over the Paned area, return False lets the handle's standard draw run). Since 0.38.1 (F46 XI, user finding): in light mode the margin stayed visible anyway – two color bugs: the fallback derivation in \_paint\_background was INVERTED (light FG → light instead of dark base, dark FG → dark instead of light; light mode painted almost black rgb(31,31,31)), and \_apply\_surface\_css fell back to hard rgb(56,56,56) when the panel context could not resolve; both derivations are contrast-correct FG-based since then (light FG → base 0.12 dark, dark FG → base 0.92 light), the CSS fallback FG-derived. Since 0.40.0 (spaghetti audit round 1): F46 is solved – the diagnosis machinery is removed (\_dbg\_pixels with pixel probes and panel scan, \_dbg\_list\_margins, the GdkWindow flag in the folder log line); the functional painters, the CSS rule and the folder icons diagnosis line stay.

```text
        # 0.31.5 (F46 III, user finding): GtkBox never calls gtk_render_background itself – therefore this hook paints the background BEFORE all children. It additionally sits on the folder list's scroll window: that one carries its own GdkWindow which the panel painting would otherwise never reach (→ REF PAN-BG-2).
        self._paint_background(widget, cr)
        return False
```

### PAN-K11-1 – Hide dashed undershoot hints (K11)

- **Module:** previewer\_panel.py
- **Location:** panel \_\_init\_\_, after the content area setup
- **Reason:** User finding (0.59.1): themes draw dashed lines at the scroll edges – hide them in the preview.

```text
K11 (0.59.1, user finding): GTK adds undershoot nodes to every GtkScrolledWindow at the edges where content is scrolled off and can be revealed by scrolling (node "undershoot" with .top/.bottom/.left/.right class) – the active theme paints them as dashed lines, so every scrollable preview showed them. FIRST ATTEMPT (0.59.1, ineffective): one CssProvider on the panel's own style context – gtk_style_context_add_provider applies to THAT context only and does NOT reach the descendant widgets' contexts (unlike add_provider_for_screen, which explicitly covers every context under the screen; our own _surface_css_contexts walk exists for exactly that reason). CORRECT MECHANISM (0.59.2): the panel gets the widget name "previewer-panel" (set_name, the rec-dot pattern) and the rule goes to the SCREEN via Gtk.StyleContext.add_provider_for_screen, but scoped by ancestor: "#previewer-panel undershoot, #previewer-panel .undershoot { background-image: none; background-color: transparent; }" – matching walks the widget path, so it hits the undershoot nodes of every scrolled window inside the panel while Nemo's own windows stay untouched. A module-level one-shot flag (_K11_STATE) installs the provider only once per process, not once per Nemo window.
```

### PAN-DOC-1 – Docstring: \_sniff\_is\_text

- **Module:** previewer\_panel.py
- **Location:** `\_sniff\_is\_text` (module level)
- **Reason:** Text sniffer as the last instance (F23/B10) – decides by content, not by name.

```text
F23/B10: Is a file readable text? Gio only guesses the MIME type from the file name – B10 calls the sniffer as the LAST instance, before the preview gives up: extension-less files (notes, dotfiles) and extensions whose guessed type is mapped nowhere (.pub, .crt, .csr, .pref …) get the text preview by CONTENT instead of by name. Quick look at the first bytes: NULL bytes and an excessive share of control characters (everything except tab/LF/CR) hint at binary data; B10 adds the UTF-8 decoding probe as a second criterion – a head made up of at least 30 % of 8-bit bytes that do NOT yield valid UTF-8 is packed/encrypted and fails (Latin-1 text stays allowed, umlauts mix in under plenty of ASCII). Encoding-agnostic – UTF-8 as well as Latin-1 text pass, random binary data reliably fails. The actual text preview still caps as always at 256 KB / 2000 lines.
```

### PAN-DOC-2 – Docstring: \_silhouette

- **Module:** previewer\_panel.py
- **Location:** `\_silhouette` (module level)
- **Reason:** Symbol icons as monochrome silhouettes in the fg color (0.31.2).

```text
0.31.2 (user finding): load the chosen symbol and redraw it as a monochrome silhouette in the foreground color. The 0.31.1 diagnosis showed that the loading course kept picking -symbolic names – but under those names the WhiteSur theme delivers colored icons of its own, which appear in dark mode as dark slabs with a hard edge. The redraw keeps the alpha channel of the original (shape) and sets RGB uniformly to the passed color – so the icon is light in dark mode and dark in light mode, whatever the theme smuggles in. Returns: Pixbuf or None (then the caller loads the symbol unchanged).
```

### PAN-DOC-3 – Docstring: PreviewPanel (class)

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel` (class)
- **Reason:** Class marker – the docked preview panel (right half of the Gtk.Paned).

```text
The docked preview panel (right half of the Gtk.Paned).
```

### PAN-DOC-4 – Docstring: \_bg\_content\_ctx

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_bg\_content\_ctx` (method)
- **Reason:** Style context of the rendered content – genuine colors for the background chain (F46).

```text
Style context of the rendered content (list/text view).

Its area is visibly painted – a background color resolved there is guaranteed genuine and matches the plate.
```

### PAN-DOC-5 – Docstring: \_derived\_base

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_derived\_base` (method)
- **Reason:** Contrast-correct base color from the panel fg color (F46 XI).

```text
Contrast-correct base from the panel fg color (0.38.1, F46 XI): bright fg → dark base and vice versa.
```

### PAN-DOC-6 – Docstring: \_paint\_background

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_paint\_background` (method)
- **Reason:** Paint the background beneath all children as a chain (F46 III).

```text
Paint the background beneath all children – as a chain (F46 III).

The first source with a resolved color wins; dbg names all candidates so the log shows what the theme delivers (→ REF PAN-BG-2).
```

### PAN-DOC-7 – Docstring: \_on\_scroll\_realized

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_on\_scroll\_realized` (method)
- **Reason:** Hook the scrollbars to the painter on realization (F46 IV/V).

```text
Hook the scrollbars to the painter (F46 IV) – they only appear on realization (→ REF PAN-BG-2). 0.31.7 (F46 V): also re-apply the surface CSS rule.
```

### PAN-DOC-8 – Docstring: \_apply\_surface\_css

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_apply\_surface\_css` (method)
- **Reason:** Surface CSS rule for the scroll areas above theme priority (F46 V).

```text
F46 V: set the background of the scroll surfaces via CSS.

The draw painter runs BEFORE the widget's standard draw – if the theme paints its own surface there (trough, viewport), it covers the painter. A CSS rule on the other hand colors in the regular paint pass, with application priority above the theme. The rule only applies below the class pvw-surface, so it never touches Nemo itself (→ REF PAN-BG-2).
```

### PAN-DOC-9 – Docstring: \_surface\_css\_contexts

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_surface\_css\_contexts` (method)
- **Reason:** Style contexts that also carry the surface provider directly (F46 V).

```text
Style contexts that additionally need the surface rule (F46 V) – providers do reach through the parent chain, but for safety they also sit directly on every child (→ REF PAN-BG-2).
```

### PAN-DOC-10 – Docstring: set\_selection

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.set\_selection` (method)
- **Reason:** Set the selection and re-render the preview.

```text
Set the selection and re-render the preview (names = file names). 0.56.0 (F2): heavy formats no longer render here directly – a pending debounced render is always cancelled first, then _is_heavy decides: light formats render immediately as before, heavy ones arm the _RENDER_QUIET_MS timeout (mechanism in PAN-DOC-33).
```

### PAN-DOC-11 – Docstring: \_render

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_render` (method)
- **Reason:** Build the preview for the current path – never throw, always fall back.

```text
Build the preview for self._path. Never throw – always fall back.
```

### PAN-DOC-12 – Docstring: \_on\_content\_size\_allocate

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_on\_content\_size\_allocate` (method)
- **Reason:** Fit the scaled preview to width changes without re-rendering (0.41.0); F68: exception font waterfall.

```text
Watch width changes of the preview area (the user drags the Gtk.Paned divider). It does NOT re-render – instead only the displayed pixbuf of the scalable preview is fitted to the new width immediately (cheap, no re-decoding). 0.41.0: A dragged width only applies to the running session and no longer changes the START WIDTH – that lives solely in the settings window. F68 (0.58.3): one exception re-renders after all – the font waterfall \_apply\_font\_scale rebuilds its surface at the new width so the sample text re-wraps live (user bug report: the faces grew while the wrap stuck to the old width).
```

### PAN-DOC-13 – Docstring: \_scaled\_image

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_scaled\_image` (method)
- **Reason:** Registration and initial scaling of a live-scaling image (S6/R3/0.17.0).

```text
Gtk.Image that lives with the panel width. The source (src) stays in memory at full resolution; the displayed pixbuf is re-scaled live on width changes. The image sits in a ScrolledWindow so its minimum width does not block the Gtk.Paned when shrinking (that was the stutter cause). upscale=True lets small sources (e.g. office thumbnails) grow with the panel width – capped by max_upscale so tiny thumbnails are not blown up into unreadable mush. keep_height=True only with non-expanded packing (office, cover, video frame): holds the container at image height so the image is not cut off at the bottom under space pressure. With expanded packing (PDF) NO minimum height may be set – portrait images would otherwise force their height onto the window. 0.17.0: frac_h (e.g. 0.6) caps the display height at this fraction of the COLUMN HEIGHT – live, because _apply_scale pulls anew on every window resize. Used by the image preview (user wish: max. 60 % of the column, a separator and later additional information below it); embedded images (cover, office thumbnail, video frame) stay without frac. R3: the scaling parameters sit as a Python data dict EACH on the image entry in self._scale_items instead of single panel attributes – several live-scaled images per preview (cover + chapter images …) no longer overwrite each other. (Deliberately NOT Gtk set_data/get_data: PyGObject blocks the GObject data methods with 'Data access methods are unsupported' – the panel would otherwise crash on the first image.) Returns the finished container (Gtk.ScrolledWindow). S6 (0.42.0): the widget construction lives as build_scaled_image() in previewer_util; registration and initial scaling stay here.
```

### PAN-DOC-14 – Docstring: \_apply\_scale

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_apply\_scale` (method)
- **Reason:** Fit all registered preview images to the panel width (R3); since the image-backlog fix the rescale runs generation-guarded in idle steps like the PDF path (K12).

```text
Fit the displayed pixbufs of ALL registered preview images to the current panel width (R3: list instead of a single slot; entries are data dicts, see _scaled_image). Backlog fix (live deploy report: image previews fell behind on fast width changes, same phenomenon the Office/PDF path had): _apply_scale no longer loops synchronously – it bumps _img_scale_gen (init 0 next to _pdf_scale_gen) and schedules _scale_step(0, gen) via GLib.idle_add. _scale_step scales exactly ONE item per call, re-arms itself with GLib.idle_add(_scale_step, i + 1, gen) and stops early on a stale generation (a newer resize or a clear ran – return False drops the idle source). Rapid width changes (divider drag, the reset arrow of _on_reset_width_clicked/F63) cancel older passes instead of queueing scale_simple calls; the UI stays responsive between items. _scale_item itself is unchanged (lastw/lasth thresholds still dampen micro-changes).
```

### PAN-DOC-15 – Docstring: \_scale\_item

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_scale\_item` (method)
- **Reason:** Fit one registered preview image (R3/0.17.0).

```text
Fit ONE preview image to the panel width (R3/0.17.0) – height cap fresh, upscale limited, skip changes below 4 px (early return instead of nesting).
```

### PAN-DOC-16 – Docstring: \_preview\_width

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_preview\_width` (method)
- **Reason:** Live preview width from the content allocation.

```text
Width available to the preview objects. Live from the current area of the content region (get_allocated_width), so the preview can scale with the panel width; the start width only serves as a fallback as long as no size allocation has happened yet.
```

### PAN-DOC-17 – Docstring: \_preview\_height

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_preview\_height` (method)
- **Reason:** Live content height – basis of the image height cap (0.17.0).

```text
0.17.0: height of the content region – basis for the height cap of the image preview (max. 60 % of the column height, user wish: room below the image for a separator and additional information). Live from the current area, fallback as long as no size allocation has happened yet.
```

### PAN-DOC-18 – Docstring: \_source\_language

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_source\_language` (method)
- **Reason:** GtkSource language guess from the file name (F44).

```text
F44 (0.28.0): guess the file's language via the GtkSource LanguageManager (from the name). None means: no language recognized – the normal text preview stays in place.
```

### PAN-DOC-19 – Docstring: \_source\_scheme

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_source\_scheme` (method)
- **Reason:** Match the GtkSource color scheme to the system theme (F44).

```text
F44 (0.28.0): match the color scheme to the system theme – a dark theme (gtk-theme-name contains “dark” or prefer-dark set) gets a dark scheme (oblivion, solarized-dark as a fallback), otherwise the light “classic”. If a candidate is missing, the widget default applies.
```

### PAN-DOC-20 – Docstring: \_text\_view

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_text\_view` (method)
- **Reason:** Configured TextView; the construction lives in previewer_util (S6).

```text
Fully configured TextView in a ScrolledWindow, packed into self._content. font: Pango description; None keeps the GTK theme's system font (i.e. the system font size) and does not call override_font at all. markup: optional Pango markup string (must be validated beforehand); without markup the raw text is set. linenumbers (F24): line numbers on the left margin – only set by _render_text (text files and extension-less text files), rendered previews (Markdown, e-mail, e-book, font waterfall) stay without. source_path (F44, 0.28.0): file whose language GtkSourceView shall guess – if a language is recognized, syntax highlighting shows up; without a binding or language it stays a normal TextView. S6 (0.42.0): configuration and buffer filling live as build_text_view() in previewer_util. 0.55.0 (F25): passes the config value _conf_text_line_spacing as the spacing argument – the line spacing therefore flows centrally into ALL TextView previews (plain text, Markdown, e-mail, e-book, font), unlike the line numbers which only the plain text preview has.
```

### PAN-DOC-21 – Docstring: \_install\_line\_numbers

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_install\_line\_numbers` (method)
- **Reason:** Line numbers in the TextView margin – excluded from every copy (F24).

```text
F24 (0.16.0): draw line numbers into the left margin of the TextView – not into the text buffer. That excludes them from the selection, and they NEVER end up in the copied text (user wish: numbers not copyable, text yes), while the text itself stays normally selectable and copyable. The draw handler fires on every redraw (also while scrolling) and draws only the visible lines; wrapped lines get their number on the first visual line. 0.55.1 (deploy feedback "the numbers sit offset vertically"): the number font is 80 % of the text size, but was drawn at the line box top + 1 px – so it sat too high. It now centers vertically on the TEXT area: offset = spacing + (line height - spacing - number height) / 2, floored at 0; spacing is the F25 line spacing passed in from _text_view, because get_line_yrange counts the pixels-above space at the top of the line box – centering on the whole box would leave the number half the spacing too high.
```

### PAN-DOC-22 – Docstring: \_folder\_symbol

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_folder\_symbol` (method)
- **Reason:** Symbol icon of a folder row, redrawn as a silhouette (S2/0.31.2).

```text
S2 (0.42.0): symbol icon of a folder row – check candidates from the content type with -symbolic suffix against the theme (0.30.1), keep missing variants generic, never the colored full icon; every chosen symbol shape is redrawn as a silhouette in the foreground color (0.31.2, → REF PAN-FOLDER-1).
```

### PAN-DOC-23 – Docstring: \_folder\_row

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_folder\_row` (method)
- **Reason:** One row of the folder list: icon, name, size (S2).

```text
S2 (0.42.0): one row of the folder list – icon, name (folders bold, hidden entries dimmed), size on the right. The plate padding (10 px sideways, 8 px on top of the first row) sits on the row content, not on the ListBox (0.31.11, → REF PAN-FOLDER-1).
```

### PAN-DOC-24 – Docstring: \_folder\_scroll

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_folder\_scroll` (method)
- **Reason:** Scroll window of the folder list with the F46 safeguarding (S2).

```text
S2 (0.42.0): scroll window of the folder list with the full F46 background safeguarding – inline bar instead of overlay (0.31.10), painter on scroll window and viewport (0.31.5/0.31.6), CSS rule on top (0.31.7) (→ REF PAN-BG-2).
```

### PAN-DOC-25 – Docstring: \_render\_folder

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_render\_folder` (method)
- **Reason:** Folder preview as a content list (F43/S2).

```text
F43 (user wish): the folder preview shows the content as a list instead of just a folder icon – folders first (bold), then files, each alphabetical; per row icon, name plus “Folder” or size. Since 0.29.0 (user wish): the type icon from the icon theme in front of every name, the list carries the inner padding of the text previews (10/10/8/8 px). Since 0.30.0 (user wish): the icons are symbolic and follow the system theme (light in dark mode, dark in light mode); hidden entries only appear in the list when Nemo shows them (Ctrl+H, org.nemo.preferences show-hidden-files), otherwise the head hint reports them by count (K1). Huge folders: the first 300 rows in the scroll window, the rest as a footer – otherwise a folder with ten thousand entries built just as many label widgets. S2 (0.42.0): decomposed – _folder_symbol, _folder_row and _folder_scroll build icon, row and scroll window; only the flow remains here.
```

### PAN-DOC-26 – Docstring: \_on\_panel\_destroy

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_on\_panel\_destroy` (method)
- **Reason:** Stop playback and timers when the panel is torn down (B3).

```text
Panel is torn down: stop playback and timers (B3). 0.65.5 (F71): the F2 pending-render timer and the F25 line-spacing quiet timer are cancelled here too – no one-shot fires into the dead widget tree.
```

### PAN-DOC-27 – Docstring: \_config\_load

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_config\_load` (method)
- **Reason:** Read the settings; defaults on any failure (F12).

```text
F12 (0.12.0): read the settings from CONF_FILE. Without a file or on ANY failure the defaults apply – a broken or half-written configuration must never stop Nemo from starting. New settings dock here as get_boolean/get_string with try/except. 0.53.0 (F65): the debug_log boolean docks here like every setting; on True the panel calls set_debug_log(True) right after loading – late enough for the config, early enough for all runtime dbg lines (the module-load lines of the other modules may be missing from the log when only the toggle is on; NEMO_PREVIEWER_DEBUG=1 catches them too). 0.55.0 (F25): the integer text_line_spacing docks here with a range check (0–12, values outside are ignored).
```

### PAN-DOC-28 – Docstring: \_config\_save

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_config\_save` (method)
- **Reason:** Write the settings immediately after every change (F12).

```text
F12 (0.12.0): write the settings to CONF_FILE immediately (creating the directory if needed). Called after every change in the settings window – a separate save button is therefore unnecessary. 0.53.0 (F65): persists the debug_log boolean like every other setting. 0.55.0 (F25): persists the integer text_line_spacing.
```

### PAN-DOC-29 – Docstring: apply\_start\_settings

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.apply\_start\_settings` (method)
- **Reason:** Apply the loaded configuration after show_all (F12).

```text
F12 (0.12.0): apply the loaded configuration to the panel. Called by the entry point AFTER the show_all of the injection – otherwise a requested invisibility would be overridden immediately at startup. New start settings dock here.
```

### PAN-DOC-30 – Docstring: \_apply\_panel\_width\_live

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_apply\_panel\_width\_live` (method)
- **Reason:** Apply a new start width live from the settings window (F12).

```text
F12 (0.13.0): apply a new start width immediately while the settings window is open – the user sees the effect directly. The Paned position is set so that the preview column is self._panel_width wide; if that fails (window too small), everything stays unchanged.
```

### PAN-DOC-31 – Docstring: \_on\_reset\_width\_clicked

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_on\_reset\_width\_clicked` (method)
- **Reason:** F63 reset button – one click back to the configured column width.

```text
F63 (user wish 2026-11-04): the new header button right next to "Open with the default application" resets the preview column to the default width (PANEL_WIDTH, 350 px) with a single click – the exact same course as the settings spin button: no-op if the width already matches, then self._panel_width = PANEL_WIDTH, _config_save() (persists across restarts) and _apply_panel_width_live() (the Paned divider jumps immediately). Button: symbolic system icon via pick_icon – first hit zoom-fit-best-symbolic, then view-restore-symbolic, edit-undo-symbolic as the last resort; tooltip "Reset preview column to default width", relief off like the open button. pack_end packs the width button BEFORE the open button, so it ends up to its RIGHT (first pack_end = rightmost). 0.52.1 (deploy feedback): TWO fixes – (1) the button did NOTHING: the no-op guard compared self._panel_width, but dragging the divider has not updated _panel_width since 0.41.0 (drag tracking removed), so the guard always saw 350 == PANEL_WIDTH and returned; the guard now measures the LIVE column width (parent.get_allocated_width() − parent.get_position()) and a dbg line logs "panel/reset_width: <old> px -> <new> px". (2) Icon change (user wish, zoom-fit-best did not fit the style): sidebar-collapse-right-symbolic first, then sidebar-collapse-right, zoom-fit-best-symbolic as the last resort. 0.52.2 (user hint): sidebar-collapse-right is NOT part of the standard icon themes – the chain now ends in guaranteed-standard names: sidebar-collapse-right-symbolic → arrow-right-symbolic (nearest equivalent, stays symbolic like the icon discipline), absolute last resort arrow-right (non-symbolic, but always present). 0.52.3 (deploy feedback): the button jumped to the hardcoded PANEL_WIDTH (350 px) instead of the width the user CONFIGURED in the settings – _panel_width holds exactly that configured value (set by the settings spin button and the config load; dragging never touches it since 0.41.0), so the handler now restores the live width to self._panel_width WITHOUT overwriting it: no _panel_width = PANEL_WIDTH, no _config_save() (the config was never wrong), just _apply_panel_width_live(); the no-op guard compares cur == self._panel_width, the dbg line logs the dynamic target ("panel/reset_width: <old> px -> <configured> px"), and the tooltip reads "Reset preview column to configured width". 0.65.6 (deploy feedback, Linux Mint 22.3): arrow-right is NOT always present either – the preinstalled Mint-Y theme lacks it, and pick_icon handed out the unchecked fallback, so the button rendered blank. The chain gains go-next-symbolic as a further symbolic candidate and go-next as the checked fallback (the standard navigation icon, guaranteed in Mint-Y), and pick_icon itself (UT-DOC-4) now verifies the fallback and returns image-missing as the absolute last resort.
```

---

### PAN-DOC-32 – Docstring: \_update\_rec\_dot (F65, 0.54.0)

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_update\_rec\_dot` (method) and the recording dot construction in `\\_\\_init\\_\\_`
- **Reason:** F65 – make active debug logging visible in the header, live in both directions.

```text
F65 (0.54.0, user wish): a red recording dot at the left of the header signals active debug logging. Construction in __init__: Gtk.Image with the standard icon media-record-symbolic (icon naming spec – the standard themes ship it, keeps the symbolic icon discipline), widget name previewer-rec-dot, recolored red (#e01b24) via a small CssProvider on the widget's own style context (same pattern as TB-CSS-1, no Gdk import), no_show_all so it can hide cleanly. _update_rec_dot mirrors the live state via set_visible(debug_log_active()) – called once after construction (covers config toggle AND NEMO_PREVIEWER_DEBUG=1) and from the settings toggle handler, so switching is live in both directions. Env var rule: with NEMO_PREVIEWER_DEBUG=1 the dot stays visible even when the toggle goes OFF – logging IS still on then. Tooltip "Debug logging is active". The panel also calls debug_log_cleanup() after _config_load (F65b log retention, see UT-LOG-1). 0.54.1 (deploy feedback): \_update\_rec\_dot uses the battle-tested show()/hide() pair instead of set\_visible, and the icon goes through pick\_icon with the media-record fallback (non-symbolic, also standard) – if media-record-symbolic is missing in a theme, the dot still renders.
```

### PAN-DOC-33 – Docstring: \_on\_pending\_render (F2)

- **Module:** previewer\_panel.py
- **Location:** `PreviewPanel.\_on\_pending\_render` (method) with `\_cancel\_pending\_render`, `\_is\_heavy` and the `\_RENDER\_QUIET\_MS` constant; armed in `set\_selection` (PAN-DOC-10)
- **Reason:** F2 – heavy renders start only after selection quiet (debounce).

```text
F2 (0.56.0): heavy renderers (PDF, Office, audio, video) start only after _RENDER_QUIET_MS (400 ms) of selection quiet – fast browsing over many files no longer fires renders whose result is dropped immediately. Mechanism: set_selection ALWAYS cancels a pending render first (_cancel_pending_render via GLib.source_remove), then _is_heavy decides: light formats (text, images, folder …) render immediately as before, heavy ones arm GLib.timeout_add(_RENDER_QUIET_MS, _on_pending_render). The handler returns False (self-removing source) and re-checks self._path – a selection cleared in between renders nothing. _is_heavy classifies by extension (.pdf, _OFFICE_EXTS from the render switch, the audio endings) and by mime prefix (audio/, video/) via query_file_info. The timer id lives in _pending_render_id (None default in __init). During the quiet window the previous preview stays visible. Debounce cousins already in the code: the size-allocate re-render and the panel-width config save. 0.56.1 (deploy feedback: TypeError "can only concatenate tuple (not set) to tuple" on EVERY selection): _OFFICE_EXTS is a SET (built for the "in" lookups of the render switch), but _is_heavy concatenated it with a tuple – the tuple-plus-set expression was evaluated on every call, so every single selection raised and the preview died. Fix: tuple(_OFFICE_EXTS).
```

### PAN-SELFTEST-1 – Parser selftest (F1)

- **Module:** previewer\_panel.py
- **Location:** module level, after the PREVIEWER\_VERSION dbg line: the \_st\_\* fixture builders and tests, run\_selftest and the \_\_main\_\_ guard; the parsers come in via the import line
- **Reason:** F1 – regression tests for the file parsers without Nemo, called with `python3 previewer\_panel.py --selftest`.

```text
F1 (0.61.0): four synthetic fixtures are built in a tempfile dir and checked against the pure parsers: a Markdown file (bold/italic/strike/inline code, h1 heading, two bullet items, one link) against _markdown_to_pango, a minimal EPUB (one content.opf with dc:title/dc:creator/dc:language, manifest and spine; found via the .opf fallback) against _epub_data, a 94-byte MOBI (PalmDB header BOOKMOBI, one 4-byte record offset entry, record 0 with MOBI magic, header length 232, encoding 65001 and an EXTH author entry of type 100) against _mobi_data, and a minimal sfnt (one name table, family and subfamily records in UTF-16BE) against _font_faces. Each check prints PASS or FAIL (with the detail on FAIL), the summary line counts, the exit code is 0 or 1; the fixture dir is removed afterwards. Building the first MOBI fixture exposed a real bug in _mobi_records (TXT-DOC-23) – the Palm record offsets were read as three bytes although the PDB entry stores four, so on real files record 0 started at offset>>8 and the EXTH author was never parsed (unnoticed because the title comes from the PalmDB name field).
```

### PAN-F69-1 – Font size keys in the config (F69)

- **Module:** previewer\_panel.py
- **Location:** `__init__` (defaults), `\_config\_load`, `\_config\_save` (both behind the F25 block), the apply call after `self.\_config\_load()`
- **Reason:** F69 – the two font size keys follow the F12 config pattern (defaults first, then load, then save).

```text
F69 (0.62.0): two new conf keys, both integers with a 0–28 guard on load: text_font_size and meta_font_size. Defaults sit next to the F25 spacing default; load next to the F25 block; _config_save persists both and then calls apply_font_size_css(self._conf_text_font_size, self._conf_meta_font_size) after save_to_file – so every settings save (also from other spins) reloads the CSS rules live. The same call runs once at panel startup behind _config_load. 0.62.1 (user finding before deploy): both defaults are the DETECTED system font size now (system_font_size_px, one call for both keys), not 0 – the spins start at the system value; a stored 0 keeps its meaning (explicit theme font).
```

### PAN-K6-1 – Multi-selection shows only the count (K6)

- **Module:** previewer\_panel.py
- **Location:** `\_render\_inner`, first block after the content margin reset
- **Reason:** K6 – user decision (2026-11-07): multi-selection renders no preview, the column only shows the count.

```text
K6 (0.63.0): _render_inner returns early when the selection holds more than one item – no renderer runs, the column shows only a centered dim label "N items selected" (N = number of selected items). The old behavior (preview of the first selected file plus "... and N more selected") is removed. A dbg line logs the count for deploy tests; single and empty selection behave as before.
```

---

## Selection (SEL)

### SEL-VTABLE-1 – Class vtable peek\_selection

- **Module:** previewer\_select.py
- **Location:** module level, below the section title “Native selection via the class vtable of NemoView (peek\_selection)”
- **Reason:** libnemo-private is static on Mint 22 – peek\_selection is read as a function pointer from the NemoView class vtable, indices verified against nemo-view.h. Since 0.39.0 (slimming round) the dlopen fallback (libnemo-private.so, fundamentally unsuccessful on Nemo 6) and the GI cascade (route 2) are removed – the class vtable is the only Nemo source, GTK/ATK fallbacks follow.

```text
# On Linux Mint 22 libnemo-private is a STATIC library – there is no .so whose symbols one could load (the dlopen attempt above stays as a fallback for older systems). Nemo's selection is still reachable: NemoView holds 'peek_selection' as a function pointer in the class vtable (nemo-view.h, NemoViewClass: index 12 after GtkScrolledWindowClass), and NemoFile implements the NemoFileInfo interface, whose vtable contains 'get_name' (index 1) and 'get_uri' (index 2) per nemo-file-info.h. The size of the parent class is queried AT RUNTIME via GObject.type_query() from the actually linked GTK – nothing is guessed. The indices are verified against the Mint 22 and master branches of nemo-view.h.
# ----------------------------------------------------------------------------
```

### SEL-GTYPE-1 – GType IDs via libgobject

- **Module:** previewer\_select.py
- **Location:** `_native_vtable_api`, above the CDLL access
- **Reason:** PyGObject returns a GType OBJECT from type\_from\_name() that ctypes does not accept – hence g\_type\_from\_name from libgobject.

```text
        # Get GType IDs DIRECTLY via libgobject: PyGObject lately returns a GType OBJECT from type_from_name() which ctypes does not accept as an argument ('cannot be interpreted as an integer' – an ArgumentError that silently killed the whole route). The way over g_type_from_name from libgobject guarantees the raw numeric ID from the same GLib runtime.
```

### SEL-WILDCALL-1 – Wildcall guard (0.9.2)

- **Module:** previewer\_select.py
- **Location:** module level, below the section title “Wildcall guard (0.9.2, audit “buffer overflow/OOM”)”, above `_NEMO_TEXT_RANGES`
- **Reason:** vtable function pointers may only be called when they lie inside a Nemo library; otherwise the route is switched off fail-closed.

```text
# The ctypes routes read function pointers from calculated vtable offsets (peek_selection, get_name, get_uri) and call them. If a Nemo update shifts the class/interface layout, a slot could point to a wrong but non-NULL pointer – calling it would be a wildcall and would kill Nemo instantly (try/except does not help against segfaults). Every call target must therefore lie inside a Nemo library before it is called; otherwise the route is switched off (fail-closed – the other selection strategies take over).
```

### SEL-DOC-1 – Docstring: \_gobject\_pointer

- **Module:** previewer\_select.py
- **Location:** `\_gobject\_pointer` (module level)
- **Reason:** Raw GObject pointer extraction for ctypes access (capsule or int).

```text
Determine the GObject pointer of a PyGObject wrapper. PyGObject usually stores it as a PyCapsule in __gpointer__; some builds return an integer directly. Both variants are supported, including nameless capsules (PyCapsule_GetPointer demands an exact name match – on a name mismatch the old path silently returned None).
```

### SEL-DOC-2 – Docstring: \_read\_cptr

- **Module:** previewer\_select.py
- **Location:** `\_read\_cptr` (module level)
- **Reason:** Memory read helper for the vtable route.

```text
Read a pointer from process memory (address addr + offset).
```

### SEL-DOC-3 – Docstring: \_native\_vtable\_api

- **Module:** previewer\_select.py
- **Location:** `\_native\_vtable\_api` (module level)
- **Reason:** One-time preparation of the native vtable API.

```text
Prepare vtable access to NemoView.peek_selection (once).
```

### SEL-DOC-4 – Docstring: \_nemo\_addr\_ranges

- **Module:** previewer\_select.py
- **Location:** `\_nemo\_addr\_ranges` (module level)
- **Reason:** Fail-closed address ranges for wild-call protection.

```text
Address ranges of all executable mappings of Nemo libraries (read once from /proc/self/maps). Returns None if the maps are not readable – callers treat that as fail-closed: rather switch off one route too many than risk a possible wild call.
```

### SEL-DOC-5 – Docstring: \_ptr\_in\_nemo

- **Module:** previewer\_select.py
- **Location:** `\_ptr\_in\_nemo` (module level)
- **Reason:** Pointer range check against the Nemo mappings.

```text
True if ptr lies within one of the Nemo address ranges.
```

### SEL-DOC-6 – Docstring: \_name\_from\_uri

- **Module:** previewer\_select.py
- **Location:** `\_name\_from\_uri` (module level)
- **Reason:** Central URI-to-basename conversion.

```text
File name (basename) from a Nemo URI – one place, one truth.
```

### SEL-DOC-7 – Docstring: \_iface\_file\_name

- **Module:** previewer\_select.py
- **Location:** `\_iface\_file\_name` (module level)
- **Reason:** File name via the NemoFileInfo interface with 0.9.2 wild-call protection.

```text
File name of a raw NemoFile pointer via the NemoFileInfo interface: get_name if the pointer is present; otherwise get_uri with basename fallback. Returns "" if there is nothing to fetch. The caller must have validated file_ptr against the NemoFile GType beforehand (api["is_a"]). 0.9.2: the function pointers are checked against the Nemo address ranges before the call (wild-call protection) – if a Nemo update shifts the interface layout, the wrong pointer is never called; "" is returned silently instead.
```

### SEL-DOC-8 – Docstring: \_vtable\_selection\_names

- **Module:** previewer\_select.py
- **Location:** `\_vtable\_selection\_names` (module level)
- **Reason:** Vtable selection read, returns (names, supported).

```text
Read the selection via NemoView.peek_selection. Returns (names, supported); supported=False means the strategy is not usable. names=[] is a valid, empty selection.
```

### SEL-DOC-9 – Docstring: \_nemo\_file\_name\_from\_ptr

- **Module:** previewer\_select.py
- **Location:** `\_nemo\_file\_name\_from\_ptr` (module level)
- **Reason:** File name of a raw NemoFile pointer via ctypes.

```text
Determine the file name of a raw NemoFile pointer (ctypes via the NemoFileInfo interface). Returns "" if the pointer is invalid or the vtable API is not ready. Validates the instance against the NemoFile GType beforehand – a wrong pointer is never followed. 0.9.1: the interface read logic lives in the shared helper _iface_file_name (previously identical in _vtable_selection_names).
```

### SEL-DOC-10 – Docstring: \_dump\_widget\_tree

- **Module:** previewer\_select.py
- **Location:** `\_dump\_widget\_tree` (module level)
- **Reason:** Verbose diagnostics – widget tree with selection methods.

```text
Diagnose actual GTK descendants and their selection-related methods.
```

### SEL-DOC-11 – Docstring: \_signals\_of\_gtype

- **Module:** previewer\_select.py
- **Location:** `\_signals\_of\_gtype` (module level)
- **Reason:** Own void signals with 'select' in the name.

```text
Void signals of this GType with 'select' in the name (without inherited ones).
```

### SEL-DOC-12 – Docstring: selection\_signals

- **Module:** previewer\_select.py
- **Location:** `selection\_signals` (module level)
- **Reason:** All selection signals including inherited and interface signals.

```text
All 'selection' signals of a GObject – including inherited ones by walking the GType hierarchy upwards; additionally the signals of implemented interfaces (ATK reports selection changes e.g. via an interface signal of AtkSelection). Nemo does not guarantee uniform signal naming (hyphens vs. underscores); nothing is guessed here – the actual name is read at runtime. Sorted list, possibly empty.
```

### SEL-DOC-13 – Docstring: \_atk\_children

- **Module:** previewer\_select.py
- **Location:** `\_atk\_children` (module level)
- **Reason:** Defensive ATK children enumeration (get\_n\_children may lie).

```text
Determine the children of an ATK object defensively. get_n_children() fails on some systems (Nemo views reported -1, the a11y tree seemed empty); therefore, on exception or nonsense, ref_child() is tried blindly for the first indices until ref_child itself fails. Returns a (possibly empty) list – never None.
```

### SEL-DOC-14 – Docstring: \_a11y\_root

- **Module:** previewer\_select.py
- **Location:** `\_a11y\_root` (module level)
- **Reason:** Mapped a11y root, None for unusable views.

```text
Mapped a11y root of the view (None if the view is unusable).

Never call ATK on a view that is hidden or being torn down.
```

### SEL-DOC-15 – Docstring: \_atk\_selection\_objects

- **Module:** previewer\_select.py
- **Location:** `\_atk\_selection\_objects` (module level)
- **Reason:** All AtkSelection implementors in the view's a11y tree.

```text
Collect all AtkSelection implementors in the a11y tree of the view.
```

### SEL-DOC-16 – Docstring: is\_nemo\_view

- **Module:** previewer\_select.py
- **Location:** `is\_nemo\_view` (module level)
- **Reason:** Positive-only Nemo file view detection (no sidebar trees).

```text
Is this widget a real Nemo FILE view? IMPORTANT: NOT the sidebar trees! 'NemoPlacesTreeView' (places sidebar) starts with 'Nemo' and ends with 'View', but it is a GtkTreeView of the sidebar – exactly this case sabotaged the selection detection invisibly for a long time. Detection therefore runs positively only: via the base type NemoView or the known view names, never via 'starts with Nemo + ends with View'.
```

### SEL-DOC-17 – Docstring: find\_view

- **Module:** previewer\_select.py
- **Location:** `find\_view` (module level)
- **Reason:** Only mapped views count as a fallback.

```text
Return only a currently mapped Nemo file view.

While switching folders the old view can still be in the widget tree although its GObject instance is already being torn down. Therefore no unmapped view is returned as a fallback anymore.
```

### SEL-DOC-18 – Docstring: SelectionReader (class)

- **Module:** previewer\_select.py
- **Location:** `SelectionReader` (class)
- **Reason:** Class marker – multi-stage selection reader.

```text
Reads the current selection of the Nemo view – multi-stage.
```

### SEL-DOC-19 – Docstring: read

- **Module:** previewer\_select.py
- **Location:** `SelectionReader.read` (static method)
- **Reason:** Entry point – the first non-empty result wins across all strategies.

```text
Returns (list_of_names, strategy) or (None, None) if the selection was not readable. ALL strategies are asked and the first NON-EMPTY result wins:
1. NemoView.peek_selection via the class vtable (primary API)
2. Gtk.IconView/Gtk.TreeView selection
3. ATK selection, SELECTED state and focus as fallback
If a strategy reports [] (readable, but nothing selected), the others are still asked – a 'blind' strategy can never block the others.
```

### SEL-DOC-20 – Docstring: \_read\_nemo\_vtable

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_nemo\_vtable` (static method)
- **Reason:** Primary strategy with one-time exception reporting.

```text
Selection via NemoView.peek_selection (vtable) – see module head.

Returns None if the strategy is not available, otherwise the (possibly empty) name list. An empty list is a valid selection, not an error. Unexpected exceptions (which read() would otherwise swallow silently) are reported once with cause so silent failures become visible.
```

### SEL-DOC-21 – Docstring: \_read\_icon\_view

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_icon\_view` (static method)
- **Reason:** Direct GTK selection for icon views.

```text
Direct GTK selection for Gtk.IconView-based Nemo views.
```

### SEL-DOC-22 – Docstring: \_read\_atk

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_atk` (static method)
- **Reason:** ATK route – the first real selection wins.

```text
Via the accessibility interface (icon view). ALL AtkSelection implementations in the a11y tree of the view are asked; the first with a real selection wins. This way a wrong AtkSelection object (which always reports 0) can no longer swallow the real selection.
```

### SEL-DOC-23 – Docstring: \_read\_atk\_states

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_atk\_states` (static method)
- **Reason:** ATK SELECTED-state fallback for the icon view.

```text
Fallback for the icon view: collect all objects with ATK state SELECTED in the a11y tree of the view and take their names. Returns the names or None (tree not evaluable).
```

### SEL-DOC-24 – Docstring: \_read\_atk\_focused

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_atk\_focused` (static method)
- **Reason:** Single-click fallback via the focused object.

```text
Single-click fallback: name the single focused object in the a11y tree. After a simple click the clicked icon is focused, even if AtkSelection fails. The name only counts if it resolves to a real file in the displayed folder.
```

### SEL-DOC-25 – Docstring: \_tree\_row\_name

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._tree\_row\_name` (static method)
- **Reason:** List-row name in two stages (NemoFile column 0 + string columns).

```text
Determine the file name of a marked list row.

Nemo's list model (nemo-list-model.h) stores NO string in column 0 but the NemoFile object; the pixbufs follow in columns 1–7, the visible file name only sits in one of the dynamic attribute columns (12+, depending on sorting/column choice). Hence two stages:
1. Read column 0: a PyGObject wrapper is asked via its NemoFileInfo interface methods (get_name/get_uri) – exactly this is how all Nemo Python extensions read their files. If PyGObject only yields the raw pointer (int), the ctypes route takes over (_nemo_file_name_from_ptr). The result serves as a fallback.
2. Additionally scan ALL string columns and prefer the string that resolves to a real file in the displayed folder; otherwise the first string, and at the very end the name from stage 1.
```

### SEL-DOC-26 – Docstring: \_read\_tree

- **Module:** previewer\_select.py
- **Location:** `SelectionReader._read\_tree` (static method)
- **Reason:** GtkTreeView route (list and compact views).

```text
GtkTreeView-based views (list, compact).
```

---

## Helpers (UT)

### UT-TRACE-1 – Step trace via sys.settrace (F45)

- **Module:** previewer\_util.py
- **Location:** `install\_step\_trace`, started in the entry point right after the util import
- **Reason:** User request: every function of the eight modules shall be identifiable in the debug log. Instead of instrumenting every function individually, a central hook is set via sys.settrace – it only tracks files with the previewer\_ prefix (Nemo, GTK and foreign extensions stay untouched); dbg/diag are excluded so the logger does not log itself. Level via NEMO\_PREVIEWER\_TRACE: 1/call logs every call with arguments cut to 60 characters, every return and every exception; line additionally logs every executed line. An error in the hook switches off silently instead of endangering Nemo.

```text
# Log calls, returns, exceptions: NEMO_PREVIEWER_TRACE=1 nemo --no-desktop additionally every executed line: NEMO_PREVIEWER_TRACE=line nemo --no-desktop without the variable NO hook runs – zero overhead in daily use.
```

### UT-WIDGET-1 – Widget helpers for all modules (S6, 0.42.0)

- **Module:** previewer\_util.py
- **Location:** widget-helpers section, after the byte/pixbuf helpers before PREVIEWER\_VERSION
- **Reason:** Spaghetti audit round 2 (S6, user decision “collect in util”): the cross-mixin helpers moved from the panel mixin into util: pack\_hint (dim label hint, formerly mixin method \_hint) and pack\_meta\_grid (key-value table with F35 colon logic, formerly \_meta\_grid – the target container has been a mandatory parameter since then instead of a self.\_content default), cover\_round\_path (F34 corner path, formerly staticmethod \_cover\_round\_path in the media module), build\_scaled\_image (image in a scroll window, R3 dict on the image entry) and build\_text\_view (TextView configuration and buffer fill, 10/10/8/8 padding). Panel, media, docs and text import them; the panel keeps thin wrappers – \_scaled\_image registers in \_scale\_items and scales, \_text\_view guesses GtkSourceView, sets line numbers and packs. Behaviour unchanged.

### UT-DOC-1 – Docstring: dbg

- **Module:** previewer\_util.py
- **Location:** `dbg` (module level)
- **Reason:** Basic debug output for the terminal; every module logs through it with the [previewer] prefix.

```text
Debug output – visible when Nemo is started in a terminal. 0.53.0 (F65): with DEBUG_LOG on (settings toggle or NEMO_PREVIEWER_DEBUG=1) dbg additionally mirrors every line into the log file (see UT-LOG-1); stdout behavior stays unchanged in every mode, so terminal deploy tests stay identical. 0.54.1 (deploy feedback): dbg is now FULLY GATED – "debug logging" means ALL debug output: with the toggle and the env var off dbg writes NOTHING, neither into the log file nor to stdout; only the entry point's version-mismatch warning stays visible via a plain print (a stale module must never hide behind silent mode). Consequence: terminal deploy tests now run with NEMO_PREVIEWER_DEBUG=1 nemo.
```

### UT-DOC-2 – Docstring: diag

- **Module:** previewer\_util.py
- **Location:** `diag` (module level)
- **Reason:** Verbose diagnostics (dumps, signals) behind the VERBOSE\_DIAG switch, silent in daily use. Since 1.0.0 the switch defaults to False (release decision); flip it to True to investigate a new Nemo version or a new system.

```text
Diagnostics output – only visible when VERBOSE_DIAG=True.
```

### UT-DOC-3 – Docstring: install\_step\_trace

- **Module:** previewer\_util.py
- **Location:** `install\_step\_trace` (module level, started by the entry point)
- **Reason:** F45 (user request) – central sys.settrace hook, activated only via NEMO\_PREVIEWER\_TRACE.

```text
F45 (user request): install a sys.settrace hook when NEMO_PREVIEWER_TRACE is set (1/call or line). Returns True while the trace is running. Only files with the previewer_ prefix are tracked – Nemo, GTK and foreign extensions stay untouched; dbg/diag are excluded so the logger does not log itself; errors in the hook switch it off silently.
```

### UT-DOC-4 – Docstring: pick\_icon

- **Module:** previewer\_util.py
- **Location:** `pick\_icon` (module level)
- **Reason:** F40 – the first icon name that exists in the active theme, so no button is left without an image.

```text
F40: return the first symbol from names that EXISTS in the active icon theme – Mint/Nemo themes do not provide every name –, otherwise fallback. That way no button is left without an image. 0.65.6: the fallback is VERIFIED too – if the theme lacks it as well (Mint-Y lacks arrow-right), image-missing is returned and rendered from GTK's built-in last-resort set; no button can end up blank.
```

### UT-DOC-5 – Docstring: walk

- **Module:** previewer\_util.py
- **Location:** `walk` (module level)
- **Reason:** Iterates the whole widget subtree, the start widget included.

```text
Yield all widgets in the subtree, including the widget itself.
```

### UT-DOC-6 – Docstring: query\_file\_info

- **Module:** previewer\_util.py
- **Location:** `query\_file\_info` (module level)
- **Reason:** Mime type, size and mtime of a path, each with a fallback ("unknown", −1).

```text
(mime_type, size, mtime) – all with fallbacks.
```

### UT-DOC-7 – Docstring: \_pixbuf\_from\_bytes

- **Module:** previewer\_util.py
- **Location:** `\_pixbuf\_from\_bytes` (module level)
- **Reason:** Pixbuf decoding with a decode cap (PNG bomb protection) and reporting of the original dimensions (R9).

```text
Decode bytes into a pixbuf – GdkPixbuf sniffs the format – with a decode cap (0.9.2): the size-prepared signal fires BEFORE the pixel data is allocated; set_size() shrinks the decoding there. An image that only declares giant dimensions in its header (PNG bomb) thus costs only the capped area instead of gigabytes. Decoding errors are raised as before (the respective caller catches them). orig: optional dict – filled with the ORIGINAL dimensions reported before capping (R9): size-prepared reports them before set_size shrinks, so the image preview can show the real dimensions although decoding is capped.
```

### UT-DOC-8 – Docstring: \_zf\_read\_capped

- **Module:** previewer\_util.py
- **Location:** `\_zf\_read\_capped` (module level)
- **Reason:** R4 – ZIP member reading with a read cap against decompression bombs.

```text
R4: read a ZIP member with a read cap – protection against decompression bombs: zipped XHTML chapters can occupy a multiple of their packed size once unpacked, blocking the panel for seconds. Everything beyond the cap is deliberately cut off – for the preview the beginning of the chapter or image is enough.
```

### UT-DOC-9 – Docstring: \_xml\_dtd\_rejected

- **Module:** previewer\_util.py
- **Location:** `\_xml\_dtd\_rejected` (module level)
- **Reason:** R10 – entity guard for all xml.etree parse sites (Billion Laughs protection).

```text
R10: entity guard for all xml.etree parse sites (EPUB OPF, FB2, .contact, Office XML). xml.etree does not follow external entities, but it expands DOCTYPE declarations with internal entities without restraint – a "Billion Laughs" document occupies a multiple of the file size in memory before the preview can react. The formats shown here practically come without a DTD: if the file head (first 64 KB) contains a DOCTYPE declaration or an ENTITY definition, parsing is rejected; the caller shows its open hint instead of the content.
```

### UT-DOC-10 – Docstring: pack\_hint

- **Module:** previewer\_util.py
- **Location:** `pack\_hint` (module level)
- **Reason:** S6 – dim-label hint with line wrap, packed into any container.

```text
S6 (0.42.0): dim label with line wrap, left-aligned, packed into the container – the former _hint part of the panel mixin, now in util for panel, media, docs and text.
```

### UT-DOC-11 – Docstring: pack\_meta\_grid

- **Module:** previewer\_util.py
- **Location:** `pack\_meta\_grid` (module level)
- **Reason:** S6 – central key-value table with F35 colon logic and F60 wrap mode. F54 (0.58.2): bold_keys=True packs bold labels, italic_values=True italic values (EML header, user request). F52 (0.60.0): title_width pins the label column to a fixed pixel width (ICS event table, user request). F69 (0.62.0): CSS class for the configurable info table font size.

```text
Key-value table (dim label on the left, value on the right with END ellipsize and tooltip) – central helper for e-book, EML, audio and video info. 0.9.1: previously also built identically inline several times; the inline copies are gone. F35: every label automatically gets a colon at the end (if not already present). F38: packs into any position handed over – image previews give their 40% info area along. S6 (0.42.0): born as the panel mixin method _meta_grid, now usable across util. F60 (0.45.0): wrap=True packs the values multi-line instead of with END ellipsize – package info (description, dependencies) is longer than one line and flows into the scrollable info area of the package preview. F54 (0.58.2): bold_keys=True renders the labels as bold markup (escaped via GLib.markup_escape_text, no dim class), italic_values=True the values italic – EML headers use both, the other callers keep the default look. F52 (0.60.0): title_width pins the title column to a fixed pixel width – labels get a size request plus END ellipsize with tooltip, so the column stays exactly at the requested width even when a label like Description: is longer (ICS event tables use 75). 0.65.4: title_width is a MINIMUM in practice – the column still widens with the longest label of the single grid, so ICS cards with missing rows (e.g. no Description) stood at odds; the new optional size_group (a Gtk.SizeGroup, HORIZONTAL) joins every label of the grid, and ONE group per ICS file equalizes the label column of ALL event cards (the widest label wins), so a missing property never shifts the layout between cards. F69 (0.62.0): the grid gets the CSS class pvw-meta-size – the configurable info table font size rides on it (rule from apply_font_size_css, UT-DOC-16); the labels inherit the size from the grid.
```

### UT-DOC-12 – Docstring: cover\_round\_path

- **Module:** previewer\_util.py
- **Location:** `cover\_round\_path` (module level)
- **Reason:** F34 – rounded-rectangle Cairo path for covers.

```text
F34: rectangle with rounded corners as the current Cairo path. S6 (0.42.0): moved to util from previewer_render_media (staticmethod _cover_round_path) – text covers use it too.
```

### UT-DOC-13 – Docstring: build\_scaled\_image

- **Module:** previewer\_util.py
- **Location:** `build\_scaled\_image` (module level)
- **Reason:** S6 – image widget in a scroll window; returns the R3 resize dict item.

```text
S6 (0.42.0): image in a scroll window – the widget part of the panel method _scaled_image (the R3 documentation stays there); registration and initial scaling stay with the panel.
```

### UT-DOC-14 – Docstring: build\_text\_view

- **Module:** previewer\_util.py
- **Location:** `build\_text\_view` (module level)
- **Reason:** S6 – TextView configuration and buffer fill with 10/10/8/8 padding. F69 (0.62.0): CSS class for the configurable text preview font size.

```text
S6 (0.42.0): TextView configuration and buffer fill – the widget part of the panel method _text_view; line numbers, GtkSourceView guessing and packing stay with the panel. 0.55.0 (F25): optional spacing parameter – values above 0 create the TextTag "previewer-line-spacing" (pixels_above_lines) and apply it over the whole buffer; the tag is re-applied on every rebuild, the clipboard stays untouched. 0.62.0 (F69): the view gets the CSS class pvw-text-size – the configurable text preview font size rides on it (rule from apply_font_size_css, UT-DOC-16); where build_text_view runs with an explicit font (override_font wins), the font itself rules.
```

### UT-DOC-15 – Docstring: center\_window

- **Module:** previewer\_util.py
- **Location:** `center\_window` (module level, at the module end behind `build\_text\_view`)
- **Reason:** User rule (2026-11-03): all opening windows appear centered on the screen with ~60 % of the screen height.

```text
User rule (2026-11-03): all opening windows of the extension – settings window, info windows, every future one – appear centered on the screen and carry ~60 % of the screen height as their height. Central helper for it: sets the default size to (caller width, int(0.6 x screen height)) via Gdk.Screen and positions the window with Gtk.WindowPosition.CENTER; defensive try/except, on failure the window keeps its caller size. Used by the toolbar settings window (420 wide) and the EXIF "more" window (560 wide). 0.49.1 fix (user finding: windows came out full-height – set_default_size was overridden by the content's natural size): the height now comes from the primary monitor's geometry via Gdk.Display (current resolution, minus 40 %; fallback: monitor 0), and after mapping GLib.idle_add enforces the size once via resize; the detected monitor resolution is dbg-logged.
```

---

### UT-LOG-1 – Debug log file: dbg mirror (F65)

- **Module:** previewer\_util.py
- **Location:** `DEBUG\_ENV`, `DEBUG\_LOG`, `set\_debug\_log`, `\_debug\_log\_file`, `debug\_log\_active`, `debug\_log\_cleanup` and the `LOG\_DIR`/`LOG\_FILE`/`DEBUG\_LOG\_CAP`/`DEBUG\_LOG\_MAX\_AGE` constants (module level)
- **Reason:** F65 debug logging as a setting – dbg mirrored into a persistent log file, toggle or env var.

```text
F65 (0.53.0, user wish): debug logging as a SETTING – with the toggle on, every dbg line is mirrored into a persistent log file. Path: XDG_STATE_HOME (default ~/.local/state)/nemo-previewer/previewer.log – the XDG standard place for user logs, survives Nemo restarts and independent of where stdout lands (terminal vs session). Mechanics: DEBUG_LOG starts from the env var NEMO_PREVIEWER_DEBUG=1 (power-user one-shot, always wins over the toggle); the settings toggle feeds set_debug_log(True) from the panel config load and the toolbar handler (OR, never switches the env var off). _debug_log_file appends each line with a "YYYY-MM-DD HH:MM:SS" timestamp, writes a "--- session start, version X ---" header once per session at the first write, and rotates ONCE per session: if the file exceeds DEBUG_LOG_CAP (512 KB) it becomes previewer.log.old (exactly ONE backup, the previous .old is removed first) – bounded disk footprint in the 0.9.2 cap discipline. File errors are suppressed with a plain print (never dbg – no recursion). dbg keeps stdout output unchanged in every mode, so terminal deploy tests stay identical. 0.54.0 (deploy feedback): set\_debug\_log recomputes LIVE – OFF stops file logging during the session (the old OR semantics kept the flag stuck on TRUE); the env var is captured separately in DEBUG\_ENV at import time and still wins over the toggle. New: debug\_log\_active() returns the live state for the header dot; debug\_log\_cleanup() deletes previewer.log and previewer.log.old once their mtime is older than DEBUG\_LOG\_MAX\_AGE (7 days) – called at every panel start, even with logging off, so logs never linger on disk forever. 0.54.1 (deploy feedback): dbg is fully gated since this version – the debug toggle and the env var now switch ALL debug output (file AND stdout); nothing is written anywhere while both are off.
```

### UT-DOC-16 – Docstring: apply\_font\_size\_css (F69)

- **Module:** previewer\_util.py
- **Location:** `TEXT\_SIZE\_CSS\_CLASS`, `META\_SIZE\_CSS\_CLASS`, `\_SIZE\_CSS\_PROVIDER`, `apply\_font\_size\_css`, `system\_font\_size\_px` (module level, widget helpers section)
- **Reason:** F69 – font sizes of text previews and info tables as CSS classes, rebuilt on every settings save.

```text
F69 (0.62.0, user wish): two font size settings ride on CSS classes instead of per-widget font plumbing: build_text_view adds pvw-text-size to every preview TextView, pack_meta_grid adds pvw-meta-size to every info grid, the tag window (media) and package table (text) TreeViews carry pvw-meta-size as well. apply_font_size_css(text_px, meta_px) holds ONE provider on the default screen (K11 pattern, port note in AUDIT-GTK4-3) and rebuilds the rules on every call: a rule only exists while the size is > 0, 0 means the theme font (no rule at all). Called at panel startup after _config_load and at the end of _config_save – the provider reload makes GTK re-resolve the styles, so open previews and windows restyle LIVE without a re-render. Keys: text_font_size and meta_font_size (0–28 px). 0.62.1 (user finding before deploy): system_font_size_px() measures the theme font size in px from a fresh TextView (get_font on its style context; points are converted at 96 dpi, the result is clamped to 1–28, every failure returns 0) – the panel uses it as the DEFAULT of both keys, so the spins start at the system value; a 0 → 1 step jumped from the ~12 px system default to 1 px and looked like a bug. 0 stays selectable as the explicit theme default.
```

### UT-I18N-1 – Translations: gettext infrastructure (F58/6)

- **Module:** previewer\_util.py
- **Location:** `import gettext`, `\_LOCALE\_DIR`, `\_PO\_DIR`, `\_PoTranslations`, `\_po\_read`, `\_po\_translation`, `\_TRANSLATION`, `\_` (module level, below the gi imports)
- **Reason:** F58 (6) i18n – UI strings translatable via GNU gettext, German catalog as the first language.

```text
0.65.0 (user wish "the usual handling") marked all UI literals via _(); 0.65.1 REDESIGNED the loading after the user rejected the msgfmt-only design of 0.65.0 (the language must work out of the box, nobody compiles anything) – util imports gettext and resolves ONE translation object at import time via a three-step loading chain: (1) gettext.translation("nemo-previewer", localedir=_LOCALE_DIR) tries a compiled locale/<lang>/LC_MESSAGES/nemo-previewer.mo – an optional override for power users; (2) without it, _po_translation() resolves the language via GLib.get_language_names() (first entry that maps to an existing po/<code>.po next to the modules; codes split at "." and "@", "C" skipped) and _po_read() parses that po source with a small state machine (mode 0 = outside an entry, 1 = inside msgid, 2 = inside msgstr; quoted segments concatenated, escapes unescaped by _po_unesc, the header entry with the empty msgid skipped) into _PoTranslations(gettext.NullTranslations) – its gettext() override returns the msgid itself for unknown keys; (3) if neither exists, the NullTranslations fallback keeps the English msgid – without po/de.po the UI stays English. All UI modules import the SAME _ from previewer_util (first import line "    _,"); select carries no UI strings and needs nothing. Marking rule: every user-visible literal is wrapped in _() at the call site – labels, tooltips, hints, window/dialog titles, button texts, multi-line strings as ONE wrapped literal (concatenation inside the call); NOT translated: dbg/diag lines (English in every language), CSS, config keys, MIME names, file extensions, markup fragments ("<b>%s</b>" stays, only the payload is wrapped), font and file format proper names (TrueType, OpenType (CFF)). %-formatting stays OUTSIDE the call: _("%d items selected") % n. Runtime lookups: labels that are data keys AND display labels (EXIF keys like "Camera", vCard TEL labels, _FONT_SAMPLE_TEXT) translate at DISPLAY time via _(key) – their msgids are in the pot but not inside a literal _(). Catalogs: po/nemo-previewer.pot (template) and po/de.po (German, 189 msgids, Plural-Forms nplurals=2; plural=(n != 1)); since 0.65.1 de.po ships WITH the deployment – INSTALL.md copies it to nemo-previewer-modules/po/ (a data file, no py version lock), so a German system shows the German UI right after install (see INSTALL.md "Translations"). 0.65.0 side effect: the pre-i18n German leftovers "Telefon" (vCard TEL fallback) and "DOCTYPE im OPF" became English msgids ("Phone", "DOCTYPE in the OPF"); "Telefon" is now the German msgstr of "Phone". Naming hazard: the gettext name `_` must never double as a throwaway unpack variable in a function that also calls `_()` – _deb_rows unpacked partition() into `_` and crashed at the first _() call, the separator is `sep` now (other throwaway uses, e.g. _uri_to_dir, _rpm_data, _pkginfo_fields, _tag_number_pair, _control_fields, never call _() and stay). Concatenation hazard (0.65.2 hotfix): implicit string concatenation ("a" "b" = "ab") BREAKS as soon as one part is wrapped in _() – _get_name_and_desc built ["previewer:::" "…:::"] via implicit concat, the i18n marking produced ["previewer:::" _("…") ":::"] and Python raised a SyntaxError at import (extension never loaded, live deploy 0.65.1); the rule: concatenation with _() ALWAYS explicit via +, the 0.65.2 fix is ["previewer:::" + _("…") + ":::"].
```

---

## Toolbar (TB)

### TB-F19-1 – Static ActionBar (F19)

- **Module:** previewer\_toolbar.py
- **Location:** `_build_toolbar`, below the title “F19: Toolbar at the bottom of the preview column (0.11.0)”
- **Reason:** Static per user decision – always visible, no show/hide per renderer; renderer actions register later via pack\_start.

```text
        # Static per user decision: it is ALWAYS visible while the panel is active – no show/hide per renderer. The renderer actions (F13, F20, F21, F24–F27) register here later via pack_start; the settings button (gear from the system icons) already sits fixed at the far right, where the configuration (F12) will dock.
```

### TB-CSS-1 – Toolbar padding

- **Module:** previewer\_toolbar.py
- **Location:** `_build_toolbar`, above the CSS try block
- **Reason:** User request (0.12.0): the bar about 5 px slimmer; if a theme cannot handle the rule, the standard stays.

```text
        # User request (0.12.0): the bar about 5 px slimmer – the padding top/bottom lies below the theme standard (Adwaita standard is 6+6 px, here 3+4 px). If a theme cannot handle the rule, it simply stays with the standard – no error, no crash.
```

### TB-F12-1 – Pre-fill the SpinButton (F12 part 2)

- **Module:** previewer\_toolbar.py
- **Location:** `_open_settings_window`, above the wrow box
- **Reason:** The SpinButton carries the current value up front; the default is named next to it, the actual value marked as “current” (user request). Since 0.41.0: dragging the divider no longer changes the start width – the SpinButton value (default 350 px) is the only source; the “default/current” hint line is gone.

```text
        # Start width at launch: the SpinButton carries the value stored in the conf up front – since 0.41.0 it is the ONLY source (dragging the divider no longer overrides it); the default/current hint line was dropped.
```

### TB-DOC-1 – Docstring: PreviewToolbarMixin (class)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin` (class)
- **Reason:** Class marker – toolbar mixin with action bar (F19) and settings window (F12).

```text
Mixin: action bar (F19) + settings window (F12) of the panel.
```

### TB-DOC-2 – Docstring: \_on\_settings\_clicked

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_settings\_clicked` (method)
- **Reason:** Settings button in the toolbar opens the configuration window.

```text
F19/F12 (0.12.0): the settings button in the toolbar opens the configuration window. All settings of the preview column will gather there over time; changes apply immediately and land in the configuration file without an extra button.
```

### TB-DOC-3 – Docstring: \_open\_settings\_window

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._open\_settings\_window` (method)
- **Reason:** Single-instance configuration window; since 0.40.0 four section helpers build the frames.

```text
F12 (0.12.0): configuration window of the preview column. The frame is in place; all settings will gather here over time (F12 catalogue: panel width, document page limit, waterfall sample text …) – each with instant saving via _config_save. Only ONE instance: another click on the gear brings the existing window to the front. Since 0.40.0 four section helpers build the individual frames. 0.49.0: the window opens centered on the screen with ~60 % of the screen height (user rule for all opening windows, → REF UT-DOC-15).
```

### TB-DOC-4 – Docstring: \_settings\_frame\_general

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._settings\_frame\_general` (method)
- **Reason:** General section: start behaviour, folder contents list (F48), default width at launch.

```text
Section "General": start behaviour, folder contents list (F48) and the default width at launch (→ REF TB-F12-1). 0.53.0 (F65): fourth element – the debug logging check button (see TB-DOC-16).
```

### TB-DOC-5 – Docstring: \_settings\_frame\_text

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._settings\_frame\_text` (method)
- **Reason:** Text files section: line numbers (F24) and syntax highlighting (F44).

```text
Section "Text files" (F24, 0.16.0): line numbers and syntax highlighting – applies only to the plain text preview; rendered previews (Markdown, e-mail, e-book, font) have no line numbers. 0.55.0 (F25): spin "Line spacing (px)" (0–12, step 1) below the syntax switch – handler _on_line_spacing_changed (TB-DOC-17) saves immediately and re-renders live. NOTE: unlike the line numbers the spacing applies to ALL TextView previews, because it flows into build_text_view centrally.
```

### TB-DOC-6 – Docstring: \_settings\_frame\_docs

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._settings\_frame\_docs` (method)
- **Reason:** Documents section: PDF/Office page limit with maximum value (F12 part 3).

```text
Section "Documents" (F12 part 3, 0.27.0): PDF/Office page limit with maximum value – applies live and is saved immediately.
```

### TB-DOC-7 – Docstring: \_settings\_frame\_fonts

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._settings\_frame\_fonts` (method)
- **Reason:** Fonts section: waterfall sample text (F12, 0.34.0).

```text
Section "Fonts" (F12, 0.34.0): waterfall sample text – applies live to the font currently displayed (→ REF TXT-FONT-2).
```

### TB-DOC-8 – Docstring: \_on\_folder\_contents\_toggled

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_folder\_contents\_toggled` (method)
- **Reason:** F48 toggle – saves immediately and re-renders folder previews live.

```text
F48 (user request): save the folder contents list immediately and apply it live – if a folder is currently selected, the preview rebuilds instantly (contents list ↔ plain folder icon); file previews stay untouched.
```

### TB-DOC-9 – Docstring: \_on\_font\_sample\_changed

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_font\_sample\_changed` (method)
- **Reason:** Waterfall sample text – saves and re-renders font previews live.

```text
F12 (0.34.0, user request): save the waterfall sample text immediately and apply it live – if a font is currently selected (.ttf/.otf/.ttc), the waterfall rebuilds instantly with the new text. Empty text stays unsaved.
```

### TB-DOC-10 – Docstring: \_on\_linenumbers\_toggled

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_linenumbers\_toggled` (method)
- **Reason:** F24 toggle – rebuilds every TextView-based preview in both directions.

```text
F24 (0.16.0): save line numbers immediately and apply them live. 0.16.2: every TextView-based preview is rebuilt (text, Markdown, EML, e-book, font – the _last_textish flag in the core is now generally True when the current preview is TextView-based), so the toggle works in BOTH directions – also when re-enabling. PDF, Office, audio, video, image and folder stay untouched and are not re-rendered.
```

### TB-DOC-11 – Docstring: \_on\_syntax\_toggled

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_syntax\_toggled` (method)
- **Reason:** F44 follow-up – same live mechanism for syntax highlighting.

```text
F44 follow-up (0.28.1, user request): save syntax highlighting immediately and apply it live – the same mechanism as the line-number toggle: only TextView-based previews rebuild, everything else stays untouched.
```

### TB-DOC-12 – Docstring: \_on\_doc\_limit\_toggled

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_doc\_limit\_toggled` (method)
- **Reason:** Page-limit toggle with SpinButton sensitivity and live re-render.

```text
F12 part 3 (0.27.0): document page limit on/off – save immediately and apply live. The page-count SpinButton is only operable with the limit active; a displayed document preview rebuilds instantly via the _last_docview flag.
```

### TB-DOC-13 – Docstring: \_on\_doc\_max\_pages\_changed

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_doc\_max\_pages\_changed` (method)
- **Reason:** Maximum page count, clamped to 1–999, saved live.

```text
F12 part 3 (0.27.0): maximum page count (1–999) – save immediately and apply live, like the line-number toggle.
```

### TB-DOC-14 – Docstring: \_rerender\_docs

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._rerender\_docs` (method)
- **Reason:** Live-rebuild counterpart for document previews (\_last\_docview flag).

```text
F12 part 3 (0.27.0): rebuild the current PDF/Office page view live – the counterpart to the _last_textish flag of the line numbers: only document previews react, everything else (image, audio, text …) stays untouched.
```

### TB-DOC-15 – Docstring: \_on\_start\_width\_changed

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin._on\_start\_width\_changed` (method)
- **Reason:** F12 start width – the SpinButton is the only source since 0.41.0.

```text
F12 (0.13.0): new start width from the SpinButton – adopt immediately, apply live and save (no extra button). 0.41.0: the SpinButton is the ONLY source of the start width – dragging the divider does not change it.
```

---

### TB-DOC-16 – Docstring: \_on\_debug\_log\_toggled (F65)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_on\_debug\_log\_toggled` (method) and the check button in `\_settings\_frame\_general`
- **Reason:** F65 debug logging as a user setting (see UT-LOG-1 for the mechanics).

```text
F65 (0.53.0): check button "Debug logging (write log file)" in the settings "General" frame, active state from _conf_debug_log (panel config, key debug_log). Handler _on_debug_log_toggled: store the state, _config_save() immediately (no separate save button – same course as the other toggles), then set_debug_log(state) – the env var NEMO_PREVIEWER_DEBUG=1 still wins over an OFF toggle. The dbg confirmation line logs the raw toggle state. Tooltip names the log path (~/.local/state/nemo-previewer/previewer.log), the rotation cap and the env var one-shot. 0.54.0 (deploy feedback): the toggle now switches logging OFF live during the session (set\_debug\_log recomputes) and refreshes the header recording dot via \_update\_rec\_dot right after the flag change.
```

### TB-DOC-17 – Docstring: \_on\_line\_spacing\_changed (F25)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_on\_line\_spacing\_changed` (method) and the spin in `\_settings\_frame\_text`
- **Reason:** F25 line spacing – spin handler with ONE quiet re-render (backlog fix after live-deploy hangs; guard like the doc pages spin of TB-DOC-13).

```text
F25 (0.55.0): value-changed handler of the "Line spacing (px)" spin (Adjustment 0–12, step 1, page 2). Original course (full re-render + _config_save() per tick) HUNG the live deploy: holding an arrow fires value-changed per tick, every tick wrote the config file and rebuilt the whole TextView preview – the main loop starved and the settings window froze/crashed. New course: int(spin.get_value()) compared to _conf_text_line_spacing (equal -> return, same guard as TB-DOC-13), the value lands in MEMORY at once, then exactly ONE GLib.timeout_add(400, _on_line_spacing_quiet) is armed (a pending id is source_removed first; _spacing_render_id init None next to _settings_spacing_spin, toolbar imports GLib). _on_line_spacing_quiet fires once after the spin is quiet: ONE _config_save() and ONE _render() if _last_textish and _path, then return False drops the timeout source. The re-render passes the value through build_text_view's spacing parameter (TextTag pixels_above_lines), so the current text preview widens/narrows; because _text_view passes the config value centrally, the spacing applies to ALL TextView previews, not only the plain text.
```

### TB-DOC-18 – Docstring: \_on\_text\_size\_changed / \_on\_meta\_size\_changed (F69)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_on\_text\_size\_changed` and `.\_on\_meta\_size\_changed` (methods); spins in \_settings\_frame\_text ("Preview font size (px)") and \_settings\_frame\_general ("Info table font size (px)")
- **Reason:** F69 – two font size spins; saving reloads the CSS rules, so no re-render is needed (unlike the F25 spacing handler).

```text
F69 (0.62.0): "Preview font size (px)" (Text files frame) scales the text previews – plain text, Markdown, source code, everywhere the preview sets the text itself; rendered pages (PDF, images) stay untouched. "Info table font size (px)" (General frame) scales the metadata tables in the preview and in the "more" windows. Both spins: Adjustment 0–28, step 1, page 2, 0 = the theme's normal size. The value-changed handlers store the value and call _config_save() only – the CSS provider reload inside it restyles open widgets live (UT-DOC-16), so unlike the F25 line spacing there is no re-render. 0.62.1 (user finding before deploy): the spins start PRE-FILLED with the detected system font size (system_font_size_px, UT-DOC-16) instead of 0 – turning 0 → 1 made the preview jump from the ~12 px system default to 1 px, which looked like a bug; 0 remains the explicit "theme default" choice in the tooltips.
```

---

### TB-DOC-19 – Docstring: \_xbit\_candidate (F74)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_xbit\_candidate` (method)
- **Reason:** F74 – the candidate check decides which files get the x-bit button (user decision: shebang scripts and ELF binaries only).

```text
F74 (0.66.0): the x-bit button only makes sense for files the kernel can execute, so the candidate check reads the FIRST FOUR BYTES of the file: ELF magic (\x7fELF) marks a binary, a leading shebang (#!) marks a script (shell, Python, Perl … – regardless of the file extension). Everything else – configs, data files, images – never sees the button. The read is capped at 4 bytes, unreadable files and non-files return False (button hidden).
```

---

### TB-DOC-20 – Docstring: \_on\_xbit\_clicked (F74)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_on\_xbit\_clicked` (method)
- **Reason:** F74 – full toggle of the owner execute bit; chmod errors stay dbg lines.

```text
F74 (0.66.0): full toggle of the OWNER execute bit only (u+x / u-x, user decision): the handler works on stat.S_IMODE, sets S_IXUSR or clears it and leaves group/other permission bits untouched. A failing chmod (read-only file system, foreign owner) stays a dbg line. The dbg success line names the file and the direction ("owner x-bit set"/"owner x-bit removed"), so a deploy test can prove BOTH directions in the log; _update_xbit_button refreshes state, tooltip and style right after the toggle. 0.66.2 (deploy feedback): the toggle now touches ALL THREE execute bits (u/g/o, mask 0o111) – a file that stayed executable through group or other (e. g. copied as 0755) looked like the button did nothing, and a bit set elsewhere could not be removed; the dbg lines say "x-bits set/removed (u/g/o)".
```

---

### TB-DOC-21 – Docstring: \_update\_xbit\_button (F74)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_update\_xbit\_button` (method) and the button block in `_build_toolbar`
- **Reason:** F74 – single refresh point for visibility, tooltip and the subtle red "already executable" state.

```text
F74 (0.66.0): single refresh point, called at the end of _render and in the empty-selection branch of set_selection (multi-selection hides the button too – a toggle would target only the first file). Visibility: single selection plus _xbit_candidate; state: S_IXUSR. While the bit is set the button carries the CSS class pvw-xbit-set (button.pvw-xbit-set { background: rgba(224,27,36,0.25); } – the F65 red #e01b24 at a quarter alpha, subtle on purpose) and the tooltip "Executable – click to remove the executable bit (owner)"; otherwise plain with "Make the file executable (owner)". The button sits pack_start at the LEFT end of the action bar (user wish), built in _build_toolbar with pick_icon("system-run-symbolic", "system-run"), relief NONE, no_show_all so show_all passes never reveal it. 0.66.1 (deploy crash): Gtk.ActionBar.pack_start() takes exactly ONE argument (the child) – unlike Gtk.Box there are no expand/fill/padding parameters; the first attempt passed five arguments and the panel never docked. The button now packs with pack_start(child), same call as the settings button. 0.66.2: the red got brighter (rgba(246,97,81,0.45) instead of the dark F65 red at a quarter alpha), the state is ANY execute bit (mask 0o111), the icon chain tries gtk-execute first (user wish) with system-run-symbolic/system-run fallbacks, the tooltips dropped the (owner) suffix, and a Gio file monitor (see TB-DOC-22) refreshes the button live when permissions change outside the extension.
```

---

### TB-DOC-22 – Docstring: \_xbit\_watch / \_on\_xbit\_file\_changed (F74)

- **Module:** previewer\_toolbar.py
- **Location:** `PreviewToolbarMixin.\_xbit\_watch` and `.\_on\_xbit\_file\_changed` (methods, both share this entry)
- **Reason:** F74 live refresh – permission changes made outside the extension (properties dialog) previously needed a re-selection.

```text
F74 (0.66.2, deploy feedback "not live"): one Gio file monitor on the previewed file. _xbit_watch(path) is the single management point, called from _update_xbit_button with the candidate path (or None): it cancels a pending monitor (self._xbit_mon, getattr-guarded because the panel builds before the first render) and, for a real path, creates a new one via Gio.File.new_for_path(path).monitor_file(Gio.FileMonitorFlags.NONE, None) and connects "changed". The handler _on_xbit_file_changed simply calls _update_xbit_button again – the inotify IN_ATTRIB path (chmod from the properties dialog) reaches the button without re-selecting the file. The refresh inside the callback recreates the monitor safely (cancel of the currently firing monitor is allowed, a fresh monitor fires nothing on creation, so there is no loop); errors stay dbg lines.
```

---

## Media (MED)

### MED-B7-1 – Own show\_all in the image idle callback (B7)

- **Module:** previewer\_render\_media.py
- **Location:** `_image_probe_done`, above `self._content.show_all()`
- **Reason:** R1 pattern from \_media\_probe\_done (0.10.4) – the missing show\_all was the actual field cause of the B7 regression.

```text
        # R1 pattern from _media_probe_done (0.10.4): widgets packed HERE lie AFTER the show_all() of the render pass – they need their own show_all, otherwise the preview stays invisible. Exactly this missing show_all was the actual field cause of the B7 regression.
```

### MED-SEEK-1 – Slider range follow-up

- **Module:** previewer\_render\_media.py
- **Location:** `_tick_player`, above `self._ensure_seek_range(dur)`
- **Reason:** The slider must cover the whole playback duration; with an initially unknown duration the range was 0–1 and the timer moved nothing.

```text
                    # The slider range must cover the ENTIRE length. If the duration was still unknown when it was created (e.g. when the Discoverer failed), the slider was built with range 0–1 – the timer could then never move it visibly. The range is therefore pulled up here once from the real playback duration.
```

### MED-AUDTAG-1 – Title/disc numbers in UINT and “n/m” string (F33)

- **Module:** previewer\_render\_media.py
- **Location:** `_tag_number_pair`, called from `_media_probe_async`
- **Reason:** Number tags run differently per codec: ID3 (MP3) and MP4 split TRCK/TPOS resp. trkn/disk into separate UINTs (track-number/track-count, album-volume-number/-count); Vorbis comments (FLAC, Ogg) often carry “3/12” as ONE string, sometimes entirely without their own total tag.

```text
        # F33: number pair from the tag list – UINTs are the normal case (GStreamer's ID3/MP4 mappers deliver number and total separately), but Vorbis variants report the number as a string “n/m”, sometimes without a separate total tag: partition("/") then gets both from one value. Every reading encapsulated individually – one outlier tag only hides its own row, never the cover.
```

### MED-AUDTAG-2 – Release year over three date shapes (F33)

- **Module:** previewer\_render\_media.py
- **Location:** `_tag_year`, called from `_media_probe_async`
- **Reason:** Original release before the date year (user request): original-date takes precedence, else datetime resp. date as the year. The value type depends on the codec – Gst.DateTime, GDate or string –, therefore three readings per candidate, each in its own capsule.

```text
        # F33: year – candidates are original-date (original release), then datetime (e.g. ID3v2.4 TDRC, Gst.DateTime) and date (older GDate tag, e.g. ID3v2.3 TYER). Every codec reports a different type, therefore all three readings are tried per candidate: DateTime.get_year(), GDate.get_year() and the string head (“2020-…”). The first real year wins.
```

### MED-COVER-1 – Cover rounding and shadow without blur (F34, F35)

- **Module:** previewer\_render\_media.py
- **Location:** `_cover_shadowed` (helper `_cover_round_path`), called from `_finish_audio`
- **Reason:** Cairo has no blur filter. The shadow therefore grows from six stacked, outward-growing tiles à 4 % opacity (F35: offset to the right and bottom, 3 px more room there – core ≈ 22 %, soft rim). The radius follows the placeholder tile (0.25.1, user request: 56/960 of the edge length – a third more subtle than F34's 56/640), so embedded covers and placeholders look identical and both grow with the live scaling.

```text
        # F34/F35: same rounding as the placeholder tile: 56/960 of the edge length (min(w, h), so portrait does not over-round), scales along because the padded pixbuf goes through the same live scaling. Cairo knows no blur – the shadow grows from six stacked, growing tiles (F35: offset to the right and bottom, 3 px more area there, more transparent overall). Without PangoCairo the cover stays unframed, the preview runs.
```

### MED-EXIF-1 – TIFF IFD traversal with bomb cap (F36)

- **Module:** previewer\_render\_media.py
- **Location:** `_exif_read_ifd`, called from `_exif_parse`
- **Reason:** EXIF is a TIFF-IFD mesh: values sit inline (up to 4 bytes) or behind an offset, and the special pointers ExifIFD (0x8769) and GPSIFD (0x8825) attach further IFDs. Doctored files could harass the parser with giant entry counts or pointers into the void – hence the entry cap (512), offset validation against the file length and recursion depth 2 (B7, the same discipline as the 0.9.2 decode cap).

```text
        # Every IFD entry is 12 bytes: tag, type, count, value or offset. Everything defensive: entry count capped, offsets checked against the file length, pointer IFDs (ExifIFD/GPSIFD) only two levels deep – a broken tag must never bring the parser to its knees, the image is shown anyway.
```

### MED-EXIF-2 – EXIF with built-ins and vendor fallbacks (F36)

- **Module:** previewer\_render\_media.py
- **Location:** `_exif_parse`, called in the worker of `_render_image`
- **Reason:** The wanted fields are standard EXIF, but vendors fill them differently: exposure time/aperture sometimes only as an APEX value (ShutterSpeedValue/ApertureValue), the real date sometimes only as DateTimeDigitized instead of DateTimeOriginal, the camera model with vendor duplication (“Canon Canon EOS …”), the shooting location as GPS degree minutes, sometimes also padding between the Exif marker and the TIFF header (Samsung/Olympus). The parser reads JPEG-APP1 and TIFF headers with Python built-ins (no new mandatory dependency, fitting the project's optional-module pattern) and formats every value only after its fallbacks – if everything is missing, the row stays away (“if present”).

```text
        # Order on purpose: the direct value wins, the APEX value is the vendor-specific second path (t = 2^-av, N = 2^(av/2)), the date runs as a cascade Original → Digitized → file date. GPS is converted from degrees/minutes/seconds into decimal degrees, the reference letters (N/S, E/W) come from the respective GPS tag. Without EXIF (SVG, PNG without eXIf) the table stays at height/width.
```

### MED-EXIF-3 – EXIF candidate loop for HEIC/HEIF and RAW (F41/F42)

- **Module:** previewer\_render\_media.py
- **Location:** `_exif_bases` (with `_exif_valid`), candidate loop in `_exif_parse` → `_exif_parse_at`, RAW fallback in `_image_probe_done` with `_exif_rows`
- **Reason:** User report: HEIC images showed no photo information – even after the first correction (F41). F41's cause analysis was incomplete: the old single search let the earliest “Exif” hit alone decide whether and where to search – and in the HEIC meta box the item type “Exif” stands literally, a false hit broke the search off early. On top of that the search windows (256 KB for the marker, 4 MB for the TIFF header) were too small: HEIC Exif items sometimes sit in the middle or at the end of the file. F42 solves this structurally: \_exif\_bases collects candidates in the WHOLE buffer (64 MB read cap) from three sources – “Exif” markers (APP1-like prefixes, also in RAWs with an embedded JPEG like RAF/RW2), direct TIFF headers II\*/MM\* (plain TIFF and TIFF-based RAWs like NEF, CR2, ARW, DNG, PEF carry it from byte 0) and Olympus ORF headers IIRO/IIRS (TIFF-like, but without the 42 magic – the IFD0 pointer still sits at offset 4). Every candidate is checked structurally by \_exif\_valid (magic optional, IFD0 offset ≥ 8, entry count 1–4096, first IFD completely in the buffer), duplicates sorted out; \_exif\_parse tries the candidates in order until one yields EXIF (JPEG preferred via the marker hit standing first). False hits therefore no longer doom the whole search. The RAW fallback shows the photo table (dimensions from A002/A003) below the icon view when Gdk-Pixbuf cannot decode; the image view shares the row logic with \_exif\_rows.

```text
        # The structural validation is the lifeline against chance hits in image or box data: an II*/MM* pattern alone is no miracle in compressed bytes – but faking ADDITIONALLY a plausible IFD0 offset AND an entry count between 1 and 4096 AND a complete first IFD in the buffer is practically impossible. And even a structurally valid false hit stays harmless: it yields no EXIF, the next candidate wins. Source note: bytes([0]) instead of null byte literals – escape traps when transferring into canvases/edits.
```

### MED-XMP-1 – XMP: location and user-defined fields (F38)

- **Module:** previewer\_render\_media.py
- **Location:** `_xmp_parse`/`_xmp_clean` with namespace filter `_XMP_STD`, called in the worker of `_render_image`
- **Reason:** The textual “location” does not sit in the EXIF part but in the XMP part of the JPEG (IPTC Core, `Iptc4xmpCore:Location` – digikam/Lightroom fill it in the location dialog), and user-defined fields live in their own XMP namespaces. Adobe tools like to write simple values as an attribute of rdf:Description instead of as their own element, therefore the parser checks both shapes. Everything outside the standard namespaces (\_XMP\_STD) counts as user-defined and is taken over as a “prefix:name” row – values are freed from XML remains, entities decoded, cut to 120 characters; at most ten extra rows, so experimental metadata does not flood the table.

```text
        # XMP lives in the JPEG-APP1 segment behind the Adobe URI; the RDF block reaches from <x:xmpmeta> to </x:xmpmeta>. Regex instead of XML parser: built-ins like on the EXIF path, no new mandatory dependency. Check element shape AND attribute shape – Adobe tools write simple values as an attribute of rdf:Description, own elements only for nested values (rdf:Bag/Seq). Trap in the element shape: a nested overall match (opening up to the matching closing tag) lets <x:xmpmeta> as the FIRST hit consume everything up to the last </x:xmpmeta> – the actual fields would never be reached. Therefore only opening tags are scanned and the matching closing tag is searched per field; the namespace filter skips the standard wrappers (x, rdf), the scan still continues.
```

### MED-SPLIT-1 – Column split 60/40 with live follow-up (F38)

- **Module:** previewer\_render\_media.py
- **Location:** `_pack_image_capped` with helper `_image_split_sync`, used by `_render_image`, `_render_svg` and since F59 (0.44.0) `_render_ebook` (e-books: cover on top, book info below)
- **Reason:** Gtk.Box knows no percentage split – expand is a switch, not a ratio. The image area therefore carries 60 % of the column height as its size request; a size-allocate follow-up keeps the split current on window resizes. Centering is done by halign/valign CENTER on the Gtk.Image (NOT on the ScrolledWindow – the stripe bug in the 0.22.0 test), the info area expands and fills the rest (≈ 40 %).

```text
        # Gtk.Box divides extra space only evenly among expanding children – 60/40 does not exist as a switch. The image area therefore carries 60 % of the column height as its request and pulls it up in size-allocate (only on relevant change, otherwise the request loop tears the layout into endless loops). Centering is done BY THE IMAGE, not the ScrolledWindow: a scrollable widget may drop its natural width to ~0 – align=CENTER takes exactly that natural size, so the scroll window scaled to column width would only be a narrow stripe clipping the image. The Gtk.Image sits in the scroll via a viewport; its halign/valign CENTER centers it in both directions inside the 60 % area. The area itself needs expand=False against the height – expand/fill only affect the HEIGHT in the vertical box, the width across is given to the children by the box anyway.
```

### MED-SVG-DPI-1 – SVG DPI rendering over the Cairo route (K3)

- **Module:** previewer\_render\_media.py
- **Location:** `_rsvg_cairo_pb`, used by `_render_svg` (fallback: `get_pixbuf`)
- **Reason:** get\_pixbuf() renders strictly at the intrinsic size – a 24×24 icon SVG stays a mini dot in the column, and since librsvg 2.52 the call is deprecated anyway. render\_document on the other hand takes an Rsvg.Rectangle as the target area: the same vector geometry, an arbitrary DPI scale. If the route fails (no pycairo, old librsvg without render\_document, no intrinsic size), the previous path applies – the preview is therefore never worse than before; the dimensions label shows the intrinsic size in both cases.

```text
        # The intrinsic size (get_intrinsic_size_in_pixels) is the calculation base: the panel width is the render target, small SVGs grow sharp (vector instead of raster upcast, no blur), the cap height limits the target area upward. The rendered pixbuf goes through _scaled_image into the 60/40 split as before – the live scaling on window resize then however falls back to the raster pixbuf.
```

### MED-DOC-1 – Docstring: \_media\_gi\_warmup

- **Module:** previewer\_render\_media.py
- **Location:** `\_media\_gi\_warmup` (module level)
- **Reason:** R1 hardening – GI method tables resolved once in the GTK thread.

```text
R1 hardening: PyGObject builds the method tables of GI classes only on the FIRST attribute access. So that the discovery worker (which reads the media tags) finds stable conditions, the first contact with all involved classes happens once in the GTK thread (see _media_probe_async). The name discover_uri_sync is deliberately touched here as well: if it does not exist in the binding, that is not an error – the discovery then falls back to the correct name discover_uri.
```

### MED-DOC-2 – Docstring: \_exif\_read\_ifd

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_read\_ifd` (module level)
- **Reason:** TIFF IFD reader with EXIF/GPS sub-IFDs (B7 depth cap).

```text
Read a TIFF IFD: collects tag→(type, raw bytes) and loads the special pointers ExifIFD (0x8769) and GPSIFD (0x8825) as sub-IFDs. depth dampens pointer madness (B7).
```

### MED-DOC-3 – Docstring: \_exif\_str

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_str` (module level)
- **Reason:** ASCII tag value as text.

```text
ASCII field (type 2) as text or None.
```

### MED-DOC-4 – Docstring: \_exif\_num

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_num` (module level)
- **Reason:** First numeric value of a tag (SHORT/LONG).

```text
First numeric value (SHORT/LONG) of a tag or None.
```

### MED-DOC-5 – Docstring: \_exif\_frac

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_frac` (module level)
- **Reason:** RATIONAL tag value as float.

```text
RATIONAL/SRATIONAL (num/den) as float or None.
```

### MED-DOC-6 – Docstring: \_exif\_dms

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_dms` (module level)
- **Reason:** GPS degrees/minutes/seconds to decimal degrees.

```text
GPS degrees/minutes/seconds (3 RATIONALS) to decimal degrees.
```

### MED-DOC-7 – Docstring: \_xmp\_clean

- **Module:** previewer\_render\_media.py
- **Location:** `\_xmp\_clean` (module level)
- **Reason:** F38 XML remain and entity cleanup for XMP values.

```text
F38: strip XML remains from XMP values; decode entities.
```

### MED-DOC-8 – Docstring: \_xmp\_parse

- **Module:** previewer\_render\_media.py
- **Location:** `\_xmp\_parse` (module level)
- **Reason:** F38 XMP parser with on-board tools (regex over the RDF/XML).

```text
F38 (user wish): read XMP fields from the JPEG APP1 segment with Python on-board tools (regex over the embedded RDF/XML, no new mandatory dependency – matching the EXIF parser). The return is a dict: “Location” (IPTC Core, element OR attribute form) plus user-defined fields from non-standardized namespaces as “prefix:name” – only present, non-empty values.
```

### MED-DOC-9 – Docstring: \_exif\_valid

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_valid` (module level)
- **Reason:** F42 structure check of a TIFF candidate.

```text
F42: structure check of a TIFF candidate (42 magic optional – Olympus ORF carries “RO” instead of 42): IFD0 offset ≥ 8, entry count 1–4096, first IFD completely inside the buffer.
```

### MED-DOC-10 – Docstring: \_exif\_bases

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_bases` (module level)
- **Reason:** F42 EXIF candidates over the whole buffer (HEIC/RAW included).

```text
F42 (user report): returns EXIF candidates in the WHOLE buffer – pairs (base offset, check the 42 magic). Three sources:
1. “Exif” markers as in JPEG APP1 – HEIC/HEIF EXIF items partly carry the same prefix, often in the middle or at the end of the file; behind it, after F36 padding, follows the TIFF head. RAWs with an embedded JPEG (RAF, RW2) come in the same way.
2. Direct TIFF heads (II*/MM*) – HEIC items without prefix, plain TIFF and TIFF-based RAWs (NEF, CR2, ARW, DNG, PEF) carry it from byte 0 or in a sub-block.
3. Olympus ORF heads (IIRO/IIRS) – TIFF-like, without the 42 magic.
Every candidate is validated (_exif_valid), duplicates drop out. A wrong “Exif” hit – the item type in the HEIC meta box is one – fails the validation or yields no EXIF; the next candidate wins. Exactly that is where F41 failed: the earliest “Exif” hit alone determined whether and where to search. Order: markers before direct heads, each by position.
```

### MED-DOC-11 – Docstring: \_exif\_parse

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_parse` (module level)
- **Reason:** F36/F42 EXIF core extraction with on-board tools and vendor fallbacks.

```text
F36: core EXIF information from JPEG/TIFF bytes – with Python on-board tools, without a new mandatory dependency. Vendor peculiarities are caught by standard fallbacks (APEX instead of direct value, date cascade, GPS decimal degrees). The return is a dict with finished display texts – only present values. F42 (user report): candidate loop – _exif_bases collects validated TIFF candidates in the whole buffer, the first one with EXIF wins (HEIC/HEIF and RAW, → REF MED-EXIF-3).
```

### MED-DOC-12 – Docstring: \_exif\_bo

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_bo` (module level)
- **Reason:** S8 byte order of the TIFF head.

```text
S8 (0.42.0): byte order of the TIFF head – None if head or magic do not fit (MM/II; 42 magic, Olympus ORF carries “RO”).
```

### MED-DOC-13 – Docstring: \_exif\_camera

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_camera` (module level)
- **Reason:** F36 camera model with vendor prefix shortening.

```text
F36: camera model – many models repeat the vendor in the model name (“Canon” + “Canon EOS …”): shorten only then.
```

### MED-DOC-14 – Docstring: \_exif\_parse\_at

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_parse\_at` (module level)
- **Reason:** F42/S8 EXIF at one TIFF base offset, per topic helper.

```text
F42: EXIF at ONE TIFF base offset – the formatting part of the F36 logic, called per candidate by the candidate loop. S8 (0.42.0): decomposed – _exif_bo checks the head, a small helper fills the dict per topic block (camera, date, exposure, aperture, focal length, ISO/dimensions, location); everything stays in a try against broken files.
```

### MED-DOC-15 – Docstring: \_exif\_rows

- **Module:** previewer\_render\_media.py
- **Location:** `\_exif\_rows` (module level)
- **Reason:** F42 photo rows from EXIF/XMP for image view and RAW fallback.

```text
F42: photo rows from EXIF/XMP – shared by the image view (below height/width) and the RAW fallback (below the icon). Only present values, order as in the image table. F50 (user wish 2026-11-02): the table ends at ISO – the XMP custom fields leave the table; ALL contained details show in the "more" window via exiftool.
```

### MED-DOC-16 – Docstring: MediaRendererMixin (class)

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin` (class)
- **Reason:** Class marker – image/SVG/audio/video renderers.

```text
Mixin: renderers for image (including EXIF), SVG, audio and video.
```

### MED-DOC-17 – Docstring: \_pack\_image\_capped

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_pack\_image\_capped` (method)
- **Reason:** F38 60/40 column split for image previews.

```text
F38 (user wish): for image previews the column is split into a 60 % area for the image (centered vertically and horizontally) and a 40 % area for the image information; between the two a separator. The height of the image area is kept live at 60 % of the column height.
```

### MED-DOC-18 – Docstring: \_image\_split\_sync

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_image\_split\_sync` (method)
- **Reason:** F38 live follow-up of the 60 % image area.

```text
F38: pull the image area to 60 % of the column height.
```

### MED-DOC-19 – Docstring: \_rsvg\_cairo\_pb

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_rsvg\_cairo\_pb` (method)
- **Reason:** K3 Cairo route – SVG rendered DPI-like at panel width.

```text
K3 (2026-10-30): render SVG over the Cairo route (render_document) DPI-like at the panel width – intrinsically small SVGs stayed tiny so far, and get_pixbuf() is deprecated in newer librsvg. The return is (pixbuf, (width, height)) in INTRINSIC pixels or None – the caller then falls back to the previous get_pixbuf() path.
```

### MED-DOC-20 – Docstring: \_render\_svg

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_render\_svg` (method)
- **Reason:** SVG preview via librsvg with K3 Cairo route and old-path fallback.

```text
SVG preview via librsvg: GdkPixbuf cannot load SVG. K3 (2026-10-30): prefers the Cairo route (_rsvg_cairo_pb – DPI-like at panel width, render_document instead of the deprecated get_pixbuf()); if it fails (no pycairo, old librsvg, no intrinsic size), the old path takes over. The dimensions label shows the INTRINSIC size.
```

### MED-DOC-21 – Docstring: \_render\_image

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_render\_image` (method)
- **Reason:** R9 two-stage image loading without UI blockade.

```text
R9 (0.10.2) with field fix (0.10.3): large images (typically 20 MB JPEGs with 50–100 megapixels) blocked the GTK main loop – reading, decoding and EXIF rotation ran synchronously in one go on selection, the UI stood still. Two-stage like the media (R1): (1) show a hint immediately, the UI stays usable; (2) the daemon thread reads ONLY the file (pure Python I/O) and passes the bytes back via GLib.idle_add. Decoding, EXIF rotation and scaling run back in the GTK thread – the 0.10.2 field test showed: Gdk objects (PixbufLoader) in the worker fail silently, the R1 pattern “no Gdk objects in the worker” applies here too. The speed lever stays the decode cap max(2 × panel width, 1024): decoding becomes many times cheaper, the live scaling loses nothing (the source stays wider than any panel width, as with PDF R2 at 2-fold width). The bomb protection from 0.9.2 stays fully intact. If the thread start exceptionally fails, the old synchronous path runs as a lifeline.
```

### MED-DOC-22 – Docstring: \_image\_probe\_done

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_image\_probe\_done` (method)
- **Reason:** R9 return of the worker bytes into the GTK thread.

```text
R9 return (0.10.3/0.10.4): decode the bytes read in the worker HERE in the GTK thread (same discipline as the media covers in _media_probe_done – Gdk objects are only created in the GTK thread). Decode cap target_w; if the selection has moved on, the result is silently discarded. If decoding fails, the synchronous at_scale fallback takes over (it caps the decoding internally and is therefore also bomb-proof); only when that fails too does the generic error hint appear. 0.10.4: all widgets packed here sit AFTER the show_all() of the render pass – exactly as in _media_probe_done, the callback therefore needs its OWN show_all, otherwise the preview stays invisible (the field cause of the B7 regression, overlooked in 0.10.2/0.10.3).
```

### MED-DOC-23 – Docstring: \_render\_audio

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_render\_audio` (method)
- **Reason:** Audio preview – cover, tags and player bar.

```text
Audio preview: cover, tags and player bar. R1: tags, duration and cover are detected in the background thread (see _media_probe_async) – the panel appears immediately with a reading hint and stays usable, instead of freezing on the spot when the medium is slow to reach.
```

### MED-DOC-24 – Docstring: \_media\_probe\_async

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_media\_probe\_async` (method)
- **Reason:** R1 media discovery in a daemon thread (discover_uri fix).

```text
R1: media discovery without UI blockade. The GStreamer discoverer runs in a daemon thread (tags, duration, image bytes – NO pixbuf, Gdk objects are only created back in the GTK thread) and swings the result into the main loop via GLib.idle_add; finish is the continuation (_finish_audio/_finish_video).

R1 fix (0.5.0 test result): the synchronous discovery is called discover_uri() in the Python binding – the C name gst_discoverer_discover_uri is bound WITHOUT “_sync”; a discover_uri_sync does not exist (AttributeError). The tags/duration/cover discovery had therefore NEVER worked – the placeholder cover (F18) exposed the old bug for the first time. Additionally, the GI classes are warmed up once HERE in the GTK thread (PyGObject resolves method tables lazily) and the discovery runs in the worker as a fully resolved callable.
```

### MED-DOC-25 – Docstring: \_media\_probe\_done

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_media\_probe\_done` (method)
- **Reason:** R1 return of the background discovery into the GTK main loop.

```text
R1: return of the background discovery into the GTK main loop.
```

### MED-DOC-26 – Docstring: \_media\_cover\_placeholder

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_media\_cover\_placeholder` (method)
- **Reason:** F18/F22 generic tile for media without an embedded image.

```text
Generic tile for media without an embedded image: dark tile with a diagonal color gradient, a semi-transparent symbol and rounded corners – drawn at double resolution (640 px for a 320 px display) so the tile stays sharp on HiDPI screens too. Music without a cover (F18) shows the note symbol, video without an embedded preview image (F22) the play triangle with film perforation at the top and bottom edge. Without PangoCairo (or on drawing errors) an icon fallback on a dark background takes over.
```

### MED-DOC-27 – Docstring: \_tag\_number\_pair

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_tag\_number\_pair` (method)
- **Reason:** F33 (number, total) from the tag list, codec-dependent.

```text
F33: read (number, total) from the tag list – track number and disc number are packaged differently depending on the codec.
```

### MED-DOC-28 – Docstring: \_tag\_year

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_tag\_year` (method)
- **Reason:** F33 release year over three date shapes.

```text
F33: release year – the original release takes precedence, otherwise the date tag is read as the year.
```

### MED-DOC-29 – Docstring: \_cover\_shadowed

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_cover\_shadowed` (method)
- **Reason:** F34 cover with placeholder corners and drop shadow.

```text
F34: cover with placeholder corners and a small drop shadow.
```

### MED-DOC-30 – Docstring: \_finish\_audio

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_finish\_audio` (method)
- **Reason:** R1 continuation – cover, player bar and info rows (F33 order).

```text
R1 continuation: build cover, player bar and info. F33 (user wish): the bar sits with some distance BELOW the cover, the information follows underneath – no longer above it.
```

### MED-DOC-31 – Docstring: \_playbin\_set\_uri

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_playbin\_set\_uri` (method)
- **Reason:** B2 playbin with bus watch – central building block.

```text
Create the playbin once and set the URI. B2: bus watch – without it the player does not know its track end (pause icon stayed, position froze) and playback errors remained invisible. Central building block – a later retry of video playback can reuse it unchanged.
```

### MED-DOC-32 – Docstring: \_player\_bar

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_player\_bar` (method)
- **Reason:** B2/B3 player bar – play/pause, slider, position.

```text
Build and pack the player bar (play/pause, slider, position) – the central building block of the music preview (B2/B3). 0.65.5 (F72): play/pause button and seek slider carry tooltips (state-following Play/Pause, Seek position) – the bar is no longer the nameless corner of the a11y inventory.
```

### MED-DOC-33 – Docstring: \_on\_player\_eos

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_player\_eos` (method)
- **Reason:** B2 track end handling.

```text
Track end: back to the beginning, icon back to play (B2).
```

### MED-DOC-34 – Docstring: \_on\_player\_error

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_player\_error` (method)
- **Reason:** B2 silent stop on playback errors.

```text
Playback error: stop silently and report in the panel (B2).
```

### MED-DOC-35 – Docstring: \_ensure\_progress\_timer

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_ensure\_progress\_timer` (method)
- **Reason:** B3 position timer, only while playing.

```text
Create the position timer if it is not running right now (B3).
```

### MED-DOC-36 – Docstring: \_render\_video

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_render\_video` (method)
- **Reason:** Video preview – tile and info via R1 discovery.

```text
Video preview: tile and info. R1: discovery in the background thread (see _media_probe_async) – the UI stays usable immediately. Without an embedded preview image the generic tile appears as with music (F22). The panel playback from 0.7.0–0.7.2 was removed again in 0.8.0 – to play, the open button (media program of choice).
```

### MED-DOC-37 – Docstring: \_finish\_video

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_finish\_video` (method)
- **Reason:** R1 continuation for the video preview.

```text
R1 continuation: build tile and info.
```

### MED-DOC-38 – Docstring: \_tick\_player

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_tick\_player` (method)
- **Reason:** B3 position display tick while playing.

```text
Update the position display (B3: only during playback).
```

### MED-DOC-39 – Docstring: \_ensure\_seek\_range

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_ensure\_seek\_range` (method)
- **Reason:** Slider range follow-up to the real duration.

```text
Adjust the slider range to the real duration (ns) if necessary.
```

### MED-DOC-40 – Docstring: \_update\_seek\_pos

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_update\_seek\_pos` (method)
- **Reason:** Slider follow-up to the current position.

```text
Move the slider to the current position (ns).
```

### MED-DOC-41 – Docstring: \_on\_exif\_more

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_exif\_more` (method)
- **Reason:** F50 "more" window – ALL EXIF details via exiftool.

```text
F50 (user wish 2026-11-02): the "more" button in the photo info area opens a window with ALL EXIF details of the image, raw but formatted – fetched via exiftool. Spawn as an ARGV list with the absolute path (no shell, no PATH search); the io watch runs in the GTK main loop (no Gdk in a worker); monospace read-only TextView, output capped at 2000 lines; without exiftool the button never appears – the info area shows an install hint with the Debian package name libimage-exiftool-perl instead. 0.48.1 (user deploy feedback): the "more" button keeps NORMAL relief (it must look like a button). 0.48.2: button margins move it 10px down and right of the table; PyGObject's spawn_async_with_pipes return tuple varies by version (ValueError, then EBADF) – the data now comes from a worker thread: subprocess.Popen with an ARGV list (no shell), stderr merged in, buffer fed via GLib.idle_add (R9: no Gdk in the worker). 0.48.3 (user wish): 10px inner padding via the TextView left/right/top/bottom margins – the scrollbar stays flush at the window edge (F46 IX lesson: padding, no margin). 0.49.0: the window opens centered on the screen with ~60 % of the screen height (user rule for all opening windows, → REF UT-DOC-15). 0.50.1 (user wishes 2026-11-03): the EXIF window shows the same two-column tag table as the audio window – shared helpers _tags_table_window/_exiftool_tag_rows (subtle horizontal grid lines, 10px inner padding, colons after the tag names, unified 500-row cap instead of 2000 lines); the monospace TextView variant is gone. 0.50.2 (deploy feedback): Gtk.TreeView.set_enable_grid_lines is NOT mapped in the user's PyGObject build (AttributeError on both "more" windows) – the grid lines go through set_property("enable-grid-lines") now; if the property is missing too, set_rules_hint(True) adds subtle alternating row banding instead, every step dbg-logged. 0.51.0: the handler is a one-line delegate now – window and worker live in the shared _on_tags_more (→ REF MED-DOC-44). 0.51.1 (user wishes): grid lines BOTH (vertical separator between tag and value columns as well), tag names bold (renderer weight 700 = PANGO_WEIGHT_BOLD) and values italic (renderer style 2 = PANGO_STYLE_ITALIC) – numeric Pango values via renderer properties, no extra Pango import.
```

### MED-DOC-43 – Docstring: \_on\_video\_more

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_video\_more` (method)
- **Reason:** F62 video "more" window – all tags of the video file as a table.

```text
F62 (user wish 2026-11-04): the "more" button below the video info table opens the shared tag table window with ALL tags of the video file. exiftool delivers the raw tag set per container – QuickTime/MP4 atoms, Matroska, AVI RIFF, WebM – so the tags differ between formats by design, exactly as with photos (F50) and music (F61). Thin one-line delegate: it passes its title ("Video tags – <name>") to _on_tags_more (→ REF MED-DOC-44); button and install hint follow the F50/F61 pattern (EXIFTOOL check, margins 10, dim label without exiftool – Debian package libimage-exiftool-perl).
```

### MED-DOC-44 – Docstring: \_on\_tags\_more

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_tags\_more` (method)
- **Reason:** Shared "more" window logic for photo, audio and video tags.

```text
0.51.0 (with F62): the window-and-worker logic that _on_exif_more (MED-DOC-41) and _on_id3_more (MED-DOC-42) carried as identical twins since 0.50.1 became ONE generic handler for all three media kinds: it builds the shared _tags_table_window with the given title, a worker thread fetches _exiftool_tag_rows(path) (R9: no Gdk in the worker), apply clears the "collecting" placeholder row and fills the store, an empty result falls back to an "Info:"/"no tags found" row. The three callers are one-line delegates that only pass their title: "EXIF details", "Audio tags", "Video tags". Window design, grid lines, padding, colons and the 500-row cap stay as documented in MED-DOC-41/42. 0.51.1 (user wishes): the design adds a vertical separator between the columns (grid lines BOTH), bold tag names and italic values (→ MED-DOC-41 carries the design note). 0.51.2 (user wish): ONE window only – class attributes _tags_win/_tags_store/_tags_gen hold the per-panel state; while the window is open, a "more" click on another file updates title, clears the store, shows the "collecting" placeholder and presents the SAME window (no second window); a generation counter (_tags_gen) drops results of outdated workers, so fast clicking never mixes rows of two files; after "destroy" the next click builds a fresh window (→ REF MED-DOC-45). 0.51.3 (user wishes): the window is kept ABOVE the file window via set_transient_for(self._content.get_toplevel()) – transient windows never sink behind their parent; manual "more" clicks focus the window (present), the automatic follow-up (→ REF MED-DOC-46) never steals focus.
```

### MED-DOC-46 – Docstring: \_tags\_win\_follow

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_tags\_win\_follow` (method)
- **Reason:** Auto-refresh of the open "more" window on media selection changes.

```text
0.51.3 (user wishes 2026-11-04): while the "more" window is open, selecting another media file refreshes it AUTOMATICALLY – no second click on the button. The three render entry points call it first with their kind title: _render_image → "EXIF details", _render_audio → "Audio tags", _render_video → "Video tags". No-op while the window is closed. The call routes into _on_tags_more(title, present=False) (→ REF MED-DOC-44): title and store update, but the focus stays with the file window. Non-media selections (folders, documents, text) leave the window untouched – it keeps the last media file's tags until another media file is selected or the window is closed.
```

### MED-DOC-45 – Docstring: \_on\_tags\_win\_destroyed

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_tags\_win\_destroyed` (method)
- **Reason:** Cleanup for the one "more" window per panel.

```text
0.51.2: connected to the tag window's "destroy" signal when it is built; when the user closes the window, the singleton state resets (\_tags\_win and \_tags\_store back to None), so the next "more" click builds a fresh window. The generation counter \_tags\_gen deliberately survives – it only ever grows, so stale workers of the closed window stay discarded even if their idle callback still fires.
```

### MED-DOC-42 – Docstring: \_on\_id3\_more

- **Module:** previewer\_render\_media.py
- **Location:** `MediaRendererMixin.\_on\_id3\_more` (method)
- **Reason:** F61 audio "more" window – all tags of the file as a table.

```text
F61 (user wish 2026-11-03): the "more" button below the audio info table opens a window with ALL tags of the music file in tabular form. exiftool delivers the raw tag set per format – ID3v1/v2 (MP3), Vorbis comments (FLAC/OGG), QuickTime atoms (M4A), RIFF INFO (WAV) – so the tags differ between file formats by design; the table shows whatever the format carries. Same window and worker rules as the EXIF window (F50): center_window (→ REF UT-DOC-15; 560 wide, title "Audio tags – <name>"), worker thread with subprocess.Popen ARGV list (no shell, stderr merged, R9: no Gdk in the worker), rows fed via GLib.idle_add. exiftool prints "Tag name : value" per line – partition at the FIRST colon (values may contain colons), both sides stripped; rows capped at 500, a "…" row reports the rest; zero rows fall back to an "Info" row. Two-column Gtk.TreeView (Tag/Value; value cells wrap at 460 px, both columns resizable, selection off); without exiftool the button never appears – a dim-label install hint with the Debian package name libimage-exiftool-perl shows instead. 0.50.1 (user wishes 2026-11-03): colons after the tag names, subtle horizontal grid lines and 10px inner padding; window builder and exiftool parser now serve BOTH media "more" windows as shared helpers (_tags_table_window, _exiftool_tag_rows) – the tag column always carries a colon, the "…" cap row never does; a "collecting" placeholder row shows until the worker delivers. 0.50.2 (deploy feedback): the grid lines use set_property("enable-grid-lines") – the set_enable_grid_lines METHOD raised AttributeError in the user's PyGObject build; rules_hint banding is the logged fallback (→ MED-DOC-41 carries the same note for the shared helper). 0.51.0: the handler is a one-line delegate now – window and worker live in the shared _on_tags_more (→ REF MED-DOC-44).
```

### MED-DOC-47 – Docstring: \_ensure\_gst (K5)

- **Module:** previewer\_render\_media.py
- **Location:** module level behind the util imports; replaces the old module-level Gst import + Gst.init block; callers in the panel render switch
- **Reason:** K5 – lazy GStreamer init: the Nemo start must not pay the Gst.init cost.

```text
K5 (0.57.0): GStreamer was imported and initialized (Gst.init(None)) at MODULE IMPORT – the panel imports render_media at every Nemo start, so every session paid the GStreamer registry cost although most sessions never preview audio or video. Now HAVE_GST starts as None (undecided) and Gst/GstPbutils as None; _ensure_gst() does the one-shot work on the first call – gi.require_version, import, Gst.init, assign the module globals, cache True/False in HAVE_GST, return it. The panel's render switch calls _ensure_gst() instead of the old HAVE_GST flag (Python binds imported values at import time – an accessor function is the only safe way, same lesson as set_debug_log in 0.54.0); the audio and video branches render only on True, otherwise the install hint / generic preview shows as before. All Gst/GstPbutils uses live inside the audio/video renderers, which the switch only enters after a successful ensure – the None globals can never be touched. The first media preview pays the init (tens of ms with a warm registry); thanks to the F2 debounce that moment is exactly when the user lingers on a file anyway.
```

---

## Documents (DOC)

### DOC-BUDGET-1 – PDF pixel budget (0.9.2)

- **Module:** previewer\_render\_docs.py
- **Location:** `_pdf_page_pixbuf`, above the budget query `if w * h > _PDF_PIXEL_BUDGET:`
- **Reason:** Giant PDF pages would otherwise force ≈ 1.6 GB per page; the result is scaled back area-true, normal pages stay untouched.

```text
        # 0.9.2: pixel budget – the lower scale clamp (0.2) would otherwise force 20000×20000 px ≈ 1.6 GB per page on pathologically giant PDF pages (e.g. 100000 pt). If the result exceeds the budget, it is scaled back area-true; normal pages (even twice as wide panels) stay untouched.
```

### DOC-F14-1 – Page label instead of scroll hint (F14)

- **Module:** previewer\_render\_docs.py
- **Location:** `_render_pdf`, above `self._content.show_all()`
- **Reason:** The page label shows the page count by itself now; the office callback calls \_render\_pdf directly and therefore needs its own show\_all. 0.27.0 (user request): the label now sits above EVERY document – single-page ones show “Page 1 of 1” too – and counts uniformly in the format “Page X of Y”; the cap itself is configurable (F12 part 3).

```text
        # F14: the page label shows the page count by itself now – the former hint “N pages – scroll down for the preview.” is gone with that. The office callback calls _render_pdf DIRECTLY (without the show_all follow-up of _render) – hence provide here.
```

### DOC-UPSCALE-1 – Scale thumbnails to panel width

- **Module:** previewer\_render\_docs.py
- **Location:** `_render_office_thumb`, above `self._scaled_image(...)`
- **Reason:** Office thumbnails (often only 256 px) grow with the panel width instead of clinging small in the corner.

```text
                    # Upscale: office thumbnails are often only 256 px wide – they grow with the panel width instead of clinging small in the corner. Show office thumbnails NATIVE and sharp: the embedded thumbnail has only ~256 px – any enlargement makes it unreadably blurry.
```

### DOC-B4-1 – Cache the failed conversion (B4)

- **Module:** previewer\_render\_docs.py
- **Location:** `_office_job_done`, above `self._office_failed.add(path)`
- **Reason:** Without a cache, EVERY selection would convert again (infinite loop); the finished PDF is rendered directly from the temp folder.

```text
                    # B4: without a cache, EVERY selection would convert again (infinite loop, the same symptom as the old EXDEV bug). Therefore: note it as failed, but do not throw away the finished PDF – the sharp view is rendered directly from the temp folder (Poppler reads the pages immediately, after that the file does not matter).
```

### DOC-LEGACY-1 – Office formats without a ZIP share (F39)

- **Module:** previewer\_render\_docs.py
- **Location:** `_render_office_thumb`, safeguard via `_OFFICE_NOZIP_EXTS`
- **Reason:** The transition view reads the embedded thumbnail and the text extract from office files – both sit only in ZIP archives (ODF/OOXML). The old binary formats (.doc/.xls/.ppt) and RTF are no ZIP archives: zipfile fails, and without their own branch the misleading error message “Office document could not be opened” would stand in the preview. The branch distinguishes three cases: conversion running (hint waits for the sharp PDF), conversion failed (broken file, via \_office\_failed not endlessly retried) and LibreOffice/Poppler missing (installation hint).

```text
        # The sharp route is the same for all office formats (LibreOffice --convert-to pdf also eats the binary formats and RTF), only the transition until then is EMPTY for them: no ZIP, no thumbnail, no text extract. Therefore the no-ZIP branch ends in a hint instead of an error – and without LibreOffice/Poppler in an installation tip instead of diagnosing a broken file.
```

### DOC-DOC-1 – Docstring: office\_cache\_dir

- **Module:** previewer\_render\_docs.py
- **Location:** `office\_cache\_dir` (module level)
- **Reason:** Cache folder for LibreOffice conversion PDFs.

```text
Cache folder ~/.cache/previewer (created on demand). 0.65.5 (F70): the cache is BOUNDED – _OFFICE_CACHE_MAX (256 MB) plus office_cache_evict(), which runs after every successful cache write and removes the oldest files first.
```

### DOC-DOC-2 – Docstring: office\_cache\_path

- **Module:** previewer\_render\_docs.py
- **Location:** `office\_cache\_path` (module level)
- **Reason:** Cache key of a converted PDF.

```text
Cache path of the converted PDF (key = hash of the absolute path).
```

### DOC-DOC-3 – Docstring: \_extract\_office\_text

- **Module:** previewer\_render\_docs.py
- **Location:** `\_extract\_office\_text` (module level)
- **Reason:** Text excerpt from the Office ZIP with the R10 entity guard.

```text
Pull a text excerpt from an Office ZIP. ODF carries the content in content.xml (text:p/text:h/text:span), OOXML in word/document.xml (w:p/w:t) – in both cases collecting the text nodes is enough, paragraphs are carried over as line breaks.
```

### DOC-DOC-4 – Docstring: DocsRendererMixin (class)

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin` (class)
- **Reason:** Class marker – document renderer mixin.

```text
Mixin: renderers for PDF and office documents.
```

### DOC-DOC-5 – Docstring: \_pdf\_page\_pixbuf

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._pdf\_page\_pixbuf` (method)
- **Reason:** Renders one PDF page with white backing and pixel budget.

```text
Render one PDF page at target_w pixels width (white backing).
```

### DOC-DOC-6 – Docstring: \_pdf\_page\_cap

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._pdf\_page\_cap` (method)
- **Reason:** F12 part 3 – effective page-limit value with fallback.

```text
F12 part 3 (0.27.0): effective cap for the document preview – 0 means unlimited, otherwise the number of pages shown. Configurable in the settings window (performance); if the config values are missing (old conf, foreign binding), the previous state applies: limit with MAX_PDF_PAGES.
```

### DOC-DOC-7 – Docstring: \_render\_pdf

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._render\_pdf` (method)
- **Reason:** Scrollable PDF preview with F14 page indicator and R2 idle feed.

```text
PDF preview scrollable: all pages (up to the configured cap, otherwise all) are stacked vertically in a scrollable area. Each page is rendered at double panel width and – as with the image preview – only re-scaled on width changes, not re-rendered. F14: a subtle label "Page X of Y" above the area follows the page at the top edge of the viewport while scrolling – since 0.27.0 ALWAYS, one-page documents also show "Page 1 of 1" (user request). R2: page 1 is rendered synchronously right away, the remaining pages are fed piecewise in a GLib idle – the panel appears instantly even for large/scanned PDFs, the UI does not freeze.
```

### DOC-DOC-8 – Docstring: \_pdf\_idle\_step

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._pdf\_idle\_step` (method)
- **Reason:** R2 – one more PDF page per idle cycle, generation-guarded.

```text
R2: render one more PDF page in the idle (UI stays responsive). The index is carried in the call, not derived from len(self._pdf_src) – otherwise a render error could become an endless loop. Returns False: do not repeat automatically, the follow-up is scheduled explicitly each time.
```

### DOC-DOC-9 – Docstring: \_on\_pdf\_scrolled

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._on\_pdf\_scrolled` (method)
- **Reason:** F14 – page indicator follows the viewport while scrolling.

```text
F14: update the page indicator while scrolling. Current is the page whose bottom edge crosses the top edge of the viewport – the page you are on. The coordinates of the page images are box coordinates and thus directly comparable with the scrollbar value.
```

### DOC-DOC-10 – Docstring: \_pdf\_scale\_one

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._pdf\_scale\_one` (method)
- **Reason:** Live scaling of a single PDF page (never upscaled).

```text
Scale one PDF page to the target width and assign it.
```

### DOC-DOC-11 – Docstring: \_apply\_pdf\_scale

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._apply\_pdf\_scale` (method)
- **Reason:** Re-scales the PDF pages on width changes – K12: incrementally, only page 1 synchronously.

```text
Fit the PDF pages to the current panel width. K12 (0.60.1): only page 1 scales synchronously – the top page stays exact and the pass stays cheap even mid-drag; the remaining pages follow via _pdf_scale_step, a few per idle cycle. Until 0.60.0 this loop scaled EVERY page inline in the size-allocate handler; while dragging the column the passes starved the main loop (the preview lagged behind) and the still-too-wide pages wobbled in the viewport when shrinking – enlarging looked smooth only because the lagging images stayed narrower than the column. K14 (0.65.8, deploy feedback): _pdf_scale_one is now index-based and records each page's scaled width in the new list _pdf_scaled (0 = not yet scaled / mismatching width; panel init/clear reset it, _render_pdf and the R2 feed append entries); _apply_pdf_scale arms _pdf_scale_step without a start index. Dragging usually skips the pass entirely via the 8-px threshold, but a width JUMP (reset button) re-scales everything – the visible-first handling in _pdf_scale_step makes the column fit right after the jump. K15 (0.65.9, deploy feedback, reset round 2): the armed background pass visibly never scaled the follow-up pages (page 1 fitted, scrolling repaired the rest via the scroll hook), so correctness no longer depends on it: a jump of 40 px or more (reset button, window resize) scales the first 6 pages plus the visible range SYNCHRONOUSLY inside _apply_pdf_scale; small drag crossings keep the light K12 behavior (page 1 only). _render_pdf forces the opening pass (_pdf_last_w = 0) so a re-render at an unchanged width – an office conversion arriving after a resize – still fits page 1 instead of leaving it at double width behind the 8-px threshold. dbg breadcrumbs log every pass (old/new width, page count; the idle pass logs its scaled counts, lo/hi and stale reasons with generation numbers). K16 (0.65.10, deploy feedback with screenshot + breadcrumb log): the passes scaled every page correctly, yet the view kept showing the old wide page until a scroll – scaling inside the size-allocate handler leaves GTK's queue_resize from set_from_pixbuf deferred, so the shrunk pages never repaint without an expose. _pdf_scale_one now queues a draw right after setting the pixbuf, and after the synchronous block _apply_pdf_scale arms the one-shot idler _pdf_relayout (queue_resize + queue_draw on the page box) which runs after the resize pass – the view snaps into place immediately; that is also why dragging never showed the effect (the next size-allocate in a drag flushes the stale paint anyway). K17 (0.65.11, deploy feedback, fourth round): the queued draws never get flushed on their own – GTK processes pending updates only when an X event pushes the main loop through the paint path. _pdf_relayout therefore performs the scroll's own operation from code: invalidate_rect(None, True) on the scrolled window's GdkWindow (full recursive invalidation) followed by process_updates(True) (synchronous update pass in the same cycle); it also logs the layout state (box allocation, hadjustment upper span, first page allocation) so one dbg line per reset proves the widget tree already holds the correct sizes. K18 (0.65.12, deploy feedback with layout-state dbg): that dbg line exposed the real root – after the reset jump the tree kept the OLD sizes (box 634 px while every page was scaled to 317 px): queue_resize is absorbed in this embedding (panel inside a paned, scrolled window, viewport), the follow-up allocation pass never runs, and only panel-driven resizes or SCROLLS re-allocate the subtree (the viewport re-allocates its child on every scroll – scrolling "fixed" the view all along, it was never about the paint). _pdf_relayout therefore replicates the scroll's mechanism directly: it sets the child viewport's alloc-needed flag (defeats GTK3's unchanged-allocation fast path) and re-allocates the viewport with its current allocation – the viewport handler re-allocates the page box from its current requests, the box re-allocates the pages, and the adjustments update; the dbg line now logs before -> after values, one line per resize proving the fix. This also removes the one-behind allocation lag during column drags.
```

### DOC-DOC-12 – Docstring: \_render\_office

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._render\_office` (method)
- **Reason:** Sharp route via cached LibreOffice PDF with background fallback.

```text
Office documents (ODT/ODS/ODP, DOCX/XLSX/PPTX; F39: also DOC/XLS/PPT and RTF) – sharp route: if a fresh LibreOffice conversion PDF is in the cache, its pages are rendered sharp and at full panel width via Poppler (identical to the PDF preview, scrollable). Otherwise the embedded thumbnail appears first with a hint, and the conversion starts in the background – the sharp result shows up automatically as soon as it is ready. Without LibreOffice/Poppler it stays with the thumbnail.
```

### DOC-DOC-13 – Docstring: \_render\_office\_thumb

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._render\_office\_thumb` (method)
- **Reason:** Transitional view: embedded thumbnail, text fallback, hint.

```text
Transitional view for office documents: the thumbnail embedded by the document itself (Thumbnails/thumbnail.png or docProps/thumbnail.*). Only if NO thumbnail is present, a text excerpt is shown instead. With converting=True the LibreOffice conversion runs in parallel – then with a hint. Since 0.40.0 two helpers read the package data and the no-ZIP hint.
```

### DOC-DOC-14 – Docstring: \_office\_nozip\_hint

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_nozip\_hint` (method)
- **Reason:** F39 – hint line for office formats without a ZIP part.

```text
F39: hint line for office formats WITHOUT a ZIP part (binary and RTF) – there are no embedded thumbnails there, only the LibreOffice conversion helps (→ REF DOC-LEGACY-1).
```

### DOC-DOC-15 – Docstring: \_office\_package\_data

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_package\_data` (method)
- **Reason:** Reads thumbnail and text excerpt from the Office ZIP with caps.

```text
Read the embedded thumbnail and the text excerpt from the Office ZIP package (0.9.2: read caps against thumbnail bombs) – throws on an unreadable package; returns (thumb|None, text).
```

### DOC-DOC-16 – Docstring: \_office\_cached\_pdf

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_cached\_pdf` (method)
- **Reason:** Fresh cache hit only if not older than the source file.

```text
Freshly converted PDF from the cache, or None.
```

### DOC-DOC-17 – Docstring: \_office\_fail

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_fail` (method)
- **Reason:** B4 – failed conversion memory, capped at 256 paths.

```text
Remember a failed conversion (B4: capped at 256 paths, the set then resets – retry loop protection).
```

### DOC-DOC-18 – Docstring: \_office\_start\_job

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_start\_job` (method)
- **Reason:** One background LibreOffice conversion at a time, safe fallback.

```text
Start the LibreOffice conversion in the background. 0.65.7 (deploy feedback, Mint 22.3 VM): the child's stdout/stderr go to DEVNULL (SpawnFlags STDOUT_TO_DEV_NULL | STDERR_TO_DEV_NULL) – the benign javaldx warning and load errors no longer leak into Nemo's terminal; a dbg hint in the failure path of _office_job_done points at the LibreOffice component packages (libreoffice-core alone ships no document filters, headless conversion then fails with "Error: source file could not be loaded").
```

### DOC-DOC-19 – Docstring: \_office\_job\_done

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._office\_job\_done` (method)
- **Reason:** Cache the result, refresh the preview, chain the next job.

```text
Conversion finished: cache the result, refresh the preview.
```

### DOC-DOC-20 – Docstring: \_pdf\_scale\_step

- **Module:** previewer\_render\_docs.py
- **Location:** `DocsRendererMixin._pdf\_scale\_step` (method)
- **Reason:** K12 – incremental resize pass: 4 pages per idle cycle.

```text
K12 (0.60.1): the idler behind _apply_pdf_scale – scales the pages in _pdf_src/_pdf_imgs in packets of 4 per idle cycle to the passed target width, so a column drag never starves the main loop. Stale passes end silently: a newer resize bumps _pdf_scale_gen, a torn-down preview nulls _pdf_box (both checked first). Pages arriving from the R2 feed chain meanwhile are already scaled by _pdf_idle_step and get re-scaled at most once – harmless. K14 (0.65.8, deploy feedback): visible-first – each cycle first scales ALL pages inside the viewport (_pdf_visible_range reads the vertical adjustment of _pdf_scroll and checks the page allocations against top/bottom, so the column fits immediately after a width jump like the reset button), then at most 4 off-screen pages; re-arm only while _pdf_scaled still holds a mismatching width. The scroll hook _on_pdf_scrolled scales newly visible pages on the spot, so the background pass is never felt. K15 (0.65.9, deploy feedback, reset round 2): the pass showed no visible effect after the reset jump, so it now only tops up what _apply_pdf_scale already scaled synchronously (first 6 pages + visible on jumps >= 40 px) – and every cycle leaves dbg breadcrumbs: stale exits log the generation numbers and whether _pdf_box is gone, normal cycles log the scaled page count and the visible range (lo/hi). If a future log shows the pass going stale right after the reset, those numbers identify the invisible gen bumper. K16 (0.65.10): the scroll hook logs a line only when it actually scales (`docs/_on_pdf_scrolled: N page(s) -> W px`) – in a healthy run after a reset neither that line nor any pass line should appear, which separates a pure repaint problem from a scaling problem in one glance. K17 (0.65.11): the hook now logs EVERY scroll event (position, computed page, scaled count, target width) – after a healthy reset it reports `scaled 0` because the view is correct before any scrolling.
```

---

## Text (TXT)

### TXT-HR-1 – “+”-concatenation in \_md\_hr

- **Module:** previewer\_render\_text.py
- **Location:** `_md_hr`, above the return
- **Reason:** Implicit string concatenation with \* is a precedence trap; YAML front matter otherwise stayed without a preview.

```text
    # Important: "+" instead of implicit string concatenation – "a" "b" * 12 would otherwise give ("ab") * 12 (precedence trap): 12 unclosed <span> tags made the markup completely invalid, and every file with a ---- line (YAML front matter!) stayed without a preview.
```

### TXT-EPUB-1 – container.xml under the R4 cap

- **Module:** previewer\_render\_text.py
- **Location:** `_epub_data`, above `opf_path`
- **Reason:** Even small OPF entries over the read cap – a doctored EPUB could pack them as a decompression bomb (0.9.2).

```text
        # OPF content file: sits in META-INF/container.xml. 0.9.2: these small entries also over the R4 read cap – a doctored EPUB could pack them as a decompression bomb (chapters and cover were long capped, these two reads were not).
```

### TXT-MOBI-1 – MOBI edge cleanup (R7, dropped with F59)

- **Module:** previewer\_render\_text.py
- **Location:** formerly `_mobi_text` above `_mobi_edge` (removed with F59)
- **Reason:** MOBI records carry dirt bytes at the edge; a complete trailer decode would be risky without reference material. With F59 (0.44.0) the e-book text preview is abolished – \_mobi\_text, \_mobi\_edge and the PalmDoc decompression are removed; MOBI now shows only book title, author (EXTH) and e-book format, and without text extraction HUFF/CDIC no longer blocks. The historical R7 comment:

```text
    # R7: MOBI records can carry dirt bytes at the edge – half torn multi-byte sequences and remains of trailing entries (index/control data at the record end) which the decompressor interprets as character salad. A complete backwards decode of the trailer size would be risky without reference material (one error would damage ALL books); the safe per-record edge cleanup removes the visible bulk of the garbage.
```

### TXT-CSV-1 – CSV as a real table (F8)

- **Module:** previewer\_render\_text.py (\_render\_csv, \_pack\_table), previewer\_panel.py (dispatch)
- **Location:** `\_csv\_data` sniffs delimiter and header row by itself
- **Reason:** User request: CSV as a Gtk.TreeView instead of text mush – and the module determines the column/cell delimiter itself (user requirement, never guessed from the file name): `csv.Sniffer` tries comma, semicolon, TAB and pipe against the first 64 KB and also decides on the header row; built-in csv, 4 MB read cap, 1000-row preview with hint. `\_pack\_table` builds the TreeView (resizable, click-sortable, horizontally scrollable) – F56 (spreadsheets) can reuse the same renderer later.

```text
        sniffer = csv.Sniffer()
        delim = sniffer.sniff(sample, delimiters=",;\t|").delimiter
        ...
        col.set_sort_column_id(i)
```

### TXT-SQL-1 – SQLite table overview (F6)

- **Module:** previewer\_render\_text.py (\_render\_sqlite), previewer\_panel.py (dispatch)
- **Location:** `\_sqlite\_data` – magic check, schema, read-only
- **Reason:** User request: table list + row count (.db/.sqlite). The structure comes from the schema itself: the 16-byte magic check (“SQLite format 3”) sends foreign files into the open hint, `PRAGMA query_only` opens guaranteed read-only, `sqlite_master` delivers the tables, `PRAGMA table_info` the column names, `SELECT COUNT(*)` the rows. A progress cap (2 million opcodes) stops endless full scans over giant tables (F60 lesson: the preview must be there immediately) – such counters show “…”.

```text
        con.execute("PRAGMA query_only = 1")
        con.set_progress_handler(lambda: 1, _SQLITE_COUNT_STEPS)
        ...
        cols = ", ".join(r[1] for r in con.execute(
            'PRAGMA table_info(%s)' % q))
```

### TXT-PKG-1 – Package split 40/60 with a scrollable info area (F60)

- **Module:** previewer\_render\_text.py (split + renderer), previewer\_panel.py (dispatch), previewer\_util.py (wrap)
- **Location:** `\_pack\_package\_capped` with `\_package\_split\_sync`, used by `\_render\_package` (DEB, RPM, Arch)
- **Reason:** User request (2026-11-02): package info is more extensive than image info – hence the REVERSED split compared to MED-SPLIT-1: 40 % icon on top, 60 % info table below, and that one sits in a ScrolledWindow (v-scroll automatic, overlay scrolling off), because description and dependencies like to outgrow the area. The icon area carries 40 % of the column height as its request, a size-allocate follow-up keeps it current on window resizes (pattern \_image\_split\_sync). The icon comes best effort from the payload (\_WindowReader with an 8 MB decompression budget against giant packages – lowered from 48 MB in 0.45.1 so the info table stands immediately; the score prefers 48x48/apps), else \_package\_placeholder draws the box with the format signet (DEB/RPM/PKG). 0.45.1: the member compression is recognized by \_tar\_sniff\_mode from the magic bytes instead of the ar name – IEEE slashes and zst names escaped the old switch. pack\_meta\_grid packs the values with wrap=True multi-line instead of ellipsized – only set fields show a row.

```text
        top.set_size_request(-1,
                             max(80, int(self._preview_height() * 0.4)))
        top.connect("size-allocate", self._package_split_sync)
        ...
        info_scroll.set_policy(Gtk.PolicyType.NEVER,
                               Gtk.PolicyType.AUTOMATIC)
        info_scroll.set_overlay_scrolling(False)
        info_scroll.add(bottom)
```

### TXT-FONT-1 – Font copy register (R5)

- **Module:** previewer\_render\_text.py
- **Location:** `_fc_add_font_file`, above `state["copies"].append(dest)`
- **Reason:** Fontconfig has the fonts in memory – the register only keeps the temp folder small.

```text
            # R5: register the copy and remove the oldest when the cap is reached. Fontconfig has already loaded the fonts into memory at FcConfigAppFontAddDir – waterfalls already seen therefore stay correctly rendered, only the disk/the temp folder gets relief.
```

### TXT-FONT-2 – Waterfall: theme color and sample text (F12)

- **Module:** previewer\_render\_text.py (color + sample text), previewer\_panel.py (configuration), previewer\_toolbar.py (settings field)
- **Location:** `_render_font` (text color and waterfall label); defaults in `\_\_init\_\_`, load/save in \_config\_load/\_config\_save (key font\_sample\_text); settings window, section “Fonts”
- **Reason:** User finding (2026-10-31): the waterfall text of the font preview was black – also in dark mode, where black text on dark grey is barely readable. Cause: StyleContext.get\_color() in GTK3 demands the state argument; the old call without the argument ALWAYS threw a TypeError that the surrounding except block swallowed, so the fallback (0.13, 0.13, 0.13 = almost black) stayed in every theme. Now the call get\_color(Gtk.StateFlags.NORMAL) reads the same theme color as the folder icons; the fallback stays as the last resort. Additional user request: the sample text is no longer hard-wired in the source (\_FONT\_SAMPLE\_TEXT stays only as the default) – the new section “Fonts” in the settings window offers an entry (key font\_sample\_text), saves immediately and rebuilds a currently displayed font live (\_on\_font\_sample\_changed, extension check .ttf/.otf/.ttc/.woff); empty text stays unsaved.

```text
        fg = (0.13, 0.13, 0.13)
        try:
            c = self.get_style_context().get_color(
                Gtk.StateFlags.NORMAL)
            fg = (c.red, c.green, c.blue)
        except Exception:
            pass
```

### TXT-FONT-3 – WOFF1 and TTC with all faces (F11)

- **Module:** previewer\_render\_text.py
- **Location:** `\_woff1\_to\_sfnt`, `\_sfnt\_face\_names`, `\_font\_faces`, `\_render\_font`; dispatch in previewer\_panel.py, sample-text check in previewer\_toolbar.py
- **Reason:** User request (2026-11-05) "Ergänze das Rendern von Schriftarten um WOFF1-Fonts und TTC" – F11 from the plan.

```text
WOFF1 (.woff): Fontconfig cannot read WOFF – _woff1_to_sfnt unpacks the zlib-compressed tables (compLength < origLength) and rebuilds a plain sfnt (flavor as version, tables sorted by tag, data padded to 4 bytes, original checksums kept); _font_faces parks the sfnt as stem-hash.ttf in the font temp dir (R5 cap) and returns it as the registration path. WOFF2 (wOF2, Brotli) raises "WOFF2 is not supported" – it shows the open hint instead of a preview. TTC (ttcf): every face offset in the header is parsed (name table per face via _sfnt_face_names; one broken face is skipped), and _render_font gives EVERY face its own bold header (family – style) and its own waterfall – capped at \_TTC\_FACE\_CAP (8) with a dim remainder hint; the info table shows Format + font count instead of Family/Style. Every waterfall carries its own live-resize item (F68). The panel dispatch now routes .woff (and font/woff) to the font renderer.
```

### TXT-B6-1 – System font size for Markdown (B6)

- **Module:** previewer\_render\_text.py
- **Location:** `_render_markdown`, above the `_text_view` call
- **Reason:** Without a font override the TextView uses the system font; markup only after validation, else raw text.

```text
        # B6 (0.10.1): WITHOUT font override – the TextView uses the GTK theme's system font and with it the system's font size. The previously hard-coded "9" (default font in 9 pt) was visibly smaller on the system than the text preview (monospace) that the user knows as the yardstick. Headings scale along: their size='large'/'x-large' specs are relative to the base font. Take over markup only if it was validated – else raw text.
```

### TXT-VCARD-1 – Contact card renderer (F7)

- **Module:** previewer\_render\_text.py
- **Location:** `_render_vcard`, \_vcard\_card\_widget and \_vcard\_card\_draw with the parse helpers (\_vcard\_unfold up to \_vcard\_placeholder, \_vcard\_circle, \_ldif\_parse, \_contact\_parse)
- **Reason:** User request: render ALL known contact card formats as a card – contact photo circular, else a circular placeholder. Three parsers deliver the same card tuple structure: vCard (RFC 6350 folding, 2.1 quoted-printable, bare parameters, group prefixes), LDIF (RFC 2849, base64 values, jpegPhoto stays raw base64 for the photo decode) and Windows-Contact (.contact XML, namespace-agnostic over local element names). 0.26.0 (user note): NO card cap – all contacts of the file appear below each other scrollable, with a single contact no scrollbar shows. Finishing 0.25.0: every card carries a rectangular frame with the corner radius of the music covers plus the same drop shadow (F34/F35) – drawn in the draw signal BEHIND the widgets (rounding path via \_cover\_round\_path from the media module). Subtlety 0.25.1: NO fill – the card stays transparent (a white base hurts in dark mode), shadow and hairline frame stay; corner radius a third more subtle (56/960 instead of 56/640 of the smaller edge). Photos only inline base64 or a local URI – network URIs stay unqueried, the placeholder applies. Without pycairo the photo stays square and the placeholder a theme icon; the card frame runs without it, the draw callback gets its Cairo context from GTK.

```text
        # Read cap: contact photos sit as base64 IN the file – a few MB are common, a few dozen would be a bomb for Nemo.
```

```text
        # Frame and shadow need NO pycairo – the draw callback gets its Cairo context delivered by GTK.
```

### TXT-ICS-1 – ICS calendar events (F52)

- **Module:** previewer\_render\_text.py (\_render\_ics), previewer\_panel.py (dispatch)
- **Location:** `\_ics\_data` parses the VEVENT blocks; `\_render\_ics` stacks the event cards
- **Reason:** User request: calendar files (.ics) as an event list (decoupled from F7). Every VEVENT becomes its own card after the EML header pattern: bold summary, then Start/End/Location/Description rows via pack\_meta\_grid with wrapping values (descriptions get long). The parser unfolds RFC 5545 continuation lines, keeps the first occurrence of a property and understands DATE and DATE-TIME values (VALUE=DATE and the UTC "Z" suffix show the date, timed values show date and time). Times appear exactly as stored – no timezone conversion, the preview never invents what the file does not say. Multiple events sit scrollable below each other, 50 events max with a "… and N more" hint (cap like the contact cards); the read cap is 8 MB like vCard. Dispatch: .ics extension or text/calendar.

```text
        elif lower.endswith(".ics") or mime == "text/calendar":
            self._render_ics(path)
```

### TXT-EML-ATT-1 – EML attachments list and extraction (F54)

- **Module:** previewer\_render\_text.py (\_render\_eml, \_pack\_eml\_attachments, \_on\_eml\_extract)
- **Location:** `\_eml\_attachment\_rows` collects the parts, `\_unique\_target` avoids name conflicts
- **Reason:** User request: the EML preview lists attachments (name, size) and extracts them on a button. 0.64.0 (user request): a checkbox column before the name – only checked attachments extract; the list keeps five rows visible, the rest scrolls.

```text
        btn = Gtk.Button(label="Extract selected attachments")
        btn.connect("clicked", self._on_eml_extract, path, checks)
```

### TXT-DOC-1 – Docstring: \_pango\_escape

- **Module:** previewer\_render\_text.py
- **Location:** `\_pango\_escape` (module level)
- **Reason:** Central markup escaper for all text renderers.

```text
Escape text for Pango markup (& < >).
```

### TXT-DOC-2 – Docstring: \_md\_inline

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_inline` (module level)
- **Reason:** Inline Markdown formatting to Pango markup.

```text
Inline formatting: ***bold+italic***, **bold**, __bold__, *italic*, _italic_, ~~strikethrough~~ (GFM), `code`, [link](url) – also with parentheses in the URL –, <https://autolink>, ![image](url).
```

### TXT-DOC-3 – Docstring: \_md\_heading

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_heading` (module level)
- **Reason:** Headings with browser-like look, no extra widgets.

```text
Heading (ATX or Setext): size by depth, H1/H2 with an underline – approximates the colored bar of the browser rendering, without extra widgets.
```

### TXT-DOC-4 – Docstring: \_md\_w

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_w` (module level)
- **Reason:** Display-width estimate for GFM table layout.

```text
Estimate the display width of a string: emoji and symbols occupy two columns in the TextView (🔴 ✅ ☑ …), the variation selector FE0F none at all, everything else exactly one. Without this estimate, emoji cells were off by the emoji width.
```

### TXT-DOC-5 – Docstring: \_md\_split\_cells

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_split\_cells` (module level)
- **Reason:** S9 helper – splits a Markdown table row into cells.

```text
S9 (0.42.0): Split a Markdown line into cells – strip leading and trailing bars; a bar escaped with a backslash is NOT a separator (GFM).
```

### TXT-DOC-6 – Docstring: \_md\_wrap\_cell

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_wrap\_cell` (module level)
- **Reason:** S9 helper – wraps one cell to the column width.

```text
S9 (0.42.0): Break a cell into display segments of width w (word wrap, hard break for overlong words); fitting cells stay unchanged.
```

### TXT-DOC-7 – Docstring: \_md\_fmt\_row

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_fmt\_row` (module level)
- **Reason:** S9 helper – renders one table row as flush lines.

```text
S9 (0.42.0): Render a table row as flush <tt> lines – wrapped, padded and escaped per column, bold for the header row.
```

### TXT-DOC-8 – Docstring: \_md\_widths

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_widths` (module level)
- **Reason:** S9 helper – column width budget with safety net.

```text
S9 (0.42.0): Column widths within a total budget – narrow columns keep their full width, the rest is distributed proportionally among the wide ones; a safety net shrinks the widest column until the budget holds (0.14.0 field test: the order table in planned.md was meters wide and fell apart in the TextView).
```

### TXT-DOC-9 – Docstring: \_md\_table

- **Module:** previewer\_render\_text.py
- **Location:** `\_md\_table` (module level)
- **Reason:** GFM table reader – the S9 flow keeper.

```text
Read a GFM table starting at line i: header line, separator line with :--/--:/:-:, any number of rows. Returns (markup lines, next index) or None if no table stands there. As in the browser a total budget applies: narrow columns keep their full width, overlong cells wrap multi-line WITHIN their column – the columns stay flush instead of the longest cell bloating all lines (0.14.0 field test: the order table in planned.md was meters wide and fell apart in the TextView). Header line bold, grey separator line, right-aligned at '---:'. Widths are measured on the RAW cell and padded BEFORE escaping, so &amp; does not spoil the alignment. Markup that runs across a cell wrap is deliberately NOT rejoined – valid markup matters more than looks; the raw text fallback in _render_markdown must never trigger because of a table. S9 (0.42.0): Decomposed – _md_split_cells, _md_widths and _md_fmt_row (with _md_wrap_cell, _md_plain) are module helpers; the flow remains here.
```

### TXT-DOC-10 – Docstring: \_markdown\_to\_pango

- **Module:** previewer\_render\_text.py
- **Location:** `\_markdown\_to\_pango` (module level)
- **Reason:** Markdown preview without a webview (deliberate partial parser).

```text
Translate Markdown to Pango markup – deliberately not a full parser, but with the widespread variants (GitHub Flavored Markdown): ATX (#) and Setext headings (===/---) with an underline at H1/H2, bold/italic/bold+italic, ~~strike~~, inline and block code, unordered lists with level markers (•/◦/▪), ordered (1./1)), task lists ([x] → ☑ with strikethrough as in the browser, [ ] → ☐), indented lists, multiply nested quotes, horizontal rules (spaces allowed: - - -), links (parentheses in the URL included), autolinks and GFM tables. Headings, rules and tables get air above – that reads like in the browser. No webview, no new package dependencies; deliberately left out: 4-space code blocks (collides with list indentation).
```

### TXT-DOC-11 – Docstring: \_html\_to\_text

- **Module:** previewer\_render\_text.py
- **Location:** `\_html\_to\_text` (module level)
- **Reason:** HTML part of an EML into readable text.

```text
Roughly clean HTML into readable text (for EML text bodies).
```

### TXT-DOC-12 – Docstring: \_xml\_local

- **Module:** previewer\_render\_text.py
- **Location:** `\_xml\_local` (module level)
- **Reason:** Namespace-free tag matching for OPF/FB2/contact XML.

```text
XML tag without namespace (OPF and FB2 do not skip them).
```

### TXT-DOC-13 – Docstring: \_meta\_rows

- **Module:** previewer\_render\_text.py
- **Location:** `\_meta\_rows` (module level)
- **Reason:** Shared metadata rows for e-books and packages (S3/F59/F60).

```text
S3 (0.42.0): Metadata rows of the e-book formats – empty values drop out. F59 (0.44.0): book title, author, series, pages, e-book format, language – only set tags show a row. F60 (0.45.0): Renamed – the package formats (DEB, RPM, Pacman) use the helper too.
```

### TXT-DOC-14 – Docstring: \_series\_text

- **Module:** previewer\_render\_text.py
- **Location:** `\_series\_text` (module level)
- **Reason:** F59 – series row from name and volume number.

```text
F59 (0.44.0): Series text from name and volume number – "Name – Volume 2.5"; without a number just the name, without a name nothing at all (the row then drops via _meta_rows).
```

### TXT-DOC-15 – Docstring: \_ebook\_placeholder

- **Module:** previewer\_render\_text.py
- **Location:** `\_ebook\_placeholder` (module level)
- **Reason:** F59 – drawn cover for e-books without one.

```text
F59 (0.44.0): Drawn portrait cover for e-books without an embedded cover – book cover skeleton in grey tones (spine stripe, title bar, text line hints), theme-neutral like the vCard placeholder. Without Cairo it returns None; the caller then shows the open hint.
```

### TXT-DOC-16 – Docstring: \_epub\_opf\_path

- **Module:** previewer\_render\_text.py
- **Location:** `\_epub\_opf\_path` (module level)
- **Reason:** S3 helper – OPF path from container.xml with fallback.

```text
S3 (0.42.0): OPF path of an EPUB – first from META-INF/container.xml, else fallback to the first .opf name (→ REF TXT-EPUB-1).
```

### TXT-DOC-17 – Docstring: \_epub\_metadata

- **Module:** previewer\_render\_text.py
- **Location:** `\_epub\_metadata` (module level)
- **Reason:** S3/F59 – OPF evaluation, manifest and cover id.

```text
S3 (0.42.0): Evaluate the OPF – title/author/language, manifest (id → href, media type, properties) and cover id (cover-image properties, else meta name=cover). F59 (0.44.0): series and pages added – calibre:series (plus index) or EPUB3 belongs-to-collection (plus group-position); pages only if the OPF carries a page-count meta (no standard tag – no tag, no row). The spine is gone with the text preview (F59).
```

### TXT-DOC-18 – Docstring: \_epub\_cover

- **Module:** previewer\_render\_text.py
- **Location:** `\_epub\_cover` (module level)
- **Reason:** S3 helper – cover bytes per manifest or heuristic.

```text
S3 (0.42.0): Cover bytes – per the manifest, else heuristic: the file name contains "cover" and looks like an image.
```

### TXT-DOC-19 – Docstring: \_epub\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_epub\_data` (module level)
- **Reason:** EPUB loader (rows, cover) – S3 decomposition flow.

```text
Open an EPUB: metadata (F59: book title, author, series, pages, language) and cover bytes. Returns (rows, cover) – the text preview was dropped with F59. S3 (0.42.0): Decomposed – _epub_opf_path, _epub_metadata and _epub_cover each parse one part; the flow remains here.
```

### TXT-DOC-20 – Docstring: \_fb2\_metadata

- **Module:** previewer\_render\_text.py
- **Location:** `\_fb2\_metadata` (module level)
- **Reason:** S3/F59 – FB2 head fields.

```text
S3 (0.42.0): FB2 head – title, author (first-/last-name) and cover reference (coverpage l:href). F59 (0.44.0): language (<lang>) and series (<sequence name number>) added; the body is gone with the text preview (F59).
```

### TXT-DOC-21 – Docstring: \_fb2\_cover

- **Module:** previewer\_render\_text.py
- **Location:** `\_fb2\_cover` (module level)
- **Reason:** S3 helper – FB2 cover from the binary resource.

```text
S3 (0.42.0): Cover from the embedded <binary> resource (base64).
```

### TXT-DOC-22 – Docstring: \_fb2\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_fb2\_data` (module level)
- **Reason:** FictionBook loader with the R11 read cap.

```text
FictionBook 2 (.fb2): book title, author, series, language and cover (base64 binary). Returns (rows, cover) – the text preview was dropped with F59. S3 (0.42.0): Decomposed – _fb2_metadata and _fb2_cover each one part; the flow remains here. R11: Read cap like EML/vCard (the cover sits as base64 in the file, a few MB are normal) – huge FB2s get truncated and are then not parsed at all: the ParseError runs into the caller's open hint instead of memory pressure at the panel.
```

### TXT-DOC-23 – Docstring: \_mobi\_records

- **Module:** previewer\_render\_text.py
- **Location:** `\_mobi\_records` (module level)
- **Reason:** S3 helper – Palm record offsets; the four-byte contract is pinned by the selftest fixture (PAN-SELFTEST-1).

```text
S3 (0.42.0): Palm records from offset 78 – 8 bytes per entry. 0.61.0 (F1 selftest finding): the offset is FOUR big-endian bytes per the PDB record entry (attributes and unique id follow); the previous three-byte read delivered offset>>8 – on real MOBIs record 0 started at the wrong position, so the MOBI header and with it the EXTH author were never parsed (unnoticed because the title comes from the PalmDB name field). Fixed together with F1; the selftest fixture pins the contract.
```

### TXT-DOC-24 – Docstring: \_mobi\_header

- **Module:** previewer\_render\_text.py
- **Location:** `\_mobi\_header` (module level)
- **Reason:** S3 helper – MOBI header record and EXTH author.

```text
S3 (0.42.0): MOBI header record – compression method, encoding, first non-book record and the EXTH author (entry type 100).
```

### TXT-DOC-25 – Docstring: \_mobi\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_mobi\_data` (module level)
- **Reason:** MOBI loader – title/author without HUFF/CDIC blocking (F59).

```text
MOBI/PRC (Palm container): book title and author (EXTH). Returns (rows, None) – F59: e-books show cover and info table instead of text; MOBI covers sit as a REC entry (addressed differently), so the preview shows the drawn placeholder. Without text extraction HUFF/CDIC no longer blocks – title and author now show for AZW files too. S3 (0.42.0): Decomposed – _mobi_records and _mobi_header each one part; the flow remains here.
```

### TXT-DOC-26 – Docstring: \_WindowReader (class)

- **Module:** previewer\_render\_text.py
- **Location:** `\_WindowReader` (class)
- **Reason:** Class marker – F60 budgeted read window for tar streams.

```text
F60 (0.45.0): read() window over a file with a budget – tarfile in stream mode (r|gz, r|xz) only needs read(), and the budget stops the icon hunt in huge packages with an EOFError (cap pattern like R11/B5 instead of memory pressure).
```

### TXT-DOC-27 – Docstring: \_tar\_sniff\_mode

- **Module:** previewer\_render\_text.py
- **Location:** `\_tar\_sniff\_mode` (module level)
- **Reason:** F60.1 – compression from magic bytes, not member names.

```text
F60.1 (0.45.1): tarfile mode from the MAGIC BYTES of the member – gz and xz are on-board tools, zst is not (None → caller shows a hint or leaves the icon out). Guessing from the ar member name became the invalid-header finding: depending on the tool the names carry IEEE slashes ('control.tar.gz/').
```

### TXT-DOC-28 – Docstring: \_pkg\_icon\_score

- **Module:** previewer\_render\_text.py
- **Location:** `\_pkg\_icon\_score` (module level)
- **Reason:** F60 – icon candidate ranking.

```text
F60: Icon candidate? PNG/JPG under icons/ or pixmaps/, small enough; 48x48 and apps score best (best score -3).
```

### TXT-DOC-29 – Docstring: \_deb\_control\_fields

- **Module:** previewer\_render\_text.py
- **Location:** `\_deb\_control\_fields` (module level)
- **Reason:** F60 – deb control parsing with continuation lines.

```text
F60 (0.45.0): deb control file – 'Field: value', continuation lines (leading spaces) attach to the value; ' .' is the paragraph break in the long description. First field wins.
```

### TXT-DOC-30 – Docstring: \_kb\_size

- **Module:** previewer\_render\_text.py
- **Location:** `\_kb\_size` (module level)
- **Reason:** F60 – Installed-Size formatting.

```text
F60: deb Installed-Size is in KB – format it readably.
```

### TXT-DOC-31 – Docstring: \_deb\_rows

- **Module:** previewer\_render\_text.py
- **Location:** `\_deb\_rows` (module level)
- **Reason:** F60 – deb info rows via \_meta\_rows.

```text
F60 (0.45.0): Info rows from the control file – only set fields; the description splits into short and long.
```

### TXT-DOC-32 – Docstring: \_deb\_icon

- **Module:** previewer\_render\_text.py
- **Location:** `\_deb\_icon` (module level)
- **Reason:** F60/F60.1 – app icon from data.tar with probe read.

```text
F60: App icon from data.tar – best effort with a budget. 0.45.1: compression from magic bytes (6-byte probe read, see _tar_sniff_mode), not from the member name.
```

### TXT-DOC-33 – Docstring: \_deb\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_deb\_data` (module level)
- **Reason:** F60 – Debian package loader (ar archive).

```text
F60 (0.45.0): Debian package (.deb) – ar archive: control.tar.<gz|xz> carries the control file (on-board tools), data.tar.<gz|xz> the payload, from which the first app icon is fished best effort (budget, else a drawn placeholder). Returns (rows, icon).
```

### TXT-DOC-34 – Docstring: \_rpm\_section

- **Module:** previewer\_render\_text.py
- **Location:** `\_rpm\_section` (module level)
- **Reason:** F60 – RPM header section parsing.

```text
F60 (0.45.0): RPM header section from pos – magic 8E AD E8, 16-byte header (index count + store size), 16-byte index entries each (tag, type, offset, count) and the data store. Returns (index, store, end).
```

### TXT-DOC-35 – Docstring: \_rpm\_value

- **Module:** previewer\_render\_text.py
- **Location:** `\_rpm\_value` (module level)
- **Reason:** F60 – RPM tag value decoding by type.

```text
F60: First value of an RPM tag – STRING (7) and I18NSTRING (9) as str, STRING_ARRAY (6) as list, INT32 (4) as int; else None.
```

### TXT-DOC-36 – Docstring: \_rpm\_rows

- **Module:** previewer\_render\_text.py
- **Location:** `\_rpm\_rows` (module level)
- **Reason:** F60 – RPM info rows via \_meta\_rows.

```text
F60: Info rows from the RPM header – only set tags.
```

### TXT-DOC-37 – Docstring: \_rpm\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_rpm\_data` (module level)
- **Reason:** F60 – RPM loader, cpio payload deliberately out.

```text
F60 (0.45.0): RPM – lead (96 B), signature header and main header sit at the file start (on-board tools: struct); the cpio payload stays out (usually zstd) – the preview shows the drawn placeholder. Returns (rows, None).
```

### TXT-DOC-38 – Docstring: \_pkginfo\_fields

- **Module:** previewer\_render\_text.py
- **Location:** `\_pkginfo\_fields` (module level)
- **Reason:** F60 – .PKGINFO single/multi field split.

```text
F60 (0.45.0): .PKGINFO ('key = value' per line) – collect multi lines (depend, optdepend, makedepend, license, group); for single fields the first value wins. Returns (single, multi).
```

### TXT-DOC-39 – Docstring: \_pkg\_rows

- **Module:** previewer\_render\_text.py
- **Location:** `\_pkg\_rows` (module level)
- **Reason:** F60 – Pacman info rows via \_meta\_rows.

```text
F60: Info rows from .PKGINFO – only set fields.
```

### TXT-DOC-40 – Docstring: \_pkg\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_pkg\_data` (module level)
- **Reason:** F60 – Arch/Pacman loader, one stream pass for icon and meta.

```text
F60 (0.45.0): Arch/Pacman package (.pkg.tar.xz, AUR builds among others) – .PKGINFO gives the metadata, the app icon is fished in the same stream pass (budget, else placeholder). .pkg.tar.zst would need zstd – not an on-board tool, then the open hint. Returns (rows, icon).
```

### TXT-DOC-41 – Docstring: \_package\_placeholder

- **Module:** previewer\_render\_text.py
- **Location:** `\_package\_placeholder` (module level)
- **Reason:** F60 – drawn package icon (box with format signet).

```text
F60 (0.45.0): Drawn package icon (box with lid and format signet) for packages without a readable app icon – e.g. RPM (cpio payload) or tar.zst. Without Cairo: None, the caller then shows the open hint.
```

### TXT-DOC-42 – Docstring: \_font\_faces

- **Module:** previewer\_render\_text.py
- **Location:** `\_font\_faces` (module level)
- **Reason:** F11 – every readable face of a font file; WOFF1 becomes an sfnt.

```text
Reads the whole font file and returns (registration path, format text, faces): WOFF1 is rebuilt to a plain sfnt via _woff1_to_sfnt and parked in the font temp dir (Fontconfig cannot read WOFF) – the temp path is the registration path; wOF2 raises "WOFF2 is not supported". ttcf collections list EVERY face: the name table is parsed per face offset via _sfnt_face_names, one broken face is skipped instead of killing the whole preview. Single TrueType/OpenType files return exactly one face. Format texts: TrueType, OpenType (CFF), the WOFF variants "… (WOFF)" and the collection variants TrueType-Collection / OpenType-Collection (CFF).
```

### TXT-DOC-43 – Docstring: \_fc\_add\_font\_file

- **Module:** previewer\_render\_text.py
- **Location:** `\_fc\_add\_font\_file` (module level)
- **Reason:** Per-process Fontconfig takeover via ctypes; F11: temp-dir passthrough.

```text
Register a font file with Fontconfig for THIS process – without installing it system-wide: copy into a temporary folder, then FcConfigAppFontAddDir (libfontconfig via ctypes). Pango then reads the family via Fontconfig as usual. F11 (0.59.0): paths that already live in the temp dir (rebuilt WOFF sfnts) are NOT copied a second time – the directory add picks them up directly.
```

### TXT-DOC-44 – Docstring: \_font\_known

- **Module:** previewer\_render\_text.py
- **Location:** `\_font\_known` (module level)
- **Reason:** Family check against a FRESH font map.

```text
Is the family in the given (fresh) font map? The check goes through a NEW font map, because GTK's default font map only knows the state at startup.
```

### TXT-DOC-45 – Docstring: \_vcard\_unfold

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_unfold` (module level)
- **Reason:** vCard folding – standard plus 2.1 soft wrapping.

```text
Join line continuations: standard folding (line starts with a space or tab, RFC 6350) and the soft wrapping of vCard 2.1 (line ends with =, only with QUOTED-PRINTABLE).
```

### TXT-DOC-46 – Docstring: \_vcard\_split

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_split` (module level)
- **Reason:** Property line into (name, params, value).

```text
Split a property line into (name, params, value). The first colon separates head and value – further colons in the value (URLs, time stamps) stay untouched. Bare vCard 2.1 parameters (without TYPE=) land under TYPE.
```

### TXT-DOC-47 – Docstring: \_vcard\_parse

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_parse` (module level)
- **Reason:** Text into card tuples, quoted-printable decoded.

```text
Split text into cards. Each card is a list of (name, params, value). Quoted-printable values are decoded here; other escapes stay raw – callers resolve them with _vcard_unescape.
```

### TXT-DOC-48 – Docstring: \_vcard\_unescape

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_unescape` (module level)
- **Reason:** vCard value escapes.

```text
Resolve vCard escapes in the value (comma, semicolon, line break).
```

### TXT-DOC-49 – Docstring: \_vcard\_props

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_props` (module level)
- **Reason:** All values of a property as pairs.

```text
All values of a property as (params, value) pairs.
```

### TXT-DOC-50 – Docstring: \_vcard\_first

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_first` (module level)
- **Reason:** First non-empty property value.

```text
First non-empty value of a property (unescaped).
```

### TXT-DOC-51 – Docstring: \_vcard\_display\_name

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_display\_name` (module level)
- **Reason:** Display name with FN/N/nickname fallback chain.

```text
Display name: FN, else composed from N, else the nickname.
```

### TXT-DOC-52 – Docstring: \_vcard\_tel\_label

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_tel\_label` (module level)
- **Reason:** Telephone label from the TYPE parameter (German labels until F49).

```text
Telephone label from the TYPE parameter.
```

### TXT-DOC-53 – Docstring: \_vcard\_adr

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_adr` (module level)
- **Reason:** ADR into a readable address.

```text
ADR line (post box through country) into a readable address.
```

### TXT-DOC-54 – Docstring: \_vcard\_bday

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_bday` (module level)
- **Reason:** Birthday in dot notation.

```text
Birthday in dot notation (1985-04-12 or 19850412).
```

### TXT-DOC-55 – Docstring: \_vcard\_photo

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_photo` (module level)
- **Reason:** Card photo – inline base64 or local URI only.

```text
Photo of the card as bytes – inline base64 (ENCODING=b or BASE64, vCard 2.1 also with a bare parameter) or a local file URI (VALUE=URI respectively a file: spec). Network URIs are deliberately NOT loaded – the preview does not ask anyone on the net; the placeholder applies.
```

### TXT-DOC-56 – Docstring: \_vcard\_circle

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_circle` (module level)
- **Reason:** F7 – round photo crop with the F34 clip technique.

```text
F7: Crop the photo square and centered and mask it circularly (alpha channel at the edge) – the same Cairo clip technique as the cover corners (F34). Without Cairo the cropped square stays square.
```

### TXT-DOC-57 – Docstring: \_vcard\_placeholder

- **Module:** previewer\_render\_text.py
- **Location:** `\_vcard\_placeholder` (module level)
- **Reason:** F7 – round placeholder with person silhouette.

```text
F7: Round placeholder – bright circle with a muted person silhouette (head and shoulder arc), theme-neutral in grey tones. Without Cairo it returns None; the caller then shows a theme icon as a stopgap.
```

### TXT-DOC-58 – Docstring: \_ldif\_unfold

- **Module:** previewer\_render\_text.py
- **Location:** `\_ldif\_unfold` (module level)
- **Reason:** LDIF line continuation.

```text
LDIF line continuation (line starts with a space, RFC 2849).
```

### TXT-DOC-59 – Docstring: \_ldif\_record

- **Module:** previewer\_render\_text.py
- **Location:** `\_ldif\_record` (module level)
- **Reason:** One LDIF record into card tuples.

```text
Turn one LDIF record into card tuples – None if the record carries no contact fields (organizational containers, groups).
```

### TXT-DOC-60 – Docstring: \_ldif\_parse

- **Module:** previewer\_render\_text.py
- **Location:** `\_ldif\_parse` (module level)
- **Reason:** LDIF address books into the vCard card structure.

```text
LDIF address book (Thunderbird/Mozilla/Outlook exports): records are separated by blank lines; base64 values (double colon) are decoded, jpegPhoto stays raw. Each record goes through _ldif_record into the same card structure as vCard.
```

### TXT-DOC-61 – Docstring: \_contact\_one

- **Module:** previewer\_render\_text.py
- **Location:** `\_contact\_one` (module level)
- **Reason:** One .contact XML node into a card tuple.

```text
ONE contact node as a card tuple. Attributes are recognized via the LOCAL element names – the Microsoft namespace changes with the Windows version. Values sit in the element text or the Value attribute; photos stay out (the format embeds them inconsistently), the placeholder applies.
```

### TXT-DOC-62 – Docstring: \_contact\_parse

- **Module:** previewer\_render\_text.py
- **Location:** `\_contact\_parse` (module level)
- **Reason:** Windows contact file (XML) into cards.

```text
Windows contact file (.contact, XML): usually the ROOT already carries the contact; files with several contact nodes (collection) get all of them. Without a recognizable contact: empty list – the caller then shows the open hint.
```

### TXT-DOC-63 – Docstring: \_csv\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_csv\_data` (module level)
- **Reason:** F8 – CSV loader with sniffer and caps.

```text
F8: returns (headers, rows, delim, truncated).
```

### TXT-DOC-64 – Docstring: \_sqlite\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_sqlite\_data` (module level)
- **Reason:** F6 – schema-driven table list with progress cap.

```text
F6: Table list (name, columns, row count) from the schema. The magic check sends foreign files (.db is not always SQLite) to the open hint. The progress cap stops endless COUNT scans over huge tables (F60 lesson: the preview must be there immediately).
```

### TXT-DOC-65 – Docstring: TextRendererMixin (class)

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin` (class)
- **Reason:** Class marker – all text-side renderers.

```text
Mixin: renderers for text, Markdown, EML, e-book, font, vCard.
```

### TXT-DOC-66 – Docstring: \_read\_text\_file

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_read\_text\_file` (method)
- **Reason:** Capped file read for text and Markdown.

```text
Read a file capped: (text, truncated) – text and Markdown.
```

### TXT-DOC-67 – Docstring: \_render\_markdown

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_markdown` (method)
- **Reason:** Markdown with visible formatting, raw text on markup failure.

```text
Markdown with visible formatting: headings, bold/italic, code, lists, quotes and links render via Pango markup (no webview, no new packages). If markup generation ever fails, the raw text appears.
```

### TXT-DOC-68 – Docstring: \_render\_eml

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_eml` (method)
- **Reason:** EML preview with header table and body; 0.58.2: bold labels, italic values, subject below date, body always built.

```text
EML files (RFC 822): header lines (from, to, Cc, date, subject) as a table – the subject row sits BELOW the date row, labels bold, values italic (0.58.2, user request). Below the text body, which is ALWAYS built – mails WITHOUT text render like a mail with text (the "No readable text body found" hint is gone). Prefers text/plain; if missing, the HTML part is cleaned into readable text. All with Python on-board tools (email module).
```

### TXT-DOC-69 – Docstring: \_eml\_body

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_eml\_body` (method)
- **Reason:** Text body extraction with HTML fallback.

```text
Text body of an e-mail: text/plain preferred, else HTML.
```

### TXT-DOC-70 – Docstring: \_render\_vcard

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_vcard` (method)
- **Reason:** F7 – contact card formats as business cards.

```text
F7 (user request): contact card formats as a business card – vCard (.vcf/.vcard, dialects 2.1, 3.0, 4.0), LDIF address books (.ldif) and Windows contacts (.contact, XML). Each card carries a rectangular frame with the corner radius of the music covers (F34 formula) plus the same drop shadow. Card head: round photo (inline base64 or a local URI, else the drawn placeholder circle), below the name in large, position and company, then the contact data as the usual table. ALL cards of the file appear below each other in a scroll area; with a single contact no scrollbar shows, naturally.
```

### TXT-DOC-71 – Docstring: \_vcard\_card\_widget

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_vcard\_card\_widget` (method)
- **Reason:** F7 – one card widget with the draw-callback frame.

```text
F7: ONE business card as a widget. The frame – a rounded rectangle with the corner radius of the music covers plus the same drop shadow – is drawn in the draw signal BEHIND the widgets (→ _vcard_card_draw). Returns: (widget, photo?)
```

### TXT-DOC-72 – Docstring: \_vcard\_card\_draw

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_vcard\_card\_draw` (method)
- **Reason:** F7 – card background: frame, shadow, NO fill. Also frames the ICS event cards (F52, 0.60.0).

```text
F7: Background of the business card – rounded rectangle with the corner radius of the embedded music covers (0.25.1 a third more subtle: 56/960 of the smaller edge), the same drop shadow (F34/F35: six stacked, growing tiles) and NO fill – the card stays transparent, in dark mode a white tile base hurts the eyes. Returns False: GTK draws the widgets on top afterwards.
```

### TXT-DOC-73 – Docstring: \_render\_ebook

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_ebook` (method)
- **Reason:** F59 – e-book presentation after the image model.

```text
F59 (0.44.0): New e-book presentation after the image model – cover at the top (60 %), without a cover a drawn portrait placeholder, below (40 %) the info table (book title, author, series, pages, e-book format, language – only set tags). The text preview is dropped: it rendered poorly, the book info suffices. If the book cannot be read, there is a hint plus the generic preview.
```

### TXT-DOC-74 – Docstring: \_render\_epub

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_epub` (method)
- **Reason:** EPUB preview (F59 model).

```text
EPUB preview (F59: cover on top, book info below).
```

### TXT-DOC-75 – Docstring: \_render\_fb2

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_fb2` (method)
- **Reason:** FictionBook-2 preview (F59 model).

```text
FictionBook-2 preview (F59: cover on top, book info below).
```

### TXT-DOC-76 – Docstring: \_render\_mobi

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_mobi` (method)
- **Reason:** MOBI/PRC/AZW preview (F59 model).

```text
MOBI/PRC/AZW preview (F59: placeholder lid, book info).
```

### TXT-DOC-77 – Docstring: \_pack\_package\_capped

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_pack\_package\_capped` (method)
- **Reason:** F60 – inverse split: 40 % icon, 60 % scrollable info.

```text
F60 (0.45.0): Inverse image split (F38): 40 % icon on top, 60 % info area below – the latter sits in a ScrolledWindow because package info (description, dependencies) likes to be longer than the area. The split follows window resizes (pattern _image_split_sync).
```

### TXT-DOC-78 – Docstring: \_package\_split\_sync

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_package\_split\_sync` (method)
- **Reason:** F60 – icon area tracks 40 % of the column height.

```text
F60: Pull the icon area to 40 % of the column height.
```

### TXT-DOC-79 – Docstring: \_render\_package

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_package` (method)
- **Reason:** F60 – package preview flow (DEB, RPM, Arch).

```text
F60 (0.45.0): Package preview (DEB, RPM, Arch/Pacman) – 40 % icon on top (embedded app icon from the payload, else the drawn package placeholder), 60 % info table below in the scrollable area. If the package cannot be read, there is a hint plus the generic preview.
```

### TXT-DOC-80 – Docstring: \_render\_deb

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_deb` (method)
- **Reason:** Debian package preview entry.

```text
Debian package preview (F60: icon on top, info scrollable).
```

### TXT-DOC-81 – Docstring: \_render\_rpm

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_rpm` (method)
- **Reason:** RPM preview entry.

```text
RPM preview (F60: placeholder icon, info scrollable).
```

### TXT-DOC-82 – Docstring: \_render\_pkg

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_pkg` (method)
- **Reason:** Arch package preview entry.

```text
Arch package preview (F60: icon on top, info scrollable).
```

### TXT-DOC-83 – Docstring: \_pack\_table

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_pack\_table` (method)
- **Reason:** F8/F6 – real tables as Gtk.TreeView (F56 reuse later).

```text
F8/F6 (0.46.0): Real tables as Gtk.TreeView – scrollable in both directions, columns clickable-sortable and width-draggable. F56 (spreadsheets) can reuse the same renderer later.
```

### TXT-DOC-84 – Docstring: \_render\_csv

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_csv` (method)
- **Reason:** F8 – CSV as a real table, delimiter and header from content.

```text
F8 (0.46.0): CSV as a real table. The module detects delimiter AND header line from the content itself (user requirement: the column/cell delimiter is never guessed from the file name) – csv.Sniffer tries comma, semicolon, TAB and pipe against the first lines.
```

### TXT-DOC-85 – Docstring: \_render\_sqlite

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_sqlite` (method)
- **Reason:** F6 – SQLite table list, read-only, schema-driven.

```text
F6 (0.46.0): SQLite databases – table list with columns and row count. The structure comes entirely from the schema (sqlite_master, PRAGMA table_info), opened read-only (PRAGMA query_only).
```

### TXT-DOC-86 – Docstring: \_render\_font

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_font` (method)
- **Reason:** Font waterfall with a fresh Pango font map; F68: live re-render; F11: WOFF1 and all TTC faces.

```text
Font waterfall (TrueType, OpenType, WOFF1, collections): the file – for WOFF1 the rebuilt sfnt (F11) – is registered with Fontconfig for this process only (nothing is installed). The waterfall is pre-rendered into a pixbuf with a FRESH Pango font map – GTK's default font map is built at startup and overlooks fonts added at runtime (labels would silently show the fallback font). F11 (0.59.0): _font_faces returns EVERY face of a TTC; each face gets its own bold header (family – style) and its own waterfall, capped at _TTC_FACE_CAP (8) with a dim remainder hint – single fonts keep the info table with Family/Style, collections show Format + font count. F68 (0.58.3, user bug report): the surfaces come from _font_waterfall_pixbuf at the CURRENT column width and _apply_font_scale rebuilds them live while the divider is dragged – the sample text re-wraps immediately, the point sizes on screen stay constant (before, the one-time surface only got scaled: dragging wider grew the faces while the wrap kept the old width until the font was re-selected).
```

### TXT-DOC-87 – Docstring: \_ics\_unfold

- **Module:** previewer\_render\_text.py
- **Location:** `\_ics\_unfold` (module level)
- **Reason:** Unfold RFC 5545 folded lines.

```text
Unfold RFC 5545 line folding: a line break followed by a space or tab continues the previous line. Returns the unfolded lines of the whole file.
```

### TXT-DOC-88 – Docstring: \_ics\_dt

- **Module:** previewer\_render\_text.py
- **Location:** `\_ics\_dt` (module level)
- **Reason:** Readable date formatting for ICS values.

```text
DATE or DATE-TIME into a readable string; all-day values (VALUE=DATE parameter or no "T" in the value) show the date only. Anything the digit check cannot parse returns the raw value.
```

### TXT-DOC-89 – Docstring: \_ics\_text

- **Module:** previewer\_render\_text.py
- **Location:** `\_ics\_text` (module level)
- **Reason:** Unescape RFC 5545 text values for display.

```text
Unescapes RFC 5545 text values (\n line breaks, \, \; \\\) and collapses whitespace into single spaces – SUMMARIES and descriptions become one displayable line.
```

### TXT-DOC-90 – Docstring: \_ics\_data

- **Module:** previewer\_render\_text.py
- **Location:** `\_ics\_data` (module level)
- **Reason:** Parse VEVENT blocks from an iCalendar file.

```text
VEVENT blocks into dicts of (params, value) pairs; the first occurrence of a property wins (repeating properties stay unhandled). A block counts as an event when SUMMARY or DTSTART is present; the file is read with the 8 MB cap and decoded as UTF-8 with a BOM tolerance.
```

### TXT-DOC-91 – Docstring: \_eml\_attachment\_rows

- **Module:** previewer\_render\_text.py
- **Location:** `\_eml\_attachment\_rows` (module level)
- **Reason:** Collect EML attachments for the list.

```text
Every MIME part with a filename becomes a row of (name, size) – the content type is deliberately not collected anymore (0.58.2, user request); undecodable sizes stay None and display as "unknown". Path components in filenames are stripped – only the basename survives.
```

### TXT-DOC-92 – Docstring: \_unique\_target

- **Module:** previewer\_render\_text.py
- **Location:** `\_unique\_target` (module level)
- **Reason:** Conflict-free target path for extraction.

```text
Conflict-free target: if a file of that name already exists in the folder, a numbered suffix is appended (name_1.ext, name_2.ext …) until the path is free.
```

### TXT-DOC-93 – Docstring: \_pack\_eml\_attachments

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_pack\_eml\_attachments` (method)
- **Reason:** Attachment list plus extract button in the preview; 0.58.2: two-column table (name, size), no icon; 0.64.0: checkbox column before the name, five visible rows.

```text
Builds the "Attachments (N)" section at the bottom of the preview (packed from the bottom, directly above the toolbar). Each row: CheckButton, file name (hexpand, Middle-Ellipsize, tooltip), size (dim, END). The grid sits in a ScrolledWindow (policy NEVER/AUTOMATIC, max_content_height 150 px, propagate_natural_height) – at most five rows stay visible, longer lists scroll. The button "Extract selected attachments" receives the checkbox list via connect.
```

### TXT-DOC-94 – Docstring: \_on\_eml\_extract

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_on\_eml\_extract` (method)
- **Reason:** Extract the CHECKED attachments into a chosen folder (0.64.0: selected only, was all before).

```text
Reads the checkbox states (none checked: dim hint "No attachment selected", no chooser), opens the folder chooser (centered, transient for the Nemo toplevel), re-reads the whole e-mail and writes every part whose cleaned file name is in the checked set; conflicts get numbered suffixes via _unique_target. Duplicate file names share one checkbox and extract together; feedback counts only the selected parts.
```

### TXT-DOC-95 – Docstring: \_render\_ics

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_render\_ics` (method)
- **Reason:** ICS preview as scrollable event cards.

```text
ICS files (text/calendar): every VEVENT becomes its own card in the vCard look – frame and drop shadow via the _vcard_card_draw draw callback (0.60.0), stacked scrollable below each other, 50 events max with a dim remainder hint. Unreadable or eventless files fall back to the generic preview with a hint.
```

### TXT-DOC-96 – Docstring: \_ics\_event\_widget

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_ics\_event\_widget` (method)
- **Reason:** One event as a vCard-style card (F52, 0.60.0).

```text
One event as a vCard-style card: frame and drop shadow come from _vcard_card_draw (same look and inner margins as the contact cards, 0.60.0), bold summary on top, then Start/End/Location/Description rows via pack_meta_grid with wrapping values and the title column at least 75 px – longer labels ellipsize with a tooltip, the value column takes the rest (descriptions cap at 240 characters with an ellipsis). Missing properties are skipped instead of shown empty. 0.65.4 (user finding, live deploy): the label column had only a MINIMUM width, so cards without e.g. a Description stood narrower than the others; _render_ics now builds ONE Gtk.SizeGroup (HORIZONTAL) for all cards of the file and passes it through _ics_event_widget into pack_meta_grid's new size_group parameter – every label joins the group, GTK gives all cards the same label column (the widest label wins), the layout never shifts between events.
```

### TXT-DOC-97 – Docstring: \_font\_waterfall\_pixbuf

- **Module:** previewer\_render\_text.py
- **Location:** `\_font\_waterfall\_pixbuf` (module level)
- **Reason:** F68 – waterfall surface builder, extracted for live re-rendering.

```text
Builds the waterfall surface at DOUBLE the current preview width (sharp while scaling down): a "%d pt" tag line (9 pt, dimmed via 55 % alpha) and the sample text in the new family for every size of _FONT_SIZES, both Pango layouts on the fresh font context; the text wraps at the surface width (WORD_CHAR). Drawn into one cairo surface and returned as a pixbuf. F68 (0.58.3): takes the target width as a parameter – _apply_font_scale rebuilds the waterfall on column resize, so the wrap follows the dragged divider live.
```

### TXT-DOC-98 – Docstring: \_apply\_font\_scale

- **Module:** previewer\_render\_text.py
- **Location:** `TextRendererMixin.\_apply\_font\_scale` (method)
- **Reason:** F68 – live waterfall re-render on column resize (user bug report); F11: one item per face.

```text
Called from the panel's size-allocate handler (like _apply_pdf_scale): every waterfall item of \_font\_wf (F11: one PER FACE of a collection) re-renders on its own if the preview width moved at least 8 px – the waterfall pixbuf is REBUILT at the new width (re-wrapping the sample text) and fitted into the existing image, downscaled to fit, never upscaled, height capped at MAX_IMAGE_HEIGHT. Before 0.58.3 the surface was rendered once at the width the preview had when the font was selected and only scaled afterwards: dragging the column wider GREW the font faces while the wrap kept the old width (user bug report – only re-selecting the font helped). The item dicts (family, font context, theme color, sample text, image, last width) live in a list on the panel; it is dropped in \_clear\_content.
```

### TXT-DOC-99 – Docstring: \_woff1\_to\_sfnt

- **Module:** previewer\_render\_text.py
- **Location:** `\_woff1\_to\_sfnt` (module level)
- **Reason:** F11 – WOFF1 unpacked to a plain sfnt (pure bytes).

```text
WOFF1 (wOFF) rebuild: the 20-byte directory entries (tag, offset, compLength, origLength, origChecksum) are walked from offset 44; tables with compLength < origLength are zlib-decompressed. The sfnt is assembled with the WOFF flavor as version (never ttcf – a WOFF1 cannot wrap a collection), searchRange/entrySelector/rangeShift computed like a real font, tables sorted by tag, data padded to 4 bytes, the original checksums kept. WOFF2 (wOF2) is deliberately NOT supported (Brotli).
```

### TXT-DOC-100 – Docstring: \_sfnt\_face\_names

- **Module:** previewer\_render\_text.py
- **Location:** `\_sfnt\_face\_names` (module level)
- **Reason:** F11 – name table of one face, also inside collections.

```text
Reads family and style from the name table of ONE sfnt face at the given offset (pure byte work): walks the face's table directory for the name table, decodes the name records (platform 0/3 as UTF-16BE, else roughly Latin-1), prefers name IDs 1/16/4 for the family and 2/17 for the style, and returns (family, style). Extracted from the former \_font\_info so collections can parse EVERY face at its own offset.
```
---

## GTK4-Port-Audit (F57)

### AUDIT-GTK4-1 – Method and standing rule (F57)

- **Module:** all eight Python modules
- **Location:** this REFERENCE section (added at the end of the file)
- **Reason:** F57 – first GTK4 check: inventory per module of the GTK3-only APIs, so a later port stays possible.

```text
F57 (2026-11-06, audit round WITHOUT code changes): static scan of the eight modules for APIs that GTK4 removes or changes. Standing rule for every future round: do not introduce NEW uses of the breaking families (draw signal, Gdk.Screen, StyleContext color getters, size-allocate connects, container add/pack, border-width properties, show_all, IconTheme.get_default, FileChooserDialog, WindowType, shadow types). Re-run patterns: connect("draw", add_provider_for_screen, get_background_color, connect("size-allocate", show_all(), get_default(), FileChooserDialog, set_border_width, .pack_, container .add(. GTK deprecation warnings of the PyGObject layer land on the stderr of the Nemo process – watch them in the debug log (NEMO_PREVIEWER_DEBUG=1) after system GTK updates. Verdict: the port is NOT blocked by the byte and parser layers (struct/zipfile, offscreen Pango/cairo, Gdk.pixbuf_get_from_surface, Poppler, GStreamer all survive GTK4); it is blocked by (a) the draw-signal painter chain, (b) four size-allocate connects, (c) roughly 90 mechanical box/window calls and – hardest – (d) the crowbar itself, because the injection re-parents widgets of the HOST file manager and no GTK4 host exists today (see AUDIT-GTK4-10).
```

### AUDIT-GTK4-2 – Entry point (previewer.py)

- **Module:** previewer.py
- **Location:** PanelState: crowbar placement (\_on\_crowbar\_placed), \_on\_hpaned\_draw, \_on\_size\_allocate
- **Reason:** F57 inventory – two GTK3-only signal connects plus the injection mechanics.

```text
hpaned.connect("draw") for the Paned handle painter: GTK4 has no draw signal, and the Paned handle GdkWindow the painter relies on disappears with Gdk.Window – the whole F46 handle approach needs a new plan in GTK4. hpaned.connect("size-allocate"): not a connectable signal in GTK4 (vfunc only) – would need a widget subclass. Gtk.Paned.new(Gtk.Orientation.HORIZONTAL) survives GTK4. Mechanical: pack_start x2, pack_end x1, parent.add(child1) (crowbar re-parent), show_all x2, set_no_show_all x1. The isinstance Gtk.Toolbar check survives (the class still exists), but the entire injection depends on the host widget tree (AUDIT-GTK4-10).
```

### AUDIT-GTK4-3 – Panel (previewer_panel.py)

- **Module:** previewer\_panel.py
- **Location:** painter chain (\_paint\_background, \_on\_panel\_draw), CSS provider, header/content packing, \_is\_desktop\_window
- **Reason:** F57 inventory – the heaviest module: painters, StyleContext colors and screen-scoped CSS.

```text
connect("draw") x4 (panel itself, folder bar, scroll window, viewport): the whole F46 background chain rides on the draw signal – GTK4 needs Gtk.DrawingArea draw funcs or snapshot painting, and the chain paints through OTHER widgets' style contexts, which is exactly what the new render model forbids. Gtk.StyleContext.add_provider_for_screen (K11, 0.59.2) becomes add_provider_for_display; the #previewer-panel scope via widget name still works. get_style_context x20, get_color x3, get_background_color x4: the color getters are removed (background) or deprecated (color, 4.10) in GTK4 – the fallback color derivation of the painter chain needs a replacement source (settings/theme CSS). Gtk.IconTheme.get_default x2 becomes get_for_display. connect("size-allocate") x1 needs a subclass. get_toplevel x1 becomes get_root. Mechanical: pack_start x14, pack_end x2, container add x3, set_border_width x3 (CSS margins instead), show_all x2, set_no_show_all x1. Survive GTK4 unchanged: connect("realize"), set_overlay_scrolling(False), queue_draw, the rec dot, size drawing via Pango.
```

### AUDIT-GTK4-4 – Selection (previewer\_select.py)

- **Module:** previewer\_select.py
- **Location:** whole module (Nemo provider signals, ctypes capsule bridge)
- **Reason:** F57 inventory – cleanest module.

```text
No GTK widget API at all: the module works on the Nemo provider signals and the ctypes capsule bridge; the .add( hits are Python sets. Zero port work outside the host API itself (see AUDIT-GTK4-10).
```

### AUDIT-GTK4-5 – Helpers (previewer\_util.py)

- **Module:** previewer\_util.py
- **Location:** pick\_icon, build\_text\_view, build\_scaled\_image, pack\_hint
- **Reason:** F57 inventory – icon theme, shadow type, two container adds.

```text
pick_icon: Gtk.IconTheme.get_default() becomes get_for_display in GTK4. build_text_view: scroll.set_shadow_type(Gtk.ShadowType.IN) – shadow types are removed in GTK4, the frame look would move to CSS (border or .undershoot styling). Mechanical: scroll.add(img)/scroll.add(view) x2 become set_child, pack_start x2 becomes append. get_style_context x2 + add_class x2 survive GTK4 (add_class stays). Gdk.Display.get_default().get_primary_monitor()/get_monitor(0) and the Pango layout code survive GTK4 unchanged.
```

### AUDIT-GTK4-6 – Toolbar (previewer\_toolbar.py)

- **Module:** previewer\_toolbar.py
- **Location:** settings window + frames, PreviewToolbarMixin packing
- **Reason:** F57 inventory – settings window type, five border widths, pure box packing.

```text
Gtk.Window(type=Gtk.WindowType.TOPLEVEL) in the settings window: WindowType is removed in GTK4 – plain Gtk.Window() suffices there. set_border_width x5 (window and frames) becomes CSS margins/padding. Mechanical: pack_start x24, pack_end x1, frame.add x5 (set_child), show_all x2 (show). Everything else (Gtk.Frame, Gtk.CheckButton, Gtk.SpinButton, entries) survives GTK4.
```

### AUDIT-GTK4-7 – Media (previewer\_render\_media.py)

- **Module:** previewer\_render\_media.py
- **Location:** player bar (seek scale), tag windows, image split sync, placeholder cover
- **Reason:** F57 inventory – the only event-signal connects of the codebase.

```text
Seek scale: connect("button-press-event")/connect("button-release-event") – event signals move to event controllers in GTK4 (GestureDrag or Button/GestureLongPress on the scale); both handlers ignore the event object (only _seek_dragging is toggled), so the port is mechanical. connect("size-allocate") x1 (image split sync) needs a subclass. get_toplevel x1 (tag window transient) becomes get_root. Gtk.IconTheme.get_default x1 becomes get_for_display. Mechanical: show_all x7, pack_start x17, container add x2 (scroll.add, win.add). Survive GTK4: the offscreen pycairo cover tile (F18), the SVG-DPI route (K3), Gdk.pixbuf_get_from_surface, the whole GStreamer layer (GtkSink/videooverlay stays a Gst question, not a Gtk one).
```

### AUDIT-GTK4-8 – Documents (previewer\_render\_docs.py)

- **Module:** previewer\_render\_docs.py
- **Location:** PDF page box, office fallback, page scaling
- **Reason:** F57 inventory – the smallest module.

```text
Mechanical only: show_all x1, pack_start x5, scroll.add(box) x1 (set_child). get_style_context x1 + add_class x1 survive. The rendering core (Poppler page render into a cairo ImageSurface, Gdk.pixbuf_get_from_surface) works the same under GTK4; the _pdf_scale_step idler lives on GLib, unaffected.
```

### AUDIT-GTK4-9 – Text (previewer\_render\_text.py)

- **Module:** previewer\_render\_text.py
- **Location:** font file pick, vCard/ICS card painters, package split, tag/package tables
- **Reason:** F57 inventory – file chooser, the two card painters, five container adds.

```text
Gtk.FileChooserDialog (font pick in the font preview) is removed in GTK4 – the replacement is Gtk.FileDialog (since 4.10) or Gtk.FileChooserNative. connect("draw") x2 (vCard and ICS cards) move to Gtk.DrawingArea with set_draw_func; the cards pre-render with pycairo offscreen anyway, so only the widget hookup changes. connect("size-allocate") x1 (package split) needs a subclass. get_toplevel x1 becomes get_root. Mechanical: pack_start x22, pack_end x1, scroll.add x5. Survive GTK4: the offscreen font waterfall (F68), watermarks and placeholder covers via ImageSurface + Gdk.pixbuf_get_from_surface, the TreeView tag/package tables (TreeView stays in GTK4), pack_meta_grid.
```

### AUDIT-GTK4-10 – Host API: Nemo (Caja) separately

- **Module:** previewer.py + previewer\_select.py (host coupling)
- **Location:** crowbar injection, column/info providers
- **Reason:** F57 – the Nemo-API port is evaluated separately, as planned demands.

```text
The extension lives inside the host process: previewer.py re-parents Nemo's own widgets (crowbar) and walks the host widget tree (isinstance Gtk.Toolbar), previewer_select.py rides on the Nemo column/info provider API. A GTK4 port of OUR code would be pointless while the host binds GTK3 – and the crowbar would break first, because it relies on the host's container/add mechanics. Caja (MATE) is GTK3 as well. Conclusion: keep the own modules free of new GTK3-only APIs (this audit is the baseline), re-evaluate the injection layer only when a GTK4-based host exists; porting the Nemo API is a separate project item, not part of F57.
```

## Performance-Audit (F58)

### AUDIT-PERF-1 – Method and standing rule (F58)

- **Module:** all eight Python modules
- **Location:** this REFERENCE section (after the GTK4-Port-Audit)
- **Reason:** F58 (2) performance – static scan of the hot paths: render times per format (large PDFs, office conversion, full folders) and entry load time.

```text
F58 (2026-11-07, audit round WITHOUT code changes): static performance scan – the sandbox cannot run or profile the code, so the audit covers the planned scope from the code side (structure, caps, thread/idle discipline, per-event costs) and names the deploy-side runtime checks at the end. Standing rule for every future round: (a) heavy work NEVER runs synchronously inside a size-allocate or value-changed handler – the 0.65.3 incidents are the reference case; generation-guarded idle steps (K12 pattern) or a quiet timer are the accepted patterns; (b) every reader keeps a byte/row/page budget; (c) one stat per render is fine, per-row I/O needs a cap; (d) worker threads decode, idle_add delivers to GTK (R1/B7).
```

### AUDIT-PERF-2 – Entry load time and per-window costs (previewer.py)

- **Module:** previewer.py (+ previewer_select.py)
- **Location:** module imports, _get_widget, PanelState, _poll/_refresh/_reconcile
- **Reason:** F58 (2) – load time of the entry: import chain and the recurring per-window costs.

```text
Startup: Nemo imports the extension module once per process – previewer.py then imports all seven modules eagerly (extension contract, unavoidable). Heavy gi families stay guarded: Poppler (HAVE_POPPLER), GtkSource (HAVE_GTKSOURCE) and PangoCairo (HAVE_PANGOCAIRO) sit behind require_version try blocks; GStreamer initialises lazily on the first media render (K5 one-shot, HAVE_GST tri-state). Startup cost = Python imports + GTK binding init; no Poppler/Gst work at load. Per window: _get_state caches ONE PanelState per window (no re-scan per folder change), the crowbar packs a zero-size box and defers its placement to an idle handler; _get_widget itself is cheap widget packing. Recurring: the 500 ms safety-net poll (POLL_MS, util) runs _reconcile (bounded: window children once + parent-pointer chain up to the top box) and _refresh (SelectionReader.read per tick, one widget-tree diag dump per view TYPE, the selection-unreadable debug throttled to 5 s). Verdict: OK – the only recurring cost is the bounded 500 ms walk; the timer is removed on window destroy (ENT-DOC-17). Deploy-side check: Nemo start with and without the extension (log timestamps), rapid folder hopping.
```

### AUDIT-PERF-3 – Render dispatch, F2 debounce and per-render overhead (panel)

- **Module:** previewer_panel.py
- **Location:** _render/_render_inner, _is_heavy, the _pending_render_id chain, _clear_content
- **Reason:** F58 (2) – dispatch costs: how often renders run and what each render pays up front.

```text
F2: heavy formats (PDF/Office via _OFFICE_EXTS + .pdf, audio/video by MIME) render after a 400 ms selection-quiet timeout (_RENDER_QUIET_MS), light formats immediately; a new selection CANCELS a queued render – renders never stack. Per render: exactly ONE query_file_info (single Gio query_info stat) plus _clear_content, which resets all incremental state and bumps every generation counter (_pdf_gen, _pdf_scale_gen; the 0.65.3 image rescale rides _img_scale_gen) – running idle steps abort cleanly instead of painting into a torn-down tree. Verdict: OK – no unbounded pre-work per render; the heavy/light split keeps the common case (images, text) immediate.
```

### AUDIT-PERF-4 – Large PDFs (previewer_render_docs.py)

- **Module:** previewer_render_docs.py
- **Location:** _render_pdf, _pdf_page_pixbuf, the R2 idle feed, _pdf_scale/_pdf_scale_step
- **Reason:** F58 (2) – large PDFs: first-page latency, page budget, resize costs.

```text
_render_pdf: page 1 renders synchronously (the panel is usable at once), the remaining pages feed through R2 idle steps – a huge PDF paints progressively without blocking the loop. Per page: _pdf_page_pixbuf renders at 2x the target width (stays sharp while live-scaling) but is BOUNDED – the scale is clamped to 0.2–3.0 and _PDF_PIXEL_BUDGET shrinks both dimensions until the pixel count fits (DOC-BUDGET-1), so the worst-case single-page cost is constant, not proportional to the PDF. Page COUNT: the settings cap (_pdf_page_cap, at most 999) limits the feed. Resize: _pdf_scale does NOT re-render pages – it scales the stored pixbufs, generation-guarded, one page per idle step (K12). Verdict: OK. Deploy-side check: 1000+-page PDF and a 500 MB scanned PDF – first page fast, scrolling stays fluid.
```

### AUDIT-PERF-5 – Office conversion (previewer_render_docs.py)

- **Module:** previewer_render_docs.py
- **Location:** _render_office, _render_office_thumb, _office_start_job/_office_job_done, office_cache_path
- **Reason:** F58 (2) – office conversion: UI blocking, retry storms, repeat costs.

```text
Flow: the thumbnail route first (ZIP member read with caps – _OFFICE_THUMB_CAP guards a crafted thumbnail bomb; embedded text via _extract_office_text) gives an instant preview; the sharp conversion runs soffice --headless via GLib.spawn_async + child_watch – the UI NEVER blocks on LibreOffice. Single-flight: _office_job holds exactly ONE running conversion (a further selection just shows the thumbnail), _office_failed prevents endless retries of broken documents. Repeat selections are O(1): the result lands in ~/.cache/previewer/<sha-of-path>.pdf and _office_cached_pdf validates by mtime before reuse. Temp handling: one temp dir per job, shutil.move (EXDEV-safe) into the cache, cleanup on every path including _destroyed (window gone). Verdict: OK. Follow-up for the memory audit: the cache has no size limit (planned item 3). Deploy-side check: a 100 MB DOCX – thumbnail at once, sharp view after the conversion, re-selection instant.
```

### AUDIT-PERF-6 – Full folders (previewer_panel.py)

- **Module:** previewer_panel.py
- **Location:** _render_folder, _folder_row, _folder_symbol
- **Reason:** F58 (2) – full folders: scan cost, row building, icon work.

```text
Scan: os.scandir with the dirent type – the dirs/files split needs NO per-entry stat; the one os.stat per FILE row (size column) is bounded by the row cap of 300 (worst case 300 stats – negligible on local disks, bounded on network shares). Rows: max 300 built, the rest collapses into "... and N more". Icon work stays O(unique types), not O(rows): _folder_symbol caches the drawn silhouettes per symbol (sil dict), the picked map collects one entry per content type; per row only Label+Box assembly. The rows land in a Gtk.ListBox inside a ScrolledWindow. Verdict: OK – a folder with 10000 files costs one scandir plus 300 cheap rows. Deploy-side check: /usr/bin or a kernel source directory.
```

### AUDIT-PERF-7 – Images and A/V (previewer_render_media.py)

- **Module:** previewer_render_media.py
- **Location:** image probe worker, _image_probe_done, GStreamer lazy init, media probe threads
- **Reason:** F58 (2) – decode costs: big images, EXIF walk, media discovery.

```text
Images: the EXIF/XMP probe and the file read run in a worker thread (R1/B7 discipline) with GLib.idle_add delivery; the decode uses new_from_file_at_scale – the cost scales with the TARGET size, not the source resolution (a 50 MP photo decodes to panel width, never to full size). Lifeline: only when a thread cannot start at all does the same path run synchronously. A/V: GStreamer initialises lazily on the first media render (K5 one-shot, tri-state HAVE_GST – nothing Gst at import), the discoverer runs in its own thread with idle delivery; the pipeline builds once per preview. Live resize of images goes through the 0.65.3 generation-guarded idle rescale (see AUDIT-PERF-9). Verdict: OK – nothing decodes on the GTK thread. Deploy-side check: a 40 MP photo and a 4K video file.
```

### AUDIT-PERF-8 – Text format caps (previewer_render_text.py)

- **Module:** previewer_render_text.py
- **Location:** the reader constants (caps) and the truncation points
- **Reason:** F58 (2) – per-format budgets: no unbounded reader in the text module.

```text
Every reader has a budget: plain text MAX_TEXT_BYTES/MAX_TEXT_LINES (read truncated, lines capped), vCard/FB2/ICS 8 MB each (_VCARD_FILE_CAP, _FB2_FILE_CAP, _ICS_FILE_CAP), ICS events _ICS_EVENT_CAP = 50, CSV 4 MB/1000 rows with a 64 KB sniffer window (_CSV_FILE_CAP/_CSV_ROW_CAP/_CSV_SNIFF_CAP), e-book container chunks 2 MB and covers 16 MB (_EBOOK_CHUNK_CAP/_EBOOK_COVER_CAP), package control 2 MB/RPM head 4 MB/icon scan 8 MB (_PKG_CONTROL_CAP/_PKG_HEADER_CAP/_PKG_ICON_SCAN_CAP), TTC faces 8 (_TTC_FACE_CAP). Long strings truncate BEFORE widget building (descriptions 240 characters, package fields, and so on). Verdict: OK – no reader in this module can loop over unbounded input; the caps are old and battle-tested.
```

### AUDIT-PERF-9 – Findings, fixed incidents and follow-ups

- **Module:** previewer_panel.py, previewer_toolbar.py (incidents) / all modules (standing rules)
- **Location:** this audit section
- **Reason:** F58 (2) – verdict summary: what the audit found, what it confirms, what moves to the other audits.

```text
Verdict: no NEW hot-path defect found. The audit CONFIRMS the 0.65.3 fixes as the correct patterns for this risk class: the live-deploy incidents (synchronous image rescale per size-allocate; config write + full re-render per spin tick) violated exactly the standing rules, and their fixes (generation-guarded idle steps; equality guard + 400 ms quiet timer) match how the PDF path has worked since K12. Remaining notes, none blocking: (a) _apply_font_scale (F68 font waterfall) still re-renders synchronously on a width change – bounded to a handful of font previews, acceptable here, revisit when the waterfall grows; (b) the office conversion cache is unbounded – not a PERFORMANCE bug (repeat selections are cache hits), but it is the planned memory-audit item "Cache-Wachstum in ~/.cache/previewer/ begrenzen"; (c) runtime numbers (ms per format) are deploy-side: the per-renderer dbg lines plus NEMO_PREVIEWER_DEBUG=1 provide the timestamps for a quick profile pass. Deploy-side checks are named in AUDIT-PERF-2/4/5/6/7.
```

## Speicher/Leaks-Audit (F58)

### AUDIT-MEM-1 – Method and standing rule (F58)

- **Module:** all eight Python modules
- **Location:** this REFERENCE section (after the Performance-Audit)
- **Reason:** F58 (3) memory/leaks – signal handlers and references during the live re-renders, pixbuf caches, growth of ~/.cache/previewer.

```text
F58 (2026-11-07, audit round WITHOUT code changes): static leak scan with the planned focus areas. Standing rule: every widget-owned signal dies with the widget (GTK destroy cascade), every process-wide structure needs a cap or an explicit cleanup, every GLib source needs exactly ONE owner that removes it, and every byte we park on disk outside the config belongs to a bounded store. The audit inventories (a) the signal wiring and its teardown, (b) the live re-render state that holds big objects, (c) unbounded sets and disk stores, (d) the timer-vs-destroy races.
```

### AUDIT-MEM-2 – Signal wiring and teardown

- **Module:** previewer_panel.py, previewer_render_media.py, previewer.py, previewer_select.py
- **Location:** all connect() sites, _on_panel_destroy, _on_window_destroyed
- **Reason:** F58 (3) – do handlers outlive their widgets and keep references alive?

```text
Panel/media signal wiring connects handlers ON the widgets they belong to (draw, size-allocate, clicked, change-value) – GTK disconnects them when the widget dies in the destroy cascade; no manual disconnect list is needed and none exists, so none can be forgotten half-managed. The panel destroy handler sets _destroyed, stops playback and removes the playbin bus signal watch (0.9.1) – the only watch that needs manual removal. The per-window poll timer is the single GLib source owned by the WINDOW side; _on_window_destroyed removes it explicitly (ENT-DOC-17). previewer_select.py holds NO GTK signal handlers at all (AUDIT-GTK4-4) – the module reads the host via the Nemo provider API and Atk, it never connects. The one child_watch (LibreOffice) is one-shot and fires exactly once. Verdict: no leaked handler wiring.
```

### AUDIT-MEM-3 – Live re-render state (big objects)

- **Module:** previewer_panel.py, previewer_render_docs.py, previewer_render_media.py
- **Location:** _clear_content, _scale_items, _pdf_src/_pdf_imgs, _font_wf, _image_info_box, playbin
- **Reason:** F58 (3) – the preview keeps big pixbufs alive during live re-renders; where do they die?

```text
The heavy objects of a preview are the ORIGINAL-resolution pixbufs behind the scale items, the rendered PDF page pixbufs (_pdf_src/_pdf_imgs) and the font waterfall surfaces. All of them die TOGETHER in _clear_content, which every new selection/render passes through: it resets _scale_items (dropping the originals), _pdf_src/_pdf_imgs/_pdf_box, _font_wf and _image_info_box, and bumps every generation counter (_pdf_gen, _pdf_scale_gen – and via the 0.65.3 rescale _img_scale_gen) so already-scheduled idle steps stop instead of painting into the torn-down tree. The GStreamer playbin is created ONCE per panel and reused per media file (no per-render pipeline accumulation); the progress timer stops itself within one tick when nothing plays. The office thumbnail/text route holds only capped byte blobs. Verdict: no accumulation across renders – the clear discipline is the load-bearing wall and it is intact.
```

### AUDIT-MEM-4 – Unbounded sets and disk stores

- **Module:** previewer_render_docs.py, previewer_util.py, previewer_render_text.py
- **Location:** _office_failed, office_cache_dir, debug log (F65), _FONT_STATE tmpdir, selftest
- **Reason:** F58 (3) – process-lifetime structures and on-disk growth.

```text
_office_failed (broken office documents): CAPPED at 256 entries – on overflow it clears completely (all-or-nothing, retry storm impossible either way). Debug log (F65/F65b): rotates once per session at 512 KB (keeps exactly one .old) and the stale cleanup deletes logs older than 7 days at every panel start – bounded on both axes. Font temp dir (_FONT_STATE): process-lifetime in /tmp, grows with the number of PREVIEWED fonts (rebuilt WOFF sfnts + copies for Fontconfig, deduplicated by path hash) – bounded by usage, and /tmp is a systemd-tmpfiles store; acceptable, not a leak. Selftest: temp dir removed in a finally (files then rmdir). FINDING (the one real gap): the office conversion cache ~/.cache/previewer/<sha>.pdf has NO size limit – every distinct office document leaves a permanent PDF of up to document size; nothing ever deletes an entry. Not a process leak (disk), but exactly the planned item "Cache-Wachstum begrenzen". Recommendation: cap by total size (e.g. 256 MB) with oldest-mtime eviction at panel start, or cap per-file at conversion time. → FIXED in 0.65.5 (F70): _OFFICE_CACHE_MAX 256 MB, oldest-mtime eviction after every successful cache write (office_cache_evict).
```

### AUDIT-MEM-5 – Timer races vs. panel destroy

- **Module:** previewer_panel.py, previewer_toolbar.py, previewer_render_media.py
- **Location:** _pending_render_id, _spacing_render_id, probe idle callbacks vs. _destroyed
- **Reason:** F58 (3) – timers and idle callbacks that fire into a destroyed panel.

```text
The F2 pending render (_pending_render_id) is cancelled on every NEW selection, but _on_panel_destroy does NOT cancel it – a queued heavy render can fire up to 400 ms after the panel died. The 0.65.4 line-spacing quiet timer (_spacing_render_id) has the same shape: re-armed on every tick, never cancelled at panel teardown, and _on_line_spacing_quiet checks neither. The worker-idle deliveries (image/media probe done) compare self._path != path (stale-selection guard, works), but do not check _destroyed. All three are WARNING class, not leak class: the callbacks are one-shot, the Python objects still exist after the GTK destroy, and the references die with the fired callback – nothing accumulates. Still: _on_pending_render/_on_line_spacing_quiet/probe callbacks painting into a destroyed panel produce GTK warnings on stderr of the host. Recommendation (one small hardening item): cancel _pending_render_id and _spacing_render_id in _on_panel_destroy and let the idle deliveries test _destroyed first. → FIXED in 0.65.5 (F71): _on_panel_destroy cancels both timers (_cancel_pending_render + _spacing_render_id), _image_probe_done/_media_probe_done return early on _destroyed.
```

### AUDIT-MEM-6 – Verdict (F58/3)

- **Module:** –
- **Location:** this audit section
- **Reason:** F58 (3) – summary: leaks, findings, planned items.

```text
Verdict: no classic leak found – handler wiring dies with its widgets, the big-object clear discipline is intact on every render switch, every process-lifetime structure except the disk cache is capped, and the GStreamer pipeline is reused, not accumulated. TWO findings go into planned as items: (1) office conversion cache unbounded (~/.cache/previewer) – size cap with oldest-first eviction recommended; (2) timer/idle callbacks can fire up to 400 ms into a destroyed panel (F2 pending render, spacing quiet timer, probe deliveries) – add destroy cancels and _destroyed guards. Both are small, neither blocks the release; together with AUDIT-PERF-9 they are the complete follow-up list of the audit phase.
```

## Reentrancy-Audit (F58)

### AUDIT-REENTR-1 – Method and standing rule (F58)

- **Module:** all eight Python modules
- **Location:** this REFERENCE section (after the Speicher/Leaks-Audit)
- **Reason:** F58 (4) reentrancy/threading – clicks and selection changes during a running LibreOffice conversion; timeout-ID discipline.

```text
F58 (2026-11-07, audit round WITHOUT code changes): the audit follows the two planned focus areas. Standing rule: (a) every GLib source has exactly one owner and one removal path; (b) async results apply only if the world they were computed for still exists (stale checks: generation counters, path comparison, _destroyed); (c) ONE async job per class of work (single-flight); (d) GTK calls happen on the GTK thread only – worker threads hand over via idle_add; (e) no synchronous heavy work inside signal emission (the 0.65.3 incidents are the reference cases).
```

### AUDIT-REENTR-2 – Clicks and changes during the LibreOffice conversion

- **Module:** previewer_render_docs.py
- **Location:** _office_start_job, _office_job_done, _office_failed
- **Reason:** F58 (4) – the planned core question: what happens to a conversion when the user moves on?

```text
Single-flight: _office_job holds exactly ONE running conversion – a second office selection cannot start a parallel soffice (it shows the thumbnail route and waits). The child_watch fires once, _office_job resets first, and _office_job_done then decides by STATE, not by hope: _destroyed (panel gone) drops the result and cleans the temp dir; on success the cache gets the PDF (mtime-validated on reuse); a re-render only happens when self._path == path – the stale-selection guard; a failure lands in _office_failed (capped) so nothing retry-loops. finally: rmtree covers every branch. And the queueing is explicit: after the job ends, IF the current selection is an office file without cache/failed/job, the NEXT conversion starts immediately – no implicit recursion depth, just one hand-off. Verdict: OK – the conversion pipeline is the discipline showpiece; the 0.65.3 incidents happened in UI-thread paths, not here.
```

### AUDIT-REENTR-3 – Worker threads and their delivery

- **Module:** previewer_render_media.py, previewer_render_text.py
- **Location:** image/media/font probe workers, GLib.idle_add delivery, stale guards
- **Reason:** F58 (4) – thread/GTK hand-overs: who checks what, and when?

```text
All decode/probe work runs in daemon threads and hands its result over with GLib.idle_add (R1/B7); the GTK thread only assembles widgets. Stale guards on delivery: the image probe compares self._path != path and drops the result ("Image result dropped, selection changed"), the media probe delivers the same way, the font work deduplicates by path hash in a state dict (no double-registration races because everything mutates on the GTK side). The known weak spot is not reentrancy inside the workers (they never touch GTK) but the delivery target: the idle callbacks test the SELECTION but not _destroyed – a destroyed panel can receive one last paint attempt (see AUDIT-MEM-5, warning class). The 0.65.2 live incident pair (sync rescale inside size-allocate; re-render storm inside value-changed) was exactly rule (e) violated; the 0.65.3 fixes restored it. Verdict: OK with one hardening item (shared with AUDIT-MEM-5). → FIXED in 0.65.5 (F71).
```

### AUDIT-REENTR-4 – Timeout- and idle-ID discipline (inventory)

- **Module:** all modules with GLib sources
- **Location:** poll timer, F2 pending render, spacing quiet timer, progress timer, R2 feed, scale steps
- **Reason:** F58 (4) – the planned "Timeout-ID-Disziplin": every source, its owner, its removal.

```text
Inventory: (1) window poll (500 ms, entry) – owned by the window state, removed in _on_window_destroyed; (2) F2 pending render (400 ms, panel) – cancelled on every new selection, source id cleared in _cancel_pending_render and _on_pending_render; NOT cancelled at panel destroy (AUDIT-MEM-5); (3) spacing quiet timer (400 ms, 0.65.4) – re-armed via source_remove before every new arm, id cleared in the callback; not destroyed-at-teardown (AUDIT-MEM-5); (4) player progress timer (400 ms, media) – self-stopping: _tick_player returns False when nothing plays, re-created on the next start (no remove needed, no id leak); (5) R2 PDF page feed + K12 pdf scale steps + 0.65.3 image scale steps – generation-guarded idlers: every new event bumps the generation, stale steps return False and drop themselves (no ids to track, the generation IS the discipline); (6) _refresh_soon/crowbar placement idles – one-shot lambdas. Verdict: two disciplines coexist and both are consistently applied: id-with-owner for timers, generation-counter for idler families; the only gap is the destroy path of (2) and (3).
```

### AUDIT-REENTR-5 – Verdict (F58/4)

- **Module:** –
- **Location:** this audit section
- **Reason:** F58 (4) – summary.

```text
Verdict: the async machinery is sound: single-flight conversions with stale-selection and destroy guards, worker threads that never touch GTK, delivery via idle with path checks, and two clean cancellation disciplines (id-owner for timers, generation counter for idler families). The two live incidents of the 0.65.x deploys both traced back to rule (e) violations in UI-thread handlers and are fixed since 0.65.3. The one remaining hardening item is shared with AUDIT-MEM-5: destroy-side cancels for the two 400 ms timers plus _destroyed checks in the probe deliveries – warnings only, one small planned item, not release-blocking.
```

## Barrierefreiheits-Audit (F58)

### AUDIT-A11Y-1 – Method (F58)

- **Module:** all UI modules
- **Location:** this REFERENCE section (after the Reentrancy-Audit)
- **Reason:** F58 (5) a11y – accessible roles and states, checked systematically (static scan of the widget inventory).

```text
F58 (2026-11-07, audit round WITHOUT code changes): systematic static pass over the widget inventory by class: every interactive control needs a name (label, tooltip or accessible description), every informational label needs its text in the widget (not only painted), every icon-only button needs a tooltip, ellipsized text needs the full content as tooltip, and state changes must ride on widget states (dim-label, sensitivity), not on invisible side channels. Screen-reader behaviour itself is deploy-side; this audit checks the supply side.
```

### AUDIT-A11Y-2 – Inventory: what is already supplied

- **Module:** previewer_panel.py, previewer_toolbar.py, previewer_util.py, previewer_render_text.py
- **Location:** labels, tooltips, ellipsized widgets, settings window
- **Reason:** F58 (5) – the positive inventory.

```text
Labels carry their text in the widget everywhere (no painted-only text); info tables get tooltips with the FULL value on every row (pack_meta_grid, including the ellipsized title column of the ICS cards); the folder rows give the full name as tooltip on middle-ellipsized labels and dim hidden files via a style class; the settings window is fully supplied: every check button, spin and the close button carry label or tooltip; the toolbar toggle, the reset-width arrow, the open button and the recording dot carry tooltips; the K6 multi-selection count is a real label in the content area; hints (pack_hint) are labels, not painted text; interactive widgets use sensitivity (set_sensitive) for state, not hidden alternatives. previewer_select.py consumes Atk on the HOST side (AtkSelection/StateType to READ the Nemo selection) – the only a11y API in the project so far.
```

### AUDIT-A11Y-3 – Finding: the media player bar

- **Module:** previewer_render_media.py
- **Location:** _player_bar (_btn_play, _seek_scale)
- **Reason:** F58 (5) – the one gap of the scan.

```text
The player bar is the ONLY unsupplied area: the module has zero set_tooltip_text calls. The play/pause button is icon-only (media-playback-start-symbolic, swaps its icon per state) and has NEITHER a tooltip NOR an accessible name/description; the seek scale has no label/tooltip either. For a keyboard/screen-reader user the bar reads as two nameless controls; the icon swap also means the accessible name should follow the state (play vs. pause). Recommendation (planned item): tooltip + accessible description on _btn_play that follows the state (_("Play")/_("Pause")), a tooltip on _seek_scale (_("Seek position")), and the duration label already exists as text. One small, isolated fix – the rest of the widget inventory is supplied. → FIXED in 0.65.5 (F72): state-following tooltips on _btn_play (_("Play")/_("Pause")), tooltip on _seek_scale (_("Seek position")); three new msgids in pot and de.po.
```

### AUDIT-A11Y-4 – Verdict (F58/5)

- **Module:** –
- **Location:** this audit section
- **Reason:** F58 (5) – summary.

```text
Verdict: the supply side is in good shape for a preview tool – text lives in widgets, tooltips carry full content where the display truncates, settings and toolbar are completely named, and state rides on widget states. ONE finding goes into planned: the media player bar needs tooltips and state-following accessible names for play/pause and seek. Deploy-side check for the release notes: run orca (or any AT-SPI client) over a preview with an image, a text file and an audio file – everything except the player bar should announce sensibly.
```

## Umgebungs-Matrix-Audit (F58)

### AUDIT-ENV-1 – Method (F58)

- **Module:** all eight Python modules
- **Location:** this REFERENCE section (after the Barrierefreiheits-Audit)
- **Reason:** F58 (7) environment matrix – Nemo versions, Python minimum, Wayland vs. X11.

```text
F58 (2026-11-07, audit round WITHOUT code changes): static determination of the supported environment from the code side (API pins, language features, windowing dependencies) plus the tested matrix from INSTALL.md; the runtime matrix cells (older Nemo, older Python distros, Wayland session) are deploy-side checks, listed at the end.
```

### AUDIT-ENV-2 – Nemo and the host API

- **Module:** previewer.py, previewer_select.py
- **Location:** gi.require_version Nemo 3.0, NameAndDescProvider hasattr guard
- **Reason:** F58 (7) – which Nemo versions does the extension support?

```text
The Nemo API pin is require_version('Nemo', '3.0') – the Nemo 3.x GIR that Mint ships since the Cinnamon 3.x era. The provider set is defensive: the NameAndDescProvider base is only added when hasattr(Nemo, 'NameAndDescProvider') – an older Nemo without it still loads the extension (it then simply reports no name/description); the LocationWidgetProvider/ColumnProvider bases are as old as the Nemo-python binding itself. The crowbar and the selection reader walk the widget tree of whatever Nemo builds – no version-specific widget paths (the view scan is structural, not version-pinned), and the reader carries multiple strategies (vtable/ATK/GTK) precisely because the view zoo varies. Tested: Nemo on Linux Mint 22 and Debian 13 (INSTALL.md). Caja (MATE) is NOT supported – the extension targets Nemo only (AUDIT-GTK4-10). Verdict: Nemo 3.x line; concrete older-version cells are a deploy-side check.
```

### AUDIT-ENV-3 – Python minimum

- **Module:** all eight Python modules
- **Location:** language feature scan (syntax floor), stdlib usage
- **Reason:** F58 (7) – the oldest Python that runs the code.

```text
Syntax floor: the code base uses %-formatting throughout – NO f-strings, no walrus, no match statements (the grep hits for "f\"" are the aperture string "f/%.1f" and a variation-selector escape). The newest stdlib features in use: os.scandir (3.5), email.policy (3.3+), sqlite3, subprocess, csv.Sniffer, xml.etree – so the SYNTAX floor is about 3.5. Realistic floor: every distro that ships Nemo 3.x also ships at least Python 3.9 (Debian 11-era), and the tested cells are 3.12 (Mint 22) and 3.13 (Debian 13); gettext/GLib bindings need PyGObject, which the distro pairs anyway. Recommendation for the README/INSTALL: declare "Python 3.8+" (comfortably below every realistic Nemo 3.x distro, far above the syntax floor) and drop the vaguer wording. → DONE in 0.65.5 (F73): INSTALL.md declares "Python 3.8 or newer".
```

### AUDIT-ENV-4 – Wayland vs. X11

- **Module:** all eight Python modules
- **Location:** windowing-API scan (GdkX11, XIDs, screen geometry, draw painters)
- **Reason:** F58 (7) – does anything tie the extension to X11?

```text
Nothing in the extension touches the windowing layer directly: no GdkX11 import, no XID handling (the only "X11" hit is a comment about GTK selection-signal NAMES). Geometry goes through the monitor API (Gdk.Display.get_default().get_primary_monitor() in center_window), which works on both backends; all painting rides the GTK3 draw signal, which is cairo-based and backend-neutral; the crowbar re-parents widgets inside the GTK hierarchy, not windows on the X stack. Caveat: the injection depends on the HOST's widget tree, and the tested sessions are X11 (Cinnamon on Mint 22 and Debian 13) – under Wayland the extension itself has no blocker, but Nemo/Cinnamon runs as XWayland or native; the crowbar being widget-level (not X-window-level) is exactly why it should survive both. Verdict: no X11 dependency; Wayland session is a deploy-side matrix cell (Mint 22 ships an experimental Wayland session).
```

### AUDIT-ENV-5 – Verdict and matrix (F58/7)

- **Module:** –
- **Location:** this audit section
- **Reason:** F58 (7) – the matrix as it stands after the audit.

```text
Matrix after the audit: Nemo 3.x (API pin 3.0, defensive provider guards), Cinnamon/X11 tested on Mint 22 + Debian 13; Python 3.12/3.13 tested, recommendation to declare 3.8+; Wayland: no code blocker (widget-level architecture), runtime cell open. Deploy-side matrix checks for the release: (1) one older-Nemo cell (e.g. Mint 21.x), (2) one Wayland session (Mint 22 experimental), (3) confirm the Python declaration against the oldest distro you care about. No code change required by this audit; the declaration text for README/INSTALL is the only follow-up (documentation item, goes into planned).
```