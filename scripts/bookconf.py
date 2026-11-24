"""Shared helpers: load a book's book.json and list its chapters in book order.

Layout (all names configurable in book.json):

    <book root>/
      book.json
      manuscript/                 the single source of truth
        00-front/01-intro.md      part folder / chapter file
        01-part-one/02-x.md       NN- prefix = chapter number
        01-part-one/02z-recap.md  NNz- = summary page, unnumbered
        01-part-one/_notes.md     leading "_" = skipped by every build
        99-back/90-thanks.md      parts listed in unnumbered_parts have no chapter numbers
        assets/                   figures (not a part)
      build/                      generated, overwritten on every run
      review/                     one DOCX per chapter for the author

Stdlib only. Import it from a script in this folder:

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bookconf
"""
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass

CONFIG_NAME = "book.json"

DEFAULTS = {
    "title": "",
    "subtitle": "",
    "author": "",
    "lang": "he",
    "dir": "rtl",
    "manuscript_dir": "manuscript",
    "build_dir": "build",
    "output_name": "book",
    "review_dir": "review",
    "review_name": "פרק {n} - {title}.docx",
    "review_name_unnumbered": "{title}.docx",
    "unnumbered_parts": [],
    "parts": {},
    "forbidden_chars": ["—"],
    "fonts": {"body": "Noto Serif Hebrew", "heading": "Noto Sans Hebrew"},
    "page_size": "A5",
    "special_headings": {"deep": "להעמקה", "sources": "מקורות לפרק זה"},
    "overwrite_open": [],
    # how language corrections go in: "apply" (directly, then reported) or "propose" (shown first)
    "language_fixes": "propose",
    "copyright": [],
    "labels": {"chapter": "פרק", "contents": "תוכן העניינים", "draft": "טיוטה – לא להפצה"},
}

# folders directly under the manuscript that are never parts
NON_PART_DIRS = {"assets", "cover", "figures", "images"}

_NUM_RE = re.compile(r"^(\d+)(z?)-")
# characters that are not allowed in file names on Windows (and "/" anywhere)
_BAD_NAME = {"/": "-", "\\": "-", ":": " -", "*": "", "?": "", "<": "", ">": "", "|": "-"}
_HEBREW_RE = re.compile("[\u0590-\u05ff]")
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}
MAX_NAME_BYTES = 200  # file names stay under this many UTF-8 bytes
MANIFEST_NAME = ".sync-state.json"


@dataclass
class Chapter:
    path: str           # absolute path of the .md
    rel: str            # path relative to the book root, with "/"
    part: str           # part folder name, e.g. "01-basics"
    number: object      # int, or None when unnumbered
    summary: bool       # NNz- file
    key: str            # "3", "3z", or the file stem for unnumbered files without a number
    title: str          # first "# " line, or the file stem


class BookError(Exception):
    pass


def find_root(start=None):
    """Walk up from `start` (default: cwd) to the folder that holds book.json."""
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, CONFIG_NAME)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise BookError("no %s found in %s or any parent folder" % (CONFIG_NAME, start or os.getcwd()))
        d = parent


def load(root=None):
    """Config dict: book.json merged over DEFAULTS, plus "_root" (absolute book root)."""
    root = find_root(root)
    cfg = os.path.join(root, CONFIG_NAME)
    try:
        with open(cfg, encoding="utf-8-sig") as f:
            user = json.load(f)
    except json.JSONDecodeError as e:
        raise BookError("%s is not valid JSON: %s (line %d, column %d, character %d)"
                        % (cfg, e.msg, e.lineno, e.colno, e.pos))
    except (OSError, UnicodeDecodeError) as e:
        raise BookError("cannot read %s: %s" % (cfg, e))
    if not isinstance(user, dict):
        raise BookError("%s must contain a JSON object" % cfg)
    conf = dict(DEFAULTS)
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(conf.get(k), dict):
            conf[k] = {**conf[k], **v}
        else:
            conf[k] = v
    conf["_root"] = root
    return conf


def path(conf, key, *more):
    """Absolute path of a configured folder ("manuscript_dir", "build_dir", "review_dir")."""
    return os.path.join(conf["_root"], conf[key], *more)


def build_output(conf, ext):
    """build/<output_name>.<ext>"""
    return path(conf, "build_dir", "%s.%s" % (conf["output_name"], ext))


