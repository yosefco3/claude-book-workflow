# book-workflow

A [Claude Code](https://claude.com/claude-code) skill that helps you write a book with Claude,
from research to the cover and the print layout. It is written for Hebrew (right to left) first
and works for left-to-right books as well.

The skill gives Claude a method (where the source of truth lives, what runs after every change,
what Claude may fix on its own and what goes to the author as a proposal) and a set of small
scripts for the mechanical parts. Here is what it does, stage by stage.

## 1. Research: source books and summaries

Put the books you draw on (PDF, scanned PDF, EPUB or text) in a `sources/` folder inside the
book. Claude extracts their text with line numbers (`extract_text.py`, with OCR for scans),
summarises each book chapter by chapter (the ideas in paraphrase, the concepts, one or two short
quotations with their exact location) and keeps a list of what has been summarised. On request
it also gathers passages on one theme from several books into a single file. The books
themselves stay out of git.

## 2. Planning the book

Claude turns your articles, notes or ideas into a book plan: parts, chapter order, what goes in
and what stays out. It sets up the project (`init_book.py`), a style sheet with your spelling
and punctuation choices and the words of yours that must never be corrected, and a book map
where every decision is written down with a date, so a later session does not reopen it.

## 3. Writing chapters

A chapter can start from an article, notes or a raw idea. Text you already wrote is not thinned,
reordered or "improved" on Claude's own initiative. The body is written in plain language and
paraphrase, with only a few short quotations, each checked against the source text; the heavier
quotations and references go to a "Sources for this chapter" section. Every change then goes
through a wording pass that removes phrasing typical of AI writing (the `humanizer` skill when
installed).

## 4. Your edits in Word

The manuscript is kept in two forms that always match: one Markdown file per chapter, which the
build reads, and one Word file per chapter in `review/`, which you open in your own word
processor. You edit there and say "I edited chapter 7, check it". Claude finds every changed,
added, deleted or re-formatted paragraph (`docx_diff.py`), merges it into the book as written,
rebuilds and reports what was merged and what was deleted. A Word file that is open, or that
holds edits not merged yet, is never overwritten.

## 5. Editing and outside reviews

You decide once whether language fixes go in directly or are shown to you first. A change of
meaning or fact is always a proposal, the current wording next to the proposed one, for you to
accept or reject one at a time. Reports from an editor or a reader, human or a model such as
ChatGPT or Gemini, are split the same way. Claude also writes the prompt for an outside critic.

## 6. Layout and print

After every change Claude rebuilds the whole book in Markdown (with a check for leftover em
dashes), the PDF through Chrome (title page, contents, part pages, figures, page numbers that
follow Hebrew conventions) and the chapter's Word file. For print it prepares the interior at
the trim size, checks figures for a black-and-white interior and reports the page count.

## 7. Cover

The full print wrap (back, spine and front) is built in code from `cover.json`, with the spine
width taken from the page count, so a new page count gives a new cover. The front image is
yours, or Claude writes a prompt for Gemini, ChatGPT or another image generator, or uses an image
tool the session has. A CMYK version is made for the printer.

## 8. Publishers and print-on-demand

Claude prepares submission packages for publishers and the files a print-on-demand service
asks for. Nothing is sent to anyone, put on sale or published online without your request.

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
