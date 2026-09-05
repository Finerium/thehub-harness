# packages/

Pinned harness output and the adopted hand artefacts the harness reads as inputs. Every number a surface prints comes out
of `fixtures.json`; the other files are either written by a harness command or carry their own provenance label.

| file | what | written by |
|---|---|---|
| `fixtures.json` | the fixture: every key of the blueprint 10.5 registry plus the older spellings the v1.1 harness used | `make fixtures` (`harness/analyze_corpus.py`) |
| `chains.json` | the causal links of blueprint 9.4 (`harness.master.chains`) | `make packages` |
| `area_aliases.json` | area vocabulary per asset (`harness.integrity`, CD-16) | `make fixtures` |
| `families.json` | failure-family membership with the rationale per member; basis `agent_classification`, review pending (ADR-007) | adopted, hand-kept |
| `interlock_effects.json` | the column identity of every X in the eight cause-and-effect matrices (the raw text keeps only the count); every text field is re-derived from the sheet and any disagreement raises | adopted, hand-kept |
| `datasheet_spot.json`, `revision_spot.json` | 24 pinned datasheet values and the expected revision tuples, verified against the canonical text at fixture time | adopted, hand-kept |
| `coverage_labels.draft.json`, `labels_1.draft.json`, `labels_2.draft.json`, `adjudication_log.draft.md` | the machine-drafted coverage labels and their adjudication; status `machine_drafted_pending_human` until `coverage_labels.json` exists | adopted, machine-drafted |
| `hand_verified.json` | the eight P&ID sheet readings the integrity rules CD-2, CD-7, CD-8, CD-9 and CD-18 count; basis `agent_transcription`, review pending (D-12) | adopted, agent-transcribed |
| `pid_sidecars/set_0n.transcript.json` | the adopted transcript of each P&ID PNG in the shape `pid_sidecars/README.md` documents (every label, note and coordinate) | adopted, agent-transcribed |
| `pid_sidecars/set_0n.json` | the blueprint 9.3 `PidSidecar` derived from the transcript; what the bundle ships | `uv run python -m harness.analyze_corpus --write-sidecars` |

Files are written with `json.dump(sort_keys=True, indent=1, ensure_ascii=False)` plus a trailing newline, so re-serialising
reproduces them byte for byte and two runs on the same corpus give the same `fixtures.json`.

## The fixture key registry (blueprint 10.5)

`harness/analyze_corpus.py::registry` projects the 10.5 registry over the parts the modules compute: every registered key
exists at its registered path and `contracts/fixtures.schema.json` validates the file. The harness may add keys and never
rename one, so the older spellings stay beside the registered ones (`coverage_bands` beside `coverage.bands`, the top-level
`lead_time` beside `workbook.lead_time`, `demo_wo` beside `demo`, `labelled_draft` beside `coverage_labels`, `total` beside
`size` under `golden`, and so on). Where the registry names a path an older key already used with another shape, the
registered path carries the contract's shape and the older content sits under a sibling key:

| registered path (contract shape) | older content now at |
|---|---|
| `populations.<name>` (record counts) | `population_ids.<name>` (the sorted work-order numbers) |
| `families.r_by_tag.<tag>` (the share r) | `families.r_detail.<tag>` (rows, members, r) |
| `chains.links` (link count) | `chains.link_list` (the links; also `chains.json`) |
| `debt.coefficients` (`a`, `b`, `c`, `d`, basis `ASSUMPTION`) | `debt.coefficients_by_factor` (`D`, `C`, `k`, `r`) |
| `personnel.people` (head count) | `personnel.roster` (the people keyed by id) |
| `method.strict_sections` (`header`, `1`, `2`, `3`, `4`, `6`) | `method.strict_section_headings` (the headings as `harness.opl.STRICT_SECTIONS` spells them) |
| `method.labels_status` (`machine_drafted_pending_human` or `human_adjudicated`) | `method.labels_note` (the sentence the coverage module writes) |

Conventions the registry keys follow:

- A `share` (coverage cells, `coverage_labels`, `workbook.incomplete`, `workbook.lead_time`) is the one-decimal percentage
  the surfaces print divided by 100 (`0.246` for 14 of 57), so `tools/fx.py`'s `share1` format returns exactly that
  percentage and the older `pct` twin in the same object never disagrees with it.
- `method.recipe_sha256` is the SHA-256 over the bytes of `harness/coverage.py` and `harness/opl.py` in that order (the
  tokeniser, window and layers, and the strict-layer composition): a change to the recipe moves the fixture.
- `demo` carries the loop demo's work-order numbers; the build refuses to write them unless the analysis agrees (primary
  and backup uncovered in both layers at t = 0.62, contrast covered in the generous layer and uncovered in the strict one).
