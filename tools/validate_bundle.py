#!/usr/bin/env python3
"""Validate every file of a bundle directory against contracts/bundle_map.json (JSON Schema 2020-12), one line per
file; exits 1 on any INVALID, missing or unmapped file. `make contracts` runs it over bundle/ when that directory exists.

    uv run python tools/validate_bundle.py [bundle_dir]        (default: bundle)
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.validate import report, validate_bundle


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    bundle_dir = argv[0] if argv else os.path.join(ROOT, "bundle")
    if not os.path.isdir(bundle_dir):
        print(f"validate_bundle: no bundle directory at {bundle_dir}")
        return 1
    return 1 if report(validate_bundle(bundle_dir)) else 0


if __name__ == "__main__":
    sys.exit(main())
