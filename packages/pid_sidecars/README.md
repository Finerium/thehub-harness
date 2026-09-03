# P&ID sidecars (FR-111)

Hand-transcribed metadata for the eight P&ID PNGs of Case 1. The PNGs have no text layer, so nothing in this
directory is harness output: every value was read off the image by a person (`provenance.basis =
"manual transcription of the image"`) and cross-checked against the asset's typed documents (interlock sheet,
datasheet, GA drawing, plot plan via `harness.pdftext.class_texts`). Closes AE-09 (no extractor for PNGs), CF-06,
CF-24 and CF-V-01 (defect inventory), CR-08 (hotspots bound to C&E tags).

Files: `set_01.json` … `set_08.json`, one per PNG, in set order (GA-1201A, YD-2301, DC-3401A, KC-4501, EA-5601,
LV-6701, CT-7801, FA-8901). Written with `json.dump(sort_keys=True, indent=1, ensure_ascii=False)`; re-serialising a
file must reproduce it byte for byte.

## Schema (one object per file)

| key | type | meaning |
|---|---|---|
| `set`, `file`, `tag` | int, str, str | set number, PNG file name exactly as in the corpus, equipment tag of the set |
| `image_px` | [w, h] | pixel size of the PNG the coordinates were estimated on |
| `title_as_drawn` | str or null | the most title-like text on the sheet (title cell, caption or heading); null when only instrument/equipment labels exist |
| `title_block_as_drawn` | list (Set 4 only) | every cell of the title block, verbatim |
| `ref_dwg_as_drawn` | str or null | the reference-drawing box verbatim, label included (`Ref. Dwg.`, `Ref. Drg.`, `Ref. Plog.`); the number is the last token; null when there is no box (Set 3) |
| `revision_block_as_drawn` | str or null | revision table and title-block REV/DATE cells, verbatim (Set 4 only) |
| `datasheet_cited_as_drawn` | str or null | document number after "Datasheet" in the notes |
| `seq_cited_as_drawn` | str or null | sequence or interlock document cited in the notes or table title |
| `notes_as_drawn` | list of str | the NOTES block, one verbatim line each, whitespace collapsed; `[]` when there is none (Set 6) |
| `equipment_shown` | list of str | equipment, insets, tables and legends on the sheet, described with their verbatim labels |
| `instruments` | list | every tagged or captioned element, see below |
| `defects` | list of `{kind, detail}` | one entry per defect family; `detail` quotes the sheet and the contradicting document |
| `provenance` | object | `{basis, by, date}`; `by` is a role alias, never a name |

Instrument entry: `{as_drawn_text, bound_tag, role, setpoint_as_drawn, foreign, x, y, note?}`.

- `as_drawn_text`: the label verbatim, garbling included (`S5LL 2305`, `VSIFH-7802`, `9 m/0h`). Table rows are written
  `cell | cell | …`; effect boxes that point at a tag are written `EFF-n -> TAG`.
- `bound_tag`: the tag in the asset's own C&E or datasheet that the element stands for, or null when nothing in the
  typed documents corresponds. A hotspot binds to `bound_tag`, never to `as_drawn_text` (CR-08). Where the drawn tag
  and the bound tag differ, the `note` says which C&E row or datasheet field was matched.
- `role`: `initiator | effect | permissive | indicator | control_valve | isolation | relief | equipment | other`
  (`other` covers line numbers, captions, table cells and DCS/legend bubbles).
- `setpoint_as_drawn`: the value string printed next to the element, or null.
- `foreign`: true when the tag belongs to another asset of the corpus (all cases are GA-1201A tags or its line
  number `HC-1002` on Sets 2, 4, 7, 8). Mistyped tags of the asset itself (`HS-5901`, `PT-8202`, `ZSO-4901`,
  `TSHH-7802`) are not foreign; they carry the correct `bound_tag` and a defect of kind `label_vs_ce_mismatch`.

Defect kinds: `placeholder_ref` (CD-2), `missing_title_block` (CD-2, Set 3), `wrong_datasheet_citation` (CD-7),
`wrong_seq_citation` (CD-8), `foreign_tag` (CD-9), `label_vs_ce_mismatch` / `footprint_vs_plot_plan` /
`revision_conflict` (CD-18), `copy_paste_inset`, `garbled_text`, `other` (observations, not counted as defects).
The integrity rules count sheets, so the number of defect entries per file is not a rule count.

## Hotspot coordinate convention

`x` and `y` are fractions of the image width and height (0–1), origin at the top-left corner, pointing at the
centre of the label or symbol named in `as_drawn_text`. They were estimated from 2x quadrant crops of the PNG and
are accurate to about ±0.02 (±25 px on these images). Coordinates are present for every instrument on every set;
Sets 1, 2, 4 and 5 (the FR-507 hotspot sets, Set 2 as the defect showcase) were measured with the most care.
Render a hotspot at `(x * width, y * height)` of whatever size the PNG is displayed at.

