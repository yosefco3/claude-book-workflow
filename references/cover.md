# Book cover: print-ready Hebrew (RTL) wrap

Contents: 1. Principle - 2. Workflow - 3. The front image - 4. Image prompt template - 5. Geometry and spine - 6. Spec (cover.json) - 7. Build and checks - 8. CMYK - 9. Dependencies and limits

## 1. Principle

An image model does not draw reliable text, least of all Hebrew. The illustration is made separately,
and the Hebrew typography is set over it in code (HTML/CSS, Noto Hebrew fonts, Chrome headless) at
exact print dimensions. Output, in `build/cover/` by default:

- `cover-wrap.pdf`: back + spine + front in one PDF, for the printer
- `cover-wrap-cmyk.pdf`: optional, with `--cmyk`
- `cover-wrap.png`: preview of the whole wrap
- `cover-front.png` / `.jpg`: the front alone (trim area, no bleed) for online shops

## 2. Workflow

1. Gather: title, subtitle, author (or pen name), trim size, page count, paper thickness per page
   (ask the printer), back-cover text (headline, 2-3 short paragraphs, closing line), ISBN if any.
   For anything missing use the defaults and say so.
2. Design: read `cover-genre-conventions.md` (layout zones, thumbnail test, typography).
3. Front image: section 3. Save it as `manuscript/assets/cover-front.png`.
4. Write `manuscript/cover/cover.json` (section 6). `\n` in the title, subtitle or back headline is
   a manual line break, to avoid a single word on a line.
5. Build: `python3 scripts/make_cover.py --root BOOK` (add `--cmyk` if the printer wants CMYK).
6. Check before handing over (section 7).

## 3. The front image

Pick the first option that applies. Never tell the user a generator is free or already installed;
ask what they have.

a. **The author supplies the image**: a photo, their own artwork, or a designer's file. Check the
   size against the table in section 4, and that it carries no text or logos.
b. **Claude writes a prompt** for the generator the user has (Gemini / Imagen, ChatGPT image
   generation, Midjourney, Flux, Stable Diffusion, a local ComfyUI setup, or any other), using the
   template in section 4. The user generates 2-4 variants, picks one, and saves it to
   `manuscript/assets/cover-front.png`. Keep the rejected variants outside the repo.
c. **The session has an image tool** (a built-in image-generation tool or an MCP connector): use it
   with the same prompt, and save the chosen result to the same path.

If the generator cannot reach the pixel size, generate at its maximum and upscale with a tool the
user has. Flat illustration styles survive moderate enlargement in print; photographs do not.

## 4. Image prompt template

Fill the angle brackets. Keep the order: subject, composition, style, palette, exclusions.

```text
<style, e.g. "painterly illustration" | "documentary photograph" | "minimal flat vector art">
of <one central subject or scene tied to the book's theme>.
Vertical portrait composition, aspect ratio about 2:3.
<Quiet area>: the upper third is calm and uncluttered (open sky, soft blur or plain surface) so a
large title can be placed there. The lower fifth is also calm, for the author's name.
Main subject sits in the middle band, slightly off-center.
Palette: <2-3 colors, matching the genre>. Mood: <one or two words>.
No text, no letters, no numbers, no logos, no watermark, no symbols or glyphs in the sky.
```

Notes that make prompts work:

- Ask for the empty zones explicitly; models fill every corner otherwise.
- State what must not appear (text, religious or political symbols, faces) in the same prompt.
- The cover must also work in greyscale and at 80 px wide (thumbnail test).
- Genre example prompts are in `cover-genre-conventions.md`; adapt them, do not paste them.

### Aspect ratio and minimum size (A5 example)

The front panel is the trim width plus one outer bleed, by the trim height plus bleed top and bottom.
For A5 (148 x 210 mm) with 3.2 mm bleed:

- width 148 + 3.2 = 151.2 mm, height 210 + 2 x 3.2 = 216.4 mm
- at 300 dpi: 151.2 / 25.4 x 300 = 1786 px, 216.4 / 25.4 x 300 = 2556 px
- so **at least 1786 x 2556 px** (round up to 1800 x 2560); the ratio is about 0.70, between 2:3 and 3:4
- the image is scaled to cover the panel and the overflow is cropped, so keep the subject away from
  the edges. Formula for another size: `(trim + bleed) / 25.4 x 300`.

## 5. Geometry and spine (`scripts/cover_geometry.py`)

