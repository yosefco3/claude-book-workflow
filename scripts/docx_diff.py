#!/usr/bin/env python3
"""docx_diff.py - read-only: which paragraphs of a chapter did the author change in the DOCX?

The author edits each chapter as a DOCX in a word processor; this script compares that DOCX
with the chapter's Markdown source (the source of truth) and reports, paragraph by paragraph,
every changed, added, deleted or re-formatted paragraph, so the edits can be merged into the
.md with precise edits. The md -> paragraph segmentation mirrors scripts/md2docx.js.
The script never writes, renames or deletes anything (git is only used through `git status`).

Usage:
    docx_diff.py <chapter> [--root DIR] [--docx PATH] [--json] [--quote-mode group|separate]
    docx_diff.py --scan [--root DIR] [--json]

    <chapter>   chapter key ("3", "3z", a file stem) or a path to the .md
    --root DIR  folder inside the book (default: cwd); book.json is searched upwards
    --docx PATH compare with this DOCX instead of the one in the review folder
    --scan      every chapter that has a review DOCX: which ones differ
    --json      machine-readable output (default: readable report)

Exit codes: 0 no differences, 1 differences found, 2 error (message on stderr).
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402
import office  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % W_NS


# JavaScript's String.prototype.trim / \s whitespace set (md2docx.js semantics).
_JS_WS = ("\t\n\x0b\x0c\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
          "\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff")
_WS = "[" + re.escape(_JS_WS) + "]"
_NOT_WS = "[^" + re.escape(_JS_WS) + "]"
_NOT_LT = "[^\\n\\r\\u2028\\u2029]"  # JS "." does not match line terminators

_HEADING_RE = re.compile("^(#{1,3})" + _WS + "+(" + _NOT_LT + "*)\\Z")
_LIST_RE = re.compile("^[*-]" + _WS + "+(" + _NOT_LT + "*)\\Z")
_QUOTE_STRIP_RE = re.compile("^>" + _WS + "*")
_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*" + re.escape(_JS_WS) + r"][^*]*\*)")

_PAIR_WINDOW = 8  # a replaced md paragraph is only paired with one of the next 8 DOCX paragraphs


class ChapterError(Exception):
    """Lookup / usage error: reported on stderr, exit code 2."""


# ----------------------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------------------

def _js_strip(s):
    return s.strip(_JS_WS)


def _norm(s):
    """Normalization for matching: odd spaces -> " ", collapse whitespace, strip."""
    s = re.sub("[\u00a0\u2000-\u200a\u202f\u205f\u3000]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_AGGR_TABLE = {}
for _c in "\u05f4\"\u201c\u201d\u201e":
    _AGGR_TABLE[ord(_c)] = '"'
for _c in "\u05f3'\u2018\u2019":
    _AGGR_TABLE[ord(_c)] = "'"
for _c in "\u2013\u2014\u2011-":
    _AGGR_TABLE[ord(_c)] = "-"


def _aggressive(s):
    """Punctuation/spacing-insensitive form: unify quotes and dashes, drop all whitespace."""
    return re.sub(r"\s+", "", s.translate(_AGGR_TABLE))


def _depunct(s):
    """Letters and digits only: a difference left after this is more than punctuation."""
    return "".join(ch for ch in _aggressive(s) if unicodedata.category(ch)[0] not in "PSZC")


def _cut(s, n=80):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def _iso(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None



def word_diff(old, new):
    """Word-level diff old -> new: [-removed-] and {+added+}."""
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(a[i1:i2]))
            continue
        if i2 > i1:
            parts.append("[-" + " ".join(a[i1:i2]) + "-]")
        if j2 > j1:
            parts.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(parts)


def _render_rich(runs):
    """runs = [(text, bold, italic)] -> text with **bold** / *italic* markers (merged runs)."""
    groups = []
    for text, b, i in runs:
        if not text:
            continue
        if groups and groups[-1][1] == b and groups[-1][2] == i:
            groups[-1][0] += text
        else:
            groups.append([text, b, i])
    out = []
    for text, b, i in groups:
        if (b or i) and text.strip():
            core = text.strip()
            lead = text[: text.index(core)]
            trail = text[len(lead) + len(core):]
            if i:
                core = "*" + core + "*"
            if b:
                core = "**" + core + "**"
            out.append(lead + core + trail)
        else:
            out.append(text)
    return "".join(out)


def _fmt_sig(runs):
    """(bold, italic) of every non-space character: formatting of spaces is ignored."""
    return [(b, i) for text, b, i in runs for ch in text if not ch.isspace()]


# ----------------------------------------------------------------------------------------
# markdown -> paragraphs (mirror of scripts/md2docx.js)
# ----------------------------------------------------------------------------------------

def _inline_runs(text):
    """JS inlineRuns(): split on **bold** / *italic* segments -> [(text, bold, italic)]."""
    runs = []
    for seg in _INLINE_RE.split(text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**") and len(seg) > 4:
            runs.append((seg[2:-2], True, False))
        elif seg.startswith("*") and seg.endswith("*") and len(seg) > 2:
            runs.append((seg[1:-1], False, True))
        else:
            runs.append((seg, False, False))
    return runs


_FIGURE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_SECTION_RE = re.compile(r"^::section::\s*(folio|nofolio)\s*$")
_STYLE_RE = re.compile(r"^::(\w+)::\s*(.*)$")


def md_paragraphs(text, quote_mode="group"):
    """Split markdown text into the paragraphs md2docx.js would write.

    Each paragraph: kind (heading/para/list/quote), level (headings, else 0), raw (source lines
    joined by newline, markers kept), plain (markers stripped = what the DOCX shows), rich,
    line_start / line_end (1-based). quote_mode "group" (default, exactly what md2docx.js does):
    consecutive lines of the same sort (all `>` quote lines, or all prose lines) are joined
    with a space into ONE paragraph, and a change between quote and prose starts a new one;
    "separate": every `>` line is its own paragraph (for DOCX files made by other tools).
    """
    if quote_mode not in ("group", "separate"):
        raise ValueError("quote_mode must be 'group' or 'separate'")
    lines = text.split("\n")
    paras = []
    buf = []  # (lineno, raw_line, text)
    buf_kind = "para"

    def add(kind, level, src, raw, ls, le, runs=None):
        if runs is not None:
            pass
        elif kind == "heading":
            runs = [(src, False, False)]
        else:
            runs = _inline_runs(src)
        plain = "".join(r[0] for r in runs)
        if not plain.strip():
            return  # md2docx writes an empty paragraph; the DOCX reader drops those
        paras.append({"kind": kind, "level": level, "raw": raw, "plain": plain,
                      "rich": _render_rich(runs), "runs": runs,
                      "line_start": ls, "line_end": le})

    def flush():
        nonlocal buf, buf_kind
        if buf:
            src = _js_strip(" ".join(b[2] for b in buf))
            add(buf_kind, 0, src, "\n".join(b[1] for b in buf), buf[0][0], buf[-1][0])
        buf = []
        buf_kind = "para"

    for no, line in enumerate(lines, 1):
        raw = line.rstrip("\r")
        t = _js_strip(line)
        if not t:
            flush()
            continue
        if t == "---" or _SECTION_RE.match(t):
            flush()  # page break / section marker: no text in the DOCX
            continue
        m = _FIGURE_RE.match(t)
        if m:
            flush()  # md2docx.js writes the image, then the caption in italics
            add("figure", 0, m.group(1), raw, no, no, runs=[(m.group(1), False, True)])
            continue
        m = _STYLE_RE.match(t)
        if m:
            flush()  # ::style:: text -> a special paragraph with that text
            add("para", 0, m.group(2), raw, no, no)
            continue
        m = _HEADING_RE.match(t)
        if m:
            flush()
            add("heading", len(m.group(1)), m.group(2), raw, no, no)
            continue
        m = _LIST_RE.match(t)
        if m:
            flush()
            add("list", 0, "\u2022 " + m.group(1), raw, no, no)
            continue
        if t.startswith(">"):
            stripped = _QUOTE_STRIP_RE.sub("", t, count=1)
            if quote_mode == "separate":
                flush()
                add("quote", 0, stripped, raw, no, no)
                continue
            if buf and buf_kind != "quote":
                flush()
            buf_kind = "quote"
            buf.append((no, raw, stripped))
            continue
        if buf and buf_kind != "para":
            flush()  # md2docx.js: a switch between quote and prose closes the paragraph
        buf.append((no, raw, t))
    flush()
    return paras


# ----------------------------------------------------------------------------------------
# DOCX -> paragraphs
# ----------------------------------------------------------------------------------------

_TRACK_TAGS = {W + "ins", W + "del", W + "moveFrom", W + "moveTo"}
_SKIP_TAGS = {W + "pPr", W + "del", W + "moveFrom", W + "p"}
_HEADING_STYLE_RE = re.compile(r"(?i)^heading\s*(\d)$")


def _on(rpr, name):
    """True when run properties switch `name` (b / i) on: <w:b/> but not w:val=0|false|off."""
    if rpr is None:
        return False
    for tag in (W + name, W + name + "Cs"):
        el = rpr.find(tag)
        if el is not None:
            return (el.get(W + "val") or "").lower() not in ("0", "false", "off")
    return False


def _read_run(r, out):
    rpr = r.find(W + "rPr")
    parts = []
    for c in r:
        if c.tag == W + "t":
            parts.append(c.text or "")
        elif c.tag == W + "tab":
            parts.append("\t")
        elif c.tag in (W + "br", W + "cr"):
            parts.append(" ")
        elif c.tag == W + "noBreakHyphen":
            parts.append("-")
    text = "".join(parts)
    if text:
        out.append((text, _on(rpr, "b"), _on(rpr, "i")))


def _collect_runs(elem, out):
    for child in elem:
        if child.tag == W + "r":
            _read_run(child, out)
        elif child.tag in _SKIP_TAGS:
            continue  # deleted text / paragraph properties / nested paragraphs
        else:
            _collect_runs(child, out)  # w:ins, w:hyperlink, w:sdt, w:smartTag, ...


def docx_paragraphs(path):
    """Read word/document.xml -> (paragraphs, tracked_changes).

    Paragraph: kind (heading/para/list), level, text (= plain), rich (with ** / *), runs.
    Tracked insertions count as accepted, deleted text is ignored; empty paragraphs are dropped.
    """
    with zipfile.ZipFile(path) as z:
        data = z.read("word/document.xml")
    root = ET.fromstring(data)
    tracked = any(el.tag in _TRACK_TAGS for el in root.iter())
    body = root.find(W + "body")
    paras = []
    for p in (body if body is not None else root).iter(W + "p"):
        runs = []
        _collect_runs(p, runs)
        text = "".join(r[0] for r in runs).strip()
        if not text:
            continue
        level = 0
        style = p.find(W + "pPr/" + W + "pStyle")
        if style is not None:
            m = _HEADING_STYLE_RE.match(style.get(W + "val") or "")
            if m:
                level = int(m.group(1))
        if level:
            kind = "heading"
            rich = text
        else:
            kind = "list" if text.startswith("\u2022") else "para"
            rich = _render_rich(runs).strip()
        paras.append({"kind": kind, "level": level, "text": text, "plain": text,
                      "rich": rich, "runs": runs})
    return paras, tracked


# ----------------------------------------------------------------------------------------
# paragraph diff
# ----------------------------------------------------------------------------------------

def _similar(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:
        return False
    return sm.ratio() >= 0.5


def _context(md_paras, idx):
    return _cut(md_paras[idx]["plain"]) if 0 <= idx < len(md_paras) else ""


def _change(kind_type, md_paras, other_paras, i, j, note=None, after=None):
    """Build one change dict. i = md index / None, j = other index / None."""
    old_p = md_paras[i] if i is not None else None
    new_p = other_paras[j] if j is not None else None
    ch = {"type": kind_type}
    if old_p is not None:
        ch["md_index"] = i
        ch["md_lines"] = [old_p["line_start"], old_p["line_end"]]
        before_i, after_i = i - 1, i + 1
    else:
        ch["after_md_index"] = after
        ch["after_line"] = md_paras[after]["line_end"] if after is not None and after >= 0 else 0
        before_i, after_i = after, after + 1
    old = old_p["plain"] if old_p else None
    new = new_p["plain"] if new_p else None
    ch["old_raw"] = old_p["raw"] if old_p else None
    ch["old"] = old
    ch["new"] = new
    ch["new_rich"] = (new_p.get("rich", new) if new_p else None)
    src = new_p or old_p
    ch["kind"] = src["kind"]
    ch["level"] = src["level"]
    if kind_type == "changed" and old_p and new_p:
        ch["old_level"] = old_p["level"]
        ch["word_diff"] = word_diff(_norm(old), _norm(new))
        ch["minor"] = (note is None) and _depunct(old) == _depunct(new)
    elif kind_type == "format":
        ch["word_diff"] = ""
        ch["minor"] = False
    elif kind_type == "deleted":
        ch["word_diff"] = "[-" + _norm(old) + "-]"
        ch["minor"] = False
    else:
        ch["word_diff"] = "{+" + _norm(new) + "+}"
        ch["minor"] = False
    if note:
        ch["note"] = note
    ch["context_before"] = _context(md_paras, before_i)
    ch["context_after"] = _context(md_paras, after_i)
    return ch


def diff_paragraphs(md_paras, other_paras):
    """Compare md paragraphs with DOCX (or editor) paragraphs -> (changes, format_changes)."""
    a = [_norm(p["plain"]) for p in md_paras]
    b = [_norm(p["plain"]) for p in other_paras]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    changes, fmt_changes = [], []
    last_md = -1

    def same_text_pair(i, j):
        mp, op = md_paras[i], other_paras[j]
        if (mp["kind"] == "heading" or op["kind"] == "heading") and \
                (mp["kind"], mp["level"]) != (op["kind"], op["level"]):
            changes.append(_change("changed", md_paras, other_paras, i, j, note="heading level"))
            return
        if mp["kind"] != "heading" and "runs" in mp and "runs" in op \
                and _fmt_sig(mp["runs"]) != _fmt_sig(op["runs"]):
            fmt_changes.append(_change("format", md_paras, other_paras, i, j))

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                same_text_pair(i1 + k, j1 + k)
            last_md = i2 - 1
        elif tag == "delete":
            for i in range(i1, i2):
                changes.append(_change("deleted", md_paras, other_paras, i, None))
            last_md = i2 - 1
        elif tag == "insert":
            for j in range(j1, j2):
                changes.append(_change("added", md_paras, other_paras, None, j, after=last_md))
        else:  # replace: pair greedily by similarity, in order
            jp = j1
            for i in range(i1, i2):
                found = None
                for jj in range(jp, min(j2, jp + _PAIR_WINDOW)):
                    if a[i] == b[jj] or _similar(a[i], b[jj]):
                        found = jj
                        break
                if found is None:
                    changes.append(_change("deleted", md_paras, other_paras, i, None))
                else:
                    for jj in range(jp, found):
                        changes.append(_change("added", md_paras, other_paras, None, jj,
                                               after=last_md))
                    if a[i] == b[found]:
                        same_text_pair(i, found)
                    else:
                        changes.append(_change("changed", md_paras, other_paras, i, found))
                    jp = found + 1
                last_md = i
            for jj in range(jp, j2):
                changes.append(_change("added", md_paras, other_paras, None, jj, after=last_md))
            last_md = i2 - 1
    return changes, fmt_changes


# ----------------------------------------------------------------------------------------
# chapter check
# ----------------------------------------------------------------------------------------

def git_dirty(root, relpath):
    """True / False: uncommitted changes to relpath; None when root is not a git repo."""
    try:
        r = subprocess.run(["git", "-C", root, "--no-optional-locks", "status", "--porcelain",
                            "--", relpath], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return bool(r.stdout.strip())


def _summary(changes, fmt_changes):
    return {"changed": sum(1 for c in changes if c["type"] == "changed"),
            "added": sum(1 for c in changes if c["type"] == "added"),
            "deleted": sum(1 for c in changes if c["type"] == "deleted"),
            "minor": sum(1 for c in changes if c.get("minor")),
            "format": len(fmt_changes)}


def check_chapter(conf, ch, docx=None, quote_mode="group", manifest=None):
    """Compare one chapter's .md with its DOCX -> result dict (see the JSON schema in the docs)."""
    root = conf["_root"]
    try:
        docx = docx or bookconf.find_review_docx(conf, ch, manifest)
    except bookconf.BookError as e:
        raise ChapterError(str(e))
    if not docx or not os.path.isfile(docx):
        raise ChapterError("no review DOCX found for chapter %s (looked in %s)"
                           % (ch.key, bookconf.path(conf, "review_dir")))
    try:
        md_text = bookconf.read_text(ch.path)
    except bookconf.BookError as e:
        raise ChapterError(str(e))
    try:
        d_paras, tracked = docx_paragraphs(docx)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ChapterError("cannot read DOCX %s: %s" % (docx, e))
    md_paras = md_paragraphs(md_text, quote_mode)
    changes, fmt_changes = diff_paragraphs(md_paras, d_paras)
    md_ts, docx_ts = _mtime(ch.path), _mtime(docx)
    return {"md": ch.rel, "docx": docx, "open": office.is_open(docx),
            "md_mtime": _iso(md_ts), "docx_mtime": _iso(docx_ts),
            "docx_stale": bool(md_ts is not None and docx_ts is not None and md_ts > docx_ts),
            "md_dirty": git_dirty(root, ch.rel),
            "tracked_changes": tracked, "changes": changes, "format_changes": fmt_changes,
            "summary": _summary(changes, fmt_changes)}


