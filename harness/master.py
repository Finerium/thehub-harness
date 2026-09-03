"""Equipment master, C&E sheet rows, proof tests, personnel, failure families, causal chains and spot fixtures.

Closes plan Task 1.7 (equipment master), FR-104 typed rows with `row_kind` (CF-20, DP-20), FR-116 counts (Addendum P3),
CF-18 (personnel role coding), CR-20 (family membership, Appendix C.4), CR-12 (PRD 19.4 causal links made reproducible),
CR-07 (FR-105 spot fixtures) and Addendum A4 (real revision and issue status).

Text comes only from harness.pdftext (D10: `pdftotext -raw`, canonical form). One thing the raw text cannot carry is the
COLUMN of each X in a cause-and-effect matrix (only the X count survives), so every row takes its column identity from
packages/interlock_effects.json, typed by hand off the rendered sheets (basis "H+M"). The harness re-derives every text
field of that file from the raw text and raises on any disagreement, so the hand file can only add the column mapping and
the effect final-element labels, never overwrite what the document says.
"""
import datetime
import json
import os
import re
import sys
from collections import Counter

from .config import PACKAGES
from .pdftext import class_texts

INSTR = r"[A-Z]{1,4}-\d{4,5}"

# ---------------------------------------------------------------- C&E sheets (FR-104)
IL_HDR = re.compile(
    r"DOC NO: (?P<doc_no>TJC-LLD-IL-\S+) WORK NO: (?P<work_no>\S+) REV: (?P<rev>\d+) LOGIC No: (?P<logic_no>.+?) "
    r"DESCRIPTION: (?P<description>.+?) SIL: (?P<sil>.+?) TAG: (?P<tag>\S+) FLOC: (?P<floc>\S+)"
)
IL_ROW = re.compile(
    r"(?:^| )(?P<id>[TCAR]\d) (?P<initiator>.+?) (?P<tag>" + INSTR + r") (?P<setpoint>.+?) "
    r"(?P<vote>1oo1|1oo2|2oo3|control|alarm|mech)(?P<xs>(?: X)*)"
)
IL_EFF = re.compile(r"(EFF-\d+) (.+?)(?= EFF-\d+ |$)")
IL_GATE = re.compile(r"=> ALL permissives (?P<state>TRUE) \((?P<gate>AND)\) => START (?P<tag>\S+) (?P<result>ENABLED RUN)")
IL_PERM = re.compile(
    r"(?:^| )(?P<n>\d) (?P<condition>.+?) (?P<signal>" + INSTR + r"|DCS reset|FSL upstream|LG gearbox|lockout|DVC6200)(?= \d |$)"
)
SETPOINT = re.compile(r"(?P<cmp>[<>])?\s*(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%][A-Za-z0-9/%]*)?")
ROW_KIND = {"T": "trip", "C": "control", "A": "alarm", "R": "mech"}


def hand_effects():
    """packages/interlock_effects.json keyed by LOGIC No (SEQ-nnnn, or the tag for EA-5601's control-loop-only sheet)."""
    with open(os.path.join(PACKAGES, "interlock_effects.json"), encoding="utf-8") as f:
        return json.load(f)


def _agree(what, got, want):
    """The hand file may only carry what the raw text also says; anything else is a typing error, not a fact."""
    if got != want:
        raise ValueError(f"interlock_effects.json disagrees with the raw text at {what}: text {got!r}, file {want!r}")


def _setpoint(text):
    m = SETPOINT.search(text)
    if not m:
        return None, None
    return float(m.group("num")), m.group("unit")


