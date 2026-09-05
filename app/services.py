import re,json,os,smtplib,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime,timezone
from . import db
from .models import Delivery
BASE=Path(__file__).resolve().parent
DATA=BASE/'data/current_pricing.json'
CATALOGS=BASE/'data/catalogs'
SCHEMAS=BASE/'data/form_schemas.json'
def norm(v): return re.sub(r'[^a-z0-9]+',' ',str(v or '').lower()).strip()
def num(v):
 try:return float(str(v).replace(',',''))
 except:return None
def load_data():
 records=[]; sources=[]
 for path in sorted(CATALOGS.glob('*.json')) if CATALOGS.exists() else []:
  payload=json.loads(path.read_text(encoding='utf-8'));records.extend(payload.get('records',[]));sources.append(path.name)
 if DATA.exists():
  legacy=json.loads(DATA.read_text(encoding='utf-8'))
  records.extend(legacy.get('records',[]));sources.append(DATA.name)
 return {'schema_version':'2.0','records':records,'catalogs':sources}
VEHICLE_APPLICATIONS=(('three_wheeler','Three Wheeler'),('four_wheeler','Four Wheeler'),
 ('commercial_vehicle','Commercial Vehicle'),('bus','Bus'),('truck','Truck'),('tractor','Tractor'),
 ('earth_mover','Earth Mover'))
def load_form_schemas():
 data=json.loads(SCHEMAS.read_text(encoding='utf-8'));applications=data['new']['applications'];expanded={}
 for key,schema in applications.items():
  if key!='vehicle':expanded[key]=schema;continue
  fields=[field for field in schema['fields'] if field['name']!='vehicle_type']
  for vehicle_key,label in VEHICLE_APPLICATIONS:expanded[vehicle_key]={**schema,'label':label,'fields':fields}
 data['new']['applications']=expanded
 return data
def validate_form(form):
 mode=form.get('solution_type','new'); application=form.get('application_key')
 schema=load_form_schemas().get(mode,{}).get('applications',{}).get(application)
 if not schema:return ['solution_type','application_key']
 missing=[]
 for field in schema['fields']:
  visible=all(str(form.get(k,''))==str(v) for k,v in field.get('show_when',{}).items())
  if visible and field.get('required') and not str(form.get(field['name'],'')).strip():missing.append(field['name'])
 return missing
def fitment_application(value):
 key=norm(value).replace(' ','_')
 return {'bus':'commercial_vehicle','truck':'commercial_vehicle','car_suv_muv':'four_wheeler'}.get(key,key)
class SearchUnavailable(RuntimeError): pass
SEARCH_FIELDS=('application','application_key','vehicle_type','vehicle_make','vehicle_model','registration_year',
               'generator_make','generator_model','generator_capacity_kw','generator_year','fuel_type',
               'capacity_ah','voltage','new_battery_height','new_battery_width','new_battery_depth','model_no',
               'old_capacity_ah','old_voltage','vehicle_details','generator_details','new_dimensions')
DEFAULT_SEARCH_DOMAINS=('exidecare.com','amaron.com','livguard.com','luminousindia.com','sfsonicpower.com')
def battery_search_terms(form):
 values=[]
 for name in SEARCH_FIELDS:
  value=str(form.get(name,'')).strip()
  if not value:continue
  value=re.sub(r'\b[A-Z]{2}[- ]?\d{1,2}[- ]?[A-Z]{1,3}[- ]?\d{1,4}\b',' ',value,flags=re.I)
  value=re.sub(r'[^A-Za-z0-9 ./+()\-]',' ',value)
  value=re.sub(r'\s+',' ',value).strip()[:80]
  if value:values.append(value)
 return values
def fitment_label(form):
 values=(form.get('vehicle_make'),form.get('vehicle_model'),form.get('registration_year'),
         form.get('generator_make'),form.get('generator_model'),form.get('generator_year'))
 return ' '.join(str(value).strip() for value in values if value) or form.get('vehicle_details') or form.get('generator_details')
