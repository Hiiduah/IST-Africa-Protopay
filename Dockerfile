# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for OCR and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONPATH=/app

RUN mkdir -p /app/media /app/staticfiles

EXPOSE 8000

# Run migrations and serve via gunicorn in production
CMD ["bash", "-lc", "python manage.py migrate && python manage.py collectstatic --noinput || true && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]