# Coverage labels: machine-drafted adjudication (WS1 Task 1.6)

Inputs: `packages/labels_1.draft.json` (AGENT-L1) and `packages/labels_2.draft.json` (AGENT-L2), 57 work orders each, the whole `unplanned_failure` population. Output: `packages/coverage_labels.draft.json`. Both verdicts are preserved in every record, so both kappas below can be recomputed from the output file alone.

## 1. The rule the labellers and the adjudicator applied

> A lesson covers a work order when, for the same asset, its procedure steps, troubleshooting table or key-learning points address the recorded failure mechanism or the corrective action. A copied troubleshooting row counts as coverage in the generous layer only; table_only is true when nothing outside section 5 addresses the mechanism.

## 2. Labeller totals

| | AGENT-L1 | AGENT-L2 |
| --- | ---: | ---: |
| work orders labelled | 57 | 57 |
| covered (covered_by non-empty) | 47 | 47 |
| table_only true | 16 | 17 |
| taught (covered and not table_only) | 31 | 30 |
| distinct OPL ids cited | 56 | 44 |

Both labellers call the same 47 work orders covered and the same 10 uncovered. AGENT-L1 cites every lesson that carries the copied section-5 row as well as the teaching lesson, so it names 56 distinct lessons against AGENT-L2's 44.

## 3. Cohen's kappa

### 3.1 Binary covered decision (covered_by non-empty)

| AGENT-L1 \ AGENT-L2 | covered | uncovered |
| --- | ---: | ---: |
| covered | 47 | 0 |
| uncovered | 0 | 10 |

p_o = 1 = 1.000000, p_e = 2309/3249 = 0.710680, **kappa = (p_o - p_e) / (1 - p_e) = 1.0000** (exactly 1).

### 3.2 Taught decision (covered and not table_only)

| AGENT-L1 \ AGENT-L2 | taught | not taught |
| --- | ---: | ---: |
| taught | 30 | 1 |
| not taught | 0 | 26 |

p_o = 56/57 = 0.982456, p_e = 544/1083 = 0.502308, **kappa = (p_o - p_e) / (1 - p_e) = 0.9647** (exactly 520/539).

Perfect agreement on the binary decision and one disagreement out of 57 on the taught decision. Two machine labellers reading the same corpus under the same written rule are not independent in the way two human labellers are, so these figures state the rule's reproducibility, not human inter-rater reliability; the human pass (D6, OQ-6) supplies the second.

## 4. Disagreements and their adjudication

### 4.1 Verdict disagreements (1 of 57)

**WO-240061 (DC-3401A)**

- AGENT-L1: covered_by OPL-DC-3401A-07, table_only false.
- AGENT-L2: covered_by OPL-DC-3401A-07, table_only true.
- Adjudicated: covered_by OPL-DC-3401A-07, table_only true.
- Reason: table_only adjudicated to true with AGENT-L2. Outside section 5, OPL-DC-3401A-07 teaches only the box-up that follows a catalyst change ('Always fit a new spiral-wound SS316/graphite gasket', 'Torque the manway bolts in a star pattern to the specified value', 'Leak test the joint with nitrogen at 2 kg/cm2'); none of the three recorded actions (vacuum out the spent catalyst, inspect the grids, load 3.2 m3 of fresh catalyst) is taught there, and step 4 'Record the catalyst batch number and the loaded volume (3.2 m3)' is a close-out record rather than the loading procedure, which AGENT-L1's own basis concedes ('moderate: unloading and grid inspection are not taught'). Nothing outside section 5 addresses the mechanism 'Spent Pd/Al2O3 catalyst at end of run', so the coverage rests on the copied section-5 row and the work order lands in the table_only band.

### 4.2 Attribution differences (16 of 57, same verdict, different covered_by list)

