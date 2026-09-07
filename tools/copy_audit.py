#!/usr/bin/env python3
"""Copy audit (plan Task 7.4): every unit-bearing number in thehub/prd.html must carry an fx directive and equal its value.

Unit-bearing = a number followed by: percent | % | h | hours | IDR-preceded | of 211/57/56/31/23 | days | d. Numbers inside
<code>, years 2024-2027, section/ID numbers, dates and `<span class="nonfx">` (a figure that is not harness output: an
acceptance target, a plan figure, a threshold constant, or an externally sourced company figure) are exempt. An fx comment
with no number after it is reported too, since neither the substituter nor part 1 would ever see it (CSK-08).
Two unit-less cases are checked as well: the frozen threshold written bare after "t = " (LD-07 re-labels every appearance
of it, and a bare 0.62 carries no unit for UNIT_AFTER to catch), and an unescaped "<" in text content, which any consumer
that tokenises tags naively swallows along with the rest of the sentence, deleting a comparator from a setpoint.
Exit 1 on any unmatched, mismatched or orphaned number.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx as FX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "thehub", "prd.html")
# Plan Task 7.4's definition: a computed figure is a number followed by percent, hours, days, "of <population>",
# or preceded by IDR. Physical corpus values (barg, degC, mm/s, kW, m3, rpm) are quoted evidence, not harness output,
# and are exempt: they are checked by the golden set and the datasheet spot fixture instead.
UNIT_AFTER = re.compile(r"(?<![\w.\-/])(\d[\d,]*(?:\.\d+)?)\s*(percent\b|%|hours?\b|h\b|of (?:211|57|56|31|23|8|98)\b|days?\b|d\b)")
UNIT_BEFORE = re.compile(r"IDR\s+(\d[\d,]*(?:\.\d+)?)\s*(M|million|billion)?")
# Style sheets, code spans, HTML comments, image/style attributes, figure filenames and explicitly marked
# not-harness-output figures are not prose the fixture governs.
EXEMPT_CONTEXT = re.compile(
    r'<style>.*?</style>'          # style sheets
    r'|<code>[^<]*</code>'         # code spans
    r'|<!--.*?-->'                 # comments (fx directives are matched separately)
    r'|style\s*=\s*"[^"]*"'       # inline style attributes
    r'|<img[^>]*>'                 # image tags
    r'|<span class="nonfx">[^<]*</span>',   # target / plan / external figure, marked at the point of use
    re.DOTALL,
)
ANY_FX = re.compile(r"<!--\s*fx:[^>]*-->")
# The frozen matching threshold is a fixture value (method.t). A bare "t = 0.62" carries no unit, so UNIT_AFTER
# cannot see it, yet it is exactly the label a threshold change has to re-write (LD-07). Only the frozen value is
# checked: the sensitivity ladder's other t labels are axis points, not the frozen threshold.


def audit(path=HTML):
    html = Path(path).read_text(encoding="utf-8")
    fx = FX.load()
    problems = []
    # 1. directive values must equal the formatted fixture value
    for m in FX.DIRECTIVE.finditer(html):
        spec, shown = m.group(1), m.group(2)
        key, _, f = spec.partition("|")
        try:
            want = FX.fmt(FX.resolve(fx, key), f or None)
        except Exception as e:  # noqa: BLE001
            problems.append(f"unresolvable directive {spec}: {e}")
            continue
        if want != shown:
            problems.append(f"directive {spec}: shown {shown} != fixture {want}")
    # 2. an fx comment the DIRECTIVE regex does not match has no number after it: it substitutes nothing and part 1
    #    never sees it, so the value it claims to track has quietly left the fixture's control (CSK-08).
    directive_spans = [(m.start(), m.end()) for m in FX.DIRECTIVE.finditer(html)]
    for m in ANY_FX.finditer(html):
        if not any(s0 <= m.start() < e0 for s0, e0 in directive_spans):
            problems.append(f"orphan fx directive (no number follows): {m.group(0)}")
    # EXEMPT_CONTEXT blanks each exempt run with an equal-length run of spaces, so offsets into scrub and into html
    # are the same and directive_spans still line up.
    scrub = EXEMPT_CONTEXT.sub(lambda m: " " * len(m.group(0)), html)

    def covered(pos):
        return any(s <= pos <= e for s, e in directive_spans)

    # 3. the frozen threshold, written bare after "t = ", must carry its directive like any other fixture value
    t_txt = FX.fmt(FX.resolve(fx, "method.t"), "d2")
    for m in re.finditer(r"t\s*=\s*(" + re.escape(t_txt) + r")(?![\d])", scrub):
        if not covered(m.start(1)):
            ctx = html[max(0, m.start() - 90): m.end() + 40].replace("\n", " ")
            problems.append(f"no fx directive on the frozen threshold 't = {t_txt}' at ...{ctx}...")
    # 4. a bare "<" in text content: HTML5 renders it, but any consumer that tokenises tags naively swallows from it to
    #    the next ">", which silently deletes a comparator and the rest of the sentence ("< 0.05 mm/100 mm").
    text = re.sub(r"<style>.*?</style>|<!--.*?-->", "", html, flags=re.DOTALL)
    for m in re.finditer(r"<(?![/!a-zA-Z])", text):
        problems.append(f"unescaped '<' in text (use &lt;): ...{text[max(0, m.start() - 70): m.start() + 40]}...")
    # 5. unit-bearing numbers without a directive in the preceding 160 characters

    for rx in (UNIT_AFTER, UNIT_BEFORE):
        for m in rx.finditer(scrub):
            num = m.group(1)
            pos = m.start(1)
            if covered(pos):
                continue
            if re.fullmatch(r"20(2[4-9]|30)", num):
                continue
            # Section, chapter, requirement and figure references ("Chapter 19", "Figure 2", "SIL 1", "1oo2")
            before = html[max(0, pos - 40): pos].lower()
            if re.search(r"(chapter|section|figure|table|appendix|sil|phase|slide|beat|tier|round|level|rev)\s*$", before):
                continue
            ctx = html[max(0, pos - 90): pos + 40].replace("\n", " ")
            problems.append(f"no fx directive: '{num} {m.group(2) or 'IDR'}' at ...{ctx}...")
    return problems


if __name__ == "__main__":
    probs = audit(sys.argv[1] if len(sys.argv) > 1 else HTML)
    for p in probs:
        print("COPY-AUDIT:", p)
    print(f"copy_audit: {len(probs)} problem(s)")
    sys.exit(1 if probs else 0)