- Hebrew book (`rtl`, the default): **front on the left, back on the right**. Left-to-right books: reversed.
- Spine width = pages x `mm_per_page`. `mm_per_page` is the paper thickness per page: take it from
  the printer's spec sheet or cover calculator for the paper you chose, because it differs between
  papers and printers. Example only: 0.05 mm (a value like this suits a light uncoated paper).
  A spine under about 6 mm should carry no text.
- Bleed: use what the printer asks for (3 mm and 3.2 mm are common). Safe zone: 6 mm inside the trim line (adjustable).
- Total width = 2 x (trim width + bleed) + spine; total height = trim height + 2 x bleed.
  A5, 3.2 mm bleed, 200 pages x 0.05 mm: 2 x 151.2 + 10 = 312.4 mm wide, 216.4 mm high.
- Spine text is rotated `-90` (head tilts left, the Hebrew convention); `90` for left-to-right books.
- Trim presets: `A4`, `A5`, `B5`, `6x9`, `5.5x8.5`, `5x8`, `15.5x23.5`, `17x24`, or `WIDTHxHEIGHT` in mm.
- Print the numbers: `python3 scripts/cover_geometry.py --trim A5 --pages 200 --mm-per-page 0.05 --bleed 3.2`

The page count must be final. If the page count changes, rebuild the cover, because the spine changes.

## 6. Spec: `manuscript/cover/cover.json`

See `examples/sample-book/manuscript/cover/cover.json`. Fields:

| Field | Meaning |
|---|---|
| `title`, `subtitle`, `author` | title and author fall back to `book.json` |
| `front_image` | path relative to the spec folder or to the book root |
| `trim`, `bleed`, `safe` | mm; trim is a preset or `WxH` |
| `pages` | fallback page count (see below) |
| `mm_per_page` | paper thickness per page, from the printer |
| `spine_rotation` | `-90` Hebrew, `90` left-to-right |
| `back` | `headline`, `paragraphs`, `tagline` |
| `isbn` | 12 or 13 digits draws an EAN-13 barcode on the back; `null` leaves the corner free (use `null` if the printer adds its own barcode) |
| `colors` | `bg`, `text`, `accent`, `scrim` (strength of the top and bottom darkening for legibility) |
| `fonts`, `sizes` | `sizes` are ratios of the trim width (title 0.19 x 148 mm = 28 mm) |
| `out_prefix` | file prefix, default `cover` |

Page count order: `--pages`, else the page count of `build/<output_name>.pdf` if it exists, else `pages`.

## 7. Build and checks

```bash
python3 scripts/make_cover.py [--root BOOK] [--spec PATH] [--pages N] [--out DIR] [--cmyk]
```

`--keep-html` keeps the HTML for debugging; `--dpi` sets the preview and front resolution (default 300).
Exit code 2 means bad input (missing image, spec or page count), 1 a missing tool.

Check before handing over:

1. Open `cover-wrap.png`: front on the left, spine in the middle, back on the right; no text touching an edge.
2. The spine reads with the head tilted left; the title is readable.
3. Shrink the front to 80 px wide: the title must still read. If not, enlarge it or raise `scrim`.
4. `pdfinfo cover-wrap.pdf`: page size = (2 x (trim + bleed) + spine) x (height + 2 x bleed), in mm.
5. Send the printer the PDF and ask them to confirm the spine width and bleed against their template.

## 8. CMYK

Chrome writes RGB PDFs. Many printers convert RGB themselves; some ask for CMYK. `--cmyk` adds
`cover-wrap-cmyk.pdf` through Ghostscript (`-sColorConversionStrategy=CMYK`). If `gs` is missing the
step is skipped with a message and the RGB PDF is still written. The conversion has no printer ICC
profile; saturated greens and blues shift, so look at the CMYK file, and ask the printer which they prefer.

## 9. Dependencies and limits

- Google Chrome, Chromium or Edge (found through `office.find_chrome()`, or set `BOOK_CHROME`),
  `pdftoppm` (poppler-utils), Pillow, Noto Hebrew fonts installed (otherwise Chrome substitutes others).
  Optional: Ghostscript for `--cmyk`.
- Tests: `python3 -m pytest tests/test_cover.py -q`.
- A low-resolution image is stretched; check the pixel size first (section 4).
- Fonts are embedded in the PDF, colors are RGB unless `--cmyk` is used.