def serpbase_predict(form,key):
 domains=tuple(x.strip().lower() for x in os.getenv('BATTERY_SEARCH_ALLOWED_DOMAINS',','.join(DEFAULT_SEARCH_DOMAINS)).split(',') if x.strip())
 terms=battery_search_terms(form)
 if not terms:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No battery-fitment details were available to search.','sources':[],'records':[]}
 query=('compatible battery model capacity Ah '+' '.join(terms)+' ('+' OR '.join('site:'+d for d in domains)+')')[:500]
 body=json.dumps({'q':query,'hl':'en','gl':'in','device':'default'}).encode()
 endpoint=os.getenv('SERPBASE_BASE_URL','https://api.serpbase.dev').rstrip('/')+'/google/search'
 try:
  req=urllib.request.Request(endpoint,data=body,headers={
   'Content-Type':'application/json','Accept':'application/json','X-API-Key':key,
   'User-Agent':'BatteryWala/1.0','X-SerpBase-Source':'batterywala'})
  with urllib.request.urlopen(req,timeout=int(os.getenv('SERPBASE_TIMEOUT','20'))) as response:payload=json.loads(response.read())
 except urllib.error.HTTPError as error:
  if error.code==401:raise SearchUnavailable('Serpbase rejected the API key. Check SERPBASE_API_KEY.') from error
  if error.code==403:raise SearchUnavailable('Serpbase blocked the search request (HTTP 403). Check the key permissions or Serpbase account access.') from error
  raise SearchUnavailable('Google search is temporarily unavailable.') from error
 except Exception as error:raise SearchUnavailable('Google search is temporarily unavailable.') from error
 if payload.get('status') not in (None,0):raise SearchUnavailable('Google search could not complete the request.')
 def allowed(link):
  host=(urllib.parse.urlsplit(link).hostname or '').lower()
  return any(host==domain or host.endswith('.'+domain) for domain in domains)
 items=[item for item in payload.get('organic',[]) if allowed(item.get('link') or item.get('url',''))]
 sources=[{'title':re.sub(r'\s+',' ',str(item.get('title',''))).strip()[:160],
           'url':item.get('link') or item.get('url'),'domain':urllib.parse.urlsplit(item.get('link') or item.get('url')).hostname}
          for item in items[:5]]
 excluded={token.upper() for value in terms for token in re.findall(r'[A-Za-z0-9./-]+',value)};candidates={};evidence={}
 for item in items:
  text=' '.join((str(item.get('title','')),str(item.get('snippet','')))).upper()
  for model in re.findall(r'\b(?=[A-Z0-9./-]{3,24}\b)(?=[A-Z0-9./-]*[A-Z])(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]+\b',text):
   if model in excluded or re.fullmatch(r'\d+(?:\.\d+)?(?:V|AH|KW|CC|F|M|Y)',model):continue
   candidates[model]=candidates.get(model,0)+1;evidence.setdefault(model,item)
 if not candidates:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'Google returned trusted sources, but no battery model could be extracted safely.','sources':sources,'records':[]}
 model,count=max(candidates.items(),key=lambda pair:pair[1]);item=evidence[model];text=' '.join((str(item.get('title','')),str(item.get('snippet',''))))
 brand=next((label for token,label in (('EXIDE','EXIDE'),('AMARON','AMARON'),('LIVGUARD','LIVGUARD'),('LUMINOUS','LUMINOUS'),('SF SONIC','SF SONIC')) if token in text.upper()),None)
 capacity=re.search(r'\b(\d+(?:\.\d+)?)\s*AH\b',text,re.I)
 record={'source_type':'web','model_no':model,'brand':brand,'capacity_ah':float(capacity.group(1)) if capacity else None,
         'vehicle_model':fitment_label(form),'source':sources[0]['domain'],'source_url':sources[0]['url']}
 confidence='high' if count>1 else 'medium'
 return {'prediction':record,'confidence':confidence,'needs_manual_review':confidence!='high',
         'message':'Google recommendation only. Confirm OEM fitment, dimensions, terminal orientation and warranty before sale.',
         'sources':sources,'records':[record],'shared_fields':[name for name in SEARCH_FIELDS if form.get(name)]}
