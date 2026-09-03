# Contracts (blueprint section 9, FROZEN)

Every interface contract of The Hub lives in this directory and nowhere else (blueprint 8.3). Both repositories consume it by pointer:

- `thehub-harness` (this repository) validates its packages and the bundle of 9.1 against these files in its tests and at bundle time, and ships the three connector schemas inside the bundle under `contracts/`.
- `thehub-3v` (the application) derives its Zod schemas (`src/contracts/`, generated, never hand-edited) and its Drizzle schema (`src/db/schema.ts`) from these files. It pins one harness release tag: the tag of the release whose bundle it seeds from (`Manifest.harness_commit` is that tag's commit), regenerates `src/contracts/` from that tag's `contracts/`, and seeds only from a bundle whose manifest verifies (8.3, 9.1). Moving the pin is a reviewed change in the application repository, never an implicit read of a branch.

A name, type or enum that differs from section 9 is a blocker in either repository. Section 9 is frozen; the deviation log (`.crown/notes.md`, D-01 to D-14) records the decisions that override it (D-05 one model id for every role, D-07 reviewer links not built, D-11 extractor build 26.02.0, D-12 adopted sidecars carry `agent_transcription` and `pending`).

## Index

| File | Blueprint | Contents |
| --- | --- | --- |
| `bundle/manifest.schema.json` | 9.1 | `Manifest` of the package bundle; `BundleLayout`, the frozen file tree (chunks.jsonl untracked, produced at seed time) |
| `fixtures.schema.json` | 10.5 | The fixture key registry: the 20 top-level keys of `fixtures.json`, nested keys, frozen constants and the values stated at freezing (`x-expected`) |
| `entities/document.schema.json` | 9.2 | `DocumentClass`, `ApprovalStatus`, `Document`, `DocumentRevision`, `DocumentEdge`, `Span`, `Claim`, `Chunk`; the canonical form |
| `entities/asset.schema.json` | 9.3 | `Equipment`, `Area`, `Interlock`, `InterlockRow`, `StartPermissive`, `DatasheetParam`, `InstrumentTag`, `PidSidecar`; the FR-106 rule |
| `entities/operations.schema.json` | 9.4 | `WorkOrder`, `FailureEvent`, `FailureFamily`, `CausalLink`, `ProofTest`, `BomItem`, `BomMatch`; the causal-link rule |
| `entities/coverage.schema.json` | 9.5 | `CoverageMethod`, `CoverageAssessment`, `CoverageSummary`, `DebtCluster`, `Opl`, `OplStep`, `TroubleshootingRow`; the frozen recipe and debt formula |
| `entities/drafts.schema.json` | 9.6 | `DraftState` and its legal transitions, `DraftDocument`, `DraftField`, `RedlineVerdict`, `DraftTransition`, `SmeNote`, the fixed unverified-value line |
| `entities/serving.schema.json` | 9.7 | `Role`, `AppUser`, `Session`, `ReviewerLink` (not built in this run, D-07), `CorpusVersion`, `AnswerTrace`, `EvaluationRun`, `EvaluationResult`, `AuditEvent`, `AuditAction` |
| `evidence_packet.schema.json` | 9.8 | `Citation`, the packet `Claim`, `TypedFact`, `Block`, `Procedure`, `Abstention`, `Refusal`, `EvidencePacket`, the ask stream, the fixed as-built caveat |
| `api.md` | 9.9 | The permission matrix, the principals, every endpoint with its role and contract, rate limits and pagination |
| `rulepack.schema.json` | 9.10 | `RulePack` version 1: lexicons, suppressions, protective vocabulary, documented bypass entities, the ordered rules, routing text, moment keywords, fixtures |
| `golden_case.schema.json` | 9.11 | `GoldenCase` with its category, check and origin enums and the category counts at v1 |
| `deliverables.md` | 9.12 | Export, deck, video, pointer PDF, pre-submit and byte budgets as a checklist; the team-facts JSON |
| `team_facts.schema.json` | 9.12 | The `supplied/team-facts.json` object the deck build reads (`TBD_` is the placeholder marker) |
| `gateway.schema.json` | 9.13, 9.16 | `GatewayRole`, `GatewayCall`; the typed envelopes of AG-1 to AG-4 and the embedding role; recorded replay |
| `connectors/edms.schema.json` | 9.14 | EDMS records; specified, not connected |
| `connectors/aims.schema.json` | 9.14 | AIMS work-order rows (the 9.4 `WorkOrder` shape by reference); specified, not connected |
| `connectors/historian.schema.json` | 9.14 | Historian samples (tag, timestamp, value, quality); specified, not connected |
| `env.md` | 9.15 | Every environment variable name with its purpose and owner; no values |
| `README.md` | 8.3, 9.1 | This index and the consumption rule |

## Conventions (every `.schema.json`)

- `"$schema": "https://json-schema.org/draft/2020-12/schema"`; `"$id": "https://thehub.finerium.dev/contracts/<path relative to this directory>"`.
- Top level: `title` (the blueprint subsection), `description` (one sentence citing the section), `x-blueprint`, and `$defs` with one entry per named type of the subsection, keyed and titled by the blueprint's type name verbatim.
- Each type: `"type": "object"`, `"additionalProperties": false`, properties in the blueprint's field order, every field required; `T | null` is `["T", "null"]`, an optional field (`?`) is not required. Closed enums are copied verbatim; literal constants are `const`; timestamps are ISO 8601 UTC strings with `"format": "date-time"`; money is an integer number of rupiah; hours and ratios are numbers; counts and ordinals are integers.
- Cross-file references are relative: `"$ref": "<file>.schema.json#/$defs/<Type>"` (or a deeper pointer into a property, for an enum the blueprint declares inline). The fixture registry keeps `additionalProperties` open because the harness may add keys and may never rename one (10.5).
- Annotation keywords (ignored by validators): `x-blueprint`, `x-expected` (the value stated at freezing), `x-status`, `x-transitions`, `x-counts-at-v1`, `x-sync`, `x-conflict-rule`, `x-failure-behaviour`, `x-untracked`, `x-optional`, `x-file-notes`.
- Validate a file with:

```sh
cd thehub-harness && uv run python -c "import json,jsonschema,sys; s=json.load(open(sys.argv[1])); jsonschema.Draft202012Validator.check_schema(s); print('valid')" contracts/<file>
```
