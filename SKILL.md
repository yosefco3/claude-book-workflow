---
name: book-workflow
description: >
  End-to-end method for writing a book with Claude, tuned for Hebrew (RTL), usable in any
  language. The manuscript is kept in sync as Markdown and as one Word file per chapter that the
  author edits in whatever word processor they have (detected, not assumed). Covers planning, a
  style sheet and chapter map, writing chapters, merging the author's DOCX edits back, the rebuild
  after every change (AI-phrasing pass, full-book Markdown, PDF via Chrome, the chapter's DOCX),
  external reports (human editors, ChatGPT, Gemini), the print-ready cover, print-on-demand files
  and publisher submissions. Use when the user works on a book or manuscript project: "turn my
  articles into a book", "I edited chapter 7, check it", "rebuild the book", "the editor's report
  came back", "make the cover", "files for the printer", "עשיתי שינויים בפרק", "תבדוק תיקונים
  בפרק", "תבנה את הספר", "כתב היד", "דוח עריכה", "כריכה לספר", "להוצאה לאור". Not for a single
  article or post.
---

# book-workflow: a book with Claude, from Markdown to print

A book is a long project with one author, many sessions and many output files. This method
keeps it sane: one source of truth, one rebuild chain that always runs, a clear line between
what Claude fixes and what the author decides, and a written record of every decision so a new
session can pick up where the last one stopped.

`$SKILL` below is this skill's folder (the base directory shown when the skill loads).

## Precedence

1. The book's own `CLAUDE.md` and style sheet (`docs/STYLE.md`) win over this skill. They hold
   the author's taste; this skill holds the method.
2. When the book's `CLAUDE.md` names another skill or its own scripts for a step (for example a
   `## chapter-check` section, or `scripts/build_release.py`), use those for that step.
3. Everything else: this file, then the reference it points to.

## The principles (why the method works)

- **One manuscript, two synced forms** (next section): Markdown for the build, Word for the
  author. Never edit `build/`; edits made there vanish on the next build.
- **Every change runs the whole rebuild chain** (below), with no skipping. The author checks
  your work in the DOCX and the PDF. A stale file makes a fix look undone, and the author then
  loses trust in every other fix.
- **The author decides content.** A change of meaning, fact, claim or structure is always a
  proposal: current wording → proposed wording, one at a time, for the author to accept or
  reject.
- **Language fixes go in the way the author chose.** Grammar, spelling, punctuation and
  consistency fixes are either applied directly or shown first for approval. Ask the author
  once, when the book is set up, and record the answer in `book.json` as `language_fixes`:
  `"apply"` or `"propose"`. A new book has no value yet: ask, and until the author answers treat
  it as `"propose"`.
- **The author's edits are merged as written**, deletions included, with light polish only.
  Don't ask whether a deletion was intended: the author's file is binding. Report what was
  merged and what was deleted so they can catch a slip themselves.
- **The author's text stays the author's.** A chapter can start from anything: an article,
  notes, a draft, a raw idea. Whatever the author already wrote, don't thin it, reorder it or
  "improve" it on your own initiative.
- **Don't put words in the author's mouth.** Never present a position as theirs before they
  said it. Label your own suggestions ("my proposal", "for your decision").
- **One chapter at a time.** Finish it, get the author's approval, then the next.
- **Decisions are written down with a date** (in the book map or the foundation doc) and are
  not reopened unless the author reopens them.

## The manuscript: Markdown and Word, kept in sync

The manuscript exists in two forms that always match:

- **Markdown**, one file per chapter in `manuscript/` (a folder per part). The build reads it,
  git tracks it, and Claude edits it.
- **Word**, one DOCX per chapter in `review/`. The author reads and edits there, in their own
  word processor (see office-tools.md for how open files are detected).

An edit in either one reaches the other:
- a change Claude makes in the Markdown refreshes the chapter's DOCX (`sync_docx.py`, step 4 of
  the rebuild chain);
- an edit the author makes in the DOCX ("I edited chapter N", "check my corrections") is found
  with `docx_diff.py`, merged into the Markdown as written, and then the chain runs. The full
  procedure, its judgement calls and the report: [author-roundtrip.md](references/author-roundtrip.md).

