#!/usr/bin/env python3
"""The one harness CLI: writes packages/fixtures.json, the only source of every number in the PRD (plan Task 1.7; closes
HN-12, HN-14, HN-11, LD-03; Addendum D10, P4), and rewrites the contract-shaped P&ID sidecars from their transcripts.

    python3 -m harness.analyze_corpus [--corpus DIR] [--out packages/fixtures.json] [--t 0.62] [--legacy-window | --no-legacy-window]
    python3 -m harness.analyze_corpus --write-sidecars          (packages/pid_sidecars/set_0n.json from set_0n.transcript.json)
    python3 harness/analyze_corpus.py ...      (same; the repository root is put on sys.path)

Builds ctx = {rows, pops, opl, parsed, files} from the foundation modules, then assembles: golden (the golden-set size read
off golden/cases.yaml by tools.computed.golden_block), inventory, workbook, populations, the keys returned by
coverage/dates/integrity/master.compute, debt, meta, and finally `registry`, the projection of the blueprint 10.5 fixture key
registry over those parts. Text comes only from harness.pdftext (`pdftotext -raw`, canonical form). The JSON is written with
sort_keys=True so two runs on the same corpus are byte-identical; nothing inside is a timestamp, a path or a typed number.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # `python3 harness/analyze_corpus.py`

HARNESS_VERSION = "1.1.0"
RECIPE = "LD-07 revised"
CANONICAL_FORM_VERSION = "1"  # blueprint 9.1 Manifest.canonical_form_version: harness.pdftext.canonical is form 1
# The frozen recipe as source (blueprint 9.5): the tokeniser, window and layers live in coverage.py, the strict-layer
# composition in opl.py; method.recipe_sha256 is the digest over both files' bytes, so a change to either moves the fixture.
RECIPE_SOURCES = ("harness/coverage.py", "harness/opl.py")
# Blueprint 10.5 `demo`: the loop demo's records. Identifiers, not numbers; `registry` refuses to write them unless the
# analysis agrees (primary and backup uncovered in both layers, contrast covered generous and uncovered strict).
DEMO = {"primary_wo": "WO-240007", "backup_wo": "WO-240039", "contrast_wo": "WO-240060"}
DEMO_WOS = (
    "WO-240007",
)  # the loop demo's own record: its downtime and cost are quoted per work order, not per asset
FIELD_NAMES = {
    "Problem_Description": "problem_description",
    "Root_Cause": "root_cause",
    "Corrective_Action": "corrective_action",
}
PROOF_CLASS_NAMES = {
    "sis_proof_test": "sis_proof_test",
    "sil_logic_proof_test": "sil_logic_test",
    "calibration_proof_test": "calibration_proof_test",
    "psv_statutory_test": "statutory_relief_test",
}
DEBT_COEFFICIENT_NAMES = {
    "D": "a",
    "C": "b",
    "k": "c",
    "r": "d",
}  # 9.5: debt = a D/Dmax + b C/Cmax + c k + d r
# ADR-007 (blueprint): family membership the prior harness classified carries basis agent_classification, pending review.
FAMILY_PROVENANCE = {"basis": "agent_classification", "review_status": "pending"}
DS_SERVICE = re.compile(r"SERVICE (.+?) DESIGN & MECHANICAL")
SIDECARS = "pid_sidecars"


def extractor_version():
    """First line of `pdftotext -v` (poppler prints it on stderr), e.g. 'pdftotext version 26.02.0' (D10: poppler >= 24)."""
    cp = subprocess.run(
        ["pdftotext", "-v"], capture_output=True, text=True, check=False
    )
    return (cp.stderr or cp.stdout).strip().splitlines()[0]


def share(n, d):
    """A 10.5 `share`: the 1-decimal percentage the surfaces print, divided by 100 (0.246 for 14 of 57), so tools/fx.py's
    share1 gives back exactly that percentage and the fixture's older `pct` twin never disagrees with it."""
    return round(round(100 * n / d, 1) / 100, 4) if d else 0.0