def predict(form):
 key=os.getenv('SERPBASE_API_KEY')
 if not key:raise SearchUnavailable('Google search is not configured. Add SERPBASE_API_KEY to .env and restart the server.')
 return serpbase_predict(form,key)

def _brand(text):
 upper=text.upper()
 for token,label in (('EXIDE','EXIDE'),('AMARON','AMARON'),('PRYCAL','PMK-PRYCAL'),('LIVGUARD','LIVGUARD'),('LUMINOUS','LUMINOUS'),('SF SONIC','SF SONIC')):
  if token in upper:return label
 return 'UNCLASSIFIED'
def _application(section):
 value=norm(section)
 if '2 wheeler' in value:return 'two_wheeler'
 if 'generator' in value:return 'generator'
 if 'inverter' in value or 'tubular' in value:return 'inverter'
 if 'ups' in value or 'smf' in value:return 'online_ups'
 if 'forklift' in value or 'traction' in value:return 'forklift_stacker'
 return 'vehicle'
def _record(source,source_type,page,brand,model=None,capacity=None,application=None,**prices):
 return {'source':source,'source_type':source_type,'page':page,'brand':brand,'model_no':model,
         'capacity_ah':capacity,'application':application,**prices}
def _parse_text(text,source,source_type,page,brand):
 records=[]; section=''
 money_re=r'\d[\d,]*(?:\.\d+)?'
 for raw in text.splitlines():
  line=re.sub(r'\s+',' ',raw).strip(); upper=line.upper()
  if not line:continue
  if any(word in upper for word in ('CAR/SUV:','2-WHEELER:','TRACTOR:','E-RICKSHAW:','AUTOMOTIVE SERIES')):section=line
  if source_type=='scrap':
   values=[float(x.replace(',','')) for x in re.findall(money_re,line)]
   if len(values)>=6:
    for offset in (0,3):
     records.append(_record(source,source_type,page,brand,capacity=values[offset],application='scrap',scrap_price=values[offset+1],unbranded_scrap_price=values[offset+2]))
   continue
  for match in re.finditer(rf'(?P<ah>\d+(?:\.\d+)?)\s+(?P<model>[A-Z0-9][A-Z0-9()./+\-]{{2,30}})\s+(?P<warranty>(?:\d{{1,2}}[A-Z](?:\+\d{{1,2}}[A-Z])?|\d{{1,2}}M FOC|NA))\s+(?P<price>{money_re})',upper):
   records.append(_record(source,source_type,page,brand,match['model'],float(match['ah']),_application(section),mrp=float(match['price'].replace(',','')),warranty=match['warranty']))
  prycal=re.search(rf'\b(PN(?:S)?\s+[A-Z0-9 /]+|DIN\s+[A-Z0-9 /]+)\s+(\d{{1,3}})\s+18\s*\+\s*18\s+36\D+({money_re})\s+({money_re})',upper)
  if prycal:records.append(_record(source,source_type,page,brand,re.sub(r'\s+',' ',prycal[1]),float(prycal[2]),'vehicle',dealer_price=float(prycal[3].replace(',','')),mrp=float(prycal[4].replace(',','')),warranty='18+18 months'))
  amaron=re.search(rf'\b((?:AAM|AMS)-[A-Z0-9-]+)\s+({money_re})\s*$',upper)
  if amaron:records.append(_record(source,source_type,page,brand,amaron[1],application='vehicle',mrp=float(amaron[2].replace(',',''))))
 return records
