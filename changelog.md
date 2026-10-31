# Nemo Previewer — Installation

A Nemo file manager extension that docks a preview panel to the right  
side of every Nemo window and renders the currently selected file:  
images (with EXIF orientation), text and source code, Markdown, e-mails,  
e-books (EPUB, FictionBook 2, MOBI), PDF, audio (with player), video,  
folders, and office documents.

Repository: [https://github.com/NBoESFWbVaf/nemo-previewer](https://github.com/NBoESFWbVaf/nemo-previewer)

## Requirements

Tested on Linux Mint 22 and Debian 13 (Trixie) with Cinnamon/Nemo. The  
extension consists of **eight files that**  
**belong together** and must all carry the same version:


| File                        | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `previewer.py`              | Entry point: Nemo integration, panel injection |
| `previewer_panel.py`        | Panel core: dispatch, helpers, config (F12)    |
| `previewer_select.py`       | Selection detection (vtable, GTK, ATK)         |
| `previewer_util.py`         | Helpers and configuration constants            |
| `previewer_toolbar.py`      | Toolbar bar + settings window                  |
| `previewer_render_media.py` | Renderers: images, SVG, audio, video           |
| `previewer_render_docs.py`  | Renderers: PDF, Office                         |
| `previewer_render_text.py`  | Renderers: text, Markdown, EML, e-books, fonts |


**Mandatory packages**

```bash
sudo apt install nemo-python python3-gi git
```

**Optional packages** — each one unlocks additional preview types:

```bash
# PDF preview
sudo apt install gir1.2-poppler-0.18 python3-cairo

# Audio/video preview (GStreamer)
sudo apt install gir1.2-gst-plugins-base-1.0

# Audio output (autoaudiosink) comes from the good plugin set —
# preinstalled on Mint/Cinnamon, optional on minimal Debian
sudo apt install gstreamer1.0-plugins-good

# SVG preview (gdk-pixbuf ships no SVG loader anymore)
sudo apt install gir1.2-rsvg-2.0

# Syntax highlighting in the text preview — same module as the xed
# editor, practically always preinstalled on Mint via xed
sudo apt install gir1.2-gtksource-4

# Sharp office preview (ODT/ODS/ODP, DOCX/XLSX/PPTX, DOC/XLS/PPT):
# converts documents to PDF in the background, once per document
sudo apt install libreoffice-core
```

**All packages at once**

  ```bash
    sudo apt install nemo-python python3-gi git gir1.2-poppler-0.18 python3-cairo gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-good gir1.2-rsvg-2.0 gir1.2-gtksource-4 libreoffice-core
  ```


Everything else runs on Python standard library modules only.

**Debian notes** (verified on Debian 13 "Trixie" with Cinnamon/Nemo)

- There is **no `python-gi` package on Debian** — the Python 3  
GObject bindings are called `python3-gi`. Installing `nemo-python`  
pulls in `python3-gi` and the Nemo GIR bindings automatically
- Cinnamon on Debian does **not** preinstall `nemo-python`. Without  
it, extensions in `~/.local/share/nemo-python/extensions/` are  
silently ignored — the panel never appears
- The SVG package is named `gir1.2-rsvg-2.0` on both Debian and Mint  
(Debian has no `gir1.2-rsvg` alias). PDF (`gir1.2-poppler-0.18`),  
`python3-cairo`, GStreamer, `gir1.2-gtksource-4` and `libreoffice-core`  
carry the same names on both distributions

## Install

### Change directory and clone git
  ```bash
    cd /tmp && \
    git clone https://github.com/NBoESFWbVaf/nemo-previewer.git
  ```

### Create the needed directory and copy all *.py Files to this directory
  ```bash
    mkdir -p ~/.local/share/nemo-python/extensions
    cp /tmp/nemo-previewer/*.py ~/.local/share/nemo-python/extensions/
  ```


1. Restart Nemo:
  ```bash
   nemo -q && nemo
  ```
2. Check the log. Each module reports its version on load:
  ```text
   [previewer] previewer_util 0.31.7 geladen
   [previewer] previewer_select 0.31.7 geladen
   [previewer] previewer_render_media 0.31.7 geladen (...)
   [previewer] previewer_render_docs 0.31.7 geladen (...)
   [previewer] previewer_render_text 0.31.7 geladen (...)
   [previewer] previewer_toolbar 0.31.7 geladen (...)
   [previewer] previewer_panel 0.31.7 geladen (...)
   [previewer] previewer (Einstieg) v0.31.7 bereit
  ```

   Eight lines with the same version number — anything else means an old  
   file is still in the folder.
3. Select a file in Nemo. The panel appears on the right; toggle it with  
**Ctrl+Alt+P** or the button in its header. The divider between the  
file view and the panel is draggable.

## Upgrade

1. Overwrite **all eight files** — they share a version lock, and the  
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

   All eight files must report the same version.

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

Set `NEMO_PREVIEWER_TRACE=1` to log every function call of the  
extension — arguments, return values and exceptions — and  
`NEMO_PREVIEWER_TRACE=line` to log every executed line as well  
(no variable set: no hook, no overhead):

```
nemo -q
NEMO_PREVIEWER_TRACE=1 nemo --no-desktop
```

## Troubleshooting


| Symptom                                           | Cause and fix                                                                                                  |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No `geladen`/`bereit` lines in the log            | `nemo-python` missing or the files are not in `~/.local/share/nemo-python/extensions/`                         |
| Version warning in the log, or different versions | Mixed old/new files in the extension folder — copy **all eight** files again                                   |
| Panel loads but stays empty                       | Watch the terminal; renderers log errors there. A missing preview type usually just needs its optional package |
| Office preview converts over and over             | Old version before 0.3.x — update; the cache failed on `/tmp` being a separate device                          |
| `net usershare` warnings in the log               | Comes from Nemo-Share, not from this extension — harmless                                                      |


The changelog (`changelog.md` in the repository) documents every release.