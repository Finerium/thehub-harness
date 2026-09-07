"""Frozen recipe LD-07 under `pdftotext -raw` (D10): these are the values printed by the first -raw run on 2026-08-30 and
become the regression floor (Addendum D10, OQ-8). Every expectation below was observed by running harness.coverage.compute
and cross-checked by a throwaway script (scratchpad xcheck.py) that re-derived every score with a naive set-slice window
(no Counter sliding), re-aggregated every table/band/by_tag/by_work_type with explicit loops, recomputed the verbatim counts
case-insensitively as well, recomputed the stop-list digest with hashlib directly, and re-summed the legacy all-breakdown
columns from the uncovered ids: zero mismatches. Plan interim proxies that moved under -raw are noted per test.

Strict re-freeze, 2026-08-30: the strict layer is now COMPOSED by harness.opl.strict_text (identity header plus sections 1,
2, 3, 4 and 6) instead of stripped from the whole document, because OPL-DC-3401A-07's raw text emits two troubleshooting
cells after the 'Prepared by' footer, outside the stripped span, and WO-240062 scored 1.0 in the strict layer through one of
them. Every strict expectation below was re-observed from `python3 -m harness.analyze_corpus` and cross-checked by a second
script (scratchpad xcheck_strict.py) that re-extracted the 56 lessons with its own `pdftotext -raw` subprocess call and its
own canonicaliser, sliced the six sections with str.split instead of str.find, composed the strict text again, and re-scored
every work order with a naive set-slice window (no Counter, every window materialised): all 211 strict scores, all seven
threshold rows, the uncovered ids, the bands, the by_tag counts and the verbatim recount (case-insensitive too) matched.

Strict re-freeze 2, 2026-08-30 (P10b): composing was not sufficient. `-raw` prints the page watermark "This is sample data
provided for CALIBER purposes only" inside section 6 of three lessons and then emits out-of-flow table cells after it, so
OPL-DC-3401A-01 and -04 carried a 63-character copy of WO-240056's Corrective_Action inside the composed strict text and
WO-240056 scored 0.7778 off it. harness.opl._between now ends every section at the watermark. One verdict moves
(WO-240056, an unplanned breakdown of 8.0 h / IDR 16,104,000) and the strict figures move with it: 57-population 40 -> 41,
13 -> 14 breakdowns, 138.0 -> 146.0 h, IDR 182,314,000 -> 198,418,000; all-211 189 -> 190; bands 14 / 26 / 17 -> 14 / 27 / 16.
Re-observed and cross-checked by the same second path (scratchpad xcheck_strict.py, rerun after the cut).
"""

import hashlib
import json
import random

from harness import coverage as C
from harness import integrity as I
from harness import opl as O
from harness import pdftext as P
from harness import workbook as W

ROWS = W.load()
POPS = W.populations(ROWS)
TEXTS = P.opl_texts()
PARSED = O.parse_all(TEXTS)
CTX = {
    "rows": ROWS,
    "pops": POPS,
    "opl": TEXTS,
    "parsed": PARSED,
    "files": P.corpus_files(),
}
FX = C.compute(CTX)
T62 = {
    layer: {
        pop: {r["t"]: r for r in rows} for pop, rows in FX["coverage"][layer].items()
    }
    for layer in FX["coverage"]
}
UNCOVERED_14 = [
    "WO-240007",
    "WO-240013",
    "WO-240033",
    "WO-240034",
    "WO-240037",
    "WO-240039",
    "WO-240063",
    "WO-240064",
    "WO-240089",
    "WO-240094",
    "WO-240120",
    "WO-240167",
    "WO-240169",
    "WO-240196",
]  # = plan 5.7 list, unchanged under -raw


