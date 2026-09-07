"""packages/fixtures.json as written by `make fixtures` (harness/analyze_corpus.py): headline structure and the cross-module
reconciliations every chapter relies on (plan WS1 verification; Addendum D1, D10, A1, P3).

Every expectation was observed in the fixture written on 2026-08-30 and cross-checked by a throwaway script outside the
package (scratchpad xcheck_fixtures.py) that imports nothing from harness: os.walk for the inventory, openpyxl for the
workbook block and populations, a fresh `pdftotext -raw` call plus regex for the datasheet criticality, families.json read
directly and the debt formula re-implemented from the plan text; zero mismatches. Values that moved from the plan's
interim proxies under -raw are asserted as observed (D10 re-freeze), not forced to the plan: strict 41 / 14 / 146.0 h /
IDR 198,418,000 after the P10b footer fix (the composed strict layer stops at the page watermark, so the copied
Corrective_Action cell in OPL-DC-3401A-01/-04 no longer teaches WO-240056), bands 14 / 27 / 16, CD-12 38, total 174, and
KC-4501 debt 0.5497 after PS-09 moved WO-240091 out of the bearing family into its own lubrication family.

Updated on 2026-09-05 for the blueprint 10.5 registry (harness/analyze_corpus.py::registry): the registered paths carry
the contract's shape and the older content sits under a sibling key (populations counts beside population_ids, rows and
hours beside count and downtime_h, debt.coefficients a to d beside coefficients_by_factor, r_by_tag a number beside
r_detail, labels_status an enum beside labels_note); every value is the one observed before.
"""

import json
import os

import pytest

from harness import debt, workbook
from harness.config import CORPUS, PACKAGES, ROOT

FIXTURES = os.path.join(PACKAGES, "fixtures.json")
assert os.path.exists(FIXTURES), (
    "packages/fixtures.json missing: run `make fixtures` first"
)
with open(FIXTURES, encoding="utf-8") as _f:
    TEXT = _f.read()
FX = json.loads(TEXT)
T = FX["meta"]["t"]
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
TOP_KEYS = {
    "chains",
    "coverage",
    "coverage_bands",
    "coverage_by_tag",
    "coverage_by_work_type",
    "coverage_scores",
    "datasheet_spot",
    "dates",
    "debt",
    "demo_wo",
    "equipment_master",
    "families",
    "golden",
    "integrity",
    "interlock_rows",
    "inventory",
    "labelled",
    "labelled_draft",
    "labels_agreement",
    "labels_agreement_draft",
    "latency",
    "lead_time",
    "legacy",
    "lessons",
    "meta",
    "method",
    "personnel",
    "populations",
    "proof_tests",
    "revision_spot",
    "verbatim",
    "workbook",
    "coverage_labels",
    "demo",
    "population_ids",
}  # the last three: 10.5 registry keys


def row(layer, pop, t=T):
    return next(r for r in FX["coverage"][layer][pop] if r["t"] == t)


def test_top_level_keys_and_meta():
    assert set(FX) == TOP_KEYS
    assert FX["meta"] == {
        "harness_version": "1.1.0",
        "t": 0.62,
        "recipe": "LD-07 revised",
        "legacy_window": True,
        "note": "all numbers computed by this harness; nothing hand-typed",
    }


FROZEN_EXTRACTOR = "pdftotext -raw (pdftotext version 26.02.0)"  # LD-11: the build every published figure descends from


