"""Rule pack v1 reference matcher (blueprint 9.10): a pure function of the pack and the text.

classify(pack, text) applies R1 permanent change, R2 defeat targeted, R3 documented bypass, R4 defeat untargeted and
R5 none, in pack order, with the four suppression vocabularies read from the file, the window of
lexicons.window_tokens and both languages. screen_outbound(pack, text, whitelisted_spans) is the outbound gate: the
verbatim spans of approved lessons are cut from the artefact before the pack runs. parse_interlocks() regenerates
protective_vocabulary from the eight C&E sheets so every row is corpus-derived and testable; refresh() rewrites the
corpus-derived parts of rulepack/v1.json (the rows and the outbound fixture) in place.

Matcher constants the frozen shape has no field for, pinned here and in rulepack/README.md and mirrored by the
TypeScript port: GAP (a '*' inside a lexicon phrase matches 0 to 3 tokens), OBJECT (a defeat phrase is targeted when a
protective token starts inside it or within 4 tokens after it), CONTEXT (a suppression looks 2 tokens before or after a
phrase) and BAHASA (function words that mark a Bahasa Indonesia question).
"""

import json
import os
import re
import sys
from typing import Any

from .config import ROOT
from .pdftext import canonical, class_texts, must_match, opl_texts

DEFAULT = os.path.join(ROOT, "rulepack", "v1.json")
TOKEN = re.compile(r"\*|[a-z]{1,4}-\d{2,6}[a-z]?|[a-z0-9]+")
TAG = re.compile(r"\b[A-Z]{2,4}-\d{4,5}[A-Z]?\b")
GAP, OBJECT, CONTEXT = 3, 4, 2
MOMENTS = ("readiness", "trip", "job", "reading")
RULES = (
    "R1-permanent-change",
    "R2-defeat-targeted",
    "R3-documented-bypass",
    "R4-defeat-untargeted",
    "R5-none",
)
# ponytail: word-list language detection over the pack's own Bahasa lexicons plus these function words; a real
# detector only if the application needs one.
BAHASA = frozenset(
    [
        "apa",
        "apakah",
        "bagaimana",
        "berapa",
        "kapan",
        "kenapa",
        "mengapa",
        "siapa",
        "yang",
        "dan",
        "untuk",
        "dengan",
        "pada",
        "dari",
        "tidak",
        "bisa",
        "boleh",
        "harus",
        "sudah",
        "belum",
        "saat",
        "sebelum",
        "supaya",
        "agar",
        "tolong",
        "dulu",
        "semalam",
        "walaupun",
        "kalau",
        "jika",
    ]
)

# --- C&E sheet parser (raw pdftotext lines, canonicalised per line) ---
HDR = re.compile(
    r"DOC NO: (TJC-LLD-IL-\S+) .*?LOGIC No: (.+?) DESCRIPTION: (.+?) SIL: (SIL \d|N/A) TAG: (\S+) FLOC: (\S+)"
)
ROW = re.compile(
    r"^([TCAR]\d) (.+?) ([A-Z]{2,4}-\d{4,5}) (.+?) (1oo1|1oo2|2oo3|control|alarm|mech)((?: X)+)$"
)
EFF = re.compile(r"^(EFF-\d) (.+)$")
PERM = re.compile(
    r"^(\d) (.+?) (DCS reset|LG gearbox|FSL upstream|lockout|DVC6200|[A-Z]{2,4}-\d{4,5})$"
)
NOTE = re.compile(r"1\. (Trip set points are [^.]*\.).*?3\. (A trip is latched[^.]*\.)")


