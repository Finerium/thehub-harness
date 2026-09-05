"""Documents, revisions, spans, parser claims and document edges of blueprint 9.2 for the bundle (T1).

Every document is one of the 98 corpus files (harness.pdftext.corpus_files, classed by harness.pdftext.doc_class).
Identifiers are the ones the application's seed uses (scripts/db/seed-m0.ts), so every lane names a document the same
way: id "doc-" + sha256[:12] and, for the one current revision of corpus version 1, "rev-" + sha256[:12]; a superseded
revision a drawing's history table records (A, B before 0) is "rev-" + sha256[:12] + "-" + revision. harness.chunks and
harness.pages must name files by the same two functions (document_id, revision_id) for chunks.jsonl and pages/ to pass
G1's referential closure.

Text comes only from harness.pdftext (`pdftotext -raw`, the canonical form): a PDF page's text is the form-feed
separated page of the extractor output, canonicalised; the workbook's "pages" are its rows (the Excel row number) and a
row's text is the canonical join of its WORKBOOK_TEXT_COLUMNS. A Span anchors a run of that page text: start_ordinal and
end_ordinal are character offsets into the canonical page text, so `page_text[start:end] == canonical(anchor_text)`
and `quote_hash == sha256(canonical(anchor_text))`; G1 recomputes both from the corpus. Anchors are cut at citation
length (CITATION_MAX_CHARS, under the 200-character rule of blueprint 8.3).

Parser claims (`extracted_by: {basis: "parser"}`) bind to the closed entity set of the bundle: equipment tags, instrument
tags, sequence ids, work-order numbers, lesson ids, document ids and BOM item ids. No AG-1 claim exists yet (D-18).

Edges are typed only from extracted text (datasheet cross-reference notes, drawing ASSOC DOCS notes, plot-plan and C&E
notes, lesson header labels, lesson cross-reference lines); a citation that names no document of the bundle is raised in
`unresolved_references`, never guessed. P&ID citations live in the sidecars (no text layer) and in the CD-7 / CD-8 rules.
A P&ID number resolves through the set's own typed documents (every lesson header of a set names its P&ID), a LOGIC No
through the C&E sheet that types it (FR-106: nothing is derived from a tag number).
"""

import os
import re
import zipfile

import openpyxl

from . import pdftext as P
from .canonical import canonical, quote_hash
from .config import WORKBOOK

CITATION_MAX_CHARS = 199
CORPUS_VERSION_ID = "v1"  # the label of the first corpus version; the seed maps it to its deterministic id
NO_REVISION = "-"  # the corpus's own marker for "none recorded" (Related_Interlock, Spare_Parts_Used)
WORKBOOK_TEXT_COLUMNS = (
    "WO_Number",
    "Problem_Description",
    "Root_Cause",
    "Corrective_Action",
    "Spare_Parts_Used",
    "Remarks",
)
APPROVAL = {
    "ISSUED FOR OPERATION": "issued_for_operation",
    "ISSUED FOR CONSTRUCTION": "issued_for_construction",
    "ISSUED FOR APPROVAL": "issued_for_approval",
    "ISSUED FOR REVIEW": "issued_for_review",
}
OPL_APPROVAL_TEXT = "Approved by (Manager)"  # the lesson footer's own column label
SET_NO = re.compile(r"Set_(\d{2})_")
OPL_MARKER = re.compile(r"(?i)_(edited(?:_[a-z_]+)?)\.pdf$")
EMP = re.compile(r"\(EMP-(\d{4})\)")
PID_NO = re.compile(r"TJC-LLD-PID-\d{4}")
PID_ANY = re.compile(r"TJC-LLD-PID-\S+")
SEQ_NO = re.compile(r"SEQ-\d{4}")
PID_REV = re.compile(r"title block REV\. (\S+)")


