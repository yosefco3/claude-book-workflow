# Publishing: publishers, self-publishing, privacy

## Contents
- The plan
- The rule that protects the publishers' round
- Submission packages
- Privacy and the pen name

## The plan

Write the plan down with the author, with a date, in the book map or a planning doc:
- the routes and their time box (for example: a round of submissions to publishers, in parallel
  with preparing self-publishing: print-on-demand and an e-book), and when the author decides;
- the list of publishers, ranked, after filtering out those whose line clashes with the book's
  content (a publisher that cannot accept the book's positions is a wasted letter and a delay);
- the budget (professional proofreader or reader, cover);
- the status of each submission (sent, reviewing, answered) as the author reports it.

## The rule that protects the publishers' round

Many publishers will not take a book that has already been published, self-publishing
included. So, until the round is over:
- no public sale (print-on-demand store pages stay private, no e-book store),
- no full text on a website,
- review copies printed privately are fine.

Don't send publishers updates on your own initiative while they are reviewing a version; when
one asks for the final manuscript, build a fresh package from the current source. Never send
anything to a publisher, or to anyone, without the author's explicit request.

## Submission packages

One folder per publisher under the book (for example `submissions/<publisher>/`), built by a
script of the book's own from shared templates, so a source change rebuilds every package:
- a cover letter tailored to the publisher (why this book fits their list), from a template
  with `{{placeholders}}`;
- a synopsis, a note about the author, the table of contents;
- sample chapters, or the full manuscript (PDF, and DOCX if they ask), with page numbers;
- an instructions file per publisher, written by hand: how they want it (email, form, post),
  to whom, what to attach.

Personal contact details for the letters (real name, address, phone, email) live in one file
that is never committed. The generated DOCX and PDF files stay out of git. Convert the letters
to PDF with whichever tool renders them correctly (see office-tools.md) and look at the PDF
before the author sends it.

## Privacy and the pen name

When the book is published under a pen name:
- the real name never appears in the book's files: title page, copyright page, metadata,
  file names, the cover;
- identifying details about the author (place, family, workplace) are kept to what the book
  needs;
- the real name appears only where it must: the private contact file for publishers' letters;
- anything that would link the two (a public repository, a site, a shared document) is checked
  before it goes out.