def parse_interlocks(texts=None):
    """protective_vocabulary rows (9.10) for the eight sheets, sorted by seq_id or tag; every string is verbatim from
    the sheet. initiators are the instrument tags of the T rows (the C, A and R layer tags on a control_loop_only
    sheet); permissives keep the sheet line after its number; effects are the EFF actions."""
    texts = texts if texts is not None else class_texts("interlock", canon=False)
    rows = []
    for tag in sorted(texts):
        raw = texts[tag]
        h = must_match(HDR.search(canonical(raw)), f"cause-and-effect header of {tag}")
        n = must_match(NOTE.search(canonical(raw)), f"cause-and-effect note of {tag}")
        lines = [canonical(line) for line in raw.splitlines()]
        seq = h.group(2) if h.group(2).startswith("SEQ-") else None
        rows.append(
            {
                "seq_id": seq,
                "equipment_tag": h.group(5),
                "kind": "trip_logic" if seq else "control_loop_only",
                "sil": int(h.group(4)[-1]) if seq else None,
                "ce_doc_no": h.group(1),
                "initiators": [
                    m.group(3) for m in (ROW.match(line) for line in lines) if m
                ],
                "permissives": [
                    {"n": int(m.group(1)), "text": m.group(2) + " " + m.group(3)}
                    for m in (PERM.match(line) for line in lines)
                    if m
                ],
                "effects": [
                    m.group(2) for m in (EFF.match(line) for line in lines) if m
                ],
                "reset_note": n.group(2),
                "setpoint_qualifier": n.group(1),
            }
        )
    return sorted(rows, key=lambda r: r["seq_id"] or r["equipment_tag"])


def protective_terms(row):
    """The tokens that name a row's function: its tag and SEQ id, its initiator tags and every tag inside its
    permissive lines and effect actions."""
    terms = (
        {row["equipment_tag"]}
        | ({row["seq_id"]} if row["seq_id"] else set())
        | set(row["initiators"])
    )
    terms |= {t for p in row["permissives"] for t in TAG.findall(p["text"])}
    terms |= {t for e in row["effects"] for t in TAG.findall(e)}
    return sorted(terms)


# --- matching primitives ---
def tokens(text):
    return TOKEN.findall((text or "").lower())


def _alts(toks):
    """Per token, the forms a lexicon phrase may match: the token itself and, for a tag, its alphabetic prefix
    ('psv-8901' also matches the generic 'psv')."""
    return [{t, t.split("-")[0]} if "-" in t else {t} for t in toks]


def _match_end(p, toks, i, alts):
    """End index (exclusive) of the first match of phrase tokens `p` starting at `i`, or None."""
    if not p:
        return i
    if p[0] == "*":
        for k in range(GAP + 1):
            if i + k <= len(toks):
                e = _match_end(p[1:], toks, i + k, alts)
                if e is not None:
                    return e
        return None
    if i < len(toks) and p[0] in alts[i]:
        return _match_end(p[1:], toks, i + 1, alts)
    return None


def _hits(phrases, toks, alts):
    """[(start, end, phrase, key)] for every occurrence of every (phrase, phrase_tokens, key), sorted by position,
    a shorter phrase before a longer one at the same start."""
    out = []
    for ph, pt, key in phrases:
        for i in range(len(toks)):
            e = _match_end(pt, toks, i, alts)
            if e is not None:
                out.append((i, e, ph, key))
    return sorted(out, key=lambda h: (h[0], h[1]))


def _phrases(strings, key=None):
    return [(s, tokens(s), key) for s in strings]


def _gap(a, b):
    """Tokens between two hits; 0 when they touch or overlap."""
    return max(b[0] - a[1], a[0] - b[1], 0)


_COMPILED: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}


