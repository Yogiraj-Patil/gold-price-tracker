# Metal Buy-Day Tracker - handoff for AI assistants

Paste this whole file into any AI model (ChatGPT, Gemini, Claude, ...) together with the request
("Add store X, URL ...") and, ideally, the contents of `scraper/stores.json`. It is self-contained.

## 1. What this project is
A free, static-site + GitHub Actions tool for someone who buys **22K gold (Rs 10,000 per purchase)** and
**silver (Rs 5,000 per purchase)** once a month from Chandukaka Saraf stores in Pune, India. Rates move daily, so
it records each store's rate, compares today with recent history, says **which store is cheapest** and
**whether today is a good day to buy** (BUY NOW / OK / WAIT), shows it on a dashboard and sends a daily
message (email, ntfy phone push, WhatsApp). It is a statistical comparison, not financial advice.

- Hosting: GitHub repo + GitHub Pages (no server, no database). Data is CSV/JSON committed back to the repo by a bot.
- Language: Python 3.12 (scraper) + plain HTML/JS (dashboard, Chart.js from cdnjs). No build step.
- **All rates are stored and shown as Rs per GRAM** (sites quoting per 10 g / 500 g / 1 kg are converted).
- Times are IST. GitHub's cron runs in UTC and is often hours late; cron-job.org calls the workflow on time.

Current stores (see `scraper/stores.json`):
| key | label | source | how read |
|---|---|---|---|
| `chandukaka-chandannagar` | Chandukaka Chandannagar | https://chandukakasaraf.in/todays-gold-rate/ | server-rendered HTML, `render: "http"`; silver quoted per 1 KG |
| `chandukaka-alandi` | Chandukaka Alandi | https://csjewels.com/ ("Metal Rates" menu) | JavaScript fills the rates -> `render: "browser"`; silver per 1 g |

Naming convention for new stores: `<brand>-<area>`, lowercase, hyphens (e.g. `png-kharadi`,
`png-chandannagar`, `ranka-charholi-alandi`). Label = readable name shown in the UI.

## 2. Repo map
```
scraper/stores.json     <- THE ONLY FILE NEEDED TO ADD A STORE (data, no code)
scraper/stores.py       loads stores.json; paths per store; SUMMARY_PATH
scraper/fetch_rate.py   fetches every store, appends one row/day to each store's history.csv
scraper/analyze.py      per-store verdicts + cross-store summary (gold and silver) -> JSON
scraper/notify.py       sends ONE combined message (HTML+text email with dashboard button / ntfy / Meta WhatsApp / CallMeBot)
.github/workflows/gold.yml   Actions: install -> fetch -> analyze -> commit data -> notify
index.html, stores.html      dashboard pages (overview; per-store). Read data/summary.json
site.js, site.css       shared header/menu/title for all pages (edit site.js to change them)
data/history.csv + data/verdict.json                 first store (legacy location)
data/<store-dir>/history.csv + verdict.json          other stores (data_dir in stores.json)
data/summary.json       everything the dashboard and notifier read (generated, committed)
README.md, WHATSAPP_SETUP.md   setup docs
```
history.csv columns: `site_updated,fetched_at,rate_22k,rate_24k,grams_for_10k,rate_silver` (rates Rs/g;
`grams_for_10k` is legacy-named and is always 10000/rate_22k; silver may be blank on old rows).
One row per day at least; a second row the same day is added only if gold or silver changed.

Pipeline per run: `fetch_rate.py` (all stores; one store failing never blocks the others; exits 1 if any failed)
-> `analyze.py` -> commit `data/` -> `notify.py` (only on manual/cron-job.org runs) -> final step fails the
run if any store failed to fetch.

`summary.json` shape: top level = gold: `{generated_at, invest, metal, stores:[{key,label,note,rate,grams_for_10k,as_of,stale,verdict,reasons,days_of_data,history:[{date,rate}]}], ranking, verdict, best_store, best_label, rate, grams_for_10k, reasons, timing_basis}`; `silver` = same shape for silver (its `invest` is 5000).

