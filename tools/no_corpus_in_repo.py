#!/usr/bin/env python3
"""Addendum A7: no text file in the working tree may contain a run of >= 200 canonical characters that also occurs in the
corpus text (the organiser's documents are not redistributed).

Enumerates `git ls-files` PLUS `git ls-files --others --exclude-standard`, because what gets committed is the working
tree: with tracked files alone the gate skipped packages/, golden/ and rulepack/ entirely and printed a green "0 file(s)"
without ever opening fixtures.json (CS-02). packages/text|claims|chunks are git-ignored and stay excluded.
The window slides one character at a time: at a step of 40 a corpus run of 200 to 239 characters could start between two
window starts and be missed."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness import pdftext as P  # noqa: E402
from harness import workbook as W  # noqa: E402

TEXT_EXT = {".md", ".html", ".py", ".txt", ".json", ".yaml", ".yml", ".sh", ".js", ".ts", ".tsx", ".css", ".csv"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
WIN, PROBE = 200, 40


def corpus_text():
    parts = [P.canonical(P.pdf_text(p)) for p in P.corpus_files() if p.lower().endswith(".pdf")]
    parts += [P.canonical(" ".join(str(v) for v in w.values() if isinstance(v, str))) for w in W.load()]
    return "\n".join(parts)


def main():
    corpus = corpus_text()
    def ls(*args):
        return subprocess.run(["git", "ls-files", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()

    files = sorted(set(ls()) | set(ls("--others", "--exclude-standard")))
    bad = []
    # A7 also covers pictures of the corpus, which the text scan cannot see. Every figure this package draws goes through
    # fig_helpers.save(), which always writes the PNG and a .pdf twin; a rasterised corpus page (pdftoppm) has no twin.
    # So an image with no sibling .pdf is not a figure we drew. Gitignored exhibits never reach this list and stay legal.
    exhibits = [f for f in files
                if os.path.splitext(f)[1].lower() in IMG_EXT
                and not os.path.exists(os.path.join(ROOT, os.path.splitext(f)[0] + ".pdf"))]
    for f in files:
        if os.path.splitext(f)[1] not in TEXT_EXT or f.startswith("docs/audit/"):
            continue
        t = P.canonical(open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read())
        for i in range(0, max(1, len(t) - PROBE + 1), PROBE):
            # Every 200-character window contains a whole PROBE-aligned 40-character probe, so a probe that is not in the
            # corpus rules out every window covering it. Exact, and 40x fewer full-length searches.
            if t[i: i + PROBE] not in corpus:
                continue
            for j in range(max(0, i - WIN + PROBE), min(i, len(t) - WIN) + 1):
                w = t[j: j + WIN]
                if len(w) == WIN and w in corpus:
                    bad.append((f, j, w[:80]))
                    break
            if bad and bad[-1][0] == f:
                break
    for f, i, w in bad:
        print(f"CORPUS-TEXT {f} @ {i}: '{w}...'")
    for f in exhibits:
        print(f"CORPUS-IMAGE {f}: image with no .pdf twin, so not drawn by fig_helpers.save(); "
              f"if this is a rasterised corpus page it must not be published (A7) -- git rm --cached it and gitignore it")
    print(f"no_corpus_in_repo: {len(bad)} file(s) with >= {WIN} chars of corpus text, "
          f"{len(exhibits)} un-drawn image(s) in the publishable tree")
    return 1 if (bad or exhibits) else 0


if __name__ == "__main__":
    sys.exit(main())
