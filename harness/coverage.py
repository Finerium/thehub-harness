"""Frozen coverage method LD-07 (Revision Plan 5.7 items 1-5, 7; Addendum D1, D10, P5, P6; closes HN-04, HN-06, HN-07, HN-V-01).

Recipe: a work-order narrative field is reduced to content tokens (`tokens`, `STOP` ported verbatim from the audit's
analyze_corpus.py); each same-asset lesson document is scanned separately with a window of twice the field's token count
sliding one token at a time (`contain_doc`, ported verbatim from the audit's recipe_check.py); the field's score is the
largest share of its distinct content tokens found inside one window; the work order's score is the best over its three
fields and the asset's lessons; it is uncovered when score <= t (t = 0.62). Two layers: generous = full canonical lesson
text, strict = harness.opl.strict_text(parsed), the identity header plus sections 1, 2, 3, 4 and 6 composed from the parsed
lesson (seven rebuilt header fields, not the extracted header text) so that section 5, the page watermark and anything after
it, and anything after the "Prepared by" footer are excluded wherever the extractor places them.
Text comes only from harness.pdftext (D10). Every output is a
pure function of the corpus: sorted keys, sorted lists, lessons visited in sorted opl_id order.
"""
import difflib
import hashlib
import json
import os
import re
from collections import Counter
from typing import Any

from .config import PACKAGES
from .opl import STRICT_SECTIONS, strict_texts
from .pdftext import canonical, tag_of_opl
from .workbook import NARR

T = 0.62
THRESHOLDS = (0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75)
WINDOW_MULTIPLIER = 2
MIN_FIELD_TOKENS = 3
VERBATIM_MIN_CHARS = 20
LABELS_PATH = os.path.join(PACKAGES, "coverage_labels.json")
DRAFT_LABELS_PATH = os.path.join(PACKAGES, "coverage_labels.draft.json")   # WS1 Task 1.6: the machine-drafted set
DRAFT_STATUS = ("machine-drafted labels present (packages/coverage_labels.draft.json); human adjudication pending (OQ-6); "
                "deck numbers remain the proxy")
# --- verbatim port of legacy/audit_reference/analyze_corpus.py (STOP, tokens) ---
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "by", "from", "is", "are", "was",
    "were", "be", "been", "as", "that", "this", "it", "its", "into", "after", "before", "during", "not", "no", "per",
    "via", "than", "then", "which", "when", "while", "under", "over", "out", "up", "down", "off", "all", "any",
    "each", "both", "has", "have", "had", "do", "does", "did", "but", "if", "so", "such", "also", "may", "can",
    "will", "would", "should", "must",
}


def tokens(s):
    """Content tokens: lower-cased alphanumeric runs, tag-like tokens (VSHH-1201, 0.05mm/100mm) kept whole, STOP removed,
    single characters dropped. Verbatim from the audit's analyze_corpus.py (HN-07)."""
    return [t for t in re.findall(r'[a-z0-9]+(?:[-./][a-z0-9]+)*', s.lower()) if t not in STOP and len(t) > 1]


# --- verbatim port of legacy/audit_reference/recipe_check.py (contain_doc) ---
def contain_doc(ftoks, dtoks, mult=2):
    """Share of the field's distinct tokens found inside one window of len(ftoks)*mult document tokens, sliding by one
    token; a document no longer than the window is one window. Verbatim from the audit's recipe_check.py (HN-07, LD-07)."""
    F = set(ftoks)
    if not F: return 0.0
    n = len(ftoks) * mult
    if len(dtoks) <= n: return len(F & set(dtoks)) / len(F)
    best = 0; win = Counter(dtoks[:n]); best = sum(1 for t in F if t in win)
    for i in range(n, len(dtoks)):
        o, inn = dtoks[i - n], dtoks[i]
        win[o] -= 1
        if not win[o]: del win[o]
        win[inn] += 1
        c = sum(1 for t in F if t in win)
        best = max(best, c)
        if best == len(F): break
    return best / len(F)


def lessons_by_tag(texts):
    """{tag: [(opl_id, tokens)]} from {opl_id: text}, in sorted opl_id order (HN-04: no file-order dependence)."""
    out: dict[str, list[tuple[str, list[str]]]] = {}
    for oid in sorted(texts):
        out.setdefault(tag_of_opl(oid), []).append((oid, tokens(canonical(texts[oid]))))
    return out


def field_tokens(w):
    """{field: tokens} for the narrative fields with at least MIN_FIELD_TOKENS content tokens (the skip rule, LD-07 item 1)."""
    ft = {cf: tokens(canonical(str(w[cf] or ""))) for cf in NARR}
    return {cf: t for cf, t in ft.items() if len(t) >= MIN_FIELD_TOKENS}


def score(rows, lessons):
    """{wo: {score (4 dp), unit [field, opl_id] | None}}: best contain_doc over the scoreable narrative fields and the asset's
    lessons visited in sorted opl_id order, so the unit of a tie is order-independent. unit is None when nothing scored above
    0.0: no scoreable field (method.unscoreable_ids) or no token of any field inside any lesson (LD-07 item 1)."""
    out = {}
    for w in rows:
        best, unit = 0.0, None
        docs = sorted(lessons.get(w["Equipment_Tag"], []), key=lambda d: d[0])
        for cf, ft in field_tokens(w).items():
            for oid, dt in docs:
                c = contain_doc(ft, dt, WINDOW_MULTIPLIER)
                if c > best:
                    best, unit = c, [cf, oid]
        out[w["WO_Number"]] = {"score": round(best, 4), "unit": unit}
    return out


def table(pop, scores, thresholds=THRESHOLDS):
    """One row per threshold: uncovered = score <= t; unplanned_bd / downtime_h / cost_idr over the uncovered rows whose
    breakdown_kind is 'unplanned' (None counted as 0); ids and by_tag sorted (plan Task 1.2, LD-04)."""
    rows = []
    for t in thresholds:
        unc = [w for w in pop if scores[w["WO_Number"]]["score"] <= t]
        ub = [w for w in unc if w["breakdown_kind"] == "unplanned"]
        rows.append({
            "t": t, "n": len(pop), "uncovered": len(unc), "pct": round(100 * len(unc) / len(pop), 1) if pop else 0.0,
            "unplanned_bd": len(ub),
            "downtime_h": sum(w["Downtime_Hours"] or 0 for w in ub),
            "cost_idr": int(sum(w["Total_Cost_IDR"] or 0 for w in ub)),
            "uncovered_ids": sorted(w["WO_Number"] for w in unc),
            "by_tag": dict(sorted(Counter(w["Equipment_Tag"] for w in unc).items())),
        })
    return rows


def uncovered_ids(pop, scores, t=T):
    return sorted(w["WO_Number"] for w in pop if scores[w["WO_Number"]]["score"] <= t)


def verbatim(rows, texts):
    """Exact-substring reuse: a canonical narrative field of >= VERBATIM_MIN_CHARS characters found in the concatenated
    canonical text of the same asset's lessons (plan 5.7 item 7, CF-V-01, HN-06). Counts by field, work orders with any
    field, sorted ids."""
    by_tag: dict[str, str] = {}
    for oid in sorted(texts):
        by_tag[tag_of_opl(oid)] = by_tag.get(tag_of_opl(oid), "") + " " + canonical(texts[oid])
    by_field, any_ids = Counter(dict.fromkeys(NARR, 0)), []
    for w in rows:
        hit = False
        for cf in NARR:
            v = canonical(str(w[cf] or ""))
            if len(v) >= VERBATIM_MIN_CHARS and v in by_tag.get(w["Equipment_Tag"], ""):
                by_field[cf] += 1; hit = True
        if hit:
            any_ids.append(w["WO_Number"])
    return {"by_field": dict(sorted(by_field.items())), "any": len(any_ids), "any_ids": sorted(any_ids)}


def load_labels(path=LABELS_PATH):
    """{wo: covered_by} from packages/coverage_labels.json, or from the machine-drafted coverage_labels.draft.json when
    called with DRAFT_LABELS_PATH (plan Task 1.3/1.6); {} when the file does not exist."""
    try:
        with open(path, encoding="utf-8") as f:
            return {x["wo_number"]: x["covered_by"] for x in json.load(f)}
    except FileNotFoundError:
        return {}


