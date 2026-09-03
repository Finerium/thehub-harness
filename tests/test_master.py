"""harness.master: equipment master, C&E rows, proof tests, personnel, families, chains, spot fixtures.

Every expectation below was observed by running harness.master.compute() and cross-checked on 2026-08-30 with two
throwaway scripts on a different code path (scratchpad xcheck_master.py: direct openpyxl reads, substring class tests,
line-based counts over the raw pdftotext output, an independent token-split chain rule; xcheck_revision.py: line-based
title-block parse of the raw text that wrote packages/revision_spot.json). The C&E effect columns were hand-read from the
rendered sheets (pdftoppm) and checked against the X counts parsed from the raw text.
"""
import json
import os
import random

import pytest

from harness import master
from harness.config import PACKAGES

TAGS = ["CT-7801", "DC-3401A", "EA-5601", "FA-8901", "GA-1201A", "KC-4501", "LV-6701", "YD-2301"]


@pytest.fixture(scope="module")
def ctx():
    return master.context()


@pytest.fixture(scope="module")
def out(ctx):
    return master.compute(ctx)


def test_equipment_master_reconciles_to_workbook(out):
    """Totals cross-checked by direct openpyxl sums (211 rows, 31 flagged, 434.0 h, IDR 413,345,000 / 537,770,000)."""
    em = out["equipment_master"]
    assert [e["tag"] for e in em] == TAGS
    assert sum(e["wos"] for e in em) == 211
    assert sum(e["breakdowns_flagged"] for e in em) == 31
    assert sum(e["breakdown_h_flagged"] for e in em) == 434.0
    assert sum(e["breakdown_cost_flagged_idr"] for e in em) == 413_345_000
    assert sum(e["all_cost_idr"] for e in em) == 537_770_000
    assert sum(e["planned_flagged_rows"] for e in em) == 8
    assert sum(e["unplanned_breakdowns"] for e in em) == 23
    assert sum(e["unplanned_breakdown_h"] for e in em) == 270.0
    assert sum(e["unplanned_failure_rows"] for e in em) == 57
    assert sum(e["incomplete_rows"] for e in em) == 26
    by = {e["tag"]: e for e in em}
    assert {t: by[t]["sil_sheet"] for t in TAGS} == {"GA-1201A": 1, "YD-2301": 2, "DC-3401A": 2, "KC-4501": 2, "EA-5601": None,
                                                     "LV-6701": 1, "CT-7801": 1, "FA-8901": 1}
    assert by["YD-2301"]["interlock_sheet"] == by["YD-2301"]["interlock_workbook"] == "SEQ-5500"
    assert by["EA-5601"]["interlock_sheet"] is None and by["EA-5601"]["interlock_workbook"] is None
    assert by["CT-7801"]["criticality_datasheet"] == "NON CRITICAL" and by["CT-7801"]["unplanned_breakdown_h"] == 46.0
    assert by["EA-5601"]["criticality_datasheet"] == "LOW CRITICAL" and by["EA-5601"]["unplanned_breakdown_h"] == 54.0
    for e in em:  # workbook and datasheet agree on area and criticality for all eight assets
        assert e["area_workbook"] == e["area_datasheet"] and e["criticality_workbook"] == e["criticality_datasheet"]


