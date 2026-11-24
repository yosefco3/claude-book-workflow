import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

if not shutil.which("node"):
    pytest.skip("node is not installed", allow_module_level=True)

import office  # noqa: E402
import sync_docx  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "sample-book")
EXPECTED = ["פרק 1 - הקדמה.docx", "פרק 2 - אדמה ועציצים.docx", "פרק 3 - השקיה.docx",
            "מה למדנו בחלק א.docx", "פרק 4 - תבלינים לשימוש יומיומי.docx", "תודות.docx"]


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "book"
    shutil.copytree(SAMPLE, dst)
    return dst


def run(book, *extra):
    return sync_docx.main(["--root", str(book), *extra])


def review(book):
    return book / "review"


def docx_names(book):
    return sorted(n for n in os.listdir(review(book)) if n.endswith(".docx"))


def xml(path):
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edit_conf(book, fn):
    p = book / "book.json"
    c = json.loads(p.read_text(encoding="utf-8"))
    fn(c)
    p.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


def test_first_run_creates_all(book, capsys):
    assert run(book) == 0
    names = docx_names(book)
    assert len(names) == 6
    assert set(names) == set(EXPECTED)
    assert not any("notes" in n for n in names)
    out = capsys.readouterr().out
    assert "created" in out and "6 created" in out


def test_expected_names_and_content(book):
    assert run(book) == 0
    names = set(docx_names(book))
    assert names == set(EXPECTED), names
    x = xml(review(book) / "פרק 3 - השקיה.docx")
    assert "מי שמשקה מתוך דאגה" in x
    assert "w:bidi" in x
    assert "Noto Serif Hebrew" in x


def test_only_rewrites_one(book):
    run(book)
    files = {n: review(book) / n for n in EXPECTED}
    before = {n: digest(p) for n, p in files.items()}
    mt = {n: p.stat().st_mtime_ns for n, p in files.items()}
    # a visible change in chapter 3 only
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nפסקה חדשה לגמרי.\n", encoding="utf-8")
    assert run(book, "--only", "3") == 0
    for n, p in files.items():
        if n == "פרק 3 - השקיה.docx":
            assert digest(p) != before[n]
        else:
            assert digest(p) == before[n] and p.stat().st_mtime_ns == mt[n]


def test_only_unknown_key(book, capsys):
    assert run(book, "--only", "3,77") == 2
    assert "77" in capsys.readouterr().err
    assert not review(book).exists()


def test_lock_blocks_and_force_writes(book, capsys):
    run(book)
    target = review(book) / "פרק 3 - השקיה.docx"
    lock = review(book) / (".~lock.%s#" % target.name)
    lock.write_text("x")
    h = digest(target)
    assert run(book, "--only", "3") == 2
    assert digest(target) == h
    assert "BLOCKED" in capsys.readouterr().out
    # a new build is deterministic enough to differ only if content changed; change the source
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nעוד שורה.\n", encoding="utf-8")
    assert run(book, "--only", "3", "--force") == 0
    assert digest(target) != h


def test_overwrite_open_config(book, capsys):
    run(book)
    target = review(book) / "פרק 3 - השקיה.docx"
    (review(book) / (".~lock.%s#" % target.name)).write_text("x")
    edit_conf(book, lambda c: c.update(overwrite_open=["libreoffice"]))
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nעוד שורה.\n", encoding="utf-8")
    h = digest(target)
    assert run(book, "--only", "3") == 0
    assert "WARNING" in capsys.readouterr().out
    assert digest(target) != h


def test_monkeypatched_is_open(book, monkeypatch, capsys):
    run(book)
    monkeypatch.setattr(office, "is_open", lambda p: "wordcraft")
    before = {n: digest(review(book) / n) for n in EXPECTED}
    assert run(book) == 2
    out = capsys.readouterr().out
    assert out.count("BLOCKED") == 6 and "open in wordcraft" in out
    assert before == {n: digest(review(book) / n) for n in EXPECTED}


def test_title_change_rewrites_same_file(book, capsys):
    run(book)
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8").replace("# השקיה", "# השקיה נכונה", 1), encoding="utf-8")
    assert run(book, "--only", "3") == 0
    names = docx_names(book)
    assert len(names) == 6 and "פרק 3 - השקיה.docx" in names
    assert "השקיה נכונה" in xml(review(book) / "פרק 3 - השקיה.docx")
    assert "title" in capsys.readouterr().out


def test_ltr_has_no_bidi(book):
    edit_conf(book, lambda c: c.update({"dir": "ltr"}))
    assert run(book, "--only", "3") == 0
    x = xml(review(book) / "פרק 3 - השקיה.docx")
    assert "w:bidi" not in x and "w:rtl" not in x


def _sizes_of(x, text):
    """Run sizes (w:sz) of the runs whose text contains `text`."""
    return [int(m.group(1)) for r in re.findall(r"<w:r>.*?</w:r>", x, re.S) if text in r
            for m in [re.search(r'<w:sz w:val="(\d+)"', r)] if m]


def test_special_headings_from_config(book):
    # default sources heading: its paragraphs use the small sources size (A4: 23 half-points)
    run(book, "--only", "3")
    target = review(book) / "פרק 3 - השקיה.docx"
    assert _sizes_of(xml(target), "מדריך ההשקיה") == [23]
    # custom heading: the old one no longer switches the style, the new one does
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8").replace("מקורות לפרק זה", "Sources here"), encoding="utf-8")
    run(book, "--only", "3")
    assert _sizes_of(xml(target), "מדריך ההשקיה") == [26]
    edit_conf(book, lambda c: c["special_headings"].update(sources="Sources here"))
    run(book, "--only", "3")
    assert _sizes_of(xml(target), "מדריך ההשקיה") == [23]
    assert "Noto Sans Hebrew" in xml(target)


def test_deep_heading_from_config(book):
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + "\n## Going deeper\n\nטקסט עמוק כאן.\n", encoding="utf-8")
    run(book, "--only", "3")
    target = review(book) / "פרק 3 - השקיה.docx"
    assert _sizes_of(xml(target), "טקסט עמוק") == [26]
    edit_conf(book, lambda c: c["special_headings"].update(deep="Going deeper"))
    run(book, "--only", "3")
    assert _sizes_of(xml(target), "טקסט עמוק") == [23]


# ---------------------------------------------------------------- manifest, held files, backups

CH3 = "פרק 3 - השקיה.docx"


def manifest(book):
    return json.loads((review(book) / ".sync-state.json").read_text(encoding="utf-8"))


def append_md(book, text="\nעוד שורה.\n"):
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + text, encoding="utf-8")


def author_edit(path):
    """Change the DOCX the way a word processor save would: different bytes."""
    path.write_bytes(path.read_bytes() + b"\0author")


def test_manifest_written_with_hash_and_key(book):
    assert run(book) == 0
    m = manifest(book)
    assert set(m) == set(EXPECTED)
    assert m[CH3]["key"] == "3"
    assert m[CH3]["sha256"] == digest(review(book) / CH3)
    assert not [n for n in os.listdir(review(book)) if n.endswith(".tmp")]


def test_author_edit_is_held_not_overwritten(book, capsys):
    run(book)
    target = review(book) / CH3
    author_edit(target)
    h = digest(target)
    append_md(book)
    capsys.readouterr()
    assert run(book, "--only", "3") == 2
    out = capsys.readouterr().out
    assert "HELD" in out and "docx_diff.py 3" in out and "--merged" in out
    assert digest(target) == h
    assert not (review(book) / ".backup").exists()


def test_force_overwrites_held_file_with_backup(book, capsys):
    run(book)
    target = review(book) / CH3
    author_edit(target)
    edited = target.read_bytes()
    capsys.readouterr()
    assert run(book, "--only", "3", "--force") == 0
    assert "backup " in capsys.readouterr().out
    backups = list((review(book) / ".backup").iterdir())
    assert len(backups) == 1 and backups[0].name.startswith(CH3 + ".")
    assert backups[0].read_bytes() == edited
    assert manifest(book)[CH3]["sha256"] == digest(target)
    assert run(book, "--only", "3") == 0  # clean again


def test_merged_replaces_held_file_with_backup(book, capsys):
    run(book)
    target = review(book) / CH3
    author_edit(target)
    edited = target.read_bytes()
    capsys.readouterr()
    assert run(book, "--only", "3", "--merged") == 0
    assert "backup " in capsys.readouterr().out
    backups = list((review(book) / ".backup").iterdir())
    assert len(backups) == 1 and backups[0].read_bytes() == edited
    assert manifest(book)[CH3]["sha256"] == digest(target)


def test_merged_still_skips_an_open_file(book, monkeypatch, capsys):
    run(book)
    target = review(book) / CH3
    author_edit(target)
    h = digest(target)
    monkeypatch.setattr(office, "is_open", lambda p: "wordcraft")
    capsys.readouterr()
    assert run(book, "--only", "3", "--merged") == 2
    assert "BLOCKED" in capsys.readouterr().out
    assert digest(target) == h
    assert not (review(book) / ".backup").exists()


def test_file_without_manifest_entry_is_backed_up(book, capsys):
    run(book)
    (review(book) / ".sync-state.json").unlink()  # an old setup
    target = review(book) / CH3
    before = target.read_bytes()
    capsys.readouterr()
    assert run(book, "--only", "3") == 0
    assert "backup " in capsys.readouterr().out
    backups = list((review(book) / ".backup").iterdir())
    assert len(backups) == 1 and backups[0].read_bytes() == before
    assert CH3 in manifest(book)


def test_unchanged_file_is_rewritten_without_backup(book):
    run(book)
    assert run(book) == 0
    assert not (review(book) / ".backup").exists()


def test_side_file_with_same_prefix_is_never_touched(book):
    run(book)
    side = review(book) / "פרק 3 - הערות שלי.docx"
    side.write_bytes(b"my own notes")
    (review(book) / CH3).unlink()  # exact name gone: the old prefix fallback would grab the side file
    assert run(book, "--only", "3") == 0
    assert side.read_bytes() == b"my own notes"
    assert (review(book) / CH3).exists()


def test_renamed_chapter_found_through_manifest(book):
    run(book)
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8").replace("# השקיה", "# השקיה נכונה", 1), encoding="utf-8")
    import bookconf
    conf = bookconf.load(str(book))
    ch = bookconf.resolve(conf, "3")
    assert os.path.basename(bookconf.find_review_docx(conf, ch)) == CH3
    # a file the manifest does not list is ignored even with a matching prefix
    m = manifest(book)
    m.pop(CH3)
    (review(book) / ".sync-state.json").write_text(json.dumps(m), encoding="utf-8")
    assert bookconf.find_review_docx(conf, ch) is None


def test_two_manifest_files_for_one_chapter_is_an_error(book):
    run(book)
    shutil.copy(review(book) / CH3, review(book) / "פרק 3 - ישן.docx")
    m = manifest(book)
    m["פרק 3 - ישן.docx"] = {"key": "3", "sha256": "x"}
    (review(book) / ".sync-state.json").write_text(json.dumps(m), encoding="utf-8")
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8").replace("# השקיה", "# שם אחר", 1), encoding="utf-8")
    import bookconf
    conf = bookconf.load(str(book))
    with pytest.raises(bookconf.BookError) as e:
        bookconf.find_review_docx(conf, bookconf.resolve(conf, "3"))
    assert "ישן" in str(e.value) and CH3 in str(e.value)


# ---------------------------------------------------------------- atomic write, failures

