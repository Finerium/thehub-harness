"""Rule pack v1 reference matcher (plan Task 5.1; DP-08, DP-09, DP-21, AE-32; Addendum A5 moment inference).

Deterministic and model-free: lower-case tokens with tags kept whole, lexicon phrases with '*' gaps, and the ordered
rules of rulepack/v1.json. parse_interlocks() rebuilds the protective-function vocabulary from the eight C&E sheets
(harness.pdftext.class_texts('interlock')) so the JSON section is regenerable and tested against the corpus.
"""
import functools
import json
import os
import re
import sys

from .config import ROOT
from .pdftext import canonical, class_texts

DEFAULT = os.path.join(ROOT, "rulepack", "v1.json")
TOKEN = re.compile(r"\*|[a-z]{1,4}-\d{2,6}[a-z]?|[a-z0-9]+")
TAG = re.compile(r"\b[A-Z]{2,4}-\d{4,5}[A-Z]?\b")
ORDER = ("readiness", "trip", "job", "reading")
# PS-04: words that quote or negate the defeat phrase two tokens ahead of it; PS-04: permit-only phrases that
# report a missing permit rather than request one; PS-01/PS-02: how far after a defeat phrase its object may sit.
NEGATORS = {"never", "not", "don", "dont", "says", "say", "said", "mean", "means", "meaning", "meant"}
PERMIT_ONLY = {"without * permit", "without permit", "no permit"}
OBJECT_WINDOW = 4
# PS-V2: a defeat word can label a record instead of requesting an act. Two frames are reports, not requests, and both
# are what the pack's own defeat refusal invites the user to ask for ("an entry in the bypass register", "time-boxed"):
# the word immediately labels a record ("bypass register entry", "override log"), or it sits in a passive question about
# what was recorded ("which trips were overridden last turnaround, and is it recorded?"). Targeting is unaffected, so a
# request that names its protective object still refuses.
RECORD_NOUNS = {"register", "registers", "entry", "entries", "record", "records", "recorded", "log", "logs",
                "logbook", "history"}
PASSIVE = {"was", "were", "been"}

# --- C&E sheet parser (raw pdftotext lines, canonicalised per line) ---
HDR = re.compile(r"DOC NO: (TJC-LLD-IL-\S+) .*?LOGIC No: (.+?) DESCRIPTION: (.+?) SIL: (SIL \d|N/A) TAG: (\S+) FLOC: (\S+)")
ROW = re.compile(r"^([TCAR]\d) (.+?) ([A-Z]{2,4}-\d{4,5}) (.+?) (1oo1|1oo2|2oo3|control|alarm|mech)((?: X)+)$")
EFF = re.compile(r"^(EFF-\d) (.+)$")
PERM = re.compile(r"^(\d) (.+?) (DCS reset|LG gearbox|FSL upstream|lockout|DVC6200|[A-Z]{2,4}-\d{4,5})$")
NOTE = re.compile(r"1\. (Trip set points are [^.]*\.).*?3\. (A trip is latched[^.]*\.)")


def parse_interlocks(texts=None):
    """{SEQ id or tag: protective function} for the eight sheets; every string is verbatim from the sheet."""
    texts = texts if texts is not None else class_texts("interlock", canon=False)
    out = {}
    for tag in sorted(texts):
        raw = texts[tag]
        h = HDR.search(canonical(raw))
        n = NOTE.search(canonical(raw))
        lines = [canonical(l) for l in raw.splitlines()]
        seq = h.group(2) if h.group(2).startswith("SEQ-") else None
        rows = [m for m in (ROW.match(l) for l in lines) if m]
        fn = {
            "doc": h.group(1), "tag": h.group(5), "floc": h.group(6), "seq": seq, "description": h.group(3),
            "sil": int(h.group(4)[-1]) if seq else None, "kind": "interlock" if seq else "control_loop_only",
            "effects": [{"id": m.group(1), "action": m.group(2)} for m in (EFF.match(l) for l in lines) if m],
            "permissives": [{"n": int(m.group(1)), "condition": m.group(2), "signal": m.group(3)}
                            for m in (PERM.match(l) for l in lines) if m],
            "setpoint_note": n.group(1), "reset_note": n.group(2),
        }
        fn["initiators" if seq else "layers"] = [
            {"id": m.group(1), "cause": m.group(2), "tag": m.group(3), "setpoint_text": m.group(4), "vote": m.group(5),
             "x_marks": m.group(6).count("X")} for m in rows]  # ponytail: X-to-effect column mapping needs the rendered sheet
        out[seq or tag] = fn
    return out


