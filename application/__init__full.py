# from flask import Flask, jsonify
# from flask_cors import CORS
# from .extensions import api, db
# from .workers import setup_config, setup_config_secret
#
# application = Flask(__name__, instance_relative_config=True)
#
# # safe config
# for fn in (setup_config, setup_config_secret):
#     try:
#         fn()
#     except Exception as e:
#         print(f"[BOOT] {fn.__name__} skipped: {e}")
#
# # CORS: allow local dev + your future frontend domain(s)
# CORS(
#     application,
#     resources={r"/api/*": {"origins": [
#         "http://localhost:3000",
#         "http://127.0.0.1:3000",
#         # add your prod frontend when you have it, e.g. "https://app.yourdomain.com"
#     ]}},
#     supports_credentials=False,
#     expose_headers=["Content-Disposition"],
#     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["Content-Type", "Authorization"],
# )
#
# api.init_app(application, title="Media AI API", description="MVP endpoints")
# db.init_app(application)
#
# @application.get("/_health")
# def trivial_health():
#     return {"status": "ok"}, 200
#
# from application.v1.resources.health import ns_health
# api.add_namespace(ns_health)
# # keep other namespaces disabled until deps are restored
# # from .resources import *

from flask import Flask, jsonify
from .extensions import api, db
from .workers import setup_config, setup_config_secret
import os, sys, time

print(f"[BOOT] Starting Flask at {time.strftime('%X')} | PID {os.getpid()} | Python {sys.version}")
sys.stdout.flush()

application = Flask(__name__, instance_relative_config=True)

# Run safe setup functions
for fn in (setup_config, setup_config_secret):
    try:
        fn()
    except Exception as e:
        print(f"[BOOT] {fn.__name__} skipped: {e}")

# Initialize API
api.init_app(application, title="Media AI API", description="MVP")

# Initialize DB safely (skip if not available)
if db is not None:
    try:
        db.init_app(application)
    except Exception as e:
        print(f"[BOOT] DB init skipped: {e}")

# Simple health check endpoint
@application.get("/_health")
def _health():
    return jsonify({"status": "ok"}), 200

# Register namespaces AFTER api.init_app()
from application.v1.resources.health import ns_health
api.add_namespace(ns_health)

print("[BOOT] Flask app created successfully.")
sys.stdout.flush()
