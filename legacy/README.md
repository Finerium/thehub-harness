# legacy/ - the v1.0 computation, kept as evidence only

These two scripts are the v1.0 computation. `validate_corpus.py`'s date parser and coverage matcher are broken (0/56
dates, 99-100 percent uncovered); `validate_fix.py` reproduces the v1.0 headline but compares a field of length L with a
window of length 1.5L (ratio capped at 0.80) and its result depends on file order. They are kept as evidence for the
CHANGELOG and must not be run for figures.

Details, with the finding IDs they document (Revision Plan section 5 and Task 1.8):

- `validate_corpus.py` (LD-03, HN-12, EC-V-03): the Date of Sharing sits on the line after its header, so the parser finds
  0 of 56 dates and fails all six latency pairs; its matcher compares whole fields with single `-layout` lines, so it prints
  99-100 percent uncovered at every threshold. On macOS it counted 101 files because it skipped only `._*` files and not
  `.DS_Store` (HN-11). The v1.0 README credited it with the coverage numbers; they came from `validate_fix.py`.
- `validate_fix.py` (LD-01, HN-02, HN-04): `best_ratio` slides a window of `L + step` characters (`step = max(20, L // 2)`),
  so a perfect non-verbatim alignment scores at most 0.80 and "uncovered at t = 0.62" mostly means "not copied verbatim";
  lessons are concatenated in `os.walk` order and the window phase depends on the concatenation offset, so the same code
  prints 158, 159 or 160 uncovered depending on file order. Both scripts pin `pdftotext -layout` and the old
  `/home/claude/...` corpus path; neither is imported by anything.

The v1.1 harness re-runs that scorer verbatim (`harness/coverage.py::best_ratio`, lessons concatenated in sorted lesson-id
order) only to record the v1.0 headline inside the fixture (`fixtures.json["legacy"]`, 158 / 13 / 238.5 h / IDR 178,870,000
at t = 0.62, `evidence_only: true`); `--no-legacy-window` skips it. Every published number comes from the frozen recipe
in `harness/coverage.py` instead (Revision Plan 5.7, Addendum D10).

`legacy/audit_reference/` holds the audit's reference recipe (`analyze_corpus.py`: `tokens`, `STOP`; `recipe_check.py`:
`contain_doc`; `recipe.json`, `test_analyze_corpus.py`). `harness/coverage.py` ports those three functions verbatim (HN-07);
the copies here are the provenance of that port and are not run by the build either.
