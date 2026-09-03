#!/usr/bin/env python3
"""The one harness CLI: writes packages/fixtures.json, the only source of every number in the PRD (plan Task 1.7; closes
HN-12, HN-14, HN-11, LD-03; Addendum D10, P4).

    python3 -m harness.analyze_corpus [--corpus DIR] [--out packages/fixtures.json] [--t 0.62] [--legacy-window | --no-legacy-window]
    python3 harness/analyze_corpus.py ...      (same; the repository root is put on sys.path)

Builds ctx = {rows, pops, opl, parsed, files} from the foundation modules, then assembles: golden (the golden-set size read
off golden/cases.yaml by tools.computed.golden_block), inventory, workbook, populations, the keys returned by
coverage/dates/integrity/master.compute, debt, meta. Text comes only from harness.pdftext
(`pdftotext -raw`, canonical form). The JSON is written with sort_keys=True so two runs on the same corpus are
byte-identical; nothing inside is a timestamp, a path or a typed number.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # `python3 harness/analyze_corpus.py`

HARNESS_VERSION = "1.1.0"
RECIPE = "LD-07 revised"


def extractor_version():
    """First line of `pdftotext -v` (poppler prints it on stderr), e.g. 'pdftotext version 26.02.0' (D10: poppler >= 24)."""
    cp = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    return (cp.stderr or cp.stdout).strip().splitlines()[0]


def inventory(files, pdftext):
    """Deterministic inventory over harness.pdftext.corpus_files (HN-11: junk and AppleDouble files skipped, 98 not 101)."""
    return {
        "files": len(files),
        "by_class": dict(sorted(Counter(pdftext.doc_class(f) for f in files).items())),
        "by_extension": dict(sorted(Counter(os.path.splitext(f)[1].lower() for f in files).items())),
        "opl_count": sum(1 for f in files if pdftext.doc_class(f) == "opl"),
        "corpus_sha256": pdftext.corpus_sha256(files),
        "extractor": "pdftotext -raw (" + extractor_version() + ")",
    }


DEMO_WOS = ("WO-240007",)  # the loop demo's own record: its downtime and cost are quoted per work order, not per asset


def demo_wo_block(rows):
    """Per-work-order downtime and cost for the records the document quotes by work-order number.

    The asset-level aggregates (`equipment_master[...].unplanned_breakdown_h`, `debt.per_asset[...].C`) agree with
    WO-240007's own row only because GA-1201A happens to carry one flagged breakdown and one empty-closeout uncovered
    row. A sentence that says "of WO-240007" reads its value from here instead, so the agreement is not load-bearing.
    """
    by_id = {w["WO_Number"]: w for w in rows}
    return {wo: {"downtime_h": by_id[wo]["Downtime_Hours"] or 0.0,
                 "cost_idr": by_id[wo]["Total_Cost_IDR"] or 0,
                 "tag": by_id[wo]["Equipment_Tag"]}
            for wo in DEMO_WOS if wo in by_id}


def workbook_block(rows, pops):
    """Workbook totals that every chapter quotes (211 rows, 31 flagged breakdowns, 434.0 h, IDR 413,345,000 / 537,770,000,
    520.5 labour hours), the categorical counts, the 26 incomplete closeouts (F3) and the record window (HN-20).

    `window.days` is report_first to report_last, the span the value model of Chapter 23 counts shifts over."""
    bd = [w for w in rows if w["Breakdown"] == "Yes"]
    inc = [w for w in rows if not w["closeout_complete"]]

    def kind(pop):
        return {"count": len(pop), "downtime_h": sum(w["Downtime_Hours"] or 0.0 for w in pop),
                "cost_idr": sum(w["Total_Cost_IDR"] or 0 for w in pop)}

    def counts(col):
        return dict(sorted(Counter(w[col] for w in rows).items()))

    return {
        "rows": len(rows),
        "breakdowns": len(bd),
        "downtime_h": sum(w["Downtime_Hours"] or 0.0 for w in rows),
        "breakdown_cost_idr": sum(w["Total_Cost_IDR"] or 0 for w in bd),
        "all_cost_idr": sum(w["Total_Cost_IDR"] or 0 for w in rows),
        "labor_h": sum(w["Labor_Hours"] or 0.0 for w in rows),
        "breakdown_kinds": {"unplanned": kind(pops["unplanned_breakdowns"]), "planned_flagged": kind(pops["planned_flagged"])},
        "work_types": counts("Work_Type"),
        "disciplines": counts("Discipline"),
        "priorities": counts("Priority"),
        "criticality_counts": counts("Criticality"),
        "status": counts("Status"),
        "incomplete": {"count": len(inc), "pct": round(100 * len(inc) / len(rows), 1),
                       "by_work_type": dict(sorted(Counter(w["Work_Type"] for w in inc).items())),
                       "ids": sorted(w["WO_Number"] for w in inc)},
        "window": {
            "report_first": min(w["Report_Date"] for w in rows).date().isoformat(),
            "report_last": max(w["Report_Date"] for w in rows).date().isoformat(),
            "completion_last": max(w["Completion_Date"] for w in rows).date().isoformat(),
            "days": (max(w["Report_Date"] for w in rows).date() - min(w["Report_Date"] for w in rows).date()).days,
        },
    }


def build(t=0.62, legacy_window=True):
    """The whole fixture as a dict. Imports happen here so that --corpus (CASE1_CORPUS) is honoured by harness.config."""
    from harness import coverage, dates, debt, integrity, master, opl, pdftext, workbook
    from tools.computed import golden_block   # golden/cases.yaml is repository data, not corpus text (WS4 Task 4.1)

    files = pdftext.corpus_files()
    rows = workbook.load()
    pops = workbook.populations(rows)
    texts = pdftext.opl_texts()
    ctx = {"rows": rows, "pops": pops, "opl": texts, "parsed": opl.parse_all(texts), "files": files,
           "t": t, "legacy_window": legacy_window}
    fx = {
        "golden": golden_block(),
        "inventory": inventory(files, pdftext),
        "workbook": workbook_block(rows, pops),
        "demo_wo": demo_wo_block(rows),
        "populations": {name: workbook.ids(pop) for name, pop in pops.items()},
    }
    for part in (coverage.compute(ctx), dates.compute(ctx), {"integrity": integrity.compute(ctx, write_aliases=True)}, master.compute(ctx)):
        clash = set(part) & set(fx)
        if clash:
            raise SystemExit(f"fixture key collision: {sorted(clash)}")
        fx.update(part)
    fx["debt"] = debt.compute(dict(ctx, coverage=fx["coverage"], equipment_master=fx["equipment_master"], families=fx["families"]))
    fx["meta"] = {
        "harness_version": HARNESS_VERSION,
        "t": t,
        "recipe": RECIPE,
        "legacy_window": legacy_window,
        "note": "all numbers computed by this harness; nothing hand-typed",
    }
    return fx


def headline(fx):
    """One line per verification command of the plan (WS1): the deck numbers as the fixture carries them."""
    t = fx["meta"]["t"]
    g = next(r for r in fx["coverage"]["generous"]["unplanned_failure"] if r["t"] == t)
    s = next(r for r in fx["coverage"]["strict"]["unplanned_failure"] if r["t"] == t)
    b = fx["coverage_bands"]["unplanned_failure"]
    return (f"generous t={t}: {g['uncovered']}/{g['n']} uncovered ({g['pct']} %), {g['unplanned_bd']} unplanned breakdowns, "
            f"{g['downtime_h']} h, IDR {g['cost_idr']:,}\n"
            f"strict   t={t}: {s['uncovered']}/{s['n']} uncovered ({s['pct']} %), {s['unplanned_bd']} unplanned breakdowns, "
            f"{s['downtime_h']} h, IDR {s['cost_idr']:,}\n"
            f"bands: none {b['none']} / table_only {b['table_only']} / taught {b['taught']}; "
            f"integrity total {fx['integrity']['total']}; debt top: {fx['debt']['ranking'][0]['tag']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", help="Case 1 corpus root (default: $CASE1_CORPUS or harness.config.CORPUS)")
    ap.add_argument("--out", help="output path (default: packages/fixtures.json)")
    ap.add_argument("--t", type=float, default=0.62, help="coverage threshold for the derived tables (default 0.62)")
    ap.add_argument("--legacy-window", action=argparse.BooleanOptionalAction, default=True,
                    help="run the v1.0 scorer (about 13 s, evidence only); --no-legacy-window writes legacy = null")
    a = ap.parse_args(argv)
    if a.corpus:
        os.environ["CASE1_CORPUS"] = a.corpus
    from harness.config import PACKAGES
    out = a.out or os.path.join(PACKAGES, "fixtures.json")
    fx = build(a.t, a.legacy_window)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fx, f, sort_keys=True, indent=1, ensure_ascii=False)
        f.write("\n")
    print(headline(fx))
    print(f"wrote {os.path.relpath(out)} ({os.path.getsize(out):,} bytes; corpus {fx['inventory']['corpus_sha256'][:16]})")


if __name__ == "__main__":
    main()
