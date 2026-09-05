# BatteryWala Full Stack

A deployable Flask application containing:
- Public battery recommendation form
- Admin-only pricing workspace
- PDF upload, OCR fallback, preview and publish
- Atomic replacement of the current pricing JSON, with backup and upload history
- Recipient management for email and phone numbers
- Lead storage and notification delivery logs
- SQLite by default, configurable with `DATABASE_URL`

## Local run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```
Open `http://127.0.0.1:8000`. Admin login is at `/admin/login`.

The first start creates the admin from `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
Email is sent when SMTP values are configured. SMS is sent by POSTing JSON to `SMS_WEBHOOK_URL` when configured. Without providers, the lead and delivery attempt are still saved.

## Test
```bash
pytest -q
```

## Automatic quotations

The public form performs a server-side Google search through Serpbase. Add your API
key to `.env` as `SERPBASE_API_KEY`, then restart the server. The key is never sent to
browser JavaScript. The search uses only battery-fitment fields; customer name, phone,
email, address, city, and PIN code are not included. Only domains in
`BATTERY_SEARCH_ALLOWED_DOMAINS` can influence or appear in a recommendation.

The former SQLite fitment lookup is not used for recommendations or form options.
Vehicle make, model, and preferred brand are free-text fields so they can be searched
directly through Google.

The application stores a minimal lead and immutable quotation snapshot so its private PDF can
be delivered. The public download control and download URL are not exposed. The
customer may send the quotation by email, mobile number (SMS link), or both, and
delivery starts only after clicking **Send quotation**.

Prices are frozen in the saved quotation. Only exact battery-model matches or
catalogue records with an exact `vehicle_model` mapping are quoted; brand and Ah
preferences are respected. Catalogue customer prices must include 18% GST.
`price_without_exchange`, `discounted_price`, or `selling_price` is used, in that
order, falling back to MRP if no customer selling price is provided. Dealer cost
is never exposed as the customer price. Exchange quotes use `price_with_exchange`
or deduct the record's `exchange_value` from the regular customer price. Missing
matches or exchange values produce a PDF explicitly marked for price confirmation.
The customer form is driven by `app/data/form_schemas.json`, with separate question
sets for each new-battery and restoration application. Supplied Exide, PMK-Prycal,
Amaron and scrap data is stored in separate files under `app/data/catalogs/`.

Admin PDF/image uploads run text extraction or OCR immediately. Retail records are
upserted by brand and battery model; scrap records are upserted by application and
capacity. A matching record is replaced with the newly extracted values while new
brands/models are added without deleting unrelated catalogue data.

Example verified catalogue record (illustrative, not installed as live pricing):

```json
{"source_type":"retail","brand":"Exide","model_no":"35B20L","vehicle_model":"Alto","capacity_ah":35,"mrp":5096,"selling_price":3500,"exchange_value":500,"warranty":"24+12 months"}
```

Email uses the existing `SMTP_*` settings and attaches the PDF. SMS posts the
existing `{ "to": "...", "message": "..." } payload to `SMS_WEBHOOK_URL`; set
`PUBLIC_BASE_URL` to the deployed HTTPS origin so the PDF link works on a phone.
Without providers, the UI explicitly reports that delivery is not configured
(nothing is falsely reported as sent or queued).
PDF links contain a random access token: treat them as private share links.
Delivery attempts are logged in the existing `Delivery` table. No database migration
is required. The original `/api/predict` endpoint remains unchanged.
