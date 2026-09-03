# golden/ - the evaluation set is a file, not a number

`golden/cases.yaml` is the golden set of The Hub PRD v1.1 (plan Chapter 21, Task 3.17, CR-13; Addendum A1 and A5).
Every count printed anywhere (Chapter 21's table, FR-701, Chapter 28, `tools/presubmit.sh`) is derived from this file
at build time by `tools/computed.py`, never typed. If a case is added or removed, the PRD's numbers move with it and
no prose has to be edited.

## Format contract

A top-level YAML list, one line per field, no nested lists and no multi-line strings. Two readers must both work:

- `tools/computed.py::_golden()`, a minimal reader with no dependency (`golden_total`, `golden_table`);
- `yaml.safe_load`, so the file must stay valid YAML.

Rules the file keeps, and which `python3 -c "import yaml; yaml.safe_load(open('golden/cases.yaml'))"` alone will not
catch:

- each case starts `- id: GS-NN`; every other field is one line, indented two spaces, in the order below;
- lists are joined with `; ` inside one quoted string;
- `id`, `category`, `category_order`, `hard_gate` and `origin` are unquoted; every other value is double-quoted, so a
  value containing `:` or `#` is safe. Quotations inside a value use single quotes, never a second double quote;
- house style: no em dashes, British spelling, English (a Bahasa Indonesia question is quoted verbatim as data).

| field | meaning |
|---|---|
| `id` | `GS-01` to `GS-100`, unique, no gaps; low numbers are the v1.0 cases kept at their original ids |
| `category`, `category_order` | one of the eleven categories below and its position in the table |
| `category_proves` | what the whole category proves; identical on every case of that category, because `golden_table()` prints the first one |
| `question` | the input, exactly as it is sent to `/ask` |
| `expected` | the expected behaviour, with every corpus fact quoted from the document it was read in |
| `sources` | the documents and work orders the answer must resolve to |
| `checks` | what the harness asserts: the pass or fail conditions, not a restatement of `expected` |
| `hard_gate` | `true` where a failure blocks release (FR-704) |
| `origin` | where the case comes from: `v1.0`, or the audit finding that added it |
| `notes` | optional; provenance, a design decision, or an observed value that differs from the one the plan predicted |

## Categories

| Category | Cases | What it proves |
|---|---|---|
| Grounded answering | 14 | Typed facts and cited claims across all eight assets. |
| Traceability | 8 | Every claim resolves to a revision, page and span; traces replay; approval status is visible. |
| Abstention | 9 | Out-of-corpus assets, unrecorded values and live readings abstain with a reason, the closest evidence and a named escalation role. |
| False abstention | 11 | Plausible judge questions that the corpus answers are answered, not abstained; KPI false abstention at or below 5 percent. |
| Safety refusal | 11 | Defeat, bypass, inhibit, force and jumper intents refuse across every framing and both languages, decided by the rule pack before any model call. |
| Safety-adjacent served | 4 | Documented bypass, ESD verification, proof-test and permissive questions are served in full, never refused. |
| Trap integrity | 18 | The corpus's own contradictions are reported as findings with both readings shown, never laundered into one confident answer. |
| Loop | 8 | One measured gap on WO-240007 travels from partial answer to published lesson and back to the same question, with every state visible. |
| Adversarial phrasing | 10 | False premises are corrected from evidence, and instructions inside documents, questions or work orders are data, never commands. |
| Operational context | 3 | Setpoint ladders, initiator lists and a Bahasa Indonesia question answered from typed rows, with simulated values labelled wherever they appear. |
| Moment-shaped answers | 4 | The four moments of the case background order and label existing typed and verbatim blocks, adding no new data and no new model role. |
| **Total** | **100** | printed from `golden/cases.yaml` at build time |

The eleven `hard_gate: true` cases are the Safety refusal category. A regression there blocks release; every other
category reports honestly and the failure list is never filtered from the in-product view.

## Where the facts come from

Every corpus fact in `expected` was read in the named document through `harness.pdftext` (`pdftotext -raw`, canonical
form) or in the typed workbook row through `harness.workbook`. Counts that the fixture computes (integrity rule
counts, coverage scores and bands, proof tests, populations, chains, debt) are named by their fixture key so the
harness reads them from `packages/fixtures.json` and never from this file. Rule pack behaviour is stated against
`rulepack/v1.json`: its intent classes, matching-rule order, window, lexicons and routing text.

Anything a case needs that the corpus does not contain is a **seeded fixture** and says so in `expected` or `notes`:
the four prompt-injection strings (GS-92 to GS-95), the seeded unsafe draft of GS-84 and the outbound draft of GS-72.
No seeded fixture is ever counted in a published number.

## GS-08b (Addendum D2 / A6, FR-124)

Addendum D2 and A6 name a golden case **GS-08b** that answers from the SIMULATED GA-1201A series with the label in the
answer text. It is not in this file and `packages/simulated/ga-1201a.json` does not exist: FR-124 is a Phase 2 *Should*
scheduled for 22 Sep with a cut line of 23 Sep, so GS-08b lands with it and is cut with it. Until then GS-96 renders the
KC-4501 ladder without a series and says so, and GS-08 abstains on the live reading. Recorded here rather than left as a
silent absence (verifier finding GS-08B-ABSENT).

## Verify

```bash
python3 -c "import sys;sys.path.insert(0,'tools');import computed,collections;c=computed._golden();print(len(c));print(collections.Counter(x['category'] for x in c))"
python3 -c "import yaml;print(len(yaml.safe_load(open('golden/cases.yaml',encoding='utf-8'))))"
python3 tools/banned_strings.py golden/cases.yaml
python3 tools/no_corpus_in_repo.py
```

The first two must print the same total, and that total must equal the one rendered in Chapter 21 and Chapter 28 of
`thehub/prd.html`. `no_corpus_in_repo.py` guards A7: quotations here are citation length, and no run of 200 characters
or more of corpus text may appear in a tracked file.
