#!/usr/bin/env node
// Convert one Markdown chapter to a DOCX the author can edit in any word processor.
// Usage: node md2docx.js <input.md> <output.docx> [--config book.json] [--size A4|A5] [--no-page-numbers]
//   --config book.json   book settings: special_headings.deep / .sources (section headings that switch
//                        the paragraph style), fonts.body / fonts.heading (override the preset fonts),
//                        dir ("rtl" default, or "ltr").
//   --no-page-numbers    no page number in the footer.
//   --size A4|A5         A4 (default): comfortable editing size. A5: page, margins, sizes and spacing
//                        of a printed A5 book, so page counts come close to the printed book.
// Extra markup (used for a whole-book DOCX):
//   ---                        page break
//   ![caption](path.png)       centred figure (PNG) with its caption below
//   ::style:: text             special block: title, subtitle, author, kicker, chnum, part, small, caption,
//                              tocpart, tocline, blank
//   ::section:: folio|nofolio  new section (starts a new page) with or without a page number
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle,
  Footer, PageNumber, PageBreak, ImageRun,
} = require('docx');

const args = process.argv.slice(2);
const pageNumbers = !args.includes('--no-page-numbers');
const optValue = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
const size = optValue('--size') || 'A4';
const configPath = optValue('--config');
const [inPath, outPath] = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--size' && args[i - 1] !== '--config');
if (!inPath || !outPath) {
  console.error('usage: node md2docx.js <in.md> <out.docx> [--config book.json] [--size A4|A5] [--no-page-numbers]');
  process.exit(1);
}

// Book settings (all optional).
let conf = {};
if (configPath) {
  try { conf = JSON.parse(fs.readFileSync(configPath, 'utf8')); } catch (e) {
    console.error('--config: cannot read ' + configPath + ': ' + e.message);
    process.exit(1);
  }
}
const special_ = conf.special_headings || {};
const DEEP_HEADING = special_.deep || 'להעמקה';
const SOURCES_HEADING = special_.sources || 'מקורות לפרק זה';
const RTL = (conf.dir || 'rtl') !== 'ltr';

// Geometry and typography per page size. Sizes in half-points, distances in twips (1 mm = 56.7, 1 pt = 20).
// A5 mimics a printed book: body 10.4pt/1.55, sources 9.2pt/1.5, deep 9.4pt, quote 9.9pt,
// headings 18/13/11pt, symmetric 15 mm side margins, caption 8.8pt.
const PRESETS = {
  A4: {
    font: 'David', sourcesFont: 'David',
    page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440, footer: 720 } },
    body: 26, sources: 23, deep: 23, quote: 25, caption: 22, folio: 20,
    leading: null, after: 200,                         // automatic 1.5 spacing
    heading: { 1: [40, 320, 240], 2: [32, 320, 240], 3: [28, 320, 240] },  // size, before, after
    deepIndent: 360, quoteIndent: 400,
    figMax: [576, 720],                                 // pixels (96 per inch)
    title: 64, subtitle: 34, author: 30, part: 48, kicker: 24, small: 20, toc: [26, 24],
  },
  A5: {
    font: 'Noto Serif Hebrew', sourcesFont: 'Noto Sans Hebrew',
    page: { size: { width: 8391, height: 11906 }, margin: { top: 850, bottom: 907, left: 850, right: 850, footer: 300 } },
    body: 21, sources: 18, deep: 19, quote: 20, caption: 18, folio: 18,
    leading: 1.55, after: 156,                          // 0.75em of 10.4pt
    heading: { 1: [36, 0, 216], 2: [26, 364, 130], 3: [22, 264, 88] },
    deepIndent: 140, quoteIndent: 190,
    figMax: [446, 612],                                 // 118 mm x 162 mm
    title: 60, subtitle: 28, author: 26, part: 42, kicker: 21, small: 17, toc: [21, 20],
  },
}[size];
if (!PRESETS) { console.error('--size: A4 or A5'); process.exit(1); }
const P = PRESETS;
const BIDI = RTL ? { bidirectional: true } : {};
// Fonts from the book config replace the preset font names (sizes stay).
if (conf.fonts && conf.fonts.body) P.font = conf.fonts.body;
if (conf.fonts && conf.fonts.heading) { P.sourcesFont = conf.fonts.heading; P.headingFont = conf.fonts.heading; }


