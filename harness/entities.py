"""Typed entities of blueprint 9.3, 9.4 and 9.5 read from the corpus for the bundle, every quoted field anchored by a
span of harness.documents: datasheet parameters, C&E sheets (rows, permissives, notes), instrument tags, equipment and
areas, GA-drawing bills of material and their work-order matches, lessons (sections, steps, troubleshooting rows, permit
lines), work orders, failure events, proof tests, failure families, causal links, coverage, debt, integrity findings
and the P&ID sidecars in the 9.3 shape.

Text comes only from harness.pdftext; every number comes from packages/fixtures.json (the one fixture) or the workbook
rows; the C&E column identity comes from packages/interlock_effects.json through harness.master.parse_interlock, which
raises on any disagreement with the text. Nothing here derives a sequence id from a tag (FR-106): every protective-function
relation is read from the sheet that types it.
"""

import re
from collections import Counter

from .canonical import canonical, quote_hash
from .documents import CORPUS_VERSION_ID, emp_alias
from .integrity import RULES, canonical_lines
from .workbook import NARR, OUTCOME_FIELDS

# A tag token: 2 to 5 letters, 4 or 5 digits, an optional suffix letter, not glued into a longer hyphenated identifier
# (TJC-LLD-DS-GA-1201A is a document number, not the tag GA-1201A); TE-3401-1..8 still yields TE-3401.
INSTR = re.compile(r"(?<![A-Z0-9-])[A-Z]{2,5}-\d{4,5}[A-Z]?(?![A-Z0-9])")
# identifiers of the same shape that are not instrument tags: sequence ids, aliases, work numbers, notifications
NOT_A_TAG = re.compile(r"^(SEQ|EMP|BA|NT|WO)-")
WATERMARK = "This is sample data provided for CALIBER purposes only"
PROJECT_LINE = "SDK Polyolefin Expansion Project"

# ---------------------------------------------------------------- datasheets (9.3 DatasheetParam)
DS_GROUPS = (
    "DESIGN & MECHANICAL DATA",
    "DRIVER / MOTOR / HEATER DATA",
    "PERFORMANCE / NOZZLE DATA",
    "VENDOR / MANUFACTURER",
)
# The cell labels of the eight datasheets' three table blocks (the header block is parsed by DS_HEADER). `-raw` emits a
# two-column table as "LABEL value LABEL value" runs with values wrapping over lines, and most values are upper case too,
# so the split needs the label vocabulary; every label below is a cell of one of the eight sheets, read once and pinned.
DS_LABELS = sorted(
    {
        "PUMP TYPE",
        "CASING MATERIAL",
        "MODEL",
        "IMPELLER MATERIAL",
        "RATED FLOW",
        "SHAFT MATERIAL",
        "RATED HEAD",
        "MECHANICAL SEAL",
        "NPSH REQUIRED",
        "SEAL FLUSH PLAN",
        "DIFF. PRESSURE",
        "BEARING TYPE",
        "PUMPING TEMP.",
        "LUBRICATION",
        "SPECIFIC GRAVITY",
        "COUPLING",
        "VISCOSITY",
        "TOWER TYPE",
        "BLADE MATERIAL",
        "ITEM NO.",
        "HUB MATERIAL",
        "FAN DIAMETER",
        "DRIVE SHAFT",
        "FAN TYPE",
        "WATER FLOW (CELL)",
        "AIR FLOW",
        "RANGE / APPROACH",
        "FAN SPEED",
        "DRIFT ELIMINATOR",
        "GEARBOX RATIO",
        "FILL",
        "GEARBOX OIL",
        "REACTOR TYPE",
        "CATALYST",
        "CATALYST VOLUME",
        "DIAMETER (ID)",
        "SHELL MATERIAL",
        "TANGENT-TANGENT",
        "INTERNALS",
        "DESIGN PRESSURE",
        "HEATER",
        "OPERATING PRESSURE",
        "INERT MEDIUM",
        "DESIGN TEMP.",
        "REDUCTANT",
        "OPERATING TEMP.",
        "PSV",
        "TEMA TYPE",
        "TUBE LENGTH",
        "NO. OF TUBES",
        "DUTY",
        "TUBE PASSES",
        "SHELL SIDE FLUID",
        "TUBE MATERIAL",
        "TUBE SIDE FLUID",
        "SHELL DESIGN P/T",
        "TUBESHEET",
        "TUBE DESIGN P/T",
        "BAFFLE",
        "TUBE OD x BWG",
        "GASKET",
        "VESSEL TYPE",
        "HEAD TYPE",
        "CORROSION ALLOW.",
        "BOOT",
        "PWHT",
        "RADIOGRAPHY",
        "N2 BLANKET",
        "COMPRESSOR TYPE",
        "CYLINDER MATERIAL",
        "PISTON RINGS",
        "CAPACITY (SUCTION)",
        "PACKING",
        "SUCTION PRESSURE",
        "VALVES",
        "DISCHARGE PRESSURE",
        "LUBE SYSTEM",
        "SUCTION TEMP.",
        "SEAL GAS",
        "DISCHARGE TEMP.",
        "COOLING",
        "GAS",
        "VIBRATION MON.",
        "VALVE TYPE",
        "FAIL ACTION",
        "TAG / ITEM",
        "ACTUATOR",
        "BODY SIZE",
        "POSITIONER",
        "BODY RATING",
        "AIR SUPPLY",
        "BODY MATERIAL",
        "TRIM MATERIAL",
        "BENCH SET",
        "TRIM CHARACTERISTIC",
        "HANDWHEEL",
        "RATED CV",
        "SERVICE FLUID",
        "DRYER TYPE",
        "DRUM DIAMETER",
        "ROTOR SHAFT",
        "DRUM LENGTH",
        "GLAND PACKING",
        "ROTATION SPEED",
        "OIL SEAL",
        "HEATING MEDIUM",
        "O-RING",
        "ROTARY JOINT",
        "DRIVE CHAIN & SPROCKET",
        "OUTPUT",
        "ENCLOSURE",
        "POLES",
        "AREA CLASSIFICATION",
        "SPEED",
        "EX PROTECTION",
        "VOLTAGE",
        "FRAME",
        "RATED CURRENT",
        "WEIGHT (MOTOR)",
        "WEIGHT (MOTOR+GEARBOX)",
        "INSULATION CLASS",
        "MOUNTING",
        "EA-3401 HEATER OUTPUT",
        "HEATER VOLTAGE",
        "HEATER CURRENT",
        "TIC CONTROL",
        "HEATER TYPE",
        "BED TC's",
        "HEAT TRANSFER AREA",
        "STEAM CONSUMPTION",
        "CLEAN U",
        "SOLVENT INLET T",
        "SERVICE U",
        "SOLVENT OUTLET T",
        "FOULING (TUBE)",
        "PRESSURE DROP (TUBE)",
        "VOLUME",
        "PRODUCT NOZZLE N3",
        "REFLUX PUMP",
        "BOOT DRAIN N4",
        "INLET NOZZLE N1",
        "PSV NOZZLE N5",
        "REFLUX NOZZLE N2",
        "MANWAY",
        "CONTROLLER",
        "ACTION ON AIR FAIL",
        "INPUT SIGNAL",
        "SOLENOID",
        "STROKE",
        "LIMIT SWITCH",
        "LEAKAGE CLASS",
        "DRIVER SUPPLIER",
        "DRIVER TYPE",
        "DATASHEET REV",
    },
    key=lambda s: (-len(s.split()), s),
)
DS_HEADER = re.compile(
    r"DOC NO: (?P<doc_no>\S+) REV: (?P<rev>\d+) .*?ITEM / TAG NO\. (?P<tag>\S+) EQUIPMENT ID (?P<equipment_id>\S+) "
    r"EQUIPMENT NAME (?P<equipment_name>.+?) TYPE (?P<type>.+?) PLANT / UNIT (?P<plant>.+?) AREA (?P<area>.+?) "
    r"FUNCTIONAL LOC\. (?P<floc>\S+) CRITICALITY (?P<criticality>HIGH CRITICAL|LOW CRITICAL|NON CRITICAL) "
    r"SERVICE (?P<service>.+?) (?=DESIGN & MECHANICAL DATA)"
)
# (label as the sheet prints it, group key of DS_HEADER); the anchor is the printed label followed by the value
DS_HEADER_FIELDS = (
    ("DOC NO:", "doc_no"),
    ("REV:", "rev"),
    ("ITEM / TAG NO.", "tag"),
    ("EQUIPMENT ID", "equipment_id"),
    ("EQUIPMENT NAME", "equipment_name"),
    ("TYPE", "type"),
    ("PLANT / UNIT", "plant"),
    ("AREA", "area"),
    ("FUNCTIONAL LOC.", "floc"),
    ("CRITICALITY", "criticality"),
    ("SERVICE", "service"),
)
IDENTITY_FIELDS = (
    "EQUIPMENT ID",
    "FUNCTIONAL LOC.",
)  # typed identifiers a P&ID hotspot may bind to besides tags
NUM_UNIT = re.compile(
    r"^(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?=\s|$|[/)])\s*(?P<unit>[A-Za-z%][A-Za-z0-9/%.]*)?"
)


