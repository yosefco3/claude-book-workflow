# The author round-trip

The manuscript is kept in two synced forms: Markdown (`manuscript/`, what the build reads) and
one Word DOCX per chapter (`review/`, where the author edits in their own word processor).
Some authors also use a web Markdown editor, handy on a phone where DOCX is awkward. A change
Claude makes in the Markdown refreshes the DOCX; an edit the author makes in the DOCX comes
back into the Markdown by the procedure below. The job: get the author's edits into the `.md`
faithfully, rebuild everything generated from it, and say exactly what happened.

If the book's `CLAUDE.md` has its own section for this (for example `## chapter-check`) or
names a dedicated skill, follow that; this file is the general procedure.

## Contents
- The editing surfaces
- "I edited chapter N": the procedure
- Judgement calls
- The report
- Decisions marked inside a DOCX

## The editing surfaces

- **Review DOCX**: `review/<name>.docx`, one per chapter, written by `sync_docx.py` from the
  `.md`. A new chapter gets its DOCX on the first sync. The DOCX is outside git.
- **Web editor** (optional): any page where the author edits the Markdown text itself and that
  stores the edited text with a time stamp. Read the stored text, not what the page displays.
- The author may use both for the same chapter. **The later one is the base**: apply all of its
  changes; from the earlier one apply only changes to paragraphs the later one did not rewrite,
  and report the overlap.

## "I edited chapter N": the procedure

1. **Find the chapter.** `python3 $SKILL/scripts/docx_diff.py N --json` (N is the number,
   `Nz` for a summary page, or the `.md` path). No N, or nothing found in N:
   `docx_diff.py --scan` lists every chapter whose DOCX differs from its `.md`. If the change is
   in another chapter, say so ("the change is in chapter 15, not 14") and continue with it only
   if it is clearly the one the author meant.
2. **Check before merging.**
   - `md_dirty` true: the `.md` has uncommitted changes, someone's work is in progress there and
     the diff would show it as the author's deletions. Stop and ask.
   - `open` set: the DOCX is open in an editor. Merge what is on disk and say so; if the author
     says there is unsaved work, wait for it.
   - `docx_stale` true: the `.md` changed after the DOCX was written, so some differences may be
     source changes that never reached the DOCX. Compare with `git log -p` of the `.md` since
     the DOCX time; lines that only undo a later source change are not the author's edits.
   - `tracked_changes`: Word tracked changes are read as accepted. Say so in the report.
3. **Merge into the `.md`, before any sync** (a sync overwrites the DOCX from the `.md`, so the
   edits must land in the `.md` first).
   - Apply the changes from the bottom of the file up, so line numbers above stay valid, and
     anchor each Edit on the `old_raw` text, not on the line number alone.
   - Edit inside the paragraph where `word_diff` shows the change, so markup the author did not
     touch (bold, links, table pipes) stays.
   - `added`: insert after `after_line` (0 = top); restore `**`/`*` from `new_rich`; a DOCX
     bullet `• ` becomes `- `; a DOCX heading `level` becomes `#`/`##`/`###`.
   - `deleted`: delete it, without asking. List it in the report.
   - `minor` (punctuation and spacing): apply; the author typed it. Exception: it breaks a
     style-sheet rule.
   - `format_changes`: apply the bold or italic the author set.
   - Light polish only: typos, spacing, the style sheet's punctuation rules (no em dash).
     The author's words, and phrases the style sheet protects, stay as written.
4. **Verify.** Run `docx_diff.py N` again (the DOCX still holds the author's version). What it
   still lists must be only your light polish, or a change you name in the report as not merged,
   with the reason.
5. **Language pass** on this chapter only, as the book defines it (language editor; the
   wording pass against AI phrasing, which in the author's text fixes only clear cases; any
   further pass the book lists). Language fixes follow `language_fixes` in `book.json`: applied
   and listed, or listed for approval. Changes of meaning or fact are always numbered proposals
   in the report. A reader pass only produces a short list; nothing from it is applied until
   the author approves.
6. **Rebuild** with the chain in SKILL.md, syncing this chapter with
   `sync_docx.py --only N --merged`. Without `--merged` the sync answers HELD: it keeps a hash of
   every DOCX it wrote (`review/.sync-state.json`) and does not overwrite one the author changed
   since. `--merged` copies the author's file to `review/.backup/` and then writes the fresh one;
   a file that is open is still skipped. Use it only for chapters whose edits you just merged:
   any other chapter that comes back HELD holds edits nobody has merged yet, so run this
   procedure for it first. A word processor can also change the file without any edit (a plain
   re-save or an autosave): when `docx_diff.py` finds nothing of the author's in a HELD
   chapter, sync it with `--merged`. `--merged` requires `--only`.
7. **Commit** the chapter in one commit (the `.md`, the book map if its status changed, the
   tracked build files), subject first, for example `Chapter 12 'Title': merge the author's
   corrections`, then push. Approvals of proposals are applied later, in a commit of their own.

## Judgement calls

- **Mass deletion** (the stored editor text is empty, or more than a third of the paragraphs
  come back deleted): stop and ask. That is an accident more often than an edit.
- A paragraph the author rewrote heavily can come back as `deleted` + `added` at the same place.
  Treat it as one rewrite, in the merge and in the report.
- Many DOCX files with the same modification minute and no differences: that was a sync, not
  the author.
- Nothing to merge anywhere: report "no edits from the author in chapter N" and stop. No
  rebuild, no commit.
- The author edited two chapters: run the procedure per chapter, one commit each.

## The report

In the author's language, plainly. Drop the parts that are empty.

```
**Chapter N – <title>**

Merged from the DOCX (or: from the editor): <count>
- <short description, in the author's words>
Deleted:
- <paragraph or sentence, abbreviated>
Not merged: <what and why>

Language pass: <count, and 2–4 notable examples>

Proposals that change meaning (for your decision, one by one):
1. Current: "..." → proposed: "..." (why)

Rebuilt: <commands>; DOCX refreshed; <page count; changed or not>
Open file: "<name>" is open in <editor>. Close it without saving and reopen it.
Commit: <short hash> <subject>, pushed.
```

## Decisions marked inside a DOCX

When you send the author a recommendations document (from an external report, or a list of
proposals), they may answer inside it: "accept", "reject", a note in brackets. Read it with
`python3 $SKILL/scripts/office.py text <file.docx>` (no office suite needed), apply what was
accepted, record what was rejected in the book map so it is not proposed again, and report.
Proposals were easiest to decide in small rounds (about four per question).
