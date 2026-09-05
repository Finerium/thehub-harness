"""The package bundle writer of blueprint 9.1 (T1).

    uv run python -m harness.bundle --out bundle        (CASE1_CORPUS names the corpus)

Writes every file of the 9.1 tree except chunks.jsonl and pages/ (harness.chunks and harness.pages write them; they are
hashed into the manifest here when present), seeded/* (recorded from the answer engine, required from bundle 1.1.0) and
the optional simulated/. Every number is read from packages/fixtures.json, the one fixture, which is refused when its
corpus digest is not the digest of the corpus at hand; every text comes through harness.pdftext; every adopted artefact
comes from packages/. JSON is written with sorted keys, one-space indent, UTF-8 and a trailing newline; manifest.json is
written last with the sha256 and byte size of every other file of the tree. Two runs on the same corpus at the same
commit are byte-identical: created_at is SOURCE_DATE_EPOCH when set, else the committer date of HEAD.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess

from . import documents as D
from . import entities as E
from . import master as M
from . import opl as O
from . import pdftext as P
from . import workbook as W
from .config import PACKAGES, ROOT

BUNDLE_VERSION = "1.0.0"
CLASSES = ("datasheet", "ga_drawing", "interlock", "plot_plan")
SPOT_CLASSES = ("datasheet", "ga_drawing", "plot_plan", "interlock", "pid")
# (bundle path, repository path): byte copies
COPIES = (
    ("fixtures.json", "packages/fixtures.json"),
    ("rulepack/v1.json", "rulepack/v1.json"),
    ("golden/cases.yaml", "golden/cases.yaml"),
    ("contracts/edms.schema.json", "contracts/connectors/edms.schema.json"),
    ("contracts/aims.schema.json", "contracts/connectors/aims.schema.json"),
    ("contracts/historian.schema.json", "contracts/connectors/historian.schema.json"),
)
# corpus text and imagery: listed in the manifest, excluded from the release and every public tree (D-17)
SEED_TIME = ("chunks.jsonl", "opls.json", "pages/", "text/")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, sort_keys=True, indent=1, ensure_ascii=False)
        f.write("\n")


def sha256_file(path):
    return P.file_sha256(path)


def git(*args):
    cp = subprocess.run(
        ["git", "-C", ROOT, *args], capture_output=True, text=True, check=False
    )
    return cp.stdout.strip() if cp.returncode == 0 else ""


def harness_commit():
    sha = git("rev-parse", "HEAD") or "unknown"
    return sha + ("-dirty" if git("status", "--porcelain") else "")


def created_at():
    """ISO 8601 UTC: SOURCE_DATE_EPOCH, else the committer date of HEAD, else now (only then non-reproducible)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        dt = datetime.datetime.fromtimestamp(int(epoch), datetime.UTC)
    else:
        iso = git("log", "-1", "--format=%cI")
        dt = (
            datetime.datetime.fromisoformat(iso).astimezone(datetime.UTC)
            if iso
            else datetime.datetime.now(datetime.UTC)
        )
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def manifest_files(out):
    """[{path, sha256, bytes}] of every file under the bundle directory except manifest.json, sorted by path."""
    rows = []
    for d, _, fs in os.walk(out):
        for name in fs:
            p = os.path.join(d, name)
            rel = os.path.relpath(p, out).replace(os.sep, "/")
            if rel == "manifest.json":
                continue
            rows.append(
                {"path": rel, "sha256": sha256_file(p), "bytes": os.path.getsize(p)}
            )
    return sorted(rows, key=lambda r: r["path"])


def sidecar_packages():
    """{set number: (packages/pid_sidecars/set_0n.json, its transcript)}."""
    out = {}
    for path in sorted(
        glob.glob(os.path.join(PACKAGES, "pid_sidecars", "set_??.json"))
    ):
        n = int(re.search(r"set_(\d\d)\.json$", path).group(1))
        transcript = path.replace(".json", ".transcript.json")
        out[n] = (
            read_json(path),
            read_json(transcript) if os.path.exists(transcript) else {},
        )
    return out


