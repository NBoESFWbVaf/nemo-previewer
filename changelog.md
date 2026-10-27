# Nemo Previewer — Installation

A Nemo file manager extension that docks a preview panel to the right  
side of every Nemo window and renders the currently selected file:  
images (with EXIF orientation), text and source code, Markdown, e-mails,  
e-books (EPUB, FictionBook 2, MOBI), PDF, audio (with player), video,  
folders, and office documents.

Repository: [https://github.com/NBoESFWbVaf/nemo-previewer](https://github.com/NBoESFWbVaf/nemo-previewer)

## Requirements

Tested on Linux Mint 22. The extension consists of **four files that**  
**belong together** and must all carry the same version:


| File                  | Purpose                                        |
| --------------------- | ---------------------------------------------- |
| `previewer.py`        | Entry point: Nemo integration, panel injection |
| `previewer_panel.py`  | The preview panel and all renderers            |
| `previewer_select.py` | Selection detection (vtable, GTK, ATK)         |
| `previewer_util.py`   | Helpers and configuration constants            |


**Mandatory packages**

```bash
sudo apt install nemo-python python3-gi
```

**Optional packages** — each one unlocks additional preview types:

```bash
# PDF preview
sudo apt install gir1.2-poppler-0.18 python3-cairo

# Audio/video preview (GStreamer)
sudo apt install gir1.2-gst-plugins-base-1.0

# SVG preview (gdk-pixbuf ships no SVG loader anymore)
sudo apt install gir1.2-rsvg

# Sharp office preview (ODT/ODS/ODP, DOCX/XLSX/PPTX):
# converts documents to PDF in the background, once per document
sudo apt install libreoffice-core
```

Everything else runs on Python standard library modules only.

## Install

1. Copy **all four files** into the Nemo extension folder:
  ```bash
   mkdir -p ~/.local/share/nemo-python/extensions
   cp previewer.py previewer_panel.py previewer_select.py previewer_util.py \
      ~/.local/share/nemo-python/extensions/
  ```
2. Restart Nemo:
  ```bash
   nemo -q && nemo
  ```
3. Check the log. Each module reports its version on load:
  ```text
   [previewer] previewer_util 0.3.1 geladen
   [previewer] previewer_panel 0.3.1 geladen (...)
   [previewer] previewer_select 0.3.1 geladen
   [previewer] previewer (Einstieg) v0.3.1 bereit
  ```

   Four lines with the same version number — anything else means an old  
   file is still in the folder.
4. Select a file in Nemo. The panel appears on the right; toggle it with  
 **Ctrl+Alt+P** or the button in its header. The divider between the  
 file view and the panel is draggable.

## Upgrade

1. Overwrite **all four files** — they share a version lock, and the  
 entry point warns in the log about version mismatches.
2. Remove stale bytecode caches, then restart Nemo:
  ```bash
   rm -rf ~/.local/share/nemo-python/extensions/__pycache__
   nemo -q && nemo
  ```
3. Verify the copy is complete before restarting:
  ```bash
   wc -l ~/.local/share/nemo-python/extensions/*.py
   grep -H PREVIEWER_VERSION ~/.local/share/nemo-python/extensions/*.py
  ```

   All four files must report the same version.

## Uninstall

```bash
rm ~/.local/share/nemo-python/extensions/previewer*.py
rm -rf ~/.local/share/nemo-python/extensions/__pycache__
rm -rf ~/.cache/previewer      # optional: office preview cache
nemo -q && nemo
```

## Debugging

For debugging, close your filebrowser and start it again over terminal.

```
nemo -q && nemo --no-desktop
```

## Troubleshooting


| Symptom                                           | Cause and fix                                                                                                  |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No `geladen`/`bereit` lines in the log            | `nemo-python` missing or the files are not in `~/.local/share/nemo-python/extensions/`                         |
| Version warning in the log, or different versions | Mixed old/new files in the extension folder — copy **all four** files again                                    |
| Panel loads but stays empty                       | Watch the terminal; renderers log errors there. A missing preview type usually just needs its optional package |
| Office preview converts over and over             | Old version before 0.3.x — update; the cache failed on `/tmp` being a separate device                          |
| `net usershare` warnings in the log               | Comes from Nemo-Share, not from this extension — harmless                                                      |


The changelog (`changelog.md` in the repository) documents every release.