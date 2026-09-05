"""The pinned local embedding role (harness.embed; ADR-009, second branch): every case of
contracts/fixtures/embedding_cases.json reproduces within 1e-4 per dimension, the vectors are unit norm and 384 wide,
the three model files on disk hash to packages/embedding_pin.json, and a wrong pin fails closed before any inference.
"""

import json
import math
import os

import pytest

from harness import embed as E
from harness.config import ROOT
from harness.pdftext import file_sha256

with open(E.PIN_PATH, encoding="utf-8") as _f:
    PIN = json.load(_f)
with open(
    os.path.join(ROOT, "contracts", "fixtures", "embedding_cases.json"),
    encoding="utf-8",
) as _f:
    CASES = json.load(_f)


def norm(v):
    return math.sqrt(sum(x * x for x in v))


@pytest.fixture(scope="module")
def embedder():
    return E.Embedder()


def test_pin_names_the_module_constants():
    assert PIN["model"] == E.MODEL and PIN["dim"] == E.DIM == 384
    assert [f["path"] for f in PIN["files"]] == list(E.FILES)
    assert PIN["pooling"] == "mean" and PIN["normalize"] is True
    assert (PIN["query_prefix"], PIN["passage_prefix"]) == (
        E.QUERY_PREFIX,
        E.PASSAGE_PREFIX,
    )
    assert all(
        len(f["sha256"]) == 64 and int(f["sha256"], 16) and f["bytes"] > 0
        for f in PIN["files"]
    )


def test_model_files_on_disk_hash_to_the_pin():
    for f in PIN["files"]:
        p = os.path.join(E.MODEL_DIR, f["path"])
        assert os.path.exists(p), f"{p} missing: run `python -m harness.embed --pin`"
        assert file_sha256(p) == f["sha256"] and os.path.getsize(p) == f["bytes"]


def test_cases_file_names_the_pin():
    assert (CASES["model"], CASES["dim"], CASES["prefix"], CASES["decimals"]) == (
        E.MODEL,
        E.DIM,
        E.QUERY_PREFIX,
        E.DECIMALS,
    )
    ids = [c["id"] for c in CASES["cases"]]
    assert ids and len(set(ids)) == len(ids)
    assert all(len(c["expected"]) == E.DIM for c in CASES["cases"])


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["id"] for c in CASES["cases"]])
def test_case_reproduces_within_tolerance(embedder, case):
    got = embedder.embed(case["text"], E.QUERY_PREFIX)
    assert len(got) == len(case["expected"]) == E.DIM == 384
    assert max(abs(a - b) for a, b in zip(got, case["expected"])) <= 1e-4
    assert abs(norm(got) - 1.0) <= 1e-4 and abs(norm(case["expected"]) - 1.0) <= 1e-4
    assert all(round(x, E.DECIMALS) == x for x in got)


def test_same_text_gives_the_same_vector(embedder):
    text = "Berapa setpoint trip getaran tinggi pada pompa umpan heksana?"
    assert embedder.embed(text, E.QUERY_PREFIX) == embedder.embed(text, E.QUERY_PREFIX)
    assert embedder.embed(text, E.QUERY_PREFIX) != embedder.embed(
        text, E.PASSAGE_PREFIX
    )


def test_wrong_pin_hash_fails_closed(tmp_path):
    pin = json.loads(json.dumps(PIN))
    pin["files"][-1]["sha256"] = "0" * 64
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(pin), encoding="utf-8")
    with pytest.raises(SystemExit, match="pin mismatch"):
        E.Embedder(str(path))


def test_wrong_model_or_missing_pin_fails_closed(tmp_path):
    pin = json.loads(json.dumps(PIN))
    pin["model"] = "someone/else"
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(pin), encoding="utf-8")
    with pytest.raises(SystemExit, match="embedding pin names"):
        E.Embedder(str(path))
    with pytest.raises(SystemExit, match="no embedding pin"):
        E.Embedder(str(tmp_path / "absent.json"))


def test_over_long_text_is_refused_not_truncated(embedder):
    with pytest.raises(ValueError, match="exceed"):
        embedder.embed("interlock " * (E.MAX_TOKENS + 1), E.PASSAGE_PREFIX)
