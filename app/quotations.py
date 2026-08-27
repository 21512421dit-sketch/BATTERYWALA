"""Deterministic quotation snapshots, PDF downloads and opt-in delivery."""
import hmac
import json
import os
import re
import secrets
import smtplib
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

import fitz
from flask import Blueprint, abort, current_app, jsonify, request, url_for

from . import db
from .models import Delivery, Lead, Recipient
from .services import load_data, norm, notify, predict

bp = Blueprint('quotations', __name__)
NOTES = {
    'yes': 'Discounted Price is after deducting the exchange value of old battery and it is including 18% GST',
    'no': 'Discounted Price is including 18% GST',
}


def money(value):
    try:
        amount = Decimal(str(value).replace(',', ''))
        if amount.is_finite() and 0 <= amount <= 100000000:
            return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        pass
    return None


def quotation_options(form):
    """Only quote an exact battery model or an explicitly mapped vehicle.

    Dealer cost is not a customer selling price. All selling-price fields in
    the catalogue must already include GST; tax is never added a second time.
    """
    options = []
    for record in load_data().get('records', []):
        if record.get('source_type') == 'scrap' or not record.get('model_no'):
            continue
        model_match = form.get('model_no') and norm(form['model_no']) == norm(record['model_no'])
        vehicle_match = (form.get('car_model') and record.get('vehicle_model')
                         and norm(form['car_model']) == norm(record['vehicle_model']))
        if not (model_match or vehicle_match):
            continue
        brand = norm(form.get('brand'))
        if brand and brand != 'any verified brand' and brand != norm(record.get('brand')):
            continue
        if form.get('capacity_ah') and money(form['capacity_ah']) != money(record.get('capacity_ah')):
            continue
        price = next((money(record.get(key)) for key in
                      ('price_without_exchange', 'discounted_price', 'selling_price', 'mrp')
                      if money(record.get(key)) is not None), None)
        if form['exchange_old_battery'] == 'yes':
            exchange_price = money(record.get('price_with_exchange'))
            credit = money(record.get('exchange_value'))
            price = exchange_price if exchange_price is not None else (
                price - credit if price is not None and credit is not None and credit <= price else None)
        options.append({
            'brand': record.get('brand') or 'Pending', 'model_no': record['model_no'],
            'capacity_ah': record.get('capacity_ah') or '-',
            'mrp': str(money(record.get('mrp'))) if money(record.get('mrp')) is not None else None,
            'price': str(price) if price is not None else None,
            'warranty': record.get('warranty') or (
                f"{record['warranty_months']} months" if record.get('warranty_months') else 'To be confirmed'),
        })
    return options