def test_populations_and_method():
    assert (
        len(POPS["failure"]),
        len(POPS["unplanned_failure"]),
        len(POPS["planned_flagged"]),
        len(POPS["unplanned_breakdowns"]),
    ) == (66, 57, 8, 23)
    m = FX["method"]
    assert m["stop_list_size"] == 65 and m["stop_list"] == sorted(C.STOP)
    assert (
        m["stop_list_sha256"]
        == hashlib.sha256("\n".join(sorted(C.STOP)).encode("utf-8")).hexdigest()
    )
    assert m["stop_list_sha256"].startswith(
        "8262d5122704987d"
    )  # observed; xcheck.py recomputed it independently
    assert (
        m["unscoreable_ids"] == []
    )  # every work order has a field with >= 3 content tokens (8 thermography rows score 0.0 but are scoreable)
    assert (m["t"], m["window_multiplier"], m["extractor"], m["uncovered_rule"]) == (
        0.62,
        2,
        "pdftotext -raw",
        "score <= t",
    )
    assert "the" in C.STOP and C.tokens("The VSHH-1201 trips at > 7.1 mm/s") == [
        "vshh-1201",
        "trips",
        "7.1",
        "mm/s",
    ]


def test_strict_layer_is_composed_from_the_taught_sections():
    """The strict corpus is harness.opl.strict_text of the parsed lesson, not a strip of the whole document: section 5 and
    everything after the 'Prepared by' footer are absent from all 56, whatever the extractor did with them. The old strip
    could not promise that (OPL-DC-3401A-07 puts two troubleshooting cells after the footer), so the rule is asserted here."""
    assert FX["method"]["strict_sections"] == list(O.STRICT_SECTIONS)
    strict = O.strict_texts(PARSED)
    assert sorted(strict) == sorted(TEXTS) and len(strict) == 56
    for k, t in TEXTS.items():
        s = strict[k]
        assert len(s) < len(t), k
        for absent in (
            "COMMON PROBLEMS",
            "Prepared by",
            "Date of Sharing",
            "Reviewed by",
        ):
            assert absent not in s, (k, absent)
        for taught in (
            PARSED[k]["purpose"],
            PARSED[k]["safety_text"],
            PARSED[k]["tools_text"],
            PARSED[k]["steps_text"],
            PARSED[k]["key_learning"],
        ):
            assert taught and taught in s, k
        assert PARSED[k]["troubleshooting_text"] not in s, k
    # the deprecated stripper still does what its docstring says, and this is exactly why it cannot define the layer
    leak = O.strip_troubleshooting(TEXTS["OPL-DC-3401A-07"])
    assert (
        "COMMON PROBLEMS" not in leak and "Spiral-wound gasket unevenly seated" in leak
    )
    assert "Spiral-wound gasket unevenly seated" not in strict["OPL-DC-3401A-07"]


def test_generous_unplanned_failure_headline():
    g = T62["generous"]["unplanned_failure"]
    assert (
        g[0.62]["n"],
        g[0.62]["uncovered"],
        g[0.62]["pct"],
        g[0.62]["unplanned_bd"],
        g[0.62]["downtime_h"],
        g[0.62]["cost_idr"],
    ) == (57, 14, 24.6, 5, 74.5, 93_721_000)
    assert g[0.62]["uncovered_ids"] == UNCOVERED_14
    assert g[0.62]["by_tag"] == {
        "CT-7801": 2,
        "DC-3401A": 2,
        "EA-5601": 1,
        "FA-8901": 1,
        "GA-1201A": 2,
        "KC-4501": 2,
        "YD-2301": 4,
    }
    assert [g[t]["uncovered"] for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70)] == [
        13,
        13,
        14,
        14,
        14,
        14,
    ]  # flat within 1 (LD-07 item 1)
    assert (
        g[0.75]["uncovered"],
        g[0.75]["unplanned_bd"],
        g[0.75]["downtime_h"],
        g[0.75]["cost_idr"],
    ) == (20, 8, 94.5, 124_806_000)
    assert all(
        g[t]["unplanned_bd"] == 5 and g[t]["cost_idr"] == 93_721_000
        for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70)
    )


