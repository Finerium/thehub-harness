"""The package bundle of blueprint 9.1 as `make bundle` writes it (harness.bundle over harness.chunks, harness.pages
and harness.embed) and as `make release` ships it (harness.release): every 9.1 file except seeded/* and the optional
simulated/ exists (the sequencing decision of .crown/notes.md: bundle 1.0.0 ships without them), every file validates
against contracts/bundle_map.json, the manifest lists every file with its sha256 and byte size, the seed-time files
(chunks.jsonl, opls.json, pages/) never reach the release tarball (D-17), and two runs are byte-identical.

The bundle already built under bundle/ is used when present; otherwise the session fixture builds one into a
temporary directory the way `make bundle` does (chunks, pages, embeddings, then the bundle writer), which needs the
corpus at $CASE1_CORPUS. The other bundle-reading modules (test_g1, test_chunks, test_pages,
test_sidecars) load this module as a plugin (pytest_plugins) to share that fixture.
"""

import hashlib
import json
import os
import tarfile

import pytest

from harness import bundle as B
from harness import release as R
from harness.config import ROOT
from harness.pdftext import file_sha256
from harness.validate import validate_bundle

BUNDLE = os.path.join(ROOT, "bundle")
CONTRACTS = os.path.join(ROOT, "contracts")
FIXTURES = os.path.join(ROOT, "packages", "fixtures.json")
# recorded from the answer engine once it exists (required from bundle 1.1.0) and the optional POLISH series
NOT_AT_1_0_0 = {
    "seeded/packets.json",
    "seeded/drafts.json",
    "seeded/traces.json",
    "simulated/ga-1201a.json",
}
SEED_TIME = ("chunks.jsonl", "opls.json", "pages/", "text/")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def layout():
    """The frozen file tree of 9.1, read from the manifest contract's BundleLayout enum, never typed here."""
    schema = read_json(os.path.join(CONTRACTS, "bundle", "manifest.schema.json"))
    return schema["$defs"]["BundleLayout"]["enum"]


def tree_files(root):
    """Every file under root as a relative posix path."""
    out = set()
    for d, _, fs in os.walk(root):
        for name in fs:
            out.add(os.path.relpath(os.path.join(d, name), root).replace(os.sep, "/"))
    return out


def build_like_make_bundle(out):
    """`make bundle` into `out`: chunks, pages, embeddings, then the bundle writer with its manifest (slow)."""
    from harness import chunks as C
    from harness import embed as E
    from harness import pages as PG

    chunks_path = os.path.join(out, "chunks.jsonl")
    C.main(["--out", chunks_path])
    PG.build(os.path.join(out, "pages"))
    E.embed_chunks(chunks_path)
    B.build(out)


_FALLBACK = []  # one fallback build per process, however many modules request the fixture


@pytest.fixture(scope="session")
def bundle_dir(tmp_path_factory):
    """bundle/ as built on disk when present, else a fresh `make bundle` into a temporary directory."""
    if os.path.exists(os.path.join(BUNDLE, "manifest.json")):
        return BUNDLE
    if not _FALLBACK:
        out = str(tmp_path_factory.mktemp("bundle"))
        build_like_make_bundle(out)
        _FALLBACK.append(out)
    return _FALLBACK[0]


@pytest.fixture(scope="session")
def manifest(bundle_dir):
    return read_json(os.path.join(bundle_dir, "manifest.json"))


def test_every_9_1_file_exists_except_seeded_and_simulated(bundle_dir, manifest):
    expected = [p for p in layout() if p not in NOT_AT_1_0_0]
    missing = [p for p in expected if not os.path.isfile(os.path.join(bundle_dir, p))]
    assert not missing, missing
    if manifest["bundle_version"] == B.BUNDLE_VERSION == "1.0.0":
        present = [
            p for p in NOT_AT_1_0_0 if os.path.exists(os.path.join(bundle_dir, p))
        ]
        assert not present, present
    # the seed-time products of `make bundle` beside the writer's own files
    assert os.path.isfile(os.path.join(bundle_dir, "pages", "index.json"))
    with open(os.path.join(bundle_dir, "chunks.jsonl"), encoding="utf-8") as f:
        first = json.loads(f.readline())
    pin = read_json(os.path.join(ROOT, "packages", "embedding_pin.json"))
    assert len(first["embedding"]) == pin["dim"]


