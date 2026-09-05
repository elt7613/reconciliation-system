# AI microservice — FastAPI + Pydantic AI over OpenRouter.
#
# Build context is the REPO ROOT (Dokploy runs: docker build -f ai-service/Dockerfile .),
# so every COPY path is prefixed with ai-service/. Do not build with the service
# directory itself as context — the paths below assume the repo root.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai-service/ .

# Dokploy sets PORT; uvicorn honors it at runtime via CMD env expansion.
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 65"]