def test_strict_unplanned_failure():
    """Re-frozen on the composed strict layer with the P10b page-watermark cut: 41 / 14 / 146.0 h / IDR 198,418,000 at
    t = 0.62 (was 40 / 13 / 138.0 h / IDR 182,314,000 while the watermark and the out-of-flow cells after it still reached
    section 6; the stripped layer before that printed 40 / 12 / 128.0 h / IDR 170,042,000).

    Every literal here was printed by harness.coverage AND reproduced by a throwaway second path (scratchpad
    xcheck_strict.py, 2026-08-30) that shares no code with the harness: `pdftotext -raw` called through subprocess, openpyxl
    read directly, the strict text rebuilt from its own regexes, and containment scored by a naive max over every window
    (no Counter, no early exit). Both paths print the same ladder, the same per-asset split and the same 14 / 27 / 16 bands.

    The single verdict that moves from the previous freeze is WO-240056: its Corrective_Action was scored off a truncated
    copy of itself that `-raw` emits after the page watermark inside OPL-DC-3401A-01 and -04, the same string CD-12 reports.
    Strict 0.7778 (unit Corrective_Action / OPL-DC-3401A-01) -> 0.4 (Root_Cause / OPL-DC-3401A-06), and it carries the
    8.0 h and IDR 16,104,000 of the move as an unplanned breakdown."""
    s = T62["strict"]["unplanned_failure"]
    assert (
        s[0.62]["n"],
        s[0.62]["uncovered"],
        s[0.62]["pct"],
        s[0.62]["unplanned_bd"],
        s[0.62]["downtime_h"],
        s[0.62]["cost_idr"],
    ) == (57, 41, 71.9, 14, 146.0, 198_418_000)
    assert [s[t]["uncovered"] for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75)] == [
        32,
        32,
        41,
        41,
        41,
        43,
        52,
    ]
    assert [
        s[t]["unplanned_bd"] for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75)
    ] == [12, 12, 14, 14, 14, 15, 19]
    assert [s[t]["downtime_h"] for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75)] == [
        132.0,
        132.0,
        146.0,
        146.0,
        146.0,
        158.0,
        182.0,
    ]
    assert [s[t]["cost_idr"] for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75)] == [
        178_671_000,
        178_671_000,
        198_418_000,
        198_418_000,
        198_418_000,
        215_980_000,
        260_448_000,
    ]
    assert s[0.62]["by_tag"] == {
        "CT-7801": 4,
        "DC-3401A": 7,
        "EA-5601": 6,
        "FA-8901": 3,
        "GA-1201A": 7,
        "KC-4501": 4,
        "LV-6701": 4,
        "YD-2301": 6,
    }
    assert {"WO-240056", "WO-240062"} <= set(
        s[0.62]["uncovered_ids"]
    ) and "WO-240112" not in s[0.62]["uncovered_ids"]
    assert FX["coverage_scores"]["WO-240056"]["strict"] == {
        "score": 0.4,
        "unit": ["Root_Cause", "OPL-DC-3401A-06"],
    }
    for t in (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75):
        assert set(T62["generous"]["unplanned_failure"][t]["uncovered_ids"]) <= set(
            s[t]["uncovered_ids"]
        ), t


def test_strict_uncovered_contains_generous_uncovered():
    """Observed, not structural: the composed strict text is not a substring of the lesson, it is a re-ordering (the identity
    header is pulled in front of section 1 and the sections are joined), so one window can span tokens the full text kept
    apart and a strict score can exceed its generous twin. Exactly one work order in the corpus does that -- WO-240005,
    generous 0.5 / strict 0.5556 -- and it is not a failure row, so the strict-uncovered set is a superset of the
    generous-uncovered set in every population except all-211 at t = 0.50 and t = 0.55."""
    sc = FX["coverage_scores"]
    higher = sorted(
        w for w, v in sc.items() if v["strict"]["score"] > v["generous"]["score"]
    )
    assert higher == ["WO-240005"] and (
        sc["WO-240005"]["generous"]["score"],
        sc["WO-240005"]["strict"]["score"],
    ) == (0.5, 0.5556)
    assert "WO-240005" not in W.ids(POPS["failure"])
    for pop in sorted(POPS):
        for t in C.THRESHOLDS:
            g = set(T62["generous"][pop][t]["uncovered_ids"])
            s = set(T62["strict"][pop][t]["uncovered_ids"])
            assert g <= s or (pop, t) in {("all", 0.50), ("all", 0.55)}, (
                pop,
                t,
                sorted(g - s),
            )
            if not g <= s:
                assert sorted(g - s) == ["WO-240005"], (pop, t)