# ---------------------------------------------------------------- identifiers
def document_id(digest):
    """The bundle's document id: "doc-" + sha256[:12] (the scheme the application's seed uses)."""
    return "doc-" + digest[:12]


def revision_id(digest):
    """The id of the one current revision of a file in corpus version 1: "rev-" + sha256[:12]."""
    return "rev-" + digest[:12]


def revision_row_id(digest, revision, is_current):
    """A DocumentRevision id: the current revision's revision_id, a superseded one suffixed with its revision label."""
    return revision_id(digest) + ("" if is_current else f"-{revision}")


def rev_id(doc_id, revision):
    """Label form "<document label>@<revision>" that harness.chunks and harness.pages call with a lesson id or a
    document number. It is not a bundle id: revisions.json carries revision_row_id, so chunks.jsonl and pages/ written
    with this form fail G1's referential closure until those modules name files by digest again."""
    return f"{doc_id}@{revision}"


# ---------------------------------------------------------------- page text
def pdf_page_texts(path):
    """Canonical text per page of a PDF (the extractor separates pages with a form feed)."""
    pages = P.pdf_text(path).split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    return [canonical(p) for p in pages]


def workbook_row_texts(path=WORKBOOK):
    """{excel_row_number: canonical text} of the maintenance sheet, one "page" per data row."""
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    hdr = [c.value for c in ws[1]]
    idx = [hdr.index(c) for c in WORKBOOK_TEXT_COLUMNS]
    out = {}
    for n, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        out[n] = canonical(" ".join(str(r[i]) for i in idx if r[i] not in (None, "")))
    return out


def workbook_row_count(path=WORKBOOK):
    return openpyxl.load_workbook(path, read_only=True).worksheets[0].max_row


def pptx_slide_count(path):
    with zipfile.ZipFile(path) as z:
        return sum(
            1 for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
        )


def emp_alias(cell):
    """'Name (EMP-1113)' -> 'EMP-1113' (the pseudonym; the name never leaves the workbook)."""
    m = EMP.search(str(cell or ""))
    return f"EMP-{m.group(1)}" if m else None


def approval_status(text):
    if text == OPL_APPROVAL_TEXT:
        return "approved"
    return APPROVAL.get((text or "").strip().upper(), "unknown")


# ---------------------------------------------------------------- spans and claims
class Spans:
    """Span registry: one span per (revision, page, start, end); anchors located in the canonical page text."""

    def __init__(self):
        self.by_id = {}

    def add(self, rev_id, page, page_text, anchor, hint=0):
        a = canonical(anchor)
        if len(a) > CITATION_MAX_CHARS:
            cut = a.rfind(" ", 0, CITATION_MAX_CHARS)
            a = a[: cut if cut > 0 else CITATION_MAX_CHARS]
        start = page_text.find(a, hint)
        if start < 0:
            raise LookupError(
                f"anchor not in page text of {rev_id} p{page}: {a[:80]!r}"
            )
        sid = f"{rev_id}/p{page}/{start}-{start + len(a)}"
        self.by_id.setdefault(
            sid,
            {
                "id": sid,
                "document_revision_id": rev_id,
                "page": page,
                "anchor_text": a,
                "quote_hash": quote_hash(a),
                "start_ordinal": start,
                "end_ordinal": start + len(a),
            },
        )
        return sid

    def locate(self, rev_id, pages, anchor):
        """The span of `anchor` on the first page (1-based, in order) of `pages` that carries it."""
        a = canonical(anchor)
        for n, text in enumerate(pages, start=1):
            if a[:CITATION_MAX_CHARS] in text:
                return self.add(rev_id, n, text, a)
        raise LookupError(f"anchor on no page of {rev_id}: {a[:80]!r}")

    def rows(self):
        return [self.by_id[k] for k in sorted(self.by_id)]


