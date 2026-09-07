"""Integrity register: the rule table of Revision Plan WS1 Task 1.5 (CD-1..CD-18, CD-3 deleted by DP-06) with the
Addendum A corrections P1 (CD-13 unit-aware), P2 (CD-12 prefix cells), P8 (hand-verified notes) and A1 (CD-4 priority,
`cd4_emergency`).

Text comes only from harness.pdftext (`pdftotext -raw` + canonical form, D10). Facts that exist only inside the P&ID PNGs
(no text layer) are keyed by hand in packages/hand_verified.json (basis M); where the harness can read the sibling document
the rule is H+M. Everything returned is a pure function of the corpus: sorted keys, sorted items, no timestamps, no paths.

`-raw` extraction glues words inside drawing and plot-plan title blocks (WATERBOOT, DRYWEIGHTpast, AREA7800-COOLINGTOWERSYSTEM),
so CD-11, CD-16 and CD-18 compare with all whitespace removed (`_squash`).

Severity rubric (three levels): high = a reader who follows the document acts on a wrong fact (foreign asset named, wrong
citation, foreign tags, wrong drawing content, contradicting facts, hazard limit absent from the datasheet, unrecorded outcome
of an emergency job); medium = a record is incomplete or mis-classified (planned rows flagged breakdown, missing cross-ref line,
placeholder number, truncated cell, phantom trip boilerplate, criticality review); low = arithmetic, identifier and vocabulary
observations. Register total = sum of counts over the defect rules; CD-15 and CD-16 are observations (`observation_only`).
"""

import json
import os
import re
import statistics
from collections import defaultdict
from itertools import pairwise

from . import pdftext as P
from .config import PACKAGES
from .workbook import NARR, OUTCOME_FIELDS

HAND_VERIFIED = os.path.join(PACKAGES, "hand_verified.json")
AREA_ALIASES = os.path.join(PACKAGES, "area_aliases.json")
MIN_PREFIX = 15  # P2: a cell must repeat at least 15 characters of the field to count as its prefix
UNIT_VALUE = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*(barg|bar|kg/cm2g|degC)\b"
)
UNIT_CLASS = {
    "barg": "pressure",
    "bar": "pressure",
    "kg/cm2g": "pressure",
    "degC": "temperature",
}
DRUM_MARKERS = ("WATER BOOT", "MIST PAD", "HORIZONTAL DRUM")
TRIP_BOILERPLATE = ("On any trip", "Safety PLC", "latched")
VOTE = re.compile(r"\b[123]oo[123]\b")
ROW_KIND = re.compile(r"\b(control|alarm|mech)\b")
SEQ_NO = re.compile(r"SEQ-\d{4}")

