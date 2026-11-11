# Tickets service image
FROM python:3.12-slim

# No .pyc files, unbuffered logs to stdout; defaults overridable at docker run
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/data

WORKDIR /app

# Unprivileged user, and the folder the SQLite file lives in (a volume at runtime)
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data \
 && chown appuser:appuser /data

# Dependencies first so this layer is cached when only the code changes
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs to run: no tests, no .env, no COPY . .
COPY app.py db.py schema.sql ./
COPY tickets/ ./tickets/

USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
