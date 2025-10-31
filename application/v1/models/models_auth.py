from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from application import db
from sqlalchemy.orm import relationship
from datetime import datetime


# =============================================================================================
class UserGroup(db.Model):
	__tablename__ = "user_groups"
	id = Column(Integer, primary_key=True)
	group_name = Column(String(100), nullable=False, unique=True)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	users = relationship('User', backref='user_group')


# =============================================================================================
class User(db.Model):
	__tablename__ = "users"
	id = Column(Integer, primary_key=True)
	group_id = Column(Integer, ForeignKey('user_groups.id'), nullable=False)
	username = Column(String(100), nullable=False, unique=True)
	api_key = Column(String(64), nullable=False)
	is_deleted = Column(Boolean, nullable=False, default=False)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	sessions = relationship('Session', backref='user')


# =============================================================================================
class Session(db.Model):
	__tablename__ = "user_sessions"
	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	ip_address = Column(String(200), nullable=False)
	session_start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
	access_logs = relationship('AccessLog', backref='session')


# =============================================================================================
class AccessLog(db.Model):
	__tablename__ = "user_access_logs"
	id = Column(Integer, primary_key=True)
	session_id = Column(Integer, ForeignKey('user_sessions.id'), nullable=False)
	url = Column(String(500), nullable=False)
	timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