class Claims:
    def __init__(self):
        self.items = set()

    def add(self, span_id, binding, kind, value_text):
        self.items.add((span_id, kind, binding or "NONE", canonical(value_text)))

    def rows(self):
        out = []
        for n, (sid, kind, binding, value) in enumerate(sorted(self.items), start=1):
            out.append(
                {
                    "id": f"CLM-{n:05d}",
                    "span_id": sid,
                    "entity_binding": binding,
                    "claim_kind": kind,
                    "value_text": value,
                    "extracted_by": {"basis": "parser"},
                }
            )
        return out


# ---------------------------------------------------------------- documents and revisions
def file_marker(path):
    m = OPL_MARKER.search(os.path.basename(path))
    return m.group(1) if m else None


def set_no(path):
    m = SET_NO.search(path)
    return int(m.group(1)) if m else None


def register(files, drawings, plots, datasheets, interlocks, sidecars_by_set):
    """Document rows (9.2) for the 98 files plus the per-document facts the other builders need.

    drawings / plots: harness.master.parse_drawing per tag; datasheets: parse_datasheet per tag; interlocks:
    parse_interlock per tag; sidecars_by_set: the packages/pid_sidecars/set_0n.json object per set number (for the
    P&ID's own reference box). facts[id] = {path, sha256, class, tag, set, opl_id}.
    """
    docs, facts = [], {}
    for path in files:
        cls, tag = P.doc_class(path), P.tag_of_path(path)
        rel = os.path.relpath(path, P.CORPUS)
        low = path.lower()
        sha = P.file_sha256(path)
        did = document_id(sha)
        page_count = P.pdf_pages(path) if low.endswith(".pdf") else 1
        oid = None
        if cls == "opl":
            oid = doc_no = P.opl_id(path)
        elif cls == "datasheet":
            doc_no = datasheets[tag]["doc_no"]
        elif cls == "ga_drawing":
            doc_no = drawings[tag]["dwg_no"]
        elif cls == "plot_plan":
            doc_no = plots[tag]["dwg_no"]
        elif cls == "interlock":
            doc_no = interlocks[tag]["header"]["doc_no"]
        elif cls == "pid":
            m = PID_ANY.search(sidecars_by_set[set_no(path)].get("reference_box") or "")
            doc_no = m.group(0) if m else None
        elif cls == "workbook":
            doc_no, tag = None, None
            page_count = workbook_row_count(path)
        elif cls == "organiser_note":
            doc_no, tag = None, None
            page_count = pptx_slide_count(path)
        else:
            raise ValueError(f"unclassed corpus file: {rel}")
        docs.append(
            {
                "id": did,
                "doc_no": doc_no,
                "class": cls,
                "subject_tag": tag,
                "sha256": sha,
                "source_path": rel,
                "page_count": page_count,
                "file_marker": file_marker(path),
            }
        )
        facts[did] = {
            "path": path,
            "sha256": sha,
            "class": cls,
            "tag": tag,
            "set": set_no(path),
            "opl_id": oid,
        }
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise ValueError(
            "document ids collide: "
            + ", ".join(sorted(i for i in ids if ids.count(i) > 1))
        )
    return sorted(docs, key=lambda d: d["id"]), facts


