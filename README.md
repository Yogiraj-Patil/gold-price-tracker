# Gold Buy-Day Tracker

Records Chandukaka Saraf's 22K rate twice a day (GitHub Actions, free), compares it with the last 30 days, and emails/WhatsApps you every morning (11:50 IST) whether today is a good day to put ₹10,000 into gold, and why.

## Setup (10 minutes)
1. Create a new **public** GitHub repo (e.g. `gold-tracker`) and push these files.
2. Repo **Settings → Actions → General → Workflow permissions → Read and write**.
3. Repo **Settings → Pages → Deploy from branch → `main` / `(root)`** (dashboard at `https://<you>.github.io/gold-tracker/`).
4. **Settings → Secrets and variables → Actions → New repository secret**:
   - Email (Gmail): `SMTP_USER` (your gmail), `SMTP_PASS` ([App Password](https://myaccount.google.com/apppasswords), needs 2-step verification), `MAIL_TO` — one or many addresses separated by commas, e.g. `me@gmail.com, wife@gmail.com`. To add someone later, just edit this secret.
   - **Phone notification (free, recommended):** install the **ntfy** app (Android/iOS), tap *+* and subscribe to a long random topic name you invent (e.g. `gold-yogesh-7f3k9x2q` — anyone who knows it can read it, so keep it secret). Add the same name as secret `NTFY_TOPIC`. BUY NOW alerts arrive as high-priority; tapping opens the dashboard.
   - WhatsApp (optional): each person activates CallMeBot once (https://www.callmebot.com/blog/free-api-whatsapp-messages/) and gets their own apikey. Then set secret `CALLMEBOT_RECIPIENTS` = `phone:apikey, phone:apikey` (phone with country code, e.g. `919876543210:123456, 919811122233:654321`). Add more people by appending to it. (Old `CALLMEBOT_PHONE`/`CALLMEBOT_APIKEY` still work for one person.)
   - Phone push: everyone who wants it just subscribes to the same ntfy topic — no extra setup.
5. **Actions → gold-tracker → Run workflow** to test now.

## If the site blocks the bot
chandukakasaraf.in sits behind Cloudflare, which blocks some data-centre IPs. The job tries a plain request, then a headless browser. If both fail, the run turns red (GitHub emails you); use **Run workflow** and type today's rate into *manual_rate_22k* — the history and verdict continue as normal.

## Verdict rules (`scraper/analyze.py`)
- Needs 7 days of history ("COLLECTING DATA" until then; first row is seeded with 19 Oct 2026: ₹13,511/g).
- **BUY NOW**: rate in the cheapest 25% of the last 30 days, or ≥1% below the 30-day average.
- **WAIT**: priciest 25%, or ≥1% above average.
- **OK**: in between; becomes "BUY (month ending)" in the last 5 days of the month so you don't miss the month.

Statistical comparison only, not financial advice. Rates are the store's published per-gram rate (excluding making charges/GST).
