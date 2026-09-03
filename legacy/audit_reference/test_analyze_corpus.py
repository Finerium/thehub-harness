"""Fixture tests for the corpus harness. Run: python3 -m pytest -q test_analyze_corpus.py  (or python3 test_analyze_corpus.py)
Reads out.json produced by `python3 analyze_corpus.py --corpus <root> --out out.json --fast`."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = json.load(open(os.path.join(HERE, os.environ.get('HARNESS_OUT', 'out.json'))))

def test_inventory():
    assert OUT['inventory']['files'] == 98 and OUT['inventory']['opl_pdfs'] == 56
    assert OUT['inventory']['by_ext'] == {'.pdf': 88, '.png': 8, '.pptx': 1, '.xlsx': 1}

def test_workbook():
    w = OUT['workbook']
    assert (w['rows'], w['columns'], w['breakdowns']) == (211, 31, 31)
    assert w['bd_downtime_h'] == 434.0 and w['bd_cost_idr'] == 413_345_000 and w['all_cost_idr'] == 537_770_000
    assert w['labour_h'] == 520.5 and w['incomplete'] == 26
    assert w['incomplete_by_type'] == {'Corrective': 20, 'Overhaul': 3, 'Preventive': 2, 'Calibration': 1}
    assert w['lead_h']['median'] == 34.0 and w['lead_h']['ge24_pct'] == 64.5

def test_equipment_master():
    m = OUT['equipment_master']
    assert {t: (d['wo'], d['bd'], d['bd_h']) for t, d in m.items()} == {
        'CT-7801': (27, 3, 46.0), 'DC-3401A': (27, 5, 60.0), 'EA-5601': (25, 6, 124.0), 'FA-8901': (25, 5, 70.0),
        'GA-1201A': (26, 1, 6.5), 'KC-4501': (27, 2, 38.0), 'LV-6701': (26, 4, 21.0), 'YD-2301': (28, 5, 68.5)}
    assert sum(d['bd_cost'] for d in m.values()) == 413_345_000

def test_dates_and_latency():
    d = OUT['opl_dates']
    assert d['dated'] == 52 and d['undated'] == ['OPL-DC-3401A-05', 'OPL-GA-1201A-04', 'OPL-GA-1201A-07', 'OPL-YD-2301-06']
    assert (d['min'], d['max'], d['span_d'], d['gap_after_last_breakdown_d'], d['interval_median_d']) == ('2026-03-22', '2026-07-01', 101, 114, 2)
    assert sorted(p['chosen'][2] for p in OUT['latency']['pairs']) == [210, 220, 442, 503, 577, 730] and OUT['latency']['median_d'] == 472.5

def test_verbatim_and_xref():
    assert OUT['verbatim_corrective_action']['count'] == 18
    x = OUT['xref']
    assert x['robust_wrong_per_set'] == {'DC-3401A': 7, 'EA-5601': 7, 'KC-4501': 7, 'LV-6701': 7} and x['robust_wrong_total'] == 28
    assert x['no_footer'] == ['OPL-GA-1201A-01', 'OPL-GA-1201A-02', 'OPL-GA-1201A-03', 'OPL-GA-1201A-05', 'OPL-GA-1201A-06']
    assert x['both_right_and_wrong'] == ['OPL-DC-3401A-01', 'OPL-DC-3401A-04']

def test_coverage_shipped_reproduces_prd_headline_but_not_band():
    c = OUT['coverage']['shipped_L+step']
    assert c['0.62']['unc_breakdowns'] == 13 and c['0.62']['unc_bd_h'] == 238.5 and c['0.62']['unc_bd_idr'] == 178_870_000
    assert 158 <= c['0.62']['uncovered'] <= 160  # order-dependent, see HN findings

if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'): f(); print('ok', n)
