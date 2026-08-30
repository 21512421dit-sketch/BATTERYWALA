import re,json,os,smtplib,urllib.error,urllib.request,urllib.parse
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
def serpapi_predict(form,key):
 domains=tuple(x.strip().lower() for x in os.getenv('BATTERY_SEARCH_ALLOWED_DOMAINS',','.join(DEFAULT_SEARCH_DOMAINS)).split(',') if x.strip())
 terms=battery_search_terms(form)
 if not terms:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No battery-fitment details were available to search.','sources':[],'records':[]}
 query=('suggest a battery for:'+' '.join(terms))[:500]
 def fetch(params):
  url='https://serpapi.com/search.json?'+urllib.parse.urlencode(params)
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/json'}),timeout=20) as response:return json.loads(response.read())
  except urllib.error.HTTPError as error:
   if error.code in (401,403):raise SearchUnavailable('Google search rejected the SerpApi key.') from error
   raise SearchUnavailable('Google search is temporarily unavailable.') from error
  except Exception as error:raise SearchUnavailable('Google search is temporarily unavailable.') from error
 payload=fetch({'engine':'google','q':query,'api_key':key,'num':10,'location':'India','hl':'en'})
 overview=payload.get('ai_overview') or {}
 if overview.get('page_token'):overview=fetch({'engine':'google_ai_overview','page_token':overview['page_token'],'api_key':key}).get('ai_overview',{})
 def allowed(link):
  host=(urllib.parse.urlsplit(link).hostname or '').lower()
  return any(host==domain or host.endswith('.'+domain) for domain in domains)
 refs=overview.get('references',[]);sources=[{'title':str(ref.get('title',''))[:160],'url':ref.get('link',''),'domain':urllib.parse.urlsplit(ref.get('link','')).hostname} for ref in refs if allowed(ref.get('link',''))]
 blocks=overview.get('text_blocks',[])
 text=' '.join(str(block.get('snippet','')) for block in blocks)
 if text and sources:
  excluded={token.upper() for value in terms for token in re.findall(r'[A-Za-z0-9./-]+',value)};candidates={}
  for model in re.findall(r'\b(?=[A-Z0-9./-]{3,24}\b)(?=[A-Z0-9./-]*[A-Z])(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]+\b',text.upper()):
   if model not in excluded and not re.fullmatch(r'\d+(?:\.\d+)?(?:V|AH|KW|CC|F|M|Y)',model):candidates[model]=candidates.get(model,0)+1
  if candidates:
   model,count=max(candidates.items(),key=lambda pair:pair[1]);brand=next((label for token,label in (('EXIDE','EXIDE'),('AMARON','AMARON'),('LIVGUARD','LIVGUARD'),('LUMINOUS','LUMINOUS'),('SF SONIC','SF SONIC')) if token in text.upper()),None);capacity=re.search(r'\b(\d+(?:\.\d+)?)\s*AH\b',text,re.I);record={'source_type':'web','model_no':model,'brand':brand,'capacity_ah':float(capacity.group(1)) if capacity else None,'vehicle_model':fitment_label(form),'source':sources[0]['domain'],'source_url':sources[0]['url']};return {'prediction':record,'confidence':'high' if count>1 else 'medium','needs_manual_review':count<2,'message':'Google AI Overview recommendation. Confirm OEM fitment, dimensions, terminal orientation and warranty before sale.','sources':sources,'records':[record],'shared_fields':[name for name in SEARCH_FIELDS if form.get(name)]}
 return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'Google did not return a verified battery model from approved sources.','sources':sources,'records':[]}
