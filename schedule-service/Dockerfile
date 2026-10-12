FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build/schedule-service

COPY packages/ /build/packages/
COPY schedule-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

WORKDIR /app
COPY schedule-service/main.py ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV PUBLIC_KEY_PATH=/run/keys/public.pem \
    BOOKING_SERVICE_URL=http://booking-service:8001

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]