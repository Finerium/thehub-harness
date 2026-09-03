"""Lesson dates and cadence, failure-to-lesson latency, notification lead time, lesson registry (plan Task 1.4).

Every date comes from harness.opl.parse_all() (canonical `pdftotext -raw` text, D10) or from the typed workbook rows;
nothing is re-extracted here. Closes CF-03 (56 of 56 dates, median gap 1 d, mode 1 d x28, rigid 4-day cadence per set),
DP-12 (EA-5601 pair anchored on WO-240110, not the planned WO-240119), HN-V-03 (pairing basis stated), and pins the
HN-20 facts (lead time 34.0 h median, 64.5 % >= 24 h, range 1-72 h; workbook window; last breakdown 2025-11-28, 114 d).
"""
import datetime
import statistics
from collections import Counter

# Plan Task 1.4 PAIRS, DP-12 applied (WO-240110 replaces the planned WO-240119).
PAIRS = (
    ("YD-2301", "WO-240037", "OPL-YD-2301-04"),
    ("DC-3401A", "WO-240062", "OPL-DC-3401A-07"),
    ("EA-5601", "WO-240113", "OPL-EA-5601-05"),
    ("LV-6701", "WO-240135", "OPL-LV-6701-03"),
    ("EA-5601", "WO-240110", "OPL-EA-5601-06"),
    ("FA-8901", "WO-240195", "OPL-FA-8901-07"),
)
# Plan section 5.7 item 8 (HN-V-03), quoted verbatim.
PAIRING_BASIS = (
    "These pairs are matched by recorded mechanism, not by the lexical score of Chapter 19; WO-240037 is lexically "
    "uncovered because the lesson paraphrases, and WO-240062, WO-240135 and WO-240110 are covered only through the "
    "lesson's troubleshooting table; the labels file records the adjudicated status of every unplanned-failure record."
)
REGISTRY_FIELDS = (
    "opl_id", "tag", "title", "discipline", "area_unit", "related_interlock", "seq", "pid_ref", "classification",
    "date_of_sharing", "reviewed_by_id", "approved_by_id", "has_crossref_line", "foreign_crossref_tags", "hazard_note",
)


def _iso(d):
    return d.date().isoformat() if isinstance(d, datetime.datetime) else d.isoformat()


def _gaps(isodates):
    ds = sorted(datetime.date.fromisoformat(x) for x in isodates)
    return [(b - a).days for a, b in zip(ds, ds[1:])]


def dates(parsed, rows):
    """Date of Sharing statistics (CF-03) against the workbook window (HN-20).

    Rules: consecutive gaps are over the 56 dates sorted as one series; cadence is per set (tag); last breakdown is the
    latest Report_Date among Breakdown == Yes rows; `any_overlap` is true only if the first lesson is dated on or before
    the last date recorded in the workbook (max Completion_Date), i.e. whether the lesson campaign overlaps the record.
    """
    dated = {k: v["date_of_sharing"] for k, v in parsed.items() if v["date_of_sharing"]}
    series = sorted(dated.values())
    gaps = _gaps(series)
    mode, mode_n = Counter(gaps).most_common(1)[0]
    by_tag = {}
    for k, d in dated.items():
        by_tag.setdefault(parsed[k]["tag"], []).append(d)
    last_bd = max(w["Report_Date"] for w in rows if w["Breakdown"] == "Yes").date()
    first = datetime.date.fromisoformat(series[0])
    completion_last = max(w["Completion_Date"] for w in rows).date()
    return {
        "dated": len(dated),
        "undated": sorted(k for k in parsed if k not in dated),
        "first": series[0],
        "last": series[-1],
        "span_days": (datetime.date.fromisoformat(series[-1]) - first).days,
        "sorted": series,
        "gaps": {
            "median": statistics.median(gaps),
            "mode": mode,
            "mode_count": mode_n,
            "distribution": {str(g): n for g, n in sorted(Counter(gaps).items())},
        },
        "cadence": {t: _gaps(v) for t, v in sorted(by_tag.items())},
        # the one gap every set shares, or None if the sets ever disagree (so the prose claim cannot outlive the fact)
        "cadence_days": (lambda vs: vs.pop() if len(vs) == 1 else None)(
            {g for t, v in by_tag.items() for g in _gaps(v)}),
        "set_start": {t: min(v) for t, v in sorted(by_tag.items())},
        "last_breakdown_report": last_bd.isoformat(),
        "gap_to_first_lesson_days": (first - last_bd).days,
        "any_overlap": first <= completion_last,
        "workbook_window": {
            "report_first": _iso(min(w["Report_Date"] for w in rows)),
            "report_last": _iso(max(w["Report_Date"] for w in rows)),
            "completion_last": completion_last.isoformat(),
        },
    }