def revisions(
    docs, facts, opl_parsed, drawings, plots, datasheets, interlocks, pid_revisions
):
    """DocumentRevision rows (9.2): the drawings' revision history (A, B, 0 with dates), the datasheet's typed revision and
    issue status, the C&E sheet's REV, the lesson's approval footer (aliases only), the P&ID's revision block where one
    is drawn (pid_revisions: {set: revision}), and the "-" marker where a document prints no revision."""
    out = []

    def row(d, revision, status_text, is_current, **kw):
        r = {
            "id": revision_row_id(d["sha256"], revision, is_current),
            "document_id": d["id"],
            "revision": revision,
            "approval_status": approval_status(status_text),
            "approval_status_text": status_text,
            "revision_date": None,
            "prepared_by_alias": None,
            "reviewed_by_alias": None,
            "approved_by_alias": None,
            "date_of_sharing": None,
            "is_current": is_current,
            "corpus_version_id": CORPUS_VERSION_ID,
        }
        r.update(kw)
        out.append(r)

    for d in docs:
        f, cls, tag = facts[d["id"]], d["class"], d["subject_tag"]
        if cls == "datasheet":
            ds = datasheets[tag]
            row(d, str(ds["rev"]), ds["status"], True)
        elif cls in ("ga_drawing", "plot_plan"):
            dw = (drawings if cls == "ga_drawing" else plots)[tag]
            for h in dw["history"]:
                row(
                    d,
                    h["rev"],
                    h["description"],
                    h["rev"] == dw["rev"],
                    revision_date=h["date"],
                    prepared_by_alias=h["by"],
                )
        elif cls == "interlock":
            row(d, str(interlocks[tag]["header"]["rev"]), "", True)
        elif cls == "opl":
            lp = opl_parsed[f["opl_id"]]
            approved = bool(lp["approved_by_id"] and lp["date_of_sharing"])
            row(
                d,
                NO_REVISION,
                OPL_APPROVAL_TEXT if approved else "",
                True,
                revision_date=lp["date_of_sharing"],
                prepared_by_alias=lp["prepared_by_role"],
                reviewed_by_alias=lp["reviewed_by_id"],
                approved_by_alias=lp["approved_by_id"],
                date_of_sharing=lp["date_of_sharing"],
            )
        elif cls == "pid":
            row(d, pid_revisions.get(f["set"]) or NO_REVISION, "", True)
        else:
            row(d, NO_REVISION, "", True)
    return sorted(out, key=lambda r: r["id"])


def pid_revision(transcript):
    """The revision a P&ID's own title block draws (Set 4 only), read from the adopted transcript's revision block."""
    m = PID_REV.search(transcript.get("revision_block_as_drawn") or "")
    return m.group(1) if m else None


def current_rev(revs):
    """{document_id: revision id of the current revision}."""
    return {r["document_id"]: r["id"] for r in revs if r["is_current"]}


# ---------------------------------------------------------------- edges
class Resolver:
    """Document references of the corpus text resolved to document ids, from data only."""

    def __init__(self, docs, facts, opl_parsed, interlocks):
        self.by_doc_no = {
            d["doc_no"]: d["id"] for d in docs if d["doc_no"] and d["class"] != "pid"
        }
        self.by_tag_class = {
            (d["subject_tag"], d["class"]): d["id"]
            for d in docs
            if d["subject_tag"] and d["class"] != "opl"
        }
        self.by_opl = {
            facts[d["id"]]["opl_id"]: d["id"] for d in docs if d["class"] == "opl"
        }
        self.opls_of = {}
        for oid in sorted(self.by_opl):
            self.opls_of.setdefault(P.tag_of_opl(oid), []).append(self.by_opl[oid])
        singles = {
            d["class"]: d["id"]
            for d in docs
            if d["class"] in ("workbook", "organiser_note")
        }
        self.workbook = singles["workbook"]
        self.organiser = singles["organiser_note"]
        self.pid_by_set = {
            facts[d["id"]]["set"]: d["id"] for d in docs if d["class"] == "pid"
        }
        pid_no = {}
        for oid, lp in opl_parsed.items():
            pid_no.setdefault(lp["tag"], set()).add(lp["pid_ref"])
        self.by_pid_no = {}
        for tag, nos in pid_no.items():
            if len(nos) != 1:
                raise ValueError(
                    f"the lessons of {tag} name more than one P&ID: {sorted(nos)}"
                )
            self.by_pid_no[next(iter(nos))] = self.by_tag_class[(tag, "pid")]
        self.by_seq = {
            il["header"]["logic_no"]: self.by_doc_no[il["header"]["doc_no"]]
            for il in interlocks.values()
            if il["header"]["logic_no"]
        }

    def pid(self, no):
        return self.by_pid_no.get(no)

    def seq(self, seq_id):
        return self.by_seq.get(seq_id)

    def of(self, tag, cls):
        return self.by_tag_class.get((tag, cls))