def value_num_unit(value):
    """Leading whole number of a value and the unit token after it; a range, a code or a text value gives (None, None)."""
    m = NUM_UNIT.match(value)
    if not m:
        return None, None
    return float(m.group("num").replace(",", "")), m.group("unit")


def datasheet_params(tag, text, rev_id, page_text, spans, claims):
    """DatasheetParam rows of one datasheet from its canonical text: the header block by DS_HEADER, the table blocks by
    the label vocabulary (longest label first, whole tokens, a label used once per sheet), values cut at the watermark."""
    out = []

    def emit(group, label, field, value):
        value = canonical(value)
        if not value:
            return
        sid = spans.add(rev_id, 1, page_text, f"{label} {value}")
        claims.add(sid, tag, "parameter", value)
        num, unit = value_num_unit(value)
        out.append(
            {
                "id": f"DSP-{tag}-{len(out) + 1:03d}",
                "equipment_tag": tag,
                "group": group,
                "field": field,
                "unit": unit,
                "value_text": value,
                "value_num": num,
                "span_id": sid,
            }
        )

    h = DS_HEADER.search(text)
    if not h:
        raise ValueError(f"datasheet header not parsed: {tag}")
    for label, key in DS_HEADER_FIELDS:
        emit("header", label, label.rstrip(":"), h.group(key))
    starts = sorted((text.find(g), g) for g in DS_GROUPS if g in text)
    end = min(i for i in (text.find("NOTES:"), len(text)) if i >= 0)
    for (pos, group), nxt in zip(starts, [s[0] for s in starts[1:]] + [end]):
        block = text[pos + len(group) : nxt]
        for cut in (WATERMARK, PROJECT_LINE):
            k = block.find(cut)
            if k >= 0:
                block = block[:k]
        toks = block.split()
        used, pairs, i = set(), [], 0
        while i < len(toks):
            hit = None
            for label in DS_LABELS:
                lt = label.split()
                if label not in used and toks[i : i + len(lt)] == lt:
                    hit = label
                    break
            if hit:
                used.add(hit)
                pairs.append([hit, []])
                i += len(hit.split())
            else:
                if pairs:
                    pairs[-1][1].append(toks[i])
                i += 1
        for label, value in pairs:
            emit(group, label, label, " ".join(value))
    return out


# ---------------------------------------------------------------- C&E sheets (9.3 Interlock, InterlockRow, StartPermissive)
ROLE_KIND = {
    "trip": "initiator",
    "control": "control",
    "alarm": "alarm",
    "mech": "relief",
}


def is_signal_tag(signal):
    """A permissive SIGNAL cell that names one device (PSL-2306, DVC6200) rather than a phrase (DCS reset, lockout)."""
    return " " not in signal and any(ch.isdigit() for ch in signal)


