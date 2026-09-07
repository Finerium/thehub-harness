"""Corpus inventory and text extraction.

Rule (Addendum A, D10): the single text extractor is `pdftotext -raw` (poppler >= 24), invoked identically by the
harness and by the product ingestion; `-layout` is never used outside legacy/. Canonical text form (PRD 19.5):
NFKC, soft hyphens joined, whitespace collapsed to one space, trimmed; case and punctuation kept.
"""

import hashlib
import os
import re
import subprocess
import unicodedata

from .config import CACHE, CORPUS

JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}
OPL_ID = re.compile(r"(OPL-[A-Z]{2}-\d{4}[A-Z]?-\d{2})")
TAG_IN_OPL = re.compile(r"OPL-([A-Z]{2}-\d{4}[A-Z]?)-\d{2}")
TAG_IN_SET = re.compile(r"Set_\d{2}_([A-Z]{2}-\d{4}[A-Z]?)")


def corpus_files(base=CORPUS):
    """Deterministic (sorted) list of corpus files, junk and AppleDouble files skipped (HN-11)."""
    out = []
    for root, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != "__MACOSX")
        for n in sorted(names):
            if n in JUNK or n.startswith("._"):
                continue
            out.append(os.path.join(root, n))
    return out


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_sha256(files):
    """One digest over (relative path, file digest) pairs in sorted order."""
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(os.path.relpath(p, CORPUS).encode("utf-8"))
        h.update(b"\0")
        h.update(file_sha256(p).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def doc_class(path):
    n = os.path.basename(path)
    low = n.lower()
    if low.endswith(".xlsx"):
        return "workbook"
    if low.endswith(".pptx"):
        return "organiser_note"
    if low.endswith(".png"):
        return "pid"
    if n.startswith("OPL-"):
        return "opl"
    if "Datasheet" in n:
        return "datasheet"
    if "Drawing" in n:
        return "ga_drawing"
    if "Interlock" in n:
        return "interlock"
    if "Plot Plan" in n:
        return "plot_plan"
    return "other"


def tag_of_path(path):
    """Equipment tag from the Set_NN_<TAG>_... directory that contains the file."""
    m = TAG_IN_SET.search(path)
    return m.group(1) if m else None


def opl_id(path):
    m = OPL_ID.search(os.path.basename(path))
    return m.group(1) if m else None


def must_match(m, what):
    """The match a parser requires. A corpus file that does not carry the pattern is a named data error, not a None
    that surfaces later as an AttributeError on the caller's `.group`."""
    if m is None:
        raise ValueError(f"pattern not found in corpus text: {what}")
    return m


def tag_of_opl(oid):
    return must_match(TAG_IN_OPL.match(oid), f"equipment tag in lesson id {oid}").group(
        1
    )


def canonical(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("­", "")
    return re.sub(r"\s+", " ", s).strip()


def pdf_text(path, cache_dir=CACHE):
    """Raw-order text of a PDF via `pdftotext -raw`, cached by file content digest."""
    os.makedirs(cache_dir, exist_ok=True)
    key = file_sha256(path) + "-raw"
    cp = os.path.join(cache_dir, key + ".txt")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            return f.read()
    t = subprocess.run(
        ["pdftotext", "-raw", path, "-"], capture_output=True, text=True, check=True
    ).stdout
    tmp = cp + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(t)
    os.replace(tmp, cp)  # atomic: parallel readers never see a partial file
    return t


def pdf_pages(path):
    out = subprocess.run(
        ["pdfinfo", path], capture_output=True, text=True, check=True
    ).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    return int(m.group(1)) if m else None


def opl_texts(base=CORPUS, canon=True):
    """{opl_id: text} for the 56 lessons, canonical by default."""
    out = {}
    for p in corpus_files(base):
        if doc_class(p) == "opl":
            t = pdf_text(p)
            out[opl_id(p)] = canonical(t) if canon else t
    return out


def class_texts(cls, base=CORPUS, canon=True):
    """{tag: text} for one document class (datasheet, ga_drawing, interlock, plot_plan)."""
    out = {}
    for p in corpus_files(base):
        if doc_class(p) == cls:
            t = pdf_text(p)
            out[tag_of_path(p)] = canonical(t) if canon else t
    return out