def test_every_file_validates_against_the_bundle_map(bundle_dir):
    results = validate_bundle(bundle_dir)
    bad = [r for r in results if r[1] in ("INVALID", "missing", "unmapped")]
    assert not bad, bad
    valid = {r[0] for r in results if r[1] == "valid"}
    assert valid >= {p for p in layout() if p not in NOT_AT_1_0_0}
    assert "pages/" in valid


def test_manifest_lists_every_file_with_a_matching_sha256(bundle_dir, manifest):
    listed = {f["path"]: f for f in manifest["files"]}
    assert set(listed) == tree_files(bundle_dir) - {"manifest.json"}
    assert [f["path"] for f in manifest["files"]] == sorted(listed)
    wrong = [
        p
        for p, f in listed.items()
        if file_sha256(os.path.join(bundle_dir, p)) != f["sha256"]
        or os.path.getsize(os.path.join(bundle_dir, p)) != f["bytes"]
    ]
    assert not wrong, wrong


def test_manifest_binds_to_the_fixture_and_the_pins(manifest):
    fx = read_json(FIXTURES)
    assert manifest["bundle_version"] == B.BUNDLE_VERSION
    assert (
        manifest["canonical_form_version"]
        == "1"
        == fx["inventory"]["canonical_form_version"]
    )
    assert manifest["extractor"] == fx["inventory"]["extractor"]
    assert manifest["corpus_sha256"] == fx["inventory"]["corpus_sha256"]
    assert manifest["recipe_sha256"] == fx["method"]["recipe_sha256"]
    assert manifest["stop_list_sha256"] == fx["method"]["stop_list_sha256"]
    rulepack = read_json(os.path.join(ROOT, "rulepack", "v1.json"))
    assert manifest["rulepack_version"] == str(rulepack["version"]) == "1"
    pin = read_json(os.path.join(ROOT, "packages", "embedding_pin.json"))
    assert manifest["embedding_model"] == pin["model"]
    assert manifest["created_at"].endswith("Z")


def test_release_tarball_carries_no_seed_time_file(bundle_dir, manifest, tmp_path):
    out = R.build(bundle_dir, str(tmp_path))
    with tarfile.open(out["archive"]) as tar:
        names = tar.getnames()
    prefix = f"thehub-bundle-{manifest['bundle_version']}/"
    assert names and all(n.startswith(prefix) for n in names)
    inside = {n[len(prefix) :] for n in names}
    leaked = sorted(n for n in inside if n.startswith(SEED_TIME))
    assert not leaked, leaked
    assert "opls.json" not in inside and "chunks.jsonl" not in inside
    assert not any(n.startswith("pages/") for n in inside)
    listed = {f["path"] for f in manifest["files"]}
    assert inside == {p for p in listed if not p.startswith(SEED_TIME)} | {
        "manifest.json"
    }
    with open(out["archive"], "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(str(tmp_path), "SHA256SUMS"), encoding="utf-8") as f:
        sums = f.read().split()
    assert (
        sums == [digest, os.path.basename(out["archive"])] and digest == out["sha256"]
    )


@pytest.mark.slow
def test_two_bundle_runs_are_byte_identical(tmp_path):
    """Two runs of the writer on the same corpus at the same commit give the same manifest; the manifest hashes every
    other file, so equal manifests are equal trees."""
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    B.build(a)
    B.build(b)
    with open(os.path.join(a, "manifest.json"), "rb") as f:
        ma = f.read()
    with open(os.path.join(b, "manifest.json"), "rb") as f:
        mb = f.read()
    assert ma == mb
    m = json.loads(ma)
    assert (
        {f["path"] for f in m["files"]}
        == tree_files(a) - {"manifest.json"}
        == tree_files(b) - {"manifest.json"}
    )
    for f in m["files"]:
        assert file_sha256(os.path.join(b, f["path"])) == f["sha256"]