def render_pdf(lead, quote):
    """Fill the sample's artwork with real data, using its exact PDF coordinates.

    The bundled template has all sample customer details and prices removed.
    Reusing its header, table borders and footer also preserves the original logo.
    """
    form = json.loads(lead.form_json)
    ink = fitz.sRGB_to_pdf(0x0F172A)
    muted = fitz.sRGB_to_pdf(0x475569)
    green = fitz.sRGB_to_pdf(0x059669)
    fonts = {False: fitz.Font('helv'), True: fitz.Font('hebo')}
    right = 563.28

    def clean(value):
        return ' '.join(str(value if value is not None else '-').split()) or '-'

    def lines(value, width, size=9, bold=False):
        # Wrap at words, with a character fallback for long model identifiers.
        result, line = [], ''
        for word in clean(value).split(' '):
            candidate = (line + ' ' + word).strip()
            if fonts[bold].text_length(candidate, fontsize=size) <= width:
                line = candidate
                continue
            if line:
                result.append(line)
            line = ''
            for char in word:
                if line and fonts[bold].text_length(line + char, fontsize=size) > width:
                    result.append(line)
                    line = ''
                line += char
        return result + [line]

    def write(value, x, baseline, size=9, bold=False, color=ink, align='left'):
        value = clean(value)
        width = fonts[bold].text_length(value, fontsize=size)
        if align == 'right':
            x -= width
        elif align == 'center':
            x -= width / 2
        if all(ord(char) < 256 for char in value):
            page.insert_text((x, baseline), value, fontname='hebo' if bold else 'helv',
                             fontsize=size, color=color)
        else:
            writer = fitz.TextWriter(page.rect)
            writer.append((x, baseline), value, font=fonts[bold], fontsize=size)
            writer.write_text(page, color=color)

    def fragment(rect, top, height=None):
        clip = fitz.Rect(rect)
        target = fitz.Rect(clip.x0, top, clip.x1, top + (clip.height if height is None else height))
        page.show_pdf_page(target, template, 0, clip=clip, keep_proportion=False)

    def section(title, pairs, baseline):
        write(title, 32, baseline, size=12, bold=True)
        baseline += 16.3
        for label, value in pairs:
            write(label, 32, baseline, size=11, color=muted)
            for line in lines(value, right - 150, size=11, bold=True):
                write(line, right, baseline, size=11, bold=True, align='right')
                baseline += 14.1
        return baseline + 14.9

    def amount(value, mrp=False):
        if value is None:
            return 'To be confirmed'
        number = Decimal(value)
        return 'Rs.' + (f'{number:,.0f}' if mrp and number == number.to_integral() else f'{number:,.2f}')

    column_x = (39, 123.6848, 218.9552, 261.2976, 340.6896, 462.4240)
    widths = [column_x[i + 1] - x - 12 if i < 5 else right - x - 6
              for i, x in enumerate(column_x)]
    rows = []
    for item in quote['options']:
        values = (item['brand'], item['model_no'], item['capacity_ah'],
                  amount(item['mrp'], mrp=True), amount(item['price']), item['warranty'])
        cells = [lines(value, widths[i], bold=i == 4) for i, value in enumerate(values)]
        rows.append((cells, 22.9 + 11.4 * (max(map(len, cells)) - 1)))
    if not rows:
        pending = lines('No verified battery price is available for this request. ' + quote['message'], 517.28)
        rows.append(([pending], 22.9 + 11.4 * (len(pending) - 1)))
    application = form.get('application') or form.get('battery_type') or '-'
    vehicle_type = {'Passenger vehicle': 'FOUR WHEELER', 'Two wheeler': 'TWO WHEELER',
                    'Commercial vehicle': 'COMMERCIAL VEHICLE'}.get(application, application.upper())
    date = '/'.join(str(int(part)) for part in quote['date'].split('/'))
    with fitz.open(Path(__file__).with_name('assets') / 'quotation-template.pdf') as template, fitz.open() as document:
        index = 0
        while index < len(rows):
            page = document.new_page(width=595.28, height=841.89)
            fragment((0, 0, 595.28, 90), 0)
            write(date, right, 54.6, color=fitz.sRGB_to_pdf(0x64748B), align='right')
            baseline = section('Customer', [('Name', lead.name), ('Mobile', lead.phone),
                ('City' if form.get('city') else 'PIN code', form.get('city') or form.get('pincode'))], 112.15)
            baseline = section('Vehicle', [('Company / Model', ' '.join(filter(None,
                [form.get('vehicle_brand'), form.get('car_model')]))), ('Fuel', form.get('fuel_type')),
                ('Type', vehicle_type)], baseline)
            write('Battery Options', 32, baseline, size=12, bold=True)
            top = baseline + 14.4
            # Copy the original rounded header and fixed column widths unchanged.
            fragment((31, 272.55, 564.28, 297.45), top - 1)
            bottom = top + 23.9
            first_row = True
            while index < len(rows):
                cells, height = rows[index]
                if bottom + height > 740:
                    if not first_row:
                        break
                    count = int((740 - bottom - 22.9) / 11.4) + 1
                    if count < 1:
                        raise ValueError('Customer details exceed the quotation page.')
                    remaining = [cell[count:] for cell in cells]
                    rows.insert(index + 1, (remaining, 22.9 + 11.4 * (max(map(len, remaining)) - 1)))
                    cells = [cell[:count] for cell in cells]
                    height = 22.9 + 11.4 * (count - 1)
                source_top = 297.45 if first_row else 320.35
                fragment((31, source_top, 564.28, source_top + 22.9), bottom, height)
                first_row = False
                for column, cell in enumerate(cells):
                    for n, line in enumerate(cell):
                        write(line, column_x[column], bottom + 14.1 + n * 11.4,
                              bold=column == 4, color=green if column == 4 else ink)
                bottom += height
                index += 1
            # Bottom corners and the thank-you line come from the same sample.
            page.draw_rect((31, bottom - 3, 564.28, bottom + 2), color=None, fill=(1, 1, 1))
            fragment((31, 477.65, 564.28, 482.65), bottom - 3)
            note_top = bottom + 24
            if quote['options'] and quote.get('status') == 'pending_review':
                write(quote['message'], 32, note_top, size=9, color=muted)
                note_top += 14
            for line in lines(quote['note'], 531.28):
                write(line, 297.64, note_top, color=muted, align='center')
                note_top += 11.4
            fragment((0, 510, 595.28, 536), note_top - 6.05)
        document.set_metadata({'title': f"BatteryWala quotation {quote['number']}", 'author': 'BatteryWala'})
        return document.tobytes(garbage=4, deflate=True)


