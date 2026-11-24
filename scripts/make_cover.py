#!/usr/bin/env python3
"""Build a print-ready Hebrew (RTL) book cover: back + spine + front in one PDF, plus the front alone.

Usage (run from anywhere inside a book, or pass --root):
    python3 make_cover.py [--root BOOK] [--spec PATH] [--pages N] [--out DIR] [--cmyk]
                          [--dpi 300] [--prefix cover] [--keep-html]

Reads the cover spec from <manuscript_dir>/cover/cover.json of the book (see bookconf.py) and writes
to <book>/build/cover/ by default:
    <prefix>-wrap.pdf       the full wrap for the printer (RGB; exact page size in mm)
    <prefix>-wrap-cmyk.pdf  only with --cmyk (needs Ghostscript; skipped with a message if missing)
    <prefix>-wrap.png       preview of the whole wrap
    <prefix>-front.png/.jpg front cover alone (trim area, no bleed) for digital use

Page count: --pages, else the page count of build/<output_name>.pdf if it exists, else "pages" in
cover.json. Spine width = pages x "mm_per_page" (paper thickness per page, from your printer).

Pipeline: JSON -> HTML (RTL, Noto Hebrew fonts) -> PDF (Chrome/Chromium headless, page size in mm)
          -> preview PNG (pdftoppm) -> front-only PNG + JPG (crop with Pillow).

Spec fields (title, author, front_image are required; pages or --pages is required):
{
  "title": "...", "subtitle": "...", "author": "...",
  "front_image": "../assets/cover-front.png",   # relative to the spec folder or to the book root
  "trim": "A5", "pages": 200, "mm_per_page": 0.05, "bleed": 3.2, "safe": 6,
  "spine_rotation": -90,                         # -90 Hebrew (head tilts left), 90 left-to-right books
  "back": {"headline": "...", "paragraphs": ["..."], "tagline": "..."},
  "isbn": null,                                  # 12 or 13 digits draws an EAN-13 barcode on the back
  "colors": {"bg": "#1d2a3a", "text": "#f6efe1", "accent": "#c9a55a", "scrim": 0.55},
  "fonts": {"title": "Noto Serif Hebrew", "body": "Noto Sans Hebrew"},
  "sizes": {"title": 0.19, "subtitle": 0.045, "author": 0.055}   # ratio of the trim width
}
Exit codes: 0 ok, 1 a tool failed (Chrome, pdftoppm, Pillow), 2 bad input (spec, image, pages).
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402
import office  # noqa: E402
from cover_geometry import DEFAULT_MM_PER_PAGE, geometry, parse_trim  # noqa: E402

DEFAULTS = {
    "subtitle": "", "trim": "A5", "mm_per_page": None,
    "bleed": 3.2, "safe": 6.0, "spine_rotation": -90, "isbn": None,
    "back": {"headline": "", "paragraphs": [], "tagline": ""},
    "colors": {"bg": "#1d2a3a", "text": "#f6efe1", "accent": "#c9a55a", "scrim": 0.55},
    "fonts": {"title": "Noto Serif Hebrew", "body": "Noto Sans Hebrew"},
    "sizes": {"title": 0.19, "subtitle": 0.045, "author": 0.055},
}


class InputError(Exception):
    """Bad spec, missing image or page count: exit code 2."""


class ToolError(Exception):
    """A required external tool is missing or failed: exit code 1."""


# ---------- EAN-13 ----------
_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
_R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_checksum(digits12):
    s = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits12))
    return str((10 - s % 10) % 10)


def ean13_bits(code):
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) == 12:
        code += ean13_checksum(code)
    if len(code) != 13 or ean13_checksum(code[:12]) != code[12]:
        raise ValueError(f"invalid ISBN/EAN-13: {code!r}")
    first, left, right = code[0], code[1:7], code[7:]
    bits = "101"
    for d, p in zip(left, _PARITY[int(first)]):
        bits += (_L if p == "L" else _G)[int(d)]
    bits += "01010"
    for d in right:
        bits += _R[int(d)]
    return code, bits + "101"


def ean13_svg(code, width_mm=37.0, height_mm=22.0):
    code, bits = ean13_bits(code)
    module = width_mm / (len(bits) + 14)   # quiet zone on both sides
    x0 = module * 7
    bar_h = height_mm - 5
    rects = []
    for i, b in enumerate(bits):
        if b == "1":
            guard = i < 3 or 45 <= i < 50 or i >= len(bits) - 3
            rects.append(f'<rect x="{x0 + i * module:.3f}" y="0" width="{module:.3f}" '
                         f'height="{bar_h + (1.5 if guard else 0):.2f}"/>')
    label = f"{code[0]} {code[1:7]} {code[7:]}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" '
            f'viewBox="0 0 {width_mm} {height_mm}" font-family="DejaVu Sans, Arial" direction="ltr">'
            f'<rect width="{width_mm}" height="{height_mm}" fill="#fff"/><g fill="#000">{"".join(rects)}</g>'
            f'<text x="{width_mm / 2:.2f}" y="{height_mm - 1.2:.2f}" font-size="3" text-anchor="middle">{label}</text></svg>')


# ---------- HTML ----------
def esc(s):
    return html.escape(str(s or ""))


def esc_br(s):
    """Like esc, but a newline in the spec becomes <br> (manual line breaks in titles)."""
    return "<br>".join(esc(line) for line in str(s or "").split("\n"))


def build_html(spec, g, front_image_path):
    c, f, sz = spec["colors"], spec["fonts"], spec["sizes"]
    tw = g["trim_w"]
    title_pt = tw * sz["title"]
    inset_o, inset_s, inset_v = g["safe_inset_outer"], g["safe_inset_spine"], g["safe_inset_v"]
    # RTL: front on the left (outer edge left, spine right)
    front_pad = f"{inset_v}mm {inset_s}mm {inset_v}mm {inset_o}mm"
    back_pad = f"{inset_v}mm {inset_o}mm {inset_v}mm {inset_s}mm"
    if not g["rtl"]:
        front_pad, back_pad = back_pad, front_pad
    back = spec["back"]
    paras = "".join(f"<p>{esc(p)}</p>" for p in back.get("paragraphs", []))
    barcode = ""
    if spec.get("isbn"):
        barcode = f'<div class="barcode">{ean13_svg(spec["isbn"])}</div>'
    spine_title = str(spec["title"]).replace("\n", " ")
    rot = float(spec["spine_rotation"])
    spine_fs = min(g["spine"] * 0.5, 10.0)  # mm
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<style>
@page {{ size: {g['total_w']}mm {g['total_h']}mm; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
body {{ width: {g['total_w']}mm; height: {g['total_h']}mm; overflow: hidden; direction: rtl;
       font-family: "{f['body']}", "Noto Sans Hebrew", sans-serif; color: {c['text']};
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.wrap {{ position: relative; width: {g['total_w']}mm; height: {g['total_h']}mm; background: {c['bg']}; }}
.panel {{ position: absolute; top: 0; height: {g['total_h']}mm; box-sizing: border-box; overflow: hidden; }}
.front {{ left: {g['front_x']}mm; width: {g['panel_w']}mm; padding: {front_pad};
          background: {c['bg']} url("{front_image_path}") center / cover no-repeat;
          display: flex; flex-direction: column; justify-content: space-between; align-items: center; text-align: center; }}
.front::before {{ content: ""; position: absolute; inset: 0;
          background: linear-gradient(to bottom, rgba(0,0,0,{c['scrim']}) 0%, rgba(0,0,0,0) 38%, rgba(0,0,0,0) 72%, rgba(0,0,0,{c['scrim']}) 100%); }}
.front > * {{ position: relative; }}
.title {{ font-family: "{f['title']}", "Noto Serif Hebrew", serif; font-weight: bold; font-size: {title_pt:.2f}mm;
          line-height: 1.05; margin: {tw * 0.03:.2f}mm 0 0 0; text-shadow: 0 0.6mm 2mm rgba(0,0,0,0.55); letter-spacing: -0.01em; }}
.subtitle {{ font-size: {tw * sz['subtitle']:.2f}mm; line-height: 1.35; margin: {tw * 0.02:.2f}mm 0 0 0;
          text-shadow: 0 0.4mm 1.5mm rgba(0,0,0,0.6); max-width: 92%; }}
.author {{ font-family: "{f['title']}", serif; font-size: {tw * sz['author']:.2f}mm; margin: 0 0 {tw * 0.02:.2f}mm 0;
          text-shadow: 0 0.4mm 1.5mm rgba(0,0,0,0.6); }}
.author::before {{ content: ""; display: block; width: {tw * 0.18:.1f}mm; height: 0.5mm; background: {c['accent']}; margin: 0 auto {tw * 0.02:.2f}mm auto; }}
.spine {{ left: {g['spine_x']}mm; width: {g['spine']}mm; background: {c['bg']}; }}
.spine-inner {{ position: absolute; left: {g['spine_x'] + g['spine'] / 2 - g['total_h'] / 2:.3f}mm; top: {g['total_h'] / 2 - g['spine'] / 2:.3f}mm;
          width: {g['total_h']}mm; height: {g['spine']}mm; transform: rotate({rot}deg);
          display: flex; align-items: center; justify-content: space-between; direction: rtl;
          padding: 0 {inset_v + 4}mm; box-sizing: border-box; white-space: nowrap; font-size: {spine_fs:.2f}mm; line-height: 1; }}
.spine-inner .t {{ font-family: "{f['title']}", serif; font-weight: bold; }}
.spine-inner .a {{ font-size: {spine_fs * 0.72:.2f}mm; }}
.back {{ left: {g['back_x']}mm; width: {g['panel_w']}mm; padding: {back_pad}; background: {c['bg']};
         display: flex; flex-direction: column; text-align: right; }}
.back h2 {{ font-family: "{f['title']}", serif; font-size: {tw * 0.055:.2f}mm; line-height: 1.25; margin: {tw * 0.04:.2f}mm 0 {tw * 0.025:.2f}mm 0; color: {c['accent']}; }}
.back p {{ font-size: {tw * 0.028:.2f}mm; line-height: 1.55; margin: 0 0 {tw * 0.018:.2f}mm 0; max-width: 88%; }}
.back .tagline {{ margin-top: auto; font-family: "{f['title']}", serif; font-style: italic; font-size: {tw * 0.032:.2f}mm; color: {c['accent']}; }}
.back .byline {{ font-size: {tw * 0.026:.2f}mm; opacity: 0.85; margin-top: {tw * 0.012:.2f}mm; }}
.barcode {{ position: absolute; left: {inset_o + 2 if g['rtl'] else inset_s + 2}mm; bottom: {inset_v + 2}mm; line-height: 0; }}
</style></head><body><div class="wrap">
<div class="panel front">
  <div><div class="title">{esc_br(spec['title'])}</div>{f'<div class="subtitle">{esc_br(spec["subtitle"])}</div>' if spec.get('subtitle') else ''}</div>
  <div class="author">{esc(spec['author'])}</div>
</div>
<div class="panel spine"></div>
<div class="spine-inner"><span class="t">{esc(spine_title)}</span><span class="a">{esc(spec['author'])}</span></div>
<div class="panel back">
  {f'<h2>{esc_br(back.get("headline"))}</h2>' if back.get('headline') else ''}
  {paras}
  {f'<div class="tagline">{esc(back.get("tagline"))}</div>' if back.get('tagline') else ''}
  <div class="byline">{esc(spec['author'])}</div>
  {barcode}
</div>
</div></body></html>"""


