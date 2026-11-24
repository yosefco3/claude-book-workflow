# Source books

Some books are built on other books: a thinker's works, a series, a classic text. This method
turns those sources into something Claude can work from without re-reading hundreds of pages
each session, and keeps quotations accurate and few.

## Layout

```
sources/                    the source files (subfolders per series or author are fine)
  summaries/
    STATE.md                one line per book: file, summary path, status
    NN-name.md              one summary per book, from templates/source-summary.md
  themes/
    <theme>.md              optional: passages from several books on one theme
.work/texts/<name>.txt      extracted text, one per source (generated)
```

Accepted formats: PDF with a text layer, scanned PDF (OCR), EPUB, TXT. Source files are
copyrighted: do not commit them. `init_book.py` adds `sources/` and `.work/` to `.gitignore`;
for an older book, add the two lines by hand. (The summaries live under `sources/`, so they stay
local too. Keep a private backup if they matter.)

## 1. Extract the text

```
python3 $SKILL/scripts/extract_text.py sources/<file> [-o out.txt] [--ocr]
```

The output goes to `.work/texts/<stem>.txt` under the book root. Lines wrap at about 100
characters, so `<stem>.txt:812` is a stable citation.

- PDF: `pdftotext -layout`. If almost nothing comes out, or with `--ocr`, the script runs
  `pdftoppm` and `tesseract` (language from `lang` in `book.json`: Hebrew gives `heb+eng`,
  anything else `eng`) and writes `=== page N ===` markers.
- EPUB: the spine order of the OPF file, headings kept as `#`, `##`, `###`.
- TXT and MD: copied and wrapped.

A missing tool ends with exit 2 and names the package to install (`poppler-utils`,
`tesseract-ocr`). Check an OCR result by reading a few pages before relying on it.

## 2. Summarise each book

One summary per book in `sources/summaries/NN-name.md`, from
[templates/source-summary.md](../templates/source-summary.md).

1. Read the book once, in order, in blocks of about 1200 lines of the extracted text.
2. Right after each block, write the section of each chapter that ended in it. Do not wait for
   the end of the book; a long book does not fit in memory.
3. Per chapter:
   - a narrative paraphrase, 400 to 900 words, in the chapter's own order;
   - the key exchanges or steps of the argument, paraphrased;
   - at most one or two short quotes (about 20 words), each with its location
     (`file:line`, or the page for scanned books);
   - the insight, in a sentence or two;
   - a list of concepts with a one-line definition.
4. At the end of the book: a synthesis, and an alphabetical glossary of concepts.
5. Keep `sources/summaries/STATE.md` current: each book, its summary file and its status
   (not started, reading, done). A new session starts there.

## 3. Theme collections (optional)

When a theme runs through several books, collect it in `sources/themes/<theme>.md`: short
passages or paraphrases, each with the book and the location. A theme file is a finding aid,
not a chapter.

## 4. Using sources when writing

- Work from the summaries and theme files, not from memory of the book.
- The body of a chapter is paraphrase with few short quotes. Default: 3 to 5 quotes per
  chapter; the book's `CLAUDE.md` can set another number.
- Verify every quote against `.work/texts/` before it goes in: search for the exact words and
  check the location. A quote from a summary alone is not verified.
- Longer quotes and full references go to the chapter's "Sources for this chapter" section
  (the heading is `special_headings.sources` in `book.json`): book title, chapter, location.
- Never retell a passage in its own order. Take the idea and build it into the chapter's
  argument.
- Books unrelated to the main theme are summarised on their own. Do not link them to the book's
  theme unless the author asks.
- The author decides what a source means for the book. Offer a reading as a proposal.