- `families.list` labels every family `agent_classification`, review `pending` (ADR-007); `recorded_root_cause` is the
  member's workbook root cause.
- `equipment_master[].service` is the datasheet SERVICE line; `interlock_ref` is the verbatim LOGIC No text of the C&E
  sheet (`N/A (control loop only)` for EA-5601); `unplanned_rows` are the unplanned breakdown rows, so
  `planned_rows + unplanned_rows = breakdown_rows`.

## P&ID sidecars

The transcript keeps every reading as it was adopted; the contract file re-spells it for the bundle:

| transcript | `PidSidecar` |
|---|---|
| `file` | `document_id` (the PNG file name as in the corpus; `documents.json` maps it to its document) |
| `title_block_as_drawn` cells joined with ` \| `, else `title_as_drawn` (`""` when the sheet has none) | `title_box` |
| `ref_dwg_as_drawn` (`""` when there is no box, Set 3) | `reference_box` |
| `notes_as_drawn`, `equipment_shown` | `notes`, `equipment_shown` |
| `instruments[]`: `as_drawn_text`, `bound_tag`, `role`, `setpoint_as_drawn`, `foreign`, `x`, `y` | `hotspots[]`: the same under `drawn_setpoint`, `x_frac`, `y_frac`; `id` is `set0n-nnn` in transcript order |
| `instruments[].note` on an unbound instrument | `hotspots[].unbound_reason` (null when there is no note) |
| `defects[].kind`, `detail` | `defects[].rule`, `detail` |
| `provenance` `{basis, by, date, review_status}` | `provenance` `{basis, alias, date, reviewed_by: null, reviewed_at: null, review_status}` |

The transcripts hold point estimates of each label's centre (about plus or minus 0.02 of the image), so `w_frac` and
`h_frac` are `0.0`: no box extent was read, and a renderer places its marker at (`x_frac`, `y_frac`). The transcript-only
readings (`tag`, `image_px`, `datasheet_cited_as_drawn`, `seq_cited_as_drawn`, `revision_block_as_drawn`, notes on bound
instruments) stay in the transcript; `hand_verified.json` carries the cited numbers and the foreign tags the integrity rules
count. To change a reading, re-open the PNG, edit the transcript, and rerun `--write-sidecars`.

## Provenance labels (D-12, ADR-007)

The sidecars and `hand_verified.json` were produced by an agent (role alias `EXEC-1`, 2026-08-27), so they carry
`basis: agent_transcription` and `review_status: pending` with `reviewed_by` and `reviewed_at` null; the interface says so
wherever a hotspot or a sheet reading is shown. A human review records the reviewer alias in `reviewed_by`, the timestamp
in `reviewed_at` and flips `review_status` to `reviewed`; `basis` stays `agent_transcription` because it records how the
reading was produced, and only a reading re-transcribed from the image by a person carries `manual` (ADR-007).

The sidecars carry the labels in `provenance` (the 9.3 `PidSidecar` type). `hand_verified.json` has no section 9 type
(`contracts/bundle_map.json` lists it with `schema: null`), so it carries the same four fields at the top level of the
file, with the `PidSidecar.provenance` enums; `verified_by` and `verified_on` on the file and on every set are the
transcriber's alias and date, not a review.

## Checks

```sh
# the fixture against the registry, a sidecar against its type (both from the repository root)
uv run python -c "import json,jsonschema,os;from referencing import Registry,Resource;R=Registry().with_resources([(s['\$id'],Resource.from_contents(s)) for s in (json.load(open(os.path.join(d,f))) for d,_,fs in os.walk('contracts') for f in fs if f.endswith('.schema.json'))]);S=json.load(open('contracts/fixtures.schema.json'));jsonschema.Draft202012Validator(S,registry=R).validate(json.load(open('packages/fixtures.json')));print('fixtures ok')"
uv run python -c "import json,jsonschema,os;from referencing import Registry,Resource;R=Registry().with_resources([(s['\$id'],Resource.from_contents(s)) for s in (json.load(open(os.path.join(d,f))) for d,_,fs in os.walk('contracts') for f in fs if f.endswith('.schema.json'))]);A=json.load(open('contracts/entities/asset.schema.json'));jsonschema.Draft202012Validator({'\$ref':A['\$id']+'#/\$defs/PidSidecar'},registry=R).validate(json.load(open('packages/pid_sidecars/set_01.json')));print('set_01 ok')"
uv run python -c "import json;h=json.load(open('packages/hand_verified.json'));assert (h['basis'],h['review_status'],h['reviewed_by'],h['reviewed_at'])==('agent_transcription','pending',None,None) and len(h['sets'])==8;print('hand_verified ok')"
uv run python tools/computed.py            # golden counts in the 9.11 order
uv run python tools/no_corpus_in_repo.py   # no run of corpus text of 200 characters or more in any tracked file
```
