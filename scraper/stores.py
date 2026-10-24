"""Store registry, loaded from stores.json. To add a store, add an entry to stores.json - no code needed.

Fields per store:
  key         short id, also used in file names (letters/digits only)
  label       name shown on the dashboard and in notifications
  url         page that shows the rates
  data_dir    folder (relative to the repo root) for this store's history.csv and verdict.json
  render      "http"    = plain request first, headless browser as fallback (server-rendered pages)
              "browser" = headless browser only (rates are filled in by JavaScript)
  wait_text   (browser) text that appears on the page once the rates have loaded
  anchor      (optional) text to start reading from, to avoid matching something earlier on the page
  rate_22k_re, rate_24k_re, updated_re   regexes; group 1 captures the number / timestamp
  note        (optional) caveat shown on the dashboard
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

with open(os.path.join(os.path.dirname(__file__), "stores.json"), encoding="utf-8") as _f:
    STORES = json.load(_f)

for _s in STORES:
    _s["dir"] = os.path.join(ROOT, _s["data_dir"])

SUMMARY_PATH = os.path.join(ROOT, "data", "summary.json")


def paths(store):
    return os.path.join(store["dir"], "history.csv"), os.path.join(store["dir"], "verdict.json")


def by_key(key):
    for s in STORES:
        if s["key"] == key:
            return s
    raise KeyError(key)
