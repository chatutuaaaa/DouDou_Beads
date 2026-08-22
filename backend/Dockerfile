FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_CONCURRENCY=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        fontconfig \
        libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app \
    && setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.11

USER appuser

EXPOSE 80

CMD ["sh", "-c", "python -m gunicorn -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:${PORT:-80} --timeout 120 app:app"]