def test_other_populations():
    """All-211 generous at 0.62 = 143 as HN-07; strict all-211 = 190 with the P10b watermark cut (189 before it, 186 on the
    literal 'everything before section 1' reading of the header, plan proxy 188). Reproduced by the independent
    xcheck_strict.py path described in test_strict_unplanned_failure."""
    a, sa = T62["generous"]["all"], T62["strict"]["all"]
    assert (
        a[0.55]["uncovered"],
        a[0.62]["uncovered"],
        a[0.75]["uncovered"],
        a[0.62]["pct"],
    ) == (141, 143, 160, 67.8)
    assert (sa[0.62]["uncovered"], sa[0.62]["pct"]) == (190, 90.0)
    assert (
        T62["generous"]["planned_flagged"][0.62]["uncovered"],
        T62["generous"]["planned_flagged"][0.62]["unplanned_bd"],
    ) == (4, 0)
    assert (
        T62["generous"]["unplanned_breakdowns"][0.62]["uncovered"],
        T62["strict"]["unplanned_breakdowns"][0.62]["uncovered"],
    ) == (5, 14)
    assert (
        T62["generous"]["failure"][0.62]["uncovered"],
        T62["strict"]["failure"][0.62]["uncovered"],
    ) == (19, 49)
    for layer in FX["coverage"]:
        for pop, rows in FX["coverage"][layer].items():
            assert [r["t"] for r in rows] == list(C.THRESHOLDS) and all(
                r["n"] == len(POPS[pop]) for r in rows
            )


def test_named_work_orders():
    sc = FX["coverage_scores"]
    assert len(sc) == 211 and all(set(v) == {"generous", "strict"} for v in sc.values())
    assert sc["WO-240060"]["generous"] == {
        "score": 1.0,
        "unit": ["Problem_Description", "OPL-DC-3401A-07"],
    }  # LD-06: covered by a pasted table only
    assert sc["WO-240060"]["strict"]["score"] == 0.2 < C.T
    # the strict leak this re-freeze closed: WO-240062's Root_Cause is a troubleshooting cell OPL-DC-3401A-07 repeats after
    # its footer, so the stripped layer scored it 1.0; composed from sections 1-4 and 6 it scores 0.6 and is uncovered
    assert sc["WO-240062"]["generous"] == {
        "score": 1.0,
        "unit": ["Problem_Description", "OPL-DC-3401A-07"],
    }
    assert sc["WO-240062"]["strict"] == {
        "score": 0.6,
        "unit": ["Problem_Description", "OPL-DC-3401A-07"],
    }
    assert (
        sc["WO-240007"]["generous"]["score"]
        == sc["WO-240007"]["strict"]["score"]
        == 0.4286
    )  # the coupling cluster (LD-06)
    for layer in ("generous", "strict"):
        assert all(
            "WO-240007" in r["uncovered_ids"]
            for r in FX["coverage"][layer]["unplanned_failure"]
        )
    assert (
        sc["WO-240171"]["generous"]["score"] == 0.8
        and "WO-240171"
        not in T62["generous"]["unplanned_failure"][0.62]["uncovered_ids"]
    )
    assert (
        sc["WO-240037"]["generous"]["score"] == 0.3333
        and "WO-240037" in T62["generous"]["unplanned_failure"][0.62]["uncovered_ids"]
    )  # paraphrase blind spot (LD-05)
    assert (
        sc["WO-240094"]["generous"]["score"] == 0.6
    )  # the stop-list edge of P5: uncovered at 0.60/0.62, covered at 0.55