## Provenance rule

Hand-verified image facts live here and in `packages/hand_verified.json`, each entry carrying a role alias and a
date. They are never presented as harness output: the harness reads these files as inputs for CD-2/7/8/9/18 and
prints the sheet counts it derives from them, and prose that quotes an image fact cites the sidecar, not
`fixtures.json`. Every statement in `detail` or `note` that contradicts the sheet quotes the corpus document it came
from (C&E row, datasheet field, GA drawing note or plot plan field). To change a value, re-open the PNG; do not edit
from memory.

A tag is `foreign` when it is an instrument tag or an equipment ID belonging to another asset, and only then: this is
the rule CD-9 counts and the rule `packages/hand_verified.json` records in `foreign_tags`. A line number or a free-text
destination label carried over from another sheet (Set 8's `4"-HC-1002-CS02-I` and `8"-HC-1002-CS02-I`, Set 4's
`FROM STORAGE TANK 12-T-01`) is copy-paste evidence, not a foreign tag: it sits in the set's `foreign_tag` defect entry
and in `hand_verified` notes, with `foreign: false` on the instrument row, so the two hand-kept records cannot diverge
(Addendum P8).

## Per-set summary

| set | tag | ref. box | datasheet cited | seq cited | instruments | defect entries (kinds) |
|---|---|---|---|---|---|---|
| 1 | GA-1201A | `TJC-LLD-PID-XXXX` | TJC-LLD-DS-GA-1201A (correct) | SEQ-1201 (correct) | 33 | 4 (placeholder_ref, garbled_text, label_vs_ce_mismatch, other) |
| 2 | YD-2301 | `TJC-LLD-PID-XXXX` | TJC-LLD-DS-GA-1201A (wrong) | SEQ-1201 (wrong, C&E SEQ-5500) | 50 | 8 (placeholder_ref, wrong_datasheet_citation, wrong_seq_citation, foreign_tag, label_vs_ce_mismatch, footprint_vs_plot_plan, copy_paste_inset, garbled_text) |
| 3 | DC-3401A | none | none | SEQ-3401 (table title) | 63 | 4 (missing_title_block, garbled_text, label_vs_ce_mismatch, other) |
| 4 | KC-4501 | `TJC-LLD-PID-4501` Rev 02 | TJC-LLD-PF-GA-4501A (wrong) | SEQ-4501 (correct) | 56 | 7 (wrong_datasheet_citation, foreign_tag, revision_conflict, label_vs_ce_mismatch, other x3, one of them the anti-surge caption on a reciprocating machine) |
| 5 | EA-5601 | `TJC-LLD-PID-5601` | none (cites IL-EA-5601, PP-EA-5601, OPL-EA-5601-04) | IL-EA-5601 | 50 | 2 (label_vs_ce_mismatch, other) |
| 6 | LV-6701 | `TJC-LLD-PID-XXXX` (`Ref. Drg.`) | none | SEQ-6701 | 40 | 4 (placeholder_ref, garbled_text, label_vs_ce_mismatch, other) |
| 7 | CT-7801 | `TJC-LLD-PID-XXXX` (`Ref. Plog.`) | TJC-LLD-DS-GA-7801A (wrong) | SEQ-7801 (correct) | 35 | 6 (placeholder_ref, wrong_datasheet_citation, foreign_tag, label_vs_ce_mismatch, garbled_text, other) |
| 8 | FA-8901 | `TJC-LLD-PID-XXXX` | TJC-LLD-GA-FA-8901 (wrong, GA number) | SEQ-8901 (correct) | 61 | 7 (placeholder_ref, wrong_datasheet_citation, foreign_tag, label_vs_ce_mismatch, copy_paste_inset, garbled_text, other) |

Sheet counts these files support: placeholder or absent reference 6 (Sets 1, 2, 6, 7, 8 + Set 3); wrong datasheet
number 4 (Sets 2, 4, 7, 8); wrong sequence 1 (Set 2); foreign tags 4 (Sets 2, 4, 7, 8); contradictions with a
sibling document: Set 2 (footprint, PSLL-2303/S5LL-2305), Set 4 (Rev 02), Set 7 (TSHH-7802 vs TSHH-7803),
Set 8 (PSV-8901 at 0.5 barg vs datasheet 10 barg).

## Check

```
python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('packages/pid_sidecars/set_*.json')]"
```
loads all eight; the schema assertions used at authoring time are the key set above, roles and kinds from the two
enumerations, and `0 <= x, y <= 1`.
