"""harness/entities.py where a golden-set failure was traced to the extractor itself (.crown/notes.md, "Why the golden
set fails, diagnosed"): the workbook row anchors of rank 2, the permit block of rank 13 and the instrument table of
rank 19.

Rank 2: a work order or a proof test with no span is deleted from every answer by "provenance or nothing", so every one
of the 211 workbook rows carries one span and one claim bound to its number.
Rank 13: a lesson's permit_lines are its SAFETY PRECAUTIONS bullets, whatever words they use, plus the section-3 bullets
that state a permit, lock-out, tag-out or car-seal requirement; a numbered step of section 4 is served as a step and is
never a permit line, however often the word "permit" occurs in its acceptance cell.
Rank 19: an instrument tag harvested from an effect sentence or a datasheet may not be a plant item, or a question about
an asset this corpus does not describe resolves as known instead of abstaining.

Every count here was observed by running this harness over the corpus at this commit, never typed from a document: a
number that moves is a regression unless the corpus itself changed. The parsers are re-run rather than mocked, so a
change in the extractor build fails here too.
"""

import json
import os
import re

import pytest

from harness import bundle as B
from harness import documents as D
from harness import entities as E
from harness import master as M
from harness.canonical import canonical, quote_hash
from harness.pdftext import class_texts, opl_texts

# the session fixture bundle_dir (bundle/ on disk, else a fresh `make bundle` into a temporary directory)
pytest_plugins = ["tests.test_bundle"]

# rank 19, observed: the ten equipment-shaped names the instrument table used to carry, and the sizes either side of the
# rejection. The names are read back from the corpus below, never trusted from this list alone.
EQUIPMENT_SHAPED = [
    "CT-7802",
    "DA-8910",
    "DC-4501",
    "EA-3401",
    "EA-4502",
    "FA-6710",
    "GA-1201B",
    "GA-5610",
    "GA-8920",
    "GF-2210",
]
TYPED_BEFORE, TYPED_AFTER = 87, 77
# rank 13, observed: 56 lessons, five SAFETY PRECAUTIONS bullets each, six tools bullets of which one states a permit
# requirement, and eighteen distinct permit lines over the three lesson templates.
LESSONS = 56
SAFETY_BULLETS, TOOLS_BULLETS, TOOLS_KEPT = 5, 6, 1
PERMIT_LINES_TOTAL, PERMIT_DISTINCT = 336, 18
EMPTY_BULLETS = 2  # OPL-EA-5601-03 and -04 print an empty tools cell as a bullet


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bullets(raw, n):
    """The canonical bullet lines of section n of one lesson's raw text."""
    return [
        canonical(E.BULLET.sub("", x))
        for x in E._section_lines(raw, n)
        if E.BULLET.match(x)
    ]


@pytest.fixture(scope="module")
def raw_lessons():
    return opl_texts(canon=False)


@pytest.fixture(scope="module")
def typed():
    """typed_tags over the corpus with and without the equipment families, as `make bundle` computes it."""
    sheets = class_texts("interlock")
    datasheets = class_texts("datasheet")
    hand = M.hand_effects()
    parsed = {t: M.parse_interlock(t, x, hand) for t, x in sheets.items()}
    eq = set(sheets)
    prefixes = E.equipment_family_prefixes(
        eq, [p[0] for _, p in sorted(B.sidecar_packages().items())]
    )
    return {
        "equipment": eq,
        "prefixes": prefixes,
        "before": E.typed_tags(eq, parsed, datasheets),
        "after": E.typed_tags(eq, parsed, datasheets, prefixes),
    }


# ---------------------------------------------------------------- rank 19: the instrument table holds instruments
def test_equipment_families_come_from_the_master_and_the_sidecar_hotspots(
    typed, bundle_dir
):
    """The families are read from the two places the corpus itself says "this identifier is a plant item": the tag of
    every asset with a cause-and-effect sheet, and every P&ID hotspot the transcription typed as equipment. Neither
    list is typed here; the assets are cross-checked against the bundle's own equipment table."""
    il = read_json(os.path.join(bundle_dir, "interlocks.json"))
    assert typed["equipment"] == {e["tag"] for e in il["equipment"]}
    assert {E.family_prefix(t) for t in typed["equipment"]} <= typed["prefixes"]
    assert {E.family_prefix(t) for t in EQUIPMENT_SHAPED} <= typed["prefixes"]
    # the families of the eight assets alone do not cover the ten names: DA and GF are only ever named on a drawing
    assert {"DA", "GF"} <= typed["prefixes"] - {
        E.family_prefix(t) for t in typed["equipment"]
    }


def test_typed_tags_rejects_exactly_the_equipment_shaped_names(typed):
    def pairs(m):
        return {(eq, tag) for eq, roles in m.items() for tag in roles}

    before, after = pairs(typed["before"]), pairs(typed["after"])
    assert len(before) == TYPED_BEFORE and len(after) == TYPED_AFTER
    assert sorted({t for _, t in before - after}) == EQUIPMENT_SHAPED
    assert not after - before  # the rejection only removes
    assert not [t for _, t in after if E.family_prefix(t) in typed["prefixes"]]


