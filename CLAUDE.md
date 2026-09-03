# thehub-harness

The reproducible measurement behind The Hub (CALIBER 2026 Case 1, Team 3V): ingestion of the supplied corpus through one
pinned text extractor, the frozen coverage recipe in two layers, the integrity rules, the causal-chain rule, the failure
families, the knowledge-debt ranking, the rule pack and its matcher, the golden set, the fixture every published number
reads from, and the package bundle the application seeds from.

## Commands
- `make setup` (uv sync --frozen; prints the extractor build, which must read `pdftotext version 26.02.0`)
- `make fixtures` (writes packages/fixtures.json from $CASE1_CORPUS), `make test`, `make contracts`, `make check`, `make bundle`
- `CASE1_CORPUS` points at your own copy of the corpus: the `Supporting Data/Case 1_ Manufacturing Knowledge Hub` directory.

## Layout
- `harness/` the reference implementation (pdftext, workbook, opl, coverage, integrity, dates, debt, rulepack, master, analyze_corpus, bundle)
- `packages/` pinned harness output and adopted artefacts (fixtures.json, chains.json, families.json, pid_sidecars/, hand_verified.json, coverage_labels.draft.json, adjudication_log.draft.md)
- `contracts/` every JSON Schema 2020-12 of blueprint section 9; the one home of the contracts, consumed by pointer from the application
- `golden/cases.yaml` the golden set; `rulepack/v1.json` the rule pack as data; `legacy/` the v1.0 scorer kept as evidence only
- `tests/` pytest; `tools/` fx resolver, computed counts, copy audit, banned strings, no-corpus-text check

## Conventions
- One extractor everywhere: `pdftotext -raw` build 26.02.0, then `canonical()`; no module reads document text another way.
- Every published number comes out of `packages/fixtures.json`; keys may be added, never renamed.
- Extracted text, chunks, page renders and full spans are never tracked; the A7 check fails CI on any run of corpus text longer than 200 characters or any image without a drawn twin.
- Adopted sidecars and hand-verified readings carry `basis: agent_transcription`, `review_status: pending` (ADR-007).
- Commits: `Ghaisan Khoirul Badruzaman <ghaisan.khoirul.b@gmail.com>`, English message, no trailers.
