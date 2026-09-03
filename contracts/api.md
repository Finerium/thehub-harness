# API endpoints and the permission matrix

Blueprint section 9.9, frozen. Every name, role, contract and limit below is stated verbatim; the only addition is the D-07 note on the reviewer tour route. Type names refer to the JSON Schema files in this directory (`entities/*.schema.json`, `evidence_packet.schema.json`).

## Permission matrix (role -> permission)

| Role | ask_read | view_drafts | create_draft | decide | publish | activate_version | add_sme_note |
|---|---|---|---|---|---|---|---|
| Engineer | yes | yes | no | no | no | no | yes |
| Reviewing Supervisor | yes | yes | yes | yes | no | no | yes |
| Manager | yes | yes | no | reject-from-accepted only | yes | no | yes |
| Admin | yes | no | no | no | no | yes | no |

## Principals

- Public principal: `GET /api/health`, `POST /api/auth/login`, `GET /api/auth/tour/:token` only.
- CI principal (`CI_INGEST_TOKEN`): `POST /api/evaluation/runs` only.
- Job principal (`ADMIN_JOB_TOKEN`): `POST /api/admin/corpus/activate` only, audited as actor `"job:nightly-activation"`.

## Endpoints

| Method and path | Permission | Request -> response |
|---|---|---|
| `POST /api/ask` | ask_read | `{ question: string, template?: "readiness"\|"trip"\|"job"\|"reading", mode?: "answer"\|"search" }` -> ndjson stream (9.8, `evidence_packet.schema.json#/$defs/AskStream`) |
| `GET /api/trace/:id` | ask_read | -> AnswerTrace (immutable) |
| `GET /api/search?q=&include_superseded=` | ask_read | -> `{ chunks: [...], documents: [...] }` |
| `GET /api/documents/:id?include_superseded=` | ask_read | -> `{ document, revisions: DocumentRevision[], assets: string[], integrity_findings: [...], page_anchors: [...] }` |
| `GET /api/documents/:id/pages/:n` | ask_read | -> image/webp or image/png derivative, metadata-free, role-checked; no bulk or archive route exists |
| `GET /api/assets` | ask_read | -> Equipment[] joined summary |
| `GET /api/assets/:tag` | ask_read | -> `{ equipment, area, documents, interlock, rows, permissives, params, hotspots, operational_context, ladders, proof_tests, bom_matches, connectors, simulated: object \| null }` |
| `GET /api/assets/:tag/failures` | ask_read | -> `{ history: WorkOrder[], events: FailureEvent[], chains: CausalLink[], families, precedent }` |
| `GET /api/coverage` | ask_read | -> `{ method: CoverageMethod, summaries: CoverageSummary[], clusters: DebtCluster[] }` |
| `GET /api/coverage/clusters/:id` | ask_read | -> DebtCluster with its assessments and matched units |
| `POST /api/drafts` | create_draft | `{ cluster_id }` -> 202 `{ draft_id, state: "proposed" }` |
| `GET /api/drafts`, `GET /api/drafts/:id` | view_drafts | -> queue; detail with evidence, verdicts, transitions, notes |
| `POST /api/drafts/:id/decision` | decide | `{ decision: "accept"\|"edit"\|"reject", reason?: string, edits?: Array<{ field_id, text, reason }> }` -> 200 draft |
| `POST /api/drafts/:id/repropose` | create_draft | -> 201 `{ draft_id }` \| 409 on a published draft |
| `POST /api/sme-notes` | add_sme_note | `{ draft_id, field_id, text, source_reference? }` -> 201 SmeNote |
| `POST /api/drafts/:id/publish` | publish | -> 200 `{ document_revision_id, corpus_version, coverage_recount }` \| 403 \| 409 (repeat or race) \| 422 `{ gate: "G3", reason: string }` |
| `GET /api/integrity?rule=&severity=&discipline=` | ask_read | -> findings; with `Accept: text/csv` -> CSV whose header comment lines carry corpus_version, the rule ids in scope and the fixture totals |
| `GET /api/evaluation/latest` | ask_read | -> `{ run: EvaluationRun, categories: [...], failures: EvaluationResult[] }` |
| `POST /api/evaluation/runs` | ci token | `{ run: EvaluationRun, results: EvaluationResult[] }` -> 201; unauthenticated -> 401 and audited |
| `GET /api/connectors`, `GET /api/connectors/:name/schema` | ask_read | -> descriptors; the schema route returns the repository file byte for byte |
| `GET /api/admin/corpus/versions` | activate_version | -> CorpusVersion[] |
| `POST /api/admin/corpus/activate` | activate_version or job token | `{ version_id }` -> 200; audited as `corpus.version_activated` |
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session` | login: public principal; logout and session: any signed-in role | not stated in 9.9 |
| `GET /api/auth/tour/:token` | public | -> sets a read-only reviewer session bound to the link's demo account, or renders the expired or revoked state. **Not built in this run (D-07).** |
| `GET /api/health` | public | -> `{ ok: true, corpus_version: string, commit: string }` |

### D-07 note on `GET /api/auth/tour/:token`

Under deviation D-07 the live deployment is fully behind login and signed login-free reviewer links are not built in this run. The frozen route and the frozen `ReviewerLink` type (9.7) keep their names and shapes and carry `"x-status": "not built in this run (D-07)"`; the tour is the post-login landing. The public principal therefore reaches `GET /api/health` and `POST /api/auth/login` only.

## Cross-cutting rules

- Every mutating route returns 403 with an audit event when the role lacks the column.
- Every response carries `x-request-id` equal to the trace id or the audit event id.
- Rate limits are 30 asks and 5 draft creations per minute per account and 120 requests per minute per address, exhaustion rendering a designed 429 that names the limit and the reset moment.
- Every list route paginates with `?page=&page_size=` (default 50, maximum 200).