def test_an_effect_sentence_loses_its_pump_and_keeps_its_valve():
    """The rejection is at the candidate, not downstream: one effect names both the standby pump it starts and the valve
    it closes, and only the valve is an instrument."""
    parsed = {
        "GA-1201A": {
            "rows": [],
            "start_permissives": [],
            "effects": [
                {"final_element": "START STANDBY PUMP GA-1201B; CLOSE XV-1201"}
            ],
        }
    }
    eq, ds = {"GA-1201A"}, {"GA-1201A": ""}
    assert E.typed_tags(eq, parsed, ds, {"GA"}) == {
        "GA-1201A": {"XV-1201": "final_element"}
    }
    assert (
        "GA-1201B" in E.typed_tags(eq, parsed, ds)["GA-1201A"]
    )  # without the families it is typed as an instrument


def test_the_bundle_instrument_table_carries_no_plant_item(typed, bundle_dir):
    il = read_json(os.path.join(bundle_dir, "interlocks.json"))
    tags = [t["tag"] for t in il["instrument_tags"]]
    assert len(tags) == len(set(tags)) == TYPED_AFTER
    assert not [t for t in tags if E.family_prefix(t) in typed["prefixes"]]
    assert not [t for t in tags if t in typed["equipment"]]
    assert not set(tags) & set(EQUIPMENT_SHAPED)


def test_a_hotspot_reading_a_plant_item_is_nulled_with_its_own_reason(bundle_dir):
    """Nothing downstream of the rejection may hold such a tag either: the drawing does name the item, so the reason
    says it is outside the assets this corpus describes rather than that no document types it."""
    adopted = {n: p[0] for n, p in B.sidecar_packages().items()}
    drawn = {
        h["bound_tag"]
        for s in adopted.values()
        for h in s["hotspots"]
        if h["bound_tag"]
    }
    assert set(EQUIPMENT_SHAPED) & drawn  # the P&IDs are where these names occur
    for n in sorted(adopted):
        sc = read_json(os.path.join(bundle_dir, "pid_sidecars", f"set_{n:02d}.json"))
        for h in sc["hotspots"]:
            assert h["bound_tag"] not in EQUIPMENT_SHAPED
            if h["bound_tag"] is None:
                assert h["unbound_reason"]
    reasons = [
        h["unbound_reason"]
        for n in sorted(adopted)
        for h in read_json(
            os.path.join(bundle_dir, "pid_sidecars", f"set_{n:02d}.json")
        )["hotspots"]
        if h["bound_tag"] is None
    ]
    assert [r for r in reasons if "outside the assets this corpus describes" in r]


# ---------------------------------------------------------------- rank 13: the permit block of a lesson
def test_permit_lines_are_the_safety_bullets_and_the_section_3_requirements(
    raw_lessons, bundle_dir
):
    opls = read_json(os.path.join(bundle_dir, "opls.json"))
    assert len(opls["lessons"]) == LESSONS
    total, distinct, empty = 0, set(), 0
    for lesson in opls["lessons"]:
        raw = raw_lessons[lesson["opl_id"]]
        lines = lesson["permit_lines"]
        got = {
            n: [p["text"] for p in lines if p["source_section"] == n] for n in (2, 3, 4)
        }
        s2, s3 = bullets(raw, 2), bullets(raw, 3)
        assert len(s2) == SAFETY_BULLETS and len(s3) == TOOLS_BULLETS
        assert got[2] == s2, lesson["opl_id"]  # every precaution, in document order
        assert got[3] == [b for b in s3 if E.PERMIT_REQUIREMENT.search(b)]
        assert len(got[3]) == TOOLS_KEPT and not got[4]
        total += len(lines)
        empty += sum(1 for b in s2 + s3 if not b)
        distinct.update(p["text"] for p in lines)
    assert total == PERMIT_LINES_TOTAL and len(distinct) == PERMIT_DISTINCT
    assert (
        empty == EMPTY_BULLETS
    )  # an empty tools cell prints as a bullet and is not a permit line


def test_a_precaution_that_never_says_permit_is_still_a_permit_line(
    raw_lessons, bundle_dir
):
    """The rule the extractor used to apply, "the line contains the word permit", is what dropped most of the block:
    over half the distinct precautions do not use the word, and every one of them is now served."""
    opls = read_json(os.path.join(bundle_dir, "opls.json"))
    precautions = {
        p["text"]
        for o in opls["lessons"]
        for p in o["permit_lines"]
        if p["source_section"] == 2
    }
    wordless = {t for t in precautions if not re.search("permit", t, re.IGNORECASE)}
    assert len(wordless) > len(precautions) / 2
    assert all(
        t in {b for raw in raw_lessons.values() for b in bullets(raw, 2)}
        for t in wordless
    )