def test_inventory():
    i = FX["inventory"]
    assert (i["files"], i["opl_count"]) == (98, 56)
    assert i["by_extension"] == {".pdf": 88, ".png": 8, ".pptx": 1, ".xlsx": 1}
    assert i["by_class"] == {
        "datasheet": 8,
        "ga_drawing": 8,
        "interlock": 8,
        "opl": 56,
        "organiser_note": 1,
        "pid": 8,
        "plot_plan": 8,
        "workbook": 1,
    }
    assert len(i["corpus_sha256"]) == 64 and int(i["corpus_sha256"], 16)
    # D10 / LD-11: the coverage figures are a function of this extractor's tokenisation, so the exact build the
    # fixture was frozen under is pinned, not a floor. A reader on a different poppler fails here rather than
    # silently reproducing a different 14: re-freeze deliberately (make fixtures) and update this constant.
    assert i["extractor"] == FROZEN_EXTRACTOR, (
        f"extractor is {i['extractor']}, the published figures were frozen under {FROZEN_EXTRACTOR}"
    )


def test_workbook_totals():
    w = FX["workbook"]
    assert (
        w["rows"],
        w["breakdowns"],
        w["downtime_h"],
        w["breakdown_cost_idr"],
        w["all_cost_idr"],
        w["labor_h"],
    ) == (211, 31, 434.0, 413_345_000, 537_770_000, 520.5)
    assert w["incomplete"]["count"] == 26 == len(w["incomplete"]["ids"])
    assert w["incomplete"]["by_work_type"] == {
        "Calibration": 1,
        "Corrective": 20,
        "Overhaul": 3,
        "Preventive": 2,
    }
    assert w["breakdown_kinds"] == {
        "planned_flagged": {
            "cost_idr": 69_270_000,
            "count": 8,
            "downtime_h": 164.0,
            "hours": 164.0,
            "rows": 8,
        },
        "unplanned": {
            "cost_idr": 344_075_000,
            "count": 23,
            "downtime_h": 270.0,
            "hours": 270.0,
            "rows": 23,
        },
    }  # 10.5 rows and hours beside count and downtime_h
    assert w["breakdown_flagged"] == {
        "rows": 31,
        "hours": 434.0,
        "cost_idr": 413_345_000,
    }
    assert (
        sum(w["work_types"].values())
        == sum(w["disciplines"].values())
        == sum(w["priorities"].values())
        == sum(w["criticality_counts"].values())
        == 211
    )
    assert w["priorities"]["Emergency"] == 3 and w["disciplines"] == {
        "Electrical": 24,
        "Instrument": 75,
        "Mechanical": 110,
        "Process": 2,
    }
    assert w["window"] == {
        "completion_last": "2025-12-10",
        "report_first": "2024-06-04",
        "report_last": "2025-12-06",
        "days": 550,
    }
    assert {k: v for k, v in w["window"].items() if k != "days"} == FX["dates"][
        "workbook_window"
    ]


def test_demo_wo_carries_the_work_order_s_own_row():
    """WO-240007's downtime and cost are quoted per work order in five prose sites and in Figure 12.

    They must not be read from GA-1201A's asset aggregates, which equal them only because the asset happens to carry one
    flagged breakdown and one empty-closeout uncovered row.
    """
    d = FX["demo_wo"]["WO-240007"]
    assert d == {"downtime_h": 6.5, "cost_idr": 12_630_000, "tag": "GA-1201A"}


def test_populations():
    p = FX[
        "population_ids"
    ]  # the sorted work-order numbers; 10.5 populations.<name> carries the counts
    assert (
        FX["populations"]
        == {k: len(v) for k, v in p.items()}
        == {
            "all": 211,
            "failure": 66,
            "unplanned_failure": 57,
            "planned_flagged": 8,
            "unplanned_breakdowns": 23,
        }
    )
    assert all(v == sorted(set(v)) for v in p.values())
    assert set(p["unplanned_failure"]) < set(p["failure"]) < set(p["all"])
    assert set(p["unplanned_breakdowns"]) < set(p["unplanned_failure"]) and not set(
        p["planned_flagged"]
    ) & set(p["unplanned_failure"])
    assert p["planned_flagged"] == [it["wo"] for it in FX["integrity"]["CD-6"]["items"]]


