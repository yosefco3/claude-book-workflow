# {title}

<One paragraph: what the book is (genre, subject, reader), and where it stands now: drafting,
polishing, with publishers, at the printer.> Working language: <language>.
Method: the `book-workflow` skill. This file holds what is specific to this book and wins over
the skill.

## Layout
- `manuscript/` – the Markdown the build reads; one folder per part (`00-front`, `01-...`, `99-back`),
  `assets/` for figures, `cover/` for the cover spec. A file starting with `_` is skipped.
- `build/` – generated on every run; never edit it. PDFs are not in git.
- `review/` – one DOCX per chapter for the author; not in git.
- `docs/STYLE.md` – the style sheet. Read it before any edit.
- `features-prompts/book/` – foundation doc, `BOOK_MAP.md`, the one current handoff.

## The manuscript: Markdown and Word, kept in sync
The Markdown in `manuscript/` is what the build reads; the author edits the chapter DOCX files
in `review/`. A change in the Markdown refreshes the chapter's DOCX; an edit in the DOCX is
merged back into the Markdown (`docx_diff.py N`, then the chain below).

## Commands (the rebuild chain, in order, after every change)
1. Wording pass against AI phrasing on the changed text (`humanizer` skill if installed; in
   the author's own text only clear cases)
2. `python3 {skill}/scripts/build_book.py` (check: zero forbidden characters)
3. `python3 {skill}/scripts/build_pdf.py`
4. `python3 {skill}/scripts/sync_docx.py --only N` (after merging the author's edits: `--only N --merged`)
5. <the print build, if any, and what to report: page count, spine>
6. <tests, if any>

## The author's editor
<Word / LibreOffice / WordCraft / OnlyOffice / Google Docs.> If the chapter's DOCX is open:
<"ask to close it, then sync" for autosaving editors; or "write anyway and say: close without
saving and reopen" when `overwrite_open` lists the editor in book.json>.

## Rules for every session
- Edit only `manuscript/` (and the author's DOCX when merging); never `build/`.
- Every change runs the whole rebuild chain. No skipping.
- One chapter at a time; the next one only after the author approves.
- Merging the author's edits: as written, deletions included, light polish only, no questions
  about intent; report what was merged and deleted.
- Language fixes: <applied directly | shown first for approval> (`language_fixes` in
  book.json). Changes of meaning or fact are always proposals, one by one.
- Chapter length: <for example 1,200–1,600 words>. A section over ~6 paragraphs, or a
  paragraph over ~6 sentences, is split with a heading.
- <How sources are quoted: paraphrase in the body, hard quotations in "Sources for this
  chapter"; limits on quotations from copyrighted works.>
- <The author's taste: tone, words that must not be corrected, words to avoid.>
- Never attribute a position to the author before they state it; mark proposals as proposals.
- Decisions marked closed (book map, with a date) are not reopened.
- <Pen name, if any: the real name never appears in book files.>

## Ask or act
- Ask about content, voice, claims and structure, and any wording change that alters meaning.
- Just do: builds, merging the author's edits, moving files, deleting finished working files,
  commits and pushes.
- Never without a request: sending to publishers, putting the book on sale, publishing the full
  text online.

## Merging the author's edits
- DOCX folder: `review/`, named by `review_name` in book.json.
- Protected phrases: <list, or "see the style sheet">.
- Language passes after a merge, in order: <for example: language editor at full depth with the
  style sheet; then a reader pass (a short list, applied only after approval)>.
- Report extras: <for example the print page count>.
- Commit subject: <for example `Chapter 12 'Title': merge the author's corrections`>, then push.