def parse_interlock(tag, text, hand=None):
    """One C&E sheet (canonical raw text) -> header, effects, typed rows, start permissives + their AND gate (FR-104, CF-20, A4).

    Row kind comes from the row id letter (T trip, C control, A alarm, R mech) so EA-5601's C1/A1/R1 rows are typed, not
    lost. The X count comes from the text, the X column identity from the hand file keyed by LOGIC No; every text field
    of the hand row must equal the parsed one or this raises (effects_basis "H+M").
    """
    h = IL_HDR.search(text).groupdict()
    sil = None if h["sil"].startswith("N/A") else int(h["sil"].split()[1])
    header = {
        "doc_no": h["doc_no"], "work_no": h["work_no"], "rev": int(h["rev"]),
        "logic_no": None if h["logic_no"].startswith("N/A") else h["logic_no"], "logic_no_text": h["logic_no"],
        "description": h["description"], "sil": sil, "sil_text": h["sil"], "tag": h["tag"], "floc": h["floc"],
    }
    seq = header["logic_no"] or tag
    sheet = (hand if hand is not None else hand_effects())[seq]
    _agree(f"{seq} sil", header["sil"], sheet["sil"])
    for k in ("doc_no", "work_no", "rev", "description"):
        _agree(f"{seq} {k}", header[k], sheet[k])

    eff_seg = text[text.index("EFFECT ID FINAL ELEMENT / ACTION ") + len("EFFECT ID FINAL ELEMENT / ACTION "): text.index(" # START PERMISSIVE")]
    effects = [{"id": i, "action": a} for i, a in IL_EFF.findall(eff_seg)]
    _agree(f"{seq} effects", [(e["id"], e["action"]) for e in effects],
           [(e["id"], e["final_element"]) for e in sheet["effects"]])
    effects = [dict(e, final_element=f["final_element"]) for e, f in zip(effects, sheet["effects"])]

    matrix = text[text.index("SET POINT VOTE ") + len("SET POINT VOTE "): text.index(" Legend:")]
    n_cols = len(re.findall(r"EFF-\d+ ", matrix[: IL_ROW.search(matrix).start()]))
    _agree(f"{seq} n_effect_columns", n_cols, len(sheet["effects"]))
    parsed = list(IL_ROW.finditer(matrix))
    _agree(f"{seq} row ids", [m.group("id") for m in parsed], [r["id"] for r in sheet["rows"]])
    rows = []
    for m, hr in zip(parsed, sheet["rows"]):
        d = m.groupdict()
        n_x = d["xs"].count("X")
        val, unit = _setpoint(d["setpoint"])
        _agree(f"{seq} {d['id']}", (d["initiator"], d["tag"], d["setpoint"], val, unit, d["vote"]),
               (hr["initiator"], hr["tag"], hr["setpoint_text"], hr["setpoint_value"], hr["setpoint_unit"], hr["vote_cell_text"]))
        _agree(f"{seq} {d['id']} x_count", n_x, len(hr["effects"]))  # the X count is the text's own check on the hand columns
        rows.append({
            "id": d["id"], "row_kind": ROW_KIND[d["id"][0]], "initiator": d["initiator"], "tag": d["tag"],
            "setpoint_text": d["setpoint"], "setpoint_value": val, "setpoint_unit": unit,
            "comparator": hr["comparator"],
            # A relief device and a control loop have no voting architecture; the sheet's VOTE cell still says "mech" /
            # "control" / "alarm", so the cell text is published under its own name and `voting` is null (PS-15).
            "voting": d["vote"] if ROW_KIND[d["id"][0]] == "trip" else None, "vote_cell_text": d["vote"],
            "x_count": n_x, "effects": list(hr["effects"]), "effects_basis": "H+M",
        })
    perm_seg = text[text.index("# START PERMISSIVE (AND-gate) SIGNAL ") + len("# START PERMISSIVE (AND-gate) SIGNAL "): text.index(" => ALL permissives")]
    permissives = [{"n": int(p["n"]), "condition": p["condition"], "signal": p["signal"]} for p in IL_PERM.finditer(perm_seg)]
    _agree(f"{seq} permissives", permissives, sheet["permissives"])
    gate = IL_GATE.search(text)  # the AND semantics of the set, verbatim; without it a renderer shows a checklist (PS-08)
    _agree(f"{seq} gate tag", gate.group("tag"), tag)
    _agree(f"{seq} notes", [n for n in sheet["notes"] if n not in text], [])
    return {
        "tag": tag, "seq": seq, "kind": sheet.get("kind", "trip_logic"), "header": header, "effects": effects,
        "n_effect_columns": n_cols, "rows": rows, "start_permissives": permissives,
        "start_permissives_gate": gate.group("gate"), "start_permissives_gate_line": gate.group(0),
        "start_permissives_rule": f"ALL {len(permissives)} permissives must be TRUE (AND) before {tag} start is ENABLED",
        "notes": sheet["notes"],
        "training_values_note": "Trip set points are" in text and "training values" in text,
        "trip_boilerplate": "On any trip the effects marked X" in text,
    }


