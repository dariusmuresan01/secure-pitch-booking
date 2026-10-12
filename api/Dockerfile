FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY api/main.py api/seed.py ./

RUN useradd --create-home --uid 10001 appuser \
    && mkdir /data \
    && chown appuser /data
USER appuser

ENV DATABASE_PATH=/data/users.db \
    PRIVATE_KEY_PATH=/run/keys/private.pem \
    PUBLIC_KEY_PATH=/run/keys/public.pem \
    BOOKING_SERVICE_URL=http://booking-service:8001 \
    SCHEDULE_SERVICE_URL=http://schedule-service:8002

EXPOSE 8000
CMD ["sh", "-c", "python seed.py && uvicorn main:app --host 0.0.0.0 --port 8000"]