#!/usr/bin/env python3
"""Full-wrap book cover geometry (back + spine + front) in millimetres.

As a module:
    from cover_geometry import geometry
    g = geometry(trim_w=148, trim_h=210, pages=200, mm_per_page=0.05, bleed=3.2)

From the command line (prints the dimensions as JSON):
    python3 cover_geometry.py --trim A5 --pages 200 --mm-per-page 0.05 --bleed 3.2

The spine width is pages x mm_per_page. The paper thickness per page (mm_per_page) comes from
the printer's cover calculator or spec sheet and differs between papers and printers: always
take it from yours. DEFAULT_MM_PER_PAGE is only a rough placeholder for drafts.
"""
import argparse
import json

# Rough placeholder for drafts (about 80 gsm uncoated). Not a fact about any printer.
DEFAULT_MM_PER_PAGE = 0.05

# Common trim sizes (width, height) in mm.
TRIM_PRESETS_MM = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "B5": (176.0, 250.0),
    "6x9": (152.4, 228.6),
    "5.5x8.5": (139.7, 215.9),
    "5x8": (127.0, 203.2),
    "15.5x23.5": (155.0, 235.0),
    "17x24": (170.0, 240.0),
}

MM_TO_PT = 72.0 / 25.4


def parse_trim(value):
    """'A5' | '17x24' | '155x235' | (w, h) -> (w_mm, h_mm)."""
    if isinstance(value, (tuple, list)):
        w, h = value
        return float(w), float(h)
    key = str(value).strip()
    if key in TRIM_PRESETS_MM:
        return TRIM_PRESETS_MM[key]
    if "x" in key.lower():
        w, h = key.lower().split("x", 1)
        return float(w), float(h)
    raise ValueError(f"unknown trim size: {value!r}")


def spine_mm(pages, mm_per_page=DEFAULT_MM_PER_PAGE):
    """Spine width in mm: pages x paper thickness per page."""
    if pages < 1:
        raise ValueError("page count must be positive")
    if mm_per_page is None or mm_per_page <= 0:
        raise ValueError("mm_per_page must be a positive number")
    return round(pages * mm_per_page, 2)


def geometry(trim_w, trim_h, pages, mm_per_page=DEFAULT_MM_PER_PAGE, bleed=3.0, safe=6.0, rtl=True):
    """All dimensions in mm. Origin: top-left corner of the file, bleed included.

    rtl=True (Hebrew book): front on the left, spine in the middle, back on the right.
    rtl=False (left-to-right book): back on the left, front on the right.
    """
    spine = spine_mm(pages, mm_per_page)
    panel_w = trim_w + bleed          # each panel carries one outer bleed
    total_w = 2 * panel_w + spine
    total_h = trim_h + 2 * bleed
    left_x, right_x, spine_x = 0.0, panel_w + spine, panel_w
    front_x, back_x = (left_x, right_x) if rtl else (right_x, left_x)
    return {
        "trim_w": trim_w, "trim_h": trim_h,
        "pages": pages, "mm_per_page": mm_per_page,
        "bleed": bleed, "safe": safe, "rtl": rtl,
        "spine": spine,
        "panel_w": panel_w,
        "total_w": round(total_w, 2), "total_h": round(total_h, 2),
        "total_w_pt": round(total_w * MM_TO_PT, 2), "total_h_pt": round(total_h * MM_TO_PT, 2),
        "front_x": front_x, "spine_x": spine_x, "back_x": back_x,
        # Safe text area of each panel: bleed + safe from the outer trim line, safe from the spine
        "safe_inset_outer": bleed + safe,
        "safe_inset_spine": safe,
        "safe_inset_v": bleed + safe,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trim", default="A5", help="A4 | A5 | 6x9 | 17x24 | 155x235 ...")
    ap.add_argument("--pages", type=int, required=True)
    ap.add_argument("--mm-per-page", type=float, default=DEFAULT_MM_PER_PAGE,
                    help="paper thickness per page in mm, from your printer")
    ap.add_argument("--bleed", type=float, default=3.0)
    ap.add_argument("--safe", type=float, default=6.0)
    ap.add_argument("--ltr", action="store_true", help="left-to-right book: front on the right")
    a = ap.parse_args()
    w, h = parse_trim(a.trim)
    print(json.dumps(geometry(w, h, a.pages, a.mm_per_page, a.bleed, a.safe, not a.ltr),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