def interlock_entities(tag, parsed, text, rev_id, spans, claims):
    """Interlock, InterlockRow[], StartPermissive[] of one sheet from harness.master.parse_interlock output and the page
    text; the sheet's notes are the numbered sentences after its last NOTES: label (Set 2 prints a partial copy first)."""
    h = parsed["header"]
    seq = h["logic_no"]
    key = (
        seq or tag
    )  # the sheet key the harness uses everywhere (harness.master, harness.rulepack): LOGIC No, else the tag
    notes = []
    m = None
    for m in re.finditer(
        r"NOTES: (1\. .+?)(?= This is sample data|$)", text, re.IGNORECASE
    ):
        pass
    if m:
        for n, sentence in enumerate(re.split(r" (?=\d\. )", m.group(1)), start=1):
            sid = spans.add(rev_id, 1, text, sentence)
            claims.add(sid, key, "note", sentence)
            notes.append({"n": n, "text": sentence, "span_id": sid})
    interlock = {
        "seq_id": seq,
        "equipment_tag": tag,
        "logic_kind": parsed["kind"],
        "sil_sheet": h["sil"],
        "ce_doc_no": h["doc_no"],
        "ce_revision": str(h["rev"]),
        "notes": notes,
        "permissive_gate": parsed["start_permissives_gate"],
    }
    columns = {e["id"]: e["final_element"] for e in parsed["effects"]}
    rows = []
    for r in parsed["rows"]:
        anchor = (
            f"{r['id']} {r['initiator']} {r['tag']} {r['setpoint_text']} {r['vote_cell_text']}"
            + " X" * r["x_count"]
        )
        sid = spans.add(rev_id, 1, text, anchor)
        claims.add(sid, r["tag"], "row", anchor)
        rows.append(
            {
                "id": f"{key}-{r['id']}",
                "seq_id": seq,
                "equipment_tag": tag,
                "row_id": r["id"],
                "row_kind": r["row_kind"],
                "initiator": r["initiator"],
                "instrument_tag": r["tag"],
                "setpoint_value": r["setpoint_value"],
                "setpoint_unit": r["setpoint_unit"],
                "comparator": r["comparator"],
                "setpoint_text": r["setpoint_text"],
                "voting": r["voting"],
                "vote_cell_text": r["vote_cell_text"],
                "effects": [
                    {
                        "effect_id": eid,
                        "final_element": fe,
                        "marked": eid in r["effects"],
                    }
                    for eid, fe in columns.items()
                ],
                "effects_basis": "X count from the extracted text; column identity from packages/interlock_effects.json "
                "(agent_transcription, review pending), checked against the text by harness.master",
                "source_page": 1,
                "span_id": sid,
            }
        )
    perms = []
    for p in parsed["start_permissives"]:
        anchor = f"{p['n']} {p['condition']} {p['signal']}"
        sid = spans.add(rev_id, 1, text, anchor)
        sig = p["signal"] if is_signal_tag(p["signal"]) else None
        claims.add(sid, sig or key, "row", anchor)
        perms.append(
            {
                "seq_id": key,
                "n": p["n"],
                "text": p["condition"],
                "signal_tag": sig,
                "standing_bypass_state": None,
                "span_id": sid,
            }
        )
    return interlock, rows, perms


# ---------------------------------------------------------------- equipment, areas, instrument tags
def equipment_rows(master_rows, datasheets, drawings, plots, interlocks, resolver):
    """Equipment rows (9.3) from the fixture's equipment master and the parsed title blocks; document numbers are the
    typed DOC NO / DWG No of each class, the P&ID is named by its document id (a PNG carries no number of its own)."""
    out = []
    for e in master_rows:
        tag = e["tag"]
        out.append(
            {
                "tag": tag,
                "name": e["name"],
                "functional_location": e["functional_location"],
                "area_code": e["area_workbook"].split(" - ")[0],
                "service": e["service"],
                "criticality_datasheet": e["criticality_datasheet"],
                "criticality_workbook": e["criticality_workbook"],
                "interlock_ref": e["interlock_ref"],
                "datasheet_doc_no": datasheets[tag]["doc_no"],
                "ga_drawing_doc_no": drawings[tag]["dwg_no"],
                "pid_document_id": resolver.of(tag, "pid"),
                "plot_plan_doc_no": plots[tag]["dwg_no"],
                "ce_doc_no": interlocks[tag]["header"]["doc_no"],
            }
        )
    return sorted(out, key=lambda e: e["tag"])


def area_rows(rows, aliases):
    """Area rows from the workbook's area code and name and the per-class names of packages/area_aliases.json."""
    by_tag = {}
    for r in rows:
        by_tag.setdefault(r["Equipment_Tag"], Counter())[
            (str(r["Area_Code"]), r["Area_Name"])
        ] += 1
    out = []
    for tag in sorted(by_tag):
        (code, name), _ = by_tag[tag].most_common(1)[0]
        a = aliases[tag]
        out.append(
            {
                "code": code,
                "workbook_name": name,
                "datasheet_name": a["datasheet"],
                "opl_header_name": a["opl"],
                "plot_plan_title_name": a["plot_plan_title"],
            }
        )
    return sorted(out, key=lambda a: a["code"])


ROLE_ORDER = (
    "initiator",
    "final_element",
    "permissive",
    "control",
    "alarm",
    "relief",
    "monitor",
    "unknown",
)


def tag_tokens(text):
    return {t for t in INSTR.findall(text) if not NOT_A_TAG.match(t)}


def typed_tags(equipment_tags, interlocks_parsed, datasheet_texts):
    """{equipment_tag: {tag: role}} of the tags each asset's own documents type: its C&E rows (role by row kind),
    permissive signals, effect final elements, and every tag token of its datasheet. The asset's own tag is excluded."""
    out = {}
    for eq in sorted(equipment_tags):
        il = interlocks_parsed[eq]
        seen = [(r["tag"], ROLE_KIND[r["row_kind"]]) for r in il["rows"]]
        seen += [
            (p["signal"], "permissive")
            for p in il["start_permissives"]
            if is_signal_tag(p["signal"])
        ]
        seen += [
            (t, "final_element")
            for e in il["effects"]
            for t in sorted(tag_tokens(e["final_element"]))
        ]
        seen += [(t, "unknown") for t in sorted(tag_tokens(datasheet_texts[eq]))]
        roles = {}
        for tag, role in seen:  # the first document that types a tag names its role
            if tag not in equipment_tags and tag != eq:
                roles.setdefault(tag, role)
        out[eq] = roles
    return out


