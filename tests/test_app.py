import os,json
from pathlib import Path
os.environ['ADMIN_EMAIL']='admin@test.local';os.environ['ADMIN_PASSWORD']='TestPass123!'
from app import create_app

def test_health_and_validation(tmp_path):
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'t.db'),'SECRET_KEY':'test'})
 c=app.test_client(); page=c.get('/'); assert page.status_code==200
 assert b'/static/site-updates.css' in page.data
 assert b'/static/site-updates.js' in page.data
 assert b"sessionStorage.setItem('bwRestoreSeen','1')" in page.data
 r=c.post('/api/predict',json={}); assert r.status_code==400

def test_prototype_form_submission(tmp_path):
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'prototype.db'),'SECRET_KEY':'test'})
 c=app.test_client(); r=c.post('/api/predict',json={'name':'Test User','phone':'9876543210','pincode':'110001','battery_type':'Automotive','application':'Passenger vehicle'})
 assert r.status_code==200
 assert 'prediction' in r.get_json()

def test_dynamic_form_schema_and_conditional_validation(tmp_path):
 from app.services import validate_form
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'forms.db'),'SECRET_KEY':'test'})
 c=app.test_client(); schemas=c.get('/api/form-schemas')
 assert schemas.status_code==200
 assert set(schemas.json)=={'new','restoration'}
 assert len(schemas.json['new']['applications'])==12
 assert all(key in schemas.json['new']['applications'] for key in
            ('three_wheeler','four_wheeler','commercial_vehicle','bus','truck','tractor','earth_mover'))
 vehicle_fields={field['name'] for field in schemas.json['new']['applications']['four_wheeler']['fields']}
 assert {'vehicle_make','vehicle_model','brand','city','pincode'} <= vehicle_fields
 assert 'registration_year' not in vehicle_fields
 assert 'vehicle_details' not in vehicle_fields and 'vehicle_type' not in vehicle_fields
 form={'solution_type':'new','application_key':'inverter','name':'A','phone':'9876543210',
       'capacity_ah':'150','quantity':'2','city':'Pune','pincode':'411001','exchange_old_battery':'no'}
 assert validate_form(form)==[]
 assert validate_form(form|{'exchange_old_battery':'yes'})==['old_capacity_ah','old_quantity']
 script=c.get('/static/site-updates.js').data
 assert b'/api/form-schemas' in script and b'data-dynamic-fields' in script
 assert b"predictionPanel.replaceChildren()" in script and b"predictionPanel.style.display = 'none'" in script
 page=c.get('/').data
 assert b'note.textContent = j.message' not in page and b'box.append(sources)' not in page
 quotation_script=c.get('/static/quotation.js').data
 assert b'data-quote-download' not in quotation_script
 assert b'Choose email, mobile number, or both.' in quotation_script
 assert b'You can still download' not in quotation_script


def test_sqlite_fitment_lookup_and_dependent_options(tmp_path,monkeypatch):
 from app import services
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'fitments.db'),'SECRET_KEY':'test'})
 monkeypatch.setattr(services.urllib.request,'urlopen',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('network used')))
 c=app.test_client()
 makes=c.get('/api/fitment-options?field=makes&application=four_wheeler').json['options']
 assert any(make.casefold()=='ashok leyland' for make in makes)
 models=c.get('/api/fitment-options?field=models&application=four_wheeler&make=ASHOK%20LEYLAND').json['options']
 assert 'Stile' in models
 form={'application_key':'four_wheeler','vehicle_make':'Ashok Leyland','vehicle_model':'Stile','fuel_type':'Diesel'}
 with app.app_context():result=services.predict(form)
 assert result['confidence']=='high' and result['records']
 assert all(record['source']=='SQLite fitment database' for record in result['records'])
 assert {'Amaron','PowerZone'} <= {record['brand'] for record in result['records']}

def test_catalog_publish_upserts_without_deleting_other_records(tmp_path, monkeypatch):
 from app import services
 catalogs=tmp_path/'catalogs'; legacy=tmp_path/'legacy.json'
 legacy.write_text('{"records": []}',encoding='utf-8')
 monkeypatch.setattr(services,'CATALOGS',catalogs);monkeypatch.setattr(services,'DATA',legacy)
 first={'generated_at':'one','records':[
  {'source_type':'retail','brand':'EXIDE','model_no':'X1','capacity_ah':35,'mrp':100},
  {'source_type':'retail','brand':'AMARON','model_no':'A1','capacity_ah':40,'mrp':200}]}
 assert services.publish(first)=={'added':2,'updated':0,'catalogs':2}
 second={'generated_at':'two','records':[
  {'source_type':'retail','brand':'EXIDE','model_no':'X1','capacity_ah':35,'mrp':125},
  {'source_type':'retail','brand':'EXIDE','model_no':'X2','capacity_ah':45,'mrp':300}]}
 assert services.publish(second)=={'added':1,'updated':1,'catalogs':2}
 records=services.load_data()['records']
 assert len(records)==3
 assert next(r for r in records if r['model_no']=='X1')['mrp']==125
 assert next(r for r in records if r['model_no']=='A1')['mrp']==200

