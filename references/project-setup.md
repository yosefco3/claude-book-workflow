# Project setup and planning

## Contents
- Scaffolding a book
- book.json keys
- The book's CLAUDE.md
- The style sheet
- Planning documents: foundation doc, book map, handoff
- Raw material
- Git and housekeeping
- Privacy

## Scaffolding a book

```bash
python3 $SKILL/scripts/init_book.py ~/books/my-book --title "My Book" --author "Pen Name" --lang he
cd ~/books/my-book && git init
python3 $SKILL/scripts/office.py detect     # what this machine has for DOCX and PDF
```

`init_book.py` writes `book.json`, `manuscript/00-front/01-intro.md`, `manuscript/assets/`,
`.gitignore`, `CLAUDE.md` (from `templates/CLAUDE.md`) and `docs/STYLE.md` (from the style
template for the language). Then sit with the author and fill in `CLAUDE.md`: what the book is,
its genre, who the reader is, the author's standing rules, which word processor they edit in,
and whether language fixes go in directly or are shown first (`language_fixes` in
`book.json`).

## book.json keys

| Key | Default | Meaning |
|---|---|---|
| `title`, `subtitle`, `author` | "" | printed on the title page; `author` is the pen name if there is one |
| `lang`, `dir` | `he`, `rtl` | HTML language and direction; `dir` also sets the DOCX direction |
| `manuscript_dir`, `build_dir`, `review_dir` | `manuscript`, `build`, `review` | folders |
| `output_name` | `book` | `build/<output_name>.md` and `.pdf` |
| `review_name` | `פרק {n} - {title}.docx` | DOCX name for numbered chapters (`{n}`, `{title}`, `{key}`, `{stem}`) |
| `review_name_unnumbered` | `{title}.docx` | DOCX name for summary pages and back matter |
| `unnumbered_parts` | `[]` | part folders whose chapters carry no number (back matter) |
| `parts` | `{}` | display names of parts; a part listed here gets a part page in the PDF |
| `forbidden_chars` | `["—"]` | characters the build reports with file and line |
| `fonts` | Noto Serif / Sans Hebrew | body and heading fonts (PDF and DOCX) |
| `page_size` | `A5` | default PDF size: `A5`, `A4`, `15x22`, or `<W>x<H>mm` |
| `special_headings` | `להעמקה`, `מקורות לפרק זה` | `## ` headings that open a "going deeper" block and the sources block |
| `labels` | Hebrew | `chapter`, `contents`, `draft` words used by the PDF |
| `copyright` | `[]` | lines of the copyright page, printed only with `build_pdf.py --release` |
| `overwrite_open` | `[]` | editors whose open files `sync_docx.py` may still overwrite (for example `["libreoffice"]`) |
| `language_fixes` | `propose` | how language corrections go in: `apply` (directly, then listed in the report) or `propose` (shown first, applied after approval). Ask the author at setup |

File names: `NN-slug.md` is chapter NN; `NNz-slug.md` is a summary page after chapter NN
(unnumbered); a leading `_` keeps a file out of every build (notes, drafts). Part folders sort
by name (`00-front`, `01-...`, `99-back`). The chapter title is the file's first `# ` line.

Renumbering (a chapter inserted in the middle) touches file names, figure names, the DOCX names
in `review/`, cross-references in the text ("in chapter 12"), the book map and any per-chapter
lists in scripts. Do it in one commit, and add a dated note at the top of the book map saying
that chapter numbers in older notes refer to the old numbering.

## The book's CLAUDE.md

Every session reads it, so it carries the rules the author should never have to repeat. Start
from `templates/CLAUDE.md`. Keep in it:

- one paragraph on what the book is and where it stands (drafting, polishing, at publishers);
- the layout and the commands (the rebuild chain, in order);
- standing rules, each one line: the author's taste ("no superlatives", "this word is the
  author's, don't correct it"), the chapter length, how sources are quoted;
- ask-or-act: what to ask about and what to just do;
- where things live: style sheet, book map, the current handoff;
- a section for merging the author's edits (DOCX folder, naming, protected phrases, which
  language passes run, report extras such as the page count).

Background (history of decisions, the publishing plan) goes in the book map or in memory, not in
`CLAUDE.md`. When the author has to repeat a rule, it goes into `CLAUDE.md`.

## The style sheet

`docs/STYLE.md` records every spelling and usage decision once, so all chapters agree: spelling
variants chosen (for Hebrew: full or defective spelling, specific words), transliteration of
foreign names, punctuation rules, dashes, numbers, how to refer to other chapters, and a list of
the author's own words and idioms that must not be "corrected". Read it before any edit. When a
report or a pass settles a new spelling question, add the decision there with the date.

## Planning documents

Keep them in `features-prompts/book/` (or wherever the book's `CLAUDE.md` says).

**Foundation doc (`_PROGRESS.md`).** Written once at the start, updated rarely:
- summary and goal (what the finished book is, for whom; a commercial aim if there is one);
- the vision: what the book argues as a whole, so each chapter can be checked against it
  ("how does this chapter serve the book?"); a chapter that does not serve it moves to an
  appendix or out;
- requirements: structure (parts from introduction to depth, no needless duplicates, every
  term explained at first use, an introduction for each thinker or topic), language (no AI
  tells, consistent spelling, the author's voice kept), production (front and back matter,
  figures, formats);
- division of labour: what Claude does (all text work, figures, builds, drafts of blurbs and
  letters) and what only the author can do (decisions, approving each chapter's voice, a human
  proofreader before print, rights for long quotations, the publishing route, the cover
  designer if any, marketing);
- decisions with dates; open questions with your recommendation, waiting for the author;
- an acceptance test the author can run (the finished book has every chapter, a valid table
  of contents, zero forbidden characters, no leftover web phrasing such as "on this site").

**Book map (`BOOK_MAP.md`).** The working map: parts and chapters in order, each with its
source (article file), status (drafted / with author / approved ✅ with date) and notes; the
omissions list with reasons; renumbering notes; cross-cutting tasks (terminology to unify,
duplicates to resolve, figures to redraw, rights to check). When the author approves a chapter,
mark it here with the date.

**Handoff (`HANDOFF-<date>.md`).** One file only: where things stand and what comes next, for
the next session. A new handoff replaces the old one (`git rm` the previous).

## Raw material

When the book grows out of existing writing (a blog, a site, notes), first collect everything
into `articles/` as Markdown with metadata (title, URL, date, word count) and write an
`articles/_INDEX.md`. Then read all of it before proposing a structure (in parallel subagents
for a large corpus, each returning a structured extract: topics, key claims, overlaps), map
every article to a chapter, a merge, an appendix or an omission, and let the author decide the
map. Strong ideas from an omitted article can be saved as a paragraph elsewhere.

## Git and housekeeping

- Commit each finished unit (a chapter, a merge, a report applied) on its own, with the subject
  first in the book's language, and push.
- Track the source, the scripts, the docs and the full-book Markdown in `build/` (handy for
  diffs). Keep PDFs, the review DOCX files, finished print files and submission packages out of
  git; they are rebuilt from the source.
- Lean structure: working files that served their purpose (diffs, partial PDFs, raw mapping
  notes) are deleted; git keeps their history.

## Privacy

If the book comes out under a pen name, the real name never appears in book files, metadata,
title pages or file names, and identifying details about the author are kept to what the book
needs. Personal contact details for submission letters live in one file outside git.