def edges(
    docs, facts, revs, page_texts, opl_parsed, texts_by_class, spans, claims, resolver
):
    """DocumentEdge rows (9.2) from the documents' own reference lines, each anchored by a span, plus the unresolved list.

    page_texts: {document_id: [canonical page texts]} of the PDFs.
    """
    cur = current_rev(revs)
    out, unresolved = set(), []

    def add(from_id, to_id, kind, sid, cited):
        if to_id is None:
            unresolved.append(
                {
                    "from_document_id": from_id,
                    "cited_text": cited,
                    "span_id": sid,
                    "edge_kind": kind,
                }
            )
        else:
            out.add((from_id, to_id, kind, sid))

    def span(doc_id, anchor):
        return spans.locate(cur[doc_id], page_texts[doc_id], anchor)

    for d in docs:
        did, cls, tag = d["id"], d["class"], d["subject_tag"]
        if cls == "datasheet":
            text = texts_by_class["datasheet"][tag]
            m = re.search(
                r"Cross-reference for tag ([A-Z]{2}-\d{4}[A-Z]?): (.+?\.)", text
            )
            if m:
                sid = span(did, m.group(0))
                claims.add(sid, tag, "note", m.group(0))
                x = m.group(1)
                add(
                    did,
                    resolver.of(x, "ga_drawing"),
                    "cross_reference",
                    sid,
                    "GA Drawing",
                )
                pid = PID_NO.search(m.group(2))
                if pid:
                    add(
                        did,
                        resolver.pid(pid.group(0)),
                        "cross_reference",
                        sid,
                        pid.group(0),
                    )
                seq = SEQ_NO.search(m.group(2))
                if seq:
                    add(
                        did,
                        resolver.seq(seq.group(0)),
                        "cross_reference",
                        sid,
                        seq.group(0),
                    )
                for oid in resolver.opls_of.get(x, []):
                    add(did, oid, "cross_reference", sid, "OPL sheets")
                add(
                    did,
                    resolver.workbook,
                    "cross_reference",
                    sid,
                    "Maintenance History",
                )
        elif cls == "ga_drawing":
            text = texts_by_class["ga_drawing"][tag]
            m = re.search(r"6\. ASSOCDOCS:(.+?)\.\s", text)
            if m:
                sid = span(did, m.group(0).strip())
                claims.add(sid, tag, "note", m.group(0).strip())
                pid = PID_NO.search(m.group(1))
                if pid:
                    add(
                        did, resolver.pid(pid.group(0)), "assoc_docs", sid, pid.group(0)
                    )
                seq = SEQ_NO.search(m.group(1))
                if seq:
                    add(
                        did, resolver.seq(seq.group(0)), "assoc_docs", sid, seq.group(0)
                    )
        elif cls == "plot_plan":
            text = texts_by_class["plot_plan"][tag]
            m = re.search(r"4\. REFERTOGADRAWINGSFORDETAIL\.", text)
            if m:
                sid = span(did, m.group(0))
                claims.add(sid, tag, "note", m.group(0))
                add(did, resolver.of(tag, "ga_drawing"), "note", sid, "GA DRAWINGS")
        elif cls == "interlock":
            text = texts_by_class["interlock"][tag]
            m = re.search(
                r"4\. Refer to P&ID;? (TJC-LLD-PID-\d{4}) for instrument loops and the Datasheet for design limits of ([A-Z]{2}-\d{4}[A-Z]?)\.",
                text,
            )
            if m:
                sid = span(did, m.group(0))
                claims.add(sid, tag, "note", m.group(0))
                add(did, resolver.pid(m.group(1)), "note", sid, m.group(1))
                add(
                    did,
                    resolver.of(m.group(2), "datasheet"),
                    "note",
                    sid,
                    "Datasheet " + m.group(2),
                )
        elif cls == "opl":
            oid, text = facts[did]["opl_id"], " ".join(page_texts[did])
            m = re.search(
                r"Related Interlock (.+?) (?:P&ID;? Ref |Ref )?(TJC-LLD-PID-\d{4})",
                text,
            )
            if m:
                sid = span(did, m.group(0))
                claims.add(sid, oid, "title", m.group(0))
                add(did, resolver.pid(m.group(2)), "label", sid, m.group(2))
                seq = SEQ_NO.search(m.group(1))
                if seq:
                    add(did, resolver.seq(seq.group(0)), "label", sid, seq.group(0))
            for m in re.finditer(
                r"Always cross-check the Datasheet limits and the (?:P&ID;? )?(TJC-LLD-PID-\d{4}) before working on ([A-Z]{2}-\d{4}[A-Z]?)\.",
                text,
            ):
                sid = span(did, m.group(0))
                claims.add(sid, oid, "note", m.group(0))
                add(did, resolver.pid(m.group(1)), "note", sid, m.group(1))
                add(
                    did,
                    resolver.of(m.group(2), "datasheet"),
                    "note",
                    sid,
                    "Datasheet " + m.group(2),
                )
            seen = set()
            for m in re.finditer(
                r"Cross-ref tag ([A-Z]{2}-\d{4}[A-Z]?) across Datasheet, GA, P&ID;?,? Interlock and Maintenance History\.?",
                text,
            ):
                x = m.group(1)
                if x in seen:
                    continue  # the same line repeated on the page anchors once
                seen.add(x)
                sid = span(did, m.group(0))
                claims.add(sid, x, "note", m.group(0))
                for c in ("datasheet", "ga_drawing", "pid", "interlock"):
                    add(did, resolver.of(x, c), "cross_reference", sid, f"{c} of {x}")
                add(
                    did,
                    resolver.workbook,
                    "cross_reference",
                    sid,
                    "Maintenance History",
                )
    rows = [
        {
            "from_document_id": a,
            "to_document_id": b,
            "edge_kind": k,
            "source_span_id": s,
        }
        for a, b, k, s in sorted(out)
    ]
    return rows, sorted(
        unresolved, key=lambda u: (u["from_document_id"], u["span_id"], u["cited_text"])
    )