def test_login(tmp_path):
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'t2.db'),'SECRET_KEY':'test'})
 c=app.test_client(); page=c.get('/admin/login'); assert page.status_code==200
 import re
 token=re.search(b'name="csrf" value="([^"]+)',page.data).group(1).decode()
 r=c.post('/admin/login',data={'csrf':token,'email':'admin@test.local','password':'TestPass123!'},follow_redirects=False);assert r.status_code==302


def test_quotation_generation_and_delivery(tmp_path, monkeypatch):
 import fitz
 from app import quotations, db
 from app.models import Delivery, Lead
 from decimal import Decimal
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'quotes.db'),'SECRET_KEY':'test'})
 c=app.test_client()
 for key in ('SMTP_HOST','SMS_WEBHOOK_URL','PUBLIC_BASE_URL'):
  monkeypatch.delenv(key, raising=False)
 record={'source_type':'retail','model_no':'35B20L','brand':'Exide','capacity_ah':35,'mrp':5096,
         'selling_price':'3500.51','exchange_value':500,'warranty':'24+12 months','dealer_price':100}
 monkeypatch.setattr(quotations,'load_data',lambda:{'records':[record]})
 monkeypatch.setattr(quotations,'predict',lambda form:{
  'prediction':record,'confidence':'high','needs_manual_review':False,'message':'Web match.',
  'sources':[{'title':'Official result','url':'https://www.exidecare.com/result','domain':'www.exidecare.com'}],
  'records':[record]})
 payload={'name':'Rahul Sharma','phone':'9876543210','email':'rahul@example.com','pincode':'411001',
          'battery_type':'Automotive','application':'Passenger vehicle','car_model':'Alto',
          'model_no':'35B20L','capacity_ah':'35','exchange_old_battery':'yes'}
 assert c.post('/api/quotations',json={}).status_code==400
 assert c.post('/api/quotations',json=[]).status_code==400
 for change in ({'exchange_old_battery':'maybe'},{'phone':'bad'},{'email':'bad'}, {'name':'x'*121},
                {'capacity_ah':'NaN'},{'name':['bad']}):
  assert c.post('/api/quotations',json=payload|change).status_code==400
 for exchange, expected in [('yes','3000.51'),('no','3500.51')]:
  response=c.post('/api/quotations',json=payload|{'exchange_old_battery':exchange,'selling_price':'1'})
  assert response.status_code==200
  quote=response.json['quotation']
  assert quote['options'][0]['price']==expected
  assert quote['status']=='priced'
  assert 'download_url' not in quote
  pdf_path=quote['send_url'].removesuffix('/send')+'/pdf'
  pdf=c.get(pdf_path)
  assert pdf.status_code==200 and pdf.mimetype=='application/pdf'
  assert 'attachment' in pdf.headers['Content-Disposition']
  with fitz.open(stream=pdf.data,filetype='pdf') as doc:
   assert len(doc)==1
   assert len(doc[0].get_images())==1
   assert abs(doc[0].rect.width-595.28)<0.01
   assert abs(doc[0].search_for('Rahul Sharma')[0].x1-563.28)<0.01
   price_span=next(s for b in doc[0].get_text('dict')['blocks'] if 'lines' in b for line in b['lines']
                   for s in line['spans'] if s['text']==f'Rs.{Decimal(expected):,.2f}')
   assert price_span['color']==0x059669 and abs(price_span['origin'][0]-340.6896)<0.01
   content=' '.join(' '.join(page.get_text().split()) for page in doc)
   assert quotations.NOTES[exchange] in content
   assert 'Rahul Sharma' in content and f'{Decimal(expected):,.2f}' in content
  (tmp_path/f'quote-{exchange}.pdf').write_bytes(pdf.data)
 with app.app_context():
  assert Lead.query.count()==2 and Delivery.query.count()==0  # no automatic customer sending
 assert c.get(pdf_path.replace('/pdf','bad/pdf')).status_code==404
 assert c.post(quote['send_url'],json={'channel':'both','email':'bad','phone':payload['phone']}).status_code==400
 assert c.post(quote['send_url'],json={'channel':'fax'}).status_code==400
 assert c.post(quote['send_url'],json={'channel':'mobile','phone':'123'}).status_code==400
 record['selling_price']=9999
 with fitz.open(stream=c.get(pdf_path).data,filetype='pdf') as doc:
  assert '3,500.51' in doc[0].get_text()  # saved quote is stable after price updates
 result=c.post(quote['send_url'],json={'channel':'both','email':payload['email'],'phone':payload['phone']})
 assert [item['status'] for item in result.json['deliveries']]==['not_configured','not_configured']
 messages=[]
 class SMTP:
  def __init__(self,*args,**kwargs): pass
  def __enter__(self): return self
  def __exit__(self,*args): pass
  def starttls(self): pass
  def login(self,*args): pass
  def send_message(self,message): messages.append(message)
 monkeypatch.setenv('SMTP_HOST','smtp.example.com')
 monkeypatch.setenv('SMTP_FROM','quotes@example.com')
 monkeypatch.setattr(quotations.smtplib,'SMTP',SMTP)
 result=c.post(quote['send_url'],json={'channel':'email','email':payload['email']})
 assert result.json['deliveries'][0]['status']=='sent'
 assert len(messages)==1 and messages[0]['To']==payload['email']
 attachment=list(messages[0].iter_attachments())[0]
 assert attachment.get_content_type()=='application/pdf' and attachment.get_payload(decode=True).startswith(b'%PDF')
 requests=[]
 class SMSResponse:
  def __enter__(self): return self
  def __exit__(self,*args): pass
  def read(self): return b'ok'
 def post_sms(req,timeout):
  requests.append(json.loads(req.data))
  return SMSResponse()
 monkeypatch.setenv('SMS_WEBHOOK_URL','https://sms.example.com/send')
 monkeypatch.setattr(quotations.urllib.request,'urlopen',post_sms)
 result=c.post(quote['send_url'],json={'channel':'mobile','phone':payload['phone']})
 assert result.json['deliveries'][0]['status']=='not_configured' and not requests
 monkeypatch.setenv('PUBLIC_BASE_URL','https://batterywala.example')
 result=c.post(quote['send_url'],json={'channel':'both','email':payload['email'],'phone':payload['phone']})
 assert all(item['status']=='sent' for item in result.json['deliveries'])
 assert requests[0]['to']==payload['phone']
 assert 'https://batterywala.example'+pdf_path in requests[0]['message']
 def fail_sms(*args,**kwargs): raise OSError('provider secret must not be returned')
 monkeypatch.setattr(quotations.urllib.request,'urlopen',fail_sms)
 result=c.post(quote['send_url'],json={'channel':'both','email':payload['email'],'phone':payload['phone']})
 assert [item['status'] for item in result.json['deliveries']]==['sent','failed']
 assert b'provider secret' not in result.data
 with app.app_context():
  for _ in range(3): db.session.add(Delivery(lead_id=2,channel='sms',target=payload['phone'],status='sent'))
  db.session.commit()
 assert c.post(quote['send_url'],json={'channel':'email','email':payload['email']}).status_code==429