`sync_docx.py` guards the author's files: a DOCX the author changed since the last sync is
HELD, not overwritten, until its edits are merged and the sync runs with `--merged` (which backs
up the author's file to `review/.backup/` first). A DOCX open in an editor is skipped.

## Project layout

```
book.json            title, author (pen name), folders, naming, fonts, labels, language_fixes
CLAUDE.md            what the book is, commands, standing rules, ask-or-act
docs/STYLE.md        the style sheet (spelling decisions, punctuation, author's words)
manuscript/          the source: NN-part/NN-chapter.md, assets/, cover/
build/               generated, overwritten every run
review/              one DOCX per chapter for the author (outside git)
sources/             source books the book draws on, with summaries (outside git; see sources.md)
features-prompts/book/  foundation doc, book map, the single current handoff
```

New book: `python3 $SKILL/scripts/init_book.py <dir> --title "..." [--author "..."] [--lang he|en]`,
then fill in `CLAUDE.md` and the style sheet with the author. Details, the `book.json` keys and
the planning documents: [references/project-setup.md](references/project-setup.md).

## The phases

| Phase | When | Read |
|---|---|---|
| Plan | new book, or a structural change (parts, order, omissions) | [project-setup.md](references/project-setup.md) |
| Write a chapter | from an article, notes or a raw idea | [writing-chapters.md](references/writing-chapters.md) |
| Language and critic loop | after every new or heavily edited chapter | [writing-chapters.md](references/writing-chapters.md#the-quality-loop) |
| Author round-trip | "I edited chapter N", "check my corrections" | [author-roundtrip.md](references/author-roundtrip.md) |
| External report | a report arrives from a human editor or reader, or from a model such as ChatGPT or Gemini; or the author wants a prompt for one | [external-reviews.md](references/external-reviews.md) |
| Source books | the book draws on other books: extract text, summarise per chapter, quote safely | [sources.md](references/sources.md) |
| Print files | PDF for print, page count, print-on-demand | [production.md](references/production.md) |
| Cover | the full wrap (back, spine, front) for print, the front image | [cover.md](references/cover.md) |
| Publishers | submission packages, the publishing plan | [publishing.md](references/publishing.md) |
| Office tools | converting, "is the file open?", which editor the author uses | [office-tools.md](references/office-tools.md) |

## The rebuild chain

After every change to the source, run from the book root, in order:

1. **Wording pass against AI phrasing** on the text that changed: the `humanizer` skill if it
   is installed, otherwise the list in [writing-chapters.md](references/writing-chapters.md#tone-and-ai-tells).
   Wording only; in text the author wrote, only clear cases (a repetition, a staged question, a
   closing line that restates the paragraph), keeping the author's voice. In fiction, a line
   that explains an image, or a narrator's announced insight, is not a clear case: it is flagged and
   may get a rewrite (a lecture into an image), as `hebrew-short-story` pass 4 and its "Rewrites" section say.
   Changes of meaning go to the report as proposals. Fixes follow `language_fixes`: with `apply` they go in; with
   `propose` they are listed in the report and the chain continues without them. If
   `book.json` has no `language_fixes` yet, ask the author once and record the answer.
2. `python3 $SKILL/scripts/build_book.py`: the full book as one Markdown file. Read its output:
   it lists forbidden characters (the em dash by default) with file and line. The book has zero.
3. `python3 $SKILL/scripts/build_pdf.py`: the PDF (Chrome headless).
4. `python3 $SKILL/scripts/sync_docx.py --only N`: the chapter's DOCX for the author; after
   merging the author's edits, `--only N --merged`. Exit 2 leaves the file untouched. BLOCKED:
   it is open in an editor; tell the author to close it, then run again. HELD: the author
   changed it since the last sync; merge those edits first ([author-roundtrip.md](references/author-roundtrip.md)).
   If `docx_diff.py N` then shows nothing of the author's, the editor only re-saved the file:
   run with `--merged`.
   Never overwrite a file open in an editor that autosaves; `--force` only when the author asks.
5. The print build, if the book has one (see production.md). Report the page count; if it
   changed, the spine width and the cover change too.
6. The book's tests, if any.
7. Commit only the files this change touched (by name, never `git add -A`), subject first in
   the book's language, then push.

If the book's `CLAUDE.md` lists its own build commands, run those instead, in its order.

## Scripts

| Script | Does |
|---|---|
| `init_book.py` | scaffold a new book (book.json, manuscript, CLAUDE.md, style sheet) |
| `build_book.py` | full-book Markdown, forbidden-character check, guard against hand-edited build output |
| `build_pdf.py` | Markdown → HTML → PDF with Chrome: title page, contents, part pages, figures, folios |
| `md2docx.js` | one Markdown file → RTL (or LTR) DOCX, no office suite needed (npm `docx`) |
| `sync_docx.py` | regenerate the review DOCX of chosen chapters; skips files that are open or hold unmerged edits |
| `docx_diff.py` | read-only: what the author changed in a chapter's DOCX, as JSON for precise merging |
| `office.py` | detect installed editors and converters, convert files, tell whether a DOCX is open |
| `extract_text.py` | a source book (PDF, scanned PDF with OCR, EPUB, TXT) to citable plain text in `.work/texts/` |
| `make_cover.py` | the cover wrap from `manuscript/cover/cover.json`, spine width from the page count (`cover_geometry.py`) |
| `bookconf.py` | shared: reads book.json and lists chapters in book order |

Setup once: `npm install` in `$SKILL` (for `md2docx.js`), `pip install markdown` (for
`build_pdf.py`), and Chrome or Chromium for PDFs. The cover also needs Pillow, `pdftoppm`
(poppler-utils) and Noto Hebrew fonts, and Ghostscript for CMYK. `python3 $SKILL/scripts/office.py detect`
shows what the machine has.

## Ask or act

- **Ask** about content, voice, claims and structure (what goes in, what goes out, where a
  chapter sits), and about any wording change that alters meaning.
- **Just do** builds, merges of the author's edits, file moves, deleting finished working
  files, commits and pushes.
- **Never without an explicit request:** sending anything to a publisher or anyone else,
  putting the book up for sale, publishing full text online.

## Reporting to the author

Write in the author's language, plainly. Name the chapter (number and title) first. Say what
was merged, what was deleted, what was fixed in the language pass (a count and a few examples),
the proposals waiting for a decision (one by one), what was rebuilt, the page count, any DOCX
that was open, and the commit. Never end with only "tests pass": say what ran.
