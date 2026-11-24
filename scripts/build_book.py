#!/usr/bin/env python3
"""Build the whole book as one Markdown file: build/<output_name>.md.

Chapters come from bookconf (part folders, then files, "_" files skipped).
Usage: build_book.py [--root DIR] [--force] [--strict]
Exit codes: 0 ok, 1 no chapters, 2 build file was hand-edited (use --force) or the book
cannot be read (book.json is not valid JSON, a chapter is not UTF-8), 3 forbidden characters
found with --strict.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path):
    """A generated file (the build output), read as it is."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def find_forbidden(text, chars):
    """Yield (line number, char, snippet) for every forbidden character in `text`."""
    for no, line in enumerate(text.split("\n"), 1):
        line = line.rstrip("\r")
        for ch in chars:
            i = line.find(ch)
            while i != -1:
                lo, hi = max(0, i - 20), min(len(line), i + 21)
                yield no, ch, line[lo:hi].strip()
                i = line.find(ch, i + 1)


def header(conf):
    lines = ["# " + conf["title"]] if conf["title"] else []
    for key in ("subtitle", "author"):
        if conf.get(key):
            lines.append(conf[key])
    return "\n\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="book folder (default: nearest parent with book.json)")
    ap.add_argument("--force", action="store_true", help="overwrite a hand-edited build file")
    ap.add_argument("--strict", action="store_true", help="exit 3 when forbidden characters are found")
    args = ap.parse_args(argv)

    try:
        conf = bookconf.load(args.root)
        chapters = bookconf.chapters(conf)
    except bookconf.BookError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if not chapters:
        print("error: no chapters found in %s" % bookconf.path(conf, "manuscript_dir"), file=sys.stderr)
        return 1

    out = bookconf.build_output(conf, "md")
    hash_file = bookconf.path(conf, "build_dir", ".build-hash")
    if not args.force and os.path.exists(out) and os.path.exists(hash_file):
        with open(hash_file, encoding="utf-8") as f:
            stored = f.read().strip()
        if sha(read_text(out)) != stored:
            print("STOP: %s was edited by hand since the last build." % os.path.relpath(out, conf["_root"]),
                  file=sys.stderr)
            print("The build file is output only. Merge the changes back into the manuscript,",
                  file=sys.stderr)
            print("or run with --force to overwrite it on purpose.", file=sys.stderr)
            return 2

    chars = conf.get("forbidden_chars") or []
    pieces = [header(conf)] if header(conf) else []
    total_words = 0
    warnings = 0
    print("%-50s %7s" % ("chapter", "words"))
    print("-" * 58)
    for ch in chapters:
        try:
            raw = bookconf.read_text(ch.path)
        except bookconf.BookError as e:
            print("error: %s" % e, file=sys.stderr)
            return 2
        text = raw.strip()
        words = len(text.split())
        total_words += words
        print("%-50s %7s" % (ch.rel, format(words, ",")))
        # line numbers refer to the file as it is on disk (leading blank lines count)
        for no, c, snippet in find_forbidden(raw, chars):
            print("%s:%d: %s" % (ch.rel, no, snippet))
            warnings += 1
        pieces.append(text)

    output = "\n\n---\n\n".join(pieces) + "\n"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(output)
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(sha(output))

    print("-" * 58)
    print("total: %d chapters, %s words" % (len(chapters), format(total_words, ",")))
    print("file: %s" % os.path.relpath(out, conf["_root"]))
    if warnings:
        print("warning: %d forbidden character(s) found" % warnings)
        if args.strict:
            return 3
    elif chars:
        print("forbidden characters: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
