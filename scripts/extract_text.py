#!/usr/bin/env python3
"""Extract a source book (PDF, scanned PDF, EPUB, TXT/MD) to plain text with citable lines.

    python3 extract_text.py <file> [-o out.txt] [--ocr]

Default output: <book root>/.work/texts/<stem>.txt (book root = folder with book.json,
else the current folder). Lines are wrapped at about 100 characters so that
"file:line" is a usable citation. Scanned PDFs get "=== page N ===" markers.
Stdlib only; PDF needs poppler-utils, OCR also needs tesseract.
"""
import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import bookconf
except Exception:  # pragma: no cover
    bookconf = None

WRAP = 100
MIN_TEXT_CHARS = 200  # a PDF text layer shorter than this counts as "no text"


class ToolError(Exception):
    pass


def need(tool, package):
    path = shutil.which(tool)
    if not path:
        raise ToolError("%s not found; install the package %s" % (tool, package))
    return path


def wrap_text(text):
    """Wrap every paragraph line to ~WRAP chars, keeping blank lines and markdown headings."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.rstrip()
        if not line.strip():
            out.append("")
        elif line.startswith("#") or line.startswith("=== page"):
            out.append(line)
        else:
            out.extend(textwrap.wrap(line, WRAP, break_long_words=False, break_on_hyphens=False) or [""])
    return "\n".join(out).strip() + "\n"


# ---------- EPUB ----------

class _Html(HTMLParser):
    BLOCK = {"p", "div", "li", "br", "tr", "blockquote", "section", "article"}
    HEAD = {"h1": "# ", "h2": "## ", "h3": "### "}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.head = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        elif tag in self.HEAD:
            self.parts.append("\n\n")
            self.head = self.HEAD[tag]
            self.parts.append(self.head)
        elif tag in self.BLOCK:
            self.parts.append("\n\n" if tag != "br" else "\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.HEAD:
            self.head = None
            self.parts.append("\n\n")
        elif tag in self.BLOCK and tag != "br":
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(re.sub(r"\s+", " ", data))

    def text(self):
        t = "".join(self.parts)
        t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def epub_to_text(path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        container = ET.fromstring(z.read("META-INF/container.xml"))
        opf_path = next(e.get("full-path") for e in container.iter() if _local(e.tag) == "rootfile")
        opf = ET.fromstring(z.read(opf_path))
        base = posixpath.dirname(opf_path)
        manifest = {e.get("id"): e.get("href") for e in opf.iter() if _local(e.tag) == "item"}
        spine = [e.get("idref") for e in opf.iter() if _local(e.tag) == "itemref"]
        chunks = []
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            name = posixpath.normpath(posixpath.join(base, href.split("#")[0]))
            try:
                raw = z.read(name).decode("utf-8", errors="replace")
            except KeyError:
                continue
            p = _Html()
            p.feed(raw)
            t = p.text()
            if t:
                chunks.append(t)
    return wrap_text("\n\n".join(chunks))


# ---------- PDF ----------

def pdf_text_layer(path):
    exe = need("pdftotext", "poppler-utils")
    r = subprocess.run([exe, "-layout", path, "-"], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        raise ToolError("pdftotext failed: %s" % r.stderr.strip())
    return r.stdout


def pdf_ocr(path, lang):
    pdftoppm = need("pdftoppm", "poppler-utils")
    tess = need("tesseract", "tesseract-ocr (and its language data, e.g. tesseract-ocr-heb)")
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([pdftoppm, "-r", "300", "-png", path, os.path.join(tmp, "p")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolError("pdftoppm failed: %s" % r.stderr.strip())
        pages = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        for n, f in enumerate(pages, 1):
            r = subprocess.run([tess, os.path.join(tmp, f), "-", "-l", lang],
                               capture_output=True, text=True, errors="replace")
            if r.returncode != 0:
                raise ToolError("tesseract failed on page %d: %s" % (n, r.stderr.strip()))
            out.append("=== page %d ===\n%s" % (n, r.stdout))
    return "\n\n".join(out)


def book_lang(start):
    if bookconf:
        try:
            return bookconf.load(start).get("lang", "en")
        except Exception:
            pass
    return "en"


def pdf_to_text(path, ocr, lang):
    if not ocr:
        text = pdf_text_layer(path)
        if len(text.strip()) >= MIN_TEXT_CHARS:
            return wrap_text(text.replace("\f", "\n\n"))
        print("note: no usable text layer, running OCR", file=sys.stderr)
    return wrap_text(pdf_ocr(path, "heb+eng" if lang == "he" else "eng"))


def default_out(src):
    root = os.getcwd()
    if bookconf:
        try:
            root = bookconf.find_root()
        except Exception:
            pass
    return os.path.join(root, ".work", "texts", os.path.splitext(os.path.basename(src))[0] + ".txt")


def extract(src, ocr=False, lang="en"):
    ext = os.path.splitext(src)[1].lower()
    if ext == ".pdf":
        return pdf_to_text(src, ocr, lang)
    if ext == ".epub":
        return epub_to_text(src)
    if ext in (".txt", ".md"):
        with open(src, encoding="utf-8-sig", errors="replace") as f:
            return wrap_text(f.read())
    raise ToolError("unsupported file type %r (use PDF, EPUB, TXT or MD)" % ext)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("-o", "--out", help="output path (default .work/texts/<stem>.txt under the book root)")
    ap.add_argument("--ocr", action="store_true", help="force OCR for a PDF")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.file):
        print("error: no such file: %s" % a.file, file=sys.stderr)
        return 2
    try:
        text = extract(a.file, a.ocr, book_lang(None))
    except ToolError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    except (zipfile.BadZipFile, KeyError, StopIteration) as e:
        print("error: cannot read EPUB: %r" % e, file=sys.stderr)
        return 2
    out = a.out or default_out(a.file)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("%s: %d lines" % (out, text.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