def serper_predict(form,key):
 domains=tuple(x.strip().lower() for x in os.getenv('BATTERY_SEARCH_ALLOWED_DOMAINS',','.join(DEFAULT_SEARCH_DOMAINS)).split(',') if x.strip())
 terms=battery_search_terms(form)
 if not terms:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No battery-fitment details were available to search.','sources':[],'records':[]}
 query=('compatible battery model capacity Ah '+' '.join(terms)+' ('+' OR '.join('site:'+d for d in domains)+')')[:500]
 body=json.dumps({'q':query,'num':10}).encode()
 try:
  request=urllib.request.Request('https://google.serper.dev/search',data=body,headers={'Content-Type':'application/json','X-API-KEY':key})
  with urllib.request.urlopen(request,timeout=15) as response:payload=json.loads(response.read())
 except urllib.error.HTTPError as error:
  if error.code in (401,403):raise SearchUnavailable('Google search rejected the Serper API key.') from error
  raise SearchUnavailable('Google search is temporarily unavailable.') from error
 except Exception as error:raise SearchUnavailable('Google search is temporarily unavailable.') from error
 def allowed(link):
  host=(urllib.parse.urlsplit(link).hostname or '').lower()
  return any(host==domain or host.endswith('.'+domain) for domain in domains)
 items=[item for item in payload.get('organic',[]) if allowed(item.get('link',''))]
 sources=[{'title':re.sub(r'\s+',' ',item.get('title','')).strip()[:160],'url':item['link'],
           'domain':urllib.parse.urlsplit(item['link']).hostname} for item in items[:5]]
 excluded={token.upper() for value in terms for token in re.findall(r'[A-Za-z0-9./-]+',value)}; candidates={};evidence={}
 for item in items:
  text=' '.join((item.get('title',''),item.get('snippet',''))).upper()
  for model in re.findall(r'\b(?=[A-Z0-9./-]{3,24}\b)(?=[A-Z0-9./-]*[A-Z])(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]+\b',text):
   if model in excluded or re.fullmatch(r'\d+(?:\.\d+)?(?:V|AH|KW|CC|F|M|Y)',model):continue
   candidates[model]=candidates.get(model,0)+1;evidence.setdefault(model,item)
 if not candidates:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'Google returned trusted sources, but no battery model could be extracted safely.','sources':sources,'records':[]}
 model,count=max(candidates.items(),key=lambda pair:pair[1]);item=evidence[model];text=' '.join((item.get('title',''),item.get('snippet','')))
 brand=next((label for token,label in (('EXIDE','EXIDE'),('AMARON','AMARON'),('LIVGUARD','LIVGUARD'),('LUMINOUS','LUMINOUS'),('SF SONIC','SF SONIC')) if token in text.upper()),None)
 capacity=re.search(r'\b(\d+(?:\.\d+)?)\s*AH\b',text,re.I);capacity=float(capacity.group(1)) if capacity else None
 record={'source_type':'web','model_no':model,'brand':brand,'capacity_ah':capacity,'vehicle_model':fitment_label(form),'source':sources[0]['domain'],'source_url':sources[0]['url']}
 confidence='high' if count>1 else 'medium'
 return {'prediction':record,'confidence':confidence,'needs_manual_review':confidence!='high','message':'Google recommendation only. Confirm OEM fitment, dimensions, terminal orientation and warranty before sale.','sources':sources,'records':[record],'shared_fields':[name for name in SEARCH_FIELDS if form.get(name)]}
