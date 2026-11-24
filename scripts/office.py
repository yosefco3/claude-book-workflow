#!/usr/bin/env python3
"""Office tools for the book workflow (stdlib only, Python 3.9+).

Answers three questions:
  * which office tools are installed (detect),
  * how to convert files with them (convert, docx_text),
  * whether a DOCX is currently open in an editor, so a rebuild does not overwrite the
    author's work (is_open).

Public API (other scripts import these):
    find_chrome() -> str | None
    is_open(docx_path, proc_root="/proc") -> str | None
    detect() -> dict
    convert(src, to, outdir=None, tool=None) -> str      (raises OfficeError)
    docx_text(path) -> str

Environment overrides:
    BOOK_CHROME        path of a Chrome/Chromium/Edge binary
    BOOK_CHROME_NO_SANDBOX  "1" adds --no-sandbox (otherwise only when running as root)
    BOOK_OFFICE        force the docx->pdf tool: word | libreoffice | wordcraft
    BOOK_EDITOR_PROCS  comma-separated process names of editors that autosave without lock
                       files (default "wordcraft"); Linux only

CLI: python3 office.py detect [--json] | is-open <docx> | convert <src> --to T | text <docx>
"""
import argparse
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

TIMEOUT = 120


class OfficeError(Exception):
    """Raised when a conversion cannot be done; the message says what to install."""


# ---------------------------------------------------------------- platform helpers

def _os_name():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _win_dirs():
    out = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        v = os.environ.get(var)
        if v:
            out.append(v)
    if not out:
        out = [r"C:\Program Files", r"C:\Program Files (x86)"]
    return out


# ---------------------------------------------------------------- tool finders

_CHROME_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "msedge", "chrome"]