def test_coverage_rows_exist_for_both_layers_and_every_population():
    assert set(FX["coverage"]) == {
        "generous",
        "strict",
        "bands",
    }  # 10.5 coverage.bands sits beside the two layers
    for layer in ("generous", "strict"):
        assert (
            set(FX["coverage"][layer])
            == set(FX["populations"])
            == set(FX["population_ids"])
        )
        for pop in FX["populations"]:
            r = row(layer, pop)
            assert (
                r["n"] == FX["populations"][pop]
                and r["uncovered"] == len(r["uncovered_ids"])
                and set(r["uncovered_ids"]) <= set(FX["population_ids"][pop])
            )
            assert [x["t"] for x in FX["coverage"][layer][pop]] == FX["method"][
                "thresholds"
            ] and T in FX["method"]["thresholds"]
    g, s = row("generous", "unplanned_failure"), row("strict", "unplanned_failure")
    assert (
        g["uncovered"],
        g["pct"],
        g["unplanned_bd"],
        g["downtime_h"],
        g["cost_idr"],
    ) == (14, 24.6, 5, 74.5, 93_721_000)
    assert (
        s["uncovered"],
        s["pct"],
        s["unplanned_bd"],
        s["downtime_h"],
        s["cost_idr"],
    ) == (
        41,
        71.9,
        14,
        146.0,
        198_418_000,
    )  # -raw + P10/P10b (was 40 / 13 / 138.0 / 182,314,000 before the footer cut)
    assert (row("generous", "all")["uncovered"], row("strict", "all")["uncovered"]) == (
        143,
        190,
    )
    assert FX["verbatim"]["generous"]["any"] == 47 and FX["verbatim"]["generous"][
        "by_field"
    ] == {"Corrective_Action": 42, "Problem_Description": 47, "Root_Cause": 45}
    assert (
        len(FX["coverage_scores"]) == 211
        and FX["method"]["extractor"] == "pdftotext -raw"
    )


def test_bands_sum_to_57():
    b = FX["coverage_bands"]["unplanned_failure"]
    assert (b["t"], b["n"]) == (T, 57) and b["none"] + b["table_only"] + b[
        "taught"
    ] == 57
    assert (b["none"], b["table_only"], b["taught"]) == (
        14,
        27,
        16,
    )  # D1 proxy was 14 / 28 / 15; P10b moved WO-240056
    assert b["none_ids"] == row("generous", "unplanned_failure")["uncovered_ids"]
    assert (
        sorted(b["none_ids"] + b["table_only_ids"] + b["taught_ids"])
        == FX["population_ids"]["unplanned_failure"]
    )
    assert FX["coverage"]["bands"]["unplanned_failure"] == [
        {"t": T, "no_lesson": 14, "copied_row_only": 27, "taught": 16}
    ]  # the 10.5 twin


def test_integrity_total_is_the_sum_of_its_defect_rules():
    i = FX["integrity"]
    rules = {k: v for k, v in i.items() if k.startswith("CD-")}
    assert len(rules) == 17 and "CD-3" not in rules
    assert (
        i["total"]
        == sum(v["count"] for v in rules.values() if not v["observation_only"])
        == 174
    )
    assert {k for k, v in rules.items() if v["observation_only"]} == {"CD-15", "CD-16"}
    assert all(v["count"] == len(v["items"]) for v in rules.values())
    assert (
        i["CD-4"]["count"] == FX["workbook"]["incomplete"]["count"]
        and i["cd4_emergency"] == 3
    )  # A1
    assert i["CD-6"]["count"] == FX["populations"]["planned_flagged"]
    assert i["rules"] == {
        k: v["count"] for k, v in rules.items() if not v["observation_only"]
    }  # the 10.5 twins
    assert i["observations"] == {
        k: v["count"] for k, v in rules.items() if v["observation_only"]
    }
    assert (
        i["CD-1"]["count"] == FX["lessons"]["foreign_footer_lessons"] == 28
        and i["CD-5"]["count"] == FX["lessons"]["no_crossref_line_lessons"] == 5
    )


