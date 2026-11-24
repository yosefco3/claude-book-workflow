#!/usr/bin/env python3
"""Scaffold a new book folder.

Usage: init_book.py <dir> --title T [--author A] [--lang he|en]
Exit 2 if <dir>/book.json already exists.
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EN = {
    "lang": "en",
    "dir": "ltr",
    "labels": {"chapter": "Chapter", "contents": "Contents", "draft": "Draft - not for distribution"},
    "special_headings": {"deep": "Going deeper", "sources": "Sources for this chapter"},
    "review_name": "Chapter {n} - {title}.docx",
    "fonts": {"body": "Noto Serif", "heading": "Noto Sans"},
    "forbidden_chars": [],
}


def slug(title):
    s = "".join(c.lower() if c.isascii() and c.isalnum() else "-" for c in title)
    s = "-".join(p for p in s.split("-") if p)
    return s or "book"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--lang", choices=["he", "en"], default="he")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.dir)
    cfg_path = os.path.join(root, bookconf.CONFIG_NAME)
    if os.path.exists(cfg_path):
        print("error: %s already exists" % cfg_path, file=sys.stderr)
        return 2

    conf = {k: v for k, v in bookconf.DEFAULTS.items()}
    conf.update(title=args.title, author=args.author, output_name=slug(args.title))
    if args.lang == "en":
        conf.update(EN)
    # language_fixes stays out of a new book.json: the skill asks the author and records it
    conf.pop("language_fixes", None)
    created, kept = [], []

    def make(path, text=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if text is not None and os.path.exists(path):
            kept.append(os.path.relpath(path, root))  # never overwrite the author's files
            return
        if text is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        created.append(os.path.relpath(path, root))

    make(cfg_path, json.dumps(conf, ensure_ascii=False, indent=2) + "\n")
    make(os.path.join(root, conf["manuscript_dir"], "00-front", "01-intro.md"), "# %s\n\n" % (
        "Introduction" if args.lang == "en" else "הקדמה"))
    os.makedirs(os.path.join(root, conf["manuscript_dir"], "assets"), exist_ok=True)
    created.append(os.path.join(conf["manuscript_dir"], "assets") + "/")
    make(os.path.join(root, ".gitignore"), "build/*.pdf\nreview/\nnode_modules/\nsources/\n.work/\n")

    tpl = os.path.join(SKILL_ROOT, "templates", "CLAUDE.md")
    if os.path.isfile(tpl):
        with open(tpl, encoding="utf-8") as f:
            make(os.path.join(root, "CLAUDE.md"), f.read().replace("{title}", args.title).replace("{skill}", SKILL_ROOT))
    style = os.path.join(SKILL_ROOT, "templates", "STYLE-%s.md" % args.lang)
    if os.path.isfile(style):
        dest = os.path.join(root, "docs", "STYLE.md")
        if os.path.exists(dest):
            kept.append(os.path.relpath(dest, root))
        else:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(style, dest)
            created.append(os.path.relpath(dest, root))

    print("created book in %s:" % root)
    for c in created:
        print("  " + c)
    for k in kept:
        print("  kept existing " + k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
