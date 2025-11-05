# from flask import Flask, jsonify
# from .extensions import api
# import os, sys, time
# from .extensions import api, db
# from .workers import setup_config, setup_config_secret

################################################
# print(f"[BOOT] Step 1: Flask + API import | {time.strftime('%X')} | PID {os.getpid()}")
# sys.stdout.flush()
#
# application = Flask(__name__)
# api.init_app(application, title="Media AI API", description="step 1")
#
# @application.get("/_health")
# def _health():
#     return jsonify({"status": "ok"}), 200
#
# print("[BOOT] Step 1 loaded OK")

################################################

# print(f"[BOOT] Step 2: Flask + API + DB guard | {time.strftime('%X')} | PID {os.getpid()}")
# sys.stdout.flush()
#
# application = Flask(__name__)
#
# # fallback that won't try network during boot
# if not application.config.get("SQLALCHEMY_DATABASE_URI"):
#     application.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
#         "SQLALCHEMY_DATABASE_URI",
#         "sqlite:///:memory:"
#     )
# application.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
#
# api.init_app(application, title="Media AI API", description="step 2")
#
# try:
#     db.init_app(application)
#     print("[BOOT] db.init_app OK")
# except Exception as e:
#     print(f"[BOOT] db.init_app skipped: {e}")
#
# @application.get("/_health")
# def _health():
#     return jsonify({"status": "ok"}), 200
#
# # REGISTER NAMESPACES (do this AFTER api.init_app)
# from application.v1.resources.health import ns_health
# api.add_namespace(ns_health)

#############

# from flask import Flask, jsonify
# from .extensions import api, db
#
# application = Flask(__name__)
#
# # Guard DB so we never dial external services during boot
# application.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
# application.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
#
# api.init_app(application, title="Media AI API", description="MVP")
#
# if db is not None:
#     try:
#         db.init_app(application)
#         print("[BOOT] db.init_app OK")
#     except Exception as e:
#         print(f"[BOOT] db.init_app skipped: {e}")
#
# @application.get("/_health")
# def _health_root():
#     return jsonify({"status": "ok"}), 200
#
# # Register RESTX namespaces AFTER api.init_app
# from application.v1.resources.health import ns_health
# api.add_namespace(ns_health)
#
# # (Optional) print routes for verification
# try:
#     for r in application.url_map.iter_rules():
#         print(f"[ROUTE] {r.rule} -> {sorted(r.methods)}")
# except Exception:
#     pass

##############################################
# application/__init__.py
import os
from flask import Flask, jsonify
from application.extensions import api, db
from application.v1.resources import register_namespaces

application = Flask(__name__)

# Safe DB default to avoid network on boot
application.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
application.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
application.config.setdefault("OUTPUT_BUCKET", "media-ai-api-output")


api.init_app(application)
try:
    db.init_app(application)
    print("[BOOT] db.init_app OK")
except Exception as e:
    print(f"[BOOT] db.init_app skipped: {e}")

# Register namespaces AFTER api.init_app
register_namespaces(api)

@application.get("/_health")
def _health():
    return jsonify({"status": "ok"}), 200


from flask_cors import CORS
CORS(
    application,
    resources={r"/api/*": {"origins": ["http://localhost:3000","http://127.0.0.1:3000"]}},
    supports_credentials=False,
    expose_headers=["Content-Disposition"],
    methods=["GET","POST","PUT","DELETE","OPTIONS"],
    allow_headers=["Content-Type","Authorization","API-KEY"],
)