def test_quotation_missing_prices_and_matching(tmp_path, monkeypatch):
 import fitz, unicodedata
 from app import quotations
 app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'empty.db'),'SECRET_KEY':'test'})
 c=app.test_client()
 records=[]
 monkeypatch.setattr(quotations,'load_data',lambda:{'records':records})
 monkeypatch.setattr(quotations,'predict',lambda form:{
  'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No web match.',
  'sources':[],'records':[]})
 payload={'name':'Customer <b>literal</b>','phone':'9876543210','battery_type':'Automotive',
          'car_model':'Alto','model_no':'35B20L','exchange_old_battery':'yes'}
 quote=c.post('/api/quotations',json=payload).json['quotation']
 assert quote['status']=='pending_review' and not quote['options']
 pdf_path=quote['send_url'].removesuffix('/send')+'/pdf'
 with fitz.open(stream=c.get(pdf_path).data,filetype='pdf') as doc:
  content=unicodedata.normalize('NFKC', ' '.join(doc[0].get_text().split()))
  assert 'Customer <b>literal</b>' in content and 'not a confirmed price offer' in content
 records.append({'source_type':'retail','model_no':'35B20L','mrp':5000,'dealer_price':100})
 assert quotations.quotation_options(payload)[0]['price'] is None
 records[0]['price_with_exchange']='2440.46'
 assert quotations.quotation_options(payload)[0]['price']=='2440.46'
 del records[0]['price_with_exchange']
 records[0]['exchange_value']=6000
 assert quotations.quotation_options(payload)[0]['price'] is None
 assert quotations.quotation_options(payload|{'exchange_old_battery':'no'})[0]['price']=='5000.00'
 assert quotations.quotation_options(payload|{'model_no':'unknown'})==[]
 records[0]['vehicle_model']='Alto'
 assert len(quotations.quotation_options(payload|{'model_no':''}))==1
 records[0]['source_type']='scrap'
 assert quotations.quotation_options(payload)==[]


