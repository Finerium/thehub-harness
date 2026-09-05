"""The eight P&ID sidecars and the hand-verified readings (blueprint 9.3 PidSidecar; ADR-007; deviation D-12): every
packages/pid_sidecars/set_0n.json and its bundle copy validates against the contract and carries basis
agent_transcription with review_status pending and no reviewer recorded; packages/hand_verified.json carries the same
four labels at its top level for its eight sets; every adopted file re-serialises byte for byte.
"""

import json
import os

import jsonschema
import pytest

from harness.config import PACKAGES, ROOT
from harness.validate import contracts, registry

# the session fixture bundle_dir (bundle/ on disk, else a fresh `make bundle` into a temporary directory)
pytest_plugins = ["tests.test_bundle"]

SETS = list(range(1, 9))
TAGS_BY_SET = {
    1: "GA-1201A",
    2: "YD-2301",
    3: "DC-3401A",
    4: "KC-4501",
    5: "EA-5601",
    6: "LV-6701",
    7: "CT-7801",
    8: "FA-8901",
}
PENDING = ("agent_transcription", "pending", None, None)


def read(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return json.loads(text), text


def labels(prov):
    return (
        prov["basis"],
        prov["review_status"],
        prov["reviewed_by"],
        prov["reviewed_at"],
    )


@pytest.fixture(scope="module")
def validator():
    schemas = contracts(os.path.join(ROOT, "contracts"))
    return jsonschema.Draft202012Validator(
        {"$ref": schemas["entities/asset.schema.json"]["$id"] + "#/$defs/PidSidecar"},
        registry=registry(schemas),
        format_checker=jsonschema.FormatChecker(),
    )


def check_sidecar(obj, n, validator):
    validator.validate(obj)
    assert obj["set"] == n
    assert labels(obj["provenance"]) == PENDING
    assert obj["provenance"]["alias"] and obj["provenance"]["date"]
    ids = [h["id"] for h in obj["hotspots"]]
    assert ids and len(set(ids)) == len(ids)
    for h in obj["hotspots"]:
        assert 0.0 <= h["x_frac"] <= 1.0 and 0.0 <= h["y_frac"] <= 1.0
        assert h["w_frac"] >= 0.0 and h["h_frac"] >= 0.0
        assert h["as_drawn_text"]
    assert obj["defects"] and all(d["rule"] and d["detail"] for d in obj["defects"])


@pytest.mark.parametrize("n", SETS)
def test_package_sidecar_validates_and_carries_the_d12_labels(n, validator):
    obj, text = read(os.path.join(PACKAGES, "pid_sidecars", f"set_{n:02d}.json"))
    check_sidecar(obj, n, validator)
    assert text == json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


@pytest.mark.parametrize("n", SETS)
def test_bundle_sidecar_validates_and_resolves(bundle_dir, n, validator):
    obj, _ = read(os.path.join(bundle_dir, "pid_sidecars", f"set_{n:02d}.json"))
    check_sidecar(obj, n, validator)
    docs, _ = read(os.path.join(bundle_dir, "documents.json"))
    pids = {d["id"]: d for d in docs if d["class"] == "pid"}
    assert obj["document_id"] in pids
    assert pids[obj["document_id"]]["subject_tag"] == TAGS_BY_SET[n]
    assert all(h["unbound_reason"] for h in obj["hotspots"] if h["bound_tag"] is None)


def test_hand_verified_carries_the_d12_labels():
    obj, text = read(os.path.join(PACKAGES, "hand_verified.json"))
    assert labels(obj) == PENDING
    assert [s["set"] for s in obj["sets"]] == SETS
    assert [s["tag"] for s in obj["sets"]] == [TAGS_BY_SET[n] for n in SETS]
    for s in obj["sets"]:
        assert s["file"] and s["verified_by"] and s["verified_on"]
        assert isinstance(s["foreign_tags"], list) and isinstance(
            s["contradictions"], list
        )
    assert obj["verified_by"] and obj["verified_on"]
    assert text == json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def test_bundle_hand_verified_resolves_to_the_pid_documents(bundle_dir):
    obj, _ = read(os.path.join(bundle_dir, "hand_verified.json"))
    assert labels(obj) == PENDING
    docs, _ = read(os.path.join(bundle_dir, "documents.json"))
    by_id = {d["id"]: d for d in docs}
    for s in obj["sets"]:
        d = by_id[s["document_id"]]
        assert d["class"] == "pid" and os.path.basename(d["source_path"]) == s["file"]
        assert d["subject_tag"] == s["tag"]
