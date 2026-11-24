# Production: PDF, print files, cover

## Contents
- The reading PDF and the print PDF
- Page numbers in a Hebrew book
- Figures in a black-and-white interior
- Print-on-demand files
- The cover follows the page count
- Whole-book DOCX
- A print build script for the book

## The reading PDF and the print PDF

`build_pdf.py` makes both from the same source:
- the default build is a draft for reading: the title page carries a "draft, not for
  distribution" note;
- `--release` drops the note and adds the copyright page from `book.json` (`copyright`: a list
  of lines: rights, year, credits, ISBN when there is one).

The contents page lists the chapters without page numbers (Chrome cannot fill them in
reliably). For a print edition, add the numbers from the finished PDF, or set the contents page
by hand in the book's own print build.

Sizes: `--size A5` (148×210 mm), `A4`, `15x22`, or any `<W>x<H>mm`. Pick the trim size with
the printer before laying out anything else; the page count, the spine and the cover all follow
from it. Readability before page count: one volume, a comfortable body size and real margins.
Don't shrink the font or the margins to save pages.

## Page numbers in a Hebrew book

A Hebrew book opens from the right, so its first page is a LEFT page and odd pages sit on the
left (the reverse of a Latin-script book). `build_pdf.py` centres the folio at the bottom, which
sidesteps the left/right question, and prints no number on the title, copyright, contents and
part pages while still counting them. If the book wants folios on the outer corners, or a check
of a finished PDF before print, use the `book-page-numbers` skill if it is installed.

## Figures in a black-and-white interior

If the interior is printed in black and white, convert every figure to grayscale and look at it
before it goes in: nothing may depend on color alone. Keep text inside the figure clear of the
edges, keep a consistent size, and prefer SVG sources (convert to PNG with
`office.py convert fig.svg --to png`). Raster images for print: 300 dpi at the printed size.

## Print-on-demand files

Most print-on-demand services want two PDFs:

- **Interior**: the `--release` PDF at the trim size. Usually without bleed unless images run
  off the page. Read the service's upload options carefully: a switch such as "file already
  includes bleed" changes how they scale the file.
- **Cover**: one spread (back + spine + front) with bleed on all sides (often 3–3.2 mm), in
  CMYK. An RGB PDF with an embedded color profile can show strange colors in the printer's
  previewer (a pink cast was seen in practice). Convert with Ghostscript:

  ```bash
  gs -o cover-cmyk.pdf -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress \
     -sColorConversionStrategy=CMYK -sProcessColorModel=DeviceCMYK cover-rgb.pdf
  ```

- **Spine width** = page count × the paper's thickness per page. Take the coefficient from the
  printer (their calculator or dashboard), not from a guess: a wrong coefficient gives a cover
  that does not fit. After each upload, check that the spine the service shows equals
  pages × coefficient.
- Some services also want the front and back as separate panels (with and without bleed) and
  a front image for the store page (JPG/PNG, 300 dpi).

Every change to the source can change the page count. After the rebuild chain, report the page
count; if it changed, the cover must be rebuilt and both files uploaded again.

## The cover follows the page count

Keep the cover as data (`manuscript/cover/cover.json`: title, subtitle, author, blurb, image,
trim size, bleed, paper coefficient) and build it in code, so a new page count gives a new
cover without manual work. `scripts/make_cover.py` builds the full wrap from such a spec;
the procedure, the image options and the genre conventions are in [cover.md](cover.md). Any change to the title, the subtitle, the back text or the structure touches the
cover, the book map and the title page together.

## Whole-book DOCX

An outside editor or proofreader often wants the whole book as one Word file. Join the chapters
in book order into one Markdown file with `---` between chapters (page breaks) and convert it
with `md2docx.js` (`--size A4` for editing, `--size A5` to approximate the printed page
numbers). Section markers `::section:: nofolio` / `::section:: folio` turn page numbers off
and on (title, contents, part pages without them).

## A print build script for the book

The steps above are specific to the printer and the cover, so they belong in the book's own
`scripts/build_release.py` (or similar), listed in its `CLAUDE.md`: build the `--release` PDF
at the trim size, count its pages (`pdfinfo`), check the folios, build the cover for that page
count, convert it to CMYK, cut the panels, and print the page count and the spine width. Then
the rebuild chain's step 4 is one command.
