# Deliverable contracts (blueprint 9.12, frozen)

Blueprint section 9.12, verbatim, laid out as a checklist. Every byte figure is measured with `wc -c` on the file as it will be uploaded. Deviations that touch this section, from the run's deviation log and policy at the moment they happened: D-07 (the live deployment is fully behind login and signed login-free reviewer links are not built; the export stays auth-free because it is static), D-08 (team facts), D-09 (narration not considered for now; silent audio with burned captions; human-gated in the Report). Each is marked where it lands.

## Byte budget

| Deliverable | File | Budget (bytes) |
| --- | --- | --- |
| Deck | `TheHub_deck.pdf` | 2,000,000 |
| Video | `TheHub_demo.mp4` | 5,000,000 |
| Export | `TheHub_prototype.html` | 2,000,000 |
| Pointer PDF (optional) | `TheHub_README.pdf` | 150,000 |
| Buffer | never spent | 850,000 |
| Ceiling | byte sum of the uploaded files | 10,000,000 |

## Export: `TheHub_prototype.html`

- [ ] one file, at most 2,000,000 bytes by wc -c
- [ ] opens from file:// with the network off
- [ ] embeds the JSON snapshot `{ corpus_version, packets, drafts, traces, register, evaluation_run, assets, coverage, fixtures_subset }`
- [ ] first screen = reviewer landing with the live URL and a signed link. D-07: the signed link is not built in this run; the landing carries the live URL and states that the live deployment is behind login
- [ ] every read-only surface reachable
- [ ] fonts subset or system fallback
- [ ] no external request at all (asserted by a headless run with all network blocked)

## Deck: `TheHub_deck.pdf`

- [ ] at most 2,000,000 bytes
- [ ] 7 pages before the first page whose footer reads APPENDIX
- [ ] slide order and headings verbatim from the booklet: Cover, Background & Problem Statement, Solution, Business Impact, Feasibility & Roadmap, Conclusion, Team Profile
- [ ] "KQ1", "KQ2", "KQ3" present
- [ ] no slide body over 120 words
- [ ] no raster figure
- [ ] every fixture-bearing number substituted by key
- [ ] every non-fixture number marked nonfx in the source
- [ ] the supervisor line and the team table with the mandated headings on page 7. D-08: the supervisor line reads "Faculty supervisor: as registered with the CALIBER 2026 Committee"; semester 3 for all three members; team string "3V"
- [ ] appendix A1 to A9 per the PRD's 26.1
- [ ] the three Key Question sentences of the PRD's 2.2 verbatim on appendix A1 with two-line compressions on slides 3 and 4 under the same labels

## Video: `TheHub_demo.mp4`

- [ ] at most 5,000,000 bytes
- [ ] duration at most 180 s by ffprobe, planned 175 s
- [ ] 1280x720, 15 fps, x264 two-pass, -tune stillimage, -b:v 190k -maxrate 260k -bufsize 520k
- [ ] AAC-LC mono 32 kbps (silence when no narration is supplied). D-09: silence in this run
- [ ] an embedded mov_text caption stream plus burned-in captions
- [ ] every model output shown is replayed from storage and the on-screen caption says so
- [ ] the narration script is the PRD's 26.2 text verbatim, held in the repository beside the captions

## Pointer PDF (optional): `TheHub_README.pdf`

- [ ] at most 150,000 bytes, one page

## Pre-submit

- [ ] `tools/presubmit.sh` exits non-zero on any of the 13 checks of the PRD's 26.4, run on the frozen bundle
- [ ] `deliverables/SHA256SUMS.txt` written with the commit and the time, read back and compared

### The 13 checks of the PRD's 26.4 (transcribed here for the checklist; the script is the authority)

