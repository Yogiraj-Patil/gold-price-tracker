# WhatsApp setup (Meta Cloud API, free test tier, up to 5 recipients)

1. https://developers.facebook.com → **My Apps → Create App** → use case **Connect with customers through WhatsApp** (needs a free business portfolio).
2. In **WhatsApp → API Setup** you get a free **test phone number** and its **Phone number ID** (-> secret `WA_PHONE_ID`).
3. In the same page, under **To**, add each recipient's number (max 5). Each person confirms with the code WhatsApp sends them.
4. **Permanent token** (the 24-hour token on that page expires, so don't use it):
   Business Settings → Users → **System users** → Add (Admin) → **Add assets** (your app, full control) → **Generate token**
   with `whatsapp_business_messaging` + `whatsapp_business_management`, expiry **Never** (-> secret `WA_TOKEN`).
5. **Message template**: WhatsApp Manager → **Message templates → Create**: category **Utility**, name `gold_daily`, language English, body:
   `Gold update: {{1}}. 22K rate Rs {{2}}/g, Rs 10,000 buys {{3}} g. Why: {{4}}`
   Wait until status is **Active**.
6. GitHub secrets: `WA_TOKEN`, `WA_PHONE_ID`, `WA_RECIPIENTS` = `919876543210, 919811122233, ...`, `WA_TEMPLATE` = `gold_daily`.
7. To test before the template is approved, set `WA_TEMPLATE` = `hello_world` (Meta's built-in sample greeting).

Free-form text can't be used (only within 24 h of the person messaging you), so a template is required.
