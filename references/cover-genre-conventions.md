# Cover design conventions by genre

Adapted from general book-cover design guidance. Used by `cover.md` when choosing the layout, the
palette and the image prompt. The example prompts below are starting points for any image generator;
always append the exclusions from the template in `cover.md` (no text, no logos, empty title zone).

Hebrew-specific notes: the book opens from the right, so the front is on the left of the wrap. Hebrew
text has no capitals, so "all caps" advice maps to a heavy weight. Use a serif (Noto Serif Hebrew Bold)
for the title and a sans (Noto Sans Hebrew) for the back text. Add `\n` in the title to avoid a
one-word last line; browsers do not balance lines.

## Genre Conventions

Readers judge books by covers. Matching genre expectations is critical — a romance reader will skip a cover that looks like sci-fi, regardless of content.

### Fiction

| Genre | Palette | Imagery | Typography | Mood |
|-------|---------|---------|------------|------|
| **Thriller/Mystery** | Dark (black, navy, blood red) | Lone figure, urban scenes, shadows | Bold sans-serif, all caps | Tense, ominous |
| **Romance** | Warm (pink, red, gold, soft purple) | Couples, flowers, scenic backdrops | Script/cursive, elegant serif | Passionate, dreamy |
| **Sci-Fi** | Cool (blue, teal, purple, silver) | Space, tech, geometric shapes | Clean sans-serif, futuristic | Vast, technological |
| **Fantasy** | Rich saturated (emerald, crimson, gold) | Swords, magic, landscapes, creatures | Decorative serif, ornamental | Epic, magical |
| **Literary Fiction** | Muted, sophisticated | Abstract, minimal, symbolic | Elegant serif, understated | Thoughtful, artistic |
| **Horror** | Dark with high contrast pops | Faces, shadows, isolation, decay | Distressed, bold, dripping | Dread, unease |
| **Historical** | Sepia, muted period-accurate | Period clothing, architecture, artifacts | Classical serif | Nostalgic, authentic |

### Non-Fiction

| Category | Style | Imagery | Typography |
|----------|-------|---------|------------|
| **Business/Self-help** | Clean, bold, 2-3 colors | Minimal or none, icon optional | Large bold sans-serif title |
| **Memoir** | Personal, warm | Author photo or atmospheric scene | Mix of serif and sans |
| **Science/Academic** | Professional, structured | Diagrams, abstract visuals | Clean serif, structured layout |
| **Cookbook** | Appetizing, bright | Hero food photograph | Warm, inviting fonts |
| **Travel** | Vibrant, aspirational | Destination photography | Adventure-style fonts |

## Cover Sizing

### Print (Trim Sizes)

| Format | Dimensions | Common For |
|--------|-----------|------------|
| Mass market paperback | 4.25 x 6.87" | Genre fiction |
| Trade paperback | 5.5 x 8.5" | Most fiction/non-fiction |
| Standard | 6 x 9" | Non-fiction, textbooks |
| Large format | 7 x 10" | Coffee table, art books |

### Digital

| Platform | Cover Size | Aspect Ratio |
|----------|-----------|--------------|
| Amazon Kindle | 2560 x 1600 px (min 1000 x 625) | 1.6:1 |
| Apple Books | 1400 x 1873 px minimum | ~3:4 |
| General ebook | 2500 x 3750 px | 2:3 |

### Spine Width

Spine = pages x paper thickness per page, taken from the printer's spec for the chosen paper (see `cover.md`, section 5).

## Layout Zones

```
┌─────────────────────────┐
│     TITLE ZONE          │ ← Top 1/3: Title must be readable here
│     (largest text)      │    This is what shows in thumbnails
│                         │
│                         │
│     MAIN IMAGE          │ ← Middle: Core visual/illustration
│     ZONE                │    The emotional hook
│                         │
│                         │
│     SUBTITLE /          │ ← Bottom area: Author name, subtitle
│     AUTHOR ZONE         │    Smaller text, less critical at thumbnail
└─────────────────────────┘
```

## The Thumbnail Test

Your cover will be seen at **80x120px** on Amazon, 60x90px in search results, and ~40x60px on mobile grids.

**At thumbnail size, readers must be able to identify:**
1. The genre (from color and composition)
2. The title (if large enough)
3. The mood (from imagery)

**Test:** shrink your cover to 80px wide. If you can't read the title or identify the genre, redesign.

## Prompting by Genre

### Thriller
```text
dark cinematic book cover scene, silhouette of a person standing before a foggy bridge at night, single streetlamp casting long shadows, noir atmosphere, high contrast, desaturated blue tint, dramatic tension
```

### Romance
```text
romantic soft-focus scene, couple silhouetted against golden sunset on a beach, warm pink and gold tones, bokeh lights, dreamy atmosphere, soft pastel sky, intimate mood
```

### Sci-Fi
```text
science fiction book cover art, massive space station orbiting a ringed planet, deep blue and teal color palette, stars and nebula background, hard sci-fi aesthetic, cinematic scale, clean geometric architecture
```

### Fantasy
```text
epic fantasy book cover illustration, ancient stone castle on a cliff overlooking a misty valley, magical aurora in the sky, rich emerald and gold colors, detailed environment, sense of wonder and adventure
```

### Non-Fiction / Business
```text
minimal abstract book cover background, clean gradient from deep navy to white, subtle geometric pattern, professional and modern, negative space, corporate aesthetic
```

## Typography Rules

**AI cannot render text reliably.** Generate the cover art/background with AI, then add the typography in code (`make_cover.py`).

### Title Hierarchy
1. **Title** — largest, most prominent, top 1/3 of cover
2. **Subtitle** — smaller, below title or at bottom
3. **Author name** — bottom of cover, size depends on author recognition

### Font Pairing by Genre
- Thriller: bold sans-serif title + condensed sans-serif author
- Romance: script/cursive title + elegant serif author
- Sci-Fi: geometric sans-serif for both
- Fantasy: decorative/medieval serif title + clean serif author
- Business: heavy bold sans-serif title + light sans-serif subtitle

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Wrong genre signals | Readers skip it | Study bestsellers in your genre |
| Title too small | Invisible at thumbnail | Title should fill top 1/3 |
| Too much detail | Muddy at small sizes | Simplify, use negative space |
| AI-generated text | Garbled letters | Add text in code |
| Centered everything | Static, boring | Use asymmetry intentionally |
| Following trends blindly | Dates quickly | Classic genre conventions endure |

## Checklist

- [ ] Genre instantly recognizable from colors and composition
- [ ] Title readable at 80px wide (thumbnail test)
- [ ] No AI-generated text on cover
- [ ] Works in both color and greyscale
- [ ] Correct dimensions for target platform
- [ ] Author name visible but not competing with title
- [ ] High resolution (300 DPI for print, 2500px+ for digital)
- [ ] Spine text readable (for print)