def read_text(fpath):
    """Text of a chapter file: UTF-8, a leading BOM is dropped; BookError naming the file when
    it cannot be read or is not UTF-8."""
    try:
        with open(fpath, encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise BookError("%s is not valid UTF-8 (byte %d): save it as UTF-8" % (fpath, e.start))
    except OSError as e:
        raise BookError("cannot read %s: %s" % (fpath, e))


def _title_of(fpath, fallback):
    for line in read_text(fpath).split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def natural_key(name):
    """Sort key: leading number as a number (9- before 10-), then the name; unnumbered last."""
    m = re.match(r"\d+", name)
    return (0, int(m.group()), name) if m else (1, 0, name)


def part_dirs(conf):
    ms = path(conf, "manuscript_dir")
    if not os.path.isdir(ms):
        raise BookError("manuscript folder not found: %s" % ms)
    return sorted((d for d in os.listdir(ms)
                   if os.path.isdir(os.path.join(ms, d))
                   and d not in NON_PART_DIRS and not d.startswith(("_", "."))),
                  key=natural_key)


def chapters(conf, parts=None):
    """Every chapter in book order (part folders and files sorted by leading number, then name).

    `parts`: optional iterable of part folder names to keep.
    """
    out = []
    ms = path(conf, "manuscript_dir")
    unnumbered = set(conf.get("unnumbered_parts") or [])
    for part in part_dirs(conf):
        if parts is not None and part not in parts:
            continue
        pdir = os.path.join(ms, part)
        for fn in sorted(os.listdir(pdir), key=natural_key):
            if not fn.endswith(".md") or fn.startswith(("_", ".")):
                continue
            full = os.path.join(pdir, fn)
            if not os.path.isfile(full):
                continue
            stem = fn[:-3]
            m = _NUM_RE.match(fn)
            summary = bool(m and m.group(2))
            if m and not summary and part not in unnumbered:
                number, key = int(m.group(1)), str(int(m.group(1)))
            elif m and summary:
                number, key = None, "%dz" % int(m.group(1))
            else:
                number, key = None, (str(int(m.group(1))) if m else stem)
            rel = os.path.relpath(full, conf["_root"]).replace(os.sep, "/")
            out.append(Chapter(full, rel, part, number, summary, key, _title_of(full, stem)))
    return out


def resolve(conf, key):
    """One chapter by key ("3", "3z", a file stem) or by a path to its .md."""
    key = str(key).strip()
    chs = chapters(conf)
    if key.endswith(".md") or os.sep in key or "/" in key:
        want = os.path.realpath(key if os.path.isabs(key) else os.path.join(os.getcwd(), key))
        hits = [c for c in chs if os.path.realpath(c.path) == want]
        if not hits:
            want2 = os.path.realpath(os.path.join(conf["_root"], key))
            hits = [c for c in chs if os.path.realpath(c.path) == want2]
    else:
        m = re.fullmatch(r"(\d+)(z?)", key)
        k = "%d%s" % (int(m.group(1)), m.group(2)) if m else key
        hits = [c for c in chs if c.key == k or os.path.basename(c.path)[:-3] == key]
    if len(hits) != 1:
        raise BookError("chapter %r: %s" % (key, "not found" if not hits else
                        "ambiguous: " + ", ".join(c.rel for c in hits)))
    return hits[0]


def safe_filename(name):
    """File-system safe name: no characters Windows rejects, no control characters, no
    trailing dot or space, no reserved device names (CON, NUL, COM1 ...)."""
    name = re.sub(r"[\x00-\x1f]", "", name)
    for bad, good in _BAD_NAME.items():
        name = name.replace(bad, good)
    name = name.replace('"', "\u05f4" if _HEBREW_RE.search(name) else "'")
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    if stem.split(".")[0].strip().upper() in _WIN_RESERVED:
        stem += "_"
    return stem + ("." + ext if dot else "")


def _fill(conf, ch, title):
    pattern = conf["review_name"] if ch.number is not None else conf["review_name_unnumbered"]
    return safe_filename(pattern.format(n=ch.number if ch.number is not None else ch.key,
                                        title=title, key=ch.key, stem=os.path.basename(ch.path)[:-3]))


def review_name(conf, ch):
    """File name of the chapter's DOCX in the review folder (under MAX_NAME_BYTES bytes;
    the title is shortened when needed, and the key stands in for an empty title)."""
    title = ch.title.strip() or ch.key
    name = _fill(conf, ch, title)
    while len(name.encode("utf-8")) >= MAX_NAME_BYTES and len(title) > 1:
        over = len(name.encode("utf-8")) - (MAX_NAME_BYTES - 1)
        title = title[:max(1, len(title) - max(1, over // 3))].rstrip()
        name = _fill(conf, ch, title)
    return name


def review_prefix(conf, ch):
    """The part of the review name before {title} (informational; lookups use the manifest)."""
    pattern = conf["review_name"] if ch.number is not None else conf["review_name_unnumbered"]
    if "{title}" not in pattern:
        return None
    head = pattern.split("{title}", 1)[0]
    if not head.strip():
        return None
    return safe_filename(head.format(n=ch.number if ch.number is not None else ch.key,
                                     key=ch.key, stem=os.path.basename(ch.path)[:-3])) or None


# ---------------------------------------------------------------- sync manifest

def manifest_path(conf):
    return path(conf, "review_dir", MANIFEST_NAME)


def sha256_file(fpath):
    h = hashlib.sha256()
    with open(fpath, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(conf):
    """{docx name: {"key": chapter key, "sha256": hash as sync wrote it}}. Missing or unreadable
    manifest = empty (every existing DOCX is then treated as unknown and backed up before a rewrite)."""
    try:
        with open(manifest_path(conf), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and isinstance(v.get("key"), str) and isinstance(v.get("sha256"), str)}


def save_manifest(conf, manifest):
    """Atomic write (temp file in the same folder, then os.replace)."""
    target = manifest_path(conf)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sync-state.", suffix=".tmp", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def find_review_docx(conf, ch, manifest=None):
    """Existing DOCX of the chapter, or None.

    Exact name first. Otherwise (the title changed since the last sync) only a file that the sync
    manifest lists with this chapter's key. A file the manifest does not list is never picked up,
    even if its name starts like the chapter's ("Chapter 3 - my notes.docx" stays untouched).
    Two manifest files for one chapter: BookError naming both.
    """
    if manifest is None:
        manifest = load_manifest(conf)
    rdir = path(conf, "review_dir")
    exact = os.path.join(rdir, review_name(conf, ch))
    if os.path.isfile(exact):
        return exact
    hits = sorted(n for n, e in manifest.items()
                  if e["key"] == ch.key and n.endswith(".docx") and os.path.isfile(os.path.join(rdir, n)))
    if len(hits) > 1:
        raise BookError("chapter %s has more than one review DOCX in the sync manifest: %s"
                        % (ch.key, ", ".join(hits)))
    return os.path.join(rdir, hits[0]) if hits else None
