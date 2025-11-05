from flask_restx import Namespace, Resource
import os

ns_version = Namespace("version", path="/version", description="API version info")

@ns_version.route("")
@ns_version.route("/")
class VersionResource(Resource):
    def get(self):
        return {
            "service": "media-ai-api",
            "version": "0.1.0",
            "env": os.getenv("APP_ENV", "prod")
        }, 200