def extract_document(path,source_type='retail'):
 import fitz
 from PIL import Image
 import pytesseract
 path=Path(path); pages=[]
 if path.suffix.lower()=='.pdf':
  with fitz.open(path) as document:
   for page in document:
    text=page.get_text('text').strip()
    if len(re.sub(r'\s+','',text))<80:
     pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
     text=pytesseract.image_to_string(Image.frombytes('RGB',[pix.width,pix.height],pix.samples),config='--psm 6')
    pages.append(text)
 else:
  with Image.open(path) as image:pages.append(pytesseract.image_to_string(image.convert('RGB'),config='--psm 6'))
 joined='\n'.join(pages);brand=_brand(joined);records=[]
 for page,text in enumerate(pages,1):records.extend(_parse_text(text,path.name,source_type,page,brand))
 unique={record_key(r):r for r in records if r.get('model_no') or r.get('capacity_ah') is not None}
 if not unique:raise ValueError('No battery price records could be extracted. Upload a clear table with model/capacity and price columns.')
 return {'schema_version':'2.0','generated_at':datetime.now(timezone.utc).isoformat(),'records':list(unique.values())}
extract_pdf=extract_document
def record_key(record):
 if record.get('source_type')=='scrap':return '|'.join(('scrap',norm(record.get('application')),str(num(record.get('capacity_ah')))))
 model=norm(record.get('model_no'))
 return '|'.join((norm(record.get('brand')),model or 'capacity',model or str(num(record.get('capacity_ah')))))
def _catalog_name(record):return re.sub(r'[^a-z0-9]+','-',norm(record.get('brand') or 'unclassified')).strip('-')+'-'+record.get('source_type','retail')+'.json'
def publish(payload):
 CATALOGS.mkdir(parents=True,exist_ok=True);catalogs={}
 for path in CATALOGS.glob('*.json'):catalogs[path.name]=json.loads(path.read_text(encoding='utf-8'))
 locations={record_key(record):(name,index) for name,data in catalogs.items() for index,record in enumerate(data.get('records',[]))}
 added=updated=0
 for record in payload['records']:
  key=record_key(record)
  if key in locations:
   name,index=locations[key];catalogs[name]['records'][index]=record;updated+=1
  else:
   name=_catalog_name(record);data=catalogs.setdefault(name,{'schema_version':'2.0','records':[]})
   locations[key]=(name,len(data['records']));data['records'].append(record);added+=1
 for name,data in catalogs.items():
  data['updated_at']=payload.get('generated_at');target=CATALOGS/name;tmp=target.with_suffix('.tmp')
  tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');tmp.replace(target)
 return {'added':added,'updated':updated,'catalogs':len(catalogs)}
def notify(lead,form,result,recipients,include_customer=True):
 subject=f"BatteryWala recommendation for {lead.name}"; body=f"Hello {lead.name},\n\nRecommendation: {json.dumps(result,indent=2)}\n\nRequest: {json.dumps(form,indent=2)}"
 targets=[]
 if include_customer and lead.email: targets.append(('email',lead.email))
 if include_customer and lead.phone: targets.append(('sms',lead.phone))
 targets += [(r.kind,r.value) for r in recipients if r.active]
 for channel,target in targets:
  status='queued'; detail='Provider not configured'
  try:
   if channel=='email' and os.getenv('SMTP_HOST'):
    m=EmailMessage();m['Subject']=subject;m['From']=os.getenv('SMTP_FROM') or os.getenv('SMTP_USERNAME');m['To']=target;m.set_content(body)
    with smtplib.SMTP(os.getenv('SMTP_HOST'),int(os.getenv('SMTP_PORT','587')),timeout=15) as s:
     if os.getenv('SMTP_USE_TLS','true').lower()=='true':s.starttls()
     if os.getenv('SMTP_USERNAME'):s.login(os.getenv('SMTP_USERNAME'),os.getenv('SMTP_PASSWORD'))
     s.send_message(m)
    status='sent';detail='SMTP accepted'
   elif channel=='sms' and os.getenv('SMS_WEBHOOK_URL'):
    req=urllib.request.Request(os.getenv('SMS_WEBHOOK_URL'),data=json.dumps({'to':target,'message':body[:1000]}).encode(),headers={'Content-Type':'application/json'}); urllib.request.urlopen(req,timeout=15).read();status='sent';detail='Webhook accepted'
  except Exception as e: status='failed';detail=str(e)[:500]
  db.session.add(Delivery(lead_id=lead.id,channel=channel,target=target,status=status,detail=detail))
 db.session.commit()