In each of these the two labellers agree that the work order is covered and agree on table_only, and differ only in how many lessons they name. AGENT-L1's list is in every case AGENT-L2's teaching lesson plus every lesson whose section-5 table carries the copied work-order row; AGENT-L2 names the teaching lesson alone. The rule counts a copied troubleshooting row as coverage in the generous layer, so **AGENT-L1's list is adopted**. Every membership was verified against the corpus: for each named lesson at least one narrative field of the work order appears in that lesson's section-5 table, allowing for the truncation the tables apply (for example WO-240002's '... seal gland during operation, seal drain flowing' is pasted into OPL-GA-1201A-01 to -06 as '... seal gland during operation, seal dr.'). No named lesson failed the check and no lesson carrying the copied row was missing from the adopted list. Because the verdicts match, `agreed` stays true and `adjudication` stays empty in these records; the two lists remain side by side under `labellers`.

| work order | tag | AGENT-L1 (adopted) | AGENT-L2 |
| --- | --- | ---: | ---: |
| WO-240002 | GA-1201A | 6 lessons: 01, 02, 03, 04, 05, 06 | 1: 01 |
| WO-240003 | GA-1201A | 6 lessons: 01, 02, 03, 04, 05, 06 | 2: 03, 05 |
| WO-240004 | GA-1201A | 7 lessons: 01, 02, 03, 04, 05, 06, 07 | 2: 03, 07 |
| WO-240028 | YD-2301 | 7 lessons: 01, 02, 03, 04, 05, 06, 07 | 1: 02 |
| WO-240029 | YD-2301 | 7 lessons: 01, 02, 03, 04, 05, 06, 07 | 1: 02 |
| WO-240031 | YD-2301 | 4 lessons: 02, 03, 05, 07 | 1: 03 |
| WO-240056 | DC-3401A | 6 lessons: 01, 02, 03, 04, 05, 06 | 1: 06 |
| WO-240083 | KC-4501 | 6 lessons: 01, 02, 03, 04, 06, 07 | 1: 02 |
| WO-240110 | EA-5601 | 7 lessons: 01, 02, 03, 04, 05, 06, 07 | 2: 01, 06 |
| WO-240111 | EA-5601 | 6 lessons: 01, 02, 03, 04, 05, 07 | 1: 02 |
| WO-240112 | EA-5601 | 6 lessons: 01, 02, 03, 04, 05, 07 | 1: 03 |
| WO-240135 | LV-6701 | 7 lessons: 01, 02, 03, 04, 05, 06, 07 | 1: 03 |
| WO-240137 | LV-6701 | 5 lessons: 01, 02, 04, 06, 07 | 1: 01 |
| WO-240138 | LV-6701 | 6 lessons: 01, 02, 03, 04, 06, 07 | 1: 03 |
| WO-240163 | CT-7801 | 6 lessons: 01, 02, 03, 04, 05, 07 | 1: 03 |
| WO-240164 | CT-7801 | 3 lessons: 02, 03, 05 | 1: 02 |

(The lesson ids are abbreviated to their sequence number; the prefix is `OPL-<tag>-`.)

### 4.3 Borderline flags

At least one labeller marked 6 records borderline. These are the records most likely to move in the human pass, so they are listed here in full.

| work order | tag | flagged by | adjudicated verdict |
| --- | --- | --- | --- |
| WO-240061 | DC-3401A | AGENT-L2 | covered, table_only (split, see 4.1) |
| WO-240084 | KC-4501 | AGENT-L1 | covered, table_only |
| WO-240087 | KC-4501 | AGENT-L1, AGENT-L2 | covered, table_only |
| WO-240094 | KC-4501 | AGENT-L1 | uncovered |
| WO-240143 | LV-6701 | AGENT-L1 | covered, table_only |
| WO-240191 | FA-8901 | AGENT-L1, AGENT-L2 | covered, table_only |

Only WO-240061 produced a split verdict; on the other 5 both labellers reached the same verdict independently, so that verdict stands and the flag is carried into the record's basis for the human pass.

## 5. The adjudicated set against the proxy

| band | adjudicated labels | frozen proxy (t = 0.62) |
| --- | ---: | ---: |
| none (no lesson covers it) | 10 | 14 |
| table_only (covered by the copied row alone) | 17 | 26 |
| taught (covered outside section 5) | 30 | 17 |
| total | 57 | 57 |

The proxy is the more pessimistic of the two on every band. It calls 5 work orders uncovered that the labels call covered (WO-240034, WO-240037, WO-240089, WO-240167, WO-240169) and 1 covered that the labels call uncovered (WO-240091); 9 uncovered work orders are common to both. Scored as a classifier against the drafted labels, the generous layer gives tp 42, fp 1, fn 5, tn 9, precision 0.977, recall 0.894; the strict layer gives tp 16, fp 1, fn 31, tn 9, precision 0.941, recall 0.340. The strict layer's low recall is the intended effect of excluding section 5: it measures teaching, not table reuse.

## 6. Status

This file and `packages/coverage_labels.draft.json` are machine-drafted. Two agents labelled the population independently under the rule in section 1 and this adjudication resolved the differences by reading the lesson texts and the work-order rows; no human has signed either verdict. Every record therefore carries `"adjudicated": false` and `"human_adjudication": "pending (Member A + supervisor, OQ-6)"`, and the harness keeps `labelled` and `labels_agreement` null while only the draft exists, so no figure in the deck can be read off a machine label. The human adjudication required by decision D6 and open question OQ-6 (Member A labels, the supervisor adjudicates) replaces this file with `packages/coverage_labels.json` before the deck freeze; at that point the counts in sections 2 to 5 are recomputed from the human file and this draft is superseded. Until then the deck numbers remain the frozen proxy of method LD-07.
