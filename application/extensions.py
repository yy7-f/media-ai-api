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
	authorizations=authorizations,
    doc="/api/v1/docs",          # Swagger at /api/v1/docs
)


try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
except Exception as e:
    db = None
    print(f"[EXT] SQLAlchemy not available: {e}")
