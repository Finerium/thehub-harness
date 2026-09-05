"""Shared fixtures: the rule pack, the approved lessons and the golden set are each loaded once per session.

A test that asks for `positive`, `negative` or `moment_case` runs once per item of that list in rulepack/v1.json
(`fixtures.positives`, `fixtures.negatives`, `fixtures.moments`), so a failure names the case.
"""

import os

import pytest
import yaml

from harness import rulepack
from harness.config import ROOT
from harness.pdftext import opl_texts

PACK = rulepack.load()
FIXTURE_LISTS = {
    "positive": "positives",
    "negative": "negatives",
    "moment_case": "moments",
}


def _id(fx):
    return fx.get("golden_id") or fx.get("framing") or fx.get("expect_class")


def pytest_generate_tests(metafunc):
    for name, key in FIXTURE_LISTS.items():
        if name in metafunc.fixturenames:
            items = PACK["fixtures"][key]
            metafunc.parametrize(
                name, items, ids=[f"{i:02d}-{_id(fx)}" for i, fx in enumerate(items)]
            )


@pytest.fixture(scope="session")
def pack():
    return PACK


@pytest.fixture(scope="session")
def lessons():
    """{opl_id: canonical text} of the 56 approved lessons, read from the corpus through the pinned extractor."""
    return opl_texts()


@pytest.fixture(scope="session")
def golden():
    """{id: case} of golden/cases.yaml."""
    with open(os.path.join(ROOT, "golden", "cases.yaml"), encoding="utf-8") as f:
        return {c["id"]: c for c in yaml.safe_load(f)}
