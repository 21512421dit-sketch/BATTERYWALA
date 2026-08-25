import json,hashlib,re
from pathlib import Path
from flask import Blueprint,render_template,request,jsonify,redirect,url_for,flash,session,Response
from flask_login import login_user,logout_user,login_required,current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from . import db
from .models import User,Recipient,Lead,Upload,Delivery
from .services import predict,extract_pdf,publish,load_data,notify
bp=Blueprint('main',__name__)
def csrf():
 import secrets
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
 return session['csrf']
def valid_csrf(): return request.form.get('csrf')==session.get('csrf')
def admin_required(fn):
 from functools import wraps
 @wraps(fn)
 @login_required
 def inner(*a,**k):
  if not current_user.is_admin:return ('Forbidden',403)
  return fn(*a,**k)
 return inner
@bp.app_context_processor
def inject(): return {'csrf_token':csrf()}
@bp.get('/')
def index():
 path=Path(__file__).resolve().parent.parent/'docs'/'optimized_main_prototype.html'
 html=path.read_text(encoding='utf-8')
 head='''<link rel="icon" href="/static/images/batterywala-logo-original.png"><link rel="stylesheet" href="/static/site-updates.css"><script>try{sessionStorage.setItem('bwRestoreSeen','1')}catch(e){}</script></head>'''
 body='''<script src="/static/site-updates.js"></script></body>'''
 return Response(html.replace('</head>',head).replace('</body>',body),mimetype='text/html')
@bp.post('/api/predict')
def api_predict():
 form=dict(request.get_json(silent=True) or request.form.to_dict())
 form['application']=form.get('application') or form.get('battery_type','')
 form['vehicle_model']=form.get('vehicle_model') or form.get('car_model') or form.get('model_no') or form.get('vehicle_brand') or form.get('battery_type','')
 required=['name','phone','application']; missing=[x for x in required if not str(form.get(x,'')).strip()]
 if missing:return jsonify({'error':'Missing required fields','fields':missing}),400
 result=predict(form); lead=Lead(name=form.get('name'),email=form.get('email'),phone=form.get('phone'),form_json=json.dumps(form),result_json=json.dumps(result));db.session.add(lead);db.session.commit();notify(lead,form,result,Recipient.query.all());return jsonify(result)
@bp.get('/api/pricing')
def pricing(): return jsonify(load_data())
@bp.route('/admin/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  if not valid_csrf():return ('Invalid CSRF',400)
  u=User.query.filter_by(email=request.form['email'].lower()).first()
  if u and check_password_hash(u.password_hash,request.form['password']):login_user(u);return redirect(url_for('main.admin'))
  flash('Invalid email or password','error')
 return render_template('login.html')
@bp.post('/admin/logout')
@login_required
def logout():
 if not valid_csrf():return ('Invalid CSRF',400)
 logout_user();return redirect(url_for('main.login'))
@bp.get('/admin')
@admin_required
def admin(): return render_template('admin.html',recipients=Recipient.query.order_by(Recipient.id.desc()).all(),uploads=Upload.query.order_by(Upload.id.desc()).limit(20),leads=Lead.query.order_by(Lead.id.desc()).limit(20),records=len(load_data().get('records',[])))
@bp.post('/admin/upload')
@admin_required
def upload():
 if not valid_csrf():return ('Invalid CSRF',400)
 f=request.files.get('file'); kind=request.form.get('source_type','retail')
 if not f or not f.filename.lower().endswith('.pdf'):flash('PDF required','error');return redirect(url_for('main.admin'))
 name=secure_filename(f.filename); dst=Path('/tmp')/name;f.save(dst)
 try:
  payload=extract_pdf(dst,kind); publish(payload); sha=hashlib.sha256(dst.read_bytes()).hexdigest();db.session.add(Upload(filename=name,sha256=sha,record_count=len(payload['records']),status='published'));db.session.commit();flash(f"Published {len(payload['records'])} extracted records. Previous JSON was backed up.",'ok')
 except Exception as e: flash('Extraction failed: '+str(e),'error')
 return redirect(url_for('main.admin'))
@bp.post('/admin/recipients')
@admin_required
def add_recipient():
 if not valid_csrf():return ('Invalid CSRF',400)
 kind=request.form.get('kind'); value=request.form.get('value','').strip()
 if kind not in ('email','sms') or not value: flash('Invalid recipient','error')
 else: db.session.add(Recipient(kind=kind,value=value));db.session.commit();flash('Recipient added','ok')
 return redirect(url_for('main.admin'))
@bp.post('/admin/recipients/<int:rid>/delete')
@admin_required
def del_recipient(rid):
 if not valid_csrf():return ('Invalid CSRF',400)
 r=db.session.get(Recipient,rid)
 if r:db.session.delete(r);db.session.commit()
 return redirect(url_for('main.admin'))