Verdict logic (`analyze.py`): needs 7 days of history else "COLLECTING DATA". BUY NOW = cheapest 25% of the last 30
days or >=1% below the 30-day average; WAIT = priciest 25% or >=1% above; else OK; becomes "BUY (month ending)" in the
last 5 days of a month. Cross-store: cheapest non-stale store (reading <= 2 days old) is recommended; timing is
judged on the best price across stores using only days all stores share, falling back to the store with the longest
history. Amounts: `INVEST` (gold) and `INVEST_SILVER` in `analyze.py`.

### Notifications (`scraper/notify.py`)
One combined message per run (not one per store): headline verdict + cheapest store, each store's latest gold rate,
the reasons, a SILVER section, then the dashboard link. It is built once by `build()` and sent by independent
channels; one failing channel never blocks the others (the run exits 1 if any failed).
| channel | enabled by (GitHub secret/variable) | notes |
|---|---|---|
| email | `SMTP_USER`, `SMTP_PASS` (Gmail app password), `MAIL_TO` (comma-separated list; may be a repo **variable** or secret) | sent as Bcc, so recipients don't see each other. **Multipart: plain text + HTML.** The dashboard link is the **first line** of the plain-text part and a gold **"Open dashboard" button** at the top of the HTML part (`email_html()`); the `Dashboard: <url>` line in the body is also made clickable. |
| ntfy phone push | `NTFY_TOPIC` | same body; the `Click` header makes tapping the notification open the dashboard |
| WhatsApp (Meta Cloud API) | `WA_TOKEN`, `WA_PHONE_ID`, `WA_RECIPIENTS`, `WA_TEMPLATE` | template with 4 variables ({{1}} verdict, {{2}} gold rate, {{3}} grams, {{4}} reasons incl. a silver line); see `WHATSAPP_SETUP.md` |
| WhatsApp (CallMeBot, backup) | `CALLMEBOT_RECIPIENTS` = `phone:apikey, ...` | optional |
The dashboard URL comes from env `DASHBOARD_URL`, set in the workflow's Notify step to
`https://<owner>.github.io/<repo>/` (it follows repo renames). Without it, no link is added anywhere.
`NOTIFY_CHANNELS` (`all`, or e.g. `email`) limits channels; notifications are sent only on manual /
cron-job.org (`workflow_dispatch`) runs with `notify=true`, never on GitHub's own scheduled runs.
Gotcha: keep important links near the top of a message - a link in the last line of a long email gets missed.
To test the email layout without sending: `python -c "import sys; sys.path.insert(0,'scraper'); import notify; print(notify.email_html(*notify.build()[:2]))"` with `DASHBOARD_URL` set.

## 3. HOW TO ADD A STORE (the task you will most often be asked to do)
Goal: add ONE object to the JSON array in `scraper/stores.json`. No Python/HTML changes are normally needed;
the store then appears automatically in the fetch, analysis, dashboard tabs/table/chart and notifications.

### Fields
| field | required | meaning |
|---|---|---|
| `key` | yes | `<brand>-<area>`, lowercase letters/digits/hyphens; used in file names and URLs |
| `label` | yes | display name |
| `url` | yes | page that shows the rates |
| `data_dir` | yes | `data/<key>` (folder is created automatically; first store alone uses plain `data`) |
| `render` | yes | `"http"` = plain request first, headless browser as fallback (use when rates are in the HTML). `"browser"` = headless browser only (rates are inserted by JavaScript after load) |
| `wait_text` | browser | text that appears once rates have loaded, e.g. `"Updated On"` (script waits up to 45 s for it) |
| `anchor` | optional | text from which to start reading (avoids matching earlier text on the page) |
| `rate_22k_re` | yes | regex; **group 1** = the 22K number |
| `rate_24k_re` | optional | regex; group 1 = 24K number |
| `updated_re` | optional | regex; group 1 = the site's "updated on" timestamp |
| `rate_silver_re` | optional | regex; group 1 = silver number |
| `silver_per_grams` | optional (default 1) | grams the site's silver price is for: `1` per gram, `500` per 500 g, `1000` per kg |
| `gold_per_grams` | optional (default 1) | same for gold, e.g. `10` if quoted per 10 g |
| `note` | optional | caveat shown on the dashboard (e.g. "online purchase only") |