function run(text, opts = {}) {
  return new TextRun({ text, ...(RTL ? { rightToLeft: true } : {}), font: P.font, ...opts });
}

// Line spacing of a body paragraph: exact (leading x font size) when there is a leading, else automatic 1.5.
function lineSpacing(halfPts, leading = P.leading) {
  return leading ? { line: Math.round((halfPts / 2) * leading * 20), lineRule: 'exact' } : { line: 360 };
}

// "Deep" section: slightly smaller font, indent and a rule in the margin, so the reader sees it can be skipped.
const DEEP_BORDER = { style: BorderStyle.SINGLE, size: 12, color: '8a7a5c', space: 8 };
const QUOTE_BORDER = { style: BorderStyle.SINGLE, size: 18, color: 'b8a98a', space: 6 };

// Body paragraph. mode: '' | 'deep' | 'sources' | 'quote'
function para(text, mode = '') {
  const sizeHp = { deep: P.deep, sources: P.sources, quote: P.quote }[mode] || P.body;
  const font = mode === 'sources' ? P.sourcesFont : P.font;
  const extra = mode === 'deep' ? { indent: { start: P.deepIndent }, border: { right: DEEP_BORDER } }
    : mode === 'quote' ? { indent: { start: P.quoteIndent, end: Math.round(P.quoteIndent / 3) }, border: { right: QUOTE_BORDER } }
      : {};
  return new Paragraph({
    ...BIDI,
    alignment: AlignmentType.START,
    spacing: { after: P.after, ...lineSpacing(sizeHp, mode === 'sources' && P.leading ? 1.5 : P.leading) },
    ...extra,
    children: inlineRuns(text, { size: sizeHp, font }),
  });
}

// **bold** and *italic* inside a paragraph become bold/italic runs (no visible asterisks in the DOCX).
function inlineRuns(text, opts) {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/).filter(Boolean).map((seg) =>
    seg.startsWith('**') && seg.endsWith('**') && seg.length > 4
      ? run(seg.slice(2, -2), { ...opts, bold: true })
      : seg.startsWith('*') && seg.endsWith('*') && seg.length > 2
        ? run(seg.slice(1, -1), { ...opts, italics: true })
        : run(seg, opts));
}

function heading(text, level, sources = false) {
  const map = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 };
  let [sz, before, after] = P.heading[level];
  if (sources) sz = Math.round(P.sources * (level === 2 ? 1.2 : 1.08));
  return new Paragraph({
    heading: map[level],
    ...BIDI,
    alignment: AlignmentType.START,
    keepNext: true,
    spacing: { before, after },
    children: [run(text, { size: sz, bold: true, color: '1a1a1a', font: sources ? P.sourcesFont : (P.headingFont || P.font) })],
  });
}

// PNG size from the IHDR header (width and height at bytes 16-24).
function pngSize(buf) {
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

// Figure: centred, scaled down to figMax, caption below.
function figure(src, caption) {
  const abs = path.isAbsolute(src) ? src : path.resolve(path.dirname(inPath), src);
  const data = fs.readFileSync(abs);
  const { w, h } = pngSize(data);
  const scale = Math.min(P.figMax[0] / w, P.figMax[1] / h, 1);
  const out = [new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 240, after: 100 },
    children: [new ImageRun({ type: 'png', data, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) } })],
  })];
  if (caption) {
    out.push(new Paragraph({
      ...BIDI,
      alignment: AlignmentType.CENTER,
      spacing: { after: 300 },
      children: inlineRuns(caption, { size: P.caption, italics: true }),
    }));
  }
  return out;
}

