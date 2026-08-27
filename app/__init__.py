import os
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
  db.create_all(); ensure_admin(app)
 return app

def ensure_admin(app):
 from .models import User
 from werkzeug.security import generate_password_hash
 email=os.getenv('ADMIN_EMAIL','admin@batterywala.local').lower()
 if not User.query.filter_by(email=email).first():
  db.session.add(User(email=email,password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD','ChangeMe123!')),is_admin=True)); db.session.commit()
