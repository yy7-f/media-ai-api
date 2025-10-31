from application import application as app
from flask_cors import CORS

# Enable CORS *before* app.run
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
    supports_credentials=False,
    expose_headers=["Content-Disposition"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

if __name__ == '__main__':
	app.run(port=5071)