# ---------------------------------------------------------------- title blocks (A4)
DS_DOC = re.compile(r"DOC NO: (?P<doc_no>TJC-LLD-DS-\S+) REV: (?P<rev>\d+)")
DS_AREA = re.compile(r"AREA (?P<area>\d{4} - .+?) FUNCTIONAL LOC\. (?P<floc>\S+) CRITICALITY (?P<crit>HIGH CRITICAL|LOW CRITICAL|NON CRITICAL)")
DS_STATUS = re.compile(r"DATASHEET REV Rev (?P<rev>\d+) - (?P<status>ISSUED FOR [A-Z]+)")
DWG = re.compile(r"DWG No\. (?P<dwg_no>TJC-LLD-(?:GA|PP)-\S+) REV:(?P<rev>\S+) SHEET")
HIST_ROW = re.compile(r"(?P<rev>[A-Z0-9]) (?P<desc>ISSUEDFOR[A-Z]+) (?P<by>[A-Z]{2}) (?P<date>\d{2}-\d{2}-\d{4})")


def parse_datasheet(text):
    """Datasheet title block: doc_no, rev, issue status, area, functional location, criticality (A4, Task 1.7)."""
    d, a, s = DS_DOC.search(text).groupdict(), DS_AREA.search(text).groupdict(), DS_STATUS.search(text).groupdict()
    return {"doc_no": d["doc_no"], "rev": int(d["rev"]), "status": s["status"], "status_rev": int(s["rev"]),
            "area": a["area"], "floc": a["floc"], "criticality": a["crit"]}


def parse_drawing(text):
    """GA drawing or plot plan title block: dwg_no, rev and the revision history rows A/B/0 with dates as ISO (A4).

    Raw extraction drops the spaces inside ISSUEDFORREVIEW etc.; the description is re-spaced, dates are DD-MM-YYYY.
    """
    d = DWG.search(text).groupdict()
    hist = [{"rev": r, "description": desc.replace("ISSUEDFOR", "ISSUED FOR "), "by": by,
             "date": datetime.datetime.strptime(dt, "%d-%m-%Y").date().isoformat()} for r, desc, by, dt in HIST_ROW.findall(text)]
    cur = [h for h in hist if h["rev"] == d["rev"]]
    return {"dwg_no": d["dwg_no"], "rev": d["rev"], "status": cur[0]["description"] if cur else None, "history": hist}


def revision_spot(datasheets, drawings, plots, interlocks):
    """{tag: {datasheet, ga_drawing, plot_plan, interlock}} revision tuples parsed from the four title blocks (A4)."""
    out = {}
    for tag in sorted(datasheets):
        ds, il = datasheets[tag], interlocks[tag]["header"]
        out[tag] = {
            "datasheet": {"doc_no": ds["doc_no"], "rev": ds["rev"], "status": ds["status"]},
            "ga_drawing": drawings[tag], "plot_plan": plots[tag],
            "interlock": {k: il[k] for k in ("doc_no", "work_no", "rev", "logic_no", "sil")},
        }
    return out


# ---------------------------------------------------------------- equipment master (Task 1.7)
def _majority(values):
    c = Counter(v for v in values if v not in (None, ""))
    return sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0] if c else None


def equipment_master(rows, datasheets, interlocks):
    """Per-tag roll-up of the workbook joined to the datasheet and the C&E sheet (Task 1.7; DP-10: SIL is the sheet's).

    interlock_workbook = majority of Related_Interlock over populated rows ('-' -> null); interlock_sheet = LOGIC No of the
    C&E sheet (N/A -> null). Totals over the eight rows reconcile to the workbook (rows, flagged breakdowns, hours, cost).
    """
    by = {}
    for r in rows:
        by.setdefault(r["Equipment_Tag"], []).append(r)
    out = []
    for tag in sorted(by):
        rs = by[tag]
        bd = [r for r in rs if r["Breakdown"] == "Yes"]
        ub = [r for r in rs if r["breakdown_kind"] == "unplanned"]
        il = _majority(str(r["Related_Interlock"]) for r in rs)
        ds, sh = datasheets[tag], interlocks[tag]["header"]
        out.append({
            "tag": tag,
            "name": _majority(r["Equipment_Name"] for r in rs),
            "functional_location": _majority(r["Functional_Location"] for r in rs),
            "area_workbook": _majority(f"{r['Area_Code']} - {r['Area_Name']}" for r in rs),
            "area_datasheet": ds["area"],
            "criticality_workbook": _majority(r["Criticality"] for r in rs),
            "criticality_datasheet": ds["criticality"],
            "interlock_workbook": None if il == "-" else il,
            "interlock_sheet": sh["logic_no"],
            "sil_sheet": sh["sil"],
            "wos": len(rs),
            "work_types": dict(sorted(Counter(r["Work_Type"] for r in rs).items())),
            "breakdowns_flagged": len(bd),
            "breakdown_h_flagged": sum(r["Downtime_Hours"] or 0.0 for r in bd),
            "planned_flagged_rows": sum(1 for r in rs if r["breakdown_kind"] == "planned_flagged"),
            "unplanned_breakdowns": len(ub),
            "unplanned_breakdown_h": sum(r["Downtime_Hours"] or 0.0 for r in ub),
            "unplanned_failure_rows": sum(1 for r in rs if r["is_failure"] and not r["is_planned"]),
            "breakdown_cost_flagged_idr": sum(r["Total_Cost_IDR"] or 0 for r in bd),
            "all_cost_idr": sum(r["Total_Cost_IDR"] or 0 for r in rs),
            "incomplete_rows": sum(1 for r in rs if not r["closeout_complete"]),
        })
    return out