def load_label_records(path=LABELS_PATH):
    """The label file as written, both labeller verdicts per record intact; [] when the file does not exist."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _kappa(pairs):
    """Cohen's kappa over (labeller A, labeller B) boolean verdicts, 4 dp; 1.0/0.0 when chance agreement is total."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else (1.0 if po == 1 else 0.0)


def kappa(records):
    """Cohen's kappa between the two labellers on the covered and the taught decision (D6, Task 1.6).

    Recomputed from the per-labeller verdicts that every record of coverage_labels[.draft].json preserves, so the
    published figure is a function of the shipped file and never a number copied out of the adjudication log.
    """
    rs = [r for r in records if len(r.get("labellers") or []) == 2]
    if not rs:
        return None
    cov = [tuple(bool(x["covered_by"]) for x in r["labellers"]) for r in rs]
    taught = [tuple(bool(x["covered_by"]) and not x["table_only"] for x in r["labellers"]) for r in rs]
    return {"n": len(rs), "labellers": [x["labeller"] for x in rs[0]["labellers"]],
            "covered": _kappa(cov), "taught": _kappa(taught),
            "basis": "Cohen's kappa over the two per-labeller verdicts in the label file; covered = covered_by non-empty, "
                     "taught = covered and not table_only"}


def agreement(scores, labels, t=T):
    """Precision / recall (4 dp, like every other published numeric) of the proxy (score > t = covered) against the analyst labels (covered_by non-empty = covered);
    exactly plan Task 1.3 (LD-05, P5)."""
    tp = fp = fn = tn = 0
    for wo, cov in labels.items():
        pred, truth = scores[wo]["score"] > t, bool(cov)
        tp += pred and truth; fp += pred and not truth; fn += (not pred) and truth; tn += (not pred) and (not truth)
    return {"n": len(labels), "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def labelled_table(rows, labels, t=T):
    """The labelled figure as one coverage row: a labelled work order is covered iff covered_by is non-empty (D6, P5)."""
    pop = [w for w in rows if w["WO_Number"] in labels]
    pseudo = {w["WO_Number"]: {"score": 1.0 if labels[w["WO_Number"]] else 0.0} for w in pop}
    return table(pop, pseudo, (t,))[0]


# --- legacy/validate_fix.py::best_ratio, verbatim (evidence only: window L+step, order-dependent, HN-02/HN-04, P6) ---
def best_ratio(f, corpus):
    fl=re.sub(r'\s+',' ',f.lower()).strip(); L=len(fl)
    if L<20: return 0.0
    if fl in corpus: return 1.0
    step=max(20,L//2); best=0.0
    for s in range(0,max(1,len(corpus)-L+1),step):
        w=corpus[s:s+L+step]
        sm=difflib.SequenceMatcher(None,fl,w)
        if sm.real_quick_ratio()<best: continue
        if sm.quick_ratio()<best: continue
        r=sm.ratio()
        best = max(best, r)
        if best>0.95: break
    return best


def legacy_corpus(texts):
    """validate_fix.py's per-tag concatenation (leading space per lesson, lower-cased, whitespace collapsed) built in sorted
    opl_id order instead of os.walk order (HN-04)."""
    out: dict[str, str] = {}
    for oid in sorted(texts):
        out[tag_of_opl(oid)] = out.get(tag_of_opl(oid), "") + " " + re.sub(r"\s+", " ", canonical(texts[oid]).lower())
    return out


def legacy_score(rows, corpus_by_tag):
    """The v1.0 scorer (validate_fix.py work-order loop, verbatim) over `legacy_corpus`: {wo: {score}} (LD-01, P6)."""
    out = {}
    for w in rows:
        corpus = corpus_by_tag.get(w["Equipment_Tag"], ""); b = 0.0
        for cf in NARR:
            v = str(w[cf] or "")
            if len(v) >= 20:
                b = max(b, best_ratio(v, corpus))
                if b > 0.95: break
        out[w["WO_Number"]] = {"score": b}
    return out


def compute(ctx):
    """Fixture keys method, coverage, coverage_scores, coverage_bands, coverage_by_work_type, coverage_by_tag, verbatim,
    labels_agreement, labelled, legacy from ctx {rows, pops, opl, parsed, files} (WS1 Task 1.2/1.3; D1, D10, P5, P6).
    Optional ctx keys set by the CLI: t (threshold for the derived tables, default T) and legacy_window (False skips the
    v1.0 scorer and sets legacy to null)."""
    rows, pops, texts = ctx["rows"], ctx["pops"], ctx["opl"]
    t = ctx.get("t", T)  # the CLI's --t (analyze_corpus); the threshold rows always include it
    thresholds = tuple(sorted(set(THRESHOLDS) | {t}))
    layers = {"generous": texts, "strict": strict_texts(ctx["parsed"])}
    scores = {name: score(rows, lessons_by_tag(x)) for name, x in layers.items()}
    coverage = {name: {p: table(pops[p], sc, thresholds) for p in sorted(pops)} for name, sc in scores.items()}
    g_unc = uncovered_ids(pops["unplanned_failure"], scores["generous"], t)
    s_unc = uncovered_ids(pops["unplanned_failure"], scores["strict"], t)
    none, table_only = g_unc, sorted(set(s_unc) - set(g_unc))
    taught = sorted(w["WO_Number"] for w in pops["unplanned_failure"] if w["WO_Number"] not in set(g_unc) | set(s_unc))
    bands = {"t": t, "n": len(pops["unplanned_failure"]), "none": len(none), "table_only": len(table_only), "taught": len(taught),
             "none_ids": none, "table_only_ids": table_only, "taught_ids": taught}
    g = scores["generous"]
    by_type = {wt: {"n": 0, "uncovered": 0} for wt in sorted({w["Work_Type"] for w in rows})}
    bd = {"n": 0, "uncovered": 0, "planned_flagged_uncovered": 0, "unplanned_uncovered": 0}
    for w in rows:
        unc = g[w["WO_Number"]]["score"] <= t
        by_type[w["Work_Type"]]["n"] += 1; by_type[w["Work_Type"]]["uncovered"] += unc
        if w["breakdown_kind"]:
            bd["n"] += 1; bd["uncovered"] += unc; bd[w["breakdown_kind"] + "_uncovered"] += unc
    by_tag: dict[str, dict[str, Any]] = {}
    for w in pops["unplanned_failure"]:
        d = by_tag.setdefault(w["Equipment_Tag"], {"n_unplanned_failure": 0, "uncovered_generous": 0, "uncovered_strict": 0})
        d["n_unplanned_failure"] += 1
        d["uncovered_generous"] += scores["generous"][w["WO_Number"]]["score"] <= t
        d["uncovered_strict"] += scores["strict"][w["WO_Number"]]["score"] <= t
    # the v1.0 scorer (about 13 s) runs unless the CLI's --no-legacy-window asked to skip it (fixture legacy = null)
    legacy_rows = table(pops["all"], legacy_score(rows, legacy_corpus(texts)), thresholds) if ctx.get("legacy_window", True) else []
    for r in legacy_rows:  # v1.0 counted every Breakdown = Yes row, planned ones included (LD-04); kept for the P6 comparison
        ub = [w for w in rows if w["breakdown_kind"] and w["WO_Number"] in set(r["uncovered_ids"])]
        r.update(breakdowns_all=len(ub), downtime_h_all=sum(w["Downtime_Hours"] or 0 for w in ub),
                 cost_idr_all=int(sum(w["Total_Cost_IDR"] or 0 for w in ub)))
    labels = load_labels()
    # the machine-drafted adjudication is reported separately and only while the human file is absent (D6, OQ-6):
    # labelled / labels_agreement stay null so no deck number can be read off a draft label.
    draft = {} if labels else load_labels(DRAFT_LABELS_PATH)
    kap = kappa(load_label_records() if labels else load_label_records(DRAFT_LABELS_PATH))
    stop = sorted(STOP)
    method = {
        "recipe": "A work-order narrative field is reduced to content words (lower-cased alphanumeric tokens, tag-like tokens "
                  "such as VSHH-1201 kept whole, a fixed stop list removed, single-character tokens dropped, fields with fewer "
                  "than three content words skipped). The same tokeniser is applied to the lesson text. Each same-asset lesson "
                  "document is scanned separately with a window of twice the field's word count, one "
                  "word at a time; the field's score is the largest share of its distinct words found inside one window; the "
                  "work order's score is the best of its three fields; it is uncovered when that share does not exceed t = 0.62. "
                  "Generous layer: the full lesson text. Strict layer: seven header fields rebuilt from the parsed lesson "
                  "(lesson id, title, equipment name, area / unit, related interlock, P&ID reference, classification) plus "
                  "sections 1 PURPOSE, 2 SAFETY PRECAUTIONS, 3 TOOLS & MATERIALS, 4 DETAILED PROCEDURE and 6 KEY LEARNING "
                  "POINTS, composed from the parsed lesson, so that section 5 COMMON PROBLEMS & TROUBLESHOOTING, the page "
                  "watermark and anything after it, and anything after the 'Prepared by' footer are excluded wherever the "
                  "extractor places them.",
        "t": t, "thresholds": list(thresholds), "window_multiplier": WINDOW_MULTIPLIER,
        "extractor": "pdftotext -raw", "canonical": "NFKC, soft hyphens joined, whitespace collapsed",
        "strict_rule": "the strict layer is COMPOSED from the parsed lesson (harness.opl.strict_text): the seven header fields REBUILT from the parse (lesson id, title, equipment name, area / unit, related interlock, P&ID reference, classification) - not the header text as the extractor emits it - followed by sections 1, 2, 3, 4, 6, joined in that order. It is not stripped from the whole text, because stripping removes only what the extractor happens to place between the two section headings (P10). Each section body ends at the page watermark 'This is sample data provided for CALIBER purposes only', because the extractor emits out-of-flow table cells after it (P10b).",
        "strict_sections": list(STRICT_SECTIONS),
        "skip_rule": "fields with fewer than 3 content tokens skipped; work order with no scoreable field scores 0",
        "uncovered_rule": "score <= t",
        "stop_list": stop, "stop_list_size": len(stop),
        "stop_list_sha256": hashlib.sha256("\n".join(stop).encode("utf-8")).hexdigest(),
        "stop_list_sha256_of": "sorted stop words joined by newline, UTF-8",
        "unscoreable_ids": sorted(w["WO_Number"] for w in rows if not field_tokens(w)),
        "labels_status": f"labelled ({len(labels)} work orders)" if labels else DRAFT_STATUS if draft else "pending (proxy numbers in use)",
    }
    return {
        "method": method,
        "coverage": coverage,
        "coverage_scores": {wo: {name: scores[name][wo] for name in sorted(scores)} for wo in sorted(g)},
        "coverage_bands": {"unplanned_failure": bands},
        "coverage_by_work_type": {"t": t, "layer": "generous", "population": "all", "work_types": by_type, "breakdowns": bd},
        "coverage_by_tag": {"t": t, "population": "unplanned_failure", "tags": dict(sorted(by_tag.items()))},
        "verbatim": {"rule": f"canonical field of >= {VERBATIM_MIN_CHARS} chars is an exact substring of the same-asset lessons",
                     **{name: verbatim(rows, t) for name, t in layers.items()}},
        "labels_agreement": {"t": t, "kappa": kap, **{name: agreement(sc, labels, t) for name, sc in scores.items()}} if labels else None,
        "labelled": labelled_table(rows, labels, t) if labels else None,
        "labels_agreement_draft": {"t": t, "kappa": kap, **{name: agreement(sc, draft, t) for name, sc in scores.items()}} if draft else None,
        "labelled_draft": labelled_table(rows, draft, t) if draft else None,
        "legacy": {"order_dependent": True, "evidence_only": True,
                   "scorer": "legacy/validate_fix.py::best_ratio (window L+step, SequenceMatcher) on lessons concatenated in sorted opl_id order",
                   "all_breakdown_columns": "breakdowns_all / downtime_h_all / cost_idr_all count every Breakdown = Yes row as v1.0 did",
                   "all": legacy_rows} if legacy_rows else None,
    }