def scan_book(conf, quote_mode="group"):
    """Every chapter that has a review DOCX -> {"chapters": [...], "differing": n}."""
    out = []
    manifest = bookconf.load_manifest(conf)
    for ch in bookconf.chapters(conf):
        try:
            docx = bookconf.find_review_docx(conf, ch, manifest)
        except bookconf.BookError as e:
            out.append({"key": ch.key, "md": ch.rel, "docx": None, "error": str(e)})
            continue
        if not docx:
            continue
        try:
            res = check_chapter(conf, ch, docx, quote_mode, manifest)
        except ChapterError as e:
            out.append({"key": ch.key, "md": ch.rel, "docx": docx, "error": str(e)})
            continue
        n = len(res["changes"]) + len(res["format_changes"])
        out.append({"key": ch.key, "md": ch.rel, "docx": docx, "open": res["open"],
                    "docx_stale": res["docx_stale"], "differs": n > 0, "count": n,
                    "summary": res["summary"]})
    return {"chapters": out, "differing": sum(1 for c in out if c.get("differs"))}


# ----------------------------------------------------------------------------------------
# readable report
# ----------------------------------------------------------------------------------------

_TYPE_LABEL = {"changed": "CHANGED", "added": "ADDED", "deleted": "DELETED", "format": "FORMAT"}