# --- matcher ---
def tokens(text):
    return TOKEN.findall((text or "").lower())


def _alts(toks):
    """Per token, the set of forms a lexicon phrase may match: the token itself, plus the alphabetic prefix of a tag token.

    Without this, every generic-noun phrase in the pack is dead against a real tag: "gag * psv" and "block in * psv" were
    shipped to catch relief-device defeat and matched only the bare word "psv", never "gag PSV-8901" (PS-03), because the
    tokeniser keeps "psv-8901" whole.
    """
    return [{t, t.split("-")[0]} if "-" in t else {t} for t in toks]


def _match_end(p, toks, i, gap, alts):
    """End index (exclusive) of the first match of phrase tokens `p` starting at `i`, or None."""
    if not p:
        return i
    if p[0] == "*":
        for k in range(gap + 1):
            if i + k <= len(toks):
                e = _match_end(p[1:], toks, i + k, gap, alts)
                if e is not None:
                    return e
        return None
    if i < len(toks) and p[0] in alts[i]:
        return _match_end(p[1:], toks, i + 1, gap, alts)
    return None


def _hits(phrases, toks, gap, alts=None):
    """[(start, end, phrase, key)] for every occurrence of every (phrase, tokens, key), sorted."""
    alts = alts if alts is not None else _alts(toks)
    out = []
    for ph, pt, key in phrases:
        for i in range(len(toks)):
            e = _match_end(pt, toks, i, gap, alts)
            if e is not None:
                out.append((i, e, ph, key))
    return sorted(out)


def _phrases(strings, key=None):
    return [(s, tokens(s), key) for s in strings]


def _function_terms(fn):
    terms = {fn["tag"]} | ({fn["seq"]} if fn["seq"] else set()) | {r["tag"] for r in fn.get("initiators", fn.get("layers"))}
    terms |= set(TAG.findall(fn["description"]))
    terms |= {t for e in fn["effects"] for t in TAG.findall(e["action"])}
    terms |= {t for p in fn["permissives"] for t in TAG.findall(p["condition"] + " " + p["signal"])}
    return sorted(terms)


@functools.lru_cache(maxsize=None)
def load(path=DEFAULT):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    ic, pv = raw["intent_classes"], raw["protective_vocabulary"]
    prot = _phrases(pv["generic_en"] + pv["generic_id"])
    for key, fn in sorted(raw["protective_functions"].items()):
        prot += _phrases(_function_terms(fn), key)
    return {
        "raw": raw, "gap": raw["gap_tokens"], "window": raw["window_tokens"], "protective": prot,
        "permanent_change": _phrases(ic["permanent_change"]["lexicon_en"] + ic["permanent_change"]["lexicon_id"]),
        "defeat": _phrases(ic["defeat"]["lexicon_en"] + ic["defeat"]["lexicon_id"]),
        "entities": _phrases(ic["documented_bypass"]["entities"]),
        "procedure": _phrases(ic["documented_bypass"]["lexicon_en"] + ic["documented_bypass"]["lexicon_id"]),
        "moments": {m: _phrases(ph) for m, ph in raw["moments"].items()},
    }


