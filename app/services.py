import re,json,hashlib,os,smtplib,urllib.request
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime,timezone
from . import db
from .models import Delivery
BASE=Path(__file__).resolve().parent; DATA=BASE/'data/current_pricing.json'; BACKUP=BASE/'data/pricing_backup.json'
def norm(v): return re.sub(r'[^a-z0-9]+',' ',str(v or '').lower()).strip()
def num(v):
 try:return float(str(v).replace(',',''))
 except:return None
def load_data():
 if not DATA.exists(): DATA.write_text(json.dumps({'records':[]}),encoding='utf-8')
 return json.loads(DATA.read_text(encoding='utf-8'))
def predict(form):
 qs=set(norm(' '.join(str(v) for v in form.values())).split()); ranked=[]
 for r in load_data().get('records',[]):
  if r.get('source_type')=='scrap': continue
  text=norm(' '.join(str(v) for v in r.items())); overlap=len(qs & set(text.split())); score=overlap*8
  req=num(form.get('capacity_ah')); got=num(r.get('capacity_ah'))
  if req and got: score+=max(0,20-abs(req-got))
  if score: ranked.append((score,r))
 ranked.sort(key=lambda x:-x[0]); top=ranked[0] if ranked else None
 if not top:return {'prediction':None,'confidence':'low','needs_manual_review':True,'message':'No verified match was found. The admin team will review your request.'}
 r=top[1]; return {'prediction':{k:r.get(k) for k in ('model_no','brand','capacity_ah','dealer_price','mrp','warranty_months','source')},'confidence':'high' if top[0]>=30 else 'medium','needs_manual_review':top[0]<16,'message':'Confirm dimensions, terminal orientation, OEM fitment and warranty before sale.'}
def extract_pdf(path,source_type='retail'):
 import fitz
 pages=[]; records=[]
 for i,p in enumerate(fitz.open(path)):
  text=p.get_text('text').strip()
  if len(re.sub(r'\s+','',text))<50:
   try:
    import pytesseract
    from PIL import Image
    pix=p.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False); img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples); text=pytesseract.image_to_string(img,config='--psm 6')
   except Exception: pass
  if len(re.sub(r'\\s+','',text))<50:
   try:
    import subprocess,tempfile
    from PIL import Image
    import pytesseract
    with tempfile.TemporaryDirectory() as td:
     out=Path(td)/'page'
     subprocess.run(['pdftoppm','-f',str(i+1),'-singlefile','-jpeg','-r','180',str(path),str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     text=pytesseract.image_to_string(Image.open(str(out)+'.jpg'),config='--psm 6')
   except Exception: pass
  pages.append(text)
  for line in [re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]:
   amounts=[float(x.replace(',','')) for x in re.findall(r'(?<!\d)([0-9]{2,7}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)(?!\d)',line)]
   models=[m for m in re.findall(r'\b[A-Z][A-Z0-9/-]{2,20}\b',line.upper()) if m not in {'MRP','DP','GST','PRICE','DEALER','BATTERY','MODEL','TOTAL','AUTO'}]
   if not amounts and not models: continue
   ah=re.search(r'\b(\d{1,3})\s*AH\b',line,re.I); warranty=re.search(r'\b(\d{1,3})\s*(?:MONTH|MON)\b',line,re.I)
   records.append({'source':Path(path).name,'source_type':source_type,'page':i+1,'raw_line':line,'model_no':models[0] if models else None,'brand':next((b for b in ('EXIDE','AMARON','LIVGUARD','LUMINOUS','SF SONIC') if b in line.upper()),None),'capacity_ah':int(ah.group(1)) if ah else None,'warranty_months':int(warranty.group(1)) if warranty else None,'dealer_price':amounts[-2] if source_type=='retail' and len(amounts)>1 else None,'mrp':amounts[-1] if source_type=='retail' and amounts else None,'scrap_price':amounts[-1] if source_type=='scrap' and amounts else None})
 return {'schema_version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'records':records}
def publish(payload):
 if DATA.exists(): BACKUP.write_bytes(DATA.read_bytes())
 tmp=DATA.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8'); tmp.replace(DATA)
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