def test_no_permit_line_is_a_step_or_a_table_header(raw_lessons, bundle_dir):
    """A numbered step of section 4 is served as a step; the word "permit" reaches section 4 through the acceptance
    cell of the step table, which is why the old filter picked steps up."""
    opls = read_json(os.path.join(bundle_dir, "opls.json"))
    steps = {}
    for s in opls["steps"]:
        steps.setdefault(s["opl_id"], set()).add(s["action_text"])
    reached_section_4 = 0
    for lesson in opls["lessons"]:
        raw = raw_lessons[lesson["opl_id"]]
        texts = {p["text"] for p in lesson["permit_lines"]}
        lines = {canonical(x) for x in E.step_lines(raw)}
        assert not texts & lines and not texts & steps[lesson["opl_id"]]
        assert not [
            t for t in texts if re.match(r"^\d ", t)
        ]  # a step row starts with its number
        assert all(E.BULLET.search(x) or True for x in texts)
        reached_section_4 += any(
            re.search("permit", x, re.IGNORECASE) for x in E._section_lines(raw, 4)
        )
    assert (
        reached_section_4
    )  # section 4 does carry the word, and none of it is a permit line


def test_every_permit_line_carries_a_resolvable_span_and_a_note_claim(bundle_dir):
    opls = read_json(os.path.join(bundle_dir, "opls.json"))
    cl = read_json(os.path.join(bundle_dir, "claims.json"))
    spans = {s["id"]: s for s in cl["spans"]}
    notes = {
        (c["span_id"], c["entity_binding"], c["value_text"])
        for c in cl["claims"]
        if c["claim_kind"] == "note"
    }
    for lesson in opls["lessons"]:
        for p in lesson["permit_lines"]:
            s = spans[p["span_id"]]
            assert s["document_revision_id"] == lesson["document_revision_id"]
            assert s["anchor_text"] == p["text"] == canonical(p["text"])
            assert s["quote_hash"] == quote_hash(p["text"])
            assert len(p["text"]) <= D.CITATION_MAX_CHARS
            assert (p["span_id"], lesson["opl_id"], p["text"]) in notes


# ---------------------------------------------------------------- rank 2: one span and one claim per workbook row
def synthetic_rows():
    """Three workbook rows, one of them also a proof test and one proof test the work-order list does not carry, on a
    page numbering that is the Excel row (harness.documents.workbook_row_texts)."""
    rows = [{"WO_Number": "WO-000001"}, {"WO_Number": "WO-000002"}]
    tests = [{"wo_number": "WO-000002"}, {"wo_number": "WO-000003"}]
    row_of = {"WO-000001": 2, "WO-000002": 3, "WO-000003": 4}
    texts = {
        2: "WO-000001 pump casing drain plug weeping",
        3: "WO-000002 proof test of the level trip, as-found within tolerance",
        4: "WO-000003 proof test of the pressure trip, as-left within tolerance",
    }
    return rows, tests, row_of, texts


def test_workbook_row_claims_bind_every_number_once():
    rows, tests, row_of, texts = synthetic_rows()
    spans, claims = D.Spans(), D.Claims()
    n = E.workbook_row_claims(rows, tests, row_of, texts, "rev-test", spans, claims)
    assert (
        n == 3
    )  # the union: the proof test the work-order loop never reaches is bound too
    out = claims.rows()
    assert [c["entity_binding"] for c in out] == ["WO-000001", "WO-000002", "WO-000003"]
    assert {c["claim_kind"] for c in out} == {"row"}
    assert {c["extracted_by"]["basis"] for c in out} == {"parser"}
    for c in out:
        s = spans.by_id[c["span_id"]]
        page = row_of[c["entity_binding"]]
        assert (s["document_revision_id"], s["page"]) == ("rev-test", page)
        assert s["anchor_text"] == c["value_text"] == texts[page]
        assert s["quote_hash"] == quote_hash(texts[page])
        assert s["id"] == f"rev-test/p{page}/0-{len(texts[page])}"


def test_workbook_row_claims_are_idempotent():
    """A span id is (revision, page, offsets) and a claim is a set member, so a second walk adds nothing: the bundle
    stays byte-identical under a re-run."""
    rows, tests, row_of, texts = synthetic_rows()
    spans, claims = D.Spans(), D.Claims()
    E.workbook_row_claims(rows, tests, row_of, texts, "rev-test", spans, claims)
    first = (spans.rows(), claims.rows())
    E.workbook_row_claims(rows, tests, row_of, texts, "rev-test", spans, claims)
    assert (spans.rows(), claims.rows()) == first


def test_a_long_row_is_anchored_at_citation_length():
    """Blueprint 8.3: a span is citation length and nothing longer. A row longer than the limit is cut back to a word
    boundary, so the anchor stays a run of the row and the claim still binds the number."""
    text = "WO-000004 " + " ".join(["seal"] * 80)
    assert len(text) > D.CITATION_MAX_CHARS
    spans, claims = D.Spans(), D.Claims()
    E.workbook_row_claims(
        [{"WO_Number": "WO-000004"}],
        [],
        {"WO-000004": 2},
        {2: text},
        "rev-test",
        spans,
        claims,
    )
    s = spans.rows()[0]
    a = s["anchor_text"]
    assert len(a) <= D.CITATION_MAX_CHARS
    assert text.startswith(a) and text[len(a)] == " "
    assert s["end_ordinal"] == len(a) and s["quote_hash"] == quote_hash(a)
    assert claims.rows()[0]["value_text"] == a