def build(out):
    """Write the bundle into `out`; returns the summary printed by main()."""
    fx = read_json(os.path.join(PACKAGES, "fixtures.json"))
    files = P.corpus_files()
    digest = P.corpus_sha256(files)
    if digest != fx["inventory"]["corpus_sha256"]:
        raise SystemExit(
            f"packages/fixtures.json was built over corpus {fx['inventory']['corpus_sha256'][:12]}, "
            f"this corpus is {digest[:12]}: run `make fixtures` first"
        )
    rows = W.load()
    row_of = {
        w["WO_Number"]: n for n, w in enumerate(rows, start=2)
    }  # the Excel row is the workbook's page
    texts = {c: P.class_texts(c) for c in CLASSES}
    raw_ga = P.class_texts("ga_drawing", canon=False)
    opl_c, opl_r = P.opl_texts(), P.opl_texts(canon=False)
    parsed = O.parse_all(opl_c)
    hand = M.hand_effects()
    datasheets = {t: M.parse_datasheet(x) for t, x in texts["datasheet"].items()}
    interlocks = {
        t: M.parse_interlock(t, x, hand) for t, x in texts["interlock"].items()
    }
    drawings = {t: M.parse_drawing(x) for t, x in texts["ga_drawing"].items()}
    plots = {t: M.parse_drawing(x) for t, x in texts["plot_plan"].items()}
    packs = sidecar_packages()

    # 9.2 documents, revisions, spans, claims, edges
    docs, facts = D.register(
        files,
        drawings,
        plots,
        datasheets,
        interlocks,
        {n: p[0] for n, p in packs.items()},
    )
    revs = D.revisions(
        docs,
        facts,
        parsed,
        drawings,
        plots,
        datasheets,
        interlocks,
        {n: D.pid_revision(p[1]) for n, p in packs.items()},
    )
    cur = D.current_rev(revs)
    page_texts = {
        did: D.pdf_page_texts(f["path"])
        for did, f in facts.items()
        if f["path"].lower().endswith(".pdf")
    }
    row_texts = D.workbook_row_texts()
    spans, claims = D.Spans(), D.Claims()
    resolver = D.Resolver(docs, facts, parsed, interlocks)
    edges, unresolved = D.edges(
        docs, facts, revs, page_texts, parsed, texts, spans, claims, resolver
    )

    def doc(tag, cls):
        return resolver.of(tag, cls)

    def pages(tag, cls):
        return page_texts[doc(tag, cls)]

    # 9.3 asset and safety graph
    ds_params = []
    for tag in sorted(datasheets):
        ds_params += E.datasheet_params(
            tag,
            texts["datasheet"][tag],
            cur[doc(tag, "datasheet")],
            pages(tag, "datasheet")[0],
            spans,
            claims,
        )
    il_rows, il_perms, il_sheets = [], [], []
    for tag in sorted(interlocks):
        sheet, r, p = E.interlock_entities(
            tag,
            interlocks[tag],
            texts["interlock"][tag],
            cur[doc(tag, "interlock")],
            spans,
            claims,
        )
        il_sheets.append(sheet)
        il_rows += r
        il_perms += p
    equipment = E.equipment_rows(
        fx["equipment_master"], datasheets, drawings, plots, interlocks, resolver
    )
    eq_tags = {e["tag"] for e in equipment}
    typed = E.typed_tags(eq_tags, interlocks, texts["datasheet"])
    known = E.binding_targets(typed, interlocks, ds_params)
    sidecars, nulled = [], 0
    for n in sorted(packs):
        sc, k = E.sidecar(packs[n][0], resolver.pid_by_set[n], known)
        sidecars.append(sc)
        nulled += k
    instruments = E.instrument_tags(typed, texts, opl_c, sidecars, resolver)
    areas = E.area_rows(rows, read_json(os.path.join(PACKAGES, "area_aliases.json")))

    # 9.4 operations and failure
    bom = []
    for tag in sorted(drawings):
        bom += E.bom_items(
            tag,
            raw_ga[tag],
            drawings[tag]["dwg_no"],
            cur[doc(tag, "ga_drawing")],
            pages(tag, "ga_drawing")[0],
            spans,
            claims,
        )
    matches = E.bom_matches(rows, bom)
    wos = E.work_orders(rows)
    events = E.failure_events(rows)
    tests = E.proof_tests(fx["proof_tests"], rows)
    families = fx["families"]["list"]
    chains = E.causal_links(
        fx["chains"]["link_list"],
        row_of,
        row_texts,
        cur[resolver.workbook],
        spans,
        claims,
    )

    # 9.5 lessons, coverage, debt
    by_tag = {}
    for w in rows:
        by_tag.setdefault(w["Equipment_Tag"], []).append(w)
    vocab = E.acceptance_vocabulary(opl_r)
    lessons, steps, trows, skipped = [], [], [], 0
    for oid in sorted(parsed):
        did = resolver.by_opl[oid]
        lesson, s, t, k = E.opl_entities(
            oid,
            parsed[oid],
            opl_r[oid],
            page_texts[did],
            cur[did],
            vocab,
            by_tag[parsed[oid]["tag"]],
            spans,
            claims,
        )
        lessons.append(lesson)
        steps += s
        trows += t
        skipped += k
    labels_path = next(
        p
        for p in (
            os.path.join(PACKAGES, "coverage_labels.json"),
            os.path.join(PACKAGES, "coverage_labels.draft.json"),
        )
        if os.path.exists(p)
    )
    log_path = next(
        p
        for p in (
            os.path.join(PACKAGES, "adjudication_log.md"),
            os.path.join(PACKAGES, "adjudication_log.draft.md"),
        )
        if os.path.exists(p)
    )

    # pinned spot values, verified against the text through their spans
    spot = []
    for e in sorted(
        read_json(os.path.join(PACKAGES, "datasheet_spot.json")),
        key=lambda e: (e["tag"], e["field"]),
    ):
        sid = spans.locate(
            cur[doc(e["tag"], "datasheet")], pages(e["tag"], "datasheet"), e["quote"]
        )
        claims.add(sid, e["tag"], "parameter", e["value_text"])
        spot.append(
            {
                "id": f"DSS-{e['tag']}-{e['field']}",
                "equipment_tag": e["tag"],
                "group": "datasheet_spot",
                "field": e["field"],
                "unit": e["unit"],
                "value_text": e["value_text"],
                "value_num": e["value_num"],
                "span_id": sid,
            }
        )
    pins = read_json(os.path.join(PACKAGES, "revision_spot.json"))
    by_rev = {r["id"]: r for r in revs}
    rev_spot = []
    for tag in sorted(pins):
        for cls in SPOT_CLASSES:
            r = by_rev[cur[doc(tag, cls)]]
            pin = pins[tag].get(cls)
            if pin and (
                str(pin["rev"]) != r["revision"]
                or ("status" in pin and pin["status"] != r["approval_status_text"])
            ):
                raise SystemExit(
                    f"packages/revision_spot.json disagrees with the {cls} title block of {tag}: {pin}"
                )
            rev_spot.append(r)
    hv = read_json(os.path.join(PACKAGES, "hand_verified.json"))
    by_name = {os.path.basename(f["path"]): did for did, f in facts.items()}
    for s in hv["sets"]:
        s["document_id"] = by_name[s["file"]]

    inventory = dict(fx["inventory"])
    inventory["files"] = [
        {
            "document_id": d["id"],
            "source_path": d["source_path"],
            "class": d["class"],
            "sha256": d["sha256"],
            "bytes": os.path.getsize(facts[d["id"]]["path"]),
            "page_count": d["page_count"],
            "sidecar_path": f"pid_sidecars/set_{facts[d['id']]['set']:02d}.json"
            if d["class"] == "pid"
            else None,
            "text_extracted": d["class"] not in ("pid", "organiser_note"),
        }
        for d in docs
    ]

    # ---------------------------------------------------------------- write
    os.makedirs(out, exist_ok=True)
    tree = {
        "inventory.json": inventory,
        "documents.json": docs,
        "revisions.json": revs,
        "claims.json": {
            "spans": spans.rows(),
            "claims": claims.rows(),
            "edges": edges,
            "unresolved_references": unresolved,
        },
        "interlocks.json": {
            "equipment": equipment,
            "interlocks": il_sheets,
            "rows": il_rows,
            "permissives": il_perms,
            "instrument_tags": instruments,
        },
        "datasheet_params.json": ds_params,
        "datasheet_spot.json": spot,
        "revision_spot.json": rev_spot,
        "hand_verified.json": hv,
        "work_orders.json": wos,
        "failure_events.json": events,
        "families.json": families,
        "chains.json": chains,
        "coverage_scores.json": {
            "method": E.coverage_method(fx),
            "assessments": E.coverage_assessments(fx),
            "summaries": E.coverage_summaries(fx),
        },
        "coverage_labels.json": dict(
            fx["coverage_labels"], records=read_json(labels_path)
        ),
        "debt.json": E.debt_clusters(fx),
        "proof_tests.json": tests,
        "integrity_findings.json": {
            **{k: fx["integrity"][k] for k in ("total", "rules", "observations")},
            "findings": E.integrity_findings(fx, rows, parsed, interlocks, resolver),
        },
        "area_aliases.json": areas,
        "bom.json": {"items": bom, "matches": matches},
        "opls.json": {
            "lessons": lessons,
            "steps": steps,
            "troubleshooting_rows": trows,
        },
    }
    for sc in sidecars:
        tree[f"pid_sidecars/set_{sc['set']:02d}.json"] = sc
    for rel, obj in tree.items():
        write_json(os.path.join(out, rel), obj)
    shutil.copyfile(log_path, os.path.join(out, "adjudication_log.md"))
    for rel, src in COPIES:
        os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, src), os.path.join(out, rel))

    pin_path = os.path.join(PACKAGES, "embedding_pin.json")
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "harness_commit": harness_commit(),
        "corpus_sha256": digest,
        "extractor": fx["inventory"]["extractor"],
        "canonical_form_version": fx["inventory"]["canonical_form_version"],
        "recipe_sha256": fx["method"]["recipe_sha256"],
        "stop_list_sha256": fx["method"]["stop_list_sha256"],
        "rulepack_version": str(
            read_json(os.path.join(ROOT, "rulepack", "v1.json"))["version"]
        ),
        "embedding_model": read_json(pin_path)["model"]
        if os.path.exists(pin_path)
        else None,
        "files": manifest_files(out),
        "created_at": created_at(),
    }
    write_json(os.path.join(out, "manifest.json"), manifest)
    return {
        "out": out,
        "bundle_version": BUNDLE_VERSION,
        "files": len(manifest["files"]),
        "documents": len(docs),
        "revisions": len(revs),
        "spans": len(spans.by_id),
        "claims": len(claims.items),
        "edges": len(edges),
        "unresolved_references": len(unresolved),
        "datasheet_params": len(ds_params),
        "interlock_rows": len(il_rows),
        "permissives": len(il_perms),
        "instrument_tags": len(instruments),
        "hotspot_bindings_nulled": nulled,
        "bom_items": len(bom),
        "bom_matches": len(matches),
        "work_orders": len(wos),
        "lessons": len(lessons),
        "steps": len(steps),
        "troubleshooting_rows": len(trows),
        "section5_words_unexplained": skipped,
        "seed_time_present": sorted(
            p for p in SEED_TIME if os.path.exists(os.path.join(out, p.rstrip("/")))
        ),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="write the package bundle of blueprint 9.1"
    )
    ap.add_argument("--out", default="bundle")
    a = ap.parse_args(argv)
    print(json.dumps(build(os.path.abspath(a.out))))


if __name__ == "__main__":
    main()
