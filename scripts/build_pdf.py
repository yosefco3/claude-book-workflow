#!/usr/bin/env python3
"""Build a PDF of the book: Markdown -> one HTML (python-markdown) -> PDF (Chrome headless).

Usage: build_pdf.py [--root DIR] [--size A5|A4|15x22|<W>x<H>mm] [--parts p1,p2]
                    [--out PATH] [--html PATH] [--release]
Exit codes: 0 ok, 1 no chapters or a bad option, 2 missing dependency (markdown, Chrome), the book
cannot be read (invalid book.json, a chapter that is not UTF-8) or Chrome failed. Without Chrome
the script stops before building, unless --html is given: then it writes the HTML and exits 2.
"""
import argparse
import base64
import html as htmllib
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402

SIZES = {"A5": (148, 210), "A4": (210, 297), "15X22": (150, 220)}
MIME = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "webp": "image/webp"}
IMG_RE = re.compile(r"^[ \t]*!\[(.*?)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)[ \t]*$", re.M)
H1_RE = re.compile(r"^# (.+?)\s*$", re.M)


def esc(s):
    return htmllib.escape(s, quote=True)


def parse_size(spec):
    """Return (width_mm, height_mm) for 'A5', 'A4', '15x22' or '<W>x<H>mm'."""
    key = spec.strip().upper().replace(" ", "")
    if key in SIZES:
        return SIZES[key]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)MM", key)
    if m:
        return float(m.group(1)), float(m.group(2))
    raise ValueError("unknown page size %r (use A5, A4, 15x22 or <W>x<H>mm)" % spec)


def mm(x):
    return ("%.1f" % x).rstrip("0").rstrip(".") + "mm"


def css(conf, size):
    w, h = size
    top, side, bottom = w * 0.10, w * 0.088, w * 0.108
    inner = side * 1.3
    body = max(9.5, min(12.5, 10.5 + (w - 148) / (210 - 148) * 1.5))
    fonts = conf["fonts"]
    serif = "'%s', 'Noto Serif', 'DejaVu Serif', serif" % fonts.get("body", "serif")
    sans = "'%s', 'Noto Sans', 'DejaVu Sans', sans-serif" % fonts.get("heading", "sans-serif")
    return """
@page {{ size: {w} {h}; margin: {top} {side} {bottom} {side};
  @bottom-center {{ content: counter(page); font-family: {sans}; font-size: {fs:.1f}pt; }} }}
@page :left {{ margin-right: {inner}; }}
@page :right {{ margin-left: {inner}; }}
@page front {{ @bottom-center {{ content: none; }} }}
html {{ font-size: {body:.1f}pt; }}
body {{ font-family: {serif}; line-height: 1.55; margin: 0; text-align: justify; hyphens: auto; }}
h1, h2, h3, .kicker, .sources, figcaption, .draft {{ font-family: {sans}; text-align: start; }}
h1 {{ font-size: 1.75em; margin: 0 0 0.8em; line-height: 1.25; }}
h2 {{ font-size: 1.3em; margin: 1.4em 0 0.5em; }}
h3 {{ font-size: 1.1em; margin: 1.1em 0 0.4em; }}
p {{ margin: 0 0 0.7em; orphans: 2; widows: 2; }}
.chapter {{ break-before: page; }}
.chapter-head {{ margin: 12mm 0 0; }}
.kicker {{ font-size: 0.95em; letter-spacing: 0.04em; margin-bottom: 0.3em; color: #444; }}
.front {{ page: front; break-before: page; }}
.front:first-child {{ break-before: auto; }}
.cover, .part {{ display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; min-height: {minh}; }}
.cover .title {{ font-family: {sans}; font-size: 2.9em; font-weight: bold; margin-bottom: 0.4em; }}
.cover .subtitle {{ font-size: 1.35em; margin-bottom: 2em; }}
.cover .author {{ font-size: 1.25em; }}
.draft {{ margin-top: 3em; font-size: 0.85em; color: #666; }}
.part h1 {{ font-size: 2em; }}
.copyright {{ font-size: 0.85em; text-align: start; display: flex; flex-direction: column;
  justify-content: flex-end; min-height: {minh}; }}
.copyright p {{ margin: 0 0 0.4em; }}
.toc h1 {{ font-size: 1.6em; }}
.toc ul {{ list-style: none; padding: 0; margin: 0; }}
.toc li {{ margin: 0.25em 0; }}
.toc a {{ color: inherit; text-decoration: none; }}
.toc li.toc-part {{ font-family: {sans}; font-weight: bold; margin-top: 0.9em; }}
.toc .num {{ display: inline-block; min-width: 1.6em; color: #555; }}
.deep {{ font-size: 0.92em; padding-inline-start: 0.7em; border-inline-start: 0.5mm solid #999; margin: 1em 0; }}
.deep h2 {{ font-size: 1.15em; margin-top: 0.3em; }}
.sources {{ font-size: 0.88em; margin-top: 1.6em; padding-top: 0.6em; border-top: 0.2mm solid #999; }}
.sources h2 {{ font-size: 1.1em; margin-top: 0.2em; }}
blockquote {{ font-size: 0.95em; margin: 0.6em 1.2em 0.8em 0.3em; padding-inline-start: 0.8em;
  border-inline-start: 0.4mm solid #bbb; }}
figure {{ margin: 1em 0; text-align: center; break-inside: avoid; }}
figure img {{ max-width: 100%; max-height: {maxh}; }}
figcaption {{ font-size: 0.85em; margin-top: 0.3em; color: #333; }}
.fig-missing {{ text-align: center; color: #900; }}
table {{ border-collapse: collapse; font-size: 0.92em; margin: 0.8em 0; }}
th, td {{ border: 0.2mm solid #999; padding: 0.25em 0.45em; }}
hr {{ border: none; border-top: 0.2mm solid #999; margin: 1.5em 0; }}
""".format(w=mm(w), h=mm(h), top=mm(top), side=mm(side), bottom=mm(bottom), inner=mm(inner),
           body=body, fs=body * 0.85, serif=serif, sans=sans,
           minh=mm(h - top - bottom - 2), maxh=mm(h * 0.72))