1. The three mandatory deliverable files are present and each is the artefact its name claims; the optional pointer PDF is the only other file that may be uploaded; the checksum manifest of check 13 is a repository record beside them, never uploaded.
2. The byte sum is at most 10,000,000, measured with `wc -c` on the files as they will be uploaded.
3. The deck has at most seven pages before the first page whose footer reads APPENDIX.
4. "Background", "Solution", "Business Impact", "Feasibility", "Conclusion" and "Team Profile" appear in the deck text in that order, matched whole-word on first occurrence and compared by position.
5. "KQ1", "KQ2" and "KQ3" all appear in the deck text.
6. The Team Profile page carries a labelled supervisor line and the table on that page carries the headings No., Name, Major, Semester, Area of expertise and Contribution, in that order, checked by position on that page. D-08: redefined to "labelled supervisor line present" (no name), recorded as a compliance risk in the Report.
7. No placeholder marker (the `TBD_` prefix) survives in any deliverable.
8. The banned-strings list is clean across the deck text, the narration script and the export, the legacy product name included.
9. English only: no Indonesian stop word in the deck text or the captions, except inside a string marked as a quotation from the corpus.
10. Video duration is at most 180 seconds by ffprobe, and the caption track is present.
11. The export opens from file:// with the network disabled and all seven surfaces render, checked by a headless browser.
12. The live URL returns 200 from a clean network with no redirect to a login page, and every signed reviewer link resolves. D-07 conflicts with this check as written (the deployment is behind login and no reviewer link exists); the deviation log has not yet redefined it, see the open point returned with this file.
13. The SHA-256 of every submitted file is written to `deliverables/SHA256SUMS.txt` with the commit that produced the bundle and the time it was recorded, then read back and compared against the files themselves.

## Team facts (9.12 verbatim)

`supplied/team-facts.json` (read by the deck build; the `TBD_` prefix is the placeholder marker the pre-submit script greps for). Schema: `contracts/team_facts.schema.json`.

```json
{
  "team_name_registered": "3V",
  "university": "Politeknik Negeri Bandung",
  "case_title": "CALIBER 2026, Case 1: Manufacturing Knowledge Hub (AI-Powered Knowledge Integration)",
  "theme_line": "Future-Ready Operational Excellence: Knowledge, Reliability, and Smart Manufacturing",
  "supervisor": { "name": "TBD_SUPERVISOR_NAME", "title": "TBD_SUPERVISOR_TITLE" },
  "members": [
    { "no": 1, "name": "Ghaisan Khoirul Badruzaman", "role": "team lead", "major": "D4 Teknik Informatika (Sarjana Terapan), Jurusan Teknik Komputer dan Informatika", "semester": "TBD_SEMESTER", "area": "System architecture, data method, build orchestration", "contribution": "Product architecture, the harness and the frozen coverage method, the provider decision in ADR-001, the PRD, the deck and the video, correspondence with the Committee, final integration and the submission" },
    { "no": 2, "name": "Hafiz Fauzan Syafrudin", "role": "member", "major": "D4 Teknik Informatika (Sarjana Terapan), Jurusan Teknik Komputer dan Informatika", "semester": "TBD_SEMESTER", "area": "Data engineering and evaluation", "contribution": "Ingestion pipeline and versioned packages, extraction review, the golden set and the evaluation harness, coverage labelling, the drafting path and the two drafts the video shows" },
    { "no": 3, "name": "Elang Permadi Lau", "role": "member", "major": "D4 Teknik Informatika (Sarjana Terapan), Jurusan Teknik Komputer dan Informatika", "semester": "TBD_SEMESTER", "area": "Application engineering and delivery", "contribution": "The product surfaces and the guided loop route, deployment, availability and the nightly reset, the Evaluation page, the seeded demo data, the export and the screen capture" }
  ],
  "final_round_window": "TBD_FINAL_WINDOW",
  "registration_date": "TBD_REGISTRATION_DATE"
}
```

D-08 applied to this object: `semester` is `"3"` for all three members; `team_name_registered` stays `"3V"`; `supervisor.name` is withheld by owner decision and slide 7 carries the fixed line "Faculty supervisor: as registered with the CALIBER 2026 Committee" instead of a name; `final_round_window` and `registration_date` are dropped from the deliverable path (the fields stay in the frozen shape and are not rendered or grepped).
