"""chunks.jsonl as `make chunks` and `make embed` write it (harness.chunks, harness.embed; blueprint 9.2 Chunk,
AC-ING-13): the counts by document class and unit kind observed in the file on 2026-09-05 and pinned here, every chunk a
run of its page's canonical text carrying the hash of that run, chunks never overlapping and never over 512 tokens, and
ids deterministic (a fresh run of harness.chunks over the corpus reproduces every row).
"""

import hashlib
import json
import os
from collections import Counter

import pytest

from harness import chunks as C
from harness import documents as D
from harness import embed as E
from harness.canonical import canonical, quote_hash
from harness.config import ROOT
from harness.pdftext import corpus_files, doc_class

# the session fixture bundle_dir (bundle/ on disk, else a fresh `make bundle` into a temporary directory)
pytest_plugins = ["tests.test_bundle"]

TOTAL = 832
BY_KIND = {
    "ce_row": 39,
    "datasheet_group": 40,
    "note": 193,
    "opl_section": 280,
    "opl_step": 280,
}
BY_CLASS = {
    "datasheet": 40,
    "ga_drawing": 40,
    "interlock": 88,
    "opl": 616,
    "plot_plan": 48,
}


@pytest.fixture(scope="module")
def rows(bundle_dir):
    with open(os.path.join(bundle_dir, "chunks.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def pdfs():
    """{revision id as harness.chunks names it: (path, class)} of every corpus PDF."""
    return {
        C.identity(p)[1]: (p, doc_class(p))
        for p in corpus_files()
        if p.lower().endswith(".pdf")
    }


@pytest.fixture(scope="module")
def page_texts(pdfs):
    return {rev: D.pdf_page_texts(path) for rev, (path, _) in pdfs.items()}


def test_counts_by_class_and_kind(rows, pdfs):
    assert len(rows) == TOTAL == sum(BY_KIND.values()) == sum(BY_CLASS.values())
    assert dict(Counter(r["unit_kind"] for r in rows)) == BY_KIND
    assert dict(Counter(pdfs[r["document_revision_id"]][1] for r in rows)) == BY_CLASS
    assert {r["document_revision_id"] for r in rows} == set(
        pdfs
    )  # every PDF carries chunks, nothing else does
    with open(
        os.path.join(ROOT, "contracts", "entities", "document.schema.json"),
        encoding="utf-8",
    ) as f:
        kinds = json.load(f)["$defs"]["Chunk"]["properties"]["unit_kind"]["enum"]
    assert set(BY_KIND) <= set(kinds)


def test_every_chunk_is_a_run_of_its_page_text_with_its_hash(rows, page_texts):
    for r in rows:
        text = page_texts[r["document_revision_id"]][r["page"] - 1]
        assert r["text"] and r["text"] in text, r["id"]
        assert r["text"] == canonical(r["text"]), r["id"]
        assert (
            r["quote_hash"]
            == quote_hash(r["text"])
            == hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
        )


def test_chunks_never_overlap_and_follow_text_order(rows, page_texts):
    by_rev = {}
    for r in rows:
        by_rev.setdefault(r["document_revision_id"], []).append(r)
    for rev, chunks in by_rev.items():
        text = " ".join(page_texts[rev])
        pos = 0
        for c in chunks:
            i = text.find(c["text"], pos)
            assert i >= pos, f"{c['id']} overlaps or precedes the chunk before it"
            pos = i + len(c["text"])


def test_no_chunk_exceeds_512_tokens(rows):
    tok = E.Embedder().tok
    longest = max(len(tok.encode(E.PASSAGE_PREFIX + r["text"]).ids) for r in rows)
    assert longest <= E.MAX_TOKENS == 512


def test_ids_and_ordinals_are_deterministic(rows, pdfs):
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == len(ids)
    by_rev = {}
    for r in rows:
        by_rev.setdefault(r["document_revision_id"], []).append(r)
    for rev, chunks in by_rev.items():
        assert [c["ordinal"] for c in chunks] == list(range(len(chunks)))
        assert [c["id"] for c in chunks] == [
            f"{rev}/c{c['ordinal']:03d}" for c in chunks
        ]
    fresh = []
    for p in corpus_files():
        if p.lower().endswith(".pdf"):
            fresh += C.chunk_document(p)[1]
    assert [{k: v for k, v in r.items() if k != "embedding"} for r in rows] == fresh


def test_every_chunk_carries_its_pinned_embedding(rows):
    assert all(len(r["embedding"]) == E.DIM for r in rows)
    for r in rows:
        assert abs(sum(x * x for x in r["embedding"]) - 1.0) <= 2e-4, r["id"]
    e = E.Embedder()
    first_of_kind = {}
    for r in rows:
        first_of_kind.setdefault(r["unit_kind"], r)
    for r in first_of_kind.values():
        assert e.embed(r["text"], E.PASSAGE_PREFIX) == r["embedding"], r["id"]