def _compact_diff(wd, keep=8):
    """Shorten long unchanged stretches of a word diff for the readable report."""
    words = wd.split(" ")
    marked = [False] * len(words)
    inside = False
    for k, w in enumerate(words):
        if w.startswith("[-") or w.startswith("{+"):
            inside = True
        if inside:
            marked[k] = True
        if w.endswith("-]") or w.endswith("+}"):
            inside = False
    if not any(marked):
        return wd
    near = [False] * len(words)
    for k, m in enumerate(marked):
        if m:
            for q in range(max(0, k - keep), min(len(words), k + keep + 1)):
                near[q] = True
    out, skipping = [], False
    for k, w in enumerate(words):
        if near[k]:
            out.append(w)
            skipping = False
        elif not skipping:
            out.append("…")
            skipping = True
    return " ".join(out)


def _lines_label(ch):
    if ch["type"] == "added":
        return "after line %d" % ch["after_line"]
    a, b = ch["md_lines"]
    return "line %d" % a if a == b else "lines %d-%d" % (a, b)


def _format_change(ch, indent="  "):
    head = "[%s] %s" % (_TYPE_LABEL[ch["type"]], _lines_label(ch))
    if ch.get("note"):
        head += " (%s)" % ch["note"]
    lines = [head]
    if ch["type"] != "added":
        lines.append(indent + "before: " + (ch["old_raw"] or ""))
    if ch["type"] != "deleted":
        lines.append(indent + "after:  " + (ch["new_rich"] if ch["type"] == "format" else ch["new"]))
    if ch["type"] in ("changed", "deleted", "added") and ch.get("word_diff"):
        lines.append(indent + "diff:   " + _compact_diff(ch["word_diff"]))
    if ch.get("minor"):
        lines.append(indent + "minor (punctuation or spacing only)")
    if ch["type"] in ("added", "changed") and ch.get("level"):
        lines.append(indent + "heading level %d" % ch["level"])
    if ch.get("context_before"):
        lines.append(indent + "context before: " + ch["context_before"])
    if ch.get("context_after"):
        lines.append(indent + "context after:  " + ch["context_after"])
    return "\n".join(lines)