if __name__ == "__main__":
    # self-check: the span registry locates, hashes and cuts at citation length; ids follow harness.chunks
    sp = Spans()
    page = canonical("alpha beta  gamma\ndelta")
    sid = sp.add("rev-000000000000", 1, page, "beta gamma")
    s = sp.by_id[sid]
    assert page[s["start_ordinal"] : s["end_ordinal"]] == "beta gamma" and s[
        "quote_hash"
    ] == quote_hash("beta gamma")
    long = " ".join(["word"] * 60)
    sid2 = sp.add("rev-000000000000", 1, canonical(long), long)
    assert len(sp.by_id[sid2]["anchor_text"]) < 200
    assert sp.locate("rev-000000000000", ["nothing here", page], "delta").endswith(
        "/p2/17-22"
    )
    assert document_id("ab" * 32) == "doc-abababababab"
    assert revision_row_id("ab" * 32, "0", True) == "rev-abababababab"
    assert revision_row_id("ab" * 32, "A", False) == "rev-abababababab-A"
    assert rev_id("OPL-GA-1201A-01", NO_REVISION) == "OPL-GA-1201A-01@-"
    assert (
        emp_alias("Wahyu Setiadi (EMP-1113)") == "EMP-1113" and emp_alias("-") is None
    )
    assert approval_status("ISSUED FOR OPERATION") == "issued_for_operation"
    assert (
        approval_status(OPL_APPROVAL_TEXT) == "approved"
        and approval_status("") == "unknown"
    )
    print("documents: ok")
