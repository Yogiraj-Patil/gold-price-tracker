"""Read every store's history.csv, decide BUY NOW / OK / WAIT per store and metal, write verdict files.

Per store: <store dir>/verdict.json (gold at the top level, silver under "silver").
Overall:   data/summary.json (gold at the top level, silver under "silver"), with the cheapest store
           and one common verdict per metal.
All rates are Rs per GRAM.
"""
import csv
import json
import os
import statistics
from datetime import datetime, timedelta, timezone

import stores

INVEST = 10000          # Rs spent per purchase, gold
INVEST_SILVER = 5000    # Rs spent per purchase, silver
MIN_DAYS = 7
IST = timezone(timedelta(hours=5, minutes=30))
STALE_DAYS = 2   # a store whose latest reading is older than this is left out of the comparison


def daily_rates(csv_path, col="rate_22k"):
    """Last rate seen per calendar day -> sorted list of (date, rate). Rows without that rate are skipped."""
    by_day = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            raw = (r.get(col) or "").strip()
            if not raw:
                continue
            by_day[r["fetched_at"][:10]] = float(raw)
    return sorted(by_day.items())


def analyze(days, today=None, invest=INVEST, rate_key="rate_22k"):
    today = today or datetime.now(IST).date()

    def g(rate):
        return invest / rate

    dates = [d for d, _ in days]
    rates = [r for _, r in days]
    cur = rates[-1]
    out = {
        "as_of": dates[-1],
        rate_key: cur,
        "rate": cur,
        "grams_for_10k": round(g(cur), 4),
        "days_of_data": len(days),
        "invest": invest,
    }
    if len(days) < MIN_DAYS:
        out.update(verdict="COLLECTING DATA", reasons=[
            f"Only {len(days)} day(s) of history so far; need {MIN_DAYS} to compare.",
            f"Today: ₹{cur:,.0f}/g -> ₹{invest:,} buys {g(cur):.3f} g.",
        ])
        return out

    w30 = rates[-30:]
    avg, lo, hi = statistics.mean(w30), min(w30), max(w30)
    pct_vs_avg = (cur - avg) / avg * 100
    cheaper_days = sum(1 for r in w30 if r < cur)       # days that were cheaper
    rank = cheaper_days + 1                              # 1 = cheapest in window
    pctile = cheaper_days / len(w30) * 100               # lower = better
    yday = rates[-2]
    reasons = [
        f"Today ₹{cur:,.0f}/g -> ₹{invest:,} buys {g(cur):.3f} g "
        f"(30-day average buys {g(avg):.3f} g, best {g(lo):.3f} g, worst {g(hi):.3f} g).",
        f"Rate is {abs(pct_vs_avg):.1f}% {'below' if pct_vs_avg < 0 else 'above'} the "
        f"{len(w30)}-day average (₹{avg:,.0f}).",
        f"Cheapest-rank: {rank} of {len(w30)} days (1 = cheapest).",
    ]
    change = (cur - yday) / yday * 100
    if abs(change) >= 0.05:
        reasons.append(f"{'Up' if change > 0 else 'Down'} {abs(change):.2f}% vs previous day (₹{yday:,.0f}).")
    streak = 0
    for a, b in zip(reversed(rates[:-1]), reversed(rates[1:])):
        if (b > a) == (cur > yday) and b != a:
            streak += 1
        else:
            break
    if streak >= 2:
        reasons.append(f"Rate has {'risen' if cur > yday else 'fallen'} {streak} days in a row.")
    if len(rates) >= 60:
        w90 = rates[-90:]
        reasons.append(f"Vs {len(w90)}-day average: {(cur - statistics.mean(w90)) / statistics.mean(w90) * 100:+.1f}%.")

    if pctile <= 25 or pct_vs_avg <= -1.0:
        verdict = "BUY NOW"
        reasons.insert(0, "Today is one of the cheaper days of the last month.")
    elif pctile >= 75 or pct_vs_avg >= 1.0:
        verdict = "WAIT"
        reasons.insert(0, "Today is on the expensive side compared with the last month.")
    else:
        verdict = "OK"
        reasons.insert(0, "Today is a middle-of-the-road price: not cheap, not expensive.")

    days_left = (datetime(today.year + (today.month == 12), today.month % 12 + 1, 1).date() - today).days
    if verdict != "BUY NOW" and days_left <= 5:
        reasons.append(f"Only {days_left} day(s) left in the month - if you have not bought yet, "
                       "consider buying now rather than risking a higher rate.")
        if verdict == "OK":
            verdict = "BUY (month ending)"
    out.update(verdict=verdict, reasons=reasons, avg_30d=round(avg, 2),
               pct_vs_avg=round(pct_vs_avg, 2), rank_30d=rank, window=len(w30))
    return out


