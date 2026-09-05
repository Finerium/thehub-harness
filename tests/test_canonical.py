"""The canonical text form of blueprint 9.2 (harness.canonical, the one implementation harness.pdftext defines): every
case of contracts/fixtures/canonical_cases.json reproduces its expected string and hash. The cases are the team's own
strings (no corpus text), each derived by hand from the rule (NFKC, soft hyphens joined, whitespace runs collapsed to
one space, trimmed; case and punctuation kept; identity sha256 over the canonical form in UTF-8) before the file was
written; the application's port (src/lib/canonical.ts) must reproduce the same file.
"""

import hashlib
import json
import os
import unicodedata

import pytest

from harness import pdftext
from harness.canonical import canonical, quote_hash
from harness.config import ROOT

CASES_PATH = os.path.join(ROOT, "contracts", "fixtures", "canonical_cases.json")
with open(CASES_PATH, encoding="utf-8") as _f:
    DOC = json.load(_f)
CASES = DOC["cases"]
IDS = [c["id"] for c in CASES]
SOFT_HYPHEN = "\u00ad"


def test_the_file():
    assert DOC["canonical_form_version"] == "1"
    assert len(CASES) >= 20 and len(set(IDS)) == len(IDS)
    assert all(set(c) == {"id", "note", "input", "expected", "sha256"} for c in CASES)
    with open(CASES_PATH, "rb") as f:
        raw = f.read()
    assert raw.isascii()  # every non-ASCII character is a visible escape, so a reviewer sees what is pinned
    assert any(SOFT_HYPHEN in c["input"] for c in CASES)
    assert any(unicodedata.normalize("NFKC", c["input"]) != c["input"] for c in CASES)
    assert any(
        "  " in c["input"] or "\t" in c["input"] or "\n" in c["input"] for c in CASES
    )
    assert any("Bagaimana" in c["input"] or "Prosedur" in c["input"] for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_case_reproduces_its_string_and_hash(case):
    assert canonical(case["input"]) == case["expected"]
    assert quote_hash(case["input"]) == case["sha256"]
    assert (
        case["sha256"] == hashlib.sha256(case["expected"].encode("utf-8")).hexdigest()
    )


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_expected_is_a_fixed_point_of_the_rule(case):
    e = case["expected"]
    assert canonical(e) == e and quote_hash(e) == case["sha256"]
    assert e == e.strip() and "  " not in e and SOFT_HYPHEN not in e
    assert unicodedata.normalize("NFKC", e) == e
    assert all(ch == " " or not ch.isspace() for ch in e)


def test_one_implementation_everywhere():
    assert canonical is pdftext.canonical
    assert canonical("a\u00adb  c\n\td ") == "ab c d"
    assert canonical("\ufb01") == "fi"
    assert canonical(None) == "" and canonical("") == ""
