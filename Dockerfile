# ---- Frontend build ----
FROM node:22-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Backend runtime ----
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Built SPA from the first stage
COPY --from=frontend /web/dist /app/spa
ENV DJANGO_SPA_DIR=/app/spa

RUN python manage.py collectstatic --noinput --clear || true

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo_user --email demo@example.com --password 'DemoPass!123' || true; gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
