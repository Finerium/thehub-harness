"""Knowledge-debt ranking of the eight assets (Revision Plan 5.7 item 9; closes CR-11).

debt_e = 0.4 * D_e / D_max + 0.3 * C_e / C_max + 0.2 * k_e + 0.1 * r_e over the generous-uncovered (score <= t)
unplanned-failure work orders of asset e:
  D_e = unplanned-breakdown downtime hours of those rows (breakdown_kind == unplanned);
  C_e = their recorded Total_Cost_IDR; a row with an incomplete closeout (the eleven outcome fields empty) contributes 0
        to C and 1 to the asset's `incomplete_uncovered` flag count (the plan's "recurrence flag"), and stays an event of r;
  k_e = 1.0 / 0.5 / 0.25 for HIGH / LOW / NON CRITICAL from the datasheet (equipment_master.criticality_datasheet);
  r_e = share of the asset's unplanned-failure rows that belong to any failure family (families.r_by_tag, CR-20);
  D_max, C_max = fleet maxima over the eight assets; a zero maximum makes that term 0.
The coefficients are a product decision (ASSUMPTION), not a measured quantity; they are printed with that label.
Pure function of its inputs: assets sorted by tag, ids sorted, ties in the ranking broken by tag.
"""

COEFFICIENTS = {"D": 0.4, "C": 0.3, "k": 0.2, "r": 0.1}
COEFFICIENTS_BASIS = "product decision, ASSUMPTION"
K_MAPPING = {"HIGH CRITICAL": 1.0, "LOW CRITICAL": 0.5, "NON CRITICAL": 0.25}


def rank(rows, uncovered_ids, criticality_by_tag, r_by_tag):
    """per_asset (sorted by tag) and ranking (score desc, tag asc) for the formula in the module docstring (CR-11).

    rows: workbook rows; uncovered_ids: generous-uncovered unplanned-failure work orders; criticality_by_tag: datasheet
    criticality per tag (every asset must be present, uncovered or not); r_by_tag: families r per tag.
    """
    by_wo = {w["WO_Number"]: w for w in rows}
    per = []
    for tag in sorted(criticality_by_tag):
        mine = [
            by_wo[i] for i in sorted(uncovered_ids) if by_wo[i]["Equipment_Tag"] == tag
        ]
        per.append(
            {
                "tag": tag,
                "uncovered_ids": [w["WO_Number"] for w in mine],
                "D": sum(
                    (
                        w["Downtime_Hours"] or 0.0
                        for w in mine
                        if w["breakdown_kind"] == "unplanned"
                    ),
                    0.0,
                ),
                "C": sum(
                    w["Total_Cost_IDR"] or 0 for w in mine if w["closeout_complete"]
                ),
                "k": K_MAPPING[criticality_by_tag[tag]],
                "r": r_by_tag[tag],
                "incomplete_uncovered": sum(
                    1 for w in mine if not w["closeout_complete"]
                ),
            }
        )
    d_max = max(p["D"] for p in per)
    c_max = max(p["C"] for p in per)
    for p in per:
        p["score"] = round(
            COEFFICIENTS["D"] * (p["D"] / d_max if d_max else 0.0)
            + COEFFICIENTS["C"] * (p["C"] / c_max if c_max else 0.0)
            + COEFFICIENTS["k"] * p["k"]
            + COEFFICIENTS["r"] * p["r"],
            4,
        )
    order = sorted(per, key=lambda p: (-p["score"], p["tag"]))
    return {
        "coefficients": dict(COEFFICIENTS, basis=COEFFICIENTS_BASIS),
        "k_mapping": dict(K_MAPPING),
        "D_max": d_max,
        "C_max": c_max,
        "per_asset": per,
        "ranking": [
            {"rank": i + 1, "tag": p["tag"], "score": p["score"]}
            for i, p in enumerate(order)
        ],
    }


def compute(ctx):
    """Fixture key `debt` (CR-11). Besides rows/pops/opl/parsed/files, ctx carries the upstream fixture parts the formula
    reads: `coverage` (harness.coverage), `equipment_master` and `families` (harness.master) and `t` (default 0.62)."""
    t = ctx.get("t", 0.62)
    row = next(
        r for r in ctx["coverage"]["generous"]["unplanned_failure"] if r["t"] == t
    )
    crit = {e["tag"]: e["criticality_datasheet"] for e in ctx["equipment_master"]}
    r_by_tag = {tag: v["r"] for tag, v in ctx["families"]["r_by_tag"].items()}
    out = rank(ctx["rows"], row["uncovered_ids"], crit, r_by_tag)
    out["population"] = "generous-uncovered unplanned-failure work orders"
    out["t"] = t
    return out
