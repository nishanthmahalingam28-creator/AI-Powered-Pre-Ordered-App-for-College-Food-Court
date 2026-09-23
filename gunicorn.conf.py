"""
Gunicorn Production WSGI Configuration for College Food Court Backend.
"""

import os
import multiprocessing

# Network Binding
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Worker Processes & Concurrency
# Keep one worker because Flask-SocketIO requires a single worker unless a
# message queue + sticky sessions are configured. Use a moderate thread count
# so concurrent API requests do not queue behind slow I/O without excessive
# memory usage on small Render instances.
cpu_count = multiprocessing.cpu_count()
default_workers = min(max(cpu_count * 2, 2), 4)
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "12"))

# Process Lifecycle & Memory Protection
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "10"))

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" [req_id=%({X-Request-ID}i)s]'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
preload_app = False