def binding_targets(typed, interlocks_parsed, datasheet_params_rows):
    """Every identifier a P&ID hotspot may bind to (the sidecar's own rule, AC-ING-12): the typed tags, the eight
    equipment tags, the LOGIC No each sheet types, and the datasheet's typed identity values (EQUIPMENT ID,
    FUNCTIONAL LOC.). G1 recomputes the same set from interlocks.json and datasheet_params.json."""
    out = {t for roles in typed.values() for t in roles} | set(typed)
    out |= {
        il["header"]["logic_no"]
        for il in interlocks_parsed.values()
        if il["header"]["logic_no"]
    }
    out |= {
        p["value_text"] for p in datasheet_params_rows if p["field"] in IDENTITY_FIELDS
    }
    return out


def instrument_tags(typed, texts_by_class, opl_texts, sidecars, resolver):
    """InstrumentTag rows: every tag an asset's C&E sheet or datasheet types, with the role its sheet types (first by
    ROLE_ORDER) and the documents it occurs in (typed documents, lessons and P&ID sidecars, by document id)."""
    rows = {}
    for eq in sorted(typed):
        for tag, role in typed[eq].items():
            r = rows.setdefault(
                tag, {"equipment_tag": eq, "roles": set(), "sources": set()}
            )
            r["roles"].add(role)
    for cls, texts in texts_by_class.items():
        for eq, text in texts.items():
            did = resolver.of(eq, cls)
            for tag in rows:
                if tag in text:
                    rows[tag]["sources"].add(did)
    for oid, text in opl_texts.items():
        for tag in rows:
            if tag in text:
                rows[tag]["sources"].add(resolver.by_opl[oid])
    for s in sidecars:
        for h in s["hotspots"]:
            if h["bound_tag"] in rows:
                rows[h["bound_tag"]]["sources"].add(s["document_id"])
    return [
        {
            "tag": tag,
            "equipment_tag": r["equipment_tag"],
            "role": next(x for x in ROLE_ORDER if x in r["roles"]),
            "sources": sorted(r["sources"]),
        }
        for tag, r in sorted(rows.items())
    ]


# ---------------------------------------------------------------- GA drawings (9.4 BomItem, BomMatch)
# item, part name (carries a letter, so the grid row "1 2 3 4 5 6" never matches), material, quantity; the extractor glues
# a title-block fragment after the last row's quantity on one drawing, so text may follow the quantity
BOM_LINE = re.compile(
    r"^(?P<no>\d{1,2}) (?P<name>(?=\S*[A-Za-z])\S+) (?P<material>\S+) (?P<qty>\d+(?:\.\d+)?[A-Za-z0-9]*)(?: .*)?$"
)
GENERIC_PART_WORDS = {"set", "kit", "pcs", "x"}


def bom_items(tag, raw_text, dwg_no, rev_id, page_text, spans, claims):
    """BomItem rows of one GA drawing: the numbered BILL OF MATERIAL lines (item, part name as printed, material, qty),
    read in raw line order and accepted only while the item numbers run 1, 2, 3, ... (the grid row '1 2 3 4 5 6' and the
    revision row '0 ISSUEDFORCONSTRUCTION ...' never continue the sequence)."""
    out, expected = [], 1
    for line in raw_text.split("\n"):
        m = BOM_LINE.match(canonical(line))
        if not m or int(m.group("no")) != expected:
            continue
        expected += 1
        anchor = m.group(0)[: m.end("qty")]
        sid = spans.add(rev_id, 1, page_text, anchor)
        item_id = f"BOM-{tag}-{int(m.group('no')):02d}"
        claims.add(sid, item_id, "bom", anchor)
        out.append(
            {
                "id": item_id,
                "equipment_tag": tag,
                "ga_drawing_doc_no": dwg_no,
                "item_no": int(m.group("no")),
                "description": m.group("name"),
                "material": None if m.group("material") == "-" else m.group("material"),
                "quantity": m.group("qty"),
                "span_id": sid,
            }
        )
    return out


