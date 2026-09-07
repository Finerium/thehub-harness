"""Structural chunking of the corpus PDFs into bundle/chunks.jsonl (blueprint 9.2 Chunk, AC-ING-13).

    uv run python -m harness.chunks --out bundle/chunks.jsonl        (CASE1_CORPUS names the corpus)

One chunk per structural unit, page-anchored, text in the canonical form of harness.pdftext.canonical (9.2), and always
a contiguous run of the canonical page text, so G1 can recompute quote_hash = sha256(text) from the extracted page.
Units never overlap and never cross a lesson step or a cause-and-effect row; each one is a unit of the document:

    opl          the title block (note), sections 1, 2, 3, 5 and 6 (opl_section), one chunk per step row of section 4
                 (opl_step); the footer and the cross-reference lines are typed fields (9.5 Opl), never chunks
    interlock    title block, effect columns, one chunk per matrix row (ce_row), legend, effect list, the start
                 permissive block and the notes (note)
    datasheet    the identity block and each parameter group (datasheet_group)
    ga_drawing   nozzle schedule, bill of material, notes, revision history, title block (note)
    plot_plan    site labels, subject equipment, area legend, notes, revision history, title block (note)

Only PDFs are chunked: the workbook is typed rows (9.4), the P&IDs are sidecars (9.3) and the organiser deck carries no
chunk (AC-ING-01). The page-bottom watermark is a unit boundary, never chunk text: a unit it splits keeps the part before
it (the part after the watermark is out-of-flow table text, the same rule as harness.opl), or the part after when nothing
precedes it (Sets 7 and 8 print the watermark first). Marker-derived fragments under MIN_CHARS (a stray project name) are
dropped and counted; a step or a row is never dropped.

Identifiers are the ones harness.documents gives the same file, so chunks.jsonl joins revisions.json under G1: a
document is "doc-" + sha256[:12] of the file and its one current revision "rev-" + sha256[:12]; document_revision_id
is that revision id and a chunk id is the revision id + "/c" + a three-digit ordinal, the 0-based position of the
chunk in its document. The "embedding" field of 9.2 is added by harness.embed --chunks; this module
writes the seven other fields.
"""

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from itertools import pairwise
from typing import Any

from .config import CORPUS
from .documents import document_id, revision_id
from .master import IL_ROW
from .opl import PAGE_FOOTER
from .pdftext import canonical, corpus_files, doc_class, file_sha256, pdf_text

MIN_CHARS = 40
OPL_HEADINGS = (
    "1. PURPOSE / OBJECTIVE",
    "2. SAFETY PRECAUTIONS",
    "3. TOOLS & MATERIALS REQUIRED",
    "4. DETAILED PROCEDURE / STEPS",
    "5. COMMON PROBLEMS & TROUBLESHOOTING",
    "6. KEY LEARNING POINTS",
    "Prepared by",
)
STEP_HEADER = "Step Action Check / Acceptance"
BOM_START = re.compile(
    r" 1 (?=[A-Z])"
)  # the first bill-of-material row after the nozzle schedule of a GA drawing
MARKERS = {
    "datasheet": (
        "datasheet_group",
        [
            "DESIGN & MECHANICAL DATA",
            "PERFORMANCE / NOZZLE DATA",
            "DRIVER / MOTOR / HEATER DATA",
            "VENDOR / MANUFACTURER",
            "NOTES:",
        ],
    ),
    "ga_drawing": ("note", [BOM_START, "NOTES:", "REVISION HISTORY", "TITLE:"]),
    "plot_plan": (
        "note",
        ["SUBJECT EQUIPMENT", "AREA LEGEND", "NOTES:", "REVISION HISTORY", "TITLE:"],
    ),
}
# The permissive block ends at "ENABLED RUN"; Set 2 prints a partial copy of its notes right after it and labels the
# notes "Notes:", so the block is closed by the end marker and the notes marker is case-insensitive on this class.
INTERLOCK_TAIL = [
    "Legend:",
    "EFFECT ID FINAL ELEMENT / ACTION",
    "# START PERMISSIVE",
    re.compile(r"(?<=ENABLED RUN) "),
    re.compile(r"NOTES:", re.IGNORECASE),
]


def identity(path, text=None):
    """(document id, current revision id) of one PDF, as harness.documents names every file: "doc-" and "rev-" +
    sha256[:12] (the scheme the application's seed uses); `text` is accepted for the callers that already hold it."""
    digest = file_sha256(path)
    return document_id(digest), revision_id(digest)


def _segments(text, markers, base=0):
    """(start, end) of the pieces of text cut at the first occurrence of each marker (a string or a compiled pattern)."""
    cuts = {0}
    for m in markers:
        hit = (m if hasattr(m, "search") else re.compile(re.escape(m))).search(text)
        if hit:
            cuts.add(hit.start())
    return [
        (base + a, base + b) for a, b in pairwise([*sorted(cuts), len(text)]) if b > a
    ]


