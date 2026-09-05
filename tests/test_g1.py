"""G1, the admission gate of the bundle (blueprint 9.1, 11.2; AC-ING-09): the clean bundle admits, and one mutation of
one row names its violation. Every mutation runs on a temporary copy of the bundle (pages/ left out: G1 reports a listed
seed-time file it cannot find as absent under D-17, and the renders are most of the bytes). The manifest entry of a
rewritten file is refreshed so only the mutated fact is named; in the hash test the stale entry is the point.
"""

import json
import os
import shutil

import pytest

from harness import bundle as B
from harness import g1
from harness.pdftext import file_sha256

# the session fixture bundle_dir (bundle/ on disk, else a fresh `make bundle` into a temporary directory)
pytest_plugins = ["tests.test_bundle"]


def named(gate, check):
    """The violations of one named check."""
    return [v for v in gate.violations if v.startswith(check + ":")]


def run(bundle):
    gate = g1.Gate(bundle)
    gate.run()
    return gate


def load(bundle, rel):
    with open(os.path.join(bundle, rel), encoding="utf-8") as f:
        return json.load(f)


def rewrite(bundle, rel, obj):
    """Write one bundle file in the writer's own format and refresh its manifest entry."""
    path = os.path.join(bundle, rel)
    B.write_json(path, obj)
    m = load(bundle, "manifest.json")
    entry = next(f for f in m["files"] if f["path"] == rel)
    entry["sha256"], entry["bytes"] = file_sha256(path), os.path.getsize(path)
    B.write_json(os.path.join(bundle, "manifest.json"), m)


@pytest.fixture(scope="session")
def clean(bundle_dir):
    return run(bundle_dir)


@pytest.fixture
def mutant(bundle_dir, tmp_path):
    dst = str(tmp_path / "bundle")
    shutil.copytree(bundle_dir, dst, ignore=shutil.ignore_patterns("pages"))
    return dst


def test_clean_bundle_admits(clean):
    assert clean.violations == [], "\n".join(clean.violations)


def test_flipped_byte_names_the_hash_violation(mutant, clean):
    rel = "adjudication_log.md"
    path = os.path.join(mutant, rel)
    with open(path, "rb") as f:
        data = bytearray(f.read())
    data[len(data) // 2] ^= 0x01
    with open(path, "wb") as f:
        f.write(data)
    gate = run(mutant)
    hits = named(gate, "manifest.files")
    assert hits and f"{rel} sha256 or size differs" in hits[0], gate.violations
    assert "1 mismatched" in hits[0]
    assert not named(clean, "manifest.files")


def test_renamed_enum_value_names_the_closed_set_violation(mutant, clean):
    wos = load(mutant, "work_orders.json")
    wos[0]["work_type"] = "Reactive"  # not one of the six 9.4 work types
    rewrite(mutant, "work_orders.json", wos)
    gate = run(mutant)
    hits = [v for v in named(gate, "schema") if "work_orders.json" in v]
    assert hits and "Reactive" in hits[0] and "work_type" in hits[0], gate.violations
    assert not [v for v in named(clean, "schema") if "work_orders.json" in v]
    assert not named(
        gate, "manifest.files"
    )  # the manifest was refreshed: only the enum is at fault


def test_renamed_claim_kind_fails_the_schema_and_the_closure_set(mutant, clean):
    cl = load(mutant, "claims.json")
    cl["claims"][0]["claim_kind"] = "guess"
    rewrite(mutant, "claims.json", cl)
    gate = run(mutant)
    assert [v for v in named(gate, "schema") if "claims.json" in v and "guess" in v], (
        gate.violations
    )
    hits = named(gate, "closure.claim.kind")
    assert hits and "1 of" in hits[0] and "guess" in hits[0], gate.violations
    assert not named(clean, "closure.claim.kind")


def test_broken_span_reference_names_the_closure_violation(mutant, clean):
    cl = load(mutant, "claims.json")
    ghost = "rev-000000000000/p1/0-1"
    cl["claims"][0]["span_id"] = ghost
    rewrite(mutant, "claims.json", cl)
    gate = run(mutant)
    hits = named(gate, "closure.claim.span")
    assert hits and "1 of" in hits[0] and ghost in hits[0], gate.violations
    assert not named(clean, "closure.claim.span")
    assert not [v for v in named(gate, "schema") if "claims.json" in v]


def test_altered_anchor_text_names_the_quote_hash_violation(mutant, clean):
    cl = load(mutant, "claims.json")
    span = next(
        s for s in cl["spans"] if s["anchor_text"].swapcase() != s["anchor_text"]
    )
    a = span["anchor_text"]
    i = next(k for k, ch in enumerate(a) if ch.swapcase() != ch)
    span["anchor_text"] = (
        a[:i] + a[i].swapcase() + a[i + 1 :]
    )  # same length: the ordinals still address the page
    rewrite(mutant, "claims.json", cl)
    gate = run(mutant)
    hits = named(gate, "hashes.spans")
    assert hits and "1 mismatched" in hits[0] and span["id"] in hits[0], gate.violations
    assert not named(clean, "hashes.spans")
    assert not named(gate, "hashes.citation_length")


def test_cli_rejects_a_mutant_with_exit_1(mutant, capsys):
    cl = load(mutant, "claims.json")
    cl["claims"][0]["span_id"] = "rev-000000000000/p1/0-1"
    rewrite(mutant, "claims.json", cl)
    assert g1.main([mutant]) == 1
    out = capsys.readouterr().out
    assert "G1: REJECT bundle" in out and "closure.claim.span" in out
