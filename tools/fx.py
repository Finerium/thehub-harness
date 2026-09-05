#!/usr/bin/env python3
"""fx directives: the only way a number enters the PRD prose.

Syntax in HTML:   <!-- fx:KEY -->NUMBER      or      <!-- fx:KEY|FMT -->NUMBER
KEY is a dotted path into packages/fixtures.json; list selectors: [3], [t=0.62], [tag=GA-1201A], [rule=CD-1].
FMT (optional): int | comma | d1 | d2 | M1 (divide by 1e6, 1 decimal) | k (divide by 1e3, 1 decimal) | pct1 | len | first | last |
share1 / share0 (a `share` fraction of the 10.5 registry rendered as a percentage, 1 or 0 decimals, half up).
The assembler REPLACES NUMBER with the formatted fixture value (so a stale number cannot survive a build); copy_audit.py then
checks that every unit-bearing number in the assembled HTML carries a directive and equals its formatted value.
"""

import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "packages", "fixtures.json")
DIRECTIVE = re.compile(
    r"<!--\s*fx:([A-Za-z0-9_.\[\]=\-|+/]+)\s*-->\s*(\d(?:[\d,]*\d)?(?:\.\d+)?)"
)  # no trailing comma
SEL = re.compile(r"\[([^\]]+)\]")


def load(path=FIXTURES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _select(node, sel):
    if sel.isdigit() or (sel.startswith("-") and sel[1:].isdigit()):
        return node[int(sel)]
    k, v = sel.split("=", 1)
    for item in node:
        if isinstance(item, dict) and k in item:
            iv = item[k]
            if str(iv) == v or (
                isinstance(iv, (int, float)) and abs(float(iv) - float(v)) < 1e-9
            ):
                return item
    raise KeyError(f"no element with {k}={v}")


SEG = re.compile(r"([^.\[\]]+)((?:\[[^\]]*\])*)")


def resolve(fx, key):
    """Walk a dotted path; dots inside [...] selectors (e.g. [t=0.62]) belong to the selector, not the path."""
    node = fx
    for m in SEG.finditer(key):
        name, sels = m.group(1), m.group(2)
        if isinstance(node, list) and name.isdigit():
            node = node[int(name)]
        else:
            node = node[name]
        for sel in SEL.findall(sels):
            node = _select(node, sel)
    return node


def fmt(value, f=None):
    if f == "len":
        return str(len(value))
    if f in ("first", "last"):
        value, f = (
            (value[0] if f == "first" else value[-1]),
            None,
        )  # then fall through to the auto branch
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(
        value, str
    ):  # an identifier key (demo.primary_wo, matched_lesson); never a number, passed through
        return value
    if f in (None, "", "auto"):
        if isinstance(value, float) and not float(value).is_integer():
            return f"{value:.1f}"
        v = round(float(value))
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    if f == "int":
        return str(round(float(value)))
    if f == "comma":
        return f"{round(float(value)):,}"
    if f == "d1":
        return f"{float(value):.1f}"
    if f == "d2":
        return f"{float(value):.2f}"
    if f == "pct1":
        return f"{float(value):.1f}"
    if f == "M1":
        return f"{float(value) / 1e6:.1f}"
    if f == "M0":
        return f"{float(value) / 1e6:.0f}"
    if f == "k":
        return f"{float(value) / 1e3:.1f}"
    if f in ("share1", "share0"):
        # a share is stored as the 1-decimal percentage divided by 100 (harness/analyze_corpus.py `share`), so decimal
        # arithmetic returns exactly that percentage; float multiplication could land a hair under the half point
        q = Decimal("0.1") if f == "share1" else Decimal(1)
        return str((Decimal(str(value)) * 100).quantize(q, rounding=ROUND_HALF_UP))
    raise ValueError(f"unknown fx format {f}")


def render(html, fx):
    """Replace every directive's number with the fixture value; returns (html, [(key, fmt, old, new)])."""
    changes = []

    def sub(m):
        spec, old = m.group(1), m.group(2)
        key, _, f = spec.partition("|")
        new = fmt(resolve(fx, key), f or None)
        if new != old:
            changes.append((key, f, old, new))
        return f"<!-- fx:{spec} -->{new}"

    return DIRECTIVE.sub(sub, html), changes


if __name__ == "__main__":
    import sys

    fx = load()
    for key in sys.argv[1:]:
        k, _, f = key.partition("|")
        print(key, "=", fmt(resolve(fx, k), f or None))
