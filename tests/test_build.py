"""Tests for build_book.py, build_pdf.py and init_book.py (run on a copy of the sample book)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLE = os.path.join(SKILL, "examples", "sample-book")


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True)


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "book"
    shutil.copytree(SAMPLE, dst)
    return dst


def test_build_book_order_and_skip(book):
    r = run("build_book.py", "--root", str(book))
    assert r.returncode == 0, r.stderr
    text = (book / "build" / "sample-book.md").read_text(encoding="utf-8")
    order = ["# הקדמה", "# אדמה ועציצים", "# השקיה", "# מה למדנו", "# תבלינים", "# תודות"]
    pos = [text.index(h) for h in order]
    assert pos == sorted(pos)
    assert "רשימות עבודה" not in text
    assert text.startswith("# גינה על המרפסת")
    assert "\n\n---\n\n" in text
    assert (book / "build" / ".build-hash").exists()


def test_build_book_forbidden_char(book):
    ch = book / "manuscript" / "01-basics" / "03-hashkaya.md"
    ch.write_text(ch.read_text(encoding="utf-8") + "\nמילה — מילה\n", encoding="utf-8")
    r = run("build_book.py", "--root", str(book))
    assert r.returncode == 0
    assert "03-hashkaya.md:" in r.stdout and "warning" in r.stdout
    assert (book / "build" / "sample-book.md").exists()
    r = run("build_book.py", "--root", str(book), "--strict")
    assert r.returncode == 3


def test_build_book_hand_edit_guard(book):
    assert run("build_book.py", "--root", str(book)).returncode == 0
    out = book / "build" / "sample-book.md"
    out.write_text(out.read_text(encoding="utf-8") + "edit\n", encoding="utf-8")
    assert run("build_book.py", "--root", str(book)).returncode == 2
    assert run("build_book.py", "--root", str(book), "--force").returncode == 0
    assert "edit\n" not in out.read_text(encoding="utf-8")[-6:]


def test_build_book_no_chapters(tmp_path):
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "book.json").write_text(json.dumps({"title": "x"}))
    assert run("build_book.py", "--root", str(tmp_path)).returncode == 1


@pytest.fixture
def html(book, tmp_path):
    pytest.importorskip("markdown")
    out = tmp_path / "out.html"
    # --html is written before Chrome is looked up, so this works without Chrome too
    run("build_pdf.py", "--root", str(book), "--html", str(out), "--out", str(tmp_path / "x.pdf"))
    assert out.exists()
    return out.read_text(encoding="utf-8")


def test_pdf_html_contents(html):
    assert 'dir="rtl"' in html and 'lang="he"' in html
    assert "תוכן העניינים" in html
    assert "חלק א: יסודות" in html and "חלק ב: צמחים" in html and "נספחים" in html
    assert "טיוטה" in html
    assert 'class="deep"' in html and 'class="sources"' in html
    assert "data:image/png;base64" in html and "<figcaption>" in html
    assert "<strong>" in html and "<blockquote>" in html
    assert "רשימות עבודה" not in html


def _section(html, key):
    start = html.index('id="ch-%s"' % key)
    return html[start:html.index("</section>", start)]


def test_pdf_html_kickers(html):
    assert '<div class="kicker">פרק 2</div>' in _section(html, "2")
    assert "kicker" not in _section(html, "3z")      # summary page
    assert "kicker" not in _section(html, "90")      # back matter (unnumbered part)
    assert html.count('class="kicker"') == 4         # chapters 1 to 4 only


def _chrome():
    sys.path.insert(0, SCRIPTS)
    import office
    return office.find_chrome()


def test_real_pdf(book, tmp_path):
    pytest.importorskip("markdown")
    if not _chrome():
        pytest.skip("no Chrome")
    out = tmp_path / "book.pdf"
    r = run("build_pdf.py", "--root", str(book), "--out", str(out))
    assert r.returncode == 0, r.stderr
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout
        pages = int([l for l in info.splitlines() if l.startswith("Pages:")][0].split()[1])
        assert pages > 5
    elif importlib.util.find_spec("pypdf"):
        import pypdf
        assert len(pypdf.PdfReader(str(out)).pages) > 5
    if shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
        assert "השקיה" in txt


def test_pdf_sizes_and_bad_size(book, tmp_path):
    pytest.importorskip("markdown")
    h = tmp_path / "a4.html"
    run("build_pdf.py", "--root", str(book), "--size", "100x150mm", "--html", str(h), "--out", str(tmp_path / "y.pdf"))
    assert "size: 100mm 150mm" in h.read_text(encoding="utf-8")
    assert run("build_pdf.py", "--root", str(book), "--size", "bogus").returncode == 1


def test_release_copyright(book, tmp_path):
    pytest.importorskip("markdown")
    cfg = json.loads((book / "book.json").read_text(encoding="utf-8"))
    cfg["copyright"] = ["LINE-ONE-XYZ"]
    (book / "book.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    a, b = tmp_path / "a.html", tmp_path / "b.html"
    run("build_pdf.py", "--root", str(book), "--html", str(a), "--out", str(tmp_path / "a.pdf"))
    run("build_pdf.py", "--root", str(book), "--release", "--html", str(b), "--out", str(tmp_path / "b.pdf"))
    assert "LINE-ONE-XYZ" not in a.read_text(encoding="utf-8")
    t = b.read_text(encoding="utf-8")
    assert "LINE-ONE-XYZ" in t and "טיוטה" not in t


def test_init_book(tmp_path):
    d = tmp_path / "new"
    r = run("init_book.py", str(d), "--title", "My Book", "--author", "Me", "--lang", "en")
    assert r.returncode == 0, r.stderr
    conf = json.loads((d / "book.json").read_text(encoding="utf-8"))
    assert conf["dir"] == "ltr" and conf["labels"]["chapter"] == "Chapter"
    assert conf["title"] == "My Book" and conf["forbidden_chars"] == []
    assert (d / "manuscript" / "00-front" / "01-intro.md").read_text(encoding="utf-8").startswith("# ")
    assert (d / "manuscript" / "assets").is_dir()
    assert "review/" in (d / ".gitignore").read_text()
    assert run("init_book.py", str(d), "--title", "Again").returncode == 2
    # the new book builds
    assert run("build_book.py", "--root", str(d)).returncode == 0


def test_init_book_keeps_existing_files(tmp_path):
    """An existing CLAUDE.md, .gitignore or style sheet is never overwritten."""
    import json
    (tmp_path / "docs").mkdir()
    for rel in ("CLAUDE.md", ".gitignore", "docs/STYLE.md"):
        (tmp_path / rel).write_text("MINE\n", encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_book.py"), str(tmp_path),
                        "--title", "T"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for rel in ("CLAUDE.md", ".gitignore", "docs/STYLE.md"):
        assert (tmp_path / rel).read_text(encoding="utf-8") == "MINE\n"
        assert "kept existing " + rel in r.stdout
    conf = json.loads((tmp_path / "book.json").read_text(encoding="utf-8"))
    assert "language_fixes" not in conf  # the skill asks the author and records the answer


# ---------------------------------------------------------------- robustness

def test_malformed_book_json_reports_position(book):
    (book / "book.json").write_text('{\n  "title": "x",\n  "bad": ,\n}', encoding="utf-8")
    for script in ("build_book.py", "build_pdf.py"):
        r = run(script, "--root", str(book))
        assert r.returncode == 2, script
        assert "line 3" in r.stderr and "Traceback" not in r.stderr


def test_bom_chapter_is_read(book):
    ch = book / "manuscript" / "01-basics" / "03-hashkaya.md"
    ch.write_bytes(b"\xef\xbb\xbf" + ch.read_bytes())
    assert run("build_book.py", "--root", str(book)).returncode == 0
    text = (book / "build" / "sample-book.md").read_text(encoding="utf-8")
    assert "﻿" not in text and "# השקיה" in text


def test_non_utf8_chapter_is_a_clean_error(book):
    ch = book / "manuscript" / "01-basics" / "03-hashkaya.md"
    ch.write_bytes("# שלום\n".encode("windows-1255"))
    r = run("build_book.py", "--root", str(book))
    assert r.returncode == 2 and "03-hashkaya.md" in r.stderr and "Traceback" not in r.stderr


def test_natural_order_and_zero_keys(book):
    sys.path.insert(0, SCRIPTS)
    import bookconf
    ms = book / "manuscript"
    shutil.rmtree(ms / "02-plants")
    (ms / "99-back").rename(ms / "10-back")
    (ms / "9-extra").mkdir()
    (ms / "9-extra" / "9-a.md").write_text("# nine\n", encoding="utf-8")
    (ms / "10-back" / "10-b.md").write_text("# ten\n", encoding="utf-8")
    (ms / "00-front" / "00z-zero.md").write_text("# zero z\n", encoding="utf-8")
    conf = bookconf.load(str(book))
    assert bookconf.part_dirs(conf) == ["00-front", "01-basics", "9-extra", "10-back"]
    keys = [c.key for c in bookconf.chapters(conf)]
    assert keys.index("9") < keys.index("10")
    assert bookconf.resolve(conf, "00z").title == "zero z"
    assert bookconf.resolve(conf, "0z").title == "zero z"


def test_forbidden_line_numbers_count_leading_blank_lines(book):
    ch = book / "manuscript" / "01-basics" / "03-hashkaya.md"
    ch.write_text("\n\n\n# השקיה\n\nמילה — מילה\n", encoding="utf-8")
    r = run("build_book.py", "--root", str(book))
    assert "03-hashkaya.md:6:" in r.stdout


def _no_chrome(monkeypatch):
    sys.path.insert(0, SCRIPTS)
    import office
    monkeypatch.setattr(office, "find_chrome", lambda: None)
    import build_pdf
    return build_pdf


def test_pdf_without_chrome_stops_before_building(book, tmp_path, monkeypatch, capsys):
    pytest.importorskip("markdown")
    build_pdf = _no_chrome(monkeypatch)
    monkeypatch.setattr(build_pdf, "build_html", lambda *a, **k: pytest.fail("built without Chrome"))
    assert build_pdf.main(["--root", str(book), "--out", str(tmp_path / "x.pdf")]) == 2
    assert ("Chrome/Chromium not found: install it, set BOOK_CHROME, or pass --html PATH "
            "to write the HTML only") in capsys.readouterr().err
    assert not (tmp_path / "x.pdf").exists()


def test_pdf_without_chrome_but_with_html_writes_html(book, tmp_path, monkeypatch, capsys):
    pytest.importorskip("markdown")
    build_pdf = _no_chrome(monkeypatch)
    h = tmp_path / "out" / "b.html"
    assert build_pdf.main(["--root", str(book), "--html", str(h)]) == 2
    assert h.exists() and "HTML written" in capsys.readouterr().err


def test_chrome_failure_cleans_temp_dir(book, tmp_path, monkeypatch):
    pytest.importorskip("markdown")
    sys.path.insert(0, SCRIPTS)
    import office
    import build_pdf
    import tempfile
    monkeypatch.setattr(office, "find_chrome", lambda: "/bin/false")
    made = []
    real = tempfile.TemporaryDirectory

    class Spy(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made.append(self.name)

    monkeypatch.setattr(build_pdf.tempfile, "TemporaryDirectory", Spy)
    assert build_pdf.main(["--root", str(book), "--out", str(tmp_path / "x.pdf")]) == 2
    assert made and not os.path.exists(made[0])
