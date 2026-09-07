"""One Point Lesson parser over canonical raw text (harness.pdftext.opl_texts).

Closes CF-03 (all 56 dates parse once whitespace is collapsed), CF-V-02 (footer names split across lines), HN-08/CF-12
(cross-reference lines: every mention is captured, not the first match). Every field is a plain string or list; no model.
"""
import datetime
import re

from .pdftext import opl_texts

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
DATE = re.compile(r"(?:" + DAYS + r"),\s*(\d{1,2})\s+(" + MONTHS + r")\s+(20\d\d)")
HEADER = re.compile(
    r"OPL No:\s*(?P<opl_no>OPL-[A-Z]{2}-\d{4}[A-Z]?-\d{2}).*?OPL Title\s+(?P<title>.+?)\s+Discipline\s+(?P<discipline>.+?)\s+"
    r"Equipment\s+(?P<tag>[A-Z]{2}-\d{4}[A-Z]?)\s+-\s+(?P<equipment>.+?)\s+Area / Unit\s+(?P<area>.+?)\s+"
    r"Related Interlock\s+(?P<interlock>.+?)\s+(?:P&ID;?\s*Ref\s+|Ref\s+)?(?P<pid_ref>TJC-LLD-PID-\d{4})\s+Classification:",
    re.DOTALL,
)  # raw extraction sometimes drops the "P&ID Ref" label (Sets 5, 6): the label is optional
CLASSES = (("Basic Knowledge", "Basic Knowledge"), ("Improvement", "Improvement"), ("Trouble Case", "Trouble Case"))
PERSON = re.compile(r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)\s*\(EMP-(\d{4})\)")
XREF = re.compile(r"(?:Cross-ref|DUMMY)\s*(?:tag\s*)?([A-Z]{2}-\d{4}[A-Z]?)|([A-Z]{2}-\d{4}[A-Z]?)\s*across")
HAZARD = re.compile(r"Hazard note: this equipment is (.+?)\. Observe")
SEQ = re.compile(r"SEQ-\d{4}")


PAGE_FOOTER = "This is sample data provided for CALIBER purposes only"


def _between(text, start, end):
    """Section body between two headings, cut at the page-bottom watermark.

    Every one of the 56 lessons carries PAGE_FOOTER exactly once, and `pdftotext -raw` emits out-of-flow table cells
    immediately after it (OPL-DC-3401A-01/-04 emit a truncated copy of WO-240056's Corrective_Action there, the same
    string CD-12 reports). Nothing after the watermark is section prose, so the cut is applied here, in the one function
    all six sections route through, rather than in the one section where the leak happened to land (P10b).
    """
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    seg = text[i + len(start): j if j >= 0 else len(text)]
    k = seg.find(PAGE_FOOTER)
    return (seg[:k] if k >= 0 else seg).strip()


