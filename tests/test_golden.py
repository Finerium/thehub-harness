"""golden/cases.yaml, the golden set of blueprint 9.11: 102 GoldenCase objects that validate against
contracts/golden_case.schema.json, the category counts printed from the file in the 9.11 order (14, 8, 9, 11, 11, 5,
19, 8, 10, 3, 4), 16 hard gates (every case of the two safety categories and no other), a tier on every case, and the
representative cases of the PRD's Appendix D present.
"""

import os
import re
import sys
from collections import Counter

import jsonschema
import pytest
import yaml

from harness.config import ROOT
from harness.validate import contracts, registry

sys.path.insert(0, os.path.join(ROOT, "tools"))
import computed

GOLDEN = os.path.join(ROOT, "golden", "cases.yaml")
COUNTS_9_11 = [14, 8, 9, 11, 11, 5, 19, 8, 10, 3, 4]
HARD_GATES = 16
SAFETY = {"Safety refusal", "Safety-adjacent served"}
APPENDIX_D = [
    "GS-01",
    "GS-03",
    "GS-04",
    "GS-06",
    "GS-09",
    "GS-13",
    "GS-14",
    "GS-15",
    "GS-17",
    "GS-18",
    "GS-24",
    "GS-28",
    "GS-32",
    "GS-76",
    "GS-100",
]


@pytest.fixture(scope="module")
def cases():
    with open(GOLDEN, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def schema():
    return contracts(os.path.join(ROOT, "contracts"))["golden_case.schema.json"]


@pytest.fixture(scope="module")
def validator(schema):
    reg = registry(contracts(os.path.join(ROOT, "contracts")))
    return jsonschema.Draft202012Validator(
        {"$ref": schema["$id"] + "#/$defs/GoldenCase"},
        registry=reg,
        format_checker=jsonschema.FormatChecker(),
    )


def test_every_case_validates_against_the_contract(cases, validator):
    assert isinstance(cases, list) and len(cases) == 102
    bad = []
    for c in cases:
        err = jsonschema.exceptions.best_match(validator.iter_errors(c))
        if err is not None:
            bad.append(
                (
                    c.get("id"),
                    "/".join(str(p) for p in err.absolute_path),
                    err.message[:160],
                )
            )
    assert not bad, bad


def test_category_counts_in_the_9_11_order(cases, schema):
    order = schema["$defs"]["GoldenCase"]["properties"]["category"]["enum"]
    by_cat = Counter(c["category"] for c in cases)
    assert [by_cat[cat] for cat in order] == COUNTS_9_11
    assert sum(COUNTS_9_11) == len(cases) == 102
    stated = schema["x-counts-at-v1"]
    assert {cat: by_cat[cat] for cat in order} == {
        k: v for k, v in stated.items() if k != "total"
    }
    assert stated["total"] == 102
    block = computed.golden_block()
    assert (block["size"], block["total"], block["hard_gate_count"]) == (
        102,
        102,
        HARD_GATES,
    )
    assert block["by_category"] == dict(sorted(by_cat.items()))


def test_hard_gates_are_exactly_the_two_safety_categories(cases):
    hard = {c["id"] for c in cases if c["hard_gate"] is True}
    assert hard == {c["id"] for c in cases if c["category"] in SAFETY}
    assert len(hard) == HARD_GATES
    assert all(isinstance(c["hard_gate"], bool) for c in cases)


def test_every_case_has_a_tier(cases):
    tiers = Counter(c.get("tier") for c in cases)
    assert set(tiers) == {"A", "B"} and sum(tiers.values()) == len(cases)


def test_ids_are_gs_01_to_gs_102(cases):
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids) and all(
        re.fullmatch(r"GS-\d{2,3}", i) for i in ids
    )
    assert set(ids) == {f"GS-{n:02d}" for n in range(1, 103)}


def test_appendix_d_representative_cases_exist(cases):
    ids = {c["id"] for c in cases}
    assert set(APPENDIX_D) <= ids


def test_must_cite_is_a_subset_of_sources_and_origin_is_team(cases):
    for c in cases:
        assert set(c["expected"]["must_cite"]) <= set(c["sources"]), c["id"]
        assert c["origin"] in ("team", "external")
        assert c["input"]["question"].strip()
