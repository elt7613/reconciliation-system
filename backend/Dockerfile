# Backend API — Django + DRF + gunicorn. API-only (SPA served separately).
#
# Build context is the REPO ROOT (Dokploy runs: docker build -f backend/Dockerfile .),
# so every COPY path is prefixed with backend/. Do not build with the service
# directory itself as context — the paths below assume the repo root.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sample CSVs ship with the app so the "Load sample data" button works anywhere.
# (sample_data/ is inside backend/ in the repo.)

COPY backend/ .

RUN mkdir -p /app/staticfiles

EXPOSE 8000

# Collect static at container start (Django admin/DRF statics only). Output
# goes to the log, not /dev/null: a real failure stays visible instead of
# silently shipping without assets.
CMD ["sh", "-c", "python manage.py collectstatic --noinput || echo 'WARN: collectstatic failed'; python manage.py migrate --noinput && python manage.py seed_demo_user --email demo@example.com --password 'DemoPass!123' || true; gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