def parse(oid, text):
    """Parse one lesson. `text` is the canonical (whitespace-collapsed) raw text."""
    m = HEADER.search(text)
    if not m:
        raise ValueError(f"header not parsed: {oid}")
    h = m.groupdict()
    cls = [name for name, label in CLASSES if re.search(r"\[X\]\s*" + re.escape(label), text)]
    dm = DATE.search(text, text.find("Date of Sharing") if "Date of Sharing" in text else 0)
    # DTZ007: "Date of Sharing" is a plain calendar date on the lesson; the corpus states no time and no zone.
    date = datetime.datetime.strptime(" ".join(dm.groups()), "%d %B %Y").date().isoformat() if dm else None  # noqa: DTZ007
    tail = text[text.rfind("Prepared by"):] if "Prepared by" in text else text[-600:]
    people = PERSON.findall(tail)
    reviewed = [(n, e) for n, e in people if e.startswith("11")]
    approved = [(n, e) for n, e in people if e.startswith("09")]
    refs = sorted({a or b for a, b in XREF.findall(text)})
    subject = h["tag"]
    seqm = SEQ.search(h["interlock"])
    hz = HAZARD.search(text)
    return {
        "opl_id": oid,
        "opl_no": h["opl_no"],
        "tag": subject,
        "equipment": h["equipment"].strip(),
        "title": h["title"].strip(),
        "discipline": h["discipline"].strip(),
        "area_unit": h["area"].strip(),
        "related_interlock": h["interlock"].strip(),
        "seq": seqm.group(0) if seqm else None,
        "pid_ref": h["pid_ref"].strip(),
        "classification": cls[0] if len(cls) == 1 else (cls or None),
        "date_of_sharing": date,
        "prepared_by_role": "Panel Operator / Technician" if "Panel Operator / Technician" in tail else None,
        "reviewed_by": reviewed[0][0] if reviewed else None,
        "reviewed_by_id": ("EMP-" + reviewed[0][1]) if reviewed else None,
        "approved_by": approved[0][0] if approved else None,
        "approved_by_id": ("EMP-" + approved[0][1]) if approved else None,
        "has_crossref_line": "Cross-ref" in text,
        "crossref_tags": refs,
        "foreign_crossref_tags": [t for t in refs if t != subject],
        "hazard_note": hz.group(1) if hz else None,
        "purpose": _between(text, "1. PURPOSE / OBJECTIVE", "2. SAFETY PRECAUTIONS"),
        "safety_text": _between(text, "2. SAFETY PRECAUTIONS", "3. TOOLS & MATERIALS REQUIRED"),
        "tools_text": _between(text, "3. TOOLS & MATERIALS REQUIRED", "4. DETAILED PROCEDURE / STEPS"),
        "steps_text": _between(text, "4. DETAILED PROCEDURE / STEPS", "5. COMMON PROBLEMS"),
        "troubleshooting_text": _between(text, "5. COMMON PROBLEMS & TROUBLESHOOTING", "6. KEY LEARNING"),
        "key_learning": _between(text, "6. KEY LEARNING POINTS", "Prepared by"),
    }


def parse_all(texts=None):
    """{opl_id: parsed} for all 56 lessons, sorted by id."""
    texts = texts if texts is not None else opl_texts()
    return {k: parse(k, texts[k]) for k in sorted(texts)}


# The first element is not a slice of the text: it is the seven parsed header fields, rebuilt in this order by strict_text.
# Naming it "identity header" made the published method irreproducible (V-02): a reader who slices everything before
# "1. PURPOSE / OBJECTIVE" gets 186 uncovered of 211, not the figure the harness prints.
STRICT_HEAD_FIELDS = ("opl_id", "title", "equipment", "area_unit", "related_interlock", "pid_ref", "classification")
STRICT_SECTIONS = (("rebuilt header fields: lesson id, title, equipment name, area / unit, related interlock, "
                   "P&ID reference, classification"), "1. PURPOSE / OBJECTIVE", "2. SAFETY PRECAUTIONS",
                   "3. TOOLS & MATERIALS REQUIRED", "4. DETAILED PROCEDURE / STEPS", "6. KEY LEARNING POINTS")


def strict_text(parsed):
    """Strict-layer text of one parsed lesson: the identity header plus sections 1, 2, 3, 4 and 6, composed in that order.

    Composed, not stripped, because stripping the span between the two section headings only removes the copied work-order
    rows the extractor happens to place inside it: OPL-DC-3401A-07's raw text emits two troubleshooting cells AFTER the
    'Prepared by' footer, so `strip_troubleshooting` left them and WO-240062 scored 1.0 in the strict layer through a copied
    row. The strict layer measures what a lesson TEACHES, so nothing outside the taught sections may reach it, wherever the
    extractor puts it.
    """
    head = [" ".join(v) if isinstance(v, list) else v for v in (parsed[f] for f in STRICT_HEAD_FIELDS)]
    body = [parsed["purpose"], parsed["safety_text"], parsed["tools_text"], parsed["steps_text"], parsed["key_learning"]]
    return " ".join(p for p in head + body if p)


def strict_texts(parsed_all):
    """{opl_id: strict_text} for a parse_all() mapping, in sorted opl_id order."""
    return {k: strict_text(parsed_all[k]) for k in sorted(parsed_all)}


def strip_troubleshooting(text):
    """DEPRECATED (kept for backward compatibility only; not used by harness.coverage since the strict layer became composed).

    Removes the '5. COMMON PROBLEMS & TROUBLESHOOTING' section from a whole lesson text. It cannot define the strict layer:
    anything the extractor emits outside that span survives it (see `strict_text`). Use `strict_text(parsed)` instead.
    """
    return re.sub(r"5\.\s*COMMON PROBLEMS.*?6\.\s*KEY LEARNING", " 6. KEY LEARNING", text, flags=re.DOTALL | re.IGNORECASE)
