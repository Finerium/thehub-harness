#!/usr/bin/env python3
"""Fail if any banned string (tools/banned_strings.txt) appears in the given files.
Usage: python3 tools/banned_strings.py FILE... ; --deliverables also bans '[TBD]'.
The MOC rule: 'routed to MOC' is allowed only on a line that also says 'permanent' (one line, or this file fails itself).
The rename carve-out (plan section 0): CHANGELOG.md may carry one line introducing the retired product name as former,
identified by the words 'formerly called'; that one line is exempt, and the name fails anywhere else in the file."""
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "tools", "banned_strings.txt")


# The audit trail necessarily quotes the strings the PRD must not contain (the rename decision, the retired
# framings, the v1.0 package name), so docs/ is excluded unless --include-docs is passed. The gate covers what
# leaves the team: the PRD, the figures, the golden set, the rule pack, the README, the CHANGELOG, the deliverables.
EXCLUDED_PREFIXES = ("docs/", "legacy/")


def main(argv):
    deliverables = "--deliverables" in argv
    include_docs = "--include-docs" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not include_docs:
        skipped = [f for f in files if any(os.path.relpath(f, ROOT).startswith(x) for x in EXCLUDED_PREFIXES)]
        files = [f for f in files if f not in skipped]
        for f in skipped:
            print(f"banned_strings: skipping {f} (audit trail; use --include-docs to scan it)")
    banned = [l for l in Path(LIST).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if deliverables:
        banned.append("[TBD]")
    hits = 0
    for f in files:
        try:
            lines = Path(f).read_text(encoding="utf-8", errors="replace").split("\n")
        except IsADirectoryError:
            continue
        # Plan section 0 permits the retired product name in exactly one place that ships: the
        # single line of CHANGELOG.md that introduces it as former. That line is exempt once; a
        # second such line, or the name anywhere else in the file, still fails. No other file gets
        # the carve-out, and the archived v1.0 PDF is never edited and is never scanned. Keyed on
        # the line rather than on the string so this file does not itself spell the retired name.
        formerly_left = 1 if os.path.basename(f) == "CHANGELOG.md" else 0
        for i, line in enumerate(lines, 1):
            if formerly_left and "formerly called" in line:
                formerly_left -= 1
                continue
            for b in banned:
                if b in line:
                    print(f"BANNED {f}:{i}: '{b}'")
                    hits += 1
            if "routed to MOC" in line and "permanent" not in line:
                print(f"BANNED {f}:{i}: 'routed to MOC' outside the permanent-change sentence")
                hits += 1
    print(f"banned_strings: {hits} hit(s) in {len(files)} file(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