// Special blocks: title page, part pages, chapter number, table of contents, copyright page.
function special(kind, text) {
  const center = AlignmentType.CENTER;
  const start = AlignmentType.START;
  const base = BIDI;
  switch (kind) {
    case 'title': return new Paragraph({ ...base, alignment: center, spacing: { before: 4800, after: 400 }, children: inlineRuns(text, { size: P.title, bold: true }) });
    case 'subtitle': return new Paragraph({ ...base, alignment: center, spacing: { after: 1600 }, children: inlineRuns(text, { size: P.subtitle }) });
    case 'author': return new Paragraph({ ...base, alignment: center, spacing: { after: 200 }, children: inlineRuns(text, { size: P.author }) });
    case 'kicker': return new Paragraph({ ...base, alignment: center, spacing: { before: 2400, after: 160 }, children: inlineRuns(text, { size: P.kicker, color: '555555' }) });
    case 'chnum': return new Paragraph({ ...base, alignment: start, keepNext: true, spacing: { before: 0, after: 60 }, children: inlineRuns(text, { size: P.kicker, color: '555555' }) });
    case 'part': return new Paragraph({ ...base, heading: HeadingLevel.HEADING_1, alignment: center, spacing: { before: 1200, after: 400 }, children: inlineRuns(text, { size: P.part, bold: true, color: '1a1a1a' }) });
    case 'small': return new Paragraph({ ...base, alignment: start, spacing: { after: 120, line: 276 }, children: inlineRuns(text, { size: P.small }) });
    case 'caption': return new Paragraph({ ...base, alignment: center, spacing: { after: 300 }, children: inlineRuns(text, { size: P.caption, italics: true }) });
    case 'tocpart': return new Paragraph({ ...base, alignment: start, spacing: { before: 280, after: 100 }, children: inlineRuns(text, { size: P.toc[0], bold: true }) });
    case 'tocline': return new Paragraph({ ...base, alignment: start, indent: { start: 400 }, spacing: { after: 60 }, children: inlineRuns(text, { size: P.toc[1] }) });
    case 'blank': return new Paragraph({ children: [] });
    default: return para(text);
  }
}

const lines = fs.readFileSync(inPath, 'utf8').split('\n');
// Sections: by default one section with page numbers (unless --no-page-numbers). ::section:: opens a new one.
const sections = [];
let children = [];
let folio = pageNumbers;
function closeSection() {
  if (children.length) sections.push({ folio, children });
  children = [];
}

let buf = [];
let mode = '';       // '' | 'deep' | 'sources' by the current section
let quote = false;   // the current paragraph is a quote (>)
function flush() {
  if (buf.length) {
    children.push(para(buf.join(' ').trim(), quote ? 'quote' : mode));
    buf = [];
  }
  quote = false;
}
for (const line of lines) {
  const t = line.trim();
  if (!t) { flush(); continue; }
  if (t === '---') { flush(); children.push(new Paragraph({ children: [new PageBreak()] })); continue; }
  const sec = t.match(/^::section::\s*(folio|nofolio)\s*$/);
  if (sec) { flush(); closeSection(); folio = pageNumbers && sec[1] === 'folio'; continue; }
  const img = t.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
  if (img) { flush(); children.push(...figure(img[2], img[1])); continue; }
  const sp = t.match(/^::(\w+)::\s*(.*)$/);
  if (sp) { flush(); children.push(special(sp[1], sp[2])); continue; }
  const m = t.match(/^(#{1,3})\s+(.*)$/);
  if (m) {
    flush();
    const level = m[1].length;
    if (level === 1) mode = '';
    if (level === 2) mode = m[2].startsWith(DEEP_HEADING) ? 'deep' : m[2].startsWith(SOURCES_HEADING) ? 'sources' : '';
    children.push(heading(m[2], level, mode === 'sources'));
    continue;
  }
  // List item (* or -): its own paragraph with a bullet, instead of merging into one line with visible asterisks.
  const li = t.match(/^[*-]\s+(.*)$/);
  if (li) {
    flush();
    children.push(para('• ' + li[1], mode));
    continue;
  }
  const isQuote = t.startsWith('>');
  if (buf.length && isQuote !== quote) flush();
  quote = isQuote;
  buf.push(t.replace(/^>\s*/, ''));
}
flush();
closeSection();

// Footer: centred page number, or empty (a section without a number needs its own empty footer, else it inherits the previous one).
function footer(withNumber) {
  return new Footer({
    children: withNumber ? [new Paragraph({
      alignment: AlignmentType.CENTER,
      ...BIDI,
      spacing: { line: 220, lineRule: 'exact' },   // low line, so the number sits at the bottom of the page
      children: [new TextRun({ children: [PageNumber.CURRENT], font: P.font, size: P.folio, color: '000000' })],
    })] : [new Paragraph({ children: [] })],
  });
}

const doc = new Document({
  styles: { default: { document: { run: { font: P.font, size: P.body } } } },
  sections: sections.map((sec) => ({
    properties: { page: P.page },
    footers: { default: footer(sec.folio) },
    children: sec.children,
  })),
});

Packer.toBuffer(doc).then((buf2) => {
  fs.writeFileSync(outPath, buf2);
  console.log('written:', path.resolve(outPath));
});
