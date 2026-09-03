#!/usr/bin/env bash
# Plan Task 4.6: machine-checkable pre-submit gate for the three deliverables in deliverables/.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; D="$ROOT/deliverables"; fail=0
say(){ printf '%s\n' "$*"; }
chk(){ if eval "$2"; then say "PASS $1"; else say "FAIL $1"; fail=1; fi; }
DECK="$D/TheHub_deck.pdf"; VIDEO="$D/TheHub_demo.mp4"; EXPORT="$D/TheHub_prototype.html"
chk "three deliverable files present" '[ -f "$DECK" ] && [ -f "$VIDEO" ] && [ -f "$EXPORT" ]'
if [ -f "$DECK" ] && [ -f "$VIDEO" ] && [ -f "$EXPORT" ]; then
  sz(){ wc -c < "$1" | tr -d ' '; }   # portable: stat -f%z is BSD-only and stat -c%s is GNU-only
  total=$(( $(sz "$DECK") + $(sz "$VIDEO") + $(sz "$EXPORT") ))
  chk "byte sum <= 10,000,000 (got $total)" '[ "$total" -le 10000000 ]'
  txt=$(pdftotext -raw "$DECK" - 2>/dev/null)
  chk "deck: <= 7 pages before APPENDIX" 'python3 - "$DECK" <<EOF
import sys,subprocess,re
t=subprocess.run(["pdftotext","-raw",sys.argv[1],"-"],capture_output=True,text=True).stdout.split("\f")
n=next((i for i,p in enumerate(t) if "APPENDIX" in p.upper()), len(t))
sys.exit(0 if n<=7 else 1)
EOF'
  for s in "KQ1" "KQ2" "KQ3" "Case 1"; do
    chk "deck contains '$s'" 'printf "%s" "$txt" | grep -q -- "$s"'
  done
  # Item 4: the six mandated headings must appear IN THE BOOKLET'S ORDER. A presence loop passes on any order and
  # "Solution" matches trivially inside other words, so both are checked here: whole-word, first occurrence, ascending.
  chk "deck: the six mandated headings appear in order" 'python3 - "$DECK" <<EOF
import re,subprocess,sys
t=subprocess.run(["pdftotext","-raw",sys.argv[1],"-"],capture_output=True,text=True).stdout
want=["Background","Solution","Business Impact","Feasibility","Conclusion","Team Profile"]
at=[]
for w in want:
    m=re.search(r"(?<![A-Za-z])"+re.escape(w)+r"(?![A-Za-z])",t)
    if not m: print("missing heading:",w); sys.exit(1)
    at.append(m.start())
if at!=sorted(at): print("headings out of order:",list(zip(want,at))); sys.exit(1)
sys.exit(0)
EOF'
  # Item 6: slide 7 carries the supervisor name and the six mandated column headings, in order, on that page.
  chk "deck: slide 7 supervisor name and the six table headings in order" 'python3 - "$DECK" <<EOF
import re,subprocess,sys
t=subprocess.run(["pdftotext","-raw",sys.argv[1],"-"],capture_output=True,text=True).stdout.split("\f")
pg=next((p for p in t if "Team Profile" in p), None)
if pg is None: print("no Team Profile page"); sys.exit(1)
if not re.search(r"Supervisor\s*[:\-]", pg): print("no supervisor line on slide 7"); sys.exit(1)
if re.search(r"Supervisor\s*[:\-]\s*(\[TBD\])?\s*\$", pg, re.M): print("supervisor name is empty or [TBD]"); sys.exit(1)
want=["No.","Name","Major","Semester","Area of expertise","Contribution"]
at=[]
for w in want:
    i=pg.find(w)
    if i<0: print("missing column heading:",w); sys.exit(1)
    at.append(i)
if at!=sorted(at): print("column headings out of order:",list(zip(want,at))); sys.exit(1)
sys.exit(0)
EOF'
  chk "deck: no SIMPUL / [TBD]" '! printf "%s" "$txt" | grep -q -E "SIMPUL|\[TBD\]"'
  chk "video <= 180 s" 'dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO" 2>/dev/null); python3 -c "import sys; sys.exit(0 if float(sys.argv[1])<=180 else 1)" "${dur:-999}"'
  chk "export: no password, no SIMPUL, no [TBD]" '! grep -q -E -i "password|SIMPUL|\[TBD\]" "$EXPORT"'
  chk "banned strings absent from deliverables" 'python3 "$ROOT/tools/banned_strings.py" --deliverables "$EXPORT" >/dev/null'
fi
# CSK-01: the committed tree must rebuild and verify its own fixture. A commit that ships a fixture its own harness
# cannot reproduce fails here rather than being found by a reader.
if git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
  tmp=$(mktemp -d)
  chk "HEAD rebuilds its own fixture and passes its own tests" '
    git -C "$ROOT" archive HEAD | tar -x -C "$tmp" &&
    cp "$tmp/packages/fixtures.json" "$tmp/committed.json" &&
    make -C "$tmp" fixtures >/dev/null 2>&1 &&
    cmp -s "$tmp/committed.json" "$tmp/packages/fixtures.json" &&
    make -C "$tmp" test >/dev/null 2>&1'
  rm -rf "$tmp"
fi
# Item 13: the SHA-256 of every submitted file is recorded beside the run that produced it, so the bundle a judge
# downloads can be matched to the commit that built it. Written first, then checked, so the check is of a real file.
if [ -f "$DECK" ] && [ -f "$VIDEO" ] && [ -f "$EXPORT" ]; then
  MAN="$D/SHA256SUMS.txt"
  { echo "# The Hub, CALIBER 2026 Case 1 - submitted bundle"
    echo "# commit: $(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "# recorded: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    shasum -a 256 "$DECK" "$VIDEO" "$EXPORT" | sed "s#$D/##"
  } > "$MAN"
  chk "SHA-256 of each submitted file recorded in deliverables/SHA256SUMS.txt" '
    [ -s "$MAN" ] &&
    for f in "$DECK" "$VIDEO" "$EXPORT"; do
      grep -q "$(shasum -a 256 "$f" | cut -d" " -f1)" "$MAN" || exit 1
    done'
fi
say "presubmit: $([ $fail -eq 0 ] && echo GREEN || echo RED)"; exit $fail
