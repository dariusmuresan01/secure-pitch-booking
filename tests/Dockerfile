FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /tests

COPY tests/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY tests/ ./

RUN useradd --create-home --uid 10002 tester
USER tester

CMD ["pytest", "-v", "-p", "no:cacheprovider"]