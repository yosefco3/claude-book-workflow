"""Tests for scripts/docx_diff.py. DOCX fixtures are built in code; all text is invented."""
import json
import os
import shutil
import sys
import time
import zipfile
from xml.sax.saxutils import escape

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bookconf  # noqa: E402
import docx_diff  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "sample-book")
CH = "manuscript/01-basics/03-hashkaya.md"

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


# ---------------------------------------------------------------- fixture helpers

def run(text, flags=""):
    """A run: flags is a string of b (bold), i (italic), I (inside w:ins), D (inside w:del)."""
    rpr = ("<w:b/>" if "b" in flags else "") + ("<w:i/>" if "i" in flags else "")
    rpr = "<w:rPr>%s</w:rPr>" % rpr if rpr else ""
    if "D" in flags:
        r = '<w:r>%s<w:delText xml:space="preserve">%s</w:delText></w:r>' % (rpr, escape(text))
        return '<w:del w:id="1" w:author="x">%s</w:del>' % r
    r = '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(text))
    if "I" in flags:
        return '<w:ins w:id="2" w:author="x">%s</w:ins>' % r
    return r


def para(*runs, style=None):
    """A paragraph from runs: plain strings, or (text, flags) tuples."""
    ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else ""
    body = "".join(run(r) if isinstance(r, str) else run(*r) for r in runs)
    return "<w:p>%s%s</w:p>" % (ppr, body)


def write_docx(path, paragraphs):
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>'
           % (W, "".join(paragraphs)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
                   'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                   'officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/'
                   '2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/document.xml", doc)


# the paragraphs of the sample chapter 03-hashkaya.md, as a DOCX would hold them
def base_paras():
    return [
        para("השקיה", style="Heading1"),
        para("הכלל הפשוט ביותר: לגעת באדמה לפני שמשקים. אם היא לחה בעומק של פרק אצבע, מחכים יום."),
        para("בקיץ המרפסת מתייבשת מהר, בעיקר כשיש ", ("רוח מערבית", "b"),
             ". בחורף אפשר לשכוח מהשקיה שבוע שלם."),
        para("מי שמשקה מתוך דאגה משקה יותר מדי."),
        para("מקורות לפרק זה", style="Heading2"),
        para("• מדריך ההשקיה של משתלה שכונתית, מהדורה מקוונת."),
        para("• רשימות אישיות, שלוש עונות."),
    ]


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "book"
    shutil.copytree(SAMPLE, dst)
    conf = bookconf.load(str(dst))
    ch = bookconf.resolve(conf, "3")
    docx = bookconf.path(conf, "review_dir", bookconf.review_name(conf, ch))
    # the DOCX is written after the .md, so it is not stale
    old = time.time() - 100
    os.utime(ch.path, (old, old))
    return {"root": str(dst), "conf": conf, "ch": ch, "docx": docx}


def run_cli(book, *extra, chapter="3", capsys=None):
    code = docx_diff.main([chapter, "--root", book["root"], "--json"] + list(extra))
    out = capsys.readouterr()
    return code, (json.loads(out.out) if out.out.strip() else None), out.err


def with_docx(book, paragraphs):
    write_docx(book["docx"], paragraphs)


def edit_md(book, old, new):
    p = book["ch"].path
    with open(p, encoding="utf-8") as f:
        t = f.read()
    assert old in t
    with open(p, "w", encoding="utf-8") as f:
        f.write(t.replace(old, new))
    os.utime(p, (time.time() - 100, time.time() - 100))


# ---------------------------------------------------------------- tests

def test_identical_content_exit_0(book, capsys):
    with_docx(book, base_paras())
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 0
    assert res["changes"] == [] and res["format_changes"] == []
    assert res["summary"] == {"changed": 0, "added": 0, "deleted": 0, "minor": 0, "format": 0}
    assert res["md"] == CH
    assert res["tracked_changes"] is False
    assert res["docx_stale"] is False
    assert res["md_dirty"] is None  # the copy is not a git repository
    assert res["open"] is None


def test_human_output_when_identical(book, capsys):
    with_docx(book, base_paras())
    code = docx_diff.main(["3", "--root", book["root"]])
    assert code == 0
    assert "Summary: 0 changed" in capsys.readouterr().out


def test_one_changed_word(book, capsys):
    paras = base_paras()
    paras[3] = para("מי שמשקה מתוך דאגה משקה יותר מהצורך.")
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 1
    assert len(res["changes"]) == 1
    c = res["changes"][0]
    assert c["type"] == "changed"
    assert c["md_lines"] == [7, 7]
    assert c["md_index"] == 3
    assert c["old_raw"] == "> מי שמשקה מתוך דאגה משקה יותר מדי."
    assert "[-מדי.-]" in c["word_diff"] and "{+מהצורך.+}" in c["word_diff"]
    assert c["minor"] is False
    assert c["new"].endswith("מהצורך.")
    assert c["context_before"].startswith("בקיץ")
    assert res["summary"]["changed"] == 1


def test_deleted_paragraph(book, capsys):
    paras = base_paras()
    del paras[1]
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 1
    assert [c["type"] for c in res["changes"]] == ["deleted"]
    c = res["changes"][0]
    assert c["md_lines"] == [3, 3]
    assert c["word_diff"].startswith("[-הכלל")
    assert c["new"] is None
    assert res["summary"]["deleted"] == 1


def test_added_paragraph_after_line(book, capsys):
    paras = base_paras()
    paras.insert(2, para("פסקה חדשה שהמחברת הוסיפה כאן."))
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 1
    assert len(res["changes"]) == 1
    c = res["changes"][0]
    assert c["type"] == "added"
    assert c["after_line"] == 3
    assert c["after_md_index"] == 1
    assert c["new"] == "פסקה חדשה שהמחברת הוסיפה כאן."
    assert c["old_raw"] is None
    assert res["summary"]["added"] == 1


def test_added_at_start_has_after_line_zero(book, capsys):
    paras = base_paras()
    paras.insert(0, para("שורה לפני הכותרת"))
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["changes"][0]["after_line"] == 0


def test_punctuation_only_is_minor(book, capsys):
    paras = base_paras()
    paras[3] = para("מי שמשקה, מתוך דאגה, משקה יותר מדי.")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["changes"]) == 1
    assert res["changes"][0]["minor"] is True
    assert res["summary"]["minor"] == 1


def test_odd_spaces_are_not_changes(book, capsys):
    paras = base_paras()
    paras[1] = para("הכלל\u00a0הפשוט ביותר: לגעת באדמה לפני שמשקים.  אם היא לחה בעומק של פרק אצבע, מחכים יום.")
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 0 and res["changes"] == []


def test_quote_style_change_is_minor(book, capsys):
    edit_md(book, "משקים. אם", 'משקים. "אם')
    paras = base_paras()
    paras[1] = para("הכלל הפשוט ביותר: לגעת באדמה לפני שמשקים. \u05f4אם היא לחה בעומק של פרק אצבע, מחכים יום.")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["changes"]) == 1 and res["changes"][0]["minor"] is True


def test_bold_added_is_format_change(book, capsys):
    paras = base_paras()
    paras[1] = para("הכלל הפשוט ביותר: לגעת ", ("באדמה", "b"),
                    " לפני שמשקים. אם היא לחה בעומק של פרק אצבע, מחכים יום.")
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 1
    assert res["changes"] == []
    assert len(res["format_changes"]) == 1
    f = res["format_changes"][0]
    assert f["type"] == "format"
    assert "**באדמה**" in f["new_rich"]
    assert f["md_lines"] == [3, 3]
    assert res["summary"]["format"] == 1


def test_bold_removed_is_format_change(book, capsys):
    paras = base_paras()
    paras[2] = para("בקיץ המרפסת מתייבשת מהר, בעיקר כשיש רוח מערבית. בחורף אפשר לשכוח מהשקיה שבוע שלם.")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["format_changes"]) == 1
    assert "**" not in res["format_changes"][0]["new_rich"]


def test_italic_added_is_format_change(book, capsys):
    paras = base_paras()
    paras[3] = para(("מי שמשקה", "i"), " מתוך דאגה משקה יותר מדי.")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["format_changes"]) == 1
    assert res["format_changes"][0]["new_rich"].startswith("*מי שמשקה*")


def test_tracked_changes(book, capsys):
    paras = base_paras()
    paras[3] = para("מי שמשקה מתוך דאגה משקה יותר ", ("מדי", "D"), ("מהצורך", "I"), ".")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["tracked_changes"] is True
    assert len(res["changes"]) == 1
    c = res["changes"][0]
    assert c["new"] == "מי שמשקה מתוך דאגה משקה יותר מהצורך."  # deleted skipped, inserted kept


def test_tracked_deletion_only_leaves_no_difference(book, capsys):
    paras = base_paras()
    paras[3] = para("מי שמשקה מתוך דאגה משקה יותר מדי.", ("מילה שנמחקה", "D"))
    with_docx(book, paras)
    code, res, _ = run_cli(book, capsys=capsys)
    assert code == 0
    assert res["tracked_changes"] is True


def test_heading_text_change_has_level(book, capsys):
    paras = base_paras()
    paras[4] = para("מקורות לפרק הזה", style="Heading2")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["changes"]) == 1
    c = res["changes"][0]
    assert c["kind"] == "heading" and c["level"] == 2
    assert c["type"] == "changed"
    assert c["md_lines"] == [9, 9]


def test_heading_level_change(book, capsys):
    paras = base_paras()
    paras[4] = para("מקורות לפרק זה", style="Heading3")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["changes"]) == 1
    c = res["changes"][0]
    assert c["note"] == "heading level"
    assert c["old_level"] == 2 and c["level"] == 3


def test_empty_paragraphs_are_ignored(book, capsys):
    paras = base_paras()
    paras.insert(2, para("   "))
    paras.insert(2, "<w:p/>")
    with_docx(book, paras)
    code, _, _ = run_cli(book, capsys=capsys)
    assert code == 0


def test_two_adjacent_edits_are_paired_not_replaced(book, capsys):
    paras = base_paras()
    paras[5] = para("• מדריך ההשקיה של משתלה שכונתית, מהדורה מעודכנת.")
    paras[6] = para("• רשימות אישיות, ארבע עונות.")
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert [c["type"] for c in res["changes"]] == ["changed", "changed"]
    assert [c["md_lines"][0] for c in res["changes"]] == [11, 12]
    assert all(c["kind"] == "list" for c in res["changes"])


def test_bullet_marker_is_the_bullet_char(book, capsys):
    paras = base_paras()
    paras[6] = para("- רשימות אישיות, שלוש עונות.")  # a literal dash is a real difference
    with_docx(book, paras)
    _, res, _ = run_cli(book, capsys=capsys)
    assert len(res["changes"]) == 1


def test_quote_mode_separate_is_still_available(book, capsys):
    with_docx(book, base_paras())
    code, res, _ = run_cli(book, "--quote-mode", "separate", capsys=capsys)
    assert code in (0, 1)  # the sample has single-line quotes only


def test_quote_mode_merge_is_gone(book, capsys):
    with pytest.raises(SystemExit):
        run_cli(book, "--quote-mode", "merge", capsys=capsys)


def test_docx_stale_when_md_newer(book, capsys):
    with_docx(book, base_paras())
    past = time.time() - 1000
    os.utime(book["docx"], (past, past))
    now = time.time()
    os.utime(book["ch"].path, (now, now))
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["docx_stale"] is True
    assert res["md_mtime"] > res["docx_mtime"]


def test_open_docx_reported(book, capsys):
    with_docx(book, base_paras())
    d, name = os.path.split(book["docx"])
    open(os.path.join(d, ".~lock.%s#" % name), "w").close()
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["open"] == "libreoffice"


def test_md_dirty_in_git_repo(book, capsys):
    import subprocess
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    root = book["root"]
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True, env=env)
    with_docx(book, base_paras())
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["md_dirty"] is False
    edit_md(book, "יום.", "יומיים.")
    _, res, _ = run_cli(book, capsys=capsys)
    assert res["md_dirty"] is True


def test_missing_docx_exit_2(book, capsys):
    code, _, err = run_cli(book, capsys=capsys)
    assert code == 2
    assert "no review DOCX" in err


def test_explicit_docx_option(book, capsys, tmp_path):
    other = str(tmp_path / "elsewhere" / "x.docx")
    paras = base_paras()
    del paras[1]
    write_docx(other, paras)
    code, res, _ = run_cli(book, "--docx", other, capsys=capsys)
    assert code == 1 and res["docx"] == other


def test_corrupt_docx_exit_2(book, capsys):
    os.makedirs(os.path.dirname(book["docx"]), exist_ok=True)
    with open(book["docx"], "w") as f:
        f.write("not a zip")
    code, _, err = run_cli(book, capsys=capsys)
    assert code == 2 and "cannot read DOCX" in err


def test_unknown_chapter_exit_2(book, capsys):
    code, _, err = run_cli(book, chapter="77", capsys=capsys)
    assert code == 2 and "not found" in err


def test_chapter_by_path(book, capsys):
    with_docx(book, base_paras())
    code, res, _ = run_cli(book, chapter=book["ch"].path, capsys=capsys)
    assert code == 0 and res["md"] == CH


def test_no_chapter_no_scan_exit_2(book, capsys):
    assert docx_diff.main(["--root", book["root"]]) == 2


