"""One-off diagnostic: measure the real wall-clock latency of the configured
OpenRouter model with a representative explain-style prompt (no tools, plain
completion). Not part of the service — delete after debugging.

Run from ai-service/:  .venv/bin/python bench_model.py
"""
import json
import time

import httpx

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v

prompt = (
    "Explain this reconciliation finding. Facts (JSON):\n"
    + json.dumps(
        {
            "discrepancy_type": "duplicate_charge",
            "severity": "high",
            "order_reference": "ORD-1501",
            "amount_at_risk": "119.84",
            "engine_facts": {
                "charges": ["119.84", "119.84"],
                "same_amount": True,
                "times_charged": 2,
                "duplicate_txns": ["TXN700168"],
            },
        },
        indent=2,
    )
)

req = {
    "model": env["OPENROUTER_MODEL"],
    "messages": [
        {
            "role": "system",
            "content": (
                "You are a payments-reconciliation analyst. Explain in plain "
                "language what likely happened. Keep the summary to one sentence."
            ),
        },
        {"role": "user", "content": prompt},
    ],
    "temperature": 0.1,
    "max_tokens": 400,
}
headers = {
    "Authorization": f"Bearer {env['OPENROUTER_API_KEY']}",
    "Content-Type": "application/json",
}

for i in range(2):
    t0 = time.perf_counter()
    r = httpx.post(
        env["OPENROUTER_BASE_URL"] + "/chat/completions",
        json=req,
        headers=headers,
        timeout=60,
    )
    dt = time.perf_counter() - t0
    try:
        body = r.json()
        usage = body.get("usage") or {}
        print(
            f"attempt {i + 1}: http={r.status_code} wall={dt:.2f}s "
            f"prompt_tokens={usage.get('prompt_tokens')} "
            f"completion_tokens={usage.get('completion_tokens')}"
        )
    except Exception as exc:
        print(f"attempt {i + 1}: http={r.status_code} wall={dt:.2f}s parse_error={exc!r} body[:200]={r.text[:200]}")
