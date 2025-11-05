# Use lightweight Python base
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# ✅ Install system dependencies (FFmpeg + optional libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
 && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -c "import flask_sqlalchemy, flask_restx, flask; print('✅ Deps OK')"

# Copy app source code
COPY . .

# Default command for Cloud Run
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT -w 1 -k gthread --threads 4 --timeout 300 'wsgi:app'"]
