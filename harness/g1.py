"""G1, the admission gate of the package bundle (blueprint 9.1, 11.2; the Python lane of the two-lane check).

    uv run python -m harness.g1 bundle        (CASE1_CORPUS names the corpus the bundle was built from)

Admits a bundle directory or names every violation, one line each, exit 1: every file the manifest lists exists with
the recorded sha256 and size and nothing unlisted sits in the tree; every file validates against its contract through
contracts/bundle_map.json; the fixture counts hold (98 files, 56 lessons, 211 work orders, register total 174);
every span_id, document_id, document_revision_id, wo_number, opl_id and bom_item_id resolves inside the bundle; every
enum and entity binding is a member of its closed set; every quoted span's hash recomputes from the extracted page
text of the corpus under the canonical form (and every chunk, step and section hash with it); seeded/* is required
only from bundle_version 1.1.0 (the sequencing decision of the run notes). A seed-time file the manifest lists but the
tree lacks (a released tarball, D-17) is reported, not refused; where the corpus is not at hand the span check is a
violation, never skipped.
"""

import json
import os
import re
import sys

from . import documents as D
from . import pdftext as P
from .canonical import quote_hash
from .config import CORPUS
from .entities import IDENTITY_FIELDS
from .validate import validate_bundle

# the frozen corpus counts G1 admits on (blueprint 9.1, contracts/fixtures.schema.json)
FILES_TOTAL, LESSONS, WORK_ORDERS, REGISTER_TOTAL = 98, 56, 211, 174
SEED_TIME = ("chunks.jsonl", "opls.json", "pages/", "text/")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
CLAIM_KINDS = (
    "parameter",
    "row",
    "note",
    "step",
    "footer",
    "title",
    "bom",
    "narrative",
)


def version_tuple(v):
    return tuple(int(x) for x in v.split("."))


