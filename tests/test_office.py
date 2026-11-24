"""Tests for scripts/office.py. Run from the skill root: python3 -m pytest tests/test_office.py -q"""
import importlib.util
import os
import shutil
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("office", os.path.join(ROOT, "scripts", "office.py"))
office = importlib.util.module_from_spec(spec)
spec.loader.exec_module(office)


def fake_pid(proc, pid, comm, args, cwd=None):
    d = proc / str(pid)
    d.mkdir(parents=True)
    (d / "comm").write_text(comm + "\n")
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in args) + b"\0")
    if cwd is not None:
        (d / "cwd").symlink_to(cwd)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("BOOK_EDITOR_PROCS", raising=False)
    monkeypatch.delenv("BOOK_OFFICE", raising=False)


@pytest.fixture
def env(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "chapter-one-draft.docx"
    f.write_text("x")
    return proc, docs, f


# ---- is_open: process scan

def test_absolute_match(env):
    proc, docs, f = env
    fake_pid(proc, 11, "wordcraft", ["wordcraft", str(f)])
    assert office.is_open(str(f), proc_root=str(proc)) == "wordcraft"


def test_relative_match_via_cwd(env):
    proc, docs, f = env
    fake_pid(proc, 12, "wordcraft", ["wordcraft", f.name], cwd=docs)
    assert office.is_open(str(f), proc_root=str(proc)) == "wordcraft"


def test_cli_does_not_count(env):
    proc, docs, f = env
    fake_pid(proc, 13, "wordcraft-cli", ["wordcraft-cli", str(f)])
    assert office.is_open(str(f), proc_root=str(proc)) is None


def test_other_file_not_matched(env):
    proc, docs, f = env
    fake_pid(proc, 14, "wordcraft", ["wordcraft", str(docs / "other.docx")])
    assert office.is_open(str(f), proc_root=str(proc)) is None


def test_no_args_is_uncertain(env):
    proc, docs, f = env
    fake_pid(proc, 15, "wordcraft", ["wordcraft", "--some-flag"])
    assert office.is_open(str(f), proc_root=str(proc)) == "wordcraft?"


def test_zombie_ignored(env):
    proc, docs, f = env
    d = proc / "16"
    d.mkdir()
    (d / "comm").write_text("wordcraft\n")
    (d / "cmdline").write_bytes(b"")
    assert office.is_open(str(f), proc_root=str(proc)) is None


def test_unreadable_pid_skipped(env):
    proc, docs, f = env
    (proc / "17").mkdir()  # no comm file at all
    fake_pid(proc, 18, "wordcraft", ["wordcraft", str(f)])
    assert office.is_open(str(f), proc_root=str(proc)) == "wordcraft"


def test_custom_editor_proc(env, monkeypatch):
    proc, docs, f = env
    fake_pid(proc, 19, "myeditor", ["myeditor", str(f)])
    assert office.is_open(str(f), proc_root=str(proc)) is None
    monkeypatch.setenv("BOOK_EDITOR_PROCS", "myeditor, other")
    assert office.is_open(str(f), proc_root=str(proc)) == "myeditor"


# ---- is_open: lock files

def test_libreoffice_lock(env):
    proc, docs, f = env
    (docs / (".~lock.%s#" % f.name)).write_text("x")
    assert office.is_open(str(f), proc_root=str(proc)) == "libreoffice"


def test_word_owner_file_long_name(env):
    proc, docs, f = env
    (docs / ("~$" + f.name[2:])).write_text("x")
    assert office.is_open(str(f), proc_root=str(proc)) == "word"


def test_word_owner_file_short_name(tmp_path):
    f = tmp_path / "abc.docx"
    f.write_text("x")
    (tmp_path / "~$abc.docx").write_text("x")
    assert office.is_open(str(f), proc_root=str(tmp_path / "noproc")) == "word"


def test_closed(env):
    proc, docs, f = env
    assert office.is_open(str(f), proc_root=str(proc)) is None


# ---- detect

def test_detect_keys_and_json():
    import json
    info = office.detect()
    for k in ("os", "editors", "docx_to_pdf", "svg_to_png", "html_to_pdf", "docx_text"):
        assert k in info
    assert info["docx_text"] == "builtin"
    json.dumps(info)


def test_detect_finds_fake_soffice(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    fake = bin_ / "soffice"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_))
    info = office.detect()
    assert {"name": "LibreOffice", "path": str(fake)} in info["editors"]
    assert "libreoffice" in info["docx_to_pdf"]


