"""Fetch gold rates for every store in stores.py and append to each store's history.csv.

Per store, in order:
  1. plain HTTP request (only for server-rendered sites)
  2. headless Chromium via Playwright (also needed for sites that load rates with JavaScript)
  3. MANUAL_RATE_22K / MANUAL_RATE_24K env vars, for the store named in MANUAL_STORE
One store failing never blocks the others; the script exits non-zero at the end if any failed,
so GitHub emails you about the failed run.

Usage: python scraper/fetch_rate.py [store_key ...]   (default: all stores)
"""
import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import stores

FIELDS = ["site_updated", "fetched_at", "rate_22k", "rate_24k", "grams_for_10k", "rate_silver"]
IST = timezone(timedelta(hours=5, minutes=30))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
}


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def parse(store, text):
    """Generic parser driven by the regexes in stores.json. Returns None if the 22K rate is missing."""
    text = _clean(text)
    if store.get("anchor"):
        i = text.find(store["anchor"])
        if i >= 0:
            text = text[i:]
    r22 = re.search(store["rate_22k_re"], text, re.I)
    if not r22:
        return None
    r24 = re.search(store["rate_24k_re"], text, re.I) if store.get("rate_24k_re") else None
    up = re.search(store["updated_re"], text, re.I) if store.get("updated_re") else None
    gold_per = store.get("gold_per_grams", 1)
    return {
        "rate_22k": per_gram(r22.group(1), gold_per),
        "rate_24k": per_gram(r24.group(1), gold_per) if r24 else "",
        "rate_silver": parse_silver(store, text),
        "site_updated": up.group(1) if up else "",
    }


def per_gram(raw, per_grams):
    """Convert a quoted price to Rs per GRAM. per_grams = how many grams the quote is for
    (1 = per gram, 10 = per 10 g, 500 = per 500 g, 1000 = per kg). Returns '' if unparsable."""
    try:
        v = float(str(raw).replace(",", "")) / float(per_grams or 1)
    except ValueError:
        return ""
    return int(v) if v == int(v) else round(v, 2)


def parse_silver(store, text):
    """Silver in Rs per gram ('' if the page has none). Set silver_per_grams in stores.json to the
    quantity the site quotes: 1 (per gram), 500 (per 500 g), 1000 (per kg)..."""
    if not store.get("rate_silver_re"):
        return ""
    m = re.search(store["rate_silver_re"], text, re.I)
    return per_gram(m.group(1), store.get("silver_per_grams", 1)) if m else ""


def via_requests(store):
    if store.get("render") == "browser":
        return None
    import requests
    r = requests.get(store["url"], headers=HEADERS, timeout=30)
    r.raise_for_status()
    return parse(store, r.text)


# document.body.textContent glues neighbouring elements together ('22K13117'), which breaks the
# regexes. This joins every visible-or-hidden text node with a space (scripts/styles skipped).
SPACED_TEXT_JS = """() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const out = [];
  let n;
  while ((n = walker.nextNode())) {
    const tag = n.parentElement ? n.parentElement.tagName : '';
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') continue;
    const t = n.textContent.trim();
    if (t) out.push(t);
  }
  return out.join(' ');
}"""


def via_playwright(store):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # PLAYWRIGHT_CHANNEL=msedge (or chrome) uses the browser already installed on this PC,
        # handy for running locally without 'playwright install'. GitHub uses its own Chromium.
        b = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        pg = b.new_page(user_agent=HEADERS["User-Agent"], locale="en-IN")
        pg.goto(store["url"], wait_until="domcontentloaded", timeout=60000)
        if store.get("wait_text"):
            # JavaScript fills in the rates after load; wait for the marker text to appear.
            pg.wait_for_function("t => document.body.textContent.includes(t)", arg=store["wait_text"], timeout=45000)
        else:
            pg.wait_for_timeout(5000)
        text = pg.evaluate(SPACED_TEXT_JS)
        title = pg.title()
        b.close()
    data = parse(store, text)
    if data is None:
        # Make a silent parse failure explain itself in the Actions log.
        i = text.find(store["anchor"]) if store.get("anchor") else 0
        raise RuntimeError(f"page loaded (title {title!r}) but no 22K rate matched; "
                           f"text near the rates: {text[max(i, 0):max(i, 0) + 300]!r}")
    return data


def via_manual(store):
    if (os.environ.get("MANUAL_STORE") or stores.STORES[0]["key"]).strip() != store["key"]:
        return None
    v = os.environ.get("MANUAL_RATE_22K", "").strip()
    if not v:
        return None
    return {
        "rate_22k": int(v.replace(",", "")),
        "rate_24k": os.environ.get("MANUAL_RATE_24K", "").strip(),
        "rate_silver": os.environ.get("MANUAL_RATE_SILVER", "").strip(),   # Rs per gram
        "site_updated": "manual",
    }


def fetch_store(store):
    """Fetch one store and append a row. Returns True on success."""
    data = None
    for name, fn in (("requests", via_requests), ("playwright", via_playwright), ("manual", via_manual)):
        try:
            data = fn(store)
            if data:
                print(f"[{store['key']}] got rate via {name}: {data}")
                break
        except Exception as e:  # noqa: BLE001 - try next method
            print(f"[{store['key']}] {name} failed: {e}")
    if not data:
        print(f"ERROR [{store['key']}]: could not fetch rate by any method", file=sys.stderr)
        return False

    now = datetime.now(IST)
    if data["site_updated"] == "manual":
        data["site_updated"] = now.strftime("%Y-%m-%d %H:%M:%S")

    csv_path, _ = stores.paths(store)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    # Skip only if the same gold AND silver rates were already recorded today; otherwise record a row
    # (at least one per day) even when the store has not changed its rate or timestamp.
    if rows and rows[-1]["fetched_at"][:10] == now.strftime("%Y-%m-%d") \
            and str(rows[-1]["rate_22k"]) == str(data["rate_22k"]) \
            and str(rows[-1].get("rate_silver") or "") == str(data.get("rate_silver", "")):
        print(f"[{store['key']}] same rates already recorded today; nothing to add.")
        return True
    rows.append({
        "site_updated": data["site_updated"],
        "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "rate_22k": data["rate_22k"],
        "rate_24k": data["rate_24k"],
        "grams_for_10k": round(10000 / data["rate_22k"], 4),
        "rate_silver": data.get("rate_silver", ""),
    })
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="")   # older rows have no silver column
        w.writeheader()
        w.writerows(rows)
    silver = f", silver = ₹{data['rate_silver']}/g" if data.get("rate_silver") != "" else ", silver not found"
    print(f"[{store['key']}] saved. 22K = ₹{data['rate_22k']}/g -> {rows[-1]['grams_for_10k']} g for ₹10,000{silver}")
    return True


def main():
    keys = sys.argv[1:]
    selected = [stores.by_key(k) for k in keys] if keys else stores.STORES
    results = [fetch_store(s) for s in selected]
    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