def test_bands_partition_the_57():
    b = FX["coverage_bands"]["unplanned_failure"]
    assert (b["t"], b["n"], b["none"], b["table_only"], b["taught"]) == (
        0.62,
        57,
        14,
        27,
        16,
    )  # plan proxy 14 / 28 / 15 (D1)
    assert (
        "WO-240056" in b["table_only_ids"]
    )  # P10b: it was in taught while a pasted closeout row reached the strict layer
    assert b["none_ids"] == UNCOVERED_14
    ids = b["none_ids"] + b["table_only_ids"] + b["taught_ids"]
    assert len(ids) == 57 == len(set(ids)) and sorted(ids) == W.ids(
        POPS["unplanned_failure"]
    )


def test_by_work_type_and_tag():
    bw = FX["coverage_by_work_type"]
    assert bw["work_types"] == {
        "Calibration": {"n": 12, "uncovered": 4},
        "Corrective": {"n": 53, "uncovered": 13},
        "Inspection": {"n": 30, "uncovered": 26},
        "Overhaul": {"n": 6, "uncovered": 3},
        "Predictive": {"n": 42, "uncovered": 42},
        "Preventive": {"n": 68, "uncovered": 55},
    }  # HN-V-01
    assert bw["breakdowns"] == {
        "n": 31,
        "uncovered": 9,
        "planned_flagged_uncovered": 4,
        "unplanned_uncovered": 5,
    }
    assert (
        sum(v["n"] for v in bw["work_types"].values()) == 211
        and sum(v["uncovered"] for v in bw["work_types"].values()) == 143
    )
    bt = FX["coverage_by_tag"]["tags"]
    assert bt == {
        "CT-7801": {
            "n_unplanned_failure": 7,
            "uncovered_generous": 2,
            "uncovered_strict": 4,
        },
        "DC-3401A": {
            "n_unplanned_failure": 7,
            "uncovered_generous": 2,
            "uncovered_strict": 7,
        },
        "EA-5601": {
            "n_unplanned_failure": 8,
            "uncovered_generous": 1,
            "uncovered_strict": 6,
        },
        "FA-8901": {
            "n_unplanned_failure": 5,
            "uncovered_generous": 1,
            "uncovered_strict": 3,
        },
        "GA-1201A": {
            "n_unplanned_failure": 7,
            "uncovered_generous": 2,
            "uncovered_strict": 7,
        },
        "KC-4501": {
            "n_unplanned_failure": 8,
            "uncovered_generous": 2,
            "uncovered_strict": 4,
        },
        "LV-6701": {
            "n_unplanned_failure": 7,
            "uncovered_generous": 0,
            "uncovered_strict": 4,
        },
        "YD-2301": {
            "n_unplanned_failure": 8,
            "uncovered_generous": 4,
            "uncovered_strict": 6,
        },
    }
    assert (
        sum(v["uncovered_generous"] for v in bt.values()) == 14
        and sum(v["uncovered_strict"] for v in bt.values()) == 41
    )


def test_verbatim():
    """D10: PD 47 / RC 45 / CA 42, 47 work orders under -raw (case-insensitive recount identical), all in the generous layer.
    The strict layer now has none: the one hit was WO-240062 in OPL-DC-3401A-07, whose -raw text carries two troubleshooting
    cells after the footer, outside the stripped span; the composed strict text cannot contain them."""
    v = FX["verbatim"]
    assert v["generous"]["by_field"] == {
        "Corrective_Action": 42,
        "Problem_Description": 47,
        "Root_Cause": 45,
    }
    assert v["generous"]["any"] == 47 == len(v["generous"]["any_ids"]) and v[
        "generous"
    ]["any_ids"] == sorted(v["generous"]["any_ids"])
    assert (
        v["strict"]["by_field"]
        == {"Corrective_Action": 0, "Problem_Description": 0, "Root_Cause": 0}
        and v["strict"]["any_ids"] == []
    )
    assert all(
        FX["coverage_scores"][w]["generous"]["score"] == 1.0
        for w in v["generous"]["any_ids"]
    )  # verbatim rows score 1.0 (LD-07 item 1)