def _squash(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def bom_matches(rows, items):
    """BomMatch rows: a recorded spare-part string matches a same-asset BOM item when every content word of the string
    (a parenthetical or "x4" quantity dropped, GENERIC_PART_WORDS ignored) occurs in the item's part name plus material;
    two candidates are ordered by which one's remaining part-name text the work order's narrative mentions."""
    by_tag = {}
    for it in items:
        by_tag.setdefault(it["equipment_tag"], []).append(it)
    out = []
    for w in sorted(rows, key=lambda r: r["WO_Number"]):
        part = str(w["Spare_Parts_Used"] or "").strip()
        if part in ("", "-"):
            continue
        core = re.sub(r"\(.*?\)|\bx\d+\b", " ", part)
        words = [
            x
            for x in re.findall(r"[a-z0-9]+", core.lower())
            if len(x) > 1 and x not in GENERIC_PART_WORDS
        ]
        cands = [
            it
            for it in by_tag.get(w["Equipment_Tag"], [])
            if words
            and all(
                x.upper() in _squash(it["description"] + " " + (it["material"] or ""))
                for x in words
            )
        ]
        narrative = {c: canonical(str(w[c] or "")) for c in NARR}
        ranked = []
        for it in cands:
            residue = _squash(it["description"])
            for x in words:
                residue = residue.replace(x.upper(), "")
            hit = next(
                (
                    narrative[c]
                    for c in NARR
                    if residue and residue in _squash(narrative[c])
                ),
                None,
            )
            ranked.append((0 if hit else 1, it["item_no"], it, hit))
        ranked.sort(key=lambda r: (r[0], r[1]))
        match = {
            "wo_number": w["WO_Number"],
            "part_string": part,
            "bom_item_id": None,
            "alternative_bom_item_id": None,
            "disambiguator_text": None,
            "status": "unmatched",
        }
        if ranked:
            match.update(
                bom_item_id=ranked[0][2]["id"],
                status="matched",
                disambiguator_text=ranked[0][3] if len(ranked) > 1 else None,
            )
            if len(ranked) > 1:
                match["alternative_bom_item_id"] = ranked[1][2]["id"]
        out.append(match)
    return out


# ---------------------------------------------------------------- lessons (9.5 Opl, OplStep, TroubleshootingRow)
SECTIONS = (
    (1, "PURPOSE / OBJECTIVE", "purpose"),
    (2, "SAFETY PRECAUTIONS", "safety_text"),
    (3, "TOOLS & MATERIALS REQUIRED", "tools_text"),
    (4, "DETAILED PROCEDURE / STEPS", "steps_text"),
    (5, "COMMON PROBLEMS & TROUBLESHOOTING", "troubleshooting_text"),
    (6, "KEY LEARNING POINTS", "key_learning"),
)
HEADING_LINE = {n: f"{n}. {h}" for n, h, _ in SECTIONS}
# ponytail: the acceptance cell of a step row is recovered as a trailing word run that closes step lines in at least
# ACCEPTANCE_MIN_LESSONS lessons (the three templates recur in 23, 21 and 12 lessons); a one-off acceptance phrase stays
# inside action_text, still verbatim under its hash. A table-aware extractor if a surface needs the split exactly.
ACCEPTANCE_MIN_LESSONS = 8
BULLET = re.compile(r"^[■●]\s*")
MIN_PREFIX = 15  # the CD-12 rule: a copied cell is a prefix of at least 15 characters


def _section_lines(raw, n):
    """Raw lines of section n (between its heading line and the next heading), the watermark lines dropped."""
    lines = raw.split("\n")
    start = next(i for i, x in enumerate(lines) if x.startswith(HEADING_LINE[n]))
    stop = next(
        (
            i
            for i, x in enumerate(lines)
            if i > start
            and re.match(r"^\d\. [A-Z]", x)
            and not x.startswith(HEADING_LINE[n])
        ),
        len(lines),
    )
    stop = next(
        (
            i
            for i, x in enumerate(lines)
            if i > start
            and (
                x.startswith("Prepared by")
                or (n < 6 and x.startswith(HEADING_LINE[n + 1]))
            )
        ),
        stop,
    )
    out = []
    for x in lines[start + 1 : stop]:
        if x.startswith("This is sample data") or x.strip() in (
            "CALIBER purposes only",
            "purposes only",
            "",
        ):
            continue
        out.append(x)
    return out


def step_lines(raw):
    return [x for x in _section_lines(raw, 4) if re.match(r"^\d ", x)]


def acceptance_vocabulary(raw_texts):
    """The template acceptance phrases: trailing word runs (up to five words) that close a step line in at least
    ACCEPTANCE_MIN_LESSONS lessons; the longest such run of a line is its acceptance criterion."""
    lessons_of = {}
    for oid, raw in raw_texts.items():
        for line in step_lines(raw):
            words = line.split()
            for k in range(1, 6):
                lessons_of.setdefault(" ".join(words[-k:]), set()).add(oid)
    return {ph for ph, ls in lessons_of.items() if len(ls) >= ACCEPTANCE_MIN_LESSONS}


def split_step(line, vocabulary):
    words = line.split()
    n = words[0]
    for k in range(5, 0, -1):
        tail = " ".join(words[-k:])
        if tail in vocabulary and len(words) - 1 - k > 0:
            return int(n), " ".join(words[1:-k]), tail
    return int(n), " ".join(words[1:]), None


def match_cell(text, breaks, pos, field):
    """A troubleshooting cell at `pos` copied from a work-order field: the whole field, or a prefix of at least MIN_PREFIX
    characters that ends (after an optional full stop) at a line break or the end of the text (the CD-12 rule).
    Returns (end position, cell text, truncated) or None."""
    if not field:
        return None
    n = 0
    while pos + n < len(text) and n < len(field) and text[pos + n] == field[n]:
        n += 1
    if n == len(field):
        return pos + n, field, False
    while n and text[pos + n - 1] == " ":
        n -= 1
    if n < MIN_PREFIX:
        return None
    j = pos + n
    if text.startswith(" .", j):
        j += 2
    elif text.startswith(".", j):
        j += 1
    if j == len(text) or (text[j] == " " and j in breaks):
        return j, text[pos : pos + n], True
    return None


def find_cell(text, breaks, field):
    """A copy of `field` anywhere in `text` (the extractor displaces some table cells past the footer): (cell text,
    truncated) of the longest copy, or None."""
    if not field:
        return None
    if len(field) <= MIN_PREFIX:
        return (field, False) if field in text else None
    best, start = None, 0
    while (i := text.find(field[:MIN_PREFIX], start)) >= 0:
        start = i + 1
        m = match_cell(text, breaks, i, field)
        if m and (best is None or len(m[1]) > len(best[1])):
            best = (m[1], m[2])
    return best


def troubleshooting_rows(oid, raw, wos):
    """TroubleshootingRow[] of one lesson: the section-5 table read back as copies of same-asset work-order rows
    (symptom, likely cause, action = problem description, root cause, corrective action), full or truncated. A row whose
    trailing cells the extractor displaced past the footer (OPL-DC-3401A) takes them from the rest of the lesson text.
    Returns the rows and the count of section-5 words no work-order row explains."""
    lines = _section_lines(raw, 5)
    if not lines or not lines[0].startswith("Symptom"):
        return [], len(lines)
    text, breaks = canonical_lines("\n".join(lines[1:]))
    rest, rbreaks = canonical_lines(raw[raw.find(HEADING_LINE[5]) :])
    rows, pos, skipped = [], 0, 0
    while pos < len(text):
        best = None
        for w in wos:
            p, cells = pos, []
            for c in NARR:
                m = match_cell(text, breaks, p, canonical(str(w[c] or "")))
                if not m:
                    break
                p = m[0] + (1 if m[0] < len(text) and text[m[0]] == " " else 0)
                cells.append(m)
            if cells and (best is None or len(cells) > len(best[1])):
                best = (w, cells, p)
            if len(cells) == 3:
                break
        if best:
            w, cells, p = best
            texts, truncated = [c[1] for c in cells], any(c[2] for c in cells)
            for c in NARR[len(cells) :]:
                found = find_cell(rest, rbreaks, canonical(str(w[c] or "")))
                texts.append(found[0] if found else "")
                truncated = truncated or not found or found[1]
            rows.append(
                {
                    "opl_id": oid,
                    "n": len(rows) + 1,
                    "problem": texts[0],
                    "cause": texts[1],
                    "action": texts[2],
                    "quoted_wo_number": w["WO_Number"],
                    "truncated": truncated,
                }
            )
            pos = p
        else:
            nxt = text.find(" ", pos)
            pos = nxt + 1 if nxt >= 0 else len(text)
            skipped += 1
    return rows, skipped


def opl_entities(oid, lp, raw, pages, rev_id, vocabulary, wos, spans, claims):
    """Opl, OplStep[], TroubleshootingRow[] of one lesson plus the count of section-5 words no row explains."""
    page_text = " ".join(pages)
    sections = [
        {
            "n": n,
            "heading": heading,
            "body_text": lp[key],
            "body_hash": quote_hash(lp[key]),
        }
        for n, heading, key in SECTIONS
    ]
    permit_lines = []
    for n in (2, 3, 4):
        for line in _section_lines(raw, n):
            if re.search(r"permit", line, re.IGNORECASE) and not line.startswith(
                "Step Action"
            ):
                t = canonical(BULLET.sub("", line))
                sid = spans.locate(rev_id, pages, t)
                claims.add(sid, oid, "note", t)
                permit_lines.append({"text": t, "span_id": sid, "source_section": n})
    steps = []
    for line in step_lines(raw):
        n, action, acceptance = split_step(canonical(line), vocabulary)
        sid = spans.locate(rev_id, pages, canonical(line))
        claims.add(sid, oid, "step", action)
        steps.append(
            {
                "opl_id": oid,
                "n": n,
                "action_text": action,
                "acceptance_criterion": acceptance,
                "source_hash": quote_hash(action),
                "span_id": sid,
            }
        )
    rows, skipped = troubleshooting_rows(oid, raw, wos)
    opl = {
        "document_revision_id": rev_id,
        "opl_id": oid,
        "title": lp["title"],
        "discipline": lp["discipline"],
        "equipment_tag": lp["tag"],
        "area_unit": lp["area_unit"],
        "related_interlock_text": lp["related_interlock"],
        "pid_ref": lp["pid_ref"],
        "classification": lp["classification"],
        "aspect": re.search(r"Aspect: (\S+)", page_text).group(1),
        "sections": sections,
        "permit_lines": permit_lines,
        "footer": {
            "prepared_by": lp["prepared_by_role"] or "",
            "reviewed_by_alias": lp["reviewed_by_id"] or "",
            "approved_by_alias": lp["approved_by_id"] or "",
            "date_of_sharing": lp["date_of_sharing"] or "",
        },
        "machine_drafted": False,
        "approver_alias": lp["approved_by_id"],
    }
    return opl, steps, rows, skipped


# ---------------------------------------------------------------- workbook (9.4)
FLAG_NAMES = {
    "Breakdown": "breakdown",
    "Downtime_Hours": "downtime_hours",
    "Labor_Hours": "labor_hours",
    "Labor_Cost_IDR": "labor_cost_idr",
    "Material_Cost_IDR": "material_cost_idr",
    "Total_Cost_IDR": "total_cost_idr",
    "Reported_By": "reported_by_alias",
    "Executed_By": "executed_by_alias",
    "Approved_By": "approved_by_alias",
    "Related_Interlock": "related_interlock",
    "Remarks": "remarks",
}


def _iso(dt):
    return dt.isoformat() if dt is not None else None


def _text_or_none(v):
    v = str(v).strip() if v is not None else ""
    return None if v in ("", "-", "None") else v


def work_orders(rows):
    out = []
    for w in sorted(rows, key=lambda r: r["WO_Number"]):
        out.append(
            {
                "wo_number": w["WO_Number"],
                "notification_no": w["Notification_No"],
                "report_date": _iso(w["Report_Date"]),
                "start_date": _iso(w["Start_Date"]),
                "completion_date": _iso(w["Completion_Date"]),
                "status": w["Status"],
                "equipment_tag": w["Equipment_Tag"],
                "work_type": w["Work_Type"],
                "discipline": w["Discipline"],
                "priority": w["Priority"],
                "criticality": w["Criticality"],
                "problem_description": w["Problem_Description"] or "",
                "root_cause": w["Root_Cause"] or "",
                "corrective_action": w["Corrective_Action"] or "",
                "spare_parts_used": w["Spare_Parts_Used"] or "",
                "breakdown": w["Breakdown"] == "Yes",
                "downtime_hours": w["Downtime_Hours"],
                "labor_hours": w["Labor_Hours"],
                "labor_cost_idr": w["Labor_Cost_IDR"],
                "material_cost_idr": w["Material_Cost_IDR"],
                "total_cost_idr": w["Total_Cost_IDR"],
                "reported_by_alias": emp_alias(w["Reported_By"]) or "",
                "executed_by_alias": emp_alias(w["Executed_By"]) or "",
                "approved_by_alias": emp_alias(w["Approved_By"]) or "",
                "related_interlock": _text_or_none(w["Related_Interlock"]),
                "remarks": _text_or_none(w["Remarks"]),
                "closeout_complete": w["closeout_complete"],
                "completeness_flags": {
                    FLAG_NAMES[c]: w[c] not in (None, "") for c in OUTCOME_FIELDS
                },
                "breakdown_kind": w["breakdown_kind"] or "none",
                "notification_lead_hours": (
                    w["Start_Date"] - w["Report_Date"]
                ).total_seconds()
                / 3600,
            }
        )
    return out


def failure_events(rows):
    return [
        {
            "wo_number": w["WO_Number"],
            "equipment_tag": w["Equipment_Tag"],
            "report_date": _iso(w["Report_Date"]),
            "downtime_hours": w["Downtime_Hours"],
            "maintenance_cost_idr": w["Total_Cost_IDR"],
            "breakdown_kind": w["breakdown_kind"],
        }
        for w in sorted(rows, key=lambda r: r["WO_Number"])
        if w["breakdown_kind"]
    ]


PROOF_CLASS = {
    "sis_proof_test": "sis_proof_test",
    "sil_logic_proof_test": "sil_logic_test",
    "calibration_proof_test": "calibration_proof_test",
    "psv_statutory_test": "statutory_relief_test",
}


def proof_tests(fixture_block, rows):
    """ProofTest rows from the fixture's proof_tests.classes items (the 33 classified work orders) and the workbook."""
    by_wo = {w["WO_Number"]: w for w in rows}
    out = []
    for name, block in fixture_block["classes"].items():
        cls = PROOF_CLASS[name]
        for it in block["items"]:
            w = by_wo[it["wo"]]
            device = INSTR.search(str(w["Corrective_Action"] or "")) or INSTR.search(
                str(w["Problem_Description"] or "")
            )
            found_left = cls in ("calibration_proof_test", "statutory_relief_test")
            out.append(
                {
                    "wo_number": it["wo"],
                    "equipment_tag": it["tag"],
                    "seq_id": it["seq"],
                    "device_tag": device.group(0) if device else None,
                    "test_class": cls,
                    "completion_date": _iso(w["Completion_Date"]),
                    "result_text": w["Root_Cause"] or "",
                    "as_found": (w["Root_Cause"] or None) if found_left else None,
                    "as_left": (w["Corrective_Action"] or None) if found_left else None,
                }
            )
    return sorted(out, key=lambda t: t["wo_number"])


def causal_links(link_list, row_of, row_texts, wb_rev_id, spans, claims):
    """CausalLink rows from the fixture's chains.link_list; the linking sentence is anchored in the workbook row of B."""
    out = []
    for i, link in enumerate(link_list, start=1):
        page = row_of[link["to_wo"]]
        sid = spans.add(wb_rev_id, page, row_texts[page], link["linking_sentence"])
        claims.add(sid, link["to_wo"], "narrative", link["linking_sentence"])
        out.append(
            {
                "id": f"CL-{i:02d}",
                "from_wo": link["from_wo"],
                "to_wo": link["to_wo"],
                "equipment_tag": link["tag"],
                "mechanism_noun": link["noun"],
                "interval_days": link["days"],
                "linking_sentence": link["linking_sentence"],
                "linking_field": link["field"].lower(),
                "span_id": sid,
            }
        )
    return out


# ---------------------------------------------------------------- coverage, debt (9.5) and the register, from the fixture
def coverage_method(fx):
    m, t = fx["method"], fx["method"]["threshold"]
    return {
        "recipe_sha256": m["recipe_sha256"],
        "stop_list_sha256": m["stop_list_sha256"],
        "threshold": t,
        "window_multiplier": m["window_multiplier"],
        "min_content_words": m["min_content_words"],
        "comparison": m["comparison"],
        "extractor": fx["inventory"]["extractor"],
        "strict_sections": m["strict_sections"],
        "strict_cut_marker": m["strict_cut_marker"],
        "labels_status": m["labels_status"],
        "unscoreable_ids": m["unscoreable_ids"],
    }


def coverage_assessments(fx):
    t = fx["method"]["threshold"]
    out = []
    for wo in sorted(fx["coverage_scores"]):
        for layer in ("generous", "strict"):
            s = fx["coverage_scores"][wo][layer]
            out.append(
                {
                    "wo_number": wo,
                    "layer": layer,
                    "covered": s["best_ratio"] > t,
                    "best_ratio": s["best_ratio"],
                    "threshold": t,
                    "matched_field": s["matched_field"],
                    "matched_lesson": s["matched_lesson"],
                    "corpus_version_id": CORPUS_VERSION_ID,
                }
            )
    return out


def coverage_summaries(fx):
    t = fx["method"]["threshold"]
    b = next(x for x in fx["coverage"]["bands"]["unplanned_failure"] if x["t"] == t)
    bands = {k: b[k] for k in ("no_lesson", "copied_row_only", "taught")}
    out = []
    for layer in ("generous", "strict"):
        for pop in sorted(fx["coverage"][layer]):
            rows = fx["coverage"][layer][pop]
            r = next(x for x in rows if x["t"] == t)
            out.append(
                {
                    "corpus_version_id": CORPUS_VERSION_ID,
                    "population": pop,
                    "layer": layer,
                    "threshold": t,
                    "uncovered_count": r["uncovered"],
                    "population_count": r["n"],
                    "uncovered_breakdowns": r["breakdowns"],
                    "uncovered_downtime_hours": r["downtime_h"],
                    "uncovered_cost_idr": int(r["cost_idr"]),
                    "bands": bands if pop == "unplanned_failure" else None,
                    "sensitivity": [
                        {"t": x["t"], "uncovered_count": x["uncovered"]} for x in rows
                    ],
                }
            )
    return out


def debt_clusters(fx):
    d = fx["debt"]
    out = []
    for p in d["per_asset"]:
        out.append(
            {
                "id": f"DEBT-{p['tag']}",
                "equipment_tag": p["tag"],
                "corpus_version_id": CORPUS_VERSION_ID,
                "uncovered_wo_numbers": p["uncovered_wo_numbers"],
                "factors": {
                    "D_hours": p["D_h"],
                    "D_max": d["D_max"],
                    "C_idr": int(p["C_idr"]),
                    "C_max": int(d["C_max"]),
                    "k": p["k"],
                    "r": p["r"],
                },
                "coefficients": d["coefficients"],
                "incomplete_uncovered": p["incomplete_uncovered"],
                "score": p["score"],
                "rank": p["rank"],
            }
        )
    return sorted(out, key=lambda c: c["rank"])


def _rule_key(rid):
    return int(rid[3:])


def integrity_findings(fx, rows, opl_parsed, interlocks, resolver):
    """One finding per register item of the fixture's integrity block: the rule's own fields (name, severity, unit, basis,
    observation flag), the document the item is about, the discipline the record or lesson types, the LOGIC No of the
    asset's sheet where the rule concerns it, and the item verbatim. span_id and routing_recommendation carry nothing
    the data states (null); state is "open" for every finding of corpus version 1."""
    wo_disc = {w["WO_Number"]: w["Discipline"] for w in rows}
    pid_of_set = resolver.pid_by_set
    out = []
    for rid in sorted(
        (k for k in fx["integrity"] if k.startswith("CD-")), key=_rule_key
    ):
        block = fx["integrity"][rid]
        name, _definition, unit, basis, severity, obs = RULES[rid]
        for i, item in enumerate(block["items"], start=1):
            tag, oid, wo, set_no = (
                item.get("tag"),
                item.get("opl_id"),
                item.get("wo"),
                item.get("set"),
            )
            if oid:
                doc = resolver.by_opl[oid]
            elif set_no:
                doc = pid_of_set[set_no]
            elif wo:
                doc = resolver.workbook
            elif unit == "drawing":
                doc = resolver.of(tag, "ga_drawing")
            elif unit == "sheet":
                doc = resolver.of(tag, "interlock")
            elif unit == "asset":
                doc = resolver.of(tag, "datasheet")
            else:
                doc = None
            if oid:
                discipline = opl_parsed[oid]["discipline"]
            elif wo:
                discipline = wo_disc[wo]
            else:
                discipline = None
            concerns_sheet = rid in ("CD-8", "CD-17") or (
                rid == "CD-18" and item.get("sibling") == "interlock"
            )
            out.append(
                {
                    "id": f"{rid}-{i:03d}",
                    "rule_id": rid,
                    "rule": name,
                    "severity": severity,
                    "discipline": discipline,
                    "observation_only": obs,
                    "unit": unit,
                    "basis": basis,
                    "document_id": doc,
                    "span_id": None,
                    "state": "open",
                    "safety_function": interlocks[tag]["header"]["logic_no"]
                    if concerns_sheet and tag
                    else None,
                    "routing_recommendation": None,
                    "item": item,
                }
            )
    return out


# ---------------------------------------------------------------- P&ID sidecars (9.3 PidSidecar, D-12)
UNBOUND_DEFAULT = (
    "no corresponding tag typed in the asset's cause-and-effect sheet or datasheet"
)


def sidecar(adopted, document_id, known):
    """The bundle's PidSidecar from the adopted packages/pid_sidecars/set_0n.json: the PNG file name becomes the document
    id; a null binding without a reason gets the default reason; a binding outside `known` (binding_targets: what a
    cause-and-effect sheet or datasheet types, the sidecar's own rule for bound_tag, AC-ING-12) is nulled with the
    reason stated; a foreign hotspot binds through the foreign asset's typed set. Returns the sidecar and the count of
    bindings nulled."""
    out = dict(adopted, document_id=document_id, hotspots=[])
    nulled = 0
    for h in adopted["hotspots"]:
        h = dict(h)
        if h["bound_tag"] is None:
            h["unbound_reason"] = h["unbound_reason"] or UNBOUND_DEFAULT
        elif h["bound_tag"] not in known:
            h["unbound_reason"] = (
                f"drawn '{h['as_drawn_text']}' was read as {h['bound_tag']}, which no cause-and-effect sheet or "
                "datasheet types"
            )
            h["bound_tag"] = None
            nulled += 1
        out["hotspots"].append(h)
    return out, nulled


if __name__ == "__main__":
    assert value_num_unit("45 m3/h") == (45.0, "m3/h") and value_num_unit(
        "6 barg / FV"
    ) == (6.0, "barg")
    assert value_num_unit("3x2x10 CDX-M") == (None, None) and value_num_unit(
        "95-110 degC"
    ) == (None, None)
    assert value_num_unit("1,150,000 m3/h") == (1150000.0, "m3/h") and value_num_unit(
        "246"
    ) == (246.0, None)
    text, breaks = canonical_lines(
        "Hexane leak observed at GA-1201A\nseal gland during operation, seal dr.\nNext cell"
    )
    assert match_cell(
        text,
        breaks,
        0,
        "Hexane leak observed at GA-1201A seal gland during operation, seal drips",
    ) == (
        len(text) - len("Next cell") - 1,
        "Hexane leak observed at GA-1201A seal gland during operation, seal dr",
        True,
    )
    assert match_cell("abc def", set(), 0, "abc def") == (7, "abc def", False)
    assert (
        match_cell("abc", set(), 0, "xyz") is None
        and match_cell("abc", set(), 0, "") is None
    )
    assert find_cell(
        text,
        breaks,
        "Hexane leak observed at GA-1201A seal gland during operation, seal drips",
    ) == (
        "Hexane leak observed at GA-1201A seal gland during operation, seal dr",
        True,
    )
    assert split_step(
        "3 Rotate and capture readings Torque / clearance to spec",
        {"Torque / clearance to spec"},
    ) == (3, "Rotate and capture readings", "Torque / clearance to spec")
    assert BOM_LINE.match("2 TOPHEAD(2:1ELLIP) SA-516-70 1") and not BOM_LINE.match(
        "1 2 3 4 5 6"
    )
    m = BOM_LINE.match("12 STEAMTUBEBUNDLE SS304 1 ROTARY DRUM (SM400B) 9000 mm")
    assert m and m.group(0)[: m.end("qty")] == "12 STEAMTUBEBUNDLE SS304 1"
    assert is_signal_tag("DVC6200") and is_signal_tag("PSL-2306")
    assert not is_signal_tag("DCS reset")
    assert tag_tokens(
        "TJC-LLD-DS-GA-1201A PSV PSV-3401 set 6 barg TE-3401-1..8 SEQ-3401 EMP-1113"
    ) == {
        "PSV-3401",
        "TE-3401",
    }
    print("entities: ok")