def test_dynamic_form_details_and_provisional_prediction_render_in_pdf(monkeypatch):
 import fitz
 from types import SimpleNamespace
 from app import quotations
 form={'solution_type':'new','application_key':'two_wheeler','application':'Two Wheeler',
       'name':'Tejas Dale','phone':'7666126132','vehicle_details':'2017, Activa 3G',
       'fuel_type':'Petrol','city_pincode':'Sambhajinagar, 431007','exchange_old_battery':'no'}
 prediction={'prediction':{'brand':'EXIDE','model_no':'XLTZ4A','capacity_ah':4,'mrp':877,
                           'warranty':'24F+24P'}}
 monkeypatch.setattr(quotations,'load_data',lambda:{'records':[]})
 options=quotations.quotation_options(form,prediction)
 assert options[0]['model_no']=='XLTZ4A' and options[0]['provisional'] is True
 lead=SimpleNamespace(name=form['name'],phone=form['phone'],form_json=json.dumps(form))
 quote={'number':'BW-TEST','date':'30/08/2026','note':quotations.NOTES['no'],
        'status':'pending_review','message':'Fitment confirmation required.','options':options}
 with fitz.open(stream=quotations.render_pdf(lead,quote),filetype='pdf') as document:
  text=' '.join(page.get_text() for page in document)
  assert all(value in text for value in ('Tejas Dale','2017, Activa 3G','Sambhajinagar, 431007',
                                          'Exchange old battery','No','XLTZ4A'))


def test_quotation_sample_layout_and_overflow():
 import fitz
 from types import SimpleNamespace
 from app.quotations import render_pdf, NOTES
 lead=SimpleNamespace(name='Layout Customer',phone='9000000000',form_json=json.dumps({
  'city':'Pune','vehicle_brand':'Maruti Suzuki','car_model':'Alto','fuel_type':'Petrol','application':'Passenger vehicle'}))
 option=dict(brand='Exide',model_no='35B20L',capacity_ah='35',mrp='5096',price='3000.51',warranty='24+12 months')
 quote=dict(number='BW-TEST',date='27/08/2026',note=NOTES['no'],status='priced',options=[option]*8)
 with fitz.open(stream=render_pdf(lead,quote),filetype='pdf') as doc:
  spans=[s for b in doc[0].get_text('dict')['blocks'] if 'lines' in b for line in b['lines'] for s in line['spans']]
  assert len(doc)==1
  for text,x,y in [('BatteryWala',74,52.8),('Customer',32,112.15),('Vehicle',32,185.65),
                    ('Battery Options',32,259.15),('Model',123.6848,288.65),('35B20L',123.6848,311.55)]:
   span=next(s for s in spans if s['text']==text)
   assert abs(span['origin'][0]-x)<0.01 and abs(span['origin'][1]-y)<0.01
  footer=next(s for s in spans if s['text'].startswith('Thank you'))
  assert abs(footer['origin'][1]-527.75)<0.01
  assert 'Rahul Sharma' not in doc[0].get_text() and 'Silver-35B20L' not in doc[0].get_text()
 quote['options']=[option]*45
 with fitz.open(stream=render_pdf(lead,quote),filetype='pdf') as doc:
  assert len(doc)>1
  assert sum(page.get_text().count('Rs.3,000.51') for page in doc)==45
  for page in doc:
   assert len(page.get_images())==1 and NOTES['no'] in ' '.join(page.get_text().split())
 quote['options']=[option|{'model_no':'MODEL-'*250}]
 with fitz.open(stream=render_pdf(lead,quote),filetype='pdf') as doc:
  assert len(doc)>1
  for page in doc:
   assert 'Brand' in page.get_text() and 'Thank you' in page.get_text()