def test_debt_ranking():
    d = FX["debt"]
    assert d["coefficients"] == {
        "a": 0.4,
        "b": 0.3,
        "c": 0.2,
        "d": 0.1,
        "basis": "ASSUMPTION",
    }  # the 9.5 DebtCluster shape
    assert d["coefficients_by_factor"] == {
        "C": 0.3,
        "D": 0.4,
        "k": 0.2,
        "r": 0.1,
        "basis": "product decision, ASSUMPTION",
    }
    assert (
        d["k_mapping"]
        == {"HIGH CRITICAL": 1.0, "LOW CRITICAL": 0.5, "NON CRITICAL": 0.25}
        and d["t"] == T
    )
    assert [p["tag"] for p in d["per_asset"]] == TAGS and len(d["ranking"]) == 8
    assert [r["rank"] for r in d["ranking"]] == list(range(1, 9))
    scores = [r["score"] for r in d["ranking"]]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 1 for s in scores)
    assert [(r["tag"], r["score"]) for r in d["ranking"][:3]] == [
        ("YD-2301", 0.9375),
        ("KC-4501", 0.5497),
        ("GA-1201A", 0.3891),
    ]
    assert (
        sorted(i for p in d["per_asset"] for i in p["uncovered_ids"])
        == row("generous", "unplanned_failure")["uncovered_ids"]
    )
    crit = {e["tag"]: e["criticality_datasheet"] for e in FX["equipment_master"]}
    assert all(
        p["k"] == d["k_mapping"][crit[p["tag"]]]
        and p["r"]
        == FX["families"]["r_by_tag"][p["tag"]]
        == FX["families"]["r_detail"][p["tag"]]["r"]
        for p in d["per_asset"]
    )
    assert (d["D_max"], d["C_max"]) == (
        max(p["D"] for p in d["per_asset"]),
        max(p["C"] for p in d["per_asset"]),
    )
    # pure function of its inputs: recomputed from the fixture's own parts and fresh workbook rows
    again = debt.rank(
        workbook.load(),
        row("generous", "unplanned_failure")["uncovered_ids"],
        crit,
        dict(FX["families"]["r_by_tag"]),
    )
    assert (
        [{k: p[k] for k in a} for a, p in zip(again["per_asset"], d["per_asset"])],
        again["ranking"],
    ) == (again["per_asset"], d["ranking"])
    assert again["coefficients"] == d["coefficients_by_factor"]
    # the 10.5 twins beside the older keys carry the same values
    assert all(
        p["D_h"] == p["D"]
        and p["C_idr"] == p["C"]
        and p["uncovered_wo_numbers"] == p["uncovered_ids"]
        for p in d["per_asset"]
    )
    assert {p["tag"]: p["rank"] for p in d["per_asset"]} == {
        r["tag"]: r["rank"] for r in d["ranking"]
    }


