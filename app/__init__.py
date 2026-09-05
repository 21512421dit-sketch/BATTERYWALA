import json,os,re
from pathlib import Path
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

db=SQLAlchemy(); login=LoginManager()
def create_app(test_config=None):
 load_dotenv()
 app=Flask(__name__)
 app.config.update(SECRET_KEY=os.getenv('SECRET_KEY','dev-change-me'),SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL','sqlite:///batterywala.db'),SQLALCHEMY_TRACK_MODIFICATIONS=False,MAX_CONTENT_LENGTH=int(os.getenv('MAX_UPLOAD_MB','25'))*1024*1024)
 if test_config: app.config.update(test_config)
 db.init_app(app); login.init_app(app); login.login_view='main.login'
 from .models import User
 @login.user_loader
 def load_user(uid): return db.session.get(User,int(uid))
 from .routes import bp
 app.register_blueprint(bp)
 from .quotations import bp as quotations_bp
 app.register_blueprint(quotations_bp)
 with app.app_context():
  db.create_all(); ensure_admin(app); ensure_fitments()
 return app

def ensure_admin(app):
 from .models import User
 from werkzeug.security import generate_password_hash
 email=os.getenv('ADMIN_EMAIL','admin@batterywala.local').lower()
 if not User.query.filter_by(email=email).first():
  db.session.add(User(email=email,password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD','ChangeMe123!')),is_admin=True)); db.session.commit()

def ensure_fitments():
 from .models import BatteryFitment
 path=Path(__file__).resolve().parent/'data'/'fitments.json'
 records=json.loads(path.read_text(encoding='utf-8')).get('fitments',[]) if path.exists() else []
 expected=sum(len(item.get('batteries',[])) for item in records)
 expected_applications={item['application'] for item in records}
 current_applications={row[0] for row in db.session.query(BatteryFitment.application).distinct()}
 # ponytail: count plus category set catches the current migration without a metadata table.
 if BatteryFitment.query.count()==expected and current_applications==expected_applications:return
 BatteryFitment.query.delete()
 def key(value):return re.sub(r'[^a-z0-9]+',' ',str(value or '').lower()).strip()
 rows=[]
 for item in records:
  for battery in item.get('batteries',[]):
   rows.append({'application':item['application'],'vehicle_make':item['vehicle_make'],'make_key':key(item['vehicle_make']),
    'vehicle_model':item['vehicle_model'],'model_key':key(item['vehicle_model']),'fuel_type':item.get('fuel_type'),
    'fuel_key':key(item.get('fuel_type')),'brand':battery['brand'],'brand_key':key(battery['brand']),
    'model_no':battery['model_no'],'capacity_ah':battery.get('capacity_ah')})
 if rows:db.session.bulk_insert_mappings(BatteryFitment,rows)
 db.session.commit()