# ---- convert

def make_docx(path):
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>'
        '<w:p><w:r><w:t>שלום עולם</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>ראשון</w:t></w:r><w:r><w:tab/></w:r>'
        '<w:del w:id="1"><w:r><w:delText>נמחק</w:delText></w:r></w:del>'
        '<w:ins w:id="2"><w:r><w:t>נוסף</w:t></w:r></w:ins></w:p>'
        '</w:body></w:document>' % ns)
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.document.main+xml"/></Types>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", body)


def test_docx_to_txt(tmp_path):
    src = tmp_path / "a.docx"
    make_docx(src)
    out = office.convert(str(src), "txt", outdir=str(tmp_path / "o"))
    assert out == str(tmp_path / "o" / "a.txt")
    text = open(out, encoding="utf-8").read()
    assert text == "שלום עולם\nראשון\tנוסף"
    assert "נמחק" not in text
    assert office.docx_text(str(src)) == text


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice not installed")
def test_docx_to_pdf_libreoffice(tmp_path):
    src = tmp_path / "a.docx"
    make_docx(src)
    out = office.convert(str(src), "pdf", tool="libreoffice")
    assert out.endswith("a.pdf") and open(out, "rb").read(4) == b"%PDF"


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
       '<rect width="200" height="100" fill="#888"/></svg>')


def test_svg_to_png(tmp_path):
    if not (shutil.which("rsvg-convert") or shutil.which("inkscape") or shutil.which("soffice")
            or office.find_chrome() or office._has_module("cairosvg")):
        pytest.skip("no SVG converter installed")
    src = tmp_path / "a.svg"
    src.write_text(SVG)
    out = office.convert(str(src), "png")
    assert open(out, "rb").read(4) == b"\x89PNG"


def test_html_to_pdf(tmp_path):
    if not office.find_chrome():
        pytest.skip("Chrome not installed")
    src = tmp_path / "a.html"
    src.write_text("<html><body><p>hello</p></body></html>")
    out = office.convert(str(src), "pdf")
    assert open(out, "rb").read(4) == b"%PDF"


def test_no_tool_raises(tmp_path, monkeypatch):
    src = tmp_path / "a.docx"
    make_docx(src)
    monkeypatch.setattr(office.shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(office, "_find_soffice", lambda: None)
    monkeypatch.setattr(office, "_word_via_docx2pdf", lambda: False)
    with pytest.raises(office.OfficeError) as e:
        office.convert(str(src), "pdf")
    assert "LibreOffice" in str(e.value)


def test_md_to_docx_points_to_md2docx(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("# x")
    with pytest.raises(office.OfficeError) as e:
        office.convert(str(src), "docx")
    assert "md2docx" in str(e.value)


def test_no_sandbox_only_for_root_or_env(monkeypatch):
    monkeypatch.delenv("BOOK_CHROME_NO_SANDBOX", raising=False)
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    assert "--no-sandbox" not in office.chrome_flags()
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert "--no-sandbox" in office.chrome_flags()
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setenv("BOOK_CHROME_NO_SANDBOX", "1")
    assert "--no-sandbox" in office.chrome_flags()


def test_file_url_escapes_special_characters(tmp_path):
    d = tmp_path / "my book #1 ? עברית"
    d.mkdir()
    f = d / "a b.html"
    f.write_text("x")
    url = office.file_url(str(f))
    assert url.startswith("file:///") and "#" not in url and "?" not in url and " " not in url
    from urllib.parse import unquote, urlparse
    assert unquote(urlparse(url).path) == str(f.resolve())
