"""Cross-checked on 2026-08-27 against a metadata table built independently of this parser, and re-confirmed under the
single pinned extractor (D10): 56 dates, 28 foreign footers (all of DC/KC/EA/LV), 5 GA-1201A lessons without a cross-ref
line, classification 24/20/12, approvers EMP-0901 x28 / EMP-0912 x28, reviewers = the three workbook approvers."""
from collections import Counter
from harness import opl as O

D = O.parse_all()


def test_all_headers_and_dates():
    assert len(D) == 56
    assert all(v["date_of_sharing"] for v in D.values())
    assert min(v["date_of_sharing"] for v in D.values()) == "2026-03-22"
    assert max(v["date_of_sharing"] for v in D.values()) == "2026-07-01"
    assert D["OPL-GA-1201A-04"]["date_of_sharing"] == "2026-04-03"   # wrapped over two lines in the PDF (CF-03)
    assert D["OPL-DC-3401A-05"]["date_of_sharing"] == "2026-04-29"
    assert Counter(v["classification"] for v in D.values()) == {"Basic Knowledge": 24, "Improvement": 20, "Trouble Case": 12}


def test_interlock_and_pid_refs():
    assert D["OPL-YD-2301-01"]["seq"] == "SEQ-5500" and D["OPL-YD-2301-01"]["pid_ref"] == "TJC-LLD-PID-2301"
    assert all(v["seq"] is None for k, v in D.items() if k.startswith("OPL-EA-5601"))
    assert D["OPL-EA-5601-01"]["related_interlock"].startswith("N/A")


def test_crossref_lines():
    foreign = {k for k, v in D.items() if v["foreign_crossref_tags"]}
    assert len(foreign) == 28
    assert all(k.split("-")[1] + "-" + k.split("-")[2] in ("DC-3401A", "KC-4501", "EA-5601", "LV-6701") for k in foreign)
    missing = sorted(k for k, v in D.items() if not v["has_crossref_line"])
    assert missing == ["OPL-GA-1201A-01", "OPL-GA-1201A-02", "OPL-GA-1201A-03", "OPL-GA-1201A-05", "OPL-GA-1201A-06"]


def test_people():
    assert Counter(v["approved_by_id"] for v in D.values()) == {"EMP-0901": 28, "EMP-0912": 28}
    assert set(v["reviewed_by_id"] for v in D.values()) == {"EMP-1113", "EMP-1124", "EMP-1102"}
    assert all(v["prepared_by_role"] for v in D.values())
    assert D["OPL-GA-1201A-04"]["approved_by"] == "Arya Wibisono"   # CF-V-02: split footer parses in raw mode


def test_sections_and_strict():
    """OPL-DC-3401A-07 is the lesson that broke the old stripped strict layer: its raw text repeats two troubleshooting cells
    after the 'Prepared by' footer, so `strip_troubleshooting` left them in. `strict_text` composes sections 1, 2, 3, 4 and 6
    instead, so neither the section nor its stray copies can reach the strict layer."""
    v = D["OPL-DC-3401A-07"]
    assert "Scheduled statutory PSV pop test" in v["troubleshooting_text"]
    assert v["safety_text"] and v["tools_text"] and "Re-instate PSV-3401" in v["steps_text"]
    assert v["hazard_note"].startswith("HIGH CRITICAL")
    full = O.opl_texts()["OPL-DC-3401A-07"]
    assert "Spiral-wound gasket unevenly seated" in O.strip_troubleshooting(full)   # the leak the stripper cannot close
    s = O.strict_text(v)
    assert "Spiral-wound gasket unevenly seated" not in s and "Prepared by" not in s
    assert v["purpose"] in s and v["key_learning"] in s and v["troubleshooting_text"] not in s