JSON rules: no comments, no trailing commas, **backslashes doubled** (`"\\s+"`, `"\\d"`, `"\\b"`).
Regexes run case-insensitively over the page text with whitespace collapsed to single spaces.
Prices may contain commas (`13,511`); the parser strips them.

### Procedure
1. **Open the page in a normal browser and read how rates appear.** Note: the 22K gold, 24K gold and silver values,
   the unit each is quoted in (per 1 g / 10 g / 500 g / 1 kg), and the "updated on" text.
2. **Decide `render`.** Right-click -> View Source (not Inspect): if the numbers are in the source, use `"http"`.
   If they are missing there (filled by JavaScript, often after hover/click or a few seconds), use `"browser"`.
   Optionally find the JSON API the page calls (DevTools -> Network -> Fetch/XHR) - but do NOT hard-code site API
   keys or tokens; reading the rendered page is preferred.
3. **Write the regexes against the text a browser would give**, e.g. `... 22K 13117 24K 14180 Silver 198 ...`
   (see gotcha 1 about spacing). Test them (section 5) before committing.
4. **Add the object**, keep `key` unique, put `silver_per_grams` right for the site.
5. **Test locally with the snippet in section 5**, then run the workflow once (section 6) and confirm the
   "Fetch rates" step prints `[<key>] saved. 22K = ...`.
6. The new store has no history, so its own verdict says "COLLECTING DATA" for 7 days; it still takes part in the
   cheapest-store comparison immediately. Do not fabricate history. If real earlier prices exist, they may be
   appended to the store's `history.csv` in the same column format.

### Example entry (server-rendered page quoting per gram, silver per 500 g)
```json
{
  "key": "png-kharadi",
  "label": "PNG Kharadi",
  "url": "https://example.com/gold-rate",
  "data_dir": "data/png-kharadi",
  "render": "http",
  "rate_22k_re": "22\\s*K[^\\d]{0,20}([\\d,]+)",
  "rate_24k_re": "24\\s*K[^\\d]{0,20}([\\d,]+)",
  "updated_re": "Updated[^\\d]{0,10}(\\d{2}-\\d{2}-\\d{4}[^\\n]{0,12})",
  "rate_silver_re": "Silver[^\\d]{0,20}([\\d,]+)",
  "silver_per_grams": 500
}
```
Timestamps are only displayed/stored as text, so any format is fine; if there is no timestamp, omit `updated_re`.

### Gotchas learned the hard way
1. **Text glued together.** `document.body.textContent` joins neighbouring elements with no space (`22K13117`), which
   silently broke the Alandi regex. The scraper therefore reads text with a space between every text node
   (`SPACED_TEXT_JS` in `fetch_rate.py`). Write regexes for spaced text, but make them tolerate no space with `\\s*` if
   the site is plain HTML.
2. **Silent failure looks like "could not fetch rate by any method".** It means: nothing raised, but no regex
   matched. The browser path now raises an error that includes the page title and text near the rates - read it.
3. **Cloudflare / bot blocks.** Some sites 403 data-centre IPs (GitHub). The plain request fails, the browser fallback
   usually works. If a site blocks both, use the manual input (workflow input `manual_rate_22k`, `manual_rate_silver`
   in Rs/g, `manual_store` = the store key).
4. **JavaScript sites**: wait for text that proves the rates loaded (`wait_text`), not a fixed sleep.
5. **Silver units differ** between sites (per 1 g, 500 g, 1 kg). Always set `silver_per_grams`; the UI is per gram.
6. A page can show a store's **online-only** rate or exclude making charges/GST - mention it in `note`.
7. On the author's corporate laptop, SSL inspection (Zscaler) blocks `requests` and headless browsers, so live
   fetches cannot be tested there; test the regex with captured text and verify live on GitHub Actions.
8. Windows files may be CRLF; edit JSON with a tool that keeps valid JSON (`python -m json.tool` to validate).