def test_interlock_rows_typed(out):
    """Row, column and permissive counts cross-checked line by line on the raw text; X counts equal the hand-read lists."""
    il = out["interlock_rows"]
    order = ["GA-1201A", "YD-2301", "DC-3401A", "KC-4501", "EA-5601", "LV-6701", "CT-7801", "FA-8901"]
    assert [len(il[t]["rows"]) for t in order] == [6, 6, 6, 6, 3, 4, 4, 4]
    assert [len(il[t]["start_permissives"]) for t in order] == [4, 4, 4, 5, 2, 3, 3, 4]
    assert [il[t]["n_effect_columns"] for t in order] == [5, 5, 5, 5, 3, 4, 3, 4]
    t3 = il["GA-1201A"]["rows"][2]
    assert (t3["id"], t3["tag"], t3["setpoint_text"], t3["setpoint_value"], t3["setpoint_unit"], t3["voting"], t3["effects"]) == \
        ("T3", "VSHH-1201", "> 7.1 mm/s RMS", 7.1, "mm/s", "1oo2", ["EFF-1", "EFF-2", "EFF-4", "EFF-5"])
    # PS-15: voting is a SIF architecture (1oo1/1oo2/2oo3). A control loop, an alarm and a relief valve have none, so
    # `voting` is null for every non-trip row and the sheet's VOTE cell survives verbatim as `vote_cell_text`.
    assert [(r["id"], r["row_kind"], r["tag"], r["voting"], r["vote_cell_text"], r["effects"]) for r in il["EA-5601"]["rows"]] == [
        ("C1", "control", "TIC-5602", None, "control", ["EFF-1"]), ("A1", "alarm", "PDAH-5605", None, "alarm", ["EFF-2"]),
        ("R1", "mech", "PSV-5607", None, "mech", ["EFF-3"])]
    assert all(r["voting"] == r["vote_cell_text"] for t in TAGS for r in il[t]["rows"] if r["row_kind"] == "trip")
    assert il["EA-5601"]["header"]["logic_no"] is None and il["EA-5601"]["header"]["sil"] is None
    assert il["EA-5601"]["trip_boilerplate"] and not any(r["row_kind"] == "trip" for r in il["EA-5601"]["rows"])  # CD-17
    for t in TAGS:
        h = il[t]["header"]
        assert (h["work_no"], h["rev"], h["doc_no"]) == ("BA-0256", 3, f"TJC-LLD-IL-{t}")
        assert len(il[t]["effects"]) == il[t]["n_effect_columns"]
        alarm = [e["id"] for e in il[t]["effects"] if e["action"] == "ANNUNCIATE ALARM ON DCS"]
        for r in il[t]["rows"]:
            assert r["effects_basis"] == "H+M" and len(r["effects"]) == r["x_count"]
            assert not alarm or alarm[0] in r["effects"]  # every trip annunciates on the DCS (sheet note 2)
    assert sum(len(il[t]["rows"]) for t in TAGS) == 39
    assert sum(1 for t in TAGS for r in il[t]["rows"] if r["effects_basis"] == "H+M") == 39


