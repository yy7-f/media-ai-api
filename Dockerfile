# Python base
FROM python:3.11-slim

# Safer, cleaner runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Cloud Run will inject $PORT (default 8080). Bind gunicorn to it.
ENV PORT=8080

# Your entrypoint module is `application.py` and it exposes `app`
# (from application import application as app) → gunicorn target = application:app
CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "-w", "2", "-k", "gthread", "--threads", "8", "--timeout", "120", "application:app"]
