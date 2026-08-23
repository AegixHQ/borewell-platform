FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000
# Migrations run before the server starts - schema is Alembic's job, not the
# app's. If this fails, the container fails to start rather than serving
# against a stale/missing schema.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
