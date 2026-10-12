FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY booking-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY booking-service/main.py booking-service/seed.py ./

RUN useradd --create-home --uid 10001 appuser \
    && mkdir /data \
    && chown appuser /data
USER appuser

ENV DATABASE_PATH=/data/booking.db \
    PUBLIC_KEY_PATH=/run/keys/public.pem

EXPOSE 8001
CMD ["sh", "-c", "python seed.py && uvicorn main:app --host 0.0.0.0 --port 8001"]