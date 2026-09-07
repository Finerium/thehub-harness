# harness/ - one harness, one fixture

Every number in The Hub PRD v1.1 is read from `packages/fixtures.json`, which only `harness/analyze_corpus.py` writes.
Nothing in the PRD, the figures or the deck may carry a number that is not in that file (Revision Plan section 5,
Addendum A D10). The corpus under `Supporting Data` is read-only and is never redistributed (A7).

## Run

```bash
export CASE1_CORPUS="/path/to/CALIBER 2026 - The Case/Supporting Data/Case 1_ Manufacturing Knowledge Hub"   # default in harness/config.py
make setup               # uv sync --frozen, then print the extractor build so a mismatch is visible immediately
make fixtures            # run the harness over the corpus and write packages/fixtures.json   (about 20 s)
make packages            # rewrite the package artefacts that are pinned harness output (packages/chains.json)
make test                # pytest over the harness, the fixture, the rule pack and the contracts
make contracts           # every JSON Schema under contracts/ is a valid 2020-12 document; bundle/ validates when present
make check               # test + contracts + the standing greps (D10 extractor rule, P9 sed pitfall, A7 no corpus text)
make chunks              # structural chunks of the corpus PDFs into bundle/chunks.jsonl (seed-time, never tracked)
make pages               # metadata-free page derivatives into bundle/pages (seed-time, never tracked)
make embed               # add the pinned local embedding to every chunk
make bundle              # chunks + pages + embed, then the bundle of blueprint 9.1 with its manifest, then G1 admission
make g1                  # admit bundle/ or name every violation (exit 1)
make release             # dist/thehub-bundle-<version>.tar.gz without the seed-time files (D-17), plus SHA256SUMS
make clean-cache         # drop the pdftotext cache and the Python caches (the next run re-extracts every PDF)
python3 harness/analyze_corpus.py --corpus DIR --out packages/fixtures.json [--t 0.62] [--legacy-window | --no-legacy-window]
```

Requirements: Python 3.12+ (standard library + `openpyxl`), poppler `pdftotext`/`pdfinfo` on PATH (D10: poppler >= 24;
the version line is recorded in `inventory.extractor`). `.cache/` holds the extracted text keyed by file digest
(`make clean-cache` drops it). Two runs on the same corpus are byte-identical (`json.dump(sort_keys=True, indent=1)`,
no timestamps, no paths, sorted ids everywhere); the fixture must be regenerated and committed whenever a harness module
changes.

- `--t` sets the threshold of the derived tables (bands, by-work-type, by-tag, debt, `meta.t`); the threshold rows of
  every coverage table always include it. Default 0.62 (LD-07).
- `--legacy-window` (default on) runs the v1.0 scorer in sorted lesson order so the fixture records the v1.0 headline as
  evidence (`legacy`, about 13 of the 20 s). It is on by default because the whole run stays well under a minute;
  `--no-legacy-window` writes `legacy: null` for a quick iteration run. Never quote a `legacy` number as a finding (P6).
- `packages/interlock_effects.json` is required. It is the one hand-typed input to `master`: the X-mark to EFF column
  mapping of the eight cause-and-effect matrices, which `pdftotext -raw` cannot express (only the X count survives).
  Every other field in it is re-derived from the raw text on every run and a disagreement raises, so it can add the
  column mapping and the effect final-element labels but can never overwrite what a sheet says.
- `packages/coverage_labels.json` is optional (D6). While it is absent `labels_agreement` and `labelled` are `null` and
  `method.labels_status` is `pending (proxy numbers in use)`; the prose must carry the "pending" sentence (P5).
- `packages/coverage_labels.draft.json` is the machine-drafted adjudication of the two independent label sets
  (`labels_1.draft.json`, `labels_2.draft.json`; see `packages/adjudication_log.draft.md`). While the human file above is
  absent and this one is present, `labels_agreement_draft` and `labelled_draft` carry the same shapes computed against it
  and `method.labels_status` names the draft, but `labels_agreement` and `labelled` stay `null`, so no deck number can be
  read off a machine label. The human file replaces it before the deck freeze (D6, OQ-6).

Modules: `config` (paths), `pdftext` (inventory, `pdftotext -raw`, canonical form), `workbook` (typed rows, populations),
`opl` (lesson parser), `coverage` (frozen recipe, two layers, verbatim, labels, legacy), `dates` (dates, cadence,
latency, lead time, registry), `integrity` (CD-1..CD-18), `master` (equipment master, C&E rows, proof tests, personnel,
families, chains, spot fixtures), `debt` (CR-11 ranking), `analyze_corpus` (the CLI). Each `compute(ctx)` takes
`ctx = {rows, pops, opl, parsed, files}` (the CLI adds `t` and `legacy_window`; `debt` also receives the upstream
`coverage`, `equipment_master`, `families`). `analyze_corpus` also imports `tools.computed.golden_block`, the one
non-corpus input: `golden/cases.yaml` is repository data, so the golden-set size reaches the fixture through the same
reader the PRD's `<!-- computed:golden_table -->` block uses and the two can never disagree.

## Fixture key map

Population names: the plan's `failure66 / unplanned57 / planned8 / unplanned_breakdowns23` are the fixture's
`failure / unplanned_failure / planned_flagged / unplanned_breakdowns` (`harness/workbook.populations`). The plan's
`routine` (145 rows) is **not** published: the fixture ships `all` (211, routine rows included) and the routine subset is
`set(populations['all']) - set(populations['failure'])`. No published number depends on the 145 set (Addendum P14). Numbers
enter prose only through fx directives (`tools/fx.py`), e.g. `<!-- fx:coverage.generous.unplanned_failure[t=0.62].uncovered -->14`.

| Key | Meaning |
|---|---|
| `golden` | `total` and `by_category` read off `golden/cases.yaml` by `tools.computed.golden_block`; the only fixture key that does not come from the corpus, so a chapter may print the golden-set size from the fixture as well as from the file |
| `inventory` | `files` (98), `by_class`, `by_extension`, `opl_count` (56), `corpus_sha256` (digest over sorted relative paths + file digests), `extractor` ("pdftotext -raw (pdftotext version ...)") |
| `workbook` | `rows`, `breakdowns` (Breakdown = Yes), `downtime_h`, `breakdown_cost_idr`, `all_cost_idr`, `labor_h`, `breakdown_kinds.{unplanned,planned_flagged}.{count,downtime_h,cost_idr}`, `work_types`, `disciplines`, `priorities`, `criticality_counts`, `status`, `incomplete.{count,by_work_type,ids}` (F3), `window` |
| `populations` | `{name: sorted WO ids}` for the five populations |
| `method` | the recipe text, `t`, `thresholds`, `window_multiplier`, extractor and canonical form, `strict_rule` and `strict_sections` (the composed strict layer, P10; they replace v1.0's `strip_rule` / `strip_flags` / `strip_replacement`), skip rule, `stop_list` (65 words) and `stop_list_sha256` (P5), `unscoreable_ids`, `labels_status` |
| `coverage` | `{layer: generous or strict}` -> `{population}` -> rows `[{t, n, uncovered, pct, unplanned_bd, downtime_h, cost_idr, uncovered_ids, by_tag}]`, one row per threshold (0.50 ... 0.75) |
| `coverage_scores` | `{wo: {generous: {score, unit}, strict: {score, unit}}}`; `unit` = [field, lesson] that produced the score |
| `coverage_bands` | `unplanned_failure.{none, table_only, taught}` and their ids: no lesson / copied row only / taught (D1) |
| `coverage_by_work_type` | generous layer at `t` over all 211: `work_types.{type}.{n, uncovered}` and `breakdowns` split (HN-V-01) |
| `coverage_by_tag` | per asset: `n_unplanned_failure`, `uncovered_generous`, `uncovered_strict` |
| `verbatim` | `rule`, then per layer `by_field`, `any`, `any_ids`: narrative fields found verbatim in a same-asset lesson (CF-V-01) |
| `labels_agreement`, `labelled` | precision / recall of the proxy against `coverage_labels.json` and the labelled coverage row; `null` until D6 |
| `labels_agreement_draft`, `labelled_draft` | the same two shapes against the machine-drafted `coverage_labels.draft.json`; `null` once the human file exists (OQ-6) |
| `legacy` | the v1.0 scorer's rows over all 211 (`evidence_only`), with `breakdowns_all / downtime_h_all / cost_idr_all` counting every flagged row as v1.0 did; `null` with `--no-legacy-window` |
| `dates` | Date of Sharing statistics: `dated`, `first`, `last`, `span_days`, `gaps.{median,mode,mode_count,distribution}`, `cadence` and `set_start` per set, `last_breakdown_report`, `gap_to_first_lesson_days`, `any_overlap` (lesson campaign vs record window), `workbook_window` (CF-03, HN-20) |
| `latency` | the six failure-to-lesson `pairs`, `days`, `median_days`, `pairing_basis` (DP-12, HN-V-03) |
| `lead_time` | Start_Date - Report_Date in hours: `n`, `median_h`, `ge24_n`, `ge24_pct`, `min_h`, `max_h`, `by_work_type` |
| `lessons` | registry of the 56 lessons (ids only, no names: A2) with `classification`, `discipline`, `approvers`, `reviewers_per_set`, `foreign_footer_lessons`, `no_crossref_line_lessons` |
| `integrity` | `CD-1 ... CD-18` (CD-3 deleted), each `{rule, definition, unit, count, items, basis, severity, observation_only, ...}`; `total` = sum of the defect rules (CD-15 and CD-16 are observations); `cd4_emergency` (A1); `no_sif_fixture` (DP-06) |
| `equipment_master` | one row per asset: names, area and criticality from workbook and datasheet, interlock from workbook majority and C&E sheet, `sil_sheet`, work-order counts, flagged / planned / unplanned breakdowns, hours, costs, `incomplete_rows` |
| `interlock_rows` | per asset: `seq` (LOGIC No), `kind`, C&E header (doc, work no, rev, logic no, SIL), `effects` (`id`, `action`, `final_element`), typed `rows` (`row_kind`, setpoint, `comparator`, voting, `effects`, `x_count`, `effects_basis` "H+M"), `start_permissives`, verbatim `notes`, boilerplate flags (FR-104, CF-20). The X column mapping and the effect final elements come from `packages/interlock_effects.json`, typed off the rendered sheets; every other field of that file is re-derived from the raw text and a disagreement raises |
| `proof_tests` | `classes.{sis_proof_test, sil_logic_proof_test, calibration_proof_test, psv_statutory_test}.{count, items}`, `last_by_asset`, `total` (P3) |
| `personnel` | person table keyed by EMP id with role class and sources, `anomalies`, OPL-only managers, reviewers who are WO approvers (CF-18) |
| `families` | `packages/families.json` checked against the workbook plus `r_by_tag` (share of unplanned-failure rows in a family, CR-20) |
| `chains` | CR-12 causal links (`links`, `total`, `by_tag`, `lexicon`, window) = `packages/chains.json` |
| `datasheet_spot` | `packages/datasheet_spot.json` entries with `verified` against the datasheet text (CR-07) |
| `revision_spot` | per asset and document class: doc no, revision, issue status, revision history (A4) |
| `debt` | CR-11: `coefficients` (ASSUMPTION), `k_mapping`, `D_max`, `C_max`, `per_asset[{tag, uncovered_ids, D, C, k, r, incomplete_uncovered, score}]`, `ranking[{rank, tag, score}]` |
| `meta` | `harness_version`, `t`, `recipe`, `legacy_window`, `note` |

## Number provenance quick map (PRD number -> fixture key)

The value column is a snapshot of `packages/fixtures.json`, which is the authority; `make check` pins the strict
headline and the three bands so this table cannot drift away from the fixture unnoticed.

| Number in the PRD | Key (fx directive path) | Value on 2026-08-30 |
|---|---|---|
| files / lessons / work orders / flagged breakdowns / hours / cost | `inventory.files`, `inventory.opl_count`, `workbook.rows`, `workbook.breakdowns`, `workbook.downtime_h`, `workbook.breakdown_cost_idr`, `workbook.all_cost_idr` | 98 / 56 / 211 / 31 / 434.0 h / IDR 413,345,000 / 537,770,000 |
| the 57 unplanned-failure records; 23 unplanned breakdowns (270.0 h, IDR 344,075,000); 8 planned rows flagged breakdown (164.0 h, IDR 69,270,000) | `populations.unplanned_failure\|len`, `workbook.breakdown_kinds.unplanned.*`, `workbook.breakdown_kinds.planned_flagged.*` (= `integrity.CD-6`) | 57; 23; 8 |
| headline: uncovered in no lesson at all (generous) | `coverage.generous.unplanned_failure[t=0.62].{uncovered,pct,unplanned_bd,downtime_h,cost_idr}` | 14 (24.6 %), 5 breakdowns, 74.5 h, IDR 93,721,000 |
| in no lesson beyond a copied row (strict) | `coverage.strict.unplanned_failure[t=0.62].{uncovered,pct,unplanned_bd,downtime_h,cost_idr}` | 41 (71.9 %), 14 breakdowns, 146.0 h, IDR 198,418,000 (composed strict layer cut at the page watermark, P10 + P10b) |
| strict ladder 0.50 / 0.55 / 0.60 / 0.65 / 0.70 / 0.75 | `coverage.strict.unplanned_failure[t=...].uncovered` | 32, 32, 41, 41, 43, 52 (breakdowns 12, 12, 14, 14, 15, 19; 132.0, 132.0, 146.0, 146.0, 158.0, 182.0 h) |
| the three bands of slide 2 (D1) | `coverage_bands.unplanned_failure.{none,table_only,taught}` | 14 / 27 / 16 |
| band flatness (t = 0.50 ... 0.70) | `coverage.generous.unplanned_failure[t=0.50].uncovered` ... `[t=0.70]` | 13, 13, 14, 14, 14, 14 |
| all-211 figure (appendix only, "routine included") | `coverage.generous.all[t=0.62].{uncovered,pct}`, `coverage.strict.all[t=0.62].{uncovered,pct}` | 143 (67.8 %); 190 (90.0 %) |
| by work type (HN-V-01) | `coverage_by_work_type.work_types.{type}.{n,uncovered}` | Predictive 42/42, Inspection 26/30, Preventive 55/68, Calibration 4/12, Overhaul 3/6, Corrective 13/53 |
| per-asset uncovered | `coverage_by_tag.tags.{tag}.{n_unplanned_failure,uncovered_generous,uncovered_strict}` | YD-2301 4/8, CT-7801 2/7, GA-1201A 2/7, KC-4501 2/8, ... |
| verbatim reuse | `verbatim.generous.by_field.{Problem_Description,Root_Cause,Corrective_Action}`, `verbatim.generous.any` | 47 / 45 / 42; 47 work orders |
| verbatim reuse, strict layer (the copied rows are gone, so nothing survives) | `verbatim.strict.by_field.*`, `verbatim.strict.any` | 0 / 0 / 0; 0 work orders (P10; was 1, WO-240062) |
| WO-240060 pasted-table example; WO-240007 coupling cluster | `coverage_scores.WO-240060.{generous,strict}.score`, `coverage_scores.WO-240007.generous.score` | 1.0 / 0.2; 0.4286 |
| stop list | `method.stop_list_size`, `method.stop_list_sha256` | 65; 8262d512... |
| strict layer, stated in the method chip | `method.strict_rule`, `method.strict_sections` | composed from the parsed lesson; identity header + sections 1, 2, 3, 4, 6 |
| golden-set size and category split (Ch. 21, App. D) | `golden.total`, `golden.by_category.{category}` | 102; Trap integrity 19, Grounded answering 14, False abstention 11, Safety refusal 11, Adversarial phrasing 10, Abstention 9, Traceability 8, Loop 8, Safety-adjacent served 5, Moment-shaped answers 4, Operational context 3 |
| draft label agreement (evidence, never a deck number) | `labels_agreement_draft.{generous,strict}.{tp,fp,fn,tn,precision,recall}`, `labelled_draft.{uncovered,pct,unplanned_bd,downtime_h,cost_idr}` | generous 42/1/5/9 (P 0.977, R 0.894), strict 16/1/31/9 (P 0.941, R 0.340); 10 uncovered (17.5 %), 3 breakdowns, 34.5 h, IDR 44,256,000 |
| 56 dated lessons, 101-day campaign, gaps, four-day cadence, 114-day gap | `dates.dated`, `dates.span_days`, `dates.gaps.median`, `dates.gaps.mode`, `dates.gaps.mode_count`, `dates.cadence.{tag}`, `dates.gap_to_first_lesson_days` | 56; 101; 1; 1 x28; [4,4,4,4,4,4]; 114 |
| latency 210 ... 730 days, median | `latency.days`, `latency.median_days` | [210, 220, 442, 503, 528, 730]; 472.5 |
| notification lead time | `lead_time.median_h`, `lead_time.ge24_pct`, `lead_time.ge24_n`, `lead_time.min_h`, `lead_time.max_h` | 34.0 h; 64.5 %; 136; 1-72 |
| integrity register total and rules | `integrity.total`, `integrity.CD-n.count` | 174; CD-1 28, CD-2 6, CD-4 26, CD-5 5, CD-6 8, CD-7 4, CD-8 1, CD-9 4, CD-10 2, CD-11 2, CD-12 38, CD-13 35, CD-14 11, CD-15 123 (obs.), CD-16 8 (obs.), CD-17 1, CD-18 3 |
| foreign cross-references 28 of 56; 5 without a line; 26 incomplete closeouts; 3 of 3 emergency jobs uncosted | `integrity.CD-1.count`, `integrity.CD-5.count`, `integrity.CD-4.count`, `integrity.cd4_emergency` | 28; 5; 26; 3 |
| proof tests (FR-116) | `proof_tests.classes.{class}.count`, `proof_tests.total` | 18 / 5 / 7 / 3 = 33 |
| SIL and interlock per asset | `equipment_master[tag=...].sil_sheet`, `.interlock_sheet` | GA-1201A SIL 1 ... EA-5601 none |
| C&E rows, X-mark columns and final elements (FR-104) | `interlock_rows.{tag}.rows[].{effects,x_count,effects_basis}`, `.effects[].final_element` | 39 rows, 34 effect columns, 111 X marks, 29 permissives over eight sheets; every row `effects_basis` "H+M" |
| knowledge-debt top three (CR-11) | `debt.ranking[0..2].{tag,score}` | YD-2301 0.9375, KC-4501 0.5497, GA-1201A 0.3891 |
| causal links (19.4) | `chains.total`, `chains.by_tag.GA-1201A` | 18; 4 |
| family recurrence r | `families.r_by_tag.{tag}.r` | KC-4501 0.625, CT-7801 0.4286, ... |
| v1.0 headline (evidence only, CHANGELOG) | `legacy.all[t=0.62].{uncovered,breakdowns_all,downtime_h_all,cost_idr_all}` | 158; 13; 238.5 h; IDR 178,870,000 |
| corpus identity | `inventory.corpus_sha256`, `inventory.extractor` | 918706e4...; pdftotext -raw (pdftotext version 26.02.0) |

## The extractor rule (D10)

One text extractor everywhere: `pdftotext -raw` (poppler >= 24) through `harness.pdftext.pdf_text`, then the canonical form
of PRD 19.5 (`harness.pdftext.canonical`: NFKC, soft hyphens joined, whitespace collapsed to one space, trimmed; case and
punctuation kept). No module may call `pdftotext` in its layout mode or read text through pypdf / pdfplumber / pymupdf (pymupdf is
for page rendering only). The layout mode interleaves table columns and under-detects verbatim rows (34 vs 47 work
orders, P4); `-raw` keeps content-stream order, which is why some troubleshooting cells of the DC-3401A lessons appear after
section 6, and in OPL-DC-3401A-07 after the "Prepared by" footer (CD-12 scans the whole lesson deliberately; the strict
layer must not see them, which is why it is composed from the parsed sections rather than stripped, P10). Every
coverage literal in the plan was an interim proxy until the first `-raw` run; the values that run printed are the test
expectations (regression floor) and every prose figure follows them through the fixture (OQ-8).

Inventory: `corpus_files` skips `.DS_Store`, `Thumbs.db`, `desktop.ini`, `._*` and `__MACOSX`; the v1.0
`validate_corpus.py` printed 101 files on macOS because it skipped only `._*` (HN-11).

## The sed pitfall (Addendum P9)

On macOS BSD `sed`, `[ \t]` inside a bracket expression is a literal backslash plus the letter `t`, so a "whitespace"
class silently eats the letter t next to spaces; this produced a false "dropped-t" artefact during the audit. Never write
that bracket expression in `sed`; whitespace collapsing is done in Python (`re.sub(r"\s+", " ", s)`), and `make check`
greps the Makefile and `tools/` for it.

## Plan literals that moved under -raw (Addendum D10 re-freeze, reported at checkpoint C1)

| Plan (section 5.7 / 5.8, Addendum) | Fixture |
|---|---|
| strict layer defined as "the section 5 span stripped from every lesson" (5.7 item 3) | composed from the parsed lesson: identity header + sections 1, 2, 3, 4, 6 (`method.strict_rule`). Stripping leaks whatever the extractor places outside the span, which is how WO-240062 scored 1.0 strict off a copied row (P10) |
| strict unplanned-failure at 0.62: 42 (73.7 %) / 14 breakdowns / 146.0 h / IDR 198,418,000 | 41 (71.9 %) / 14 / 146.0 h / IDR 198,418,000 |
| strict band 0.55 / 0.70 / 0.75: 32 / 44 / 53 (breakdowns 12 / 15 / 19; 132.0 / 158.0 / 182.0 h; 178.7 / 216.0 / 260.4 M) | 32 / 43 / 52 (breakdowns 12 / 15 / 19; 132.0 / 158.0 / 182.0 h; 178.7 / 216.0 / 260.4 M) |
| strict all-211: 188 (89.1 %) | 190 (90.0 %) |
| band flatness "142-143 of 211" for t = 0.50 to 0.65 (5.7 item 1) | 141 / 141 / 143 / 143 / 143 at t = 0.50 / 0.55 / 0.60 / 0.62 / 0.65, so the range is 141-143 (the 57 population is 13-14, as the plan says) |
| bands none / table_only / taught: 14 / 28 / 15 (D1 proxy) | 14 / 27 / 16 |
| generous all-211 at 0.55: 142 | 141 (0.62: 143 and 0.75: 160 unchanged) |
| CD-12 about 35 cells in 17 lessons (P2 estimate) | 38 cells in 20 lessons; register total 174 (171 under the estimate) |
| verbatim under the layout extractor: 34 work orders (RC 31 / PD 15 / CA 18), and "the harness pins one extractor (`pdftotext -layout`, cached)" (5.7 item 7) | the harness pins `pdftotext -raw` (D10 / P4) and the fixture carries only the `-raw` counts: generous 47 work orders (PD 47 / RC 45 / CA 42), strict 0 |
| plan Task 1.2 legacy test as written | holds over all 31 flagged rows: 158 / 13 / 238.5 h / IDR 178,870,000 (unplanned-only 8 / 108.5 h / 124,716,000) |
| `revision_spot` "24 entries" (A4) | 32 (four document classes x eight assets) |
| four-link GA-1201A chain into WO-240002 (19.4) | the CR-12 noun rule gives 4 GA-1201A links on WO-240003/004/007/013; none reaches WO-240002 |

Unchanged and reproduced exactly: the whole generous layer (14 / 5 / 74.5 h / IDR 93,721,000 with the same fourteen ids,
the same per-asset split and the same 0.55 / 0.70 / 0.75 ladder of 13 / 14 / 20); band 13, 13, 14, 14, 14, 14; 143
(67.8 %); by-work-type (Predictive 42/42 ... Corrective 13/53, breakdowns 9 of 31 with 4
planned); generous verbatim 47; 56 / 101 / 1 / 28 / 114; latency; lead time; CD-1 28, CD-4 26, CD-6 8, CD-13 35 and the
rest of the register (total 174); proof tests 18 / 5 / 7 / 3; the debt ranking except KC-4501 (0.5372 -> 0.5497 when
PS-09 moved WO-240091 into its own lubrication family). The strict layer moved twice. P10 (compose, do not strip) moved
five of the 211 strict scores: WO-240062 (1.0 -> 0.6, now uncovered, the whole 128.0 -> 138.0 h and 170,042,000 ->
182,314,000 move), WO-240151 / WO-240152 / WO-240153 (0.75 -> 0.5, all-211 only) and WO-240112 (0.6 -> 0.8, now covered).
Only the first is a leak; the other four move because the composed text is shorter and re-ordered, so one window spans a
different set of tokens. P10b (cut every section at the page watermark) then moved one more, WO-240056 (0.7778 -> below
threshold, now uncovered: 138.0 -> 146.0 h and 182,314,000 -> 198,418,000, all-211 189 -> 190, bands 14 / 26 / 17 ->
14 / 27 / 16), because `key_learning` had swept in a truncated copy of that row's Corrective_Action. That re-ordering also means a strict score can exceed its generous twin: WO-240005 (0.5 generous, 0.5556 strict) is
the only such case in the 211, and it is not a failure row, so generous-uncovered stays a subset of strict-uncovered in
every population the deck quotes.

## Tests

`tests/test_<module>.py` per module and `tests/test_fixtures.py` over the written fixture. Every expectation is a value
observed by running the module and cross-checked by a throwaway script on a different code path (openpyxl and
`pdftotext` called directly, naive windows, brute-force regexes); the docstrings say how. A value that differs from a plan
literal is asserted as observed and listed above, never forced.