def data_uri(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:%s;base64,%s" % (MIME.get(ext, "application/octet-stream"), b64)


def render_body(md, ch, md_lib, conf, warnings):
    """Chapter Markdown (without its H1) -> HTML with figures and deep/sources wrappers."""
    figs = {}

    def fig(m):
        caption, src = m.group(1).strip(), m.group(2)
        token = "FIGTOKEN%dX" % len(figs)
        fpath = os.path.normpath(os.path.join(os.path.dirname(ch.path), src))
        if os.path.isfile(fpath):
            figs[token] = ('<figure><img src="%s" alt="%s">%s</figure>' % (
                data_uri(fpath), esc(caption), "<figcaption>%s</figcaption>" % esc(caption) if caption else ""))
        else:
            warnings.append("%s: image not found: %s" % (ch.rel, src))
            figs[token] = '<p class="fig-missing">%s</p>' % esc(caption or src)
        return "\n" + token + "\n"

    md = IMG_RE.sub(fig, md)
    deep = "## " + conf["special_headings"].get("deep", "\0")
    srcs = "## " + conf["special_headings"].get("sources", "\0")
    out = []
    for seg in re.split(r"(?m)^(?=## )", md):
        if not seg.strip():
            continue
        h = md_lib.markdown(seg, extensions=["tables", "sane_lists"])
        if seg.startswith(deep):
            h = '<div class="deep">%s</div>' % h
        elif seg.startswith(srcs):
            h = '<div class="sources">%s</div>' % h
        out.append(h)
    result = "".join(out)
    for token, h in figs.items():
        result = result.replace("<p>%s</p>" % token, h).replace(token, h)
    return result


def build_html(conf, chapters, size, release, md_lib, warnings):
    labels = conf["labels"]
    parts_names = conf.get("parts") or {}
    body, toc = [], []
    seen = set()
    for ch in chapters:
        md = bookconf.read_text(ch.path)
        m = H1_RE.search(md)
        title = m.group(1) if m else ch.title
        if m:
            md = md[:m.start()] + md[m.end():]
        if ch.part not in seen:
            seen.add(ch.part)
            pname = parts_names.get(ch.part)
            if pname:
                body.append('<section class="part front"><h1>%s</h1></section>' % esc(pname))
                toc.append('<li class="toc-part">%s</li>' % esc(pname))
        numbered = ch.number is not None
        kicker = '<div class="kicker">%s %s</div>' % (esc(labels["chapter"]), ch.number) if numbered else ""
        cls = "chapter" + ("" if numbered else " unnumbered") + (" summary" if ch.summary else "")
        body.append('<section class="%s" id="ch-%s"><header class="chapter-head">%s<h1>%s</h1></header>%s</section>'
                    % (cls, esc(ch.key), kicker, esc(title), render_body(md, ch, md_lib, conf, warnings)))
        num = '<span class="num">%s</span>' % ch.number if numbered else '<span class="num"></span>'
        toc.append('<li>%s<a href="#ch-%s">%s</a></li>' % (num, esc(ch.key), esc(title)))

    front = []
    cover = '<section class="cover front"><div class="title">%s</div>' % esc(conf["title"])
    if conf.get("subtitle"):
        cover += '<div class="subtitle">%s</div>' % esc(conf["subtitle"])
    if conf.get("author"):
        cover += '<div class="author">%s</div>' % esc(conf["author"])
    if not release and labels.get("draft"):
        cover += '<div class="draft">%s</div>' % esc(labels["draft"])
    front.append(cover + "</section>")
    if release and conf.get("copyright"):
        lines = "".join("<p>%s</p>" % esc(l) if l else "<p>&nbsp;</p>" for l in conf["copyright"])
        front.append('<section class="copyright front">%s</section>' % lines)
    front.append('<section class="toc front"><h1>%s</h1><ul>%s</ul></section>'
                 % (esc(labels["contents"]), "".join(toc)))

    return ('<!DOCTYPE html>\n<html lang="%s" dir="%s">\n<head>\n<meta charset="utf-8">\n<title>%s</title>\n'
            '<style>%s</style>\n</head>\n<body>\n%s\n</body>\n</html>\n'
            % (esc(conf["lang"]), esc(conf["dir"]), esc(conf["title"]), css(conf, size),
               "\n".join(front + body)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="book folder (default: nearest parent with book.json)")
    ap.add_argument("--size", help="A5, A4, 15x22 or <W>x<H>mm (default: page_size in book.json)")
    ap.add_argument("--parts", help="comma-separated part folder names to include")
    ap.add_argument("--out", help="PDF path (default: build/<output_name>.pdf)")
    ap.add_argument("--html", help="keep the intermediate HTML at this path")
    ap.add_argument("--release", action="store_true", help="print build: copyright page, no draft note")
    args = ap.parse_args(argv)

    try:
        import markdown as md_lib
    except ImportError:
        print("error: the Python 'markdown' package is missing. Run: pip install markdown", file=sys.stderr)
        return 2
    import office

    try:
        conf = bookconf.load(args.root)
        size = parse_size(args.size or conf["page_size"])
        parts = [p.strip() for p in args.parts.split(",") if p.strip()] if args.parts else None
        chapters = bookconf.chapters(conf, parts)
    except bookconf.BookError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    if not chapters:
        print("error: no chapters found", file=sys.stderr)
        return 1

    chrome = office.find_chrome()
    if not chrome and not args.html:
        print("error: Chrome/Chromium not found: install it, set BOOK_CHROME, or pass --html PATH "
              "to write the HTML only", file=sys.stderr)
        return 2

    warnings = []
    try:
        page = build_html(conf, chapters, size, args.release, md_lib, warnings)
    except bookconf.BookError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    for w in warnings:
        print("warning: " + w)

    out = os.path.abspath(args.out or bookconf.build_output(conf, "pdf"))
    if args.html:
        html_path = os.path.abspath(args.html)
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page)
        if not chrome:
            print("error: Chrome/Chromium not found: HTML written to %s, no PDF made "
                  "(install Chrome or set BOOK_CHROME)" % html_path, file=sys.stderr)
            return 2
        return _print_pdf(chrome, html_path, out, size, args.release)
    with tempfile.TemporaryDirectory(prefix="book-pdf-") as tmp:
        html_path = os.path.join(tmp, "book.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page)
        return _print_pdf(chrome, html_path, out, size, args.release)


def _print_pdf(chrome, html_path, out, size, release):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import office
    cmd = [chrome, *office.chrome_flags(), "--no-pdf-header-footer",
           "--run-all-compositor-stages-before-draw", "--virtual-time-budget=10000",
           "--print-to-pdf=" + out, office.file_url(html_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as e:
        print("error: Chrome failed: %s" % e, file=sys.stderr)
        return 2
    if res.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        print("error: Chrome failed (exit %s)\n%s" % (res.returncode, res.stderr[-800:]), file=sys.stderr)
        return 2
    print("PDF: %s" % out)
    print("size: %s x %s mm%s" % (mm(size[0])[:-2], mm(size[1])[:-2], " (release)" if release else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