def test_scan_lists_only_differing(book, capsys):
    conf = book["conf"]
    # chapter 3 differs, chapter 2 is identical, the rest have no DOCX
    paras = base_paras()
    del paras[1]
    with_docx(book, paras)
    ch2 = bookconf.resolve(conf, "2")
    write_docx(bookconf.path(conf, "review_dir", bookconf.review_name(conf, ch2)), [
        para("אדמה ועציצים", style="Heading1"),
        para("עציץ טוב מתחיל בחור בתחתית. בלי ניקוז המים עומדים, השורשים נחנקים, "
             "והצמח נובל דווקא כשמשקים אותו יותר."),
        para("איזו אדמה לקנות", style="Heading2"),
        para("תערובת שתילה מוכנה מספיקה לרוב הצמחים. כדאי להוסיף לה מעט פרלייט, כדי שתישאר "
             "אוורירית גם אחרי חודשים של השקיה."),
        para("להעמקה: למה אדמת גינה לא מתאימה", style="Heading2"),
        para("בקצרה: היא נדחסת בעציץ."),
        para("אדמת גינה רגילה בנויה לשכבות עמוקות, עם תולעים ועם חיים שמאווררים אותה. בעציץ אין לה "
             "את כל אלה, והיא הופכת לגוש קשה."),
    ])
    code = docx_diff.main(["--scan", "--root", book["root"], "--json"])
    res = json.loads(capsys.readouterr().out)
    assert code == 1
    assert {c["key"] for c in res["chapters"]} == {"2", "3"}
    assert [c["key"] for c in res["chapters"] if c["differs"]] == ["3"]
    assert res["differing"] == 1


def test_scan_all_same_exit_0(book, capsys):
    with_docx(book, base_paras())
    code = docx_diff.main(["--scan", "--root", book["root"]])
    out = capsys.readouterr().out
    assert code == 0 and "0 of 1 chapters" in out


def test_human_report_has_lines_and_diff(book, capsys):
    paras = base_paras()
    paras[3] = para("מי שמשקה מתוך דאגה משקה יותר מהצורך.")
    with_docx(book, paras)
    code = docx_diff.main(["3", "--root", book["root"]])
    out = capsys.readouterr().out
    assert code == 1
    assert "[CHANGED] line 7" in out and "[-מדי.-]" in out
    assert "Summary: 1 changed" in out


def test_does_not_modify_files(book, capsys):
    paras = base_paras()
    del paras[1]
    with_docx(book, paras)
    before = {p: open(p, "rb").read() for p in (book["ch"].path, book["docx"])}
    run_cli(book, capsys=capsys)
    assert before == {p: open(p, "rb").read() for p in before}


# ---------------------------------------------------------------- quotes mirror md2docx

def test_two_line_quote_matches_md2docx_and_one_word_edit_is_one_change(tmp_path, capsys):
    import shutil as _sh
    import subprocess
    if not _sh.which("node"):
        pytest.skip("node is not installed")
    dst = tmp_path / "book"
    _sh.copytree(SAMPLE, dst)
    md = dst / "manuscript/01-basics/03-hashkaya.md"
    md.write_text(md.read_text(encoding="utf-8") + "\n> שורה ראשונה של ציטוט\n> שורה שנייה של ציטוט\n\nאחרי הציטוט.\n",
                  encoding="utf-8")
    old = time.time() - 100
    os.utime(md, (old, old))
    sync = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "sync_docx.py")
    assert subprocess.run([sys.executable, sync, "--root", str(dst), "--only", "3"],
                          capture_output=True).returncode == 0
    assert docx_diff.main(["3", "--root", str(dst), "--json"]) == 0
    capsys.readouterr()
    docx = dst / "review" / "פרק 3 - השקיה.docx"
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "שורה ראשונה של ציטוט שורה שנייה של ציטוט" in xml  # ONE paragraph
    paras = docx_diff.md_paragraphs("> a\n> b\n\ntext\n> c\n")
    assert [(p["kind"], p["plain"]) for p in paras] == [("quote", "a b"), ("para", "text"), ("quote", "c")]
    assert len(docx_diff.md_paragraphs("> a\n> b\n", "separate")) == 2
    # edit one word inside the quote
    tmp = str(docx) + ".new"
    with zipfile.ZipFile(docx) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = zi.read(info.filename)
            if info.filename == "word/document.xml":
                data = data.decode("utf-8").replace("שנייה", "אחרונה").encode("utf-8")
            zo.writestr(info, data)
    os.replace(tmp, docx)
    assert docx_diff.main(["3", "--root", str(dst), "--json"]) == 1
    res = json.loads(capsys.readouterr().out)
    assert [c["type"] for c in res["changes"]] == ["changed"]


def test_tracked_changes_report_says_present(book, capsys):
    res = {"md": "m", "docx": "d", "open": None, "docx_stale": False, "md_dirty": False,
           "tracked_changes": True, "changes": [], "format_changes": [],
           "summary": {"changed": 0, "minor": 0, "added": 0, "deleted": 0, "format": 0}}
    text = docx_diff.format_report(res)
    assert "tracked changes present" in text and "1 tracked" not in text


def test_non_utf8_chapter_names_the_file(book, capsys):
    with_docx(book, base_paras())
    with open(book["ch"].path, "wb") as f:
        f.write("# כותרת\n".encode("windows-1255") + b"\xff\xfe")
    code, _, err = run_cli(book, capsys=capsys)
    assert code == 2 and "03-hashkaya.md" in err and "UTF-8" in err
