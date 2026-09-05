"""Validate the files of a bundle directory against contracts/bundle_map.json with JSON Schema 2020-12 (jsonschema).

One result per file: (path, status, message) where status is "valid", "INVALID", "missing", "absent" (optional or
seed-time file not present, or a file required from a later bundle_version) or "unmapped" (a file the map does not
know). Files under a seed-time prefix of the map (pages/) are reported as one line per prefix. Used by
tools/validate_bundle.py and by harness.g1; the application's G1 reads the same map.
"""

import json
import os

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .config import ROOT

MAP_PATH = os.path.join(ROOT, "contracts", "bundle_map.json")


def load_map(path=MAP_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def contracts(cdir):
    """{relative path: schema} for every *.schema.json under contracts/."""
    out = {}
    for d, _, fs in os.walk(cdir):
        for name in fs:
            if name.endswith(".schema.json"):
                p = os.path.join(d, name)
                with open(p, encoding="utf-8") as f:
                    out[os.path.relpath(p, cdir).replace(os.sep, "/")] = json.load(f)
    return out


def registry(schemas):
    return Registry().with_resources(
        (s["$id"], Resource.from_contents(s, default_specification=DRAFT202012))
        for s in schemas.values()
    )


def _ref(base_id, entry):
    if entry.get("pointer") is not None:
        return {"$ref": base_id + entry["pointer"]}
    return {"$ref": f"{base_id}#/$defs/{entry['def']}"}


def wrapper(entry, base_id):
    """The schema that validates one bundle file's parsed content."""
    if entry.get("properties"):
        props = {}
        for key, sub in entry["properties"].items():
            if sub.get("def") is None:
                props[key] = {"type": "array"}
            elif sub["root"] == "array":
                props[key] = {"type": "array", "items": _ref(base_id, sub)}
            else:
                props[key] = _ref(base_id, sub)
        return {
            "type": "object",
            "properties": props,
            "required": sorted(props),
            "additionalProperties": False,
        }
    if entry["root"] == "array":
        return {"type": "array", "items": _ref(base_id, entry)}
    return _ref(base_id, entry)


def _first_error(validator, instance):
    err = jsonschema.exceptions.best_match(validator.iter_errors(instance))
    if err is None:
        return None
    where = "/".join(str(p) for p in err.absolute_path) or "(root)"
    return f"{where}: {err.message[:200]}"


def validate_bundle(bundle_dir, map_path=MAP_PATH, cdir=None):
    m = load_map(map_path)
    cdir = cdir or os.path.dirname(os.path.abspath(map_path))
    schemas = contracts(cdir)
    reg = registry(schemas)
    present = set()
    for d, _, fs in os.walk(bundle_dir):
        for name in fs:
            present.add(
                os.path.relpath(os.path.join(d, name), bundle_dir).replace(os.sep, "/")
            )
    results = []
    for rel, entry in m["files"].items():
        path = os.path.join(bundle_dir, rel)
        if rel not in present:
            if (
                entry.get("optional")
                or entry.get("seed_time")
                or entry.get("required_from")
            ):
                results.append(
                    (
                        rel,
                        "absent",
                        "not present (optional, seed-time or required from a later bundle_version)",
                    )
                )
            else:
                results.append((rel, "missing", "required file not present"))
            continue
        present.discard(rel)
        try:
            results.append((rel, *_validate_one(path, entry, schemas, reg, cdir)))
        except Exception as ex:  # noqa: BLE001 (a parse failure is a validation failure)
            results.append((rel, "INVALID", f"{type(ex).__name__}: {str(ex)[:200]}"))
    for prefix in sorted(m.get("prefixes", {})):
        under = sorted(p for p in present if p.startswith(prefix))
        present.difference_update(under)
        if under:
            results.append(
                (
                    prefix,
                    "valid",
                    f"{len(under)} seed-time files (no schema, listed by the manifest)",
                )
            )
        else:
            results.append((prefix, "absent", "no seed-time file present"))
    for rel in sorted(present):
        results.append((rel, "unmapped", "file not in contracts/bundle_map.json"))
    return results


def _validate_one(path, entry, schemas, reg, cdir):
    fmt = entry["format"]
    if fmt in ("markdown", "text", "binary"):
        return (
            ("valid", f"{os.path.getsize(path)} bytes")
            if os.path.getsize(path)
            else ("INVALID", "empty file")
        )
    if fmt == "json_schema":
        with open(path, encoding="utf-8") as f:
            content = f.read()
        jsonschema.Draft202012Validator.check_schema(json.loads(content))
        with open(os.path.join(cdir, entry["schema"]), encoding="utf-8") as f:
            if f.read() != content:
                return ("INVALID", f"differs from contracts/{entry['schema']}")
        return ("valid", "JSON Schema 2020-12, byte copy of the contract")
    if entry.get("schema") is None:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        want = list if entry["root"] == "array" else dict
        return (
            ("valid", f"no section 9 type; JSON {entry['root']}")
            if isinstance(obj, want)
            else ("INVALID", f"root is not a JSON {entry['root']}")
        )
    base_id = schemas[entry["schema"]]["$id"]
    validator = jsonschema.Draft202012Validator(
        wrapper(entry, base_id), registry=reg, format_checker=jsonschema.FormatChecker()
    )
    if fmt == "jsonl":
        item = jsonschema.Draft202012Validator(_ref(base_id, entry), registry=reg)
        n = 0
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                err = _first_error(item, json.loads(line))
                if err:
                    return ("INVALID", f"line {n}: {err}")
        return ("valid", f"{n} lines of {entry['def']}")
    with open(path, encoding="utf-8") as f:
        obj = yaml.safe_load(f) if fmt == "yaml" else json.load(f)
    err = _first_error(validator, obj)
    if err:
        return ("INVALID", err)
    size = (
        len(obj)
        if isinstance(obj, list)
        else ", ".join(f"{k} {len(v)}" for k, v in obj.items() if isinstance(v, list))
        or "object"
    )
    return ("valid", f"{entry.get('def') or entry.get('pointer')}: {size}")


def report(results):
    width = max(len(r[0]) for r in results) if results else 10
    for rel, status, msg in results:
        print(f"{status:<8} {rel:<{width}}  {msg}")
    bad = [r for r in results if r[1] in ("INVALID", "missing", "unmapped")]
    print(f"validate_bundle: {len(results)} entries, {len(bad)} problem(s)")
    return len(bad)
