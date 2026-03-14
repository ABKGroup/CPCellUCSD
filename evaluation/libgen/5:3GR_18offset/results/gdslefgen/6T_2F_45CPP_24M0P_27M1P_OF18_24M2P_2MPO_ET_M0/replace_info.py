
# path: replace_info.py
# Python 3.5+ compatible (no __future__ imports, no typing)

import argparse
import re
from pathlib import Path

TOKEN_OLD = "_27M1P_OF0_"
TOKEN_NEW = "_27M1P_OF18_"

def derive_new_cell(stem):
    new_stem = stem.replace(TOKEN_OLD, TOKEN_NEW)
    return new_stem, (new_stem != stem)

def replace_first_line_token(lines, old_cell, new_cell):
    """Replace cell name only on the first non-empty line. Avoids appending."""
    pattern = re.compile(r"^" + re.escape(old_cell) + r"(?=\s|$)")
    changed = False

    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        updated = pattern.sub(new_cell, line, count=1)
        if updated != line:
            lines[i] = updated + ("\n" if raw.endswith("\n") else "")
            changed = True
        # Only touch the first non-empty line
        break

    return lines, changed

def process_file(path, dry_run):
    old_cell = path.stem
    new_cell, will_change = derive_new_cell(old_cell)
    if not will_change:
        print("SKIP (no '{}'): {}".format(TOKEN_OLD, path.name))
        return

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    lines, content_changed = replace_first_line_token(lines, old_cell, new_cell)

    if not dry_run:
        # backup once
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(original, encoding="utf-8")
        if content_changed:
            path.write_text("".join(lines), encoding="utf-8")

    new_name = "{}{}".format(new_cell, path.suffix)
    new_path = path.with_name(new_name)

    if new_path.exists() and new_path.resolve() != path.resolve():
        raise OSError("Target exists: {}".format(new_name))

    if not dry_run:
        path.rename(new_path)

    print("{}RENAMED: {} -> {}; in-file cell {}"
          .format("DRY-RUN " if dry_run else "",
                  path.name, new_name,
                  "updated" if content_changed else "unchanged"))

def main():
    ap = argparse.ArgumentParser(
        description="Replace '{}' with '{}' in *.info filenames and in-file cell name."
        .format(TOKEN_OLD, TOKEN_NEW)
    )
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing.")
    ap.add_argument("--glob", default="*.info", help="Glob pattern (default: *.info)")
    args = ap.parse_args()

    files = sorted(Path(".").glob(args.glob))
    if not files:
        print("No files matched.")
        return

    for p in files:
        try:
            process_file(p, args.dry_run)
        except Exception as e:
            print("ERROR {}: {}".format(p.name, e))

if __name__ == "__main__":
    main()