def test_cross_module_reconciliations():
    em = FX["equipment_master"]
    w = FX["workbook"]
    assert [e["tag"] for e in em] == TAGS
    assert (
        sum(e["wos"] for e in em),
        sum(e["breakdowns_flagged"] for e in em),
        sum(e["breakdown_h_flagged"] for e in em),
    ) == (w["rows"], w["breakdowns"], w["downtime_h"])
    assert (
        sum(e["breakdown_cost_flagged_idr"] for e in em),
        sum(e["all_cost_idr"] for e in em),
        sum(e["incomplete_rows"] for e in em),
    ) == (w["breakdown_cost_idr"], w["all_cost_idr"], w["incomplete"]["count"])
    assert (
        sum(e["unplanned_failure_rows"] for e in em) == 57
        and sum(e["unplanned_breakdown_h"] for e in em)
        == w["breakdown_kinds"]["unplanned"]["downtime_h"]
    )
    pt = FX["proof_tests"]
    assert pt["total"] == sum(c["count"] for c in pt["classes"].values()) == 33 and {
        k: c["count"] for k, c in pt["classes"].items()
    } == {
        "sis_proof_test": 18,
        "sil_logic_proof_test": 5,
        "calibration_proof_test": 7,
        "psv_statutory_test": 3,
    }
    d = FX["dates"]
    assert (
        d["dated"],
        d["span_days"],
        d["gap_to_first_lesson_days"],
        d["gaps"]["median"],
        d["gaps"]["mode"],
    ) == (56, 101, 114, 1, 1)
    assert (FX["latency"]["days"], FX["latency"]["median_days"]) == (
        [210, 220, 442, 503, 528, 730],
        472.5,
    )
    assert (
        FX["lead_time"]["n"],
        FX["lead_time"]["median_h"],
        FX["lead_time"]["ge24_pct"],
    ) == (211, 34.0, 64.5)
    assert FX["lessons"]["n"] == FX["inventory"]["opl_count"] == 56
    by_type = FX["coverage_by_work_type"]["work_types"]
    assert {k: v["n"] for k, v in by_type.items()} == w["work_types"] and sum(
        v["uncovered"] for v in by_type.values()
    ) == row("generous", "all")["uncovered"]
    lg = {r["t"]: r for r in FX["legacy"]["all"]}[T]
    assert (
        lg["uncovered"],
        lg["breakdowns_all"],
        lg["downtime_h_all"],
        lg["cost_idr_all"],
    ) == (158, 13, 238.5, 178_870_000)  # v1.0 headline, evidence only (P6)
    assert (
        FX["labels_agreement"] is None and FX["labelled"] is None
    )  # P5, until the D6 human labels exist
    assert (
        FX["method"]["labels_status"]
        == "machine_drafted_pending_human"
        == FX["coverage_labels"]["status"]
    )  # the 9.5 enum
    assert FX["method"]["labels_note"].startswith(
        "machine-drafted labels present"
    )  # the draft is evidence, not a deck number


def test_golden_block_matches_the_file():
    """Fixture key `golden` (WS4): total and by_category read off golden/cases.yaml by tools.computed.golden_block. Observed
    100 cases in 11 categories by running the harness; cross-checked here by a second, independent path -- PyYAML's own
    safe_load of the same file, which shares no code with computed.py's line-by-line reader -- and by the raw '- id:' line
    count. The three agree, so a case added to the file moves the fixture and this test together."""
    import re as _re

    yaml = pytest.importorskip(
        "yaml"
    )  # third cross-check only; the contract is stdlib + openpyxl
    raw = open(os.path.join(ROOT, "golden", "cases.yaml"), encoding="utf-8").read()
    cases = yaml.safe_load(raw)
    g = FX["golden"]
    assert (
        g["total"] == len(cases) == len(_re.findall(r"(?m)^- id: ", raw)) == 102
    )  # +GS-99/100 (PS-01, PS-04), +GS-101/102 (PS-V2, PS-V4)
    assert len({c["id"] for c in cases}) == 102
    by_cat = {}
    for c in cases:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    assert g["by_category"] == dict(sorted(by_cat.items()))
    assert sum(g["by_category"].values()) == g["total"] and len(g["by_category"]) == 11


@pytest.mark.slow
def test_a_fresh_run_reproduces_the_fixture_byte_for_byte(tmp_path):
    """`make fixtures` over the same corpus at the same commit writes the same bytes. Every published figure descends
    from this file, so a run that differs is a defect in the harness or a changed corpus, never a re-freeze that
    happens quietly: the difference has to be looked at before packages/fixtures.json is replaced."""
    from harness import analyze_corpus

    out = str(tmp_path / "fixtures.json")
    analyze_corpus.main(["--out", out])
    with open(out, encoding="utf-8") as f:
        assert f.read() == TEXT