def test_cause_and_effect_columns(out):
    """packages/interlock_effects.json, typed off the eight sheets rendered with `pdftoppm -png -r 150` and read as page
    images on 2026-08-30. Independent of the raw-text path in two directions: every X count here was parsed from
    `pdftotext -raw` by harness.master (a row raises unless the typed column list is exactly that long), and the eight
    matrices were read a second time off the images, row by row, when this test was written."""
    by_seq = {s["seq"]: s for s in out["interlock_rows"].values()}
    assert sorted(by_seq) == ["EA-5601", "SEQ-1201", "SEQ-3401", "SEQ-4501", "SEQ-5500", "SEQ-6701", "SEQ-7801", "SEQ-8901"]
    order = ["GA-1201A", "YD-2301", "DC-3401A", "KC-4501", "EA-5601", "LV-6701", "CT-7801", "FA-8901"]
    assert [len(out["interlock_rows"][t]["rows"]) for t in order] == [6, 6, 6, 6, 3, 4, 4, 4]

    rows = {r["id"]: r for r in by_seq["SEQ-1201"]["rows"]}  # DP-31: min-flow FV-1201 does not open on a vibration trip
    assert (rows["T3"]["tag"], rows["T3"]["setpoint_text"], rows["T3"]["voting"]) == ("VSHH-1201", "> 7.1 mm/s RMS", "1oo2")
    assert rows["T3"]["effects"] == ["EFF-1", "EFF-2", "EFF-4", "EFF-5"] and "EFF-3" not in rows["T3"]["effects"]
    assert [e for e in by_seq["SEQ-1201"]["effects"] if e["id"] == "EFF-3"][0]["final_element"] == "OPEN MIN-FLOW FV-1201"

    seq5500 = by_seq["SEQ-5500"]
    assert seq5500["tag"] == "YD-2301" and len(seq5500["rows"]) == 6
    assert [r["tag"] for r in seq5500["rows"]] == ["TSHH-2301", "FSLL-2302", "LSHH-2303", "SSLL-2305", "ASHH-2307", "MPR-2301"]

    t2 = {r["id"]: r for r in by_seq["SEQ-3401"]["rows"]}["T2"]  # observed: EFF-5 (the DCS alarm) as well
    assert t2["tag"] == "PSHH-3404" and {"EFF-2", "EFF-3"} <= set(t2["effects"])
    assert t2["effects"] == ["EFF-2", "EFF-3", "EFF-5"]

    ea = by_seq["EA-5601"]
    assert ea["kind"] == "control_loop_only" and ea["header"]["sil"] is None and ea["header"]["logic_no"] is None
    assert [(r["id"], r["row_kind"]) for r in ea["rows"]] == [("C1", "control"), ("A1", "alarm"), ("R1", "mech")]
    assert not any(r["row_kind"] == "trip" for r in ea["rows"])

    for seq, sheet in sorted(by_seq.items()):
        n = len(sheet["effects"])
        assert [e["id"] for e in sheet["effects"]] == [f"EFF-{i}" for i in range(1, n + 1)], seq
        assert all(e["final_element"] == e["action"] for e in sheet["effects"]), seq
        for r in sheet["rows"]:
            assert r["effects"] == sorted(set(r["effects"]), key=lambda e: int(e.split("-")[1])), (seq, r["id"])
            assert set(r["effects"]) <= {e["id"] for e in sheet["effects"]}, (seq, r["id"])


def test_hand_effects_cannot_contradict_the_raw_text():
    """A typed field that the sheet does not say must raise, not silently win (rule 3)."""
    from harness.pdftext import class_texts
    text = class_texts("interlock")["GA-1201A"]
    hand = master.hand_effects()
    assert master.parse_interlock("GA-1201A", text, hand)["rows"][0]["setpoint_text"] == "< 0.5 barg"
    hand["SEQ-1201"]["rows"][0]["setpoint_text"] = "< 0.6 barg"
    with pytest.raises(ValueError, match="disagrees with the raw text at SEQ-1201 T1"):
        master.parse_interlock("GA-1201A", text, hand)
    hand = master.hand_effects()  # T3 has four X marks in the text; a three-column list cannot be a reading of that row
    hand["SEQ-1201"]["rows"][2]["effects"] = ["EFF-1", "EFF-2", "EFF-3"]
    with pytest.raises(ValueError, match="SEQ-1201 T3 x_count"):
        master.parse_interlock("GA-1201A", text, hand)


def test_proof_tests_counts(out):
    """Addendum P3: 18 / 5 / 7 / 3 = 33; cross-checked with substring classification."""
    pt = out["proof_tests"]
    assert {k: v["count"] for k, v in pt["classes"].items()} == {"sis_proof_test": 18, "sil_logic_proof_test": 5,
                                                                "calibration_proof_test": 7, "psv_statutory_test": 3}
    assert pt["total"] == 33
    assert "WO-240012" in [i["wo"] for i in pt["classes"]["sil_logic_proof_test"]["items"]]
    assert sorted(i["wo"] for i in pt["classes"]["psv_statutory_test"]["items"]) == ["WO-240060", "WO-240116", "WO-240189"]
    assert pt["last_by_asset"]["GA-1201A"]["sis_proof_test"] == "2025-09-27"
    assert pt["last_by_asset"]["DC-3401A"]["psv_statutory_test"] == "2024-08-05"
    assert pt["last_by_asset"]["EA-5601"] == {"sis_proof_test": None, "sil_logic_proof_test": None,
                                              "calibration_proof_test": None, "psv_statutory_test": "2024-07-31"}