# id -> (rule, definition, unit, basis, severity, observation_only)
RULES = {
    "CD-1": (
        "Foreign cross-reference",
        (
            "Lesson whose cross-reference line names another asset (every mention counted, "
            "whitespace-normalised; harness.opl foreign_crossref_tags)."
        ),
        "lesson",
        "H",
        "high",
        False,
    ),
    "CD-2": (
        "P&ID drawing number placeholder or absent",
        (
            "P&ID title-block drawing number is the XXXX placeholder or "
            "there is no title block / reference box."
        ),
        "sheet",
        "M",
        "medium",
        False,
    ),
    "CD-4": (
        "Incomplete closeout",
        (
            "Work order with Status Completed, the eleven outcome fields empty and the three "
            "narrative fields present; items carry Priority (A1)."
        ),
        "work order",
        "H",
        "high",
        False,
    ),
    "CD-5": (
        "No cross-reference line",
        "Lesson with no cross-reference line at all.",
        "lesson",
        "H",
        "medium",
        False,
    ),
    "CD-6": (
        "Planned work flagged breakdown",
        (
            "Planned work (Problem_Description starts Scheduled/Statutory/Turnaround/"
            "Grid inspection) flagged Breakdown = Yes (workbook breakdown_kind == planned_flagged)."
        ),
        "work order",
        "H",
        "medium",
        False,
    ),
    "CD-7": (
        "Wrong datasheet cited",
        "P&ID cites a datasheet number that is not the DOC NO of its asset's datasheet.",
        "sheet",
        "H+M",
        "high",
        False,
    ),
    "CD-8": (
        "Wrong interlock sequence cited",
        "P&ID cites a SEQ number that is not the LOGIC No of its asset's C&E sheet.",
        "sheet",
        "H+M",
        "high",
        False,
    ),
    "CD-9": (
        "Foreign tags on P&ID",
        (
            "P&ID carries instrument tags or equipment IDs of another asset. A foreign tag is "
            "an instrument tag or an equipment ID only: a line number or a free-text destination label carried over from "
            "another sheet is recorded in the set's notes and in the sidecar's foreign_tag defect, not counted here "
            "(Addendum P8; the same rule sets the `foreign` flag in packages/pid_sidecars)."
        ),
        "sheet",
        "M",
        "high",
        False,
    ),
    "CD-10": (
        "Criticality review candidate",
        (
            "Datasheet criticality NON/LOW CRITICAL with unplanned-breakdown downtime "
            "above the fleet median (8 assets; rows with breakdown_kind == unplanned)."
        ),
        "asset",
        "H",
        "medium",
        False,
    ),
    "CD-11": (
        "GA drawing content inconsistent with class",
        (
            "GA drawing carries drum vocabulary (WATER BOOT / MIST PAD / "
            "HORIZONTAL DRUM) absent from the asset's datasheet, or its DRY WEIGHT field carries no number."
        ),
        "drawing",
        "H",
        "high",
        False,
    ),
    "CD-12": (
        "Truncated troubleshooting cell",
        (
            "Troubleshooting-table cell whose text is a strict prefix (>= 15 characters) "
            "of a same-asset workbook narrative field that the lesson does not carry in full: the LONGEST such prefix at each "
            "occurrence, wherever in the line it starts, ending (after an optional full stop) at a line break or at the end of "
            "the text, and not itself a complete field of the same asset (P2). Counting every shorter line-aligned prefix as "
            "well returns 79 cells, not 38."
        ),
        "cell",
        "H",
        "medium",
        False,
    ),
    "CD-13": (
        "Hazard limit absent from datasheet",
        (
            "Hazard-note pressure (barg/bar/kg/cm2g) or temperature (degC) numeral "
            "with no equal typed value of the same unit class in the asset's datasheet (P1)."
        ),
        "lesson",
        "H",
        "high",
        False,
    ),
    "CD-14": (
        "Cost arithmetic",
        "Labor_Cost + Material_Cost != Total_Cost on complete rows.",
        "work order",
        "H",
        "low",
        False,
    ),
    "CD-15": (
        "Identifier chronology",
        (
            "Notification number year != Report_Date year; WO numbering not chronological "
            "(observation)."
        ),
        "work order",
        "H",
        "low",
        True,
    ),
    "CD-16": (
        "Area vocabulary",
        (
            "Area named differently across document classes (workbook, datasheet, plot-plan title block, "
            "OPL header); alias table in packages/area_aliases.json (observation)."
        ),
        "area",
        "H",
        "low",
        True,
    ),
    "CD-17": (
        "Trip boilerplate without trip rows",
        (
            "C&E sheet carrying the trip/latch boilerplate while its matrix has no "
            "voted trip row (rows typed control/alarm/mech)."
        ),
        "sheet",
        "H",
        "medium",
        False,
    ),
    "CD-18": (
        "P&ID contradicts sibling document",
        (
            "P&ID fact (footprint, revision, instrument identity) contradicts the plot "
            "plan, GA drawing or C&E sheet; the sibling value is confirmed in the harness text."
        ),
        "contradiction",
        "H+M",
        "high",
        False,
    ),
}


def _rule(rid, items, **extra):
    rule, definition, unit, basis, severity, obs = RULES[rid]
    out = {
        "rule": rule,
        "definition": definition,
        "unit": unit,
        "count": len(items),
        "items": items,
        "basis": basis,
        "severity": severity,
        "observation_only": obs,
    }
    out.update(extra)
    return out


def _squash(s):
    return re.sub(r"\s+", "", s or "")