def inventory(files, pdftext):
    """Deterministic inventory over harness.pdftext.corpus_files (HN-11: junk and AppleDouble files skipped, 98 not 101)."""
    return {
        "files": len(files),
        "files_total": len(files),
        "by_class": dict(sorted(Counter(pdftext.doc_class(f) for f in files).items())),
        "by_extension": dict(
            sorted(Counter(os.path.splitext(f)[1].lower() for f in files).items())
        ),
        "opl_count": sum(1 for f in files if pdftext.doc_class(f) == "opl"),
        "corpus_sha256": pdftext.corpus_sha256(files),
        "extractor": "pdftotext -raw (" + extractor_version() + ")",
        "canonical_form_version": CANONICAL_FORM_VERSION,
    }


def demo_wo_block(rows):
    """Per-work-order downtime and cost for the records the document quotes by work-order number.

    The asset-level aggregates (`equipment_master[...].unplanned_breakdown_h`, `debt.per_asset[...].C`) agree with
    WO-240007's own row only because GA-1201A happens to carry one flagged breakdown and one empty-closeout uncovered
    row. A sentence that says "of WO-240007" reads its value from here instead, so the agreement is not load-bearing.
    """
    by_id = {w["WO_Number"]: w for w in rows}
    return {
        wo: {
            "downtime_h": by_id[wo]["Downtime_Hours"] or 0.0,
            "cost_idr": by_id[wo]["Total_Cost_IDR"] or 0,
            "tag": by_id[wo]["Equipment_Tag"],
        }
        for wo in DEMO_WOS
        if wo in by_id
    }


def workbook_block(rows, pops):
    """Workbook totals that every chapter quotes (211 rows, 31 flagged breakdowns, 434.0 h, IDR 413,345,000 / 537,770,000,
    520.5 labour hours), the categorical counts, the 26 incomplete closeouts (F3) and the record window (HN-20), plus the
    10.5 spellings of the same values (reported_first, breakdown_flagged, all_labor_hours, incomplete.rows, ...).

    `window.days` is report_first to report_last, the span the value model of Chapter 23 counts shifts over."""
    bd = [w for w in rows if w["Breakdown"] == "Yes"]
    inc = [w for w in rows if not w["closeout_complete"]]

    def kind(pop):
        hours, cost = (
            sum(w["Downtime_Hours"] or 0.0 for w in pop),
            sum(w["Total_Cost_IDR"] or 0 for w in pop),
        )
        return {
            "count": len(pop),
            "rows": len(pop),
            "downtime_h": hours,
            "hours": hours,
            "cost_idr": cost,
        }

    def counts(col):
        return dict(sorted(Counter(w[col] for w in rows).items()))

    first, last = (
        min(w["Report_Date"] for w in rows).date(),
        max(w["Report_Date"] for w in rows).date(),
    )
    completed = max(w["Completion_Date"] for w in rows).date()
    return {
        "rows": len(rows),
        "breakdowns": len(bd),
        "downtime_h": sum(w["Downtime_Hours"] or 0.0 for w in rows),
        "breakdown_cost_idr": sum(w["Total_Cost_IDR"] or 0 for w in bd),
        "breakdown_flagged": {
            k: v for k, v in kind(bd).items() if k in ("rows", "hours", "cost_idr")
        },
        "all_cost_idr": sum(w["Total_Cost_IDR"] or 0 for w in rows),
        "labor_h": sum(w["Labor_Hours"] or 0.0 for w in rows),
        "all_labor_hours": sum(w["Labor_Hours"] or 0.0 for w in rows),
        "breakdown_kinds": {
            "unplanned": kind(pops["unplanned_breakdowns"]),
            "planned_flagged": kind(pops["planned_flagged"]),
        },
        "work_types": counts("Work_Type"),
        "disciplines": counts("Discipline"),
        "discipline_counts": counts("Discipline"),
        "priorities": counts("Priority"),
        "criticality_counts": counts("Criticality"),
        "status": counts("Status"),
        "incomplete": {
            "count": len(inc),
            "rows": len(inc),
            "pct": round(100 * len(inc) / len(rows), 1),
            "share": share(len(inc), len(rows)),
            "by_work_type": dict(sorted(Counter(w["Work_Type"] for w in inc).items())),
            "emergency_rows": sum(1 for w in inc if w["Priority"] == "Emergency"),
            "ids": sorted(w["WO_Number"] for w in inc),
        },
        "reported_first": first.isoformat(),
        "reported_last": last.isoformat(),
        "completed_last": completed.isoformat(),
        "window": {
            "report_first": first.isoformat(),
            "report_last": last.isoformat(),
            "completion_last": completed.isoformat(),
            "days": (last - first).days,
        },
    }


