"""Send the daily verdict by email and/or WhatsApp (CallMeBot). Credentials come from env (GitHub Secrets)."""
import json
import os
import re
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

import stores

DASHBOARD = os.environ.get("DASHBOARD_URL", "")
CURRENT = {}  # the summary being sent (read by the WhatsApp template sender)


def build():
    """One combined message: common verdict, cheapest store, and every store's latest rate."""
    with open(stores.SUMMARY_PATH, encoding="utf-8") as f:
        v = json.load(f)
    if not v.get("best_store"):
        subject = "Gold today: no recent rates available"
        return subject, subject, v
    subject = (f"Gold today: {v['verdict']} - buy at {v['best_label']} ₹{v['rate']:,.0f}/g "
               f"({v['grams_for_10k']:.3f} g for ₹10k)")
    lines = []
    for r in sorted(v["stores"], key=lambda r: r["rate"]):
        tag = " (stale)" if r["stale"] else ""
        lines.append(f"• {r['label']}: ₹{r['rate']:,.0f}/g -> {r['grams_for_10k']:.3f} g{tag}")
    body = (f"{v['verdict']}\nBest store today: {v['best_label']}\n\n" + "\n".join(lines)
            + "\n\nWhy:\n" + "\n".join(f"• {r}" for r in v["reasons"]))
    sv = v.get("silver")
    if sv and sv.get("best_store"):
        body += f"\n\nSILVER: {sv['verdict']} - best store {sv['best_label']}\n"
        body += "\n".join(f"• {r['label']}: ₹{r['rate']:,.2f}/g -> {r['grams_for_10k']:.2f} g for ₹{sv['invest']:,}"
                          + (" (stale)" if r["stale"] else "")
                          for r in sorted(sv["stores"], key=lambda r: r["rate"]))
        body += "\n" + "\n".join(f"• {r}" for r in sv["reasons"][:3])
    if DASHBOARD:
        body += f"\n\nDashboard: {DASHBOARD}"
    body += "\n\n(Statistical comparison with recent Chandukaka Saraf 22K rates; not financial advice.)"
    return subject, body, v


def split_list(value):
    """Comma / semicolon / newline separated values -> clean list."""
    return [x.strip() for x in re.split(r"[,;\n]+", value or "") if x.strip()]


def send_email(subject, body):
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    recipients = split_list(os.environ.get("MAIL_TO"))
    if not (user and pw and recipients):
        print("Email not configured; skipping.")
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"] = subject, user
    msg["Bcc"] = ", ".join(recipients)          # each person sees only their own address
    msg.set_content(body)
    with smtplib.SMTP(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg, to_addrs=recipients)
    print(f"Email sent to {len(recipients)} recipient(s).")


def whatsapp_recipients():
    """CALLMEBOT_RECIPIENTS = 'phone:apikey, phone:apikey'. Falls back to old single-person secrets."""
    pairs = [x.split(":", 1) for x in split_list(os.environ.get("CALLMEBOT_RECIPIENTS")) if ":" in x]
    if not pairs and os.environ.get("CALLMEBOT_PHONE") and os.environ.get("CALLMEBOT_APIKEY"):
        pairs = [[os.environ["CALLMEBOT_PHONE"], os.environ["CALLMEBOT_APIKEY"]]]
    return [(p.strip(), k.strip()) for p, k in pairs]


def send_whatsapp(subject, body):
    recipients = whatsapp_recipients()
    if not recipients:
        print("WhatsApp not configured; skipping.")
        return
    errors = 0
    for phone, key in recipients:
        try:
            q = urllib.parse.urlencode({"phone": phone, "apikey": key, "text": f"{subject}\n\n{body}"})
            with urllib.request.urlopen(f"https://api.callmebot.com/whatsapp.php?{q}", timeout=30) as r:
                print(f"WhatsApp to ...{phone[-4:]}: status {r.status}")
        except Exception as e:  # noqa: BLE001 - one bad number must not block the rest
            errors += 1
            print(f"WhatsApp to ...{phone[-4:]} failed: {e}", file=sys.stderr)
    if errors:
        raise RuntimeError(f"{errors} WhatsApp message(s) failed")


