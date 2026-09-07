# thehub-harness

**The reference implementation behind The Hub: it reads the CALIBER 2026 Case 1 corpus once, offline, with one
pinned extractor, and produces every typed package, every contract and every number the product and the submission
are allowed to state.**

This repository is the measurement half of a two-repository build. The product is
[`thehub-3v`](https://github.com/Finerium/thehub-3v), a Next.js application deployed at
**https://thehub-3v.vercel.app** behind login; credentials are issued by Team 3V to the CALIBER 2026 Committee.
Read that repository's README first if you want the product. Read this one if you want to check the arithmetic.

Team 3V, Politeknik Negeri Bandung. CALIBER 2026, Case 1: Manufacturing Knowledge Hub (AI-Powered Knowledge
Integration).

---

## What it is for

Three jobs, and nothing else.

1. **One extraction.** Every controlled document of the corpus is read exactly once, by `pdftotext -raw` build
   26.02.0, into one canonical form (NFKC, soft hyphens joined, whitespace collapsed). One extractor and one
   canonical form is an invariant: two extractors would mean two sets of numbers, and `make check` fails the build
   if `-layout` is invoked anywhere outside `legacy/`.
2. **One fixture.** `packages/fixtures.json` is the single file every number in the product, the deck, the README
   and the tests reads from. Nothing downstream types a figure. `contracts/fixtures.schema.json` is the key
   registry that makes a rename a build failure rather than a silent drift.
3. **One bundle.** `make bundle` writes the typed packages plus a manifest listing every file with its SHA-256, and
   then `harness/g1.py` admits or refuses it. Only an admitted bundle can seed a corpus version in the product.

`contracts/` is the one home of every JSON Schema (2020-12). The application derives its Zod from these files and
its Drizzle schema from the same names and enums; a name, a type or an enum that differs from the contract is a
blocker on both sides.

## Layout

| Path | What is in it |
| --- | --- |
| `harness/` | The pipeline: `pdftext`, `documents`, `workbook`, `opl`, `entities`, `integrity`, `coverage`, `debt`, `chains`, `dates`, `chunks`, `pages`, `embed`, `bundle`, `g1`, `release` |
| `contracts/` | Every JSON Schema, the bundle map, the API and deliverable contracts. **Frozen.** |
| `packages/` | The typed artefacts the harness writes, and `fixtures.json` |
| `rulepack/` | The safety-intent rule pack, `v1.json`, with its README |
| `golden/` | `cases.yaml`, the golden set, written from the case's own expectations before the answer lane was measured |
| `tests/` | pytest over the harness, the fixture, the rule pack and the contracts |
| `tools/` | The standing checks, including `no_corpus_in_repo.py` |
| `legacy/` | The prior harness, kept for comparison only, and excluded from every rule above |

## Run it

Requirements: Python 3.12 through [uv](https://docs.astral.sh/uv/), and poppler `pdftotext` build 26.02.0. The
corpus path is `$CASE1_CORPUS`, pointing at the organiser's "Case 1_ Manufacturing Knowledge Hub" directory. **The
corpus is never modified and never copied into this repository.**

```bash
make setup        # uv sync --frozen, then print the extractor build so a mismatch is visible immediately
make fixtures     # run the harness over the corpus and write packages/fixtures.json
make test         # pytest over the harness, the fixture, the rule pack and the contracts
make check        # test + contracts + the standing greps (one extractor, no corpus text in any tracked file)
make bundle       # chunks, page derivatives, embeddings, the bundle and its manifest, then G1 admission
make release      # dist/thehub-bundle-<version>.tar.gz plus SHA256SUMS, without the seed-time files
```

`make bundle` and `make release` need the corpus. `make test` and `make check` do not: they run against the tracked
packages and contracts, which is what a reviewer without the corpus can do.

## The numbers

**They are not on this page.** Every figure this project produces lives in `packages/fixtures.json` with the method
that produced it, and the product's README prints its table from that file through a script that fails CI when the
two disagree. A number restated on a front page is a number that can go stale, so this front page restates none.

What is worth knowing about how they are produced:

- The **coverage recipe is frozen and published**, not described. `fixtures.method` carries the recipe in words, its
  SHA-256, the stop list, the stop list's SHA-256, the window multiplier, the threshold and the comparison rule.
  Anyone can recompute a figure from that entry alone.
- **Two layers, always both.** The generous layer scans the whole lesson text; the strict layer scans the rebuilt
  header fields plus sections 1, 2, 3, 4 and 6, cut at the corpus's own watermark line, so a lesson that copies a
  work order's row back does not count as having taught anything.
- **The population is named beside every figure.** A coverage number without its population and its threshold is
  not a number this project will emit.
- **The coverage labels are machine-drafted.** `fixtures.coverage_labels.status` reads
  `machine_drafted_pending_human`, human adjudication is outstanding, and the published figures are therefore the
  lexical proxy with its agreement against the draft labels printed beside it.
- **The debt coefficients are an assumption**, labelled `ASSUMPTION` in the contract, in the fixture and on every
  surface that shows them.

## The corpus

The corpus is the property of PT Chandra Asri Pacific Tbk and is used for this entry only. It is **never** committed
here: no source file, no extracted text, no page image, and no run of its text longer than a citation appears in any
tracked file. `tools/no_corpus_in_repo.py` enforces that on every `make check`, and the seed-time artefacts that do
carry corpus text (`bundle/chunks.jsonl`, `bundle/pages/`, `packages/opls.json`) are produced only where the corpus
exists, listed in the manifest with their SHA-256 so the admission gate still verifies them, and excluded from both
the release tarball and the tracked tree.

The private mirror the CI reads through a read-only deploy key is
[`thehub-corpus`](https://github.com/Finerium/thehub-corpus).

## Licence and disclosure

**All rights reserved. The source is published for verification**, so that the judges, the organiser and any reader
of the CALIBER 2026 submission can reproduce every number this entry states. Read it, clone it and run it unmodified
to check the claims; quote short excerpts in a review with attribution. No other right is granted, and the
organiser's data is not covered by that grant and is not in this repository. The full text is the `LICENSE` file of
[`thehub-3v`](https://github.com/Finerium/thehub-3v/blob/main/LICENSE), which governs this repository on the same
terms.

The AI disclosure covering both repositories, including which models were used where and what a human decided, is
[`docs/DISCLOSURE-AI.md`](https://github.com/Finerium/thehub-3v/blob/main/docs/DISCLOSURE-AI.md) in the product
repository.

**This software is not a control system and has no write path toward one.** It reads documents and writes typed
files about them.
