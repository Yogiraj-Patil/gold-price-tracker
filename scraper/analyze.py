"""Read data/history.csv, decide BUY NOW / OK / WAIT, write data/verdict.json."""
import csv
import json
import os
import statistics
from datetime import datetime, timedelta, timezone

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_PATH = os.path.join(BASE, "history.csv")
OUT_PATH = os.path.join(BASE, "verdict.json")
INVEST = 10000
MIN_DAYS = 7
IST = timezone(timedelta(hours=5, minutes=30))


def daily_rates():
    """Last rate seen per calendar day -> sorted list of (date, rate)."""
    by_day = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            day = r["fetched_at"][:10]
            by_day[day] = float(r["rate_22k"])
    return sorted(by_day.items())


def g(rate):
    return INVEST / rate


def analyze(days, today=None):
    today = today or datetime.now(IST).date()
    dates = [d for d, _ in days]
    rates = [r for _, r in days]
    cur = rates[-1]
    out = {
        "as_of": dates[-1],
        "rate_22k": cur,
        "grams_for_10k": round(g(cur), 4),
        "days_of_data": len(days),
        "invest": INVEST,
    }
    if len(days) < MIN_DAYS:
        out.update(verdict="COLLECTING DATA", reasons=[
            f"Only {len(days)} day(s) of history so far; need {MIN_DAYS} to compare.",
            f"Today: ₹{cur:,.0f}/g -> ₹{INVEST:,} buys {g(cur):.3f} g.",
        ])
        return out

    w30 = rates[-30:]
    prev = w30[:-1]
    avg, lo, hi = statistics.mean(w30), min(w30), max(w30)
    pct_vs_avg = (cur - avg) / avg * 100
    cheaper_days = sum(1 for r in w30 if r < cur)       # days that were cheaper
    rank = cheaper_days + 1                              # 1 = cheapest in window
    pctile = cheaper_days / len(w30) * 100               # lower = better
    yday = rates[-2]
    reasons = [
        f"Today ₹{cur:,.0f}/g -> ₹{INVEST:,} buys {g(cur):.3f} g "
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


def main():
    days = daily_rates()
    result = analyze(days)
    result["history"] = [{"date": d, "rate": r} for d, r in days[-120:]]
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(result["verdict"])
    for r in result["reasons"]:
        print(" -", r)


if __name__ == "__main__":
    main()