def send_meta_whatsapp(subject, body):
    """Official WhatsApp Cloud API. Needs an approved template with 4 body variables:
    {{1}} verdict, {{2}} rate, {{3}} grams for 10k, {{4}} reasons."""
    token, phone_id = os.environ.get("WA_TOKEN"), os.environ.get("WA_PHONE_ID")
    recipients = split_list(os.environ.get("WA_RECIPIENTS"))
    if not (token and phone_id and recipients):
        print("Meta WhatsApp not configured; skipping.")
        return
    v = CURRENT["verdict"]
    if not v.get("best_store"):
        return
    template = os.environ.get("WA_TEMPLATE") or "gold_daily"
    extra = ""
    sv = v.get("silver")
    if sv and sv.get("best_store"):
        extra = f" | Silver: {sv['verdict']}, best {sv['best_label']} at Rs {sv['rate']:,.2f}/g"
    reasons = re.sub(r"\s+", " ", f"Buy at {v['best_label']}. " + " | ".join(v["reasons"][:5]) + extra)[:900]
    tpl = {"name": template, "language": {"code": os.environ.get("WA_LANG") or "en"}}
    if template != "hello_world":
        vals = [v["verdict"], f"{v['rate_22k']:,.0f}", f"{v['grams_for_10k']:.3f}", reasons]
        tpl["components"] = [{"type": "body", "parameters": [{"type": "text", "text": x} for x in vals]}]
    errors = 0
    for to in recipients:
        to = re.sub(r"\D", "", to)
        payload = json.dumps({"messaging_product": "whatsapp", "to": to, "type": "template", "template": tpl}).encode()
        req = urllib.request.Request(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages", data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"Meta WhatsApp to ...{to[-4:]}: status {r.status}")
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"Meta WhatsApp to ...{to[-4:]} failed: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"Meta WhatsApp to ...{to[-4:]} failed: {e}", file=sys.stderr)
    if errors:
        raise RuntimeError(f"{errors} Meta WhatsApp message(s) failed")


def send_push(subject, body):
    """Free phone push via ntfy.sh (install the ntfy app, subscribe to your secret topic)."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("Phone push (ntfy) not configured; skipping.")
        return
    verdict = subject.split(":")[1].split("-")[0].strip()
    tag = "white_check_mark" if verdict.startswith("BUY") else "hourglass" if verdict == "WAIT" else "coin"
    headers = {"Title": subject.replace("₹", "Rs ").encode("utf-8"), "Tags": tag,
               "Priority": "high" if verdict.startswith("BUY") else "default"}
    if DASHBOARD:
        headers["Click"] = DASHBOARD
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        print("Phone push status:", r.status)


if __name__ == "__main__":
    failed = False
    # NOTIFY_CHANNELS: "all" (default) or a list such as "email" (evening run = email only)
    wanted = set(split_list((os.environ.get("NOTIFY_CHANNELS") or "all").lower()))
    channels = {send_email: "email", send_push: "push", send_meta_whatsapp: "whatsapp", send_whatsapp: "whatsapp"}
    if not os.path.exists(stores.SUMMARY_PATH):
        print("No summary.json yet; nothing to send.", file=sys.stderr)
        sys.exit(1)
    subject, body, v = build()
    CURRENT["verdict"] = v
    print(subject, body, sep="\n")
    for fn, name in channels.items():
        if "all" not in wanted and name not in wanted:
            print(f"Skipping {fn.__name__} (not in NOTIFY_CHANNELS).")
            continue
        try:
            fn(subject, body)
        except Exception as e:  # noqa: BLE001
            print(f"{fn.__name__} failed: {e}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)