# ---------- pipeline ----------
def load_spec(path, conf=None):
    try:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
    except FileNotFoundError:
        raise InputError(f"cover spec not found: {path}")
    except json.JSONDecodeError as e:
        raise InputError(f"cover spec is not valid JSON ({path}): {e}")
    spec = json.loads(json.dumps(DEFAULTS))
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(spec.get(k), dict):
            spec[k].update(v)
        else:
            spec[k] = v
    if conf:   # title / author fall back to book.json
        for k in ("title", "author"):
            if not spec.get(k):
                spec[k] = conf.get(k, "")
    for k in ("title", "author", "front_image"):
        if not spec.get(k):
            raise InputError(f"required field missing in the cover spec: {k}")
    base = os.path.dirname(os.path.abspath(path))
    img = spec["front_image"]
    roots = [base, conf["_root"] if conf else os.getcwd()]
    candidates = [img] if os.path.isabs(img) else [os.path.join(r, img) for r in roots]
    for cnd in candidates:
        if os.path.isfile(cnd):
            spec["front_image"] = os.path.abspath(cnd)
            break
    else:
        raise InputError(
            f"front cover image not found: {img} (looked relative to {', '.join(roots)}). "
            "Save the illustration there, see references/cover.md, section 'The front image'.")
    return spec


