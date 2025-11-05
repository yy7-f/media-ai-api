import os
from flask import request
from flask_restx import abort
from functools import wraps


def setup_config():
	from application import application
	try:
		if os.environ['ENV'] == 'test':
			application.config.from_object("config.TestingConfig")
		elif os.environ['ENV'] == 'prod':
			application.config.from_object("config.ProductionConfig")
		for attr in ['S3_BUCKET', 'S3_ACCESS_KEY', 'S3_SECRET_KEY']:
			application.config[attr] = os.environ[attr]

	except KeyError:
		application.config.from_object("config.DevelopmentConfig")

	except Exception as e:
		raise e


def setup_config_secret():
	from application import application
	try:
		instance_folder = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
		if not os.path.exists(instance_folder):
			os.makedirs(instance_folder)

		try:
			instance_config_filepath = os.path.join(instance_folder, 'config.py')
			if not os.path.exists(instance_config_filepath):
				from .helpers import get_config_files_from_s3, download_data_from_s3
				files = get_config_files_from_s3()
				for file in files:
					filename = file.split('/')[-1]
					local_filepath = os.path.join(instance_folder, filename)
					download_data_from_s3(s3_filepath=file, data_filepath=local_filepath)

			if os.environ['ENV'] in ['test', 'prod']:
				application.config.from_pyfile('config.py')
		except KeyError as e:
			application.config.from_pyfile('config_dev.py')

	except Exception as e:
		raise e



def api_key_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        sent = request.headers.get("API-Key")
        valid = os.getenv("API_KEY")
        if sent and valid and sent == valid:
            return func(*args, **kwargs)
        abort(401, message="Unauthorized access")
    return wrapper


# API key authentication decorator
# def api_key_required(func):
# 	@wraps(func)  # ✅ keep original function name & doc
# 	def wrapper(*args, **kwargs):
# 		key = request.headers.get('API_Key')
# 		if key:
# 			from application.v1.models.models_auth import User
# 			user = User.query.filter_by(api_key=key).first()
# 			if user:
# 				return func(*args, **kwargs)
# 		abort(401, message="Unauthorized access")
# 	return wrapper




