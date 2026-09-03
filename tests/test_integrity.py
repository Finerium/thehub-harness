"""Integrity register (harness/integrity.py). Every expectation below was printed by the module AND by a throwaway
cross-check (scratchpad xcheck_integrity.py, 2026-08-30) that takes a different route: pdftotext -raw called directly with its
own whitespace collapse, openpyxl read directly, the audit's cross-ref regexes for CD-1/CD-5, a brute-force longest-prefix regex
over the raw lesson text for CD-12, a token scan for CD-13, grep-style checks for CD-11/CD-16/CD-17 and plain comprehensions
over hand_verified.json for CD-2/7/8/9/18. Differences from the plan/addendum baselines are asserted as observed, not forced
(see CD-12: 38 cells in 20 lessons, not the addendum's approximate 35 in 17)."""
import json
import os

from harness import integrity as I, opl as O, pdftext as P, workbook as W
from harness.config import CORPUS, ROOT

ROWS = W.load()
CTX = {"rows": ROWS, "pops": W.populations(ROWS), "opl": O.opl_texts(), "parsed": O.parse_all(), "files": P.corpus_files()}
R = I.compute(CTX)
BY_WO = {w["WO_Number"]: w for w in ROWS}
KEYS = {"rule", "definition", "unit", "count", "items", "basis", "severity", "observation_only"}


def test_shape_counts_and_total():
    counts = {k: R[k]["count"] for k in R if k.startswith("CD-")}
    assert counts == {"CD-1": 28, "CD-2": 6, "CD-4": 26, "CD-5": 5, "CD-6": 8, "CD-7": 4, "CD-8": 1, "CD-9": 4, "CD-10": 2,
                      "CD-11": 2, "CD-12": 38, "CD-13": 35, "CD-14": 11, "CD-15": 123, "CD-16": 8, "CD-17": 1, "CD-18": 3}
    assert "CD-3" not in R  # deleted (DP-06)
    for k in counts:
        assert KEYS <= set(R[k]) and R[k]["count"] == len(R[k]["items"])
        assert R[k]["basis"] in ("H", "M", "H+M") and R[k]["severity"] in ("high", "medium", "low")
    assert {k for k in counts if R[k]["observation_only"]} == {"CD-15", "CD-16"}
    assert R["total"] == sum(v for k, v in counts.items() if k not in ("CD-15", "CD-16")) == 174
    assert {k: R[k]["basis"] for k in ("CD-2", "CD-7", "CD-8", "CD-9", "CD-18")} == {"CD-2": "M", "CD-7": "H+M", "CD-8": "H+M", "CD-9": "M", "CD-18": "H+M"}


def test_cd1_cd5_cross_references():
    assert R["CD-1"]["by_tag"] == {"DC-3401A": 7, "EA-5601": 7, "KC-4501": 7, "LV-6701": 7}
    assert all(it["foreign_tags"] == ["GA-1201A"] for it in R["CD-1"]["items"])
    assert [it["opl_id"] for it in R["CD-5"]["items"]] == ["OPL-GA-1201A-01", "OPL-GA-1201A-02", "OPL-GA-1201A-03", "OPL-GA-1201A-05", "OPL-GA-1201A-06"]


def test_cd4_closeouts_and_emergency():
    c = R["CD-4"]
    assert c["by_work_type"] == {"Calibration": 1, "Corrective": 20, "Overhaul": 3, "Preventive": 2}
    assert c["emergency"] == ["WO-240002", "WO-240032", "WO-240083"] and R["cd4_emergency"] == 3  # A1
    for it in c["items"]:
        w = BY_WO[it["wo"]]
        assert it["priority"] == w["Priority"] and w["Status"] == "Completed"
        assert all(w[f] for f in W.NARR) and all(w[f] in (None, "") for f in W.OUTCOME_FIELDS)


def test_cd6_planned_flagged():
    c = R["CD-6"]
    assert [it["wo"] for it in c["items"]] == ["WO-240060", "WO-240065", "WO-240116", "WO-240117", "WO-240119", "WO-240189", "WO-240194", "WO-240197"]
    assert (c["downtime_h"], c["cost_idr"]) == (164.0, 69_270_000)