# ---------------------------------------------------------------- proof tests (FR-116, Addendum P3)
PROOF_CLASSES = (
    ("sis_proof_test", "Inspection", re.compile(r"SIS proof test of SEQ-")),
    ("sil_logic_proof_test", "Inspection", re.compile(r"SIL-[12] proof test")),
    ("calibration_proof_test", "Calibration", re.compile(r"proof test", re.I)),
    ("psv_statutory_test", "Inspection", re.compile(r"PSV pop test|relief valve test")),
)


def proof_tests(rows):
    """Work orders classified as SIS / SIL-logic / calibration proof tests and statutory PSV tests, with the last test
    date per asset and class (FR-116; Addendum P3 fixes the counts at 18 / 5 / 7 / 3 = 33)."""
    out = {"classes": {}, "last_by_asset": {}, "total": 0}
    tags = sorted({r["Equipment_Tag"] for r in rows})
    for name, wt, rx in PROOF_CLASSES:
        hits = sorted((r for r in rows if r["Work_Type"] == wt and rx.search(str(r["Problem_Description"] or ""))),
                      key=lambda r: (r["Report_Date"], r["WO_Number"]))
        out["classes"][name] = {
            "count": len(hits),
            "items": [{"wo": r["WO_Number"], "tag": r["Equipment_Tag"], "report_date": r["Report_Date"].date().isoformat(),
                       "seq": None if r["Related_Interlock"] in (None, "", "-") else r["Related_Interlock"],
                       "problem_description": r["Problem_Description"], "root_cause": r["Root_Cause"],
                       "corrective_action": r["Corrective_Action"]} for r in hits],
        }
        out["total"] += len(hits)
        for tag in tags:
            mine = [r["Report_Date"].date().isoformat() for r in hits if r["Equipment_Tag"] == tag]
            out["last_by_asset"].setdefault(tag, {})[name] = max(mine) if mine else None
    return out


# ---------------------------------------------------------------- personnel (CF-18)
PERSON = re.compile(r"^(?P<name>.+?)\s*\((?P<id>EMP-\d{4})\)$")
ROLE_CLASS = {"09": "manager", "11": "supervisor", "20": "reporter", "30": "executor", "40": "executor", "50": "executor"}
WO_ROLES = (("Reported_By", "wo_reporter", "reporter"), ("Executed_By", "wo_executor", "executor"), ("Approved_By", "wo_approver", "supervisor"))


def role_class(emp_id):
    return ROLE_CLASS.get(emp_id[4:6]) if emp_id else None


