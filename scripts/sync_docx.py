#!/usr/bin/env python3
"""Regenerate the author's review DOCX for each chapter from its Markdown source.

    python3 sync_docx.py [--root DIR] [--only 3,4,3z] [--merged] [--force] [--size A4|A5]

For every chapter (or only the keys in --only) the DOCX in the review folder is rewritten.
Protection of the author's files, in order:
  * a DOCX that is open in a word processor is never overwritten (BLOCKED), unless its editor
    is listed in book.json "overwrite_open" or --force is given;
  * a DOCX that changed since the last sync (its hash differs from review/.sync-state.json) holds
    edits of the author's: HELD, not overwritten. Merge them into the Markdown first
    (docx_diff.py <key>), then run with --merged, which replaces the file but still skips it
    while it is open;
  * a DOCX that sync never wrote (no manifest entry) is copied to review/.backup/ first, and so is
    every changed file replaced with --merged or --force.
Each file is built under a temporary name and moved into place only when complete, so a failed
build leaves the old file untouched; one failed chapter does not stop the others.

Exit codes: 0 ok, 2 something was blocked, held or failed, the node binary is missing, two chapters
map to the same file name, or --only has an unknown key.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bookconf  # noqa: E402
import office  # noqa: E402

MD2DOCX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md2docx.js")


def write_docx(node, md, docx, conf_path, size):
    subprocess.run([node, MD2DOCX, md, docx, "--config", conf_path, "--size", size],
                   check=True, timeout=120, stdout=subprocess.DEVNULL)


def backup(target, rdir):
    """Copy `target` to review/.backup/<name>.<timestamp>.docx and return the new path."""
    bdir = os.path.join(rdir, ".backup")
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = os.path.basename(target)
    dest = os.path.join(bdir, "%s.%s.docx" % (name, stamp))
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(bdir, "%s.%s-%d.docx" % (name, stamp, n))
        n += 1
    shutil.copy2(target, dest)
    return dest


def _unlink(p):
    try:
        os.unlink(p)
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="book folder (default: search upwards from the current folder for book.json)")
    ap.add_argument("--only", help="comma-separated chapter keys, e.g. 3,4,3z")
    ap.add_argument("--merged", action="store_true",
                    help="the author's edits in these DOCX files are merged into the Markdown: replace "
                         "files changed since the last sync (backup first); open files are still skipped")
    ap.add_argument("--force", action="store_true",
                    help="overwrite DOCX files that look open or changed since the last sync (a backup is still made)")
    ap.add_argument("--size", default="A4", choices=["A4", "A5"], help="page size of the review DOCX (default A4)")
    args = ap.parse_args(argv)
    if args.merged and not args.only:
        print("ERROR: --merged needs --only with the chapters whose edits were merged", file=sys.stderr)
        return 2

    node = shutil.which("node")
    if not node:
        print("ERROR: node is not installed (needed to build DOCX files)", file=sys.stderr)
        return 2
    try:
        conf = bookconf.load(args.root)
        all_chs = bookconf.chapters(conf)
        chs = all_chs
        if args.only:
            keys = [k.strip() for k in args.only.split(",") if k.strip()]
            picked, unknown = [], []
            for k in keys:
                try:
                    ch = bookconf.resolve(conf, k)
                except bookconf.BookError:
                    unknown.append(k)
                    continue
                if ch not in picked:
                    picked.append(ch)
            if unknown:
                print("ERROR: unknown chapter key(s): %s" % ", ".join(unknown), file=sys.stderr)
                return 2
            chs = picked
        manifest = bookconf.load_manifest(conf)
        # every chapter's target file name, before anything is written
        targets = {}
        for ch in all_chs:
            found = bookconf.find_review_docx(conf, ch, manifest)
            targets[ch.key + "|" + ch.rel] = (ch, os.path.basename(found) if found
                                               else bookconf.review_name(conf, ch))
    except bookconf.BookError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    groups = {}
    for ch, name in targets.values():
        groups.setdefault(name.casefold(), []).append((ch, name))
    selected = {c.rel for c in chs}
    clash = [g for g in groups.values() if len(g) > 1 and any(c.rel in selected for c, _ in g)]
    if clash:
        for g in clash:
            print("ERROR: %d chapters map to the same file name %s: %s"
                  % (len(g), g[0][1], ", ".join(c.rel for c, _ in g)), file=sys.stderr)
        print("Nothing was written. Add {key} to review_name / review_name_unnumbered in book.json "
              "so every chapter gets its own file name.", file=sys.stderr)
        return 2

    conf_path = os.path.join(conf["_root"], bookconf.CONFIG_NAME)
    overwrite_open = set(conf.get("overwrite_open", []) or [])
    rdir = bookconf.path(conf, "review_dir")
    written = created = 0
    blocked, held, failed = [], [], []

    for ch in chs:
        wanted = bookconf.review_name(conf, ch)
        found = bookconf.find_review_docx(conf, ch, manifest)
        if found:
            target = found
            name = os.path.basename(found)
            reason = office.is_open(target)
            if reason and not args.force:
                if reason not in overwrite_open:
                    print("BLOCKED %s: open in %s – close it and run again" % (name, reason))
                    blocked.append(name)
                    continue
                print("WARNING %s was open in %s: close it without saving and reopen" % (name, reason))
            entry = manifest.get(name)
            try:
                current = bookconf.sha256_file(target)
            except OSError as e:
                print("ERROR %s: cannot read it: %s" % (name, e), file=sys.stderr)
                failed.append(name)
                continue
            changed = bool(entry) and entry["sha256"] != current
            if changed and not (args.force or args.merged):
                print("HELD %s: changed since the last sync – merge the author's edits first "
                      "(docx_diff.py %s), then run again with --merged" % (name, ch.key))
                held.append(name)
                continue
            if name != wanted:
                print("note: the title of chapter %s changed; %s keeps its old name (now %s)" % (ch.key, name, wanted))
            is_new = False
        else:
            os.makedirs(rdir, exist_ok=True)
            target = os.path.join(rdir, wanted)
            name = wanted
            is_new = True
            changed = False
        tmp =os.path.join(os.path.dirname(target), "." + name + ".tmp")
        try:
            write_docx(node, ch.path, tmp, conf_path, args.size)
            if not os.path.isfile(tmp) or not zipfile.is_zipfile(tmp):
                raise RuntimeError("the converter produced no valid DOCX")
            # the author may have opened the file while it was being built
            reason = office.is_open(target)
            if reason and not args.force and reason not in overwrite_open:
                print("BLOCKED %s: opened in %s while it was being built – close it and run again"
                      % (name, reason))
                blocked.append(name)
                _unlink(tmp)
                continue
            new_hash = bookconf.sha256_file(tmp)
            if not is_new and os.path.exists(target) and (not manifest.get(name) or args.force or changed):
                print("backup %s" % backup(target, rdir))
            os.replace(tmp, target)
            manifest[name] = {"key": ch.key, "sha256": new_hash}
            bookconf.save_manifest(conf, manifest)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, RuntimeError) as e:
            _unlink(tmp)
            print("ERROR %s: DOCX build failed: %s" % (name, e), file=sys.stderr)
            failed.append(name)
            continue
        if is_new:
            created += 1
            print("created %s" % name)
        else:
            written += 1
            print("written %s" % name)

    print("Done: %d written, %d created, %d blocked, %d held, %d failed"
          % (written, created, len(blocked), len(held), len(failed)))
    return 2 if (blocked or held or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
