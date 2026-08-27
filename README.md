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

The public form generates a PDF in Python with the existing PyMuPDF dependency (no AI).
It asks whether an old battery is being exchanged, then offers a PDF download and
optional delivery by email, mobile number (SMS link), or both. Customer delivery
only starts after clicking **Send quotation**. Existing admin notifications remain.

Prices are frozen in the saved quotation. Only exact battery-model matches or
catalogue records with an exact `vehicle_model` mapping are quoted; brand and Ah
preferences are respected. Catalogue customer prices must include 18% GST.
`price_without_exchange`, `discounted_price`, or `selling_price` is used, in that
order, falling back to MRP if no customer selling price is provided. Dealer cost
is never exposed as the customer price. Exchange quotes use `price_with_exchange`
or deduct the record's `exchange_value` from the regular customer price. Missing
matches or exchange values produce a PDF explicitly marked for price confirmation.
The repository's current pricing catalogue is empty; it must be populated with
verified prices before confirmed price quotations can be generated. The existing
PDF importer is unchanged; it does not extract customer discounts or exchange values.

Example verified catalogue record (illustrative, not installed as live pricing):

```json
{"source_type":"retail","brand":"Exide","model_no":"35B20L","vehicle_model":"Alto","capacity_ah":35,"mrp":5096,"selling_price":3500,"exchange_value":500,"warranty":"24+12 months"}
```

Email uses the existing `SMTP_*` settings and attaches the PDF. SMS posts the
existing `{ "to": "...", "message": "..." } payload to `SMS_WEBHOOK_URL`; set
`PUBLIC_BASE_URL` to the deployed HTTPS origin so the PDF link works on a phone.
Without providers, downloads still work and the UI explicitly reports that
delivery is not configured (nothing is falsely reported as sent or queued).
PDF links contain a random access token: treat them as private share links.
Delivery attempts are logged in the existing `Delivery` table. No database migration
is required. The original `/api/predict` endpoint remains unchanged.
