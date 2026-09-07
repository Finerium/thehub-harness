"""The pinned local embedding role (ADR-009 second branch: no hosted embedding API exists on the locked provider).

    uv run python -m harness.embed --pin                                  download the model files, write the pin
    uv run python -m harness.embed --chunks bundle/chunks.jsonl           add "embedding" to every chunk line
    uv run python -m harness.embed --cases contracts/fixtures/embedding_cases.json   write the expected query vectors

Model: Xenova/multilingual-e5-small, the quantized ONNX file, 384 dimensions, mean pooling over the attention mask,
L2 normalised, "passage: " before every chunk and "query: " before every query (the e5 convention). The three model
files are pinned by SHA-256 in packages/embedding_pin.json; loading hashes every file on disk against the pin (a file that
is absent is downloaded first; nothing else touches the network) and fails closed on a missing pin, a file that cannot
be fetched or a mismatch. The Node runtime loads the identical files (ADR-009), so the same text
gives the same vector on both sides; contracts/fixtures/embedding_cases.json is that equality, pinned.

Every text is embedded alone (batch of one, no padding) on one thread, so a vector never depends on what else was in the
batch or on the core count of the machine. Values are written with DECIMALS decimals, well inside float32 precision.
A chunk over MAX_TOKENS is an error, never truncated (AC-ING-13).
"""

import argparse
import json
import math
import os

import numpy as np

from .config import CACHE, PACKAGES
from .pdftext import file_sha256

MODEL = "Xenova/multilingual-e5-small"
FILES = ("onnx/model_quantized.onnx", "tokenizer.json", "tokenizer_config.json")
MODEL_DIR = os.path.join(CACHE, "models", MODEL.replace("/", "--"))
PIN_PATH = os.path.join(PACKAGES, "embedding_pin.json")
DIM, MAX_TOKENS, DECIMALS = 384, 512, 6
QUERY_PREFIX, PASSAGE_PREFIX = "query: ", "passage: "


def fetch(files=FILES):
    """The model files under MODEL_DIR, downloaded from the hub only when absent (delete the directory to re-pin from
    the hub); [{path, sha256, bytes}] in the given order."""
    out = []
    for f in files:
        p = os.path.join(MODEL_DIR, f)
        if not os.path.exists(p):
            from huggingface_hub import hf_hub_download

            p = hf_hub_download(MODEL, f, local_dir=MODEL_DIR)
        out.append({"path": f, "sha256": file_sha256(p), "bytes": os.path.getsize(p)})
    return out


def write_pin(path=PIN_PATH):
    pin = {
        "model": MODEL,
        "files": fetch(),
        "dim": DIM,
        "pooling": "mean",
        "normalize": True,
        "query_prefix": QUERY_PREFIX,
        "passage_prefix": PASSAGE_PREFIX,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pin, f, indent=1)
        f.write("\n")
    return pin


class Embedder:
    """The pinned model, verified against packages/embedding_pin.json at construction (fail closed)."""

    def __init__(self, pin_path=PIN_PATH):
        try:
            with open(pin_path, encoding="utf-8") as f:
                pin = json.load(f)
        except FileNotFoundError:
            raise SystemExit(
                f"no embedding pin at {pin_path}: run `python -m harness.embed --pin` first"
            ) from None
        if pin.get("model") != MODEL or pin.get("dim") != DIM:
            raise SystemExit(
                f"embedding pin names {pin.get('model')}/{pin.get('dim')}, this module is {MODEL}/{DIM}"
            )
        for want in pin["files"]:
            got = fetch([want["path"]])[0]
            if got["sha256"] != want["sha256"]:
                raise SystemExit(
                    f"embedding pin mismatch on {want['path']}: file {got['sha256'][:12]}, pin {want['sha256'][:12]}"
                )
        # onnxruntime ships no py.typed marker and publishes no stub package, so mypy cannot see its API.
        import onnxruntime as ort  # type: ignore[import-untyped]
        from tokenizers import Tokenizer

        self.tok = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
        self.tok.no_truncation()
        self.tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(
            os.path.join(MODEL_DIR, FILES[0]), so, providers=["CPUExecutionProvider"]
        )
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def embed(self, text, prefix):
        enc = self.tok.encode(prefix + text)
        if len(enc.ids) > MAX_TOKENS:
            raise ValueError(
                f"{len(enc.ids)} tokens exceed {MAX_TOKENS}: {text[:60]!r}"
            )
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
        }
        hidden = self.sess.run(
            None, {k: v for k, v in feeds.items() if k in self.inputs}
        )[0][0]
        mask = np.array(enc.attention_mask, dtype=np.float32)[:, None]
        v = (hidden.astype(np.float32) * mask).sum(0) / mask.sum()
        v = (v / np.linalg.norm(v)).astype(np.float32)
        if v.shape != (DIM,):
            raise ValueError(f"model returned {v.shape}, expected ({DIM},)")
        return [round(float(x), DECIMALS) for x in v]


def embed_chunks(path):
    """Rewrite a chunks.jsonl with an "embedding" per line (passage prefix); returns (count, max_tokens_seen)."""
    e = Embedder()
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    longest = 0
    for r in rows:
        longest = max(longest, len(e.tok.encode(PASSAGE_PREFIX + r["text"]).ids))
        r["embedding"] = e.embed(r["text"], PASSAGE_PREFIX)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return len(rows), longest


def embed_cases(path):
    """Write the expected query vector of every case string into the cases file; returns the cases."""
    e = Embedder()
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc.update(
        {"model": MODEL, "dim": DIM, "prefix": QUERY_PREFIX, "decimals": DECIMALS}
    )
    for c in doc["cases"]:
        c["expected"] = e.embed(c["text"], QUERY_PREFIX)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return doc["cases"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="the pinned local embedding role (ADR-009)"
    )
    ap.add_argument(
        "--pin",
        action="store_true",
        help="download the model files and write packages/embedding_pin.json",
    )
    ap.add_argument(
        "--chunks",
        metavar="JSONL",
        help="embed every chunk text (passage prefix) and rewrite the file",
    )
    ap.add_argument(
        "--cases",
        metavar="JSON",
        help="embed the case strings (query prefix) and write the expected vectors",
    )
    a = ap.parse_args(argv)
    if not (a.pin or a.chunks or a.cases):
        ap.error("nothing to do: pass --pin, --chunks or --cases")
    if a.pin:
        pin = write_pin()
        print(
            json.dumps(
                {
                    "pin": PIN_PATH,
                    "files": [
                        (f["path"], f["sha256"][:12], f["bytes"]) for f in pin["files"]
                    ],
                }
            )
        )
    if a.chunks:
        n, longest = embed_chunks(a.chunks)
        print(
            json.dumps(
                {"chunks": n, "dim": DIM, "max_tokens": longest, "limit": MAX_TOKENS}
            )
        )
    if a.cases:
        cases = embed_cases(a.cases)
        norm = math.sqrt(sum(x * x for x in cases[0]["expected"]))
        print(
            json.dumps({"cases": len(cases), "dim": DIM, "first_norm": round(norm, 6)})
        )


if __name__ == "__main__":
    main()
