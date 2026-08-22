FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./

EXPOSE 80

CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT:-80} --timeout 120 app:app"]