def hand_verified(path=HAND_VERIFIED):
    """packages/hand_verified.json: the eight P&ID PNG readings (Task 1.5 JSON + P8 notes) with verifier metadata."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def datasheet_doc_no(text):
    m = re.search(r"DOC NO: (TJC-LLD-DS-[A-Z]{2}-\d{4}[A-Z]?)", text)
    return m.group(1) if m else None


def interlock_logic_no(text):
    m = re.search(r"LOGIC No: (.+?) DESCRIPTION:", text)
    return m.group(1).strip() if m else None


def criticality(text):
    m = re.search(r"CRITICALITY (HIGH CRITICAL|LOW CRITICAL|NON CRITICAL)", text)
    return m.group(1) if m else None


def typed_values(text):
    """{(value, unit_class)} for every numeral followed by barg/bar/kg/cm2g/degC; range endpoints both count (P1)."""
    out = set()
    for lo, hi, unit in UNIT_VALUE.findall(text):
        out.add((float(lo), UNIT_CLASS[unit]))
        if hi:
            out.add((float(hi), UNIT_CLASS[unit]))
    return out


def canonical_lines(raw):
    """canonical(raw) plus the set of positions whose single space came from a line break (used by CD-12)."""
    lines = [P.canonical(x) for x in raw.split("\n")]
    lines = [x for x in lines if x]
    breaks, pos = set(), 0
    for i, x in enumerate(lines):
        if i:
            breaks.add(pos)
            pos += 1
        pos += len(x)
    return " ".join(lines), breaks


# ---------------------------------------------------------------- lessons
def cd1(parsed):
    """CD-1 (HN-08, CF-12): lesson whose cross-reference line names another asset."""
    items = [
        {"opl_id": k, "tag": v["tag"], "foreign_tags": v["foreign_crossref_tags"]}
        for k, v in sorted(parsed.items())
        if v["foreign_crossref_tags"]
    ]
    by_tag: defaultdict[str, int] = defaultdict(int)
    for it in items:
        by_tag[it["tag"]] += 1
    return _rule("CD-1", items, by_tag=dict(sorted(by_tag.items())))


def cd5(parsed):
    """CD-5 (HN-08, CF-12): lesson with no cross-reference line."""
    return _rule(
        "CD-5",
        [
            {"opl_id": k, "tag": v["tag"]}
            for k, v in sorted(parsed.items())
            if not v["has_crossref_line"]
        ],
    )


def truncated_cells(fields, text, breaks):
    """CD-12 cell parser. `fields` = {canonical field text: (wo, field name)} of the asset's rows; `text`, `breaks` from
    canonical_lines(). A cell is truncated when the longest common prefix of a field and the lesson text is >= MIN_PREFIX
    characters, shorter than the field, is not itself a complete field, and ends (after an optional '.' or ' .') at a line
    break or at the end of the text; the full field must be absent from the lesson."""
    cells = []
    for f in sorted(fields):
        if len(f) <= MIN_PREFIX or f in text:
            continue
        head, start = f[:MIN_PREFIX], 0
        while True:
            i = text.find(head, start)
            if i < 0:
                break
            start = i + 1
            n = 0
            while i + n < len(text) and n < len(f) and text[i + n] == f[n]:
                n += 1
            while n and text[i + n - 1] == " ":
                n -= 1
            cell = text[i : i + n]
            if n < MIN_PREFIX or cell in fields:
                continue
            j = i + n
            if text.startswith(" .", j):
                j += 2
            elif text.startswith(".", j):
                j += 1
            if j == len(text) or (text[j] == " " and j in breaks):
                wo, name = fields[f]
                cells.append({"wo": wo, "field": name, "cell": cell, "field_text": f})
    return cells


def cd12(rows, raw_texts):
    """CD-12 (CF-11, Addendum P2): troubleshooting-table cells that are strict prefixes of a same-asset narrative field.
    The whole lesson is scanned because `-raw` emits some table cells after section 6 (OPL-DC-3401A-01..06)."""
    fields: defaultdict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for w in sorted(rows, key=lambda w: w["WO_Number"]):
        for c in NARR:
            t = P.canonical(str(w[c] or ""))
            if t:
                fields[w["Equipment_Tag"]].setdefault(t, (w["WO_Number"], c))
    items = []
    for oid in sorted(raw_texts):
        tag = P.tag_of_opl(oid)
        text, breaks = canonical_lines(raw_texts[oid])
        for cell in truncated_cells(fields[tag], text, breaks):
            items.append({"opl_id": oid, "tag": tag, **cell})
    items.sort(key=lambda x: (x["opl_id"], x["wo"], x["field"]))
    return _rule(
        "CD-12",
        items,
        lessons=len({x["opl_id"] for x in items}),
        by_lesson=dict(
            sorted(
                (k, sum(1 for x in items if x["opl_id"] == k))
                for k in {x["opl_id"] for x in items}
            )
        ),
    )


def cd13(parsed, datasheets):
    """CD-13 (CF-21, Addendum P1): hazard-note pressure/temperature numeral with no equal typed datasheet value."""
    typed = {t: typed_values(x) for t, x in datasheets.items()}
    items = []
    for oid, v in sorted(parsed.items()):
        note = v["hazard_note"] or ""
        missing = sorted(
            {
                (lo, unit)
                for lo, hi, unit in UNIT_VALUE.findall(note)
                if (float(lo), UNIT_CLASS[unit]) not in typed.get(v["tag"], set())
            }
        )
        if missing:
            items.append(
                {
                    "opl_id": oid,
                    "tag": v["tag"],
                    "missing": [[val, unit, UNIT_CLASS[unit]] for val, unit in missing],
                    "hazard_note": note,
                }
            )
    by_tag: defaultdict[str, int] = defaultdict(int)
    for it in items:
        by_tag[it["tag"]] += 1
    return _rule("CD-13", items, by_tag=dict(sorted(by_tag.items())))


# ---------------------------------------------------------------- workbook
def cd4(rows):
    """CD-4 (F3, Addendum A1): closed work order with all eleven outcome fields empty and the three narrative fields present."""
    items = [
        {
            "wo": w["WO_Number"],
            "tag": w["Equipment_Tag"],
            "work_type": w["Work_Type"],
            "priority": w["Priority"],
            "report_date": w["Report_Date"].date().isoformat(),
        }
        for w in sorted(rows, key=lambda w: w["WO_Number"])
        if all(w[c] in (None, "") for c in OUTCOME_FIELDS) and all(w[c] for c in NARR)
    ]
    by_type: defaultdict[str, int] = defaultdict(int)
    for it in items:
        by_type[it["work_type"]] += 1
    return _rule(
        "CD-4",
        items,
        by_work_type=dict(sorted(by_type.items())),
        emergency=sorted(it["wo"] for it in items if it["priority"] == "Emergency"),
    )


def cd6(pops):
    """CD-6 (DP-04, DP-V-01): planned work flagged Breakdown = Yes, with its downtime and cost."""
    items = [
        {
            "wo": w["WO_Number"],
            "tag": w["Equipment_Tag"],
            "work_type": w["Work_Type"],
            "description": w["Problem_Description"],
            "downtime_h": w["Downtime_Hours"],
            "cost_idr": w["Total_Cost_IDR"],
        }
        for w in sorted(pops["planned_flagged"], key=lambda w: w["WO_Number"])
    ]
    return _rule(
        "CD-6",
        items,
        downtime_h=sum(x["downtime_h"] or 0.0 for x in items),
        cost_idr=sum(x["cost_idr"] or 0 for x in items),
    )


def cd10(rows, datasheets):
    """CD-10 (DP-27, CF-05): NON/LOW CRITICAL asset with unplanned-breakdown downtime above the fleet median."""
    per = {
        t: {"criticality": criticality(x), "unplanned_h": 0.0, "events": 0}
        for t, x in datasheets.items()
    }
    for w in rows:
        if w["breakdown_kind"] == "unplanned" and w["Equipment_Tag"] in per:
            per[w["Equipment_Tag"]]["unplanned_h"] += w["Downtime_Hours"] or 0.0
            per[w["Equipment_Tag"]]["events"] += 1
    median = statistics.median(v["unplanned_h"] for v in per.values())
    items = [
        {"tag": t, **v}
        for t, v in sorted(per.items())
        if v["criticality"] in ("NON CRITICAL", "LOW CRITICAL")
        and v["unplanned_h"] > median
    ]
    return _rule(
        "CD-10", items, fleet_median_h=median, per_asset=dict(sorted(per.items()))
    )


def cd14(rows):
    """CD-14 (CF-15): Labor_Cost + Material_Cost != Total_Cost on complete rows."""
    items = [
        {
            "wo": w["WO_Number"],
            "labor_cost_idr": w["Labor_Cost_IDR"],
            "material_cost_idr": w["Material_Cost_IDR"],
            "total_cost_idr": w["Total_Cost_IDR"],
            "diff_idr": w["Labor_Cost_IDR"]
            + w["Material_Cost_IDR"]
            - w["Total_Cost_IDR"],
        }
        for w in sorted(rows, key=lambda w: w["WO_Number"])
        if w["closeout_complete"]
        and w["Labor_Cost_IDR"] + w["Material_Cost_IDR"] != w["Total_Cost_IDR"]
    ]
    return _rule(
        "CD-14",
        items,
        max_abs_diff_idr=max((abs(x["diff_idr"]) for x in items), default=0),
    )


def cd15(rows):
    """CD-15 (CF-15, observation): notification year != report year; non-chronological WO numbering."""
    items = []
    for w in sorted(rows, key=lambda w: w["WO_Number"]):
        m = re.match(r"NT-(\d{4})-", str(w["Notification_No"]))
        if m and int(m.group(1)) != w["Report_Date"].year:
            items.append(
                {
                    "wo": w["WO_Number"],
                    "notification_no": w["Notification_No"],
                    "report_year": w["Report_Date"].year,
                }
            )
    srt = sorted(rows, key=lambda w: w["WO_Number"])
    out_of_order = sum(
        1 for a, b in pairwise(srt) if b["Report_Date"] < a["Report_Date"]
    )
    return _rule("CD-15", items, non_chronological_pairs=out_of_order)


# ---------------------------------------------------------------- drawings, plot plans, C&E sheets
def cd11(drawings, datasheets):
    """CD-11 (CF-07): GA drawing content inconsistent with the equipment class (drum sketch on EA-5601; 'DRY WEIGHT past')."""
    items = []
    for tag in sorted(drawings):
        d, ds = _squash(drawings[tag]), _squash(datasheets.get(tag, ""))
        ev = []
        markers = [m for m in DRUM_MARKERS if _squash(m) in d]
        if markers and not any(_squash(m) in ds for m in DRUM_MARKERS):
            ev.append(
                "drum vocabulary " + " / ".join(markers) + " absent from the datasheet"
            )
        m = re.search(r"DRY\s?WEIGHT\s?([A-Za-z]+)", drawings[tag])
        if m:
            ev.append("DRY WEIGHT " + m.group(1))
        if ev:
            items.append({"tag": tag, "evidence": ev})
    return _rule("CD-11", items)


def area_vocab(s):
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"^\s*\d{4}\s*-\s*", "", s or "").upper())


def cd16(rows, parsed, datasheets, plot_plans):
    """CD-16 (CF-16, CF-V-03, observation): area named differently across document classes; alias table per asset."""
    wb = defaultdict(set)
    for w in rows:
        wb[w["Equipment_Tag"]].add((w["Area_Code"], w["Area_Name"]))
    opl = defaultdict(set)
    for v in parsed.values():
        opl[v["tag"]].add(v["area_unit"])
    items, aliases = [], {}
    for tag in sorted(datasheets):
        ds = re.search(r" AREA (\d{4} - .+?) FUNCTIONAL LOC\.", datasheets[tag])
        pp = re.search(
            r"TITLE: PLOT PLAN / EQUIPMENT LOCATION AREA(\S+)", plot_plans.get(tag, "")
        )
        names = {
            "workbook": " | ".join(sorted(n for _, n in wb[tag])),
            "datasheet": ds.group(1) if ds else "",
            "plot_plan_title": pp.group(1) if pp else "",
            "opl": " | ".join(sorted(opl[tag])),
        }
        aliases[tag] = names
        vocab = sorted({area_vocab(v) for v in names.values() if v})
        if len(vocab) > 1:
            items.append(
                {
                    "tag": tag,
                    "area_code": sorted(c for c, _ in wb[tag]),
                    **names,
                    "vocabularies": vocab,
                    "n_vocabularies": len(vocab),
                }
            )
    return _rule("CD-16", items, aliases=aliases)


def cd17(interlocks):
    """CD-17 (CF-20, DP-20): C&E sheet with trip/latch boilerplate but no voted trip row."""
    items = []
    for tag in sorted(interlocks):
        x = interlocks[tag]
        matrix = x[x.find("CAUSE & EFFECT MATRIX") : x.find("Legend:")]
        boiler = [b for b in TRIP_BOILERPLATE if b in x]
        if boiler and not VOTE.search(matrix):
            items.append(
                {
                    "tag": tag,
                    "logic_no": interlock_logic_no(x),
                    "trip_rows": 0,
                    "row_kinds": sorted(set(ROW_KIND.findall(matrix))),
                    "boilerplate": boiler,
                }
            )
    return _rule("CD-17", items)


def no_sif_fixture(interlocks, datasheets, tag="EA-5601"):
    """DP-06 (replaces the deleted CD-3): the documented control/alarm/relief protection of the asset that has no SIF,
    parsed from its C&E sheet; used by GS-04 and FR-504, never counted as a defect."""
    x = interlocks[tag]
    doc = re.search(r"DOC NO: (TJC-LLD-IL-\S+)", x)
    tic = re.search(r"\b(TIC-\d+) SP (\d+ degC) control\b", x)
    pdah = re.search(r"\b(PDAH-\d+) > ([\d.]+ bar) alarm\b", x)
    psv = re.search(r"\b(PSV-\d+) set (\d+ barg) mech\b", x)
    protection = []
    if tic:
        protection.append(f"{tic.group(1)} control")
    if pdah:
        protection.append(f"{pdah.group(1)} alarm > {pdah.group(2)}")
    if psv:
        protection.append(f"{psv.group(1)} relief {psv.group(2)}")
    source = f"{doc.group(1) if doc else '?'} LOGIC No: {interlock_logic_no(x)}"
    if "Interlock N/A (control loop only)" in datasheets.get(tag, ""):
        source += "; datasheet note 1"
    return {
        "tag": tag,
        "protection": protection,
        "source": source,
        "criticality": criticality(datasheets.get(tag, "")),
    }


# ---------------------------------------------------------------- hand-verified P&ID facts
def cd2(hv):
    """CD-2 (HN-09, CF-06): P&ID title-block drawing number placeholder (XXXX) or absent."""
    return _rule(
        "CD-2",
        [
            {
                "set": s["set"],
                "tag": s["tag"],
                "file": s["file"],
                "ref_dwg": s["ref_dwg"],
            }
            for s in hv["sets"]
            if not s["ref_dwg"] or "XXXX" in s["ref_dwg"]
        ],
    )


def cd7(hv, datasheets):
    """CD-7 (CF-06): P&ID cites a datasheet number that is not its asset's datasheet DOC NO."""
    items = []
    for s in hv["sets"]:
        exp = datasheet_doc_no(datasheets.get(s["tag"], ""))
        if s["datasheet_cited"] and s["datasheet_cited"] != exp:
            items.append(
                {
                    "set": s["set"],
                    "tag": s["tag"],
                    "cited": s["datasheet_cited"],
                    "expected": exp,
                }
            )
    return _rule("CD-7", items)