def web_predict(form):
 if os.getenv('SERPER_API_KEY'):return serper_predict(form,os.getenv('SERPER_API_KEY'))
 if os.getenv('SERPAPI_API_KEY'):return serpapi_predict(form,os.getenv('SERPAPI_API_KEY'))
 key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_SEARCH_API_KEY')
 if not key:raise SearchUnavailable('Gemini Google Search is not configured.')
 domains=tuple(x.strip().lower() for x in os.getenv('BATTERY_SEARCH_ALLOWED_DOMAINS',','.join(DEFAULT_SEARCH_DOMAINS)).split(',') if x.strip())
 terms=battery_search_terms(form)
 if not terms:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No battery-fitment details were available to search.','sources':[],'records':[]}
 prompt=('Find the compatible lead-acid battery for these fitment details: '+'; '.join(terms)+'. '
         'Use Google Search and only evidence from these manufacturer domains: '+', '.join(domains)+'. '
         'Return only one JSON object with keys model_no, brand, capacity_ah, confidence and summary. '
         'confidence must be high, medium or low. Use null model_no if trustworthy evidence is insufficient.')
 body=json.dumps({'contents':[{'parts':[{'text':prompt}]}],'tools':[{'google_search':{}}],
                  'generationConfig':{'temperature':0,'maxOutputTokens':256}}).encode()
 model=os.getenv('GEMINI_MODEL','gemini-3.1-flash-lite')
 url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
 try:
  request=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','x-goog-api-key':key})
  with urllib.request.urlopen(request,timeout=20) as response:payload=json.loads(response.read())
 except urllib.error.HTTPError as error:
  if error.code==429:raise SearchUnavailable('Google Search quota is exhausted. Enable Gemini API billing or wait for the quota reset.') from error
  if error.code in (401,403):raise SearchUnavailable('Google rejected the Gemini API key or its permissions.') from error
  raise SearchUnavailable('Google battery search is temporarily unavailable.') from error
 except Exception as error:raise SearchUnavailable('Google battery search is temporarily unavailable.') from error
 candidate=(payload.get('candidates') or [{}])[0]
 text=''.join(part.get('text','') for part in candidate.get('content',{}).get('parts',[]))
 try:answer=json.loads(text[text.index('{'):text.rindex('}')+1])
 except Exception as error:raise SearchUnavailable('Google returned an unreadable battery result.') from error
 chunks=candidate.get('groundingMetadata',{}).get('groundingChunks',[]);sources=[]
 for chunk in chunks:
  web=chunk.get('web',{});title=re.sub(r'\s+',' ',web.get('title','')).strip();link=web.get('uri','')
  label=title.lower().removeprefix('www.')
  if link and any(label==domain or label.endswith('.'+domain) for domain in domains):
   sources.append({'title':title[:160],'url':link,'domain':title[:80]})
 if not answer.get('model_no') or not sources:return {'prediction':None,'confidence':'low','needs_manual_review':True,
  'message':'Google did not find a battery model supported by an approved manufacturer source.','sources':sources,'records':[]}
 confidence=answer.get('confidence') if answer.get('confidence') in ('high','medium','low') else 'low'
 record={'source_type':'web','model_no':str(answer['model_no'])[:80],'brand':str(answer.get('brand') or '')[:80] or None,
         'capacity_ah':num(answer.get('capacity_ah')),
         'vehicle_model':fitment_label(form),
         'source':sources[0]['domain'],'source_url':sources[0]['url']}
 return {'prediction':record,'confidence':confidence,'needs_manual_review':confidence!='high',
         'message':str(answer.get('summary') or 'Web recommendation only. Confirm OEM fitment before sale.')[:500],
         'sources':sources,'records':[record],'shared_fields':[name for name in SEARCH_FIELDS if form.get(name)]}
def predict(form):
 qs=set(norm(' '.join(str(v) for v in form.values())).split()); ranked=[]
 for r in load_data().get('records',[]):
  if r.get('source_type')=='scrap': continue
  text=norm(' '.join(str(v) for v in r.items())); overlap=len(qs & set(text.split())); score=overlap*5
  wanted=norm(form.get('model_no')); model=norm(r.get('model_no'))
  model_match=bool(wanted and model and wanted==model)
  if wanted and model: score += 80 if model_match else -30
  application=norm(form.get('application_key') or form.get('application'))
  application_match=bool(application and application==norm(r.get('application')))
  if application_match:score+=25
  req=num(form.get('capacity_ah')); got=num(r.get('capacity_ah'))
  capacity_match=bool(req and got and req==got)
  if req and got: score+=35 if capacity_match else max(-20,10-abs(req-got))
  requested_vehicle=form.get('vehicle_model') or form.get('vehicle_details')
  vehicle_match=bool(requested_vehicle and r.get('vehicle_model') and
                     norm(requested_vehicle)==norm(r['vehicle_model']))
  if vehicle_match:score+=80
  if score: ranked.append((score,r,model_match or vehicle_match,capacity_match and application_match))
 ranked.sort(key=lambda x:-x[0]); top=ranked[0] if ranked else None
 if not top:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No verified match was found. The admin team will review your request.'}
 score,r,exact_match,capacity_match=top
 confidence='high' if exact_match else 'medium' if capacity_match else 'low'
 return {'prediction':{k:r.get(k) for k in ('model_no','brand','capacity_ah','dealer_price','mrp','warranty','warranty_months','source')},'confidence':confidence,'needs_manual_review':confidence=='low','message':'Confirm dimensions, terminal orientation, OEM fitment and warranty before sale.'}

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