def personnel(rows, parsed):
    """Person table keyed by EMP id from the workbook's three role columns and the lessons' footer roles, with the id-prefix
    role class (09 manager, 11 supervisor, 20 reporter, 30-50 executor) and the per-work-order role anomalies (CF-18).

    Names come from the workbook where the id appears there, else from the lesson footer. anomalies: a row whose
    reporter and executor are the same person, or whose column holder's id class is not the column's class.
    """
    people, anomalies = {}, []
    for r in sorted(rows, key=lambda r: r["WO_Number"]):
        ids, flags = {}, []
        for col, role, expect in WO_ROLES:
            m = PERSON.match(str(r[col] or ""))
            if not m:
                continue
            p = people.setdefault(m["id"], {"name": m["name"], "role_class": role_class(m["id"]), "roles": Counter(), "sources": set()})
            p["roles"][role] += 1
            p["sources"].add("workbook")
            ids[col] = m["id"]
            if role_class(m["id"]) != expect:
                flags.append(f"{col} id class is {role_class(m['id'])}, expected {expect}")
        if ids.get("Reported_By") and ids.get("Reported_By") == ids.get("Executed_By"):
            flags.append("Reported_By and Executed_By are the same person")
        if flags:
            anomalies.append({"wo": r["WO_Number"], "ids": dict(sorted(ids.items())), "flags": flags})
    for oid in sorted(parsed):
        lp = parsed[oid]
        for key, role in (("reviewed_by", "opl_reviewer"), ("approved_by", "opl_approver")):
            eid = lp[key + "_id"]
            if not eid:
                continue
            p = people.setdefault(eid, {"name": lp[key], "role_class": role_class(eid), "roles": Counter(), "sources": set()})
            p["roles"][role] += 1
            p["sources"].add("opl")
    table = {eid: {"name": p["name"], "role_class": p["role_class"], "roles": dict(sorted(p["roles"].items())),
                   "sources": sorted(p["sources"])} for eid, p in sorted(people.items())}
    return {
        "people": table,
        "anomalies": anomalies,
        "opl_managers_absent_from_workbook": sorted(e for e, p in table.items() if p["role_class"] == "manager" and "workbook" not in p["sources"]),
        "opl_reviewers_are_wo_approvers": sorted(e for e, p in table.items() if "opl_reviewer" in p["roles"] and "wo_approver" in p["roles"]),
        "prepared_by_is_role": sorted({v["prepared_by_role"] for v in parsed.values() if v["prepared_by_role"]}),
    }


# ---------------------------------------------------------------- families (CR-20) and chains (CR-12)
def families(rows, pops):
    """packages/families.json (analyst classification, Appendix C.4) checked against the workbook, plus r per asset =
    share of the asset's unplanned-failure rows that belong to any family (the recurrence term of CR-11)."""
    fam = json.load(open(os.path.join(PACKAGES, "families.json"), encoding="utf-8"))
    tag_of = {r["WO_Number"]: r["Equipment_Tag"] for r in rows}
    uf = {r["WO_Number"] for r in pops["unplanned_failure"]}
    member_of = {}
    for f in fam:
        for w in f["member_wos"]:
            member_of.setdefault(w, []).append(f["family"])
    r_by_tag = {}
    for tag in sorted({r["Equipment_Tag"] for r in rows}):
        n = sorted(w for w in uf if tag_of[w] == tag)
        k = [w for w in n if w in member_of]
        r_by_tag[tag] = {"unplanned_failure_rows": len(n), "in_family": len(k), "member_wos": k, "r": round(len(k) / len(n), 4) if n else 0.0}
    return {
        "families": [{"family": f["family"], "basis": f["basis"], "member_wos": f["member_wos"], "member_basis": f["member_basis"],
                      "tags": sorted({tag_of[w] for w in f["member_wos"] if w in tag_of}),
                      "members_outside_unplanned57": sorted(w for w in f["member_wos"] if w not in uf)} for f in fam],
        "unknown_wos": sorted(w for w in member_of if w not in tag_of),
        "multi_family_wos": sorted(w for w, fs in member_of.items() if len(fs) > 1),
        "r_by_tag": r_by_tag,
    }


LEXICON = sorted("""misalignment spalling spalled plugging plugged fouling fouled erosion eroded corrosion corroded wear worn
cracked crack drift drifting leak leaking seized hardened degraded elongation slip slack vibration overheating imbalance
fatigue fractured ruptured collapsed dislodged relaxed restricted clearance settlement overload hunting tuning saturated
blocked burnt""".split() + ["end of life", "open circuit"])
CHAIN_WINDOW_DAYS = 365


def _nouns(text):
    low = str(text or "").lower()
    return {n for n in LEXICON if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low)}