@bp.post('/api/quotations')
def create_quotation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or any(not isinstance(v, str) for v in payload.values()):
        return jsonify(error='Please submit valid form fields.'), 400
    limits = {'name': 120, 'email': 255, 'phone': 40, 'doubts': 2000}
    if any(len(v) > limits.get(k, 200) for k, v in payload.items()) or len(payload) > 30:
        return jsonify(error='One or more form fields are too long.'), 400
    form = {k: v.strip() for k, v in payload.items()}
    form['application'] = form.get('application') or form.get('battery_type', '')
    if not form.get('name') or not form['application'] or not re.fullmatch(r'[0-9]{10}', form.get('phone', '')):
        return jsonify(error='Enter your name, battery type and a valid 10-digit mobile number.'), 400
    if form.get('exchange_old_battery') not in NOTES:
        return jsonify(error='Please choose whether you are exchanging an old battery.'), 400
    if form.get('email') and not valid_email(form['email']):
        return jsonify(error='Enter a valid email address.'), 400
    if form.get('capacity_ah') and (money(form['capacity_ah']) is None or money(form['capacity_ah']) <= 0):
        return jsonify(error='Enter a valid battery capacity.'), 400
    result = predict(form)
    options = quotation_options(form)
    pending = not options or any(item['price'] is None for item in options)
    quote = {'exchange': form['exchange_old_battery'], 'note': NOTES[form['exchange_old_battery']],
             'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%d/%m/%Y'),
             'options': options, 'status': 'pending_review' if pending else 'priced',
             'message': ('Price confirmation required. This document is not a confirmed price offer.' if pending
                         else 'Prices include 18% GST. Battery fitment is subject to confirmation.'),
             'token': secrets.token_urlsafe(32)}
    lead = Lead(name=form['name'], phone=form['phone'], email=form.get('email'), form_json=json.dumps(form))
    db.session.add(lead)
    db.session.flush()
    quote['number'] = f'BW-{lead.id:06d}'
    # Store the snapshot, so later catalogue updates cannot change this quote.
    lead.result_json = json.dumps({**result, 'quotation': quote})
    render_pdf(lead, quote)  # Validate rendering before committing the request.
    db.session.commit()
    notify(lead, form, result, Recipient.query.all(), include_customer=False)
    path = url_for('quotations.download', lead_id=lead.id, token=quote['token'])
    return jsonify({**result, 'quotation': {k: v for k, v in quote.items() if k != 'token'} | {
        'download_url': path, 'send_url': path.removesuffix('/pdf') + '/send'}})


def get_quotation(lead_id, token):
    lead = db.session.get(Lead, lead_id)
    quote = json.loads(lead.result_json or '{}').get('quotation') if lead else None
    if not quote or not hmac.compare_digest(quote['token'], token):
        abort(404)
    return lead, quote