def cd8(hv, interlocks):
    """CD-8 (CF-06): P&ID cites a SEQ number that is not its asset's C&E LOGIC No."""
    items = []
    for s in hv["sets"]:
        exp = interlock_logic_no(interlocks.get(s["tag"], ""))
        if (
            s["seq_cited"]
            and SEQ_NO.fullmatch(s["seq_cited"])
            and s["seq_cited"] != exp
        ):
            items.append(
                {
                    "set": s["set"],
                    "tag": s["tag"],
                    "cited": s["seq_cited"],
                    "expected": exp,
                }
            )
    return _rule("CD-8", items)


def cd9(hv):
    """CD-9 (CF-06, CF-24): P&ID carries instrument tags or equipment IDs of another asset."""
    return _rule(
        "CD-9",
        [
            {"set": s["set"], "tag": s["tag"], "foreign_tags": s["foreign_tags"]}
            for s in hv["sets"]
            if s["foreign_tags"]
        ],
    )


def cd18(hv, texts):
    """CD-18 (CF-22, CF-24): P&ID fact contradicts a sibling document; the sibling values are confirmed in harness text."""
    items = []
    for s in hv["sets"]:
        for c in s.get("contradictions", []):
            sib = _squash(texts[c["sibling"]].get(s["tag"], ""))
            items.append(
                {
                    "set": s["set"],
                    "tag": s["tag"],
                    "kind": c["kind"],
                    "pid": c["pid"],
                    "sibling": c["sibling"],
                    "sibling_values": c["sibling_values"],
                    "sibling_confirmed": all(
                        _squash(v) in sib for v in c["sibling_values"]
                    ),
                }
            )
    return _rule("CD-18", items)


