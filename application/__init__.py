from flask import Flask

from .extensions import api, db
from .workers import setup_config, setup_config_secret
# from application.v1.static.format import CustomJSONEncoder


application = Flask(__name__, instance_relative_config=True)
# application.json_encoder = CustomJSONEncoder
setup_config()
setup_config_secret()

api.init_app(
	application,
	title="Lama-cleanser iopaint inprint and text api",
	description="API microservice for separating voice and bgm, and imprinting from video."
)

db.init_app(application)

from .resources import *