def recipe_sha256(root):
    h = hashlib.sha256()
    for rel in RECIPE_SOURCES:
        with open(os.path.join(root, rel), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def registry(fx, ctx, root):
    """The blueprint 10.5 fixture key registry projected over the computed parts (the harness may add keys and never
    rename one). Every value is a re-spelling or a re-aggregation of a value a module computed; nothing is typed. Where
    10.5 registers a path an older key already used with another shape (populations, families.r_by_tag, chains.links,
    debt.coefficients, personnel.people, method.strict_sections, method.labels_status), the registered path takes the
    contract's shape and the older content moves to a sibling key (population_ids, r_detail, link_list,
    coefficients_by_factor, roster, strict_section_headings, labels_note)."""
    from harness import coverage, opl
    from harness.pdftext import class_texts, must_match

    t = ctx["t"]
    m = fx["method"]
    m["recipe_sha256"] = recipe_sha256(root)
    m["recipe_sha256_of"] = (
        "sha256 over the bytes of " + " and ".join(RECIPE_SOURCES) + ", in that order"
    )
    m["threshold"] = m["t"]
    m["min_content_words"] = coverage.MIN_FIELD_TOKENS
    m["comparison"] = "uncovered when score <= threshold"
    m["strict_section_headings"] = m["strict_sections"]
    m["strict_sections"] = [
        (x.group(1) if (x := re.match(r"(\d+)\.", h)) else "header")
        for h in m["strict_section_headings"]
    ]
    m["strict_cut_marker"] = opl.PAGE_FOOTER
    m["labels_note"] = m["labels_status"]
    m["labels_status"] = (
        "human_adjudicated" if fx["labelled"] else "machine_drafted_pending_human"
    )

    lt = fx["lead_time"]
    fx["workbook"]["lead_time"] = {
        "median_h": lt["median_h"],
        "at_least_24h": lt["ge24_n"],
        "share": share(lt["ge24_n"], lt["n"]),
        "min_h": lt["min_h"],
        "max_h": lt["max_h"],
    }

    fx["population_ids"] = fx["populations"]
    fx["populations"] = {k: len(v) for k, v in fx["population_ids"].items()}

    for layer in ("generous", "strict"):
        for rows in fx["coverage"][layer].values():
            for r in rows:
                r["share"], r["breakdowns"] = (
                    share(r["uncovered"], r["n"]),
                    r["unplanned_bd"],
                )
    b = fx["coverage_bands"]["unplanned_failure"]
    fx["coverage"]["bands"] = {
        "unplanned_failure": [
            {
                "t": b["t"],
                "no_lesson": b["none"],
                "copied_row_only": b["table_only"],
                "taught": b["taught"],
            }
        ]
    }
    for layers in fx["coverage_scores"].values():
        for sc in layers.values():
            unit = sc["unit"]
            sc["best_ratio"] = sc["score"]
            sc["matched_field"] = FIELD_NAMES[unit[0]] if unit else None
            sc["matched_lesson"] = unit[1] if unit else None

    lab, agr = (
        (fx["labelled"], fx["labels_agreement"])
        if fx["labelled"]
        else (fx["labelled_draft"], fx["labels_agreement_draft"])
    )
    if not lab:
        raise SystemExit(
            "coverage_labels needs packages/coverage_labels.json or packages/coverage_labels.draft.json"
        )
    kap = agr.get("kappa") or {}
    fx["coverage_labels"] = {
        "status": m["labels_status"],
        "uncovered_ids": lab["uncovered_ids"],
        "uncovered_count": lab["uncovered"],
        "share": share(lab["uncovered"], lab["n"]),
        "breakdowns": lab["unplanned_bd"],
        "downtime_h": lab["downtime_h"],
        "cost_idr": lab["cost_idr"],
        "kappa_covered": kap.get("covered"),
        "kappa_taught": kap.get("taught"),
        "proxy_agreement": {
            name: {k: agr[name][k] for k in ("precision", "recall", "fp", "fn")}
            for name in ("generous", "strict")
        },
    }

    v = fx["verbatim"]
    g = v["generous"]["by_field"]
    v.update(
        problem_description=g["Problem_Description"],
        root_cause=g["Root_Cause"],
        corrective_action=g["Corrective_Action"],
        any_field=v["generous"]["any"],
        strict_any_field=v["strict"]["any"],
    )

    d = fx["dates"]
    d.update(
        parsed=d["dated"],
        window_days=d["span_days"],
        median_gap_d=d["gaps"]["median"],
        mode_gap_d=d["gaps"]["mode"],
        mode_count=d["gaps"]["mode_count"],
        within_set_gap_d=d["cadence_days"],
        days_after_last_breakdown=d["gap_to_first_lesson_days"],
    )

    for p in fx["latency"]["pairs"]:
        p.update(wo_number=p["wo"], opl_id=p["opl"], report_date=p["failure_date"])
    fx["latency"]["median_d"] = fx["latency"]["median_days"]

    i = fx["integrity"]
    rules = {k: x for k, x in i.items() if re.fullmatch(r"CD-\d+", k)}
    i["rules"] = {k: x["count"] for k, x in rules.items() if not x["observation_only"]}
    i["observations"] = {
        k: x["count"] for k, x in rules.items() if x["observation_only"]
    }

    f = fx["families"]
    root_cause = {w["WO_Number"]: str(w["Root_Cause"] or "") for w in ctx["rows"]}
    f["list"] = [
        {
            "id": f"FF-{n:02d}",
            "label": x["family"],
            **FAMILY_PROVENANCE,
            "members": [
                {"wo_number": w, "recorded_root_cause": root_cause[w]}
                for w in x["member_wos"]
            ],
        }
        for n, x in enumerate(f["families"], 1)
    ]
    f["r_detail"] = f["r_by_tag"]
    f["r_by_tag"] = {tag: x["r"] for tag, x in f["r_detail"].items()}

    c = fx["chains"]
    c["link_list"], c["links"] = c["links"], c["total"]

    de = fx["debt"]
    de["coefficients_by_factor"] = de["coefficients"]
    de["coefficients"] = {
        DEBT_COEFFICIENT_NAMES[k]: x
        for k, x in de["coefficients_by_factor"].items()
        if k in DEBT_COEFFICIENT_NAMES
    }
    de["coefficients"]["basis"] = "ASSUMPTION"
    rank = {r["tag"]: r["rank"] for r in de["ranking"]}
    for p in de["per_asset"]:
        p.update(
            rank=rank[p["tag"]],
            uncovered_wo_numbers=p["uncovered_ids"],
            D_h=p["D"],
            C_idr=p["C"],
        )

    pt = fx["proof_tests"]
    pt["by_class"] = {
        PROOF_CLASS_NAMES[k]: x["count"] for k, x in pt["classes"].items()
    }

    service = {
        tag: must_match(DS_SERVICE.search(text), f"SERVICE field of {tag}").group(1)
        for tag, text in class_texts("datasheet").items()
    }
    for e in fx["equipment_master"]:
        e.update(
            service=service[e["tag"]],
            interlock_ref=fx["interlock_rows"][e["tag"]]["header"]["logic_no_text"],
            criticality=e["criticality_datasheet"],
            work_orders=e["wos"],
            failure_rows=e["unplanned_failure_rows"],  # C.1 "Unplanned-failure rows" (sums to 57), the 10.4 item 1 target
            breakdown_rows=e["breakdowns_flagged"],
            planned_rows=e["planned_flagged_rows"],
            unplanned_rows=e["unplanned_breakdowns"],
            unplanned_h=e["unplanned_breakdown_h"],
            flagged_h=e["breakdown_h_flagged"],
            breakdown_cost_idr=e["breakdown_cost_flagged_idr"],
        )

    pe = fx["personnel"]
    pe["roster"] = pe["people"]
    pe["people"] = len(pe["roster"])
    pe["classes"] = dict(
        sorted(
            Counter(x["role_class"] or "unknown" for x in pe["roster"].values()).items()
        )
    )
    pe["dual_role_supervisors"] = len(pe["opl_reviewers_are_wo_approvers"])
    pe["managers_not_in_workbook"] = len(pe["opl_managers_absent_from_workbook"])

    if fx["legacy"]:
        lg = next(r for r in fx["legacy"]["all"] if r["t"] == t)
        fx["legacy"].update(headline_all=lg["uncovered"], note="evidence only")

    sc = fx["coverage_scores"]
    for k in ("primary_wo", "backup_wo"):
        if not all(
            sc[DEMO[k]][layer]["score"] <= t for layer in ("generous", "strict")
        ):
            raise SystemExit(
                f"demo.{k} {DEMO[k]} is not uncovered in both layers at t = {t}"
            )
    cw = sc[DEMO["contrast_wo"]]
    if not (cw["generous"]["score"] > t >= cw["strict"]["score"]):
        raise SystemExit(
            f"demo.contrast_wo {DEMO['contrast_wo']} is not covered generous and uncovered strict at t = {t}"
        )
    fx["demo"] = dict(DEMO)
    return fx


def build(t=0.62, legacy_window=True):
    """The whole fixture as a dict. Imports happen here so that --corpus (CASE1_CORPUS) is honoured by harness.config."""
    from harness import coverage, dates, debt, integrity, master, opl, pdftext, workbook
    from harness.config import ROOT
    from tools.computed import (
        golden_block,
    )  # golden/cases.yaml is repository data, not corpus text (WS4 Task 4.1)

    files = pdftext.corpus_files()
    rows = workbook.load()
    pops = workbook.populations(rows)
    texts = pdftext.opl_texts()
    ctx = {
        "rows": rows,
        "pops": pops,
        "opl": texts,
        "parsed": opl.parse_all(texts),
        "files": files,
        "t": t,
        "legacy_window": legacy_window,
    }
    fx = {
        "golden": golden_block(),
        "inventory": inventory(files, pdftext),
        "workbook": workbook_block(rows, pops),
        "demo_wo": demo_wo_block(rows),
        "populations": {name: workbook.ids(pop) for name, pop in pops.items()},
    }
    for part in (
        coverage.compute(ctx),
        dates.compute(ctx),
        {"integrity": integrity.compute(ctx, write_aliases=True)},
        master.compute(ctx),
    ):
        clash = set(part) & set(fx)
        if clash:
            raise SystemExit(f"fixture key collision: {sorted(clash)}")
        fx.update(part)
    fx["debt"] = debt.compute(
        dict(
            ctx,
            coverage=fx["coverage"],
            equipment_master=fx["equipment_master"],
            families=fx["families"],
        )
    )
    fx["meta"] = {
        "harness_version": HARNESS_VERSION,
        "t": t,
        "recipe": RECIPE,
        "legacy_window": legacy_window,
        "note": "all numbers computed by this harness; nothing hand-typed",
    }
    return registry(fx, ctx, ROOT)


def headline(fx):
    """One line per verification command of the plan (WS1): the deck numbers as the fixture carries them."""
    t = fx["meta"]["t"]
    g = next(r for r in fx["coverage"]["generous"]["unplanned_failure"] if r["t"] == t)
    s = next(r for r in fx["coverage"]["strict"]["unplanned_failure"] if r["t"] == t)
    b = fx["coverage_bands"]["unplanned_failure"]
    return (
        f"generous t={t}: {g['uncovered']}/{g['n']} uncovered ({g['pct']} %), {g['unplanned_bd']} unplanned breakdowns, "
        f"{g['downtime_h']} h, IDR {g['cost_idr']:,}\n"
        f"strict   t={t}: {s['uncovered']}/{s['n']} uncovered ({s['pct']} %), {s['unplanned_bd']} unplanned breakdowns, "
        f"{s['downtime_h']} h, IDR {s['cost_idr']:,}\n"
        f"bands: none {b['none']} / table_only {b['table_only']} / taught {b['taught']}; "
        f"integrity total {fx['integrity']['total']}; debt top: {fx['debt']['ranking'][0]['tag']}"
    )


def sidecar(t):
    """Blueprint 9.3 PidSidecar from an adopted transcript (packages/pid_sidecars/set_0n.transcript.json): every reading is
    carried verbatim under the contract's key; the hand point estimate (x, y) becomes x_frac, y_frac with a zero extent
    because no box was read; a note on an unbound instrument is its unbound_reason; the title box is the title-block cells
    joined with ' | ' (the transcript's own table convention) or the title line; provenance follows deviation D-12."""
    cells = t.get("title_block_as_drawn") or (
        [t["title_as_drawn"]] if t["title_as_drawn"] else []
    )
    hotspots = [
        {
            "id": f"set{t['set']:02d}-{n:03d}",
            "as_drawn_text": i["as_drawn_text"],
            "bound_tag": i["bound_tag"],
            "unbound_reason": (i.get("note") or None)
            if i["bound_tag"] is None
            else None,
            "role": i["role"],
            "drawn_setpoint": i["setpoint_as_drawn"],
            "foreign": i["foreign"],
            "x_frac": i["x"],
            "y_frac": i["y"],
            "w_frac": 0.0,
            "h_frac": 0.0,
        }
        for n, i in enumerate(t["instruments"], 1)
    ]
    p = t["provenance"]
    return {
        "set": t["set"],
        "document_id": t["file"],
        "title_box": " | ".join(cells),
        "reference_box": t["ref_dwg_as_drawn"] or "",
        "notes": t["notes_as_drawn"],
        "equipment_shown": t["equipment_shown"],
        "hotspots": hotspots,
        "defects": [{"rule": d["kind"], "detail": d["detail"]} for d in t["defects"]],
        "provenance": {
            "basis": p["basis"],
            "alias": p["by"],
            "date": p["date"],
            "reviewed_by": None,
            "reviewed_at": None,
            "review_status": p["review_status"],
        },
    }


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, sort_keys=True, indent=1, ensure_ascii=False)
        f.write("\n")


