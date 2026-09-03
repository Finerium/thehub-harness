#!/bin/bash
# AC-FND-05 / A7: fail when any tracked or untracked-but-unignored file carries a run of corpus text longer than
# 200 characters, or when an image in the publishable tree has no drawn twin (a rasterised corpus page).
# Needs $CASE1_CORPUS (CI checks the corpus out through the read-only deploy key). Wraps tools/no_corpus_in_repo.py.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${CASE1_CORPUS:-}" ]; then echo "no-corpus-text: CASE1_CORPUS is not set"; exit 2; fi
exec uv run python tools/no_corpus_in_repo.py "$@"