def test_failed_build_leaves_target_and_temp_clean(book, monkeypatch, capsys):
    run(book)
    target = review(book) / CH3
    h = digest(target)
    real = sync_docx.write_docx

    def broken(node, md, docx, conf_path, size):
        open(docx, "wb").write(b"half a file")
        raise RuntimeError("boom")

    monkeypatch.setattr(sync_docx, "write_docx", broken)
    assert run(book, "--only", "3") == 2
    assert digest(target) == h
    assert not [n for n in os.listdir(review(book)) if n.endswith(".tmp")]
    assert "boom" in capsys.readouterr().err
    monkeypatch.setattr(sync_docx, "write_docx", real)


def test_one_failed_chapter_does_not_stop_the_others(book, monkeypatch, capsys):
    real = sync_docx.write_docx

    def flaky(node, md, docx, conf_path, size):
        if md.endswith("03-hashkaya.md"):
            raise RuntimeError("boom")
        return real(node, md, docx, conf_path, size)

    monkeypatch.setattr(sync_docx, "write_docx", flaky)
    assert run(book) == 2
    assert set(docx_names(book)) == set(EXPECTED) - {CH3}
    assert "5 created" in capsys.readouterr().out


def test_file_opened_during_build_is_not_replaced(book, monkeypatch, capsys):
    run(book)
    target = review(book) / CH3
    h = digest(target)
    append_md(book)
    calls = []

    def late(p):
        calls.append(p)
        return None if len(calls) == 1 else "word"

    monkeypatch.setattr(office, "is_open", late)
    assert run(book, "--only", "3") == 2
    assert digest(target) == h
    assert not [n for n in os.listdir(review(book)) if n.endswith(".tmp")]
    assert "BLOCKED" in capsys.readouterr().out


# ---------------------------------------------------------------- name collisions and file names

def test_same_title_collision_exits_2_before_writing(book, capsys):
    extra = book / "manuscript/01-basics/05z-x.md"
    extra.write_text("# מה למדנו בחלק א\n\nטקסט.\n", encoding="utf-8")
    assert run(book) == 2
    err = capsys.readouterr().err
    assert "{key}" in err and "05z-x.md" in err and "03z-ma-lamadnu.md" in err
    assert not review(book).exists()
    edit_conf(book, lambda c: c.update(review_name_unnumbered="{key} {title}.docx"))
    assert run(book) == 0


def test_long_title_is_truncated_under_200_bytes(book):
    import bookconf
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text("# " + "ש" * 300 + "\n\nטקסט\n", encoding="utf-8")
    conf = bookconf.load(str(book))
    name = bookconf.review_name(conf, bookconf.resolve(conf, "3"))
    assert len(name.encode("utf-8")) < 200 and name.startswith("פרק 3 - ש") and name.endswith(".docx")
    assert run(book, "--only", "3") == 0


def test_empty_title_falls_back_to_key(book):
    import bookconf
    md = book / "manuscript/01-basics/03-hashkaya.md"
    md.write_text("# \n\nטקסט\n", encoding="utf-8")
    conf = bookconf.load(str(book))
    assert bookconf.review_name(conf, bookconf.resolve(conf, "3")) == "פרק 3 - 3.docx"


def test_safe_filename_rules():
    import bookconf
    sf = bookconf.safe_filename
    assert sf('הוא אמר "שלום"') == "הוא אמר ״שלום״"
    assert sf('He said "hi"') == "He said 'hi'"
    assert sf("CON.docx") == "CON_.docx" and sf("com1.docx") == "com1_.docx"
    assert sf("a/b:c?.docx") == "a-b -c.docx"
    assert sf("name. ") == "name"


def test_merged_requires_only(book, capsys):
    run(book)
    author_edit(review(book) / CH3)
    capsys.readouterr()
    assert run(book, "--merged") == 2
    assert "--only" in capsys.readouterr().err
    assert not (review(book) / ".backup").exists()
