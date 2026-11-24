# book-workflow

A [Claude Code](https://claude.com/claude-code) skill for writing a book with Claude, from
Markdown sources to print. It is written for Hebrew (right to left) first and works for
left-to-right books as well.

The skill gives Claude two things. One is the method: where the source of truth lives, what
runs after every change, what Claude may fix on its own and what goes to the author as a
proposal, and how to handle the author's edits, an editor's report or a print upload. The other
is a set of small scripts that do the mechanical parts.

## What the method looks like

The manuscript is kept in two forms that always match: one Markdown file per chapter in
`manuscript/`, which the build reads, and one Word file per chapter in `review/`, which the
author opens in their own word processor. When Claude changes the Markdown, the chapter's DOCX
is refreshed. When the author edits a chapter's DOCX and says "check chapter 7", Claude runs
`docx_diff.py`, which reports every changed, added, deleted or re-formatted paragraph as JSON.
Claude merges those edits into the Markdown as written, runs the book's language pass,
rebuilds, commits, and reports what was merged, what was deleted and which proposals need the
author's decision.

Every change runs the same chain: a wording pass that removes phrasing typical of AI writing
(the `humanizer` skill when installed; in the author's own text it fixes only clear cases),
the full book in Markdown with a check for leftover em dashes, the PDF, and the chapter's DOCX.

The author decides once whether language fixes go in directly or are shown first for approval,
and the choice is stored in `book.json`. A change of meaning or fact is always a proposal,
shown with the current and the proposed wording, one at a time. Reports from outside readers,
human or a model such as ChatGPT or Gemini, are split the same way. Decisions are written down
with a date so a later session does not reopen them.

`SKILL.md` is the entry point. The details are in `references/`:

| File | Covers |
|---|---|
| `project-setup.md` | layout, `book.json`, the book's `CLAUDE.md`, the style sheet, the foundation doc, the book map, the handoff |
| `writing-chapters.md` | adapting an article, writing from a raw idea, structure rules, quotations and sources, tone, the quality loop |
| `author-roundtrip.md` | merging the author's DOCX edits, step by step, and the report |
| `external-reviews.md` | prompts for outside critics, applying a language report, a recommendations document for content |
| `sources.md` | source books: text extraction, a summary per chapter, theme collections, quoting safely |
| `production.md` | the print PDF, Hebrew page numbering, black-and-white figures, print-on-demand files, spine and cover |
| `cover.md` | the cover wrap, the front image (your own, or a prompt for Gemini, ChatGPT or another image model), typography in code |
| `publishing.md` | the publishers' round, submission packages, a pen name |
| `office-tools.md` | which word processor the author uses, open-file detection, conversions |

## Whatever word processor the author has

Reading and writing DOCX needs no office suite. `docx_diff.py` reads the file directly and
`md2docx.js` writes it with the npm `docx` package. An office application is needed only to
convert a DOCX to PDF, and `office.py` picks whichever is installed: Microsoft Word (through the
`docx2pdf` package), LibreOffice or WordCraft. PDFs of the book itself come from Chrome.

Before rewriting a chapter's DOCX, `sync_docx.py` checks whether the file is open: the `~$`
owner file Word leaves, the `.~lock` file of LibreOffice and OnlyOffice, and on Linux the process
list for editors that autosave without a lock file (WordCraft). An open file is skipped, so an
autosaving editor never writes an old copy back over a fresh one. A DOCX the author changed
since the last sync is skipped as well, until Claude has merged those edits; the author's file
is then backed up before the fresh one replaces it.

Tested on Linux with LibreOffice, WordCraft and Chrome. The Word, macOS and Windows code paths
follow the same contract but have not been run; issues are welcome.

## Scripts

| Script | Does |
|---|---|
| `init_book.py` | scaffolds a new book: `book.json`, `manuscript/`, `CLAUDE.md`, a style sheet |
| `build_book.py` | joins all chapters into one Markdown file and reports forbidden characters (the em dash by default) by file and line |
| `build_pdf.py` | Markdown to HTML to PDF with Chrome: title page, contents (without page numbers), part pages, figures, page numbers |
| `md2docx.js` | one Markdown file to an RTL or LTR DOCX |
| `sync_docx.py` | regenerates the review DOCX of chosen chapters, skipping files that are open or hold edits not merged yet |
| `docx_diff.py` | read only: what the author changed in a chapter's DOCX, as JSON or readable text |
| `office.py` | detects editors and converters, converts files, tells whether a DOCX is open |
| `extract_text.py` | a source book (PDF, scanned PDF with OCR, EPUB, TXT) to plain text with citable line numbers |
| `make_cover.py` | the print-ready cover wrap (back, spine, front) from `cover.json`, with the spine width from the page count |
| `bookconf.py` | shared by the others: reads `book.json` and lists chapters in book order |

## Requirements

- Python 3.9 or later, and `pip install markdown` for `build_pdf.py`
- Node.js, for `md2docx.js`
- Chrome, Chromium or Edge, for PDFs
- Optional: LibreOffice, Word with `docx2pdf`, or WordCraft, for DOCX to PDF
- For the cover: `pip install pillow`, `pdftoppm` (poppler-utils), Noto Hebrew fonts; Ghostscript
  for a CMYK file

## Install

```bash
git clone https://github.com/yosefco3/claude-book-workflow ~/.claude/skills/book-workflow
cd ~/.claude/skills/book-workflow && npm install
python3 scripts/office.py detect
```

## Start a book

```bash
python3 ~/.claude/skills/book-workflow/scripts/init_book.py ~/books/my-book --title "My Book" --lang he
```

Then open Claude Code in that folder and fill in `CLAUDE.md` and `docs/STYLE.md` with it: the
genre, the reader, the chapter length, how sources are quoted, and the words of yours that must
never be corrected. `examples/sample-book/` is a small Hebrew book that shows the layout and the
markup (a "going deeper" section, a sources section, a figure, a summary page, back matter).
Its cover spec is included but not the front image: put one at
`manuscript/assets/cover-front.png` to build its cover.

Things to say to Claude once the book exists: "turn these articles into a book plan", "write
chapter 5 from this article", "I edited chapter 7, check it", "rebuild the book", "the
editor's report is in this PDF", "prepare the files for the printer".

## Companion skills

Some steps point to skills that are not part of this repository and are used when installed: a
language editor and a grammar guard for Hebrew, a pass that removes machine-writing patterns
(humanizer) and a page-number checker. Without them the references describe the step in
enough detail to do it directly.

## Tests

```bash
cd ~/.claude/skills/book-workflow && python3 -m pytest tests -q
```

The tests build the sample book in a temporary folder, run the full round trip (sync, an
author edit in the DOCX, the diff, the merge), and cover open-file detection with a fake
process table.

## License

MIT
