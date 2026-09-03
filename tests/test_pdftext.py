from collections import Counter
import os
from harness import pdftext as P


def test_inventory_counts():
    files = P.corpus_files()
    assert len(files) == 98
    by_ext = Counter(os.path.splitext(f)[1] for f in files)
    assert by_ext == {".pdf": 88, ".png": 8, ".xlsx": 1, ".pptx": 1}
    assert sum(1 for f in files if os.path.basename(f).startswith("OPL-")) == 56
    cls = Counter(P.doc_class(f) for f in files)
    assert cls == {"opl": 56, "datasheet": 8, "ga_drawing": 8, "interlock": 8, "plot_plan": 8, "pid": 8, "workbook": 1, "organiser_note": 1}


def test_opl_ids_and_tags():
    t = P.opl_texts()
    assert len(t) == 56
    assert Counter(P.tag_of_opl(k) for k in t) == {tg: 7 for tg in ["GA-1201A", "YD-2301", "DC-3401A", "KC-4501", "EA-5601", "LV-6701", "CT-7801", "FA-8901"]}
    assert "Date of Sharing" in t["OPL-GA-1201A-04"] and "2026" in t["OPL-GA-1201A-04"]
    assert "  " not in t["OPL-YD-2301-01"]


def test_canonical():
    assert P.canonical("a­b  c\n\td ") == "ab c d"
    assert P.canonical("ﬁ") == "fi"


def test_corpus_digest_is_stable():
    files = P.corpus_files()
    assert P.corpus_sha256(files) == P.corpus_sha256(list(reversed(files)))