def chains(pops):
    """PRD 19.4 made reproducible (CR-12): a link A -> B exists between two failure records (Work_Type Corrective/Overhaul
    or Breakdown = Yes) of the same asset when B's Root_Cause or Problem_Description contains a LEXICON noun that also
    appears in A's Root_Cause and B is reported 1..365 days after A. The linking sentence is B's field text verbatim."""
    links = []
    fail = sorted(pops["failure"], key=lambda r: (r["Equipment_Tag"], r["Report_Date"], r["WO_Number"]))
    for a in fail:
        na = _nouns(a["Root_Cause"])
        if not na:
            continue
        for b in fail:
            days = (b["Report_Date"] - a["Report_Date"]).days
            if b["Equipment_Tag"] != a["Equipment_Tag"] or not (0 < days <= CHAIN_WINDOW_DAYS):
                continue
            for field in ("Root_Cause", "Problem_Description"):
                for noun in sorted(na & _nouns(b[field])):
                    if not any(l["from_wo"] == a["WO_Number"] and l["to_wo"] == b["WO_Number"] and l["noun"] == noun for l in links):
                        links.append({"from_wo": a["WO_Number"], "to_wo": b["WO_Number"], "tag": a["Equipment_Tag"], "noun": noun,
                                      "field": field, "linking_sentence": b[field], "days": days})
    links.sort(key=lambda l: (l["tag"], l["from_wo"], l["to_wo"], l["noun"]))
    return {"lexicon": LEXICON, "population": "failure (66)", "window_days": CHAIN_WINDOW_DAYS, "links": links,
            "total": len(links), "by_tag": dict(sorted(Counter(l["tag"] for l in links).items()))}


def datasheet_spot(datasheet_texts):
    """packages/datasheet_spot.json (CR-07: three typed values per asset) verified against the canonical datasheet text:
    an entry is `verified` when its quote occurs verbatim and its value_text occurs inside the quote."""
    spot = json.load(open(os.path.join(PACKAGES, "datasheet_spot.json"), encoding="utf-8"))
    out = []
    for e in sorted(spot, key=lambda e: (e["tag"], e["field"])):
        out.append(dict(e, verified=e["quote"] in datasheet_texts[e["tag"]] and e["value_text"] in e["quote"]))
    return {"entries": out, "n": len(out), "verified": sum(1 for e in out if e["verified"]),
            "by_tag": dict(sorted(Counter(e["tag"] for e in out).items()))}


def compute(ctx):
    """Fixture keys: equipment_master, interlock_rows, proof_tests, personnel, families, chains, datasheet_spot, revision_spot."""
    ds_text = class_texts("datasheet")
    datasheets = {t: parse_datasheet(x) for t, x in ds_text.items()}
    hand = hand_effects()
    interlocks = {t: parse_interlock(t, x, hand) for t, x in class_texts("interlock").items()}
    drawings = {t: parse_drawing(x) for t, x in class_texts("ga_drawing").items()}
    plots = {t: parse_drawing(x) for t, x in class_texts("plot_plan").items()}
    return {
        "equipment_master": equipment_master(ctx["rows"], datasheets, interlocks),
        "interlock_rows": {t: interlocks[t] for t in sorted(interlocks)},
        "proof_tests": proof_tests(ctx["rows"]),
        "personnel": personnel(ctx["rows"], ctx["parsed"]),
        "families": families(ctx["rows"], ctx["pops"]),
        "chains": chains(ctx["pops"]),
        "datasheet_spot": datasheet_spot(ds_text),
        "revision_spot": revision_spot(datasheets, drawings, plots, interlocks),
    }


def context():
    """The ctx dict compute() expects, built from the foundation modules (the integrator builds its own)."""
    from . import opl, workbook
    from .pdftext import corpus_files, opl_texts
    rows = workbook.load()
    texts = opl_texts()
    return {"rows": rows, "pops": workbook.populations(rows), "opl": texts, "parsed": opl.parse_all(texts), "files": corpus_files()}


def write_packages():
    """`make packages`: rewrite the package artefacts that are pinned copies of the harness output (CS-08).

    Only packages/chains.json today; the hand-keyed stores (families, hand_verified, sidecars, spot files) are inputs and
    are never written from here.
    """
    out = os.path.join(PACKAGES, "chains.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(chains(context()["pops"]), f, sort_keys=True, indent=1, ensure_ascii=False)
        f.write("\n")
    return out


if __name__ == "__main__":
    if "--write-packages" in sys.argv:
        print("wrote", write_packages())
    else:
        print(json.dumps(compute(context()), sort_keys=True, indent=1, default=str))