# ---------------------------------------------------------------- entry point
def compute(ctx, write_aliases=False):
    """Fixture `integrity`: {rule_id: {...}} for the 17 rules plus `total` (defect rules only), `cd4_emergency` (A1) and
    `no_sif_fixture` (DP-06). ctx keys: rows, pops, opl, parsed, files (opl_raw optional).

    `write_aliases=True` rewrites packages/area_aliases.json and is passed by `make fixtures` alone. It defaults to False so
    that importing the module, running the tests or printing the register never mutates a repository data file, and so that
    the test comparing the file with the computed aliases reads a file it did not itself write (CS-03).
    """
    rows, pops, parsed = ctx["rows"], ctx["pops"], ctx["parsed"]
    raw = ctx.get("opl_raw") or P.opl_texts(canon=False)
    texts = {
        c: P.class_texts(c)
        for c in ("datasheet", "ga_drawing", "interlock", "plot_plan")
    }
    hv = hand_verified()
    out = {
        "CD-1": cd1(parsed),
        "CD-2": cd2(hv),
        "CD-4": cd4(rows),
        "CD-5": cd5(parsed),
        "CD-6": cd6(pops),
        "CD-7": cd7(hv, texts["datasheet"]),
        "CD-8": cd8(hv, texts["interlock"]),
        "CD-9": cd9(hv),
        "CD-10": cd10(rows, texts["datasheet"]),
        "CD-11": cd11(texts["ga_drawing"], texts["datasheet"]),
        "CD-12": cd12(rows, raw),
        "CD-13": cd13(parsed, texts["datasheet"]),
        "CD-14": cd14(rows),
        "CD-15": cd15(rows),
        "CD-16": cd16(rows, parsed, texts["datasheet"], texts["plot_plan"]),
        "CD-17": cd17(texts["interlock"]),
        "CD-18": cd18(hv, texts),
    }
    out["total"] = sum(r["count"] for r in out.values() if not r["observation_only"])
    out["cd4_emergency"] = len(out["CD-4"]["emergency"])
    out["no_sif_fixture"] = no_sif_fixture(texts["interlock"], texts["datasheet"])
    if write_aliases:
        with open(AREA_ALIASES, "w", encoding="utf-8") as f:
            json.dump(
                out["CD-16"]["aliases"], f, indent=1, sort_keys=True, ensure_ascii=False
            )
            f.write("\n")
    return out


if __name__ == "__main__":
    from . import opl as O
    from . import workbook as W

    rows = W.load()
    res = compute(
        {
            "rows": rows,
            "pops": W.populations(rows),
            "opl": P.opl_texts(),
            "parsed": O.parse_all(),
            "files": P.corpus_files(),
        }
    )
    for k in sorted(
        res,
        key=lambda k: (
            not k.startswith("CD-"),
            int(k[3:]) if k.startswith("CD-") else 0,
        ),
    ):
        v = res[k]
        print(k, v["count"] if isinstance(v, dict) and "count" in v else v)