def find_chrome():
    """Path of a Chrome/Chromium/Edge binary that can print HTML to PDF, or None."""
    env = os.environ.get("BOOK_CHROME")
    if env and os.path.exists(env):
        return env
    for name in _CHROME_NAMES:
        p = shutil.which(name)
        if p:
            return p
    osn = _os_name()
    if osn == "macos":
        return _first_existing([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"])
    if osn == "windows":
        cands = []
        for d in _win_dirs():
            cands += [os.path.join(d, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(d, "Microsoft", "Edge", "Application", "msedge.exe")]
        return _first_existing(cands)
    return None


def chrome_flags():
    """Headless flags for Chrome. "--no-sandbox" only where Chrome cannot start without it:
    running as root, or BOOK_CHROME_NO_SANDBOX=1 (containers). Never by default."""
    flags = ["--headless=new", "--disable-gpu"]
    geteuid = getattr(os, "geteuid", None)
    if (geteuid and geteuid() == 0) or os.environ.get("BOOK_CHROME_NO_SANDBOX") == "1":
        flags.append("--no-sandbox")
    return flags


def file_url(p):
    """file:// URL of a local path (handles spaces, #, ?, non-ASCII)."""
    return pathlib.Path(p).resolve().as_uri()


def _find_soffice():
    for n in ("soffice", "libreoffice"):
        p = shutil.which(n)
        if p:
            return p
    osn = _os_name()
    if osn == "macos":
        return _first_existing(["/Applications/LibreOffice.app/Contents/MacOS/soffice"])
    if osn == "windows":
        return _first_existing([os.path.join(d, "LibreOffice", "program", "soffice.exe")
                                for d in _win_dirs()])
    return None


def _find_word():
    osn = _os_name()
    if osn == "macos":
        return _first_existing(["/Applications/Microsoft Word.app"])
    if osn == "windows":
        p = shutil.which("winword")
        if p:
            return p
        cands = []
        for d in _win_dirs():
            for root in ("Microsoft Office", "Microsoft Office 15", "Microsoft Office 16"):
                for sub in ("root\\Office16", "root\\Office15", "Office16", "Office15", "Office14"):
                    cands.append(os.path.join(d, root, sub.replace("\\", os.sep), "WINWORD.EXE"))
        return _first_existing(cands)
    return None


def _find_onlyoffice():
    for n in ("onlyoffice-desktopeditors", "DesktopEditors"):
        p = shutil.which(n)
        if p:
            return p
    if _os_name() == "macos":
        return _first_existing(["/Applications/ONLYOFFICE.app"])
    if _os_name() == "windows":
        return _first_existing([os.path.join(d, "ONLYOFFICE", "DesktopEditors", "DesktopEditors.exe")
                                for d in _win_dirs()])
    return None


def _has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _word_via_docx2pdf():
    """docx2pdf drives Microsoft Word; it only works on Windows and macOS."""
    return _os_name() in ("windows", "macos") and _has_module("docx2pdf")


# ---------------------------------------------------------------- is_open

def _editor_procs():
    raw = os.environ.get("BOOK_EDITOR_PROCS")
    if raw is None:
        raw = "wordcraft"
    return [p.strip() for p in raw.split(",") if p.strip()]


def _proc_open(path, proc_root, names):
    """Scan a /proc-like tree for editor processes holding `path`.
    Returns the matching process name, "<name>?" if one runs with no file argument, or None."""
    target = os.path.realpath(path)
    bare = None
    try:
        pids = [d for d in os.listdir(proc_root) if d.isdigit()]
    except OSError:
        return None
    for pid in pids:
        base = os.path.join(proc_root, pid)
        try:
            with open(os.path.join(base, "comm"), encoding="utf-8", errors="replace") as f:
                comm = f.read().strip()
            if comm not in names:
                continue
            with open(os.path.join(base, "cmdline"), "rb") as f:
                argv = f.read().split(b"\0")
            if not argv[0]:
                continue  # zombie: empty command line
            args = [a.decode("utf-8", "surrogateescape") for a in argv[1:]
                    if a and not a.startswith(b"-")]
            cwd = os.readlink(os.path.join(base, "cwd")) if any(not os.path.isabs(a) for a in args) else None
        except OSError:
            continue  # unreadable or vanished pid
        if not args:
            bare = bare or comm
        for a in args:
            if not os.path.isabs(a):
                if cwd is None:
                    continue
                a = os.path.join(cwd, a)
            if os.path.realpath(a) == target:
                return comm
    return bare + "?" if bare else None


def is_open(docx_path, proc_root="/proc"):
    """None if the DOCX looks closed; otherwise a short reason string:
    "libreoffice" (.~lock file), "word" (~$ owner file), "locked" (Windows exclusive lock),
    or an editor process name such as "wordcraft" / "wordcraft?" (Linux, no lock file)."""
    d, name = os.path.split(os.path.abspath(docx_path))
    if os.path.exists(os.path.join(d, ".~lock.%s#" % name)):
        return "libreoffice"
    owners = {"~$" + name[2:], "~$" + name}
    if any(os.path.exists(os.path.join(d, o)) for o in owners):
        return "word"
    if _os_name() == "windows" and os.path.exists(docx_path):
        try:
            with open(docx_path, "r+b"):
                pass
        except PermissionError:
            return "locked"
        except OSError:
            pass
    if _os_name() == "linux" or proc_root != "/proc":
        r = _proc_open(docx_path, proc_root, _editor_procs())
        if r:
            return r
    return None


# ---------------------------------------------------------------- detect

def detect():
    """Installed office tools, JSON-serialisable."""
    osn = _os_name()
    editors = []

    def add(name, path):
        if path:
            editors.append({"name": name, "path": path})

    add("Microsoft Word", _find_word())
    add("LibreOffice", _find_soffice())
    add("OnlyOffice", _find_onlyoffice())
    add("WordCraft", shutil.which("wordcraft"))
    if osn == "macos":
        add("Apple Pages", _first_existing(["/Applications/Pages.app"]))

    pdf = []
    if _find_word() and _word_via_docx2pdf():
        pdf.append("word")
    if _find_soffice():
        pdf.append("libreoffice")
    if shutil.which("wordcraft-cli"):
        pdf.append("wordcraft")

    png = []
    if shutil.which("rsvg-convert"):
        png.append("rsvg-convert")
    if shutil.which("inkscape"):
        png.append("inkscape")
    if _has_module("cairosvg"):
        png.append("cairosvg")
    if _find_soffice():
        png.append("libreoffice")
    chrome = find_chrome()
    if chrome:
        png.append("chrome")

    info = {"os": osn, "editors": editors, "docx_to_pdf": pdf, "svg_to_png": png,
            "html_to_pdf": chrome, "docx_text": "builtin"}
    if shutil.which("pandoc"):
        info["pandoc"] = shutil.which("pandoc")  # docx -> txt/md only
    return info


# ---------------------------------------------------------------- docx text

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _para_text(p):
    out = []

    def walk(el, deleted):
        for ch in el:
            if ch.tag == _W + "del":
                continue  # tracked deletion: skip everything inside
            if ch.tag == _W + "t":
                out.append(ch.text or "")
            elif ch.tag == _W + "tab":
                out.append("\t")
            elif ch.tag in (_W + "br", _W + "cr"):
                out.append("\n")
            else:
                walk(ch, deleted)

    walk(p, False)
    return "".join(out)


def docx_text(path):
    """Plain text of a DOCX: one line per paragraph. Tracked deletions are skipped,
    tracked insertions kept. Pure Python, no external tool."""
    try:
        with zipfile.ZipFile(path) as z:
            data = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise OfficeError("cannot read %s as a DOCX: %s" % (path, e))
    root = ET.fromstring(data)
    return "\n".join(_para_text(p) for p in root.iter(_W + "p"))


# ---------------------------------------------------------------- convert

def _run(cmd, what):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise OfficeError("%s timed out after %d s" % (what, TIMEOUT))
    except OSError as e:
        raise OfficeError("could not run %s: %s" % (what, e))
    return r


def _check_out(out, what, r=None):
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        extra = ""
        if r is not None:
            extra = " (exit %s) %s" % (r.returncode, (r.stderr or b"").decode("utf-8", "replace")[-300:])
        raise OfficeError("%s did not produce %s%s" % (what, out, extra))
    return out


def _soffice_convert(soffice, src, fmt, outdir, out):
    # a private profile avoids clashes with a running LibreOffice instance
    with tempfile.TemporaryDirectory() as prof:
        uri = file_url(prof)
        r = _run([soffice, "-env:UserInstallation=" + uri, "--headless", "--convert-to", fmt,
                  "--outdir", outdir, src], "LibreOffice")
    return _check_out(out, "LibreOffice", r)


def _svg_size(src):
    try:
        root = ET.parse(src).getroot()
    except (ET.ParseError, OSError):
        return 1000, 1250

    def num(v):
        m = re.match(r"\s*([0-9.]+)", v or "")
        return float(m.group(1)) if m else None

    w, h = num(root.get("width")), num(root.get("height"))
    if not (w and h):
        vb = (root.get("viewBox") or "").replace(",", " ").split()
        if len(vb) == 4:
            try:
                w, h = float(vb[2]), float(vb[3])
            except ValueError:
                pass
    if w and h:
        return int(round(w)), int(round(h))
    return 1000, 1250


def _docx_to_pdf(src, outdir, out, tool):
    tool = (tool or os.environ.get("BOOK_OFFICE") or "").lower() or None
    order = [tool] if tool else ["word", "libreoffice", "wordcraft"]
    tried = []
    for t in order:
        if t == "word":
            if _word_via_docx2pdf():
                try:
                    import docx2pdf  # type: ignore
                    docx2pdf.convert(src, out)
                    return _check_out(out, "Word (docx2pdf)")
                except OfficeError:
                    raise
                except Exception as e:  # docx2pdf raises many kinds
                    if tool:
                        raise OfficeError("Word conversion failed: %s" % e)
                    tried.append("word (%s)" % e)
            elif tool:
                raise OfficeError("Word conversion needs Windows or macOS with Microsoft Word "
                                  "and 'pip install docx2pdf'")
        elif t == "libreoffice":
            so = _find_soffice()
            if so:
                return _soffice_convert(so, src, "pdf", outdir, out)
            if tool:
                raise OfficeError("LibreOffice not found (install it from libreoffice.org)")
        elif t == "wordcraft":
            wc = shutil.which("wordcraft-cli")
            if wc:
                r = _run([wc, "convert", src, out], "wordcraft-cli")
                return _check_out(out, "wordcraft-cli", r)
            if tool:
                raise OfficeError("wordcraft-cli not found on PATH")
        else:
            raise OfficeError("unknown tool %r (use word, libreoffice or wordcraft)" % t)
    raise OfficeError("no tool found to convert DOCX to PDF. Install one of: LibreOffice "
                      "(libreoffice.org), Microsoft Word plus 'pip install docx2pdf' "
                      "(Windows/macOS), or WordCraft (wordcraft-cli)." +
                      (" Tried: " + "; ".join(tried) if tried else ""))


def _svg_to_png(src, outdir, out, tool):
    cands = []
    if shutil.which("rsvg-convert"):
        cands.append("rsvg-convert")
    if shutil.which("inkscape"):
        cands.append("inkscape")
    if _has_module("cairosvg"):
        cands.append("cairosvg")
    if _find_soffice():
        cands.append("libreoffice")
    if find_chrome():
        cands.append("chrome")
    if tool:
        if tool not in cands:
            raise OfficeError("svg->png tool %r not available; available: %s" % (tool, cands or "none"))
        cands = [tool]
    errors = []
    for t in cands:
        try:
            if os.path.exists(out):
                os.remove(out)
            if t == "rsvg-convert":
                r = _run(["rsvg-convert", "-o", out, src], "rsvg-convert")
                return _check_out(out, "rsvg-convert", r)
            if t == "inkscape":
                r = _run(["inkscape", src, "--export-type=png", "--export-filename=" + out], "inkscape")
                return _check_out(out, "inkscape", r)
            if t == "cairosvg":
                import cairosvg  # type: ignore
                cairosvg.svg2png(url=src, write_to=out)
                return _check_out(out, "cairosvg")
            if t == "libreoffice":
                return _soffice_convert(_find_soffice(), src, "png", outdir, out)
            if t == "chrome":
                w, h = _svg_size(src)
                r = _run([find_chrome(), *chrome_flags(),
                          "--hide-scrollbars", "--screenshot=" + out,
                          "--window-size=%d,%d" % (w, h), file_url(src)],
                         "Chrome")
                return _check_out(out, "Chrome", r)
        except OfficeError as e:
            errors.append("%s: %s" % (t, e))
        except Exception as e:
            errors.append("%s: %s" % (t, e))
    raise OfficeError("no tool could convert SVG to PNG. Install one of: rsvg-convert "
                      "(librsvg), inkscape, 'pip install cairosvg', LibreOffice, or Chrome." +
                      (" Errors: " + " | ".join(errors) if errors else ""))


def convert(src, to, outdir=None, tool=None):
    """Convert `src` to format `to` (pdf, txt, png, docx). Returns the output path.
    Raises OfficeError with install hints when no suitable tool exists."""
    src = os.path.abspath(src)
    if not os.path.exists(src):
        raise OfficeError("source not found: %s" % src)
    to = to.lower().lstrip(".")
    ext = os.path.splitext(src)[1].lower().lstrip(".")
    outdir = os.path.abspath(outdir) if outdir else os.path.dirname(src)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + "." + to)

    if ext == "docx" and to == "pdf":
        return _docx_to_pdf(src, outdir, out, tool)
    if ext == "docx" and to == "txt":
        with open(out, "w", encoding="utf-8") as f:
            f.write(docx_text(src))
        return out
    if ext == "svg" and to == "png":
        return _svg_to_png(src, outdir, out, tool)
    if ext in ("html", "htm") and to == "pdf":
        chrome = find_chrome()
        if not chrome:
            raise OfficeError("HTML to PDF needs Chrome, Chromium or Edge; install one or set BOOK_CHROME")
        r = _run([chrome, *chrome_flags(), "--no-pdf-header-footer",
                  "--run-all-compositor-stages-before-draw", "--virtual-time-budget=10000",
                  "--print-to-pdf=" + out, file_url(src)], "Chrome")
        return _check_out(out, "Chrome", r)
    if ext in ("docx", "odt", "rtf") and to == "docx":
        if out == src:
            raise OfficeError("output would overwrite the source; pass a different outdir")
        so = _find_soffice()
        if not so:
            raise OfficeError("converting to DOCX needs LibreOffice (libreoffice.org)")
        return _soffice_convert(so, src, "docx", outdir, out)
    if ext == "md" and to == "docx":
        raise OfficeError("Markdown to DOCX is not done here; use the skill's md2docx.js")
    raise OfficeError("unsupported conversion: .%s -> .%s" % (ext, to))


# ---------------------------------------------------------------- CLI

def _print_detect(info):
    print("OS: %s" % info["os"])
    print("Editors:")
    for e in info["editors"] or []:
        print("  %-16s %s" % (e["name"], e["path"]))
    if not info["editors"]:
        print("  (none found)")
    print("DOCX -> PDF : %s" % (", ".join(info["docx_to_pdf"]) or "none"))
    print("SVG  -> PNG : %s" % (", ".join(info["svg_to_png"]) or "none"))
    print("HTML -> PDF : %s" % (info["html_to_pdf"] or "none"))
    print("DOCX -> text: %s" % info["docx_text"])
    if "pandoc" in info:
        print("pandoc      : %s (docx to txt/md only)" % info["pandoc"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="office.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("detect")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("is-open")
    p.add_argument("docx")
    p = sub.add_parser("convert")
    p.add_argument("src")
    p.add_argument("--to", required=True, choices=["pdf", "txt", "png", "docx"])
    p.add_argument("--outdir")
    p.add_argument("--tool")
    p = sub.add_parser("text")
    p.add_argument("docx")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "detect":
            info = detect()
            if a.json:
                print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                _print_detect(info)
            return 0
        if a.cmd == "is-open":
            r = is_open(a.docx)
            print(r or "closed")
            return 1 if r else 0
        if a.cmd == "convert":
            print(convert(a.src, a.to, a.outdir, a.tool))
            return 0
        if a.cmd == "text":
            sys.stdout.write(docx_text(a.docx) + "\n")
            return 0
    except OfficeError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
