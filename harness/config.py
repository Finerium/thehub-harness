"""Paths shared by the harness, the figure scripts and the tools. Nothing else may hard-code a path."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The corpus root is the "Case 1_ Manufacturing Knowledge Hub" directory of the organiser's supporting data: $CASE1_CORPUS,
# else the private thehub-corpus repository checked out beside this one (blueprint 8.3, ADR-010).
CORPUS = os.environ.get(
    "CASE1_CORPUS",
    os.path.join(
        os.path.dirname(ROOT),
        "thehub-corpus",
        "CALIBER-2026_The-Case",
        "Supporting Data",
        "Case 1_ Manufacturing Knowledge Hub",
    ),
)
PACKAGES = os.path.join(ROOT, "packages")
CACHE = os.environ.get("THEHUB_CACHE", os.path.join(ROOT, ".cache"))
FIGS = os.environ.get("THEHUB_FIGS", os.path.join(ROOT, "thehub", "figs"))
WORKBOOK = os.path.join(CORPUS, "Maintenance History (All Equipment).xlsx")
