from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api

authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'API-KEY'
    }
}

api = Api(
	version='1.0',
	prefix="/api/v1",
	authorizations=authorizations
)

db = SQLAlchemy()
