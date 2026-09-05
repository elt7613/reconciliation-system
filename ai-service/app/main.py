"""AI microservice — explains reconciliation findings over OpenRouter.

Endpoints:
  GET  /health — liveness (public)
  GET  /ready  — readiness (reports LLM configuration state, still public)
  POST /explain   — one discrepancy → structured explanation (X-API-Key)
  POST /summarize — aggregated findings → executive summary (X-API-Key)

Errors are explicit HTTP codes so the Django backend can distinguish:
  401 invalid/missing service key · 422 malformed payload · 503 LLM
  unavailable/unconfigured · 500 model validation exhausted after retries
"""
import logging

from fastapi import Depends, FastAPI, HTTPException, status

from . import agents
from .config import settings
from .schemas import ExplainRequest, Explanation, SummarizeRequest, Summary
from .security import require_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai-service")

app = FastAPI(title="Reconciliation AI Service", version="1.0.0")


@app.middleware("http")
async def log_request_duration(request, call_next):
    import time

    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "%s %s -> %d in %.2fs", request.method, request.url.path, response.status_code,
        time.perf_counter() - started,
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {
        "status": "ok" if agents.llm_available() else "degraded",
        "llm_enabled": settings.llm_enabled,
        "llm_configured": bool(settings.openrouter_api_key),
        "model": settings.openrouter_model,
    }


@app.post("/explain", response_model=Explanation)
async def explain(req: ExplainRequest, _: None = Depends(require_api_key)):
    if not agents.llm_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured on this service (OPENROUTER_API_KEY / LLM_ENABLED).",
        )
    try:
        return await agents.explain_discrepancy(req.model_dump())
    except Exception:
        logger.exception("Explain failed (model=%s)", settings.openrouter_model)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider failed or returned unusable output after retries.",
        )


@app.post("/summarize", response_model=Summary)
async def summarize(req: SummarizeRequest, _: None = Depends(require_api_key)):
    if not agents.llm_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured on this service (OPENROUTER_API_KEY / LLM_ENABLED).",
        )
    try:
        return await agents.summarize_findings(req.model_dump())
    except Exception:
        logger.exception("Summarize failed (model=%s)", settings.openrouter_model)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider failed or returned unusable output after retries.",
        )