class Gate:
    def __init__(self, bundle_dir, corpus=CORPUS):
        self.dir = bundle_dir
        self.corpus = corpus
        self.violations = []
        self.lines = []
        self.cache = {}

    # ------------------------------------------------------------ helpers
    def path(self, rel):
        return os.path.join(self.dir, rel)

    def load(self, rel, default=None):
        if rel in self.cache:
            return self.cache[rel]
        p = self.path(rel)
        if not os.path.exists(p):
            self.cache[rel] = default
            return default
        with open(p, encoding="utf-8") as f:
            self.cache[rel] = json.load(f)
        return self.cache[rel]

    def ok(self, check, detail):
        self.lines.append(f"ok    {check}: {detail}")

    def fail(self, check, detail):
        self.violations.append(f"{check}: {detail}")
        self.lines.append(f"FAIL  {check}: {detail}")

    def expect(self, check, condition, detail):
        (self.ok if condition else self.fail)(check, detail)

    def members(self, check, values, universe, what):
        missing = sorted({v for v in values if v not in universe})
        self.expect(
            check,
            not missing,
            f"{what}: {len(missing)} of {len(set(values))} unresolved"
            + (f" (first: {', '.join(missing[:3])})" if missing else ""),
        )

    # ------------------------------------------------------------ checks
    def check_manifest(self):
        m = self.load("manifest.json")
        if m is None:
            self.fail("manifest", "manifest.json missing")
            return None
        self.expect(
            "manifest.version",
            bool(SEMVER.match(m["bundle_version"])),
            f"bundle_version {m['bundle_version']}",
        )
        self.expect(
            "manifest.canonical_form",
            m["canonical_form_version"] == "1",
            "canonical_form_version 1",
        )
        listed, bad, absent = set(), [], []
        for f in m["files"]:
            listed.add(f["path"])
            p = self.path(f["path"])
            if not os.path.exists(p):
                (absent if f["path"].startswith(SEED_TIME) else bad).append(
                    f"{f['path']} missing"
                )
                continue
            if os.path.getsize(p) != f["bytes"] or P.file_sha256(p) != f["sha256"]:
                bad.append(f"{f['path']} sha256 or size differs")
        present = set()
        for d, _, fs in os.walk(self.dir):
            for name in fs:
                present.add(
                    os.path.relpath(os.path.join(d, name), self.dir).replace(
                        os.sep, "/"
                    )
                )
        unlisted = sorted(present - listed - {"manifest.json"})
        self.expect(
            "manifest.files",
            not bad and not unlisted,
            f"{len(m['files'])} listed, {len(bad)} mismatched, {len(unlisted)} unlisted"
            + (f" (first: {(bad + unlisted)[0]})" if bad or unlisted else ""),
        )
        if absent:
            self.ok(
                "manifest.seed_time",
                f"{len(absent)} seed-time files listed but not present (D-17)",
            )
        return m

    def check_schemas(self, version):
        results = validate_bundle(self.dir)
        bad = [r for r in results if r[1] in ("INVALID", "missing", "unmapped")]
        for rel, status, msg in bad:
            self.fail("schema", f"{rel} {status}: {msg}")
        seeded = [r for r in results if r[0].startswith("seeded/") and r[1] == "absent"]
        if seeded and version_tuple(version) >= (1, 1, 0):
            for rel, _, _ in seeded:
                self.fail("schema", f"{rel} required from bundle_version 1.1.0")
        valid = sum(1 for r in results if r[1] == "valid")
        self.ok(
            "schema",
            f"{valid} valid, {len(bad)} problems, {sum(1 for r in results if r[1] == 'absent')} absent",
        )

    def check_counts(self, fx):
        docs = self.load("documents.json") or []
        inv = self.load("inventory.json") or {}
        wos = self.load("work_orders.json") or []
        reg = self.load("integrity_findings.json") or {}
        opls = self.load("opls.json")
        by_class = {}
        for d in docs:
            by_class[d["class"]] = by_class.get(d["class"], 0) + 1
        self.expect(
            "counts.files",
            len(docs)
            == FILES_TOTAL
            == inv.get("files_total")
            == len(inv.get("files", []))
            == fx["inventory"]["files_total"],
            f"{len(docs)} documents, inventory {inv.get('files_total')} with {len(inv.get('files', []))} entries",
        )
        self.expect(
            "counts.by_class",
            by_class == fx["inventory"]["by_class"],
            f"by_class {by_class}",
        )
        lessons = by_class.get("opl", 0)
        self.expect(
            "counts.lessons",
            lessons == LESSONS and (opls is None or len(opls["lessons"]) == LESSONS),
            f"{lessons} lesson documents"
            + (f", {len(opls['lessons'])} parsed lessons" if opls else ""),
        )
        self.expect(
            "counts.work_orders",
            len(wos) == WORK_ORDERS == fx["workbook"]["rows"],
            f"{len(wos)} work orders",
        )
        findings = reg.get("findings", [])
        defects = sum(1 for f in findings if not f["observation_only"])
        self.expect(
            "counts.register",
            reg.get("total")
            == REGISTER_TOTAL
            == fx["integrity"]["total"]
            == sum(reg.get("rules", {}).values())
            == defects,
            f"register total {reg.get('total')}, {defects} defect findings, {len(findings) - defects} observations",
        )
        spot = self.load("datasheet_spot.json") or []
        per_asset = {}
        for s in spot:
            per_asset[s["equipment_tag"]] = per_asset.get(s["equipment_tag"], 0) + 1
        self.expect(
            "counts.datasheet_spot",
            len(spot) == 24
            and all(n == 3 for n in per_asset.values())
            and len(per_asset) == 8,
            f"{len(spot)} pins over {len(per_asset)} assets",
        )
        rspot = self.load("revision_spot.json") or []
        self.expect(
            "counts.revision_spot", len(rspot) == 40, f"{len(rspot)} revision pins"
        )

    def check_closure(self):
        docs = {d["id"] for d in self.load("documents.json") or []}
        doc_class = {d["id"]: d["class"] for d in self.load("documents.json") or []}
        doc_nos = {
            d["doc_no"] for d in self.load("documents.json") or [] if d["doc_no"]
        }
        revs = self.load("revisions.json") or []
        rev_ids = {r["id"] for r in revs}
        current = {r["document_id"] for r in revs if r["is_current"]}
        cl = self.load("claims.json") or {"spans": [], "claims": [], "edges": []}
        spans = {s["id"] for s in cl["spans"]}
        il = self.load("interlocks.json") or {}
        eq = {e["tag"] for e in il.get("equipment", [])}
        seqs = {i["seq_id"] for i in il.get("interlocks", []) if i["seq_id"]}
        tags = {t["tag"] for t in il.get("instrument_tags", [])}
        wos = {w["wo_number"] for w in self.load("work_orders.json") or []}
        opls = {
            d["doc_no"]
            for d in self.load("documents.json") or []
            if d["class"] == "opl"
        }
        bom = self.load("bom.json") or {"items": [], "matches": []}
        bom_ids = {b["id"] for b in bom["items"]}
        params = self.load("datasheet_params.json") or []
        identities = {p["value_text"] for p in params if p["field"] in IDENTITY_FIELDS}
        entity_universe = eq | tags | seqs | wos | opls | docs | bom_ids | {"NONE"}
        lessons = self.load("opls.json") or {
            "lessons": [],
            "steps": [],
            "troubleshooting_rows": [],
        }
        sidecars = [self.load(f"pid_sidecars/set_{n:02d}.json") for n in range(1, 9)]
        sidecars = [s for s in sidecars if s]
        chains = self.load("chains.json") or []
        cov = self.load("coverage_scores.json") or {"assessments": [], "summaries": []}
        labels = self.load("coverage_labels.json") or {
            "records": [],
            "uncovered_ids": [],
        }
        debt = self.load("debt.json") or []
        tests = self.load("proof_tests.json") or []
        fams = self.load("families.json") or []
        events = self.load("failure_events.json") or []
        hv = self.load("hand_verified.json") or {"sets": []}
        inv = self.load("inventory.json") or {"files": []}
        reg = self.load("integrity_findings.json") or {"findings": []}

        # documents and revisions
        self.expect(
            "closure.current_revision",
            current == docs,
            f"{len(current)} of {len(docs)} documents carry a current revision",
        )
        self.members(
            "closure.revision.document_id",
            [r["document_id"] for r in revs],
            docs,
            "revisions.json document_id",
        )
        self.members(
            "closure.span.revision",
            [s["document_revision_id"] for s in cl["spans"]],
            rev_ids,
            "spans document_revision_id",
        )
        self.members(
            "closure.claim.span",
            [c["span_id"] for c in cl["claims"]],
            spans,
            "claims span_id",
        )
        self.members(
            "closure.claim.binding",
            [c["entity_binding"] for c in cl["claims"]],
            entity_universe,
            "claims entity_binding",
        )
        self.members(
            "closure.claim.kind",
            [c["claim_kind"] for c in cl["claims"]],
            set(CLAIM_KINDS),
            "claims claim_kind",
        )
        self.members(
            "closure.edge.document",
            [e["from_document_id"] for e in cl["edges"]]
            + [e["to_document_id"] for e in cl["edges"]],
            docs,
            "edges document ids",
        )
        self.members(
            "closure.edge.span",
            [e["source_span_id"] for e in cl["edges"]],
            spans,
            "edges source_span_id",
        )
        self.members(
            "closure.inventory.document",
            [f["document_id"] for f in inv["files"]],
            docs,
            "inventory files document_id",
        )
        self.members(
            "closure.revision_spot",
            [r["id"] for r in self.load("revision_spot.json") or []],
            {r["id"] for r in revs if r["is_current"]},
            "revision_spot ids (current revisions)",
        )
        # asset and safety graph
        self.members(
            "closure.equipment.docs",
            [
                e[k]
                for e in il.get("equipment", [])
                for k in (
                    "datasheet_doc_no",
                    "ga_drawing_doc_no",
                    "plot_plan_doc_no",
                    "ce_doc_no",
                )
            ],
            doc_nos,
            "equipment document numbers",
        )
        self.members(
            "closure.equipment.pid",
            [e["pid_document_id"] for e in il.get("equipment", [])],
            {d for d, c in doc_class.items() if c == "pid"},
            "equipment pid_document_id",
        )
        self.members(
            "closure.interlock.equipment",
            [i["equipment_tag"] for i in il.get("interlocks", [])]
            + [r["equipment_tag"] for r in il.get("rows", [])],
            eq,
            "interlock equipment_tag",
        )
        self.members(
            "closure.interlock.notes",
            [n["span_id"] for i in il.get("interlocks", []) for n in i["notes"]],
            spans,
            "interlock notes span_id",
        )
        self.members(
            "closure.row.span",
            [r["span_id"] for r in il.get("rows", [])],
            spans,
            "interlock rows span_id",
        )
        self.members(
            "closure.row.seq",
            [r["seq_id"] for r in il.get("rows", []) if r["seq_id"]],
            seqs,
            "interlock rows seq_id",
        )
        self.members(
            "closure.row.instrument",
            [r["instrument_tag"] for r in il.get("rows", [])],
            tags,
            "interlock rows instrument_tag",
        )
        self.members(
            "closure.permissive.seq",
            [p["seq_id"] for p in il.get("permissives", [])],
            seqs | eq,
            "permissives seq_id (sheet key)",
        )
        self.members(
            "closure.permissive.signal",
            [p["signal_tag"] for p in il.get("permissives", []) if p["signal_tag"]],
            tags,
            "permissives signal_tag",
        )
        self.members(
            "closure.permissive.span",
            [p["span_id"] for p in il.get("permissives", [])],
            spans,
            "permissives span_id",
        )
        self.members(
            "closure.instrument.equipment",
            [t["equipment_tag"] for t in il.get("instrument_tags", [])],
            eq,
            "instrument_tags equipment_tag",
        )
        self.members(
            "closure.instrument.sources",
            [s for t in il.get("instrument_tags", []) for s in t["sources"]],
            docs,
            "instrument_tags sources",
        )
        self.members(
            "closure.param.span",
            [p["span_id"] for p in params]
            + [p["span_id"] for p in self.load("datasheet_spot.json") or []],
            spans,
            "datasheet params and spot span_id",
        )
        self.members(
            "closure.param.equipment",
            [p["equipment_tag"] for p in params],
            eq,
            "datasheet params equipment_tag",
        )
        self.members(
            "closure.area.code",
            [e["area_code"] for e in il.get("equipment", [])],
            {a["code"] for a in self.load("area_aliases.json") or []},
            "equipment area_code",
        )
        # sidecars
        self.members(
            "closure.sidecar.document",
            [s["document_id"] for s in sidecars],
            {d for d, c in doc_class.items() if c == "pid"},
            "sidecar document_id",
        )
        self.members(
            "closure.sidecar.bound_tag",
            [h["bound_tag"] for s in sidecars for h in s["hotspots"] if h["bound_tag"]],
            tags | eq | seqs | identities,
            "hotspot bound_tag",
        )
        unreasoned = [
            h["id"]
            for s in sidecars
            for h in s["hotspots"]
            if h["bound_tag"] is None and not h["unbound_reason"]
        ]
        self.expect(
            "closure.sidecar.unbound_reason",
            not unreasoned,
            f"{len(unreasoned)} null bindings without a reason",
        )
        prov = [s["provenance"] for s in sidecars]
        self.expect(
            "closure.sidecar.provenance",
            all(
                p["basis"] == "manual"
                or (
                    p["basis"] == "agent_transcription"
                    and p["review_status"] == "pending"
                )
                for p in prov
            ),
            f"{len(prov)} sidecars, basis {sorted({p['basis'] for p in prov})} (D-12)",
        )
        self.members(
            "closure.hand_verified.document",
            [s["document_id"] for s in hv["sets"]],
            docs,
            "hand_verified document_id",
        )
        # operations
        self.members(
            "closure.work_order.equipment",
            [w["equipment_tag"] for w in self.load("work_orders.json") or []],
            eq,
            "work orders equipment_tag",
        )
        self.members(
            "closure.failure_event.wo",
            [e["wo_number"] for e in events],
            wos,
            "failure events wo_number",
        )
        self.members(
            "closure.family.wo",
            [m["wo_number"] for f in fams for m in f["members"]],
            wos,
            "family members wo_number",
        )
        self.members(
            "closure.chain.wo",
            [c["from_wo"] for c in chains] + [c["to_wo"] for c in chains],
            wos,
            "chains wo numbers",
        )
        self.members(
            "closure.chain.span",
            [c["span_id"] for c in chains],
            spans,
            "chains span_id",
        )
        self.members(
            "closure.proof_test.wo",
            [t["wo_number"] for t in tests],
            wos,
            "proof tests wo_number",
        )
        self.members(
            "closure.proof_test.seq",
            [t["seq_id"] for t in tests if t["seq_id"]],
            seqs,
            "proof tests seq_id",
        )
        self.members(
            "closure.bom.span",
            [b["span_id"] for b in bom["items"]],
            spans,
            "bom items span_id",
        )
        self.members(
            "closure.bom.drawing",
            [b["ga_drawing_doc_no"] for b in bom["items"]],
            doc_nos,
            "bom items ga_drawing_doc_no",
        )
        self.members(
            "closure.bom_match.wo",
            [m["wo_number"] for m in bom["matches"]],
            wos,
            "bom matches wo_number",
        )
        self.members(
            "closure.bom_match.item",
            [
                m[k]
                for m in bom["matches"]
                for k in ("bom_item_id", "alternative_bom_item_id")
                if m[k]
            ],
            bom_ids,
            "bom matches bom_item_id",
        )
        # lessons, coverage, debt, register
        self.members(
            "closure.opl.revision",
            [o["document_revision_id"] for o in lessons["lessons"]],
            rev_ids,
            "lessons document_revision_id",
        )
        self.members(
            "closure.opl.id",
            [o["opl_id"] for o in lessons["lessons"]]
            + [s["opl_id"] for s in lessons["steps"]]
            + [r["opl_id"] for r in lessons["troubleshooting_rows"]],
            opls,
            "lessons, steps and rows opl_id",
        )
        self.members(
            "closure.opl.span",
            [s["span_id"] for s in lessons["steps"]]
            + [p["span_id"] for o in lessons["lessons"] for p in o["permit_lines"]],
            spans,
            "steps and permit lines span_id",
        )
        self.members(
            "closure.opl.quoted_wo",
            [
                r["quoted_wo_number"]
                for r in lessons["troubleshooting_rows"]
                if r["quoted_wo_number"]
            ],
            wos,
            "troubleshooting rows quoted_wo_number",
        )
        self.members(
            "closure.coverage.wo",
            [a["wo_number"] for a in cov["assessments"]],
            wos,
            "coverage assessments wo_number",
        )
        self.members(
            "closure.coverage.lesson",
            [a["matched_lesson"] for a in cov["assessments"] if a["matched_lesson"]],
            opls,
            "coverage assessments matched_lesson",
        )
        self.members(
            "closure.labels.wo",
            [r["wo_number"] for r in labels["records"]] + list(labels["uncovered_ids"]),
            wos,
            "coverage labels wo numbers",
        )
        self.members(
            "closure.labels.lesson",
            [o for r in labels["records"] for o in (r.get("covered_by") or [])],
            opls,
            "coverage labels covered_by",
        )
        self.members(
            "closure.debt.equipment",
            [d["equipment_tag"] for d in debt],
            eq,
            "debt equipment_tag",
        )
        self.members(
            "closure.debt.wo",
            [w for d in debt for w in d["uncovered_wo_numbers"]],
            wos,
            "debt uncovered_wo_numbers",
        )
        self.members(
            "closure.register.document",
            [f["document_id"] for f in reg["findings"] if f["document_id"]],
            docs,
            "register findings document_id",
        )
        self.members(
            "closure.register.span",
            [f["span_id"] for f in reg["findings"] if f["span_id"]],
            spans,
            "register findings span_id",
        )
        self.members(
            "closure.register.seq",
            [f["safety_function"] for f in reg["findings"] if f["safety_function"]],
            seqs,
            "register findings safety_function",
        )
        chunk_revs = []
        if os.path.exists(self.path("chunks.jsonl")):
            with open(self.path("chunks.jsonl"), encoding="utf-8") as f:
                chunk_revs = [
                    json.loads(line)["document_revision_id"]
                    for line in f
                    if line.strip()
                ]
            self.members(
                "closure.chunk.revision",
                chunk_revs,
                rev_ids,
                "chunks.jsonl document_revision_id",
            )
        if os.path.exists(self.path("pages/index.json")):
            index = self.load("pages/index.json")
            self.members(
                "closure.pages.document",
                [d["document_id"] for d in index["documents"]],
                docs,
                "pages/index.json document_id",
            )

    def check_hashes(self):
        if not os.path.isdir(self.corpus):
            self.fail(
                "hashes.corpus",
                f"corpus not found at {self.corpus}: span hashes cannot be recomputed",
            )
            return
        docs = {d["id"]: d for d in self.load("documents.json") or []}
        revs = {r["id"]: r for r in self.load("revisions.json") or []}
        cl = self.load("claims.json") or {"spans": []}
        pages, rows = {}, None
        bad, long = [], []

        def page_text(rev_id, page):
            nonlocal rows
            d = docs[revs[rev_id]["document_id"]]
            if d["class"] == "workbook":
                rows = (
                    rows
                    if rows is not None
                    else D.workbook_row_texts(
                        os.path.join(self.corpus, d["source_path"])
                    )
                )
                return rows.get(page)
            if d["id"] not in pages:
                pages[d["id"]] = D.pdf_page_texts(
                    os.path.join(self.corpus, d["source_path"])
                )
            texts = pages[d["id"]]
            return texts[page - 1] if 0 < page <= len(texts) else None

        for s in cl["spans"]:
            text = page_text(s["document_revision_id"], s["page"])
            if len(s["anchor_text"]) > D.CITATION_MAX_CHARS:
                long.append(s["id"])
            if (
                text is None
                or text[s["start_ordinal"] : s["end_ordinal"]] != s["anchor_text"]
                or quote_hash(s["anchor_text"]) != s["quote_hash"]
            ):
                bad.append(s["id"])
        self.expect(
            "hashes.spans",
            not bad,
            f"{len(cl['spans'])} spans re-extracted, {len(bad)} mismatched"
            + (f" (first: {bad[0]})" if bad else ""),
        )
        self.expect(
            "hashes.citation_length",
            not long,
            f"{len(long)} spans over {D.CITATION_MAX_CHARS} characters",
        )
        for f in docs.values():
            got = P.file_sha256(os.path.join(self.corpus, f["source_path"]))
            if got != f["sha256"]:
                bad.append(f["id"])
        self.expect(
            "hashes.documents",
            not [b for b in bad if b in docs],
            f"{len(docs)} source files re-hashed",
        )
        opls = self.load("opls.json")
        if opls:
            steps = [
                s
                for s in opls["steps"]
                if quote_hash(s["action_text"]) != s["source_hash"]
            ]
            sections = [
                o["opl_id"]
                for o in opls["lessons"]
                for x in o["sections"]
                if quote_hash(x["body_text"]) != x["body_hash"]
            ]
            self.expect(
                "hashes.steps",
                not steps and not sections,
                f"{len(opls['steps'])} step hashes and {6 * len(opls['lessons'])} section hashes recomputed, {len(steps) + len(sections)} mismatched",
            )
        if os.path.exists(self.path("chunks.jsonl")):
            n, bad, unresolved = 0, 0, 0
            with open(self.path("chunks.jsonl"), encoding="utf-8") as f:
                for line in f:
                    c = json.loads(line)
                    if c["document_revision_id"] not in revs:
                        unresolved += 1  # named by closure.chunk.revision, not double-counted here
                        continue
                    n += 1
                    text = page_text(c["document_revision_id"], c["page"])
                    if (
                        text is None
                        or c["text"] not in text
                        or quote_hash(c["text"]) != c["quote_hash"]
                    ):
                        bad += 1
            self.expect(
                "hashes.chunks",
                bad == 0,
                f"{n} chunks checked against their page text, {bad} mismatched, {unresolved} skipped (revision unresolved)",
            )

    def check_manifest_fields(self, m, fx):
        self.expect(
            "manifest.extractor",
            m["extractor"] == fx["inventory"]["extractor"],
            m["extractor"],
        )
        self.expect(
            "manifest.recipe",
            m["recipe_sha256"] == fx["method"]["recipe_sha256"]
            and m["stop_list_sha256"] == fx["method"]["stop_list_sha256"],
            "recipe_sha256 and stop_list_sha256 equal the fixture's",
        )
        self.expect(
            "manifest.corpus",
            m["corpus_sha256"] == fx["inventory"]["corpus_sha256"],
            f"corpus_sha256 {m['corpus_sha256'][:12]} equals the fixture's",
        )
        if os.path.isdir(self.corpus):
            got = P.corpus_sha256(P.corpus_files(self.corpus))
            self.expect(
                "manifest.corpus_recomputed",
                got == m["corpus_sha256"],
                f"corpus at hand digests to {got[:12]}",
            )
        rp = self.load("rulepack/v1.json") or {}
        self.expect(
            "manifest.rulepack",
            str(rp.get("version")) == m["rulepack_version"],
            f"rulepack_version {m['rulepack_version']}",
        )

    def run(self):
        m = self.check_manifest()
        if m is None:
            return False
        fx = self.load("fixtures.json")
        if fx is None:
            self.fail("fixtures", "fixtures.json missing")
            return False
        self.check_schemas(m["bundle_version"])
        self.check_counts(fx)
        self.check_closure()
        self.check_hashes()
        self.check_manifest_fields(m, fx)
        return not self.violations


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    bundle_dir = os.path.abspath(argv[0] if argv else "bundle")
    corpus = argv[1] if len(argv) > 1 else CORPUS
    g = Gate(bundle_dir, corpus)
    admitted = g.run()
    print("\n".join(g.lines))
    m = g.load("manifest.json") or {}
    if admitted:
        print(
            f"G1: ADMIT bundle {m.get('bundle_version')} ({len(g.lines)} checks, {len(m.get('files', []))} files)"
        )
        return 0
    print(
        f"G1: REJECT bundle {m.get('bundle_version')}: {len(g.violations)} violation(s)"
    )
    for v in g.violations:
        print("  - " + v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
