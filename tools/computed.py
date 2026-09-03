"""Generators for <!-- computed:NAME --> blocks (see tools/assemble_html.py). Every count that would otherwise be typed lives here.

`golden_block()` is the one function here the harness also imports: it puts the same golden-set counts into packages/fixtures.json
under the key `golden`, so a chapter may print the size either from the file (a computed block) or from the fixture (an fx
directive) and the two can never disagree.
"""
import glob
import html as H
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(ROOT, "thehub", "chapters")
FIXTURES = os.path.join(ROOT, "packages", "fixtures.json")
GOLDEN = os.path.join(ROOT, "golden", "cases.yaml")
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words(n):
    """Spell 0-99 in words. A requirement count never leaves that range, and a lookup table that silently falls
    back to the digits (v1.0 shipped "77 (77)") is exactly the drift this document's number rules exist to stop."""
    if not 0 <= n < 100:
        raise ValueError(f"words() covers 0-99, got {n}")
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


def _chapters_text():
    return "".join(open(p, encoding="utf-8").read() for p in sorted(glob.glob(os.path.join(CH, "*.html"))))


def _ids(prefix):
    return sorted(set(re.findall(r"<td>(" + prefix + r"-\d{2,3})</td>", _chapters_text())))


def fr_count():
    n = len(_ids("FR"))
    return f"{words(n)} ({n})"


def nfr_count():
    n = len(_ids("NFR"))
    return f"{words(n)} ({n})"


def _golden():
    """Minimal YAML reader for golden/cases.yaml: a list of mappings with scalar values; no external dependency."""
    cases, cur = [], None
    for line in open(GOLDEN, encoding="utf-8"):
        if line.startswith("- "):
            cur = {}
            cases.append(cur)
            line = "  " + line[2:]
        if cur is None or not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"\s+([A-Za-z_]+):\s*(.*)$", line)
        if m:
            cur[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return cases


def golden_total():
    return str(len(_golden()))


def golden_block():
    """Fixture key `golden`: {total, by_category} straight off golden/cases.yaml, read by the same minimal reader the
    `golden_table` computed block uses (harness/analyze_corpus.py imports this one function)."""
    cases = _golden()
    return {"total": len(cases),
            "by_category": dict(sorted(Counter(c.get("category", "?") for c in cases).items()))}


def golden_table():
    cases = _golden()
    cats = {}
    for c in cases:
        cats.setdefault(c.get("category", "?"), []).append(c)
    rows = []
    for cat in sorted(cats, key=lambda k: (int(cats[k][0].get("category_order", 99)), k)):
        proves = cats[cat][0].get("category_proves", "")
        rows.append(f"<tr><td>{H.escape(cat)}</td><td>{len(cats[cat])}</td><td>{H.escape(proves)}</td></tr>")
    rows.append(f"<tr><td><strong>Total</strong></td><td><strong>{len(cases)}</strong></td><td>printed from golden/cases.yaml at build time</td></tr>")
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
        rows.append(f"<tr><td>{rid}</td><td>{H.escape(str(r.get('definition', '')))}</td><td>{H.escape(str(r.get('unit', '')))}</td><td>{r.get('count', '')}</td><td>{H.escape(str(r.get('basis', '')))}</td></tr>")
    return "\n".join(rows)


def toc():
    """Table of contents regenerated from the <h1 id=...> headings of the chapter fragments (never drifts: EC-19 ToC check)."""
    items = []
    for path in sorted(glob.glob(os.path.join(CH, "*.html"))):
        for m in re.finditer(r'<h1 id="(c\d+|ap[A-G])"[^>]*>(.*?)</h1>', open(path, encoding="utf-8").read()):
            items.append(f'<li><a href="#{m.group(1)}">{m.group(2)}</a></li>')
    return "\n".join(items)


def version():
    return open(os.path.join(ROOT, "thehub", "VERSION"), encoding="utf-8").read().strip()


def build_date():
    return open(os.path.join(ROOT, "thehub", "BUILD_DATE"), encoding="utf-8").read().strip()


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