def test_no_copied_troubleshooting_cell_survives_in_the_strict_layer():
    """The prefix-level guard the verbatim test cannot give (P10b).

    CD-12 lists every truncated copy of a work-order narrative field the extractor leaves in a lesson. The verbatim test
    only catches a FULL field, so a 63-character prefix of an 85-character field walked straight through it: that is how
    OPL-DC-3401A-01 and -04 fed WO-240056 a strict score of 0.7778 off a pasted closeout row. Every CD-12 cell must be
    absent from the strict text of the lesson that carries it, at any length."""
    strict = O.strict_texts(PARSED)
    cells = I.compute(CTX)["CD-12"]["items"]
    assert len(cells) == 38 and len({c["opl_id"] for c in cells}) == 20
    assert [c for c in cells if c["cell"] in strict[c["opl_id"]]] == []
    # and the watermark itself, which is what let the cells in
    assert [k for k, t in strict.items() if O.PAGE_FOOTER in t] == []
    assert (
        sum(O.PAGE_FOOTER in t for t in TEXTS.values()) == 56
    )  # every lesson carries it exactly once, in the generous layer


def test_no_narrative_field_survives_verbatim_in_the_strict_layer():
    """The property the strict layer claims: it holds only what a lesson TEACHES, so no work-order narrative field can appear
    in it word for word. Asserted as fixture verbatim.strict.any == 0 and recomputed here per lesson (the fixture concatenates
    a tag's lessons, which could in principle hide a hit that spans two of them) and case-insensitively. 47 work orders are
    still quoted verbatim in the generous layer -- that is the pasted troubleshooting tables, and it is the point of the
    two-layer reading, not a defect."""
    v = FX["verbatim"]
    assert v["strict"] == {
        "by_field": {"Corrective_Action": 0, "Problem_Description": 0, "Root_Cause": 0},
        "any": 0,
        "any_ids": [],
    }
    strict = O.strict_texts(PARSED)
    hits = []
    for w in ROWS:
        for cf in W.NARR:
            val = P.canonical(str(w[cf] or "")).lower()
            if len(val) < C.VERBATIM_MIN_CHARS:
                continue
            for oid, txt in sorted(strict.items()):
                if P.tag_of_opl(oid) == w["Equipment_Tag"] and val in txt.lower():
                    hits.append((w["WO_Number"], cf, oid))
    assert hits == [], hits
    assert v["generous"]["any"] == 47
    # WO-240062 was the single leak: verbatim in the full text, absent from every strict text
    w62 = next(w for w in ROWS if w["WO_Number"] == "WO-240062")
    rc = P.canonical(w62["Root_Cause"])
    assert len(rc) >= C.VERBATIM_MIN_CHARS and rc in P.canonical(
        TEXTS["OPL-DC-3401A-07"]
    )
    assert (
        all(rc not in t for t in strict.values())
        and "WO-240062" in v["generous"]["any_ids"]
    )