def test_serialisation_is_canonical_and_path_free():
    assert (
        TEXT == json.dumps(FX, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    )  # byte-identical re-dump
    assert (
        ROOT not in TEXT
        and CORPUS not in TEXT
        and "/Users/" not in TEXT
        and "scratchpad" not in TEXT
    )


def test_harness_readme_quick_map_matches_the_fixture():
    """V-02: harness/README.md is the table a reviewer checks the PRD's numbers against, and it published a strict layer
    the fixture does not contain, twice. The two rows that drifted are pinned here against the fixture itself, so the
    README cannot state a strict headline or a band split the harness never printed. Observed by running `make fixtures`
    and cross-checked by the independent recomputation recorded in this module's docstring."""
    readme = open(os.path.join(ROOT, "harness", "README.md"), encoding="utf-8").read()
    r = next(x for x in FX["coverage"]["strict"]["unplanned_failure"] if x["t"] == 0.62)
    strict = f"{r['uncovered']} ({r['pct']} %), {r['unplanned_bd']} breakdowns, {r['downtime_h']} h, IDR {r['cost_idr']:,}"
    assert strict in readme, strict
    b = FX["coverage_bands"]["unplanned_failure"]
    assert f"{b['none']} / {b['table_only']} / {b['taught']}" in readme


def test_fixture_validates_against_the_registry_schema():
    """contracts/fixtures.schema.json is the 10.5 registry as a JSON Schema; the file must validate (schema or it did not happen)."""
    import jsonschema

    from harness.validate import contracts, registry

    schemas = contracts(os.path.join(ROOT, "contracts"))
    v = jsonschema.Draft202012Validator(
        schemas["fixtures.schema.json"], registry=registry(schemas)
    )
    err = jsonschema.exceptions.best_match(v.iter_errors(FX))
    assert err is None, ("/".join(str(p) for p in err.absolute_path), err.message[:200])


def _at(obj, path):
    """Resolve a dotted 10.5 key path."""
    for seg in path.split("."):
        assert isinstance(obj, dict) and seg in obj, f"{path}: missing {seg!r}"
        obj = obj[seg]
    return obj


def _every(paths, base):
    missing = []
    for p in paths:
        try:
            _at(base, p)
        except AssertionError:
            missing.append(p)
    return missing


THRESHOLDS = [0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75]
POPULATIONS = [
    "unplanned_failure",
    "failure",
    "unplanned_breakdowns",
    "planned_flagged",
    "all",
]
CELL = ["uncovered", "share", "breakdowns", "downtime_h", "cost_idr"]
REGISTRY_PATHS = (
    [
        "inventory.files_total",
        "inventory.by_class",
        "inventory.corpus_sha256",
        "inventory.extractor",
        "inventory.canonical_form_version",
    ]
    + [
        "method." + k
        for k in (
            "recipe_sha256",
            "stop_list_sha256",
            "threshold",
            "window_multiplier",
            "min_content_words",
            "strict_rule",
            "strict_sections",
            "strict_cut_marker",
            "labels_status",
            "unscoreable_ids",
        )
    ]
    + [
        "workbook." + k
        for k in (
            "rows",
            "reported_first",
            "reported_last",
            "completed_last",
            "work_types",
            "all_cost_idr",
            "all_labor_hours",
            "discipline_counts",
        )
    ]
    + ["workbook.breakdown_flagged." + k for k in ("rows", "hours", "cost_idr")]
    + [
        f"workbook.breakdown_kinds.{kind}.{k}"
        for kind in ("unplanned", "planned_flagged")
        for k in ("rows", "hours", "cost_idr")
    ]
    + [
        "workbook.incomplete." + k
        for k in ("rows", "share", "by_work_type", "emergency_rows")
    ]
    + [
        "workbook.lead_time." + k
        for k in ("median_h", "at_least_24h", "share", "min_h", "max_h")
    ]
    + ["populations." + p for p in POPULATIONS]
    + [
        "coverage_labels." + k
        for k in (
            "status",
            "uncovered_ids",
            "uncovered_count",
            "share",
            "breakdowns",
            "downtime_h",
            "cost_idr",
            "kappa_covered",
            "kappa_taught",
        )
    ]
    + [
        f"coverage_labels.proxy_agreement.{layer}.{k}"
        for layer in ("generous", "strict")
        for k in ("precision", "recall", "fp", "fn")
    ]
    + [
        "verbatim." + k
        for k in (
            "problem_description",
            "root_cause",
            "corrective_action",
            "any_field",
            "strict_any_field",
        )
    ]
    + [
        "dates." + k
        for k in (
            "parsed",
            "first",
            "last",
            "window_days",
            "median_gap_d",
            "mode_gap_d",
            "mode_count",
            "within_set_gap_d",
            "days_after_last_breakdown",
        )
    ]
    + ["latency.pairs", "latency.median_d"]
    + [
        "integrity.total",
        "integrity.rules",
        "integrity.observations.CD-15",
        "integrity.observations.CD-16",
    ]
    + ["families.list", "families.r_by_tag", "families.multi_family_wos"]
    + ["chains.links", "chains.by_tag.GA-1201A"]
    + ["debt.coefficients", "debt.D_max", "debt.C_max", "debt.per_asset"]
    + ["proof_tests.total"]
    + [
        "proof_tests.by_class." + k
        for k in (
            "sis_proof_test",
            "sil_logic_test",
            "calibration_proof_test",
            "statutory_relief_test",
        )
    ]
    + ["equipment_master"]
    + [
        "personnel." + k
        for k in (
            "people",
            "classes",
            "dual_role_supervisors",
            "managers_not_in_workbook",
        )
    ]
    + ["golden.size", "golden.by_category", "golden.hard_gate_count"]
    + ["legacy.headline_all", "legacy.note"]
    + ["demo.primary_wo", "demo.backup_wo", "demo.contrast_wo"]
)


def test_every_10_5_key_path_exists():
    """Blueprint 10.5, the fixture key registry: every registered path exists at its registered spelling, the templated
    ones (per population and threshold, per work order, per rule, per asset, per latency pair) expanded from the fixture's
    own lists. Keys may be added and never renamed, so this list only grows."""
    missing = _every(REGISTRY_PATHS, FX)
    for layer in ("generous", "strict"):
        for pop in POPULATIONS:
            rows = FX["coverage"][layer][pop]
            assert [r["t"] for r in rows] == THRESHOLDS, (layer, pop)
            missing += [
                f"coverage.{layer}.{pop}[{r['t']}].{k}"
                for r in rows
                for k in CELL
                if k not in r
            ]
    bands = {r["t"]: r for r in FX["coverage"]["bands"]["unplanned_failure"]}
    missing += [
        f"coverage.bands.unplanned_failure[0.62].{k}"
        for k in ("no_lesson", "copied_row_only", "taught")
        if k not in bands.get(0.62, {})
    ]
    assert set(FX["coverage_scores"]) == set(FX["population_ids"]["all"])
    for wo, s in FX["coverage_scores"].items():
        for layer in ("generous", "strict"):
            missing += [
                f"coverage_scores[{wo}].{layer}.{k}"
                for k in ("best_ratio", "matched_field", "matched_lesson")
                if k not in s[layer]
            ]
    rules = {f"CD-{n}" for n in range(1, 19)} - {
        "CD-3",
        "CD-15",
        "CD-16",
    }  # CD-15 and CD-16 are observations
    missing += [
        f"integrity.rules.{k}"
        for k in sorted(rules)
        if k not in FX["integrity"]["rules"]
    ]
    for pair in FX["latency"]["pairs"]:
        missing += [
            f"latency.pairs[].{k}"
            for k in (
                "wo_number",
                "tag",
                "opl_id",
                "report_date",
                "date_of_sharing",
                "days",
            )
            if k not in pair
        ]
    for p in FX["debt"]["per_asset"]:
        missing += [
            f"debt.per_asset[{p.get('tag')}].{k}"
            for k in (
                "tag",
                "rank",
                "uncovered_wo_numbers",
                "D_h",
                "C_idr",
                "k",
                "r",
                "incomplete_uncovered",
                "score",
            )
            if k not in p
        ]
    for e in FX["equipment_master"]:
        missing += [
            f"equipment_master[{e.get('tag')}].{k}"
            for k in (
                "tag",
                "service",
                "interlock_ref",
                "sil_sheet",
                "criticality",
                "work_orders",
                "failure_rows",
                "breakdown_rows",
                "planned_rows",
                "unplanned_rows",
                "unplanned_h",
                "flagged_h",
                "breakdown_cost_idr",
            )
            if k not in e
        ]
    assert not missing, missing
    assert FX["debt"]["coefficients"] == {
        "a": 0.4,
        "b": 0.3,
        "c": 0.2,
        "d": 0.1,
        "basis": "ASSUMPTION",
    }
    assert all(t in FX["families"]["r_by_tag"] for t in TAGS) and all(
        isinstance(v, float) for v in FX["families"]["r_by_tag"].values()
    )
    assert (
        set(FX["integrity"]["rules"]) == rules
        and sum(FX["integrity"]["rules"].values()) == FX["integrity"]["total"]
    )


def test_10_5_stated_values():
    """The values blueprint 10.5 states in parentheses beside the keys, the frozen constants of contracts/fixtures.schema.json."""
    assert (
        FX["inventory"]["files_total"] == 98
        and FX["inventory"]["canonical_form_version"] == "1"
    )
    assert (
        FX["method"]["threshold"],
        FX["method"]["window_multiplier"],
        FX["method"]["min_content_words"],
    ) == (0.62, 2, 3)
    assert FX["method"]["strict_sections"] == ["header", "1", "2", "3", "4", "6"]
    assert (
        FX["method"]["strict_cut_marker"]
        == "This is sample data provided for CALIBER purposes only"
    )
    assert FX["method"]["labels_status"] in (
        "machine_drafted_pending_human",
        "human_adjudicated",
    )
    assert FX["workbook"]["rows"] == 211
    assert FX["populations"] == {
        "unplanned_failure": 57,
        "failure": 66,
        "unplanned_breakdowns": 23,
        "planned_flagged": 8,
        "all": 211,
    }
    assert FX["verbatim"]["strict_any_field"] == 0
    assert (
        FX["dates"]["parsed"],
        FX["dates"]["window_days"],
        FX["dates"]["within_set_gap_d"],
        FX["dates"]["days_after_last_breakdown"],
    ) == (56, 101, 4, 114)
    assert FX["latency"]["median_d"] == 472.5 and len(FX["latency"]["pairs"]) == 6
    assert FX["integrity"]["total"] == 174
    assert FX["families"]["multi_family_wos"] == []
    assert FX["chains"]["links"] == 18 and FX["chains"]["by_tag"]["GA-1201A"] == 4
    assert FX["proof_tests"]["total"] == 33 and FX["proof_tests"]["by_class"] == {
        "sis_proof_test": 18,
        "sil_logic_test": 5,
        "calibration_proof_test": 7,
        "statutory_relief_test": 3,
    }
    assert (
        FX["personnel"]["people"],
        FX["personnel"]["dual_role_supervisors"],
        FX["personnel"]["managers_not_in_workbook"],
    ) == (23, 3, 2)
    assert (FX["golden"]["size"], FX["golden"]["hard_gate_count"]) == (102, 16)
    assert (FX["legacy"]["headline_all"], FX["legacy"]["note"]) == (
        158,
        "evidence only",
    )
    assert FX["demo"] == {
        "primary_wo": "WO-240007",
        "backup_wo": "WO-240039",
        "contrast_wo": "WO-240060",
    }
    assert FX["demo_wo"]["WO-240007"]["tag"] == "GA-1201A"
