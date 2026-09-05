#!/usr/bin/env python3
"""Generators for <!-- computed:NAME --> blocks (see tools/assemble_html.py). Every count that would otherwise be typed lives here.

`golden_block()` is the one function here the harness also imports: it puts the same golden-set counts into packages/fixtures.json
under the key `golden`, so a chapter may print the size either from the file (a computed block) or from the fixture (an fx
directive) and the two can never disagree. `uv run python tools/computed.py` prints those counts in the category order of
blueprint 9.11 (read from contracts/golden_case.schema.json, never typed here).
"""

import glob
import html as H
import json
import os
import re
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(ROOT, "thehub", "chapters")
FIXTURES = os.path.join(ROOT, "packages", "fixtures.json")
GOLDEN = os.path.join(ROOT, "golden", "cases.yaml")
GOLDEN_CONTRACT = os.path.join(ROOT, "contracts", "golden_case.schema.json")
_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def words(n):
    """Spell 0-99 in words. A requirement count never leaves that range, and a lookup table that silently falls
    back to the digits (v1.0 shipped "77 (77)") is exactly the drift this document's number rules exist to stop."""
    if not 0 <= n < 100:
        raise ValueError(f"words() covers 0-99, got {n}")
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


def _chapters_text():
    return "".join(
        open(p, encoding="utf-8").read()
        for p in sorted(glob.glob(os.path.join(CH, "*.html")))
    )


def _ids(prefix):
    return sorted(
        set(re.findall(r"<td>(" + prefix + r"-\d{2,3})</td>", _chapters_text()))
    )


def fr_count():
    n = len(_ids("FR"))
    return f"{words(n)} ({n})"


def nfr_count():
    n = len(_ids("NFR"))
    return f"{words(n)} ({n})"


def _golden():
    """golden/cases.yaml as a list of case mappings. Reads both shapes the file has had: the flat v1.1 list (one scalar per
    field, `question`, `hard_gate`, `origin` at the top level) and the nested shape of blueprint 9.11 (`input`, `expected`,
    `sources[]`, `checks[{type, args}]`); every count below reads only `category` and `hard_gate`, which sit at the top level
    in both."""
    with open(GOLDEN, encoding="utf-8") as f:
        cases = yaml.safe_load(f)
    if not isinstance(cases, list):
        raise TypeError("golden/cases.yaml must be a top-level list of cases")
    return cases


def category_order():
    """The eleven categories in the order blueprint 9.11 lists them, read from the contract's enum."""
    with open(GOLDEN_CONTRACT, encoding="utf-8") as f:
        return json.load(f)["$defs"]["GoldenCase"]["properties"]["category"]["enum"]


def golden_total():
    return str(len(_golden()))


def golden_block():
    """Fixture key `golden` (blueprint 10.5: size, by_category, hard_gate_count; `total` is the older spelling of size, kept):
    counts straight off golden/cases.yaml (harness/analyze_corpus.py imports this one function)."""
    cases = _golden()
    return {
        "total": len(cases),
        "size": len(cases),
        "by_category": dict(
            sorted(Counter(c.get("category", "?") for c in cases).items())
        ),
        "hard_gate_count": sum(1 for c in cases if c.get("hard_gate") is True),
    }


def golden_table():
    cases = _golden()
    cats = {}
    for c in cases:
        cats.setdefault(c.get("category", "?"), []).append(c)
    order = {cat: n for n, cat in enumerate(category_order())}
    rows = []
    for cat in sorted(
        cats, key=lambda k: (int(cats[k][0].get("category_order", order.get(k, 99))), k)
    ):
        proves = cats[cat][0].get("category_proves", "")
        rows.append(
            f"<tr><td>{H.escape(cat)}</td><td>{len(cats[cat])}</td><td>{H.escape(proves)}</td></tr>"
        )
    rows.append(
        f"<tr><td><strong>Total</strong></td><td><strong>{len(cases)}</strong></td><td>printed from golden/cases.yaml at build time</td></tr>"
    )
    return "\n".join(rows)


def _fx():
    return json.load(open(FIXTURES, encoding="utf-8"))


def integrity_total():
    return str(_fx()["integrity"]["total"])


def integrity_rules_table():
    fx = _fx()["integrity"]
    rows = []
    for rid in sorted(k for k in fx if re.match(r"CD-\d+$", k)):
        r = fx[rid]
        rows.append(
            f"<tr><td>{rid}</td><td>{H.escape(str(r.get('definition', '')))}</td><td>{H.escape(str(r.get('unit', '')))}</td><td>{r.get('count', '')}</td><td>{H.escape(str(r.get('basis', '')))}</td></tr>"
        )
    return "\n".join(rows)


def toc():
    """Table of contents regenerated from the <h1 id=...> headings of the chapter fragments (never drifts: EC-19 ToC check)."""
    items = []
    for path in sorted(glob.glob(os.path.join(CH, "*.html"))):
        with open(path, encoding="utf-8") as f:
            html = f.read()
        for m in re.finditer(r'<h1 id="(c\d+|ap[A-G])"[^>]*>(.*?)</h1>', html):
            items.append(f'<li><a href="#{m.group(1)}">{m.group(2)}</a></li>')
    return "\n".join(items)


def version():
    return (
        open(os.path.join(ROOT, "thehub", "VERSION"), encoding="utf-8").read().strip()
    )


def build_date():
    return (
        open(os.path.join(ROOT, "thehub", "BUILD_DATE"), encoding="utf-8")
        .read()
        .strip()
    )


GENERATORS = {
    "toc": toc,
    "version": version,
    "build_date": build_date,
    "fr_count": fr_count,
    "nfr_count": nfr_count,
    "golden_total": golden_total,
    "golden_table": golden_table,
    "integrity_total": integrity_total,
    "integrity_rules_table": integrity_rules_table,
}


if __name__ == "__main__":
    g = golden_block()
    counts = [g["by_category"].get(cat, 0) for cat in category_order()]
    print(
        f"golden: {g['size']} cases; by category (9.11 order): {', '.join(str(n) for n in counts)}; "
        f"hard gates: {g['hard_gate_count']}"
    )
