# Production Dockerfile for AI-Powered College Food Court Backend
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=5000

WORKDIR /app

# Install system dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "Flask-SocketIO>=5.3.0,<6.0.0" "simple-websocket>=1.0.0" && \
    python -c "import flask_socketio; print('Flask-SocketIO installed:', flask_socketio.__version__ if hasattr(flask_socketio, '__version__') else 'ok')"

# Copy application files
COPY backend/ /app/backend/
COPY database/ /app/database/
COPY gunicorn.conf.py /app/gunicorn.conf.py

# Create unprivileged system user for process security
RUN useradd -m -u 1001 -s /bin/bash foodcourt && \
    chown -R foodcourt:foodcourt /app

USER foodcourt

EXPOSE 5000

# Health check using the readiness probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:5000/api/ready || exit 1

# Launch production WSGI server
CMD ["sh", "-c", "python /app/backend/init_db.py && exec gunicorn -c /app/gunicorn.conf.py --chdir /app/backend app:app"]
