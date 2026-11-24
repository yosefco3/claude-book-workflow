# Office tools: whatever the author has

The method needs almost no office suite. Reading a DOCX (`docx_diff.py`, `office.py text`) is
plain zip and XML, and writing one (`md2docx.js`) uses the npm `docx` package. PDFs come from
Chrome. An office app is needed only to convert a DOCX to PDF (for submission packages) and,
as a fallback, SVG to PNG. The author edits in whatever they already use.

```bash
python3 $SKILL/scripts/office.py detect            # editors and converters on this machine
python3 $SKILL/scripts/office.py is-open file.docx # exit 1 and the reason if it is open
python3 $SKILL/scripts/office.py convert file.docx --to pdf   # best available tool
python3 $SKILL/scripts/office.py text file.docx    # plain text, tracked changes accepted
```

## The author's editor

Ask once which editor the author uses and write it in the book's `CLAUDE.md`. It decides how
an open file is detected and what to tell the author after a rebuild.

| Editor | How an open file shows | After a rebuild rewrote an open file |
|---|---|---|
| Microsoft Word (Windows) | `~$` owner file; Windows also locks the file, so the write fails | close it, then run the sync again |
| Microsoft Word (macOS) | `~$` owner file | close without saving, reopen |
| LibreOffice | `.~lock.<name>#` next to the file | close without saving, reopen |
| OnlyOffice | a lock file in most versions (checked like the above) | close without saving, reopen |
| WordCraft | no lock file, and it autosaves; found by its process (Linux) | never overwrite: ask to close, then sync |
| Google Docs | not on disk | the author downloads the DOCX into `review/` after editing; upload the fresh one after a sync |
| Apple Pages | no lock file | export to DOCX into `review/`; treat as Google Docs |

Rules:
- `sync_docx.py` skips any DOCX that looks open (BLOCKED) and exits 2. Tell the author to close
  it and run again. `--force` only when the author asks.
- It also skips a DOCX the author changed since the last sync (HELD), whatever the editor, and
  writes every file under a temporary name first, so a failed build leaves the old file whole.
  Details in author-roundtrip.md, step 6.
- An editor that autosaves (WordCraft, and Word with AutoSave on a synced folder) will write
  its old copy back over a fresh sync. Never overwrite a file open in one.
- With lock-file editors that do not autosave, a book may choose to write anyway and warn: list
  them in `book.json` as `"overwrite_open": ["libreoffice"]`. The author then closes the file
  without saving and reopens it.
- Other autosaving editors without lock files can be watched by process name on Linux:
  `BOOK_EDITOR_PROCS=wordcraft,myeditor`.
- What open-file detection sees: on Linux, the lock files plus a process scan for the editors in
  `BOOK_EDITOR_PROCS`; on Windows, the lock files plus a test for an exclusive lock; on macOS,
  the lock files only, so an editor there that leaves no lock file is not detected. Ask the
  author to close the chapter before a sync.
- Tracked changes in Word are read as accepted by `docx_diff.py`; say so in the report.
  Comments in the DOCX are not read; ask the author to write in the text instead.

## Conversions

| From → to | Preference (first one installed wins) | Override |
|---|---|---|
| DOCX → PDF | Word (via the `docx2pdf` package, Windows/macOS) → LibreOffice → `wordcraft-cli` | `BOOK_OFFICE=word\|libreoffice\|wordcraft` |
| DOCX → text | built in, always available | |
| SVG → PNG | `rsvg-convert` → Inkscape → `cairosvg` → LibreOffice → Chrome | |
| HTML → PDF | Chrome / Chromium / Edge | `BOOK_CHROME=/path/to/chrome` |

Notes from use:
- A DOCX-to-PDF conversion can differ between tools (one tested editor dropped the bold of
  Hebrew headings and loosened the line spacing). For files that go to publishers, look at the
  PDF before sending, and pin the tool that renders it right with `BOOK_OFFICE`.
- LibreOffice is run with a private temporary profile, so an open LibreOffice window does not
  block a headless conversion.
- There is no pandoc requirement anywhere.
- `md2docx.js` writes headings, paragraphs, bold and italic, bullet lists, quotations, figures
  (PNG) and page breaks. Tables and numbered lists come out as plain paragraphs with their
  Markdown text, and `docx_diff.py` compares them as text. Footnotes are not supported.

Tested on Linux with LibreOffice, WordCraft and Chrome. The Word, macOS and Windows paths are
written to the same contract but untested; report problems.
