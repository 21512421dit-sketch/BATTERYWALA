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
