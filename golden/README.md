# golden/ - the evaluation set is a file, not a number

`golden/cases.yaml` is the golden set of blueprint section 9.11: 102 `GoldenCase` objects validated by
`contracts/golden_case.schema.json`. Every count printed anywhere (the fixture key `golden`, the Evaluation page,
the deck) is read from this file by `tools/computed.py::golden_block()`, never typed. The v1.1 flat prose format is
gone; the 9.11 shape carries the same corpus facts and expectations as structured fields.

## Format contract

A top-level YAML list in block style. Every case starts `- id: GS-NN` at column 0, preceded by one comment line
`# GS-NN [origin tag] note` that keeps the v1.1 provenance tag (v1.0, CF-17, Addendum, PS-nn, ...) and the case note
for people; the runner reads the case alone. Fields in 9.11 order, strings double-quoted, no multi-line strings,
no em dashes, British spelling, English (a Bahasa Indonesia question is quoted verbatim as data). Two readers must
both work: `yaml.safe_load` and `tools/computed.py::_golden()` (which reads only `category` and `hard_gate`).

| field | meaning |
|---|---|
| `id` | `GS-01` to `GS-102`, unique |
| `category` | one of the eleven 9.11 names, verbatim |
| `hard_gate` | `true` for every case of Safety refusal and Safety-adjacent served (16); a failure there blocks release |
| `tier` | `A` or `B`, see below |
| `input` | `question` exactly as sent to `/ask`; optional `template`, `role` (9.7 enum), `setup` (the state the case assumes, e.g. "after GS-14 has been published") |
| `expected` | `outcome` (answer, partial, abstention, refusal); `must_cite` (documents the answer must cite, a subset of `sources`); `must_contain` and `must_not_contain` (strings over the rendered answer); `numerals_allowed` (every numeral the answer may render: value as rendered, unit, `source_ref`); optional `block_order`, `escalation_role` (9.8 enum), `rulepack_class`, `corpus_version_delta` |
| `sources` | the documents, work orders and package files the case draws on |
| `checks` | machine checks, `{type, args}`, types from the 9.11 enum only |
| `origin` | `team` for every case at v1; `external` is reserved for cases written outside the team |

## Tier rule

Tier A is settled without a provider response: the outcome and every check follow from the corpus, the rule pack or
the gates (refusals, abstentions with fixed reasons, traceability, register findings over typed rows, verbatim
renders, HTTP status, state and version checks). Tier B needs a composed answer, so its wording is judged against a
recorded provider response (grounded answers, false-abstention answers, composed trap explanations, drafts and
redlines, adversarial corrections, the moment-shaped answers). Tier A runs on every pull request; Tier B replays
recorded responses in pull-request CI and runs live nightly, before a freeze, and on any change to the rule pack or
the gates (blueprint 9.11). At v1: 50 A, 52 B.

## Naming

- `must_cite` and `sources` use document numbers (`TJC-LLD-DS-...`, `-GA-`, `-IL-`, `-PP-`), lesson ids (`OPL-...`),
  work orders (`WO-2400NN`) and `P&ID Set N` for the drawings; a case that relies on a sidecar, the rule pack or a
  package lists it in `sources` too (`packages/pid_sidecars/set_0N.json`, `rulepack/v1.json`,
  `packages/fixtures.json`, `packages/chains.json`, `packages/area_aliases.json`).
- `numerals_allowed[].source_ref` names the document and its field, row, step or title-block cell
  (`WO-240003 Root_Cause`, `TJC-LLD-IL-KC-4501 row T1`, `OPL-KC-4501-05 step 2`), or the fixture key the number is
  read from (`fixtures.integrity.CD-6.downtime_h`, `fixtures.debt.per_asset[GA-1201A].score`). A number the harness
  computes is never retyped: the value in the file is the allowance, the key is the source.
- `escalation_role` is the 9.8 `Abstention.escalation_role` enum (the v1.1 "panel operator / DCS" is
  `Panel operator on shift`).
- Rule-pack expectations use the 9.10 names: rules `R1-permanent-change` to `R5-none`, `routing_text.defeat`,
  `routing_text.permanent_change`, `routing_text.relief_device`, `fixtures.positives`, `fixtures.negatives`,
  `fixtures.moments`, `fixtures.outbound`. The defeat route text names no approving role, because no supplied
  document sets one.

## Check vocabulary

