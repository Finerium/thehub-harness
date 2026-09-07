"""Expectations are values observed by running harness.dates and cross-checked on 2026-08-30 with two throwaway scripts
that import nothing from harness: xcheck_dates.py (own date regex over `pdftotext -raw` output of the 56 lessons, openpyxl
read of the workbook, cadence/latency/lead-time recomputed) and xcheck_lessons.py (header/footer fields re-read with grep
style regexes over the raw text). Where the assignment stated an expectation it agreed with both, except `any_overlap`,
whose meaning the plan never defines: it is asserted under the docstring definition in harness.dates.dates."""

import json

from harness import dates as M
from harness import opl, pdftext, workbook

ROWS = workbook.load()
CTX = {
    "rows": ROWS,
    "pops": workbook.populations(ROWS),
    "opl": opl.opl_texts(),
    "parsed": opl.parse_all(),
    "files": pdftext.corpus_files(),
}
R = M.compute(CTX)
TAGS = [
    "CT-7801",
    "DC-3401A",
    "EA-5601",
    "FA-8901",
    "GA-1201A",
    "KC-4501",
    "LV-6701",
    "YD-2301",
]


def test_dates_window_and_gaps():
    d = R["dates"]
    assert (d["dated"], d["undated"]) == (56, [])
    assert (d["first"], d["last"], d["span_days"]) == ("2026-03-22", "2026-07-01", 101)
    assert (
        len(d["sorted"]) == 56
        and d["sorted"] == sorted(d["sorted"])
        and d["sorted"][0] == d["first"]
    )
    assert (d["gaps"]["median"], d["gaps"]["mode"], d["gaps"]["mode_count"]) == (
        1,
        1,
        28,
    )
    assert d["gaps"]["distribution"] == {
        "1": 28,
        "2": 12,
        "3": 11,
        "4": 4,
    }  # CF-03 verifier's distribution


def test_cadence_per_set():
    d = R["dates"]
    assert sorted(d["cadence"]) == TAGS and all(
        v == [4, 4, 4, 4, 4, 4] for v in d["cadence"].values()
    )
    assert d["set_start"] == {
        "CT-7801": "2026-05-27",
        "DC-3401A": "2026-04-13",
        "EA-5601": "2026-05-05",
        "FA-8901": "2026-06-07",
        "GA-1201A": "2026-03-22",
        "KC-4501": "2026-04-24",
        "LV-6701": "2026-05-16",
        "YD-2301": "2026-04-02",
    }


def test_dates_against_workbook():
    d = R["dates"]
    assert (d["last_breakdown_report"], d["gap_to_first_lesson_days"]) == (
        "2025-11-28",
        114,
    )
    assert d["workbook_window"] == {
        "report_first": "2024-06-04",
        "report_last": "2025-12-06",
        "completion_last": "2025-12-10",
    }
    assert (
        d["any_overlap"] is False
    )  # every lesson is dated after the last record closed


def test_latency_pairs():
    L = R["latency"]
    assert [(p["wo"], p["opl"], p["days"]) for p in L["pairs"]] == [
        ("WO-240037", "OPL-YD-2301-04", 210),
        ("WO-240062", "OPL-DC-3401A-07", 220),
        ("WO-240113", "OPL-EA-5601-05", 442),
        ("WO-240135", "OPL-LV-6701-03", 503),
        ("WO-240110", "OPL-EA-5601-06", 528),
        ("WO-240195", "OPL-FA-8901-07", 730),
    ]
    assert (L["days"], L["median_days"]) == ([210, 220, 442, 503, 528, 730], 472.5)
    ea = next(
        p for p in L["pairs"] if p["wo"] == "WO-240110"
    )  # DP-12: the corrective fouling event, not WO-240119
    assert (ea["failure_date"], ea["date_of_sharing"]) == ("2024-12-13", "2026-05-25")
    assert all(p["tag"] == "-".join(p["opl"].split("-")[1:3]) for p in L["pairs"])
    assert (
        "matched by recorded mechanism" in L["pairing_basis"]
        and "adjudicated" in L["pairing_basis"]
    )


def test_lead_time():
    t = R["lead_time"]
    assert (
        t["n"],
        t["median_h"],
        t["ge24_n"],
        t["ge24_pct"],
        t["min_h"],
        t["max_h"],
    ) == (211, 34.0, 136, 64.5, 1.0, 72.0)
    assert t["by_work_type"] == {
        "Calibration": 34.0,
        "Corrective": 35.0,
        "Inspection": 32.5,
        "Overhaul": 55.0,
        "Predictive": 34.0,
        "Preventive": 32.5,
    }


def test_lessons_registry_and_counts():
    s = R["lessons"]
    reg = s["registry"]
    assert s["n"] == len(reg) == 56 and [r["opl_id"] for r in reg] == sorted(
        r["opl_id"] for r in reg
    )
    assert all(tuple(r) == M.REGISTRY_FIELDS for r in reg)
    assert all(
        r["date_of_sharing"]
        and r["hazard_note"]
        and r["approved_by_id"]
        and r["reviewed_by_id"]
        for r in reg
    )
    assert s["classification"] == {
        "Basic Knowledge": 24,
        "Improvement": 20,
        "Trouble Case": 12,
    }
    assert s["discipline"] == {
        "Instrument": 12,
        "Mechanical": 23,
        "Process / Operations": 21,
    }
    assert s["approvers"] == {"EMP-0901": 28, "EMP-0912": 28}
    assert s["reviewers_per_set"] == {
        "CT-7801": ["EMP-1113"],
        "DC-3401A": ["EMP-1102"],
        "EA-5601": ["EMP-1124"],
        "FA-8901": ["EMP-1124"],
        "GA-1201A": ["EMP-1113"],
        "KC-4501": ["EMP-1113"],
        "LV-6701": ["EMP-1102"],
        "YD-2301": ["EMP-1124"],
    }
    assert (s["foreign_footer_lessons"], s["no_crossref_line_lessons"]) == (28, 5)
    assert all(
        r["foreign_crossref_tags"] == ["GA-1201A"]
        for r in reg
        if r["foreign_crossref_tags"]
    )


def test_json_and_pure():
    a = json.dumps(R, sort_keys=True)
    assert a == json.dumps(M.compute(CTX), sort_keys=True)
    assert (
        "/Users/" not in a and "2026-08-" not in a
    )  # no absolute paths, no run timestamps
