#!/usr/bin/env python3
"""AC-FND-03 helper: every *.schema.json under contracts/ is a valid JSON Schema 2020-12 document, every local $ref
resolves to an existing file and $def, and every $id is unique. Prints one line per file and exits non-zero on any failure."""

import json
import os
import re
import sys
from pathlib import Path

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(ROOT, "contracts")
REF = re.compile(r'"\$ref"\s*:\s*"([^"]+)"')


def walk_refs(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                out.append(v)
            else:
                walk_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_refs(v, out)


def main():
    files = sorted(
        os.path.join(d, f)
        for d, _, fs in os.walk(CDIR)
        for f in fs
        if f.endswith(".schema.json")
    )
    if not files:
        print("check_contracts: no schema files found under contracts/")
        return 1
    ids: dict[str | None, str] = {}
    bad = 0
    for path in files:
        rel = os.path.relpath(path, CDIR)
        try:
            schema = json.loads(Path(path).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
        except Exception as ex:  # noqa: BLE001
            print(f"INVALID  {rel}: {str(ex)[:160]}")
            bad += 1
            continue
        sid = schema.get("$id")
        if sid in ids:
            print(f"DUPLICATE $id  {rel} and {ids[sid]}: {sid}")
            bad += 1
        ids[sid] = rel
        refs: list[str] = []
        walk_refs(schema, refs)
        for r in refs:
            if r.startswith("#"):
                target_file, frag = schema, r[1:]
            else:
                fpart, _, frag = r.partition("#")
                tpath = os.path.normpath(os.path.join(os.path.dirname(path), fpart))
                if not os.path.exists(tpath):
                    print(f"DANGLING $ref  {rel}: {r} (file missing)")
                    bad += 1
                    continue
                target_file = json.loads(Path(tpath).read_text(encoding="utf-8"))
            if frag:
                node = target_file
                ok = True
                for seg in [s for s in frag.split("/") if s]:
                    if isinstance(node, dict) and seg in node:
                        node = node[seg]
                    else:
                        ok = False
                        break
                if not ok:
                    print(f"DANGLING $ref  {rel}: {r} (fragment missing)")
                    bad += 1
        defs = list((schema.get("$defs") or {}).keys())
        print(f"valid    {rel}  ({len(defs)} $defs, {len(refs)} $refs)")
    print(f"check_contracts: {len(files)} files, {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
