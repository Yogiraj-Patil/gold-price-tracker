"""Fetch Chandukaka Saraf gold rate and append to data/history.csv.

Order of attempts:
  1. plain HTTP request (fast)
  2. headless Chromium via Playwright (works if Cloudflare only checks the browser)
  3. MANUAL_RATE_22K / MANUAL_RATE_24K env vars (workflow_dispatch inputs)
Exits non-zero if nothing works, so GitHub emails you about the failed run.
"""
import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone

URL = "https://chandukakasaraf.in/todays-gold-rate/"
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.csv")
FIELDS = ["site_updated", "fetched_at", "rate_22k", "rate_24k", "grams_for_10k"]
IST = timezone(timedelta(hours=5, minutes=30))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
}


def parse(text):
    """Parse rates from page text (HTML or visible text)."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    r22 = re.search(r"22\s*KT\s*Gold\s*₹\s*([\d,]+)", text, re.I)
    r24 = re.search(r"24\s*KT\s*Gold\s*₹\s*([\d,]+)", text, re.I)
    up = re.search(r"Updated On:?\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text, re.I)
    if not r22:
        return None
    return {
        "rate_22k": int(r22.group(1).replace(",", "")),
        "rate_24k": int(r24.group(1).replace(",", "")) if r24 else "",
        "site_updated": up.group(1) if up else "",
    }


def via_requests():
    import requests
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return parse(r.text)


def via_playwright():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=HEADERS["User-Agent"], locale="en-IN")
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(5000)
        text = pg.inner_text("body")
        b.close()
    return parse(text)


def via_manual():
    v = os.environ.get("MANUAL_RATE_22K", "").strip()
    if not v:
        return None
    return {
        "rate_22k": int(v.replace(",", "")),
        "rate_24k": os.environ.get("MANUAL_RATE_24K", "").strip(),
        "site_updated": "manual",
    }


def main():
    data = None
    for name, fn in (("requests", via_requests), ("playwright", via_playwright), ("manual", via_manual)):
        try:
            data = fn()
            if data:
                print(f"Got rate via {name}: {data}")
                break
        except Exception as e:  # noqa: BLE001 - try next method
            print(f"{name} failed: {e}")
    if not data:
        print("ERROR: could not fetch rate by any method", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(IST)
    if data["site_updated"] == "manual":
        data["site_updated"] = now.strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    # Skip only if this same rate was already recorded today; otherwise record one row per day
    # even when the store has not changed its rate or timestamp.
    if rows and rows[-1]["fetched_at"][:10] == now.strftime("%Y-%m-%d") \
            and str(rows[-1]["rate_22k"]) == str(data["rate_22k"]):
        print("Same rate already recorded today; nothing to add.")
        return
    rows.append({
        "site_updated": data["site_updated"],
        "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "rate_22k": data["rate_22k"],
        "rate_24k": data["rate_24k"],
        "grams_for_10k": round(10000 / data["rate_22k"], 4),
    })
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Saved. 22K = ₹{data['rate_22k']}/g -> {rows[-1]['grams_for_10k']} g for ₹10,000")


if __name__ == "__main__":
    main()
