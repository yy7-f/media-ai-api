import os
import secrets


class Config(object):
	DEBUG = False
	TESTING = False
	SQLALCHEMY_TRACK_MODIFICATIONS = False
	SESSION_COOKIE_SECURE = False
	BASE_DIR = os.path.abspath(os.path.dirname(__file__))
	SESSION_TIMEOUT = 43200
	PERMANENT_SESSION_LIFETIME = 43200
	SECRET_KEY = secrets.token_hex(32)


class DevelopmentConfig(Config):
	DEBUG = True
	ENV = 'development'


class StagingConfig(Config):
	TESTING = True
	ENV = 'staging'


class ProductionConfig(Config):
	ENV = 'production'

