"""Paths shared by the harness, the figure scripts and the tools. Nothing else may hard-code a path."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.environ.get(
    "CASE1_CORPUS",
    "/Users/ghaisan/Documents/ChandraAsri-Competition/CALIBER 2026 - The Case/Supporting Data/Case 1_ Manufacturing Knowledge Hub",
)
PACKAGES = os.path.join(ROOT, "packages")
CACHE = os.environ.get("THEHUB_CACHE", os.path.join(ROOT, ".cache"))
FIGS = os.environ.get("THEHUB_FIGS", os.path.join(ROOT, "thehub", "figs"))
WORKBOOK = os.path.join(CORPUS, "Maintenance History (All Equipment).xlsx")