@bp.get('/api/quotations/<int:lead_id>/<token>/pdf')
def download(lead_id, token):
    lead, quote = get_quotation(lead_id, token)
    return current_app.response_class(render_pdf(lead, quote), mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="BatteryWala-{quote["number"]}.pdf"',
        'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff'})


def valid_email(value):
    return len(value) <= 255 and re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', value)


@bp.post('/api/quotations/<int:lead_id>/<token>/send')
def send_quotation(lead_id, token):
    lead, quote = get_quotation(lead_id, token)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('channel') not in ('email', 'mobile', 'both'):
        return jsonify(error='Choose email, mobile number or both.'), 400
    targets = []
    if data['channel'] in ('email', 'both'):
        email = data.get('email', '')
        if not isinstance(email, str) or not valid_email(email.strip()):
            return jsonify(error='Enter a valid email address.'), 400
        targets.append(('email', email.strip()))
    if data['channel'] in ('mobile', 'both'):
        phone = data.get('phone', '')
        if not isinstance(phone, str) or not re.fullmatch(r'[0-9]{10}', phone.strip()):
            return jsonify(error='Enter a valid 10-digit mobile number.'), 400
        targets.append(('sms', phone.strip()))
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    if Delivery.query.filter(Delivery.lead_id == lead.id, Delivery.created_at >= since,
                             Delivery.channel.in_(['email', 'sms'])).count() + len(targets) > 10:
        return jsonify(error='Too many delivery attempts. Please download the PDF or try again later.'), 429
    pdf = render_pdf(lead, quote)
    results = []
    for channel, target in targets:
        status, detail = 'not_configured', 'Delivery provider is not configured. Please download the PDF.'
        try:
            if channel == 'email' and os.getenv('SMTP_HOST'):
                message = EmailMessage()
                message['Subject'] = f'BatteryWala quotation {quote["number"]}'
                message['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USERNAME')
                message['To'] = target
                message.set_content(f'Hello {lead.name},\n\nYour quotation is attached.\n{quote["message"]}\n\n{quote["note"]}')
                message.add_attachment(pdf, maintype='application', subtype='pdf', filename=f'BatteryWala-{quote["number"]}.pdf')
                with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '587')), timeout=15) as smtp:
                    if os.getenv('SMTP_USE_TLS', 'true').lower() == 'true':
                        smtp.starttls()
                    if os.getenv('SMTP_USERNAME'):
                        smtp.login(os.environ['SMTP_USERNAME'], os.getenv('SMTP_PASSWORD'))
                    smtp.send_message(message)
                status, detail = 'sent', 'Email provider accepted the quotation PDF.'
            elif channel == 'sms' and os.getenv('SMS_WEBHOOK_URL'):
                # SMS carries a PDF link. Never send a localhost or request-Host-derived URL.
                origin = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
                parsed = urlsplit(origin)
                if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                        or parsed.query or parsed.fragment or parsed.path
                        or parsed.hostname in ('localhost', '127.0.0.1', '::1')):
                    detail = 'Mobile delivery needs a public HTTPS PUBLIC_BASE_URL. Please download the PDF.'
                else:
                    link = origin + url_for('quotations.download', lead_id=lead.id, token=token)
                    body = f'BatteryWala quotation {quote["number"]}: {link}\n{quote["message"]}\n{quote["note"]}'
                    req = urllib.request.Request(os.environ['SMS_WEBHOOK_URL'],
                        data=json.dumps({'to': target, 'message': body}).encode(),
                        headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=15) as response:
                        response.read()
                    status, detail = 'sent', 'Mobile provider accepted the quotation link.'
        except Exception:
            current_app.logger.warning('Quotation %s %s delivery failed', quote['number'], channel)
            status, detail = 'failed', 'Delivery failed. Please retry or download the PDF.'
        db.session.add(Delivery(lead_id=lead.id, channel=channel, target=target, status=status, detail=detail))
        results.append({'channel': 'mobile' if channel == 'sms' else channel, 'status': status, 'message': detail})
    db.session.commit()
    return jsonify(deliveries=results)
