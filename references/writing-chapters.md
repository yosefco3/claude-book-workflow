# Writing chapters

## Contents
- A chapter from the author's existing text
- A chapter from a raw idea
- Structure rules
- Quotations and sources
- Tone and AI tells
- Texts the author writes
- Summary pages and figures
- The quality loop

## A chapter from the author's existing text

A chapter can start from anything: an article, notes, a draft, a transcript, a raw idea (next
section). When the author already wrote the material, the chapter keeps their text and their
order; the book is the same writing in a new frame. How close to stay is the author's call:
record it in the book's `CLAUDE.md` (for example "close to the article, condensed to the
chapter length").

Allowed, and welcome:
- an opening that gives background (who, when, why it matters) to a reader with no context;
- explaining a term before it is used;
- question-before-answer framing;
- references to other chapters by name ("in the chapter on watering");
- a "Sources for this chapter" section at the end.

Adjustments when the material was published on the web: "article", "series" → "chapter", "part"; remove links,
"on this site", calls to comment or share, dates of posting; internal links become references
to chapters.

Not allowed on your own initiative: thinning the text, reorganizing it, or "improving" the
argument. If something seems weak, propose a change; don't make it.

## A chapter from a raw idea

When the author gives an idea and not a text, think the mechanism through to the end first
(what claim, what it rests on, what follows), and only then bring sources, two to four of them.
A draft built source by source turns into a survey and loses the idea.

That draft is a base, not the finished chapter. It will sound less like the author than their
own writing; the author's voice comes in when they edit it. Keep it on the short side so they
have room. Once the author has worked on it, it is their text: never call it "my text".

## Structure rules

- **Definitions and background before the claim and the conclusion.** A reader meets a term
  explained before it carries weight. Facts come before what is concluded from them.
- **Length.** Set a target range in the book's `CLAUDE.md` (1,200–1,600 words works for
  reflective non-fiction). A long source article is condensed to the range; the aim is a
  chapter that is pleasant to read, without repetition or excess detail.
- **Split what is long.** A section of more than about six paragraphs, or a paragraph of more
  than about six sentences, is split, with a heading for the new section.
- **Heavy material in a "going deeper" section.** A dense section gets the heading
  `## <deep heading>: ...` (from `special_headings.deep`) and opens with a one-line "In short:"
  so a reader can skip it. The PDF sets these sections apart.
- **Don't open a chapter by summarizing the previous one.**
- **One hedge per chapter.** If a claim needs a caveat, give it once, in one clear place.
  Reconciling sources that disagree belongs in the sources section, not in the body.

## Quotations and sources

- The body is in plain language, mostly paraphrase in the author's words. One or two short,
  easy quotations that are the heart of the chapter may stay in the body.
- Hard quotations (archaic language, long passages) and exact references go to the
  "Sources for this chapter" section at the end, in the order they appear, each with its
  precise citation.
- Each source the chapter relies on gets its own short passage in the body: who it is and what
  it says, simply. Stories are retold in short sentences.
- Copyright: quotations from copyrighted works stay short and few (three to five short ones per
  chapter is a sane ceiling), and a passage is never retold in its original order. Paraphrase
  carries the meaning.
- Verify quotations against a primary source when one is available, and list in the book map
  the ones that could not be verified.

## Tone and AI tells

- Moderate and matter-of-fact: no drama, no superlatives, no punchlines, no "power words". The
  author's own sharpness (a polemic edge) stays; don't soften what they wrote.
- Before correcting an unusual phrase, consider that it may be deliberate. Words the style sheet
  lists as the author's are never "fixed".
- The book has zero em dashes (the build reports them). In Hebrew the en dash with spaces
  (` – `) is the separator.
- Remove the patterns that mark machine writing: "not X but Y" contrasts in series, a closing
  line that repeats the paragraph, forced triads, staged openers ("let's dive in"), rhetorical
  questions on a template, bold on every term, bullet lists where a paragraph reads better,
  exaggerations the source does not make ("only", "the first", "always", "everyone").
- If a `humanizer` skill (or similar) is installed, use it for this pass, with the rule below.

## Texts the author writes

Some texts must be the author's own: the personal introduction, the introduction to each part
or thinker if the author wants it, the afterword, the acknowledgements. For these, propose an
outline and questions; don't write the text. Text the author added during editing is not
touched beyond typos.

## Summary pages and figures

- A "what we learned" page at the end of a part lists the part's main points in a few lines.
- Figures: if the interior is printed in black and white, every figure must read in grayscale
  (check it converted to gray before showing it), with no meaning carried by color alone.
  Draw diagrams as SVG with the text in the book's language and export PNG for the DOCX
  (`office.py convert fig.svg --to png`). Keep a consistent size (for example 1000×1250 px)
  and keep text away from the edges. Reference figures in the chapter with
  `![Figure N: caption](../assets/NN-figK-slug.png)`.

## The quality loop

After a chapter is written or heavily edited, before it goes to the author:

1. **Self-check against a rubric**, scored afresh on the full text each round (not from memory),
   fixing and re-scoring until it reaches the bar the book set (90/100 worked well):
   faithfulness to the author's voice and ideas (25), clarity for a reader with no background
   (20), serving the book's vision (15), no AI tells (15), grammar and consistent terms (15),
   flow and argument order (10).
2. **Language critic.** A subagent with an explicit limit: grammar, punctuation, consistency
   and style only; no content changes; quotations untouched; the author's words (per the style
   sheet) kept. Keep what is clearly right; report what you rejected and why.
3. **Language editor pass** (for Hebrew, a `hebrew-editor` skill at full depth if installed),
   with the style sheet.

   The language fixes from steps 2–4 go in the way `book.json` says: `"apply"` = applied
   directly and listed in the report; `"propose"` = listed for the author (current → proposed)
   and applied after approval.
4. **Wording pass for AI tells** (a `humanizer` skill if installed). Rule for this and every
   automatic style pass: wording only. A sentence may be deleted only when it repeats the one
   next to it. Changes of meaning or fact are listed at the end for the author to decide one
   by one, never applied.
5. Rebuild (the chain in SKILL.md), send the author the chapter's DOCX or PDF, and wait for
   approval before the next chapter.
