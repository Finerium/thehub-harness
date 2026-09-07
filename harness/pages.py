"""Metadata-free page derivatives of every corpus PDF (ADR-010, ADR-011, AC-CTX-09).

    uv run python -m harness.pages --out bundle/pages        (CASE1_CORPUS names the corpus)

Every page of every PDF is rendered with pymupdf at one width of WIDTH px (the sequencing decision in the run notes: one
width, a second waits for a surface that needs it) to WebP at quality QUALITY, as pixels only: no EXIF, no XMP, no ICC
profile, verified by walking the RIFF chunks of every file written. Output: bundle/pages/<document_id>/<n>.webp with an
index.json per document (document id, source file digest, page count, width, and the height, sha256 and byte size of
each render) and one bundle/pages/index.json listing the documents and the files that were skipped because they are
not PDFs (the workbook, the deck and the eight P&ID images). Document ids are harness.chunks.identity, the ids of
documents.json, and must be path-safe. The tree is corpus imagery and stays gitignored (blueprint 8.3).
"""

import argparse
import hashlib
import io
import json
import os
import re
import struct

import pymupdf
from PIL import Image

from .chunks import identity
from .config import CORPUS
from .pdftext import corpus_files, file_sha256

WIDTH, QUALITY = 1200, 80
PATH_SAFE = re.compile(r"[A-Za-z0-9._-]+")
METADATA_CHUNKS = {b"EXIF", b"XMP ", b"ICCP"}


def assert_metadata_free(data):
    """Refuse a WebP that carries an EXIF, XMP or ICCP chunk (RIFF walk; the simple VP8/VP8L form carries none)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("render is not a WebP container")
    i, seen = 12, set()
    while i + 8 <= len(data):
        seen.add(data[i : i + 4])
        size = struct.unpack("<I", data[i + 4 : i + 8])[0]
        i += 8 + size + (size & 1)
    if seen & METADATA_CHUNKS:
        raise ValueError(f"metadata chunk in render: {sorted(seen & METADATA_CHUNKS)}")


def render_pdf(path, out_dir):
    """Write <n>.webp for every page of one PDF into out_dir; [{n, height, sha256, bytes}] in page order."""
    os.makedirs(out_dir, exist_ok=True)
    pages = []
    with pymupdf.open(path) as doc:
        for n, page in enumerate(doc, 1):
            z = WIDTH / page.rect.width
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(z, z), alpha=False, colorspace=pymupdf.csRGB
            )
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if (
                img.width != WIDTH
            ):  # integer rounding of the transformed rectangle can land one pixel off
                img = img.resize(
                    (WIDTH, round(img.height * WIDTH / img.width)), Image.Resampling.LANCZOS
                )
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=QUALITY)
            data = buf.getvalue()
            assert_metadata_free(data)
            with open(os.path.join(out_dir, f"{n}.webp"), "wb") as f:
                f.write(data)
            pages.append(
                {
                    "n": n,
                    "height": img.height,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
    return pages


def build(out, base=CORPUS):
    documents, skipped = [], []
    for p in corpus_files(base):
        if not p.lower().endswith(".pdf"):
            skipped.append(os.path.relpath(p, base))
            continue
        digest = file_sha256(p)
        did = identity(p)[0]
        if not PATH_SAFE.fullmatch(did):
            raise ValueError(f"document id is not a safe directory name: {did!r}")
        pages = render_pdf(p, os.path.join(out, did))
        index = {
            "document_id": did,
            "source_sha256": digest,
            "page_count": len(pages),
            "width": WIDTH,
            "pages": pages,
        }
        with open(os.path.join(out, did, "index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f, indent=1)
            f.write("\n")
        documents.append(
            {"document_id": did, "source_sha256": digest, "page_count": len(pages)}
        )
    top = {
        "width": WIDTH,
        "format": "webp",
        "quality": QUALITY,
        "documents": documents,
        "skipped": skipped,
    }
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(top, f, indent=1)
        f.write("\n")
    return top


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="metadata-free page derivatives of the corpus PDFs (ADR-010)"
    )
    ap.add_argument("--out", default="bundle/pages")
    a = ap.parse_args(argv)
    top = build(a.out)
    print(
        json.dumps(
            {
                "out": a.out,
                "documents": len(top["documents"]),
                "pages": sum(d["page_count"] for d in top["documents"]),
                "width": WIDTH,
                "skipped": top["skipped"],
            }
        )
    )


if __name__ == "__main__":
    main()