The three bulk checks read their list from the case: `citation_resolves {from: "expected.must_cite"}`,
`numeral_fidelity {from: "expected.numerals_allowed"}`, `string_present {from: "expected.must_contain"}` (and
`string_absent {from: "expected.must_not_contain"}`). Targeted checks name the packet field in `in` (`claims`,
`typed_facts`, `blocks.<kind>`, `refusal.<field>`, `abstention.<field>`, `procedure.<field>`, `citation_chip`,
`contradictions`, `trace`, `logs`, an export) and the condition: `text`, `pattern` (a regular expression), `ordered`
(with `order_by`), `field`, `empty: true`, `nonempty: true`. `citation_resolves` also binds one document to what
it must resolve to: `row` and `row_kind`, `step` and `binds`, `field` and `value`, `edge_to` with `resolved` and
`finding`, `bom_item` and `matched_to`, `chain` and `to` from `bundle/chains.json`, `matches` a spot file, `reading`
and `defect_kind` for a drawn label. `rulepack_class` carries `class`, `rule_id`, `matched_phrase`, `function`,
`language`, a sibling `text` to classify, or `on: "outbound"` for the outbound screen. `hash_render` names `opl_id`
and `steps` (or a `section` and `block`). `block_order` names the `template` and reads the order from
`expected.block_order`. `http_status` names `route`, `role` and `status`; `audit_event` names `action`, `present`
and what it `carries`; `version_increment` names `delta`, `after` and `previous_readable`; `trace_replays` names
`of` or `against` and what must be `equal`.

## Where the facts come from

Every corpus fact was read in the named document through `harness.pdftext` (`pdftotext -raw`, build 26.02.0,
canonical form) or in the typed workbook row through `harness.workbook`; quotations stay at citation length
(`tools/no_corpus_in_repo.py` fails on a run of 200 characters of corpus text). Fixture numbers are named by key.
Rule-pack behaviour is stated against `rulepack/v1.json`. Anything a case needs that the corpus does not contain is
a seeded fixture and says so in `input.setup`: the injected strings of GS-92, GS-94 and GS-95, the seeded unsafe
draft of GS-84 and the outbound draft of GS-72. No seeded fixture is counted in a published number.

Alignments recorded at the 9.11 conversion, each also in the case's comment line: GS-32 keeps the reading template's
block order of AC-ANS-16 (ladder, documented response, precedent; no reset path, no relief layer at a vibration
reading) where the v1.1 prose also listed a reset-path block; GS-96 expects the relief layer omitted rather than
the v1.1 slot string; GS-53's unreadable DRY WEIGHT field is the CT-7801 item of CD-11 (the prose wrote CD-10);
GS-05's CD-1 count of 28 spans four assets in the fixture (the prose wrote five); the sidecar basis on GS-06, GS-17
and GS-24 is `agent_transcription`, review status `pending` (D-12).

GS-08b (Addendum D2 / A6, FR-124, the SIMULATED GA-1201A series) is not in this file: it lands with
`simulated/ga-1201a.json` or is cut with it. Until then GS-96 renders the KC-4501 ladder without a series and GS-08
abstains on the live reading.

## Verify

```bash
uv run python -c "import yaml,collections;c=yaml.safe_load(open('golden/cases.yaml',encoding='utf-8'));print(len(c),collections.Counter(x['category'] for x in c),sum(x['hard_gate'] for x in c))"
uv run python -c "
import json,yaml,jsonschema
from harness.validate import contracts, registry
s=contracts('contracts'); sid=s['golden_case.schema.json']['\$id']
v=jsonschema.Draft202012Validator({'\$ref': sid+'#/\$defs/GoldenCase'}, registry=registry(s))
for c in yaml.safe_load(open('golden/cases.yaml',encoding='utf-8')): v.validate(c)
print('valid')"
uv run python -c "import sys;sys.path.insert(0,'tools');import computed;print(computed.golden_block())"
uv run python tools/banned_strings.py golden/cases.yaml
CASE1_CORPUS=/path/to/corpus uv run python tools/no_corpus_in_repo.py
```

The category counts must read 14, 8, 9, 11, 11, 5, 19, 8, 10, 3, 4 (total 102) with 16 hard gates, the values
`contracts/golden_case.schema.json` records under `x-counts-at-v1`; `tests/test_fixtures.py` cross-checks the
fixture's `golden` block against the file.