def test_generous_layer_unchanged_by_the_strict_re_freeze():
    """The strict fix must not touch the headline: the generous layer reads the full canonical text exactly as before."""
    g = T62["generous"]["unplanned_failure"]
    assert (
        g[0.62]["uncovered"],
        g[0.62]["unplanned_bd"],
        g[0.62]["downtime_h"],
        g[0.62]["cost_idr"],
    ) == (14, 5, 74.5, 93_721_000)
    assert g[0.62]["uncovered_ids"] == UNCOVERED_14
    assert C.score(ROWS, C.lessons_by_tag(TEXTS)) == {
        w: v["generous"] for w, v in FX["coverage_scores"].items()
    }
    assert FX["verbatim"]["generous"]["by_field"] == {
        "Corrective_Action": 42,
        "Problem_Description": 47,
        "Root_Cause": 45,
    }
    b = FX["coverage_bands"]["unplanned_failure"]
    assert (b["none"], b["table_only"], b["taught"]) == (
        14,
        27,
        16,
    )  # only the strict side moves: WO-240056 none -> table_only


def test_order_independence():
    """HN-04: shuffling the lesson order per tag with three fixed seeds leaves every score and unit identical."""
    lessons = C.lessons_by_tag(TEXTS)
    base = C.score(ROWS, lessons)
    assert base == {w: v["generous"] for w, v in FX["coverage_scores"].items()}
    for seed in (1, 2, 3):
        rnd = random.Random(seed)
        shuffled = {tag: rnd.sample(docs, len(docs)) for tag, docs in lessons.items()}
        assert any(shuffled[tag] != lessons[tag] for tag in lessons)
        assert C.score(ROWS, shuffled) == base


def test_agreement_synthetic_labels():
    """LD-05 / plan Task 1.3: WO-240037 labelled covered by OPL-YD-2301-04 (proxy 0.33 -> fn), WO-240007 labelled [] (proxy 0.43 -> tn)."""
    labels = {"WO-240037": ["OPL-YD-2301-04"], "WO-240007": []}
    scores = {w: v["generous"] for w, v in FX["coverage_scores"].items()}
    a = C.agreement(scores, labels, 0.62)
    assert a == {
        "n": 2,
        "precision": None,
        "recall": 0.0,
        "tp": 0,
        "fp": 0,
        "fn": 1,
        "tn": 1,
    }
    lab = C.labelled_table(ROWS, labels)
    w7 = next(r for r in ROWS if r["WO_Number"] == "WO-240007")
    assert (lab["n"], lab["uncovered"], lab["uncovered_ids"], lab["unplanned_bd"]) == (
        2,
        1,
        ["WO-240007"],
        1,
    )
    assert (lab["downtime_h"], lab["cost_idr"]) == (
        w7["Downtime_Hours"],
        w7["Total_Cost_IDR"],
    )


def test_labels_status_never_both_absent():
    """P5: either the labelled figure is present or the 'pending' sentence is (the draft sentence counts as pending)."""
    if FX["labels_agreement"] is None:
        assert FX["labelled"] is None
        assert FX["method"]["labels_status"] == (
            C.DRAFT_STATUS if FX["labelled_draft"] else "pending (proxy numbers in use)"
        )
    else:
        assert {"generous", "strict", "t"} <= set(FX["labels_agreement"]) and FX[
            "labelled"
        ]["n"] == FX["labels_agreement"]["generous"]["n"]
        assert FX["method"]["labels_status"].startswith("labelled")


