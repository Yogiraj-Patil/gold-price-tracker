# Gold Buy-Day Tracker

Records Chandukaka Saraf's 22K rate twice a day (GitHub Actions, free), compares it with the last 30 days, and emails/WhatsApps you every morning (11:35 IST) whether today is a good day to put ₹10,000 into gold, and why.

## Setup (10 minutes)
1. Create a new **public** GitHub repo (e.g. `gold-tracker`) and push these files.
2. Repo **Settings → Actions → General → Workflow permissions → Read and write**.
3. Repo **Settings → Pages → Deploy from branch → `main` / `(root)`** (dashboard at `https://<you>.github.io/gold-tracker/`).
4. **Settings → Secrets and variables → Actions → New repository secret**:
   - Email (Gmail): `SMTP_USER` (your gmail), `SMTP_PASS` ([App Password](https://myaccount.google.com/apppasswords), needs 2-step verification), `MAIL_TO` — one or many addresses separated by commas, e.g. `me@gmail.com, wife@gmail.com`. To add someone later, just edit this secret.
   - **Phone notification (free, recommended):** install the **ntfy** app (Android/iOS), tap *+* and subscribe to a long random topic name you invent (e.g. `gold-yogesh-7f3k9x2q` — anyone who knows it can read it, so keep it secret). Add the same name as secret `NTFY_TOPIC`. BUY NOW alerts arrive as high-priority; tapping opens the dashboard.
   - **WhatsApp via Meta Cloud API (official, free for up to 5 recipients)** – see `WHATSAPP_SETUP.md`. Secrets: `WA_TOKEN`, `WA_PHONE_ID`, `WA_RECIPIENTS` (comma-separated, with country code), `WA_TEMPLATE`.
   - WhatsApp via CallMeBot (optional, backup): each person activates CallMeBot once (https://www.callmebot.com/blog/free-api-whatsapp-messages/) and gets their own apikey. Then set secret `CALLMEBOT_RECIPIENTS` = `phone:apikey, phone:apikey` (phone with country code, e.g. `919876543210:123456, 919811122233:654321`). Add more people by appending to it. (Old `CALLMEBOT_PHONE`/`CALLMEBOT_APIKEY` still work for one person.)
   - Phone push: everyone who wants it just subscribes to the same ntfy topic — no extra setup.
5. **Actions → gold-tracker → Run workflow** to test now.

## Stores tracked
Stores are listed in `scraper/stores.json`. Naming convention: `<brand>-<area>`, e.g. `chandukaka-chandannagar`, `chandukaka-alandi`, later `png-kharadi`, `png-chandannagar`, `ranka-charholi-alandi` (the key is used in file names; the label is what you see on the dashboard):

| Store | Source | Data files |
|---|---|---|
| Chandukaka Chandannagar | https://chandukakasaraf.in/todays-gold-rate/ | `data/history.csv`, `data/verdict.json` |
| Chandukaka Alandi | https://csjewels.com/ ("Metal Rates" menu; loaded by script, so read with a headless browser) | `data/chandukaka-alandi/history.csv`, `data/chandukaka-alandi/verdict.json` |

**How it fits together**
1. `fetch_rate.py` reads every store in `stores.json` and appends one row per day to that store's `history.csv`. One store failing never blocks the others.
2. `analyze.py` gives each store its own timing verdict, then writes `data/summary.json`: today's price at every store, the cheapest store, and **one common verdict**.
3. The common verdict = *which store to buy from* (lowest 22K ₹/g among stores with a rate from the last 2 days) + *whether it is a good time* (judged on the best available price across stores, using only days where all stores have data; until 7 such days exist it uses the store with the longest history).
4. `notify.py` sends ONE message (email / ntfy / WhatsApp) with the common verdict, every store's latest rate and the reasons.
5. `index.html` shows the common verdict, a table of the latest price at each store, and one chart with every store's history.

**Changing the header / menu text**: edit `site.js` only (app title, subtitle, page titles and menu). Both pages build their header from it, and `site.css` holds its styling. A new page = one more entry in `SITE.pages` plus `<header id="site-header"></header>` and `SiteHeader.render('<id>')` in that page.

**Adding another store** - no code needed. Add an entry to `scraper/stores.json`:
```json
{
  "key": "png-kharadi",                   // <brand>-<area>, lowercase letters/digits/hyphens, used in file names
  "label": "PNG Kharadi",                 // shown on dashboard and in messages
  "url": "https://example.com/gold-rate",
  "data_dir": "data/png-kharadi",
  "render": "http",                       // "http" = plain request (browser as fallback); "browser" = JavaScript-filled page
  "wait_text": "Updated On",              // browser only: text that appears once rates have loaded
  "anchor": "Metal Rate",                 // optional: start reading the page from this text
  "rate_22k_re": "22K\\s+(\\d[\\d,]*)",   // regex, group 1 = the number
  "rate_24k_re": "24K\\s+(\\d[\\d,]*)",
  "updated_re": "Updated On:?\\s*(\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2})",
  "rate_silver_re": "Silver\\s*₹\\s*([\\d,.]+)",   // optional: silver
  "silver_per_grams": 1000,               // grams the SITE quotes silver for: 1 = per gram, 500 = per 500 g, 1000 = per kg
  "gold_per_grams": 1,                    // optional, same idea for gold (e.g. 10 if the site quotes per 10 g)
  "note": "optional caveat shown on the dashboard"
}
```
**Rates are always stored and shown per gram.** Sites quote silver differently (per 1 g, per 500 g, per 1 kg...), so set `silver_per_grams` to the quantity the site's price is for and the tracker divides it down to ₹/g (e.g. `₹198000 PER 1 KG` with `silver_per_grams: 1000` becomes ₹198/g). Silver and gold are tracked, compared and notified separately; the dashboard has a Gold 22K / Silver switch.
(JSON has no comments - remove the `//` notes. Backslashes are doubled inside JSON strings.) Then run the workflow once; the store appears on the dashboard automatically. Note csjewels.com labels its rates "applicable for online purchase only", and store rates exclude making charges and GST.

## If the site blocks the bot
chandukakasaraf.in sits behind Cloudflare, which blocks some data-centre IPs. The job tries a plain request, then a headless browser. If both fail, the run turns red (GitHub emails you); use **Run workflow** and type today's rate into *manual_rate_22k* (and, optionally, *manual_rate_silver* in ₹ per gram) and pick the store in *manual_store* (`chandukaka-chandannagar` or `chandukaka-alandi`) — the history and verdict continue as normal.

## Verdict rules (`scraper/analyze.py`)
- Needs 7 days of history ("COLLECTING DATA" until then; first row is seeded with 19 Oct 2026: ₹13,511/g).
- **BUY NOW**: rate in the cheapest 25% of the last 30 days, or ≥1% below the 30-day average.
- **WAIT**: priciest 25%, or ≥1% above average.
- **OK**: in between; becomes "BUY (month ending)" in the last 5 days of the month so you don't miss the month.

Statistical comparison only, not financial advice. Rates are the store's published per-gram rate (excluding making charges/GST).