def analyze_store(store):
    """Write the store's own verdict.json (gold on top, silver under 'silver').
    Returns {'gold': (result, days), 'silver': (result, days) or None}, or None if the store has no history."""
    csv_path, out_path = stores.paths(store)
    if not os.path.exists(csv_path):
        print(f"[{store['key']}] no history yet; skipping.")
        return None
    days = daily_rates(csv_path, "rate_22k")
    if not days:
        print(f"[{store['key']}] no gold rates yet; skipping.")
        return None
    result = analyze(days)
    result["store"] = store["key"]
    result["store_label"] = store["label"]
    result["history"] = [{"date": d, "rate": r} for d, r in days[-120:]]
    found = {"gold": (result, days), "silver": None}

    s_days = daily_rates(csv_path, "rate_silver")
    if s_days:
        s_result = analyze(s_days, invest=INVEST_SILVER, rate_key="rate_silver")
        s_result["history"] = [{"date": d, "rate": r} for d, r in s_days[-120:]]
        result["silver"] = s_result
        found["silver"] = (s_result, s_days)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    silver_note = f", silver {result['silver']['verdict']}" if s_days else ", no silver rates yet"
    print(f"[{store['key']}] gold {result['verdict']}{silver_note}")
    for r in result["reasons"]:
        print(" -", r)
    return found


def build_summary(items, today=None, invest=INVEST, name="gold"):
    """items: list of (store, result, days). Compare stores and give one common verdict."""
    today = today or datetime.now(IST).date()
    rows = []
    for store, result, days in items:
        age = (today - datetime.strptime(days[-1][0], "%Y-%m-%d").date()).days
        rows.append({
            "key": store["key"], "label": store["label"], "note": store.get("note", ""),
            "rate": result["rate"], "grams_for_10k": result["grams_for_10k"],
            "as_of": result["as_of"], "stale": age > STALE_DAYS,
            "verdict": result["verdict"], "reasons": result["reasons"],
            "days_of_data": result["days_of_data"],
            "history": [{"date": d, "rate": r} for d, r in days[-120:]],
        })
    live = sorted((r for r in rows if not r["stale"]), key=lambda r: r["rate"])
    summary = {"generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"), "invest": invest,
               "metal": name, "stores": rows, "ranking": [r["key"] for r in live]}
    if not live:
        summary.update(verdict="NO DATA", best_store=None, reasons=[f"No store has a recent {name} rate."])
        return summary

    best = live[0]
    dp = 2 if name == "silver" else 0       # silver rates are small numbers, so show paise
    reasons = [f"Cheapest today: {best['label']} at ₹{best['rate']:,.{dp}f}/g -> "
               f"₹{invest:,} buys {best['grams_for_10k']:.3f} g."]
    for o in live[1:]:
        diff = o["rate"] - best["rate"]
        extra = best["grams_for_10k"] - o["grams_for_10k"]
        if diff:
            more = invest * diff / best["rate"]
            reasons.append(f"{o['label']} is ₹{diff:,.{dp}f}/g ({diff / best['rate'] * 100:.2f}%) dearer: the same "
                           f"₹{invest:,} of {name} costs ₹{more:,.0f} more there ({extra:.4f} g less for the same money).")
        else:
            reasons.append(f"{o['label']} has the same rate.")
    for r in rows:
        if r["stale"]:
            reasons.append(f"{r['label']} left out: last rate is from {r['as_of']} (stale).")

    # Timing verdict on the best price available across stores, using only days when every live
    # store had a reading, so a store joining later does not fake a price drop.
    per_store = {r["key"]: {h["date"]: h["rate"] for h in r["history"]} for r in live}
    common_dates = sorted(set.intersection(*(set(m) for m in per_store.values())))
    series = [(d, min(m[d] for m in per_store.values())) for d in common_dates]
    if len(series) >= MIN_DAYS:
        common = analyze(series, today, invest=invest)
        basis = f"best price across {len(live)} store(s), {len(series)} days of common history"
        summary.update(verdict=common["verdict"], timing_basis=basis)
        reasons.append(f"Timing is judged on the {basis}:")
        reasons += common["reasons"][:4]
    else:
        # Not enough history shared by every store yet: judge timing on the live store with the longest history.
        timing = best if best["days_of_data"] >= MIN_DAYS else max(live, key=lambda r: r["days_of_data"])
        summary.update(verdict=timing["verdict"],
                       timing_basis=f"{timing['label']}'s own price history ({timing['days_of_data']} days; "
                                    f"only {len(series)} day(s) are shared by all stores so far)")
        reasons.append(f"Timing is judged on {summary['timing_basis']}.")
        reasons += timing["reasons"][:4]
    summary.update(best_store=best["key"], best_label=best["label"], rate=best["rate"],
                   grams_for_10k=best["grams_for_10k"], reasons=reasons)
    return summary


def main():
    gold_items, silver_items = [], []
    for store in stores.STORES:
        found = analyze_store(store)
        if not found:
            continue
        gold_items.append((store, *found["gold"]))
        if found["silver"]:
            silver_items.append((store, *found["silver"]))
    if not gold_items:
        print("No store data; nothing to summarise.")
        return
    summary = build_summary(gold_items)
    summary["rate_22k"] = summary.get("rate")                  # kept for older consumers
    if silver_items:
        summary["silver"] = build_summary(silver_items, invest=INVEST_SILVER, name="silver")
    with open(stores.SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[overall gold] {summary['verdict']} - best: {summary.get('best_label')}")
    for r in summary["reasons"]:
        print(" -", r)
    if "silver" in summary:
        sv = summary["silver"]
        print(f"[overall silver] {sv['verdict']} - best: {sv.get('best_label')}")
        for r in sv["reasons"]:
            print(" -", r)


if __name__ == "__main__":
    main()