def _compile(pack):
    hit = _COMPILED.get(id(pack))
    if hit is not None and hit[0] is pack:
        return hit[1]
    lx = pack["lexicons"]
    defeat_en, defeat_id = lx["defeat"]["en"], lx["defeat"]["id"]
    words = {p for p in defeat_en + defeat_id if len(tokens(p)) == 1}
    en = defeat_en + lx["permanent_change"]["verbs_en"] + lx["procedure_phrases"]["en"]
    idl = defeat_id + lx["permanent_change"]["verbs_id"] + lx["procedure_phrases"]["id"]
    protective = _phrases(pack["generic_protective_tokens"])
    for row in pack["protective_vocabulary"]:
        protective += _phrases(
            protective_terms(row), row["seq_id"] or row["equipment_tag"]
        )
    c = {
        "window": lx["window_tokens"],
        "protective": protective,
        "nouns": _phrases(lx["permanent_change"]["nouns"]),
        "defeat": _phrases(defeat_en + defeat_id),
        # a permit phrase reports a missing permit unless a defeat word sits inside it ("override without a permit")
        "permit_only": {
            p
            for p in defeat_en + defeat_id
            if {"permit", "izin"} & set(tokens(p)) and not words & set(tokens(p))
        },
        "change": _phrases(
            lx["permanent_change"]["verbs_en"] + lx["permanent_change"]["verbs_id"]
        ),
        "procedure": _phrases(
            lx["procedure_phrases"]["en"] + lx["procedure_phrases"]["id"]
        ),
        "artefacts": _phrases(lx["suppressions"]["named_artefacts"]),
        "entities": _phrases(
            sorted({e["entity"] for e in pack["documented_bypass_entities"]})
        ),
        "moments": {m: _phrases(pack["moment_keywords"][m]) for m in MOMENTS},
        "bahasa": BAHASA
        | (
            {t for p in idl for t in tokens(p)}
            - {t for p in en for t in tokens(p)}
            - {"*"}
        ),
    }
    _COMPILED[id(pack)] = (pack, c)
    return c


def load(path=DEFAULT):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(pack):
    """The canonical file form: keys in the 9.10 order as loaded, one-space indent, UTF-8, trailing newline."""
    return json.dumps(pack, indent=1, ensure_ascii=False) + "\n"


# --- the matcher ---
def classify(pack, text):
    """{intent_class, rule_id, matched_phrase, protective_function, entity, language_detected, moment} for a text.

    Rules in pack order. R1: a permanent_change verb phrase within window_tokens of a protective token (a
    protective_vocabulary term, a generic protective token or a permanent_change noun). R2: a surviving defeat phrase
    whose object is a protective token (one starts inside the phrase or within OBJECT tokens after it). R3: a
    documented_bypass entity is named and a procedure phrase occurs. R4: a surviving defeat phrase without a
    protective object. R5: none. A defeat phrase survives when it sits within window_tokens of a protective token
    and no suppression removes it: it is not part of a named artefact, not followed within CONTEXT tokens by a
    record label, not preceded within CONTEXT tokens by a passive marker while a record label occurs in the text,
    and not preceded within CONTEXT tokens by a negation prefix. When standalone_without_permit is set, permit
    phrases alone report a missing permit and count only beside another surviving defeat phrase.
    """
    c = _compile(pack)
    sup = pack["lexicons"]["suppressions"]
    toks = tokens(text)
    alts = _alts(toks)
    prot = _hits(c["protective"], toks, alts)
    artefacts = _hits(c["artefacts"], toks, alts)
    entities = _hits(c["entities"], toks, alts)
    labels = set(sup["record_labels"])
    passive = set(sup["passive_record_question_markers"])
    negs = set(sup["negation_prefixes"])
    records = bool(labels & set(toks))

    def near(h, targets):
        return any(_gap(h, t) <= c["window"] for t in targets)

    def survives(h):
        s, e = h[0], h[1]
        if any(a[0] < e and s < a[1] for a in artefacts):
            return False
        if labels & set(toks[e : e + CONTEXT]):
            return False
        before = set(toks[max(0, s - CONTEXT) : s])
        if records and before & passive:
            return False
        return not before & negs

    def nearest(h):
        p = min(prot, key=lambda p: _gap(h, p), default=None)
        return " ".join(toks[p[0] : p[1]]) if p else None

    defeat = [
        h for h in _hits(c["defeat"], toks, alts) if near(h, prot) and survives(h)
    ]
    if sup["standalone_without_permit"] and all(
        h[2] in c["permit_only"] for h in defeat
    ):
        defeat = []
    targeted = [(h, p) for h in defeat for p in prot if h[0] <= p[0] < h[1] + OBJECT]
    change = [
        h
        for h in _hits(c["change"], toks, alts)
        if near(h, prot + _hits(c["nouns"], toks, alts))
    ]
    procedure = _hits(c["procedure"], toks, alts)
    if change:
        intent, rule, phrase, entity = (
            "permanent_change",
            RULES[0],
            change[0][2],
            nearest(change[0]),
        )
    elif targeted:
        h, p = targeted[0]
        intent, rule, phrase, entity = (
            "defeat",
            RULES[1],
            h[2],
            " ".join(toks[p[0] : p[1]]),
        )
    elif entities and procedure:
        intent, rule, phrase, entity = (
            "documented_bypass",
            RULES[2],
            procedure[0][2],
            entities[0][2],
        )
    elif defeat:
        intent, rule, phrase, entity = (
            "defeat",
            RULES[3],
            defeat[0][2],
            nearest(defeat[0]),
        )
    else:
        intent, rule, phrase, entity = "none", RULES[4], None, None
    return {
        "intent_class": intent,
        "rule_id": rule,
        "matched_phrase": phrase,
        "protective_function": next((p[3] for p in prot if p[3]), None),
        "entity": entity,
        "language_detected": "id" if c["bahasa"] & set(toks) else "en",
        "moment": moment(pack, text),
    }