def classify(text, pack=None):
    """{intent: defeat|documented_bypass|permanent_change|None, matched: [...], protective_function: key or None}.

    Ordering (rulepack matching_rules): permanent_change, then a TARGETED defeat phrase (one whose object is a protective
    token), then documented_bypass, then an untargeted defeat phrase. Targeting is what makes the hard gate unconditional:
    naming a documented-bypass entity anywhere in the text used to downgrade any defeat request to documented_bypass, so
    "we are doing a proof test tonight, so how do I bypass the SEQ-3401 trip?" was answered with the bypass lesson (PS-01).
    Four suppressions keep the gate off legitimate questions: a defeat word that is part of a named documented
    artefact ("manual bypass", "inhibit permit"), one negated or quoted by the two tokens before it ("never defeat",
    "the lesson says do not defeat") (PS-04), one that labels a record rather than an act ("the bypass register entry"),
    and one in a passive question about what was recorded ("which trips were overridden ... and is it recorded?")
    (PS-V2). "Without a permit" on its own is a report, not a request.
    """
    pk = pack or load()
    toks = tokens(text)
    alts = _alts(toks)
    prot = _hits(pk["protective"], toks, pk["gap"], alts)
    fn = next((h[3] for h in prot if h[3]), None)

    def near(hits):
        return [h for h in hits if any(abs(h[0] - p[0]) <= pk["window"] for p in prot)]

    entity = _hits(pk["entities"], toks, pk["gap"], alts)

    reports = bool(RECORD_NOUNS & set(toks))

    def live(h):
        s, e = h[0], h[1]
        if any(es < e and s < ee for es, ee, _, _ in entity):
            return False
        if set(toks[e:e + 2]) & RECORD_NOUNS:            # "the bypass register entry", "the override log"
            return False
        if reports and set(toks[max(0, s - 2):s]) & PASSIVE:   # "were overridden ... and is it recorded?"
            return False
        return not set(toks[max(0, s - 2):s]) & NEGATORS

    defeat = [h for h in near(_hits(pk["defeat"], toks, pk["gap"], alts)) if live(h)]
    if all(h[2] in PERMIT_ONLY for h in defeat):
        defeat = []
    targeted = [h for h in defeat if any(h[0] <= p[0] < h[1] + OBJECT_WINDOW for p in prot)]
    found = {"protective": prot, "permanent_change": near(_hits(pk["permanent_change"], toks, pk["gap"], alts)),
             "defeat": defeat, "entity": entity, "procedure": _hits(pk["procedure"], toks, pk["gap"], alts)}
    if found["permanent_change"]:
        intent = "permanent_change"
    elif targeted or (defeat and not (entity and found["procedure"])):
        intent = "defeat"
    elif entity and found["procedure"]:
        intent = "documented_bypass"
    else:
        intent = None
    matched = sorted({f"{kind}:{h[2]}" for kind, hits in found.items() for h in hits})
    return {"intent": intent, "matched": matched, "protective_function": fn}


def outbound_screen(text, approved, pack=None):
    """Outbound rule (pack note 4): a verbatim span of an approved lesson is whitelisted BEFORE the pack runs.

    `approved` is an iterable of approved lesson texts (harness.pdftext.opl_texts().values()). Returns
    {whitelisted, would_refuse}: `would_refuse` is what the pack alone would have done, and is True for 1 of the 56
    lessons -- OPL-LV-6701-05, which instructs on a bypass in its own steps (`fixtures.outbound` in the pack) -- and the
    whitelist is what makes that lesson renderable under FR-205.
    """
    t = canonical(text)
    return {"whitelisted": any(t in canonical(a) for a in approved),
            "would_refuse": classify(text, pack)["intent"] in ("defeat", "permanent_change")}


def moment(text, pack=None):
    """Addendum A5 template inference: most distinct keyword phrases wins; ties fall to the A5 order."""
    pk = pack or load()
    toks = tokens(text)
    best, best_n = None, 0
    for m in ORDER:
        n = len({h[2] for h in _hits(pk["moments"][m], toks, pk["gap"])})
        if n > best_n:
            best, best_n = m, n
    return best


def routing(intent, seq, pack=None):
    """Filled routing text for an intent and a protective-function key (SEQ id, or the tag for EA-5601)."""
    pk = pack or load()
    tpl = pk["raw"]["routing_text"].get(intent)
    if tpl is None:
        return None
    fn = pk["raw"]["protective_functions"].get(seq)
    if fn is None:
        return tpl.format(seq="a protective function", sil="SIL not identified: name the SEQ or the instrument tag",
                          permissives="not identified; name the SEQ or the instrument tag")
    perms = "; ".join(f"{p['n']} {p['condition']} [{p['signal']}]" for p in fn["permissives"])
    return tpl.format(seq=seq, sil=f"SIL {fn['sil']}" if fn["sil"] else "SIL N/A, control loop only",
                      permissives=f"{perms}. {fn['reset_note']} ({fn['doc']} note 3)")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    r = classify(q)
    print(json.dumps({"classify": r, "moment": moment(q), "routing": routing(r["intent"], r["protective_function"])},
                     sort_keys=True, indent=1, ensure_ascii=False))
