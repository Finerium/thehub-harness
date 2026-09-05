# thehub-harness: one harness, one fixture, one bundle. Python 3.12 through uv; poppler pdftotext 26.02.0 pinned (ADR-005).
# The corpus path comes from $CASE1_CORPUS (the "Case 1_ Manufacturing Knowledge Hub" directory); the corpus is never modified.
PY ?= uv run python
FIXTURES = packages/fixtures.json

.PHONY: setup fixtures packages test chunks pages embed bundle g1 release check contracts clean-cache

setup:                  ## install the locked environment (uv sync --frozen) and print the extractor build
	uv sync --frozen
	@pdftotext -v 2>&1 | head -1

fixtures:               ## run the harness over the corpus and write $(FIXTURES) (about 20 s)
	$(PY) -m harness.analyze_corpus --out $(FIXTURES)

packages:               ## rewrite the package artefacts that are pinned harness output (packages/chains.json)
	$(PY) -m harness.master --write-packages

test:                   ## pytest over the harness, the fixture, the rule pack and the contracts
	$(PY) -m pytest tests/ -q -p no:cacheprovider

chunks:                 ## structural chunks of the corpus PDFs into bundle/chunks.jsonl (seed-time, never tracked)
	$(PY) -m harness.chunks --out bundle/chunks.jsonl

pages:                  ## metadata-free page derivatives into bundle/pages (seed-time, never tracked)
	$(PY) -m harness.pages --out bundle/pages

embed:                  ## add the pinned local embedding to every chunk (one-time: $(PY) -m harness.embed --pin)
	$(PY) -m harness.embed --chunks bundle/chunks.jsonl

bundle: chunks pages embed   ## build the package bundle of blueprint 9.1 under bundle/ with its manifest, then admit it (G1)
	$(PY) -m harness.bundle --out bundle
	$(PY) -m harness.g1 bundle

g1:                     ## admit bundle/ or name every violation (exit 1)
	$(PY) -m harness.g1 bundle

release:                ## dist/thehub-bundle-<version>.tar.gz without the seed-time files (D-17), plus SHA256SUMS
	$(PY) -m harness.release --bundle bundle --out dist

contracts:              ## every JSON Schema under contracts/ is a valid 2020-12 document; bundle/ validates against the map when present
	$(PY) tools/check_contracts.py
	@if [ -d bundle ]; then $(PY) tools/validate_bundle.py bundle; fi

check: test contracts   ## tests + contracts + the standing greps (D10 extractor rule, P9 sed pitfall, A7 no corpus text)
	@echo "--- D10/P4: no -layout invocation outside legacy/"
	@! grep -rnI -e "'-layout'" -e '"-layout"' -e 'pdftotext -layout' harness/ tools/ tests/ golden/ rulepack/ --exclude=README.md --exclude-dir=__pycache__ || { echo "FAIL: pdftotext -layout invoked outside legacy/ (ADR-005)"; exit 1; }
	@echo "--- P9: no bracket-tab expression in Makefile or tools/"
	@! grep -rn '\[ \\t\]' Makefile tools/ || { echo "FAIL: bracket-tab expression"; exit 1; }
	@echo "--- A7: no run of corpus text longer than 200 characters in any tracked file; no un-drawn image"
	$(PY) tools/no_corpus_in_repo.py

clean-cache:            ## drop the pdftotext cache and Python caches (the next run re-extracts every PDF)
	rm -rf .cache .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
