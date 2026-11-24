# External reviews: editors, critics, readers

Outside eyes find what the author and Claude both miss: a human editor or proofreader, a
reader, or another model the author asks (ChatGPT, Gemini and the like, usually with a prompt
Claude writes). The method separates language corrections, which go in the way the author chose
(`language_fixes` in `book.json`), from what only the author decides (content, facts,
structure).

## Contents
- Writing the prompt for an outside critic
- Handling a report
- The language part: a replacement script
- The content part: a recommendations document
- A reader pass
- Automatic style passes over the whole book

## Writing the prompt for an outside critic

When the author asks for a prompt to give another model or a human reader:

- **State the genre.** For reflective non-fiction or personal thought, testimony and personal
  experience are legitimate; the critic must not ask for proof of an experience. Distinguish
  three kinds of statement: testimony (not challenged), interpretation of a source (checked for
  fidelity to the source), facts (checked for accuracy).
- **Language editing comes first and in full**: a table of original → corrected → type, every
  finding, not a sample. This is the part the author wants most.
- Then clarity, structure, argument order, consistency, tone, accuracy of sources.
- No numeric scores.
- Say which chapters or pages, and the format of the answer (numbered items, with the chapter
  and the exact original wording, so each one can be located without page numbers).

## Handling a report

1. Read the whole report (a PDF in page ranges).
2. Split it: language corrections / content and fact comments / source checks.
3. Language: with `language_fixes: "apply"`, apply directly (below); with `"propose"`, list
   the corrections for the author first (a table of original → corrected, in the
   recommendations document) and apply the approved ones with the script below. Content and
   facts: a recommendations document for the author. If the author sets an order for several reports ("first the language from the PDF,
   then the comments in chat"), follow it.
4. Rebuild, commit, and report what was applied and what waits for decisions.
5. Record new spelling decisions in the style sheet and the report's outcome in the book map.

If the author says "apply all the corrections", apply them all, including ones you would have
kept, and list those exceptions in the book map for the author to glance over.

## The language part: a replacement script

Apply language corrections with a small script of literal replacements, each checked to match
exactly once in the manuscript, so nothing lands in the wrong place:

```python
import pathlib, sys
FIXES = [  # (original wording, corrected wording)
    ("the original phrase", "the corrected phrase"),
]
files = sorted(pathlib.Path("manuscript").rglob("*.md"))
texts = {f: f.read_text(encoding="utf-8") for f in files}
for old, new in FIXES:
    hits = [f for f, t in texts.items() if t.count(old)]
    total = sum(texts[f].count(old) for f in hits)
    if total != 1:
        sys.exit(f"{total} matches for {old!r}: widen the context")
    texts[hits[0]] = texts[hits[0]].replace(old, new)
for f, t in texts.items():
    f.write_text(t, encoding="utf-8")
```

Locate by the original wording, not by the report's page numbers. Skip suggestions that are
style preferences rather than errors when they touch words the style sheet marks as the
author's, and list them. Never change meaning in this step.

## The content part: a recommendations document

For each content or fact comment, write one entry:
- the comment, in one line, with the chapter;
- your assessment, sorted into **accept** (with the exact replacement wording ready),
  **for your decision** (both readings, briefly), or **reject** (why);
- the current wording and the proposed wording.

Write it as Markdown, convert it to DOCX for the author (`md2docx.js`), and walk through the
decisions with the author one at a time or in small rounds. The author may also mark decisions
in the DOCX; see author-roundtrip.md. Apply accepted items in their own commit. After a round
that changed many claims, read the affected chapters again for internal contradictions the
fixes may have created.

## A reader pass

A friendly reader (or a model playing one) gives a short list of points: where they got lost,
where it dragged, what was unclear. Nothing from it is applied until the author approves each
point.

## Automatic style passes over the whole book

A pass over all chapters (for AI tells, wording, consistency) can run in parallel subagents, one
part each. Rule for every such pass: wording only; a sentence may go only if it repeats its
neighbour; meaning and fact changes are listed at the end for the author. Don't touch
quotations, headings, sources sections, scripts of guided exercises, bold labels in summaries,
the afterword or the acknowledgements. Don't run the same pass again on the same chapters
without a request. Record the pass in the book map (date, commit, counts) so it is not repeated
by a later session.