def moment(pack, text):
    """Template inference: the moment with the most distinct keyword phrases wins; ties fall to the pack order;
    None when no keyword occurs."""
    c = _compile(pack)
    toks = tokens(text)
    alts = _alts(toks)
    best, best_n = None, 0
    for m in MOMENTS:
        n = len({h[2] for h in _hits(c["moments"][m], toks, alts)})
        if n > best_n:
            best, best_n = m, n
    return best


def screen_outbound(pack, text, whitelisted_spans):
    """The outbound gate (9.10): every whitelisted span, the verbatim canonical text of an approved lesson or a
    span of one, is cut from the artefact before the pack runs, and the pack classifies what remains. Returns
    {blocked, whitelisted, residual}: whitelisted when nothing remains after the cut, blocked when the residual
    classifies defeat or permanent_change; residual is that classification."""
    t = canonical(text)
    for span in sorted(
        (canonical(s) for s in whitelisted_spans), key=len, reverse=True
    ):
        if span:
            t = t.replace(span, " ")
    residual = canonical(t)
    r = classify(pack, residual)
    return {
        "blocked": r["intent_class"] in ("defeat", "permanent_change"),
        "whitelisted": residual == "",
        "residual": r,
    }


def refresh(path=DEFAULT):
    """Rewrite the corpus-derived parts of the pack in place: protective_vocabulary from the eight sheets and
    fixtures.outbound from the classifier over the 56 approved lessons. Returns the pack."""
    pack = load(path)
    pack["protective_vocabulary"] = parse_interlocks()
    lessons = opl_texts()
    pack["fixtures"]["outbound"] = [
        {
            "opl_id": k,
            "expect_blocked": screen_outbound(pack, v, lessons.values())["blocked"],
            "expect_class_without_whitelist": classify(pack, v)["intent_class"],
        }
        for k, v in sorted(lessons.items())
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(pack))
    return pack


if __name__ == "__main__":
    if sys.argv[1:] == ["--refresh"]:
        p = refresh()
        print(
            f"{len(p['protective_vocabulary'])} rows and {len(p['fixtures']['outbound'])} outbound fixtures written"
        )
    else:
        print(
            json.dumps(
                classify(load(), " ".join(sys.argv[1:])), indent=1, ensure_ascii=False
            )
        )
