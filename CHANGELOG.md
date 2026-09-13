# Changelog

This repository is the reference implementation: the ingestion, the coverage recipe, the rule-pack matcher, the
golden set and the bundle the application seeds from. Its versions are bundle versions, because the bundle is what
this repository publishes and what another repository consumes. Each entry names what changed in the corpus view,
never what changed in the corpus itself, which belongs to the organiser and is never modified.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and every entry carries the tag it was
released under. `git log --oneline` is the authority: nothing is listed here that is not in the history.

## [1.0.6] - 2026-09-13

### Added
- The eight P&ID sets are images, and the page renderer only rendered PDFs, so no drawing ever had a page
  derivative and the hotspot layer never drew the sheet it places its hotspots on. Images render to the same
  1200-wide metadata-free derivative: 96 documents rendered, 2 skipped (the workbook and the organiser's deck).

### Changed
- The corpus-redistribution guard's window matches the harness's own citation cut, so the guard can fire on the
  files it exists to guard.
- The gateway role contract declares the optional `retries` key the two long-cut roles set (D-27), with the strict
  check restored.

## [1.0.5] - 2026-09-08

### Changed
- The sources are formatted, so the format half of the lint gate is enforced rather than merely available:
  `ruff format --check` runs in CI and in `make check` beside `ruff check` and `mypy`.
- The recipe seal moves with the formatting, because it is a digest over the bytes of the two recipe sources. A
  key-by-key diff of the regenerated fixture shows exactly one changed key, `method.recipe_sha256`; every measured
  value is identical.

## [1.0.4] - 2026-09-08

### Added
- The integrity register carries the routing recommendation on the two findings that name a protective function.
- The reference implementation has continuous integration of its own: ruff, mypy, the Makefile documentation check
  and the corpus-reading suite, on every push and every pull request.

### Changed
- mypy runs with a real configuration (check_untyped_defs on, which first raised 64 errors, all fixed in the code
  and none silenced), and ruff pins 21 rule families beyond the defaults.
- The recipe seal is re-taken over the linted sources, with every measured value proved unchanged.

## [1.0.3] - 2026-09-07

### Changed
- The rule pack's moment vocabularies carry the cues a ladder and a proof test are asked for in plain words, so a
  question naming either infers its moment instead of losing the typed layer.

## [1.0.2] - 2026-09-07

### Added
- A span and a claim for every workbook row, so a work order or a proof test can be cited at all: 211 of 211 bound,
  against 12 before.

### Fixed
- The permit lines of a lesson are the safety bullets of section 2 and the permit, lock-out and car-seal
  requirements of section 3, not every line carrying the word permit.
- An instrument tag that names an equipment item is rejected at the candidate stage, so an unknown asset no longer
  resolves as known and the drawing says why a hotspot binds to nothing: 77 tags, against 87 before.

## [1.0.1] - 2026-09-06

### Fixed
- Three corpus defects the verification fleet found and proved: the failure-row population of the coverage recipe's
  C.1, the permissive-typed sidecar bindings, and the datasheet label-word collisions that bound a value to the
  wrong parameter.

## [1.0.0] - 2026-09-05

### Added
- The first admitted bundle: 98 files, 56 lessons, 211 work orders, 832 chunks with local embeddings, the coverage
  recipe frozen at t = 0.62 with a window of twice the field's word count, the rule pack, the golden set of 102
  cases and the fixture every displayed number binds to. Admitted by G1.
