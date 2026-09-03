# thehub-harness: one harness, one fixture, one bundle. Python 3.12 through uv; poppler pdftotext 26.02.0 pinned (ADR-005).
# The corpus path comes from $CASE1_CORPUS (the "Case 1_ Manufacturing Knowledge Hub" directory); the corpus is never modified.
PY ?= uv run python
FIXTURES = packages/fixtures.json

.PHONY: setup fixtures packages test bundle check contracts clean-cache

setup:                  ## install the locked environment (uv sync --frozen) and print the extractor build
	uv sync --frozen
	@pdftotext -v 2>&1 | head -1

fixtures:               ## run the harness over the corpus and write $(FIXTURES) (about 20 s)
	$(PY) -m harness.analyze_corpus --out $(FIXTURES)

packages:               ## rewrite the package artefacts that are pinned harness output (packages/chains.json)
	$(PY) -m harness.master --write-packages

test:                   ## pytest over the harness, the fixture, the rule pack and the contracts
	$(PY) -m pytest tests/ -q -p no:cacheprovider

bundle:                 ## build the package bundle of blueprint 9.1 under bundle/ with its manifest (T1)
	$(PY) -m harness.bundle --out bundle

contracts:              ## every JSON Schema under contracts/ is a valid 2020-12 document
	$(PY) tools/check_contracts.py

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