def test_draft_labels_agreement():
    """WS1 Task 1.6: the machine-drafted adjudication of the two independent label sets (packages/coverage_labels.draft.json,
    57 work orders, 47 covered, 17 of them table_only) scored against the proxy at t = 0.62. Observed by running
    harness.coverage.compute and cross-checked by a throwaway script (scratchpad adjudicate/xcheck) that re-derived every
    score with a naive max-over-slices window (no Counter sliding) and re-counted the confusion matrix in an explicit loop:
    same tp/fp/fn/tn in both layers, same single false positive WO-240091 and the same five generous false negatives
    (WO-240034, WO-240037, WO-240089, WO-240167, WO-240169). The draft is evidence, never a deck number: labelled and
    labels_agreement stay null until the human-adjudicated packages/coverage_labels.json exists (D6, OQ-6)."""
    assert FX["labelled"] is None and FX["labels_agreement"] is None
    assert FX["method"]["labels_status"] == C.DRAFT_STATUS
    a = FX["labels_agreement_draft"]
    assert a["t"] == 0.62
    assert {k: a["generous"][k] for k in ("n", "tp", "fp", "fn", "tn")} == {
        "n": 57,
        "tp": 42,
        "fp": 1,
        "fn": 5,
        "tn": 9,
    }
    assert (a["generous"]["precision"], a["generous"]["recall"]) == (
        round(42 / 43, 4),
        round(42 / 47, 4),
    )
    assert {k: a["strict"][k] for k in ("n", "tp", "fp", "fn", "tn")} == {
        "n": 57,
        "tp": 15,
        "fp": 1,
        "fn": 32,
        "tn": 9,
    }
    assert (a["strict"]["precision"], a["strict"]["recall"]) == (
        round(15 / 16, 4),
        round(15 / 47, 4),
    )
    # D6: Cohen's kappa between the two labellers, recomputed from the per-labeller verdicts in the shipped label file and
    # equal to packages/adjudication_log.draft.md section 3 (binary 1.0000 from a 47/0/0/10 table; taught 0.9647 = 520/539).
    assert a["kappa"]["labellers"] == ["AGENT-L1", "AGENT-L2"] and a["kappa"]["n"] == 57
    assert (a["kappa"]["covered"], a["kappa"]["taught"]) == (1.0, 0.9647)
    d = FX["labelled_draft"]
    assert (d["n"], d["uncovered"], d["pct"]) == (
        57,
        10,
        17.5,
    )  # the labels leave 10 uncovered, the proxy 14 (bands 14 / 27 / 16)
    with open(C.DRAFT_LABELS_PATH, encoding="utf-8") as fh:
        drafted = json.load(fh)
    assert len(drafted) == 57 and d["uncovered_ids"] == sorted(
        r["wo_number"] for r in drafted if not r["covered_by"]
    )
    assert sum(r["agreed"] for r in drafted) == 56 and not any(
        r["adjudicated"] for r in drafted
    )


def test_legacy_window_reproduces_v10_headline():
    """P6 rewrite: evidence only. Over every Breakdown = Yes row (as v1.0 counted) the sorted-order concatenation of -raw text
    prints 158 / 13 / 238.5 h / IDR 178,870,000 at t = 0.62 -- the v1.0 figures exactly, inside the HN-04 order-dependent range."""
    lg = FX["legacy"]
    assert lg["order_dependent"] is True and lg["evidence_only"] is True
    r = {row["t"]: row for row in lg["all"]}
    assert 158 <= r[0.62]["uncovered"] <= 160 and r[0.62]["uncovered"] == 158
    assert 12 <= r[0.62]["breakdowns_all"] <= 14 and r[0.62]["breakdowns_all"] == 13
    assert (
        170_000_000 <= r[0.62]["cost_idr_all"] <= 185_000_000
        and r[0.62]["cost_idr_all"] == 178_870_000
    )
    assert r[0.62]["downtime_h_all"] == 238.5
    assert (r[0.62]["unplanned_bd"], r[0.62]["downtime_h"], r[0.62]["cost_idr"]) == (
        8,
        108.5,
        124_716_000,
    )
    assert [r[t]["uncovered"] for t in C.THRESHOLDS] == [
        101,
        141,
        153,
        158,
        159,
        162,
        163,
    ]  # the band collapses at 0.50 (LD-01 noise floor)


def test_fixture_is_json_and_keys():
    assert set(FX) == {
        "method",
        "coverage",
        "coverage_scores",
        "coverage_bands",
        "coverage_by_work_type",
        "coverage_by_tag",
        "verbatim",
        "labels_agreement",
        "labels_agreement_draft",
        "labelled",
        "labelled_draft",
        "legacy",
    }
    assert set(FX["coverage"]) == {"generous", "strict"} and set(
        FX["coverage"]["generous"]
    ) == set(POPS)
    json.dumps(FX, sort_keys=True)
