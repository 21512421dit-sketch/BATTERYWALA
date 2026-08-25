from datetime import datetime, timezone
from flask_login import UserMixin
from . import db
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); email=db.Column(db.String(255),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False); is_admin=db.Column(db.Boolean,default=False)
class Recipient(db.Model):
 id=db.Column(db.Integer,primary_key=True); kind=db.Column(db.String(10),nullable=False); value=db.Column(db.String(255),nullable=False); active=db.Column(db.Boolean,default=True); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
class Lead(db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120)); email=db.Column(db.String(255)); phone=db.Column(db.String(40)); form_json=db.Column(db.Text); result_json=db.Column(db.Text); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
class Upload(db.Model):
 id=db.Column(db.Integer,primary_key=True); filename=db.Column(db.String(255)); sha256=db.Column(db.String(64)); record_count=db.Column(db.Integer); status=db.Column(db.String(30)); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
class Delivery(db.Model):
 id=db.Column(db.Integer,primary_key=True); lead_id=db.Column(db.Integer); channel=db.Column(db.String(20)); target=db.Column(db.String(255)); status=db.Column(db.String(30)); detail=db.Column(db.Text); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
