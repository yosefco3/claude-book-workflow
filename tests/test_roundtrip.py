"""End-to-end author round-trip: sync_docx -> author edits DOCX -> docx_diff -> merge -> sync.

Uses only the scripts' CLIs (subprocess) on a copy of the sample book.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLE = os.path.join(SKILL, "examples", "sample-book")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

CH3_MD = os.path.join("manuscript", "01-basics", "03-hashkaya.md")


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True)


def sync(book, *args):
    return run("sync_docx.py", "--root", str(book), *args)


def diff(book, *args):
    return run("docx_diff.py", "--root", str(book), *args)


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "book"
    shutil.copytree(SAMPLE, dst)
    return dst


@pytest.fixture
def synced(book):
    r = sync(book)
    assert r.returncode == 0, r.stdout + r.stderr
    return book


def ch3_docx(book):
    found = [p for p in (book / "review").iterdir() if p.name.startswith("פרק 3 ")]
    assert len(found) == 1
    return found[0]


def edit_document_xml(docx, fn):
    """Rewrite word/document.xml with fn(str)->str, copying every other member unchanged."""
    tmp = docx.with_suffix(".tmp")
    with zipfile.ZipFile(docx) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = zi.read(info.filename)
            if info.filename == "word/document.xml":
                data = fn(data.decode("utf-8")).encode("utf-8")
            zo.writestr(info, data)
    os.replace(tmp, docx)


def test_fresh_sync_has_no_differences(synced):
    r = diff(synced, "--scan", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert len(data["chapters"]) >= 5
    for ch in data["chapters"]:
        assert ch["differs"] is False, ch["key"]
        assert ch["count"] == 0, ch["key"]


def test_author_edit_is_found_and_merge_clears_it(synced):
    def swap(xml):
        assert xml.count("לפני") == 1
        return xml.replace("לפני", "בטרם")

    edit_document_xml(ch3_docx(synced), swap)

    r = diff(synced, "3", "--json")
    assert r.returncode == 1, r.stdout + r.stderr
    changes = json.loads(r.stdout)["changes"]
    assert len(changes) == 1
    ch = changes[0]
    assert ch["type"] == "changed"
    assert "לפני" in ch["word_diff"] and "בטרם" in ch["word_diff"]
    md_path = synced / CH3_MD
    lines = md_path.read_text(encoding="utf-8").splitlines()
    first, last = ch["md_lines"]
    assert "לפני שמשקים" in "\n".join(lines[first - 1:last])

    text = md_path.read_text(encoding="utf-8")
    assert text.count("לפני שמשקים") == 1
    md_path.write_text(text.replace("לפני שמשקים", "בטרם שמשקים", 1), encoding="utf-8")
    r = diff(synced, "3", "--json")
    assert r.returncode == 0, r.stdout + r.stderr

    # the author's DOCX changed after the last sync: sync holds it until the merge is confirmed
    r = sync(synced, "--only", "3")
    assert r.returncode == 2 and "HELD" in r.stdout, r.stdout + r.stderr
    r = sync(synced, "--only", "3", "--merged")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "backup" in r.stdout
    r = diff(synced, "3", "--json")
    assert r.returncode == 0, r.stdout + r.stderr


def test_deleted_paragraph_reported(synced):
    def drop(xml):
        pat = re.compile(r"<w:p[ >].*?</w:p>", re.DOTALL)
        hits = [m for m in pat.finditer(xml) if "רשימות אישיות" in m.group(0)]
        assert len(hits) == 1
        m = hits[0]
        return xml[:m.start()] + xml[m.end():]

    edit_document_xml(ch3_docx(synced), drop)

    r = diff(synced, "3", "--json")
    assert r.returncode == 1, r.stdout + r.stderr
    changes = json.loads(r.stdout)["changes"]
    assert len(changes) == 1
    assert changes[0]["type"] == "deleted"


def test_open_docx_is_not_overwritten(synced):
    docx = ch3_docx(synced)
    lock = docx.parent / (".~lock." + docx.name + "#")
    lock.write_text("lock", encoding="utf-8")
    before = docx.read_bytes()

    md_path = synced / CH3_MD
    md_path.write_text(md_path.read_text(encoding="utf-8") + "\nפסקה חדשה.\n", encoding="utf-8")

    r = sync(synced, "--only", "3")
    assert r.returncode == 2, r.stdout + r.stderr
    assert docx.read_bytes() == before