def test_cd10_criticality_review():
    c = R["CD-10"]
    assert c["fleet_median_h"] == 31.0
    assert [(it["tag"], it["criticality"], it["unplanned_h"], it["events"]) for it in c["items"]] == [("CT-7801", "NON CRITICAL", 46.0, 3), ("EA-5601", "LOW CRITICAL", 54.0, 3)]
    assert {t: v["unplanned_h"] for t, v in c["per_asset"].items()} == {"CT-7801": 46.0, "DC-3401A": 24.0, "EA-5601": 54.0, "FA-8901": 12.0, "GA-1201A": 6.5, "KC-4501": 38.0, "LV-6701": 21.0, "YD-2301": 68.5}
    assert sum(v["unplanned_h"] for v in c["per_asset"].values()) == 270.0


def test_cd11_ga_drawings():
    assert R["CD-11"]["items"] == [
        {"tag": "CT-7801", "evidence": ["DRY WEIGHT past"]},
        {"tag": "EA-5601", "evidence": ["drum vocabulary WATER BOOT / MIST PAD / HORIZONTAL DRUM absent from the datasheet"]},
    ]


def test_cd12_truncated_cells():
    """38 cells in 20 lessons (addendum P2 estimated about 35 in 17): the same WO-240028 cell appears without a trailing
    period in OPL-YD-2301-01/-04/-06; OPL-DC-3401A-07 has no WO-240056 row but truncates WO-240061 ('fresh cat.')."""
    c = R["CD-12"]
    assert (c["count"], c["lessons"]) == (38, 20)
    assert c["by_lesson"] == {**{f"OPL-GA-1201A-0{i}": 4 for i in range(1, 7)}, **{f"OPL-YD-2301-0{i}": 1 for i in range(1, 8)},
                              **{f"OPL-DC-3401A-0{i}": 1 for i in range(1, 8)}}
    for it in c["items"]:
        assert it["cell"] != it["field_text"] and it["field_text"].startswith(it["cell"]) and 64 <= len(it["cell"]) <= 69
        assert P.canonical(str(BY_WO[it["wo"]][it["field"]])) == it["field_text"]
    ga1 = {(it["wo"], it["field"]) for it in c["items"] if it["opl_id"] == "OPL-GA-1201A-01"}
    assert ga1 == {("WO-240002", "Problem_Description"), ("WO-240002", "Root_Cause"), ("WO-240002", "Corrective_Action"), ("WO-240003", "Corrective_Action")}
    dc = {it["opl_id"]: (it["wo"], it["cell"][-16:]) for it in c["items"] if it["tag"] == "DC-3401A"}
    assert dc["OPL-DC-3401A-01"] == ("WO-240056", "verified reading") and dc["OPL-DC-3401A-07"] == ("WO-240061", "3.2 m3 fresh cat")
    assert all(it["cell"].endswith("re-nipped after") for it in c["items"] if it["tag"] == "YD-2301")
    raw = P.opl_texts(canon=False)
    assert all(I.canonical_lines(raw[k])[0] == P.canonical(raw[k]) for k in raw)


def test_cd13_hazard_limits():
    c = R["CD-13"]
    assert c["by_tag"] == {"CT-7801": 7, "GA-1201A": 7, "KC-4501": 7, "LV-6701": 7, "YD-2301": 7}  # P1: DC, EA, FA match
    miss = {it["tag"]: it["missing"] for it in c["items"]}
    assert miss["GA-1201A"] == [["16", "barg", "pressure"], ["80", "degC", "temperature"]]
    assert miss["KC-4501"] == [["150", "degC", "temperature"], ["16", "barg", "pressure"]]
    assert miss["YD-2301"] == [["6", "barg", "pressure"]] and miss["LV-6701"] == [["120", "degC", "temperature"]] and miss["CT-7801"] == [["50", "degC", "temperature"]]
    assert I.typed_values("DESIGN P/T 16 barg / 200 degC OPERATING TEMP. 95-110 degC 2 kg/cm2g 0.35 bar") == {(16.0, "pressure"), (200.0, "temperature"), (95.0, "temperature"), (110.0, "temperature"), (2.0, "pressure"), (0.35, "pressure")}