def write_sidecars(packages):
    """`--write-sidecars`: every packages/pid_sidecars/set_0n.transcript.json to its contract-shaped set_0n.json."""
    out = []
    for src in sorted(
        glob.glob(os.path.join(packages, SIDECARS, "set_*.transcript.json"))
    ):
        with open(src, encoding="utf-8") as f:
            transcript = json.load(f)
        dst = src.replace(".transcript.json", ".json")
        write_json(dst, sidecar(transcript))
        out.append(dst)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--corpus",
        help="Case 1 corpus root (default: $CASE1_CORPUS or harness.config.CORPUS)",
    )
    ap.add_argument("--out", help="output path (default: packages/fixtures.json)")
    ap.add_argument(
        "--t",
        type=float,
        default=0.62,
        help="coverage threshold for the derived tables (default 0.62)",
    )
    ap.add_argument(
        "--legacy-window",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run the v1.0 scorer (about 13 s, evidence only); --no-legacy-window writes legacy = null",
    )
    ap.add_argument(
        "--write-sidecars",
        action="store_true",
        help="rewrite packages/pid_sidecars/set_0n.json from set_0n.transcript.json (no corpus needed) and exit",
    )
    a = ap.parse_args(argv)
    if a.corpus:
        os.environ["CASE1_CORPUS"] = a.corpus
    from harness.config import PACKAGES

    if a.write_sidecars:
        for path in write_sidecars(PACKAGES):
            print("wrote", os.path.relpath(path))
        return
    out = a.out or os.path.join(PACKAGES, "fixtures.json")
    fx = build(a.t, a.legacy_window)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    write_json(out, fx)
    print(headline(fx))
    print(
        f"wrote {os.path.relpath(out)} ({os.path.getsize(out):,} bytes; corpus {fx['inventory']['corpus_sha256'][:16]})"
    )


if __name__ == "__main__":
    main()
