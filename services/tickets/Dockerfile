# Tickets service image
FROM python:3.12-slim

# No .pyc files, unbuffered logs to stdout; defaults overridable at docker run
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Unprivileged user to run the service
RUN useradd --create-home --uid 10001 appuser

# Dependencies first so this layer is cached when only the code changes
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs to run: no tests, no .env, no COPY . .
COPY app.py db.py sqlserver.py migrate.py ./
COPY migrations/ ./migrations/
COPY tickets/ ./tickets/

# Code is owned by root and only readable by appuser, whatever the file modes on the host were
RUN chmod -R a+rX,go-w /app
USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