def latency(parsed, rows):
    """Failure-to-lesson latency for the six PAIRS (plan 5.7 item 8; DP-12): days = Date of Sharing - Report_Date."""
    by_wo = {w["WO_Number"]: w for w in rows}
    out = []
    for tag, wo, opl in PAIRS:
        w = by_wo[wo]
        if w["Equipment_Tag"] != tag or opl not in parsed:
            raise ValueError(f"latency pair does not match the corpus: {tag} {wo} {opl}")
        fd, ds = w["Report_Date"].date(), datetime.date.fromisoformat(parsed[opl]["date_of_sharing"])
        out.append({"tag": tag, "wo": wo, "failure_date": fd.isoformat(), "opl": opl,
                    "date_of_sharing": ds.isoformat(), "days": (ds - fd).days})
    out.sort(key=lambda p: (p["days"], p["wo"]))
    days = [p["days"] for p in out]
    return {"pairs": out, "days": days, "median_days": statistics.median(days), "pairing_basis": PAIRING_BASIS}


def lead_time(rows):
    """Notification lead time = Start_Date - Report_Date in hours over all rows (HN-20 pins: 34.0 h, 64.5 %, 1-72)."""
    hours = {w["WO_Number"]: (w["Start_Date"] - w["Report_Date"]).total_seconds() / 3600 for w in rows}
    xs = sorted(hours.values())
    ge24 = sum(1 for x in xs if x >= 24)
    by_type = {}
    for w in rows:
        by_type.setdefault(w["Work_Type"], []).append(hours[w["WO_Number"]])
    return {
        "n": len(xs),
        "median_h": statistics.median(xs),
        "ge24_n": ge24,
        "ge24_pct": round(100 * ge24 / len(xs), 1),
        "min_h": xs[0],
        "max_h": xs[-1],
        "by_work_type": {t: statistics.median(v) for t, v in sorted(by_type.items())},
    }


def lessons(parsed):
    """Registry of every lesson's header/footer fields (ids only, no names: A2/A4) with the CF-03/HN-08/CF-12 counts."""
    reg = [{f: parsed[k][f] for f in REGISTRY_FIELDS} for k in sorted(parsed)]
    reviewers = {}
    for r in reg:
        reviewers.setdefault(r["tag"], set()).add(r["reviewed_by_id"])
    return {
        "registry": reg,
        "n": len(reg),
        "classification": dict(sorted(Counter(r["classification"] for r in reg).items())),
        "discipline": dict(sorted(Counter(r["discipline"] for r in reg).items())),
        "approvers": dict(sorted(Counter(r["approved_by_id"] for r in reg).items())),
        "reviewers_per_set": {t: sorted(v) for t, v in sorted(reviewers.items())},
        "foreign_footer_lessons": sum(1 for r in reg if r["foreign_crossref_tags"]),
        "no_crossref_line_lessons": sum(1 for r in reg if not r["has_crossref_line"]),
    }


def compute(ctx):
    """Fixture keys dates, latency, lead_time, lessons from ctx = {rows, pops, opl, parsed, files}."""
    return {
        "dates": dates(ctx["parsed"], ctx["rows"]),
        "latency": latency(ctx["parsed"], ctx["rows"]),
        "lead_time": lead_time(ctx["rows"]),
        "lessons": lessons(ctx["parsed"]),
    }