def test_personnel_roles(out):
    """CF-18: 21 workbook ids + 2 OPL-only managers; anomalies WO-240142 and WO-240161 only (direct openpyxl scan)."""
    pe = out["personnel"]
    assert len(pe["people"]) == 23
    assert pe["opl_managers_absent_from_workbook"] == ["EMP-0901", "EMP-0912"]
    assert pe["opl_reviewers_are_wo_approvers"] == ["EMP-1102", "EMP-1113", "EMP-1124"]
    assert pe["people"]["EMP-1124"]["roles"] == {"opl_reviewer": 21, "wo_approver": 74}
    assert pe["people"]["EMP-0901"] == {"name": "Zulkarnain Hasan", "role_class": "manager", "roles": {"opl_approver": 28}, "sources": ["opl"]}
    assert [a["wo"] for a in pe["anomalies"]] == ["WO-240142", "WO-240161"]
    assert pe["anomalies"][0]["flags"] == ["Executed_By id class is reporter, expected executor"]
    assert pe["anomalies"][1]["ids"]["Reported_By"] == pe["anomalies"][1]["ids"]["Executed_By"] == "EMP-2010"
    assert pe["prepared_by_is_role"] == ["Panel Operator / Technician"]


def test_families_membership_and_r(out):
    """CR-20 memberships from the plan; r cross-checked from the workbook directly."""
    fa = out["families"]
    assert fa["unknown_wos"] == [] and fa["multi_family_wos"] == []
    m = {f["family"]: f["member_wos"] for f in fa["families"]}
    assert m["gasket seating and manway leaks"] == ["WO-240062", "WO-240111", "WO-240145", "WO-240195"]
    assert set(m["PTFE packing and stem friction"]) >= {"WO-240138", "WO-240135", "WO-240029", "WO-240028"}
    assert set(m["exchanger fouling and thermal performance"]) >= {"WO-240110", "WO-240119", "WO-240089"}
    # PS-09: WO-240091's recorded root cause is "Restricted oil supply groove to No.2 main bearing" -- a lubrication
    # supply failure with the bearing as the location, not a degraded bearing -- so it left this family for its own.
    assert set(m["alignment and bearing degradation"]) >= {"WO-240003", "WO-240004", "WO-240007", "WO-240088", "WO-240169", "WO-240166"}
    assert "WO-240091" not in m["alignment and bearing degradation"]
    assert m["lubrication supply and oil-system degradation"] == ["WO-240084", "WO-240091"]
    assert {t: v["r"] for t, v in fa["r_by_tag"].items()} == {"CT-7801": 0.4286, "DC-3401A": 0.1429, "EA-5601": 0.25, "FA-8901": 0.2,
                                                             "GA-1201A": 0.4286, "KC-4501": 0.625, "LV-6701": 0.4286, "YD-2301": 0.375}
    assert fa["r_by_tag"]["KC-4501"]["unplanned_failure_rows"] == 8
    assert [f["members_outside_unplanned57"] for f in fa["families"]] == [[], [], ["WO-240119"], [], []]


def test_chains_ga1201a(out):
    """CR-12: 18 links under the noun rule; the GA-1201A misalignment links (independent token-split implementation)."""
    ch = out["chains"]
    assert ch["total"] == len(ch["links"]) == 18
    assert ch["by_tag"] == {"CT-7801": 3, "EA-5601": 1, "FA-8901": 1, "GA-1201A": 4, "KC-4501": 3, "YD-2301": 6}
    trip = {(l["from_wo"], l["to_wo"], l["noun"]) for l in ch["links"]}
    assert {("WO-240003", "WO-240004", "misalignment"), ("WO-240004", "WO-240007", "misalignment"),
            ("WO-240003", "WO-240007", "misalignment")} <= trip
    assert not any(l["to_wo"] == "WO-240002" for l in ch["links"])  # no shared mechanism noun reaches the seal failure
    l = next(l for l in ch["links"] if (l["from_wo"], l["to_wo"]) == ("WO-240003", "WO-240004"))
    assert (l["days"], l["field"], l["linking_sentence"]) == (33, "Root_Cause", "Outer race spalling on DE bearing due to prolonged misalignment")
    assert all(0 < l["days"] <= 365 for l in ch["links"])
    assert len(ch["lexicon"]) == 45 and {"misalignment", "spalling", "fouling", "plugged", "worn", "seized"} <= set(ch["lexicon"])
    with open(os.path.join(PACKAGES, "chains.json"), encoding="utf-8") as f:
        assert json.load(f) == ch  # the reviewed package artefact is the harness output (regenerate with `make packages`)


