"""The release artefact of the bundle: dist/thehub-bundle-<version>.tar.gz plus SHA256SUMS (blueprint 8.3).

    uv run python -m harness.release --bundle bundle --out dist

The archive carries manifest.json and every file it lists except the seed-time artefacts (chunks.jsonl, opls.json,
pages/, text/: corpus text and imagery, D-17), under the prefix thehub-bundle-<version>/, in sorted order with one
fixed mtime (SOURCE_DATE_EPOCH, else the manifest's created_at), uid and gid 0, no user names and a gzip stream without
a timestamp, so the same bundle gives the same bytes. SHA256SUMS lists the archive in `sha256sum` format. Uploading the
release is the main thread's job.
"""

import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import tarfile

SEED_TIME = ("chunks.jsonl", "opls.json", "pages/", "text/")


def members(bundle):
    with open(os.path.join(bundle, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    paths = ["manifest.json"] + [
        x["path"] for x in manifest["files"] if not x["path"].startswith(SEED_TIME)
    ]
    for p in paths:
        if not os.path.exists(os.path.join(bundle, p)):
            raise SystemExit(f"manifest lists {p} but the bundle does not carry it")
    return manifest, sorted(paths)


def build(bundle, out):
    manifest, paths = members(bundle)
    version = manifest["bundle_version"]
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    mtime = (
        int(epoch)
        if epoch
        else int(datetime.datetime.fromisoformat(manifest["created_at"]).timestamp())
    )
    name = f"thehub-bundle-{version}"
    os.makedirs(out, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in paths:
            p = os.path.join(bundle, rel)
            info = tar.gettarinfo(p, arcname=f"{name}/{rel}")
            info.mtime, info.uid, info.gid, info.uname, info.gname = mtime, 0, 0, "", ""
            info.mode = 0o644
            with open(p, "rb") as f:
                tar.addfile(info, f)
    archive = os.path.join(out, name + ".tar.gz")
    with (
        open(archive, "wb") as f,
        gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as gz,
    ):
        gz.write(raw.getvalue())
    with open(archive, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8") as f:
        f.write(f"{digest}  {name}.tar.gz\n")
    return {
        "archive": archive,
        "sha256": digest,
        "files": len(paths),
        "bytes": os.path.getsize(archive),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="release tarball of the bundle without its seed-time files (D-17)"
    )
    ap.add_argument("--bundle", default="bundle")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args(argv)
    print(json.dumps(build(a.bundle, a.out)))


if __name__ == "__main__":
    main()