def format_report(res):
    lines = ["%s  <-  %s" % (res["md"], res["docx"])]
    if res["open"]:
        lines.append("WARNING: the DOCX is open in %s; the author may still be editing." % res["open"])
    if res["docx_stale"]:
        lines.append("WARNING: the .md is newer than the DOCX (%s > %s): some differences may be "
                     "source changes that never reached the DOCX, not the author's edits."
                     % (res["md_mtime"], res["docx_mtime"]))
    if res["md_dirty"]:
        lines.append("note: the .md has uncommitted changes.")
    if res["tracked_changes"]:
        lines.append("note: tracked changes present in the DOCX; insertions are kept, deletions "
                     "ignored.")
    lines.append("")
    for ch in res["changes"] + res["format_changes"]:
        lines.append(_format_change(ch))
        lines.append("")
    s = res["summary"]
    lines.append("Summary: %d changed (%d minor), %d added, %d deleted, %d format-only"
                 % (s["changed"], s["minor"], s["added"], s["deleted"], s["format"]))
    return "\n".join(lines)


def format_scan_report(res):
    lines = []
    for c in res["chapters"]:
        if "error" in c:
            lines.append("%-8s ERROR %s" % (c["key"], c["error"]))
            continue
        flag = "differs (%d)" % c["count"] if c["differs"] else "same"
        extra = (" [open in %s]" % c["open"] if c["open"] else "") + \
                (" [DOCX older than .md]" if c["docx_stale"] else "")
        lines.append("%-8s %s  %s%s" % (c["key"], flag, c["md"], extra))
    lines.append("")
    lines.append("%d of %d chapters with a review DOCX differ" % (res["differing"], len(res["chapters"])))
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(prog="docx_diff.py", description="Compare a chapter's DOCX with its "
                                ".md and report every paragraph the author changed (read-only).")
    p.add_argument("chapter", nargs="?", help="chapter key (3, 3z, a stem) or path to the .md")
    p.add_argument("--root", help="folder inside the book (default: cwd)")
    p.add_argument("--docx", help="DOCX to compare (default: the chapter's review DOCX)")
    p.add_argument("--scan", action="store_true", help="check every chapter that has a review DOCX")
    p.add_argument("--quote-mode", choices=["group", "separate"], default="group",
                   help="how '>' lines become paragraphs: grouped like md2docx.js (default) or one each")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        if not args.scan and not args.chapter:
            raise ChapterError("give a chapter, or --scan")
        try:
            conf = bookconf.load(args.root)
            if args.scan:
                res = scan_book(conf, args.quote_mode)
                differs = res["differing"] > 0
                text = format_scan_report(res)
            else:
                ch = bookconf.resolve(conf, args.chapter)
                res = check_chapter(conf, ch, args.docx, args.quote_mode)
                differs = bool(res["changes"] or res["format_changes"])
                text = format_report(res)
        except bookconf.BookError as e:
            raise ChapterError(str(e))
    except ChapterError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else text)
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main())