def test_datasheet_spot_verified(out):
    """CR-07: 24 entries, three per asset, every quote found (whitespace-insensitive grep of the raw text agrees)."""
    ds = out["datasheet_spot"]
    assert ds["n"] == ds["verified"] == 24 and set(ds["by_tag"].values()) == {3}
    v = {(e["tag"], e["field"]): (e["value_num"], e["unit"]) for e in ds["entries"]}
    assert v[("DC-3401A", "psv_set_pressure")] == (6, "barg")
    assert v[("YD-2301", "lp_steam_pressure")] == (4.5, "barg")
    assert v[("CT-7801", "gearbox_oil_grade")] == (220, "ISO VG") and v[("CT-7801", "gearbox_oil_volume")] == (4.5, "L")
    assert v[("EA-5601", "tube_design_pressure")] == (16, "barg") and v[("EA-5601", "tube_design_temperature")] == (200, "degC")
    assert v[("FA-8901", "psv_set_pressure")] == (10, "barg")
    assert v[("GA-1201A", "differential_pressure")] == (8.6, "bar")
    assert v[("KC-4501", "discharge_pressure")] == (12.5, "barg")
    assert v[("LV-6701", "body_rating")] == (300, "ASME class")


def test_revision_spot_matches_package(out):
    """A4: the canonical-text parse equals packages/revision_spot.json written by a line-based parse of the raw text."""
    rs = out["revision_spot"]
    with open(os.path.join(PACKAGES, "revision_spot.json"), encoding="utf-8") as f:
        assert rs == json.load(f)
    assert sorted(rs) == TAGS and all(sorted(rs[t]) == ["datasheet", "ga_drawing", "interlock", "plot_plan"] for t in TAGS)
    g = rs["GA-1201A"]
    assert g["datasheet"] == {"doc_no": "TJC-LLD-DS-GA-1201A", "rev": 3, "status": "ISSUED FOR OPERATION"}
    assert g["interlock"] == {"doc_no": "TJC-LLD-IL-GA-1201A", "work_no": "BA-0256", "rev": 3, "logic_no": "SEQ-1201", "sil": 1}
    assert (g["ga_drawing"]["rev"], g["ga_drawing"]["status"]) == ("0", "ISSUED FOR CONSTRUCTION")
    assert [(h["rev"], h["description"], h["date"]) for h in g["plot_plan"]["history"]] == [
        ("A", "ISSUED FOR REVIEW", "2026-05-15"), ("B", "ISSUED FOR APPROVAL", "2026-05-27"), ("0", "ISSUED FOR CONSTRUCTION", "2026-06-05")]
    for t in TAGS:
        assert rs[t]["datasheet"]["rev"] == 3 and rs[t]["interlock"]["rev"] == 3
        assert rs[t]["ga_drawing"]["history"] == rs[t]["plot_plan"]["history"]


def test_compute_is_order_independent_and_serialisable(ctx, out):
    """Shuffled rows and populations give byte-identical JSON (rule 2)."""
    rnd = random.Random(7)
    shuffled = dict(ctx, rows=rnd.sample(ctx["rows"], len(ctx["rows"])),
                    pops={k: rnd.sample(v, len(v)) for k, v in ctx["pops"].items()})
    a = json.dumps(out, sort_keys=True)
    assert json.dumps(master.compute(shuffled), sort_keys=True) == a
    assert "/Users/" not in a and "scratchpad" not in a
