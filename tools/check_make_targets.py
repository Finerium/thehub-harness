#!/usr/bin/env python3
"""AC-NFR-25 helper: the harness READMEs and the Makefile cannot drift apart.

Blueprint 11 asks for "the harness README with every make target". Three ways that stops being true, each of which
this script fails on:

1. a target is added to the Makefile and no README names it, so a reader never learns the command exists;
2. a target is renamed or deleted and a README still tells a reader to run it;
3. a target loses its own one-line `##` help text, so `make` itself stops describing it.

Both READMEs count: README.md is the reviewer's entry point and names the six commands a reader runs from a fresh
checkout, harness/README.md is the module page and carries the internal seed-time targets as well. A target named
in either one is documented.

Exit 0 and one summary line when they agree, exit 1 and one line per disagreement when they do not.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READMES = ("README.md", "harness/README.md")
PHONY = re.compile(r"^\.PHONY:(.*)$", re.MULTILINE)
HELP_LINE = re.compile(r"^([a-z][a-z0-9-]*):[^=\n]*?##", re.MULTILINE)
IN_README = re.compile(r"`?make ([a-z][a-z0-9-]*)")


def check() -> tuple[list[str], list[str]]:
    """(targets, problems): the Makefile's targets, and one string per disagreement with the two READMEs."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    phony = PHONY.search(makefile)
    if phony is None:
        return [], ["Makefile has no .PHONY line, so the target list cannot be read"]
    targets = phony.group(1).split()
    if not targets:
        return [], ["Makefile .PHONY line is empty"]
    documented = set(HELP_LINE.findall(makefile))

    problems = [
        f"target `{t}` has no `## ` help text in the Makefile"
        for t in targets
        if t not in documented
    ]
    for readme in READMES:
        text = (ROOT / readme).read_text(encoding="utf-8")
        for named in sorted(set(IN_README.findall(text))):
            if named not in targets:
                problems.append(
                    f"{readme} tells a reader to run `make {named}`, which the Makefile does not define"
                )
    prose = "\n".join((ROOT / r).read_text(encoding="utf-8") for r in READMES)
    named_anywhere = set(IN_README.findall(prose))
    problems += [
        f"target `{t}` is in the Makefile and in no README"
        for t in targets
        if t not in named_anywhere
    ]
    return targets, problems


def main() -> int:
    targets, problems = check()
    for p in problems:
        print(f"check_make_targets: {p}")
    if problems:
        print(
            f"check_make_targets: {len(problems)} disagreement(s) between the Makefile and {', '.join(READMES)}"
        )
        return 1
    print(
        f"check_make_targets: {len(targets)} make targets, each with its help text and named in a README"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