def count_pdf_pages(pdf):
    """Page count of a PDF via pypdf or pdfinfo; None when neither can read it."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf).pages)
    except Exception:
        pass
    if shutil.which("pdfinfo"):
        r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    return None


def resolve_pages(cli_pages, spec, conf):
    """(pages, where it came from)."""
    if cli_pages:
        return int(cli_pages), "--pages"
    pdf = bookconf.build_output(conf, "pdf")
    if os.path.isfile(pdf):
        n = count_pdf_pages(pdf)
        if n:
            return n, os.path.relpath(pdf, conf["_root"])
    if spec.get("pages"):
        return int(spec["pages"]), "cover.json"
    raise InputError("no page count: pass --pages, build the book PDF first, or set \"pages\" in cover.json")


def chrome_pdf(html_path, out_pdf):
    chrome = office.find_chrome()
    if not chrome:
        raise ToolError("Chrome/Chromium not found (set BOOK_CHROME to its path)")
    with tempfile.TemporaryDirectory() as profile:
        cmd = [chrome, *office.chrome_flags(), "--no-pdf-header-footer",
               f"--user-data-dir={profile}", "--run-all-compositor-stages-before-draw",
               "--virtual-time-budget=10000",
               f"--print-to-pdf={os.path.abspath(out_pdf)}", office.file_url(html_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_pdf):
        raise ToolError("Chrome PDF conversion failed:\n" + r.stderr)


def to_cmyk(src_pdf, out_pdf):
    """Optional CMYK copy through Ghostscript. Returns True if written, False if skipped."""
    gs = shutil.which("gs") or shutil.which("gswin64c")
    if not gs:
        print("note: --cmyk skipped, Ghostscript (gs) not found; the RGB PDF is still written")
        return False
    r = subprocess.run([gs, "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
                        "-sColorConversionStrategy=CMYK", "-dProcessColorModel=/DeviceCMYK",
                        f"-sOutputFile={out_pdf}", src_pdf], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_pdf):
        print("note: --cmyk failed, the RGB PDF is still written:\n" + r.stderr)
        return False
    return True


def render(spec, out_dir, prefix="cover", dpi=300, keep_html=False, cmyk=False):
    try:
        from PIL import Image
    except ImportError:
        raise ToolError("Pillow is required (pip install pillow)")
    if not shutil.which("pdftoppm"):
        raise ToolError("pdftoppm (poppler-utils) is required")
    tw, th = parse_trim(spec["trim"])
    g = geometry(tw, th, int(spec["pages"]), spec["mm_per_page"],
                 float(spec["bleed"]), float(spec["safe"]), rtl=spec.get("rtl", True))
    os.makedirs(out_dir, exist_ok=True)
    html_text = build_html(spec, g, office.file_url(spec["front_image"]))
    out_pdf = os.path.join(out_dir, f"{prefix}-wrap.pdf")
    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "cover.html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        if keep_html:
            shutil.copy(html_path, os.path.join(out_dir, f"{prefix}-wrap.html"))
        chrome_pdf(html_path, out_pdf)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", out_pdf, os.path.join(td, "wrap")],
                       check=True)
        im = Image.open(os.path.join(td, "wrap.png")).convert("RGB")
    px = dpi / 25.4
    preview = im.resize((1200, int(im.height * 1200 / im.width)), Image.LANCZOS)
    preview.save(os.path.join(out_dir, f"{prefix}-wrap.png"))
    # Trim area of the front panel (bleed cut off)
    fx = g["front_x"] + (g["bleed"] if g["rtl"] else 0.0)
    box = (int(fx * px), int(g["bleed"] * px), int((fx + tw) * px), int((g["bleed"] + th) * px))
    front = im.crop(box)
    front.save(os.path.join(out_dir, f"{prefix}-front.png"))
    front.save(os.path.join(out_dir, f"{prefix}-front.jpg"), quality=92)
    cmyk_pdf = None
    if cmyk:
        cmyk_pdf = os.path.join(out_dir, f"{prefix}-wrap-cmyk.pdf")
        if not to_cmyk(out_pdf, cmyk_pdf):
            cmyk_pdf = None
    return g, out_pdf, cmyk_pdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="book folder (default: the folder holding book.json, searched upward)")
    ap.add_argument("--spec", default=None, help="cover spec (default: <manuscript_dir>/cover/cover.json)")
    ap.add_argument("--pages", type=int, default=None, help="page count (overrides the PDF and the spec)")
    ap.add_argument("--out", default=None, help="output folder (default: <book>/build/cover)")
    ap.add_argument("--cmyk", action="store_true", help="also write a CMYK PDF with Ghostscript (optional)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--prefix", default=None, help="output file prefix (default: out_prefix in the spec, else cover)")
    ap.add_argument("--keep-html", action="store_true")
    a = ap.parse_args()
    try:
        try:
            conf = bookconf.load(a.root)
        except (bookconf.BookError, OSError) as e:
            raise InputError(str(e))
        spec_path = a.spec or bookconf.path(conf, "manuscript_dir", "cover", "cover.json")
        spec = load_spec(spec_path, conf)
        spec["pages"], source = resolve_pages(a.pages, spec, conf)
        if spec["pages"] < 1:
            raise InputError("page count must be positive")
        if spec.get("mm_per_page") in (None, 0):
            spec["mm_per_page"] = DEFAULT_MM_PER_PAGE
            print(f"warning: no mm_per_page in the spec, using the draft value {DEFAULT_MM_PER_PAGE} mm. "
                  "Take the real value from your printer before sending the file.")
        out_dir = a.out or os.path.join(conf["_root"], conf["build_dir"], "cover")
        prefix = a.prefix or spec.get("out_prefix", "cover")
        try:
            g, out_pdf, cmyk_pdf = render(spec, out_dir, prefix, a.dpi, a.keep_html, a.cmyk)
        except ValueError as e:
            raise InputError(str(e))
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ToolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"written: {out_pdf}")
    if cmyk_pdf:
        print(f"written: {cmyk_pdf}")
    print(f"size: {g['total_w']} x {g['total_h']} mm | spine {g['spine']} mm | trim {g['trim_w']}x{g['trim_h']} | "
          f"bleed {g['bleed']} | {g['pages']} pages ({source}) x {g['mm_per_page']} mm")
    print(f"also: {prefix}-wrap.png, {prefix}-front.png, {prefix}-front.jpg in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