## 4. Other tasks you may be asked to do
- **Another metal** (platinum): add a `rate_platinum_re`/column and mirror the silver code path in `fetch_rate.py`
  (`parse`, CSV `FIELDS`), `analyze.py` (`analyze_store`, `main`, `summary["platinum"]`), `notify.py` (extra section)
  and the `METALS` object in `index.html`/`stores.html`. Keep rates per gram.
- **Change purchase amounts:** `INVEST` / `INVEST_SILVER` in `analyze.py`.
- **Change header/title/menu:** `site.js` only.
- **Schedule / notification channels / secrets:** `.github/workflows/gold.yml`, README. Secrets live in GitHub
  (SMTP_USER, SMTP_PASS, MAIL_TO or variable `MAIL_TO` (comma-separated list), NTFY_TOPIC, WA_TOKEN, WA_PHONE_ID,
  WA_RECIPIENTS, WA_TEMPLATE, CALLMEBOT_*). **Never put secrets or tokens in files or chat.**
- **Triggering runs on time:** cron-job.org POSTs to
  `https://api.github.com/repositories/<repo id>/actions/workflows/gold.yml/dispatches` with a fine-grained token
  (Actions: read/write on this repo only) and body `{"ref":"main","inputs":{"notify":"true","channels":"all"}}`
  (use `"channels":"email"` for an email-only run). Use the numeric repository URL; cron-job.org does not follow
  redirects from the old repo-name URL.

## 5. Test a new store locally (no network needed)
Run from the repo root with Python 3. Replace the sample text with the page text a browser shows (copy it from
the page, spaces/newlines are fine), and the key with your new store's key:
```python
# test_store.py  (run: python test_store.py)
import sys; sys.path.insert(0, "scraper")
import fetch_rate as f, stores
store = stores.by_key("png-kharadi")
sample = """PASTE THE RATE TEXT FROM THE PAGE HERE, including the updated-on line"""
print(f.parse(store, sample))   # expect {'rate_22k': ..., 'rate_24k': ..., 'rate_silver': ... (Rs/g), 'site_updated': ...}
```
`parse` returns `None` if the 22K regex fails. Check `rate_silver` is Rs per GRAM (e.g. 198, not 198000).
Full dry run in a throw-away copy (never test on the real history files):
```
cp -r scraper data /tmp/try && python /tmp/try/scraper/analyze.py
```
Also: `python -m py_compile scraper/*.py` and open `index.html` through `python -m http.server` to see the dashboard.

## 6. Verify on GitHub
Actions tab -> gold-tracker -> **Run workflow** (pick the branch; untick "Send notification" while testing).
The "Fetch rates (all stores)" log must show `[<key>] got rate via ...` and `[<key>] saved. 22K = ...`.
Scheduled/cron-job.org runs execute the **default branch** (`main`), so merge the change there when it works.
Data commits made by test runs land on the branch the run used.

## 7. Prompt template to give an AI together with this file
```
You are working on the repository described above (Metal Buy-Day Tracker).
Task: add a new store.
  key: <brand>-<area>        label: <Readable Name>
  URL: <page that shows rates>
  Rates I can see on that page (copy the exact text): <paste text incl. updated-on line>
  Gold is quoted per: <1 g / 10 g>   Silver is quoted per: <1 g / 500 g / 1 kg>   Note: <e.g. online-only>
Output ONLY the JSON object to append to scraper/stores.json (valid JSON, backslashes doubled),
a one-line explanation of render "http" vs "browser", and a small test snippet (section 5)
with my pasted text so I can verify before committing. Do not change other files unless needed.
```
If the AI cannot see the page, give it the page's visible text or "View Source" HTML around the rates.

## 8. Do / don't
- Do keep everything per gram, one row per store per day, and keep `key` stable once data exists (it names the folder).
- Do keep `data_dir` unique per store; never reuse another store's folder.
- Don't commit or paste secrets, tokens, API keys, or personal emails/phone numbers.
- Don't delete or rewrite existing history rows; the verdicts depend on them.
- Don't present results as financial advice.