def test_cd14_cd15_workbook_observations():
    c = R["CD-14"]
    assert [it["wo"] for it in c["items"]] == ["WO-240044", "WO-240089", "WO-240097", "WO-240113", "WO-240116", "WO-240119", "WO-240123", "WO-240171", "WO-240177", "WO-240189", "WO-240201"]
    assert all(abs(it["diff_idr"]) == 1000 for it in c["items"]) and c["max_abs_diff_idr"] == 1000 and not c["observation_only"]
    o = R["CD-15"]
    assert o["count"] == 123 and o["observation_only"] and o["non_chronological_pairs"] == 103
    assert all(it["notification_no"].startswith("NT-2024-") and it["report_year"] == 2025 for it in o["items"])


def test_cd16_area_aliases():
    c = R["CD-16"]
    assert c["observation_only"] and [it["tag"] for it in c["items"]] == sorted(c["aliases"]) and len(c["aliases"]) == 8
    assert all(it["n_vocabularies"] == 2 for it in c["items"])
    assert c["aliases"]["CT-7801"] == {"workbook": "COOLING WATER SYSTEM", "datasheet": "7800 - COOLING WATER SYSTEM",
                                       "plot_plan_title": "7800-COOLINGTOWERSYSTEM", "opl": "7800 - COOLING TOWER SYSTEM"}
    with open(I.AREA_ALIASES, encoding="utf-8") as f:
        assert json.load(f) == c["aliases"]


def test_cd17_and_no_sif_fixture():
    assert R["CD-17"]["items"] == [{"tag": "EA-5601", "logic_no": "N/A (control loop only)", "trip_rows": 0,
                                    "row_kinds": ["alarm", "control", "mech"], "boilerplate": ["On any trip", "Safety PLC", "latched"]}]
    assert R["no_sif_fixture"] == {"tag": "EA-5601", "protection": ["TIC-5602 control", "PDAH-5605 alarm > 0.7 bar", "PSV-5607 relief 16 barg"],
                                   "source": "TJC-LLD-IL-EA-5601 LOGIC No: N/A (control loop only); datasheet note 1", "criticality": "LOW CRITICAL"}


def test_hand_verified_rules():
    hv = I.hand_verified()
    assert (hv["verified_by"], hv["verified_on"]) == ("executor (role alias EXEC-1)", "2026-08-27") and len(hv["sets"]) == 8
    pngs = {os.path.basename(f) for f in CTX["files"] if P.doc_class(f) == "pid"}
    for s in hv["sets"]:
        assert s["file"] in pngs and any(f"Set_0{s['set']}_{s['tag']}" in f for f in CTX["files"])
        # plan Task 1.5: verifier role alias and date on EVERY entry, so a later re-check of one sheet has a place to
        # record itself instead of silently invalidating the file-level date (mirrors pid_sidecars' per-file provenance)
        assert s["verified_by"] and s["verified_on"] and len(s["verified_on"]) == 10
    text = json.dumps(hv)
    assert "FROM STORAGE TANK 12-T-01" in text and "OPL-OPL-LV-6701-07" in text  # P8
    assert [it["set"] for it in R["CD-2"]["items"]] == [1, 2, 3, 6, 7, 8] and R["CD-2"]["items"][2]["ref_dwg"] is None
    assert [(it["set"], it["cited"], it["expected"]) for it in R["CD-7"]["items"]] == [
        (2, "TJC-LLD-DS-GA-1201A", "TJC-LLD-DS-YD-2301"), (4, "TJC-LLD-PF-GA-4501A", "TJC-LLD-DS-KC-4501"),
        (7, "TJC-LLD-DS-GA-7801A", "TJC-LLD-DS-CT-7801"), (8, "TJC-LLD-GA-FA-8901", "TJC-LLD-DS-FA-8901")]
    assert R["CD-8"]["items"] == [{"set": 2, "tag": "YD-2301", "cited": "SEQ-1201", "expected": "SEQ-5500"}]
    assert [it["set"] for it in R["CD-9"]["items"]] == [2, 4, 7, 8]
    assert [(it["set"], it["kind"], it["sibling_confirmed"]) for it in R["CD-18"]["items"]] == [(2, "footprint", True), (2, "instrument identity", True), (4, "revision", True)]


def test_deterministic_and_serialisable():
    a = json.dumps(R, sort_keys=True)
    b = json.dumps(I.compute(dict(CTX, rows=W.load()), write_aliases=False), sort_keys=True)
    assert a == b and ROOT not in a and CORPUS not in a
