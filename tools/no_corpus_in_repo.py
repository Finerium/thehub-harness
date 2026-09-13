#!/usr/bin/env python3
"""Addendum A7: no text file in the working tree may contain a run of >= 200 canonical characters that also occurs in the
corpus text (the organiser's documents are not redistributed).

Enumerates `git ls-files` PLUS `git ls-files --others --exclude-standard`, because what gets committed is the working
tree: with tracked files alone the gate skipped packages/, golden/ and rulepack/ entirely and printed a green "0 file(s)"
without ever opening fixtures.json (CS-02). packages/text|claims|chunks are git-ignored and stay excluded.
The window slides one character at a time: at a step of 40 a corpus run of 200 to 239 characters could start between two
window starts and be missed.

The window and the publishable-span cap are one interlock, and the interlock is checked here rather than assumed. Every
span the harness publishes is cut at harness.documents.CITATION_MAX_CHARS, so the only thing that keeps a legal citation
out of this report is that the cap sits below the window; and the only thing that lets this scan fire on the tracked
files it exists to guard (bundle/claims.json in the application repository, 1,546 claims whose longest string is exactly
the cap) is that same ordering. Today the margin is a single character, which is a working interlock and nowhere stated,
so a run that finds nothing prints the margin it found nothing by, and a cap raised to the window or above is reported
at its cause instead of as a thousand findings.

Usable from any repository: `--repo PATH` enumerates that repository's working tree (tracked plus untracked, unignored
files, listed from that root) and resolves every path against it; `--corpus PATH` names the corpus root and defaults to
$CASE1_CORPUS. The harness modules are imported after the options are read because harness.config binds the corpus
path at import time."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEXT_EXT = {
    ".md",
    ".html",
    ".py",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".sh",
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".csv",
    ".sql",
}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
WIN, PROBE = 200, 40


def corpus_text(P, W):
    parts = [
        P.canonical(P.pdf_text(p))
        for p in P.corpus_files()
        if p.lower().endswith(".pdf")
    ]
    parts += [
        P.canonical(" ".join(str(v) for v in w.values() if isinstance(v, str)))
        for w in W.load()
    ]
    return "\n".join(parts)


def repo_files(repo):
    """Tracked plus untracked-unignored regular files of `repo`, relative to it; NUL-separated so spaces survive."""

    def ls(*args):
        out = subprocess.run(
            ["git", "-C", repo, "ls-files", "-z", *args],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout
        return [f for f in out.split("\0") if f]

    return sorted(
        f
        for f in set(ls()) | set(ls("--others", "--exclude-standard"))
        if os.path.isfile(os.path.join(repo, f))
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--repo", default=ROOT, help="repository root to scan (default: this harness)"
    )
    ap.add_argument(
        "--corpus",
        default=os.environ.get("CASE1_CORPUS"),
        help="Case 1 corpus root (default: $CASE1_CORPUS)",
    )
    a = ap.parse_args(argv)
    if a.corpus:
        os.environ["CASE1_CORPUS"] = a.corpus
    from harness import pdftext as P
    from harness import workbook as W
    from harness.config import CORPUS
    from harness.documents import CITATION_MAX_CHARS

    if not os.path.isdir(CORPUS):
        ap.error(
            f"corpus root not found: {CORPUS} (pass --corpus PATH or set CASE1_CORPUS)"
        )
    repo = os.path.abspath(a.repo)
    try:
        files = repo_files(repo)
    except subprocess.CalledProcessError:
        ap.error(f"not a git repository: {repo}")
    corpus = corpus_text(P, W)
    # The interlock, before any scanning: a published span may not reach the window this scan looks for.
    cap_ok = CITATION_MAX_CHARS < WIN
    bad = []
    # A7 also covers pictures of the corpus, which the text scan cannot see. Every figure this package draws goes through
    # fig_helpers.save(), which always writes the PNG and a .pdf twin; a rasterised corpus page (pdftoppm) has no twin.
    # So an image with no sibling .pdf is not a figure we drew. Gitignored exhibits never reach this list and stay legal.
    exhibits = [
        f
        for f in files
        if os.path.splitext(f)[1].lower() in IMG_EXT
        and not os.path.exists(os.path.join(repo, os.path.splitext(f)[0] + ".pdf"))
    ]
    for f in files:
        if os.path.splitext(f)[1] not in TEXT_EXT or f.startswith("docs/audit/"):
            continue
        t = P.canonical(Path(repo, f).read_text(encoding="utf-8", errors="replace"))
        for i in range(0, max(1, len(t) - PROBE + 1), PROBE):
            # Every 200-character window contains a whole PROBE-aligned 40-character probe, so a probe that is not in the
            # corpus rules out every window covering it. Exact, and 40x fewer full-length searches.
            if t[i : i + PROBE] not in corpus:
                continue
            for j in range(max(0, i - WIN + PROBE), min(i, len(t) - WIN) + 1):
                w = t[j : j + WIN]
                if len(w) == WIN and w in corpus:
                    bad.append((f, j, w[:80]))
                    break
            if bad and bad[-1][0] == f:
                break
    for f, i, w in bad:
        print(f"CORPUS-TEXT {f} @ {i}: '{w}...'")
    for f in exhibits:
        print(
            f"CORPUS-IMAGE {f}: image with no .pdf twin, so not drawn by fig_helpers.save(); "
            f"if this is a rasterised corpus page it must not be published (A7) -- git rm --cached it and gitignore it"
        )
    if not cap_ok:
        print(
            f"CITATION-CAP harness.documents.CITATION_MAX_CHARS is {CITATION_MAX_CHARS}, at or above this scan's "
            f"{WIN}-character window: every published span now reaches the window, so the scan can no longer tell a "
            f"legal citation from redistributed corpus text. Lower the cap below {WIN} or raise the window"
        )
    print(
        f"no_corpus_in_repo: {len(bad)} file(s) with >= {WIN} chars of corpus text, "
        f"{len(exhibits)} un-drawn image(s) in the publishable tree of {repo}; "
        f"published spans are cut at {CITATION_MAX_CHARS} chars, "
        f"{WIN - CITATION_MAX_CHARS} under the window"
    )
    return 1 if (bad or exhibits or not cap_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
