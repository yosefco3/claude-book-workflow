"""Tests for extract_text.py."""
import os
import shutil
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import extract_text as et  # noqa: E402

CONTAINER = ('<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
OPF = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf"><manifest>'
       '<item id="a" href="one.xhtml"/><item id="b" href="two.xhtml"/></manifest>'
       '<spine><itemref idref="b"/><itemref idref="a"/></spine></package>')


def make_epub(path, long_para):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", OPF)
        z.writestr("OEBPS/one.xhtml", "<html><body><h1>Second</h1><p>Tail.</p></body></html>")
        z.writestr("OEBPS/two.xhtml", "<html><head><title>x</title></head><body><h1>First</h1>"
                   "<h2>Sub</h2><p>%s</p><h3>Deep</h3><p>End.</p></body></html>" % long_para)


def test_epub_spine_headings_wrap(tmp_path):
    p = tmp_path / "b.epub"
    make_epub(p, " ".join(["word"] * 80))
    out = tmp_path / "out" / "b.txt"
    assert et.main([str(p), "-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    lines = text.split("\n")
    assert text.index("# First") < text.index("# Second")  # spine order, not manifest order
    assert "## Sub" in lines and "### Deep" in lines
    assert "x" not in lines  # <head> skipped
    assert max(len(l) for l in lines) <= 100
    assert sum(1 for l in lines if l.startswith("word")) >= 3  # long paragraph was wrapped


def test_txt(tmp_path):
    p = tmp_path / "n.txt"
    p.write_text("# Title\n\n" + " ".join(["abc"] * 60) + "\n", encoding="utf-8")
    out = tmp_path / "n.out.txt"
    assert et.main([str(p), "-o", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "# Title"
    assert max(len(l) for l in lines) <= 100 and len(lines) > 4


def test_default_output_under_book_root(tmp_path, monkeypatch):
    (tmp_path / "book.json").write_text("{}")
    (tmp_path / "sub").mkdir()
    src = tmp_path / "sub" / "s.txt"
    src.write_text("hello\n")
    monkeypatch.chdir(tmp_path / "sub")
    assert et.main([str(src)]) == 0
    assert (tmp_path / ".work" / "texts" / "s.txt").is_file()


def test_missing_pdftotext(tmp_path, monkeypatch, capsys):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert et.main([str(p), "-o", str(tmp_path / "o.txt")]) == 2
    assert "poppler-utils" in capsys.readouterr().err


def test_missing_file_and_bad_type(tmp_path, capsys):
    assert et.main([str(tmp_path / "nope.txt")]) == 2
    p = tmp_path / "a.docx"
    p.write_text("x")
    assert et.main([str(p), "-o", str(tmp_path / "o.txt")]) == 2