def _steps(text, a, b):
    """(start, end) of each numbered step row of text[a:b]: ' k ' followed by a capital letter, k sequential from 1."""
    body = text[a:b]
    h = body.find(STEP_HEADER)
    if h < 0:
        raise ValueError("step table header not found")
    starts, k, i = [], 1, h + len(STEP_HEADER)
    while m := re.compile(rf" {k} (?=[A-Z])").search(body, i):
        starts.append(m.start())
        i, k = m.end(), k + 1
    if len(starts) < 2:
        raise ValueError("fewer than two step rows found")
    return [
        (a + s, a + e) for s, e in zip(starts, [*starts[1:], len(body)], strict=True)
    ]


def _opl_units(text):
    pos = [text.find(h) for h in OPL_HEADINGS]
    if min(pos) < 0 or pos != sorted(pos):
        raise ValueError("lesson headings missing or out of order")
    out = [(0, pos[0], "note")]
    for i in range(6):
        if i == 3:
            out += [
                (s, e, "opl_step")
                for s, e in _steps(text, pos[i] + len(OPL_HEADINGS[i]), pos[i + 1])
            ]
        else:
            out.append((pos[i], pos[i + 1], "opl_section"))
    return out


def _interlock_units(text):
    rows = list(IL_ROW.finditer(text))
    if not rows:
        raise ValueError("no cause-and-effect row found")
    out = [
        (a, b, "note")
        for a, b in _segments(text[: rows[0].start()], ["CAUSE & EFFECT MATRIX"])
    ]
    out += [(m.start(), m.end(), "ce_row") for m in rows]
    tail = rows[-1].end()
    out += [(a, b, "note") for a, b in _segments(text[tail:], INTERLOCK_TAIL, tail)]
    return out


def units(cls, text):
    """[(start, end, unit_kind)] of one document's canonical text, in text order; None for a class without chunks."""
    if cls == "opl":
        return _opl_units(text)
    if cls == "interlock":
        return _interlock_units(text)
    if cls in MARKERS:
        kind, markers = MARKERS[cls]
        return [(a, b, kind) for a, b in _segments(text, markers)]
    return None


def _cut_watermark(text, a, b):
    w = text.find(PAGE_FOOTER, a, b)
    if w < 0:
        return a, b
    return (a, w) if text[a:w].strip() else (w + len(PAGE_FOOTER), b)


def chunk_document(path):
    """(document id, chunk rows without embeddings, count of dropped fragments) of one PDF; no rows for a class without chunks."""
    cls = doc_class(path)
    raw = pdf_text(path)
    pages = [(n, canonical(p)) for n, p in enumerate(raw.split("\f"), 1)]
    pages = [(n, t) for n, t in pages if t]
    text = " ".join(t for _, t in pages)
    if text != canonical(raw):
        raise ValueError(f"page join differs from the canonical whole: {path}")
    did, rev = identity(path, text)
    found = units(cls, text)
    if found is None:
        return did, [], 0
    starts, off = [], 0
    for _, t in pages:
        starts.append(off)
        off += len(t) + 1
    out: list[dict[str, Any]] = []
    dropped = 0
    for a, b, kind in found:
        a, b = _cut_watermark(text, a, b)
        s = text[a:b]
        a += len(s) - len(s.lstrip())
        s = s.strip()
        if not s or (len(s) < MIN_CHARS and kind in ("note", "datasheet_group")):
            dropped += bool(s)
            continue
        i = max(k for k, st in enumerate(starts) if st <= a)
        page, page_text = pages[i]
        if s not in page_text:
            raise ValueError(f"chunk is not a run of its page text: {path} @ {a}")
        out.append(
            {
                "id": f"{rev}/c{len(out):03d}",
                "document_revision_id": rev,
                "page": page,
                "ordinal": len(out),
                "unit_kind": kind,
                "text": s,
                "quote_hash": hashlib.sha256(s.encode("utf-8")).hexdigest(),
            }
        )
    return did, out, dropped


def build(base=CORPUS):
    """Every chunk of every PDF in corpus order, plus a summary; two files under one document id is an error."""
    rows: list[dict[str, Any]] = []
    by_class: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    dropped = 0
    seen: dict[str, str] = {}
    for p in corpus_files(base):
        if not p.lower().endswith(".pdf"):
            continue
        cls = doc_class(p)
        did, chunks, d = chunk_document(p)
        if did in seen:
            raise ValueError(f"document id {did} names two files: {seen[did]} and {p}")
        seen[did] = p
        rows += chunks
        dropped += d
        by_class[cls] += len(chunks)
        by_kind.update(c["unit_kind"] for c in chunks)
    return rows, {
        "documents": len(seen),
        "chunks": len(rows),
        "by_class": dict(sorted(by_class.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "dropped_fragments": dropped,
        "max_chars": max((len(c["text"]) for c in rows), default=0),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="structural chunking of the corpus PDFs (blueprint 9.2 Chunk)"
    )
    ap.add_argument("--out", default="bundle/chunks.jsonl")
    a = ap.parse_args(argv)
    rows, summary = build()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    os.replace(tmp, a.out)
    print(json.dumps({"out": a.out, **summary}))


if __name__ == "__main__":
    main()
