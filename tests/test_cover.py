"""Tests for cover_geometry.py and make_cover.py (run on a copy of the sample book)."""
import os
import shutil
import struct
import subprocess
import sys
import zlib

import pytest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLE = os.path.join(SKILL, "examples", "sample-book")
sys.path.insert(0, SCRIPTS)
import cover_geometry  # noqa: E402
import office  # noqa: E402


def make_png(path, w=300, h=430):
    """A plain gradient PNG written with the standard library only."""
    rows = b"".join(b"\x00" + bytes(v for x in range(w) for v in (30, 60 + (y * 100) // h, 90))
                    for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def run(*args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "make_cover.py"), *args],
                          capture_output=True, text=True)


def pdf_size_mm(pdf):
    try:
        from pypdf import PdfReader
        box = PdfReader(pdf).pages[0].mediabox
        return float(box.width) * 25.4 / 72, float(box.height) * 25.4 / 72
    except ImportError:
        pass
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("Page size:"):
                parts = line.split()
                return float(parts[2]) * 25.4 / 72, float(parts[4]) * 25.4 / 72
    return None


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "book"
    shutil.copytree(SAMPLE, dst)
    return dst


def test_geometry_a5():
    w, h = cover_geometry.parse_trim("A5")
    g = cover_geometry.geometry(w, h, pages=200, mm_per_page=0.05, bleed=3.2)
    assert g["spine"] == 10.0
    assert g["total_w"] == pytest.approx(2 * (148 + 3.2) + 10.0)   # 312.4
    assert g["total_h"] == pytest.approx(210 + 2 * 3.2)            # 216.4
    assert g["front_x"] == 0 and g["back_x"] == pytest.approx(151.2 + 10.0)  # RTL: front on the left
    assert g["spine_x"] == pytest.approx(151.2)
    ltr = cover_geometry.geometry(w, h, 200, 0.05, 3.2, rtl=False)
    assert ltr["front_x"] > ltr["back_x"]


def test_geometry_rejects_bad_input():
    with pytest.raises(ValueError):
        cover_geometry.spine_mm(0, 0.05)
    with pytest.raises(ValueError):
        cover_geometry.spine_mm(100, 0)


def need_tools():
    pytest.importorskip("PIL")
    if not office.find_chrome():
        pytest.skip("Chrome/Chromium not found")
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm not found")


def test_build_wrap_and_front(book, tmp_path):
    need_tools()
    make_png(book / "manuscript" / "assets" / "cover-front.png")
    r = run("--root", str(book))
    assert r.returncode == 0, r.stderr + r.stdout
    out = book / "build" / "cover"
    for name in ("cover-wrap.pdf", "cover-wrap.png", "cover-front.png", "cover-front.jpg"):
        assert (out / name).stat().st_size > 0, name
    g = cover_geometry.geometry(148, 210, 120, 0.05, 3.2)   # pages and coefficient from cover.json
    size = pdf_size_mm(str(out / "cover-wrap.pdf"))
    if size is None:
        pytest.skip("neither pypdf nor pdfinfo available")
    assert size[0] == pytest.approx(g["total_w"], abs=0.5)
    assert size[1] == pytest.approx(g["total_h"], abs=0.5)


def test_pages_flag_overrides_spec(book, tmp_path):
    need_tools()
    make_png(book / "manuscript" / "assets" / "cover-front.png")
    out = tmp_path / "out"
    r = run("--root", str(book), "--pages", "300", "--out", str(out))
    assert r.returncode == 0, r.stderr + r.stdout
    g = cover_geometry.geometry(148, 210, 300, 0.05, 3.2)
    size = pdf_size_mm(str(out / "cover-wrap.pdf"))
    if size is None:
        pytest.skip("neither pypdf nor pdfinfo available")
    assert size[0] == pytest.approx(g["total_w"], abs=0.5)
    assert "300 pages" in r.stdout


def test_missing_image_is_a_clear_error(book):
    r = run("--root", str(book))
    assert r.returncode == 2
    assert "front cover image not found" in r.stderr
    assert "Traceback" not in r.stderr


def test_missing_spec_exit_2(book):
    r = run("--root", str(book), "--spec", str(book / "nope.json"))
    assert r.returncode == 2
    assert "not found" in r.stderr
