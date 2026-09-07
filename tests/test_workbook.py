from collections import Counter

from harness import workbook as W

ROWS = W.load()


def test_rows_and_incomplete():
    assert len(ROWS) == 211
    inc = [w for w in ROWS if not w["closeout_complete"]]
    assert len(inc) == 26
    assert Counter(w["Work_Type"] for w in inc) == {"Corrective": 20, "Overhaul": 3, "Preventive": 2, "Calibration": 1}
    for w in inc:  # narrative fields are present (F3 correction, EC-05)
        assert all(w[c] for c in W.NARR)
    em = [w for w in ROWS if w["Priority"] == "Emergency"]
    assert sorted(w["WO_Number"] for w in em) == ["WO-240002", "WO-240032", "WO-240083"]
    assert all(not w["closeout_complete"] for w in em)  # Addendum A1


def test_populations():
    P = W.populations(ROWS)
    assert (len(P["failure"]), len(P["unplanned_failure"]), len(P["planned_flagged"]), len(P["unplanned_breakdowns"])) == (66, 57, 8, 23)
    assert W.ids(P["planned_flagged"]) == ["WO-240060", "WO-240065", "WO-240116", "WO-240117", "WO-240119", "WO-240189", "WO-240194", "WO-240197"]
    assert sum(w["Downtime_Hours"] for w in P["planned_flagged"]) == 164.0
    assert sum(w["Total_Cost_IDR"] for w in P["planned_flagged"]) == 69_270_000
    assert sum(w["Downtime_Hours"] for w in P["unplanned_breakdowns"]) == 270.0
    assert sum(w["Total_Cost_IDR"] for w in P["unplanned_breakdowns"]) == 344_075_000
    assert Counter(w["Work_Type"] for w in P["unplanned_failure"]) == {"Corrective": 53, "Overhaul": 4}


def test_totals():
    assert sum(w["Downtime_Hours"] or 0 for w in ROWS) == 434.0
    assert sum(w["Total_Cost_IDR"] or 0 for w in ROWS) == 537_770_000
    assert sum(w["Labor_Hours"] or 0 for w in ROWS) == 520.5
    bd = [w for w in ROWS if w["Breakdown"] == "Yes"]
    assert (len(bd), sum(w["Total_Cost_IDR"] for w in bd)) == (31, 413_345_000)
