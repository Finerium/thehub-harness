"""bundle/pages as `make pages` writes it (harness.pages; ADR-010, ADR-011, AC-CTX-09): a render for every page of every
corpus PDF at one width of 1200 px, WebP with no EXIF, XMP or ICC chunk, and index.json hashes that match the bytes.
"""

import hashlib
import io
import json
import os
import struct

import pytest
from PIL import Image

from harness import pages as PG
from harness.chunks import identity
from harness.config import CORPUS
from harness.pdftext import corpus_files, file_sha256, pdf_pages

# the session fixture bundle_dir (bundle/ on disk, else a fresh `make bundle` into a temporary directory)
pytest_plugins = ["tests.test_bundle"]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pages_dir(bundle_dir):
    d = os.path.join(bundle_dir, "pages")
    assert os.path.isfile(os.path.join(d, "index.json")), (
        "no pages/index.json: run `make pages`"
    )
    return d


@pytest.fixture(scope="module")
def index(pages_dir):
    return read_json(os.path.join(pages_dir, "index.json"))


def test_index_covers_every_pdf_and_image_and_skips_the_rest(index):
    files = corpus_files()
    pdfs = [p for p in files if p.lower().endswith((".pdf", *PG.IMAGE_SUFFIXES))]
    assert (
        index["width"] == PG.WIDTH == 1200
        and index["format"] == "webp"
        and index["quality"] == PG.QUALITY
    )
    assert [d["document_id"] for d in index["documents"]] == [
        identity(p)[0] for p in pdfs
    ]
    assert index["skipped"] == [
        os.path.relpath(p, CORPUS)
        for p in files
        if not p.lower().endswith((".pdf", *PG.IMAGE_SUFFIXES))
    ]
    # The eight drawings are images: a skipped entry may never end in an image suffix again.
    assert not any(e.lower().endswith(PG.IMAGE_SUFFIXES) for e in index["skipped"])
    assert all(PG.PATH_SAFE.fullmatch(d["document_id"]) for d in index["documents"])
    by_id = {identity(p)[0]: p for p in pdfs}
    for d in index["documents"]:
        assert d["source_sha256"] == file_sha256(by_id[d["document_id"]])
        source = by_id[d["document_id"]]
        expected_pages = (
            1 if source.lower().endswith(PG.IMAGE_SUFFIXES) else pdf_pages(source)
        )
        assert d["page_count"] == expected_pages >= 1


def test_every_render_is_1200_wide_metadata_free_and_hashed(pages_dir, index):
    for d in index["documents"]:
        folder = os.path.join(pages_dir, d["document_id"])
        sub = read_json(os.path.join(folder, "index.json"))
        assert (
            sub["document_id"],
            sub["source_sha256"],
            sub["page_count"],
            sub["width"],
        ) == (
            d["document_id"],
            d["source_sha256"],
            d["page_count"],
            1200,
        )
        assert [p["n"] for p in sub["pages"]] == list(range(1, d["page_count"] + 1))
        assert sorted(os.listdir(folder)) == sorted(
            [f"{p['n']}.webp" for p in sub["pages"]] + ["index.json"]
        )
        for p in sub["pages"]:
            with open(os.path.join(folder, f"{p['n']}.webp"), "rb") as f:
                data = f.read()
            PG.assert_metadata_free(data)
            assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            assert (
                hashlib.sha256(data).hexdigest() == p["sha256"]
                and len(data) == p["bytes"]
            )
            with Image.open(io.BytesIO(data)) as im:
                assert (
                    im.format == "WEBP"
                    and im.width == 1200
                    and im.height == p["height"]
                )
                assert not any(k in im.info for k in ("exif", "icc_profile", "xmp"))


def riff(*chunks):
    body = b"WEBP" + b"".join(
        tag
        + struct.pack("<I", len(payload))
        + payload
        + (b"\0" if len(payload) & 1 else b"")
        for tag, payload in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_metadata_walk_refuses_a_tagged_webp():
    PG.assert_metadata_free(riff((b"VP8L", b"\x2f\0\0\0\0")))
    for tag in (b"EXIF", b"XMP ", b"ICCP"):
        with pytest.raises(ValueError, match="metadata chunk"):
            PG.assert_metadata_free(riff((b"VP8X", b"\0" * 10), (tag, b"\0" * 6)))
    with pytest.raises(ValueError, match="not a WebP"):
        PG.assert_metadata_free(b"\x89PNG\r\n\x1a\n")
    img = Image.new("RGB", (8, 8), (255, 255, 255))
    for kw in (
        {"exif": b"Exif\0\0II*\0\x08\0\0\0\0\0\0\0"},
        {"icc_profile": b"\0" * 128},
        {"xmp": b"<x:xmpmeta/>"},
    ):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=PG.QUALITY, **kw)
        with pytest.raises(ValueError, match="metadata chunk"):
            PG.assert_metadata_free(buf.getvalue())
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=PG.QUALITY)
    PG.assert_metadata_free(buf.getvalue())
