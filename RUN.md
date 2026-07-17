# WhyStreet — how to run

Full stack: Supabase (data) · RocketRide Cloud pipeline (agent + Linkup) · FastAPI backend · React/Vite frontend.

## One-time (already done)
- `.env` has all keys (RocketRide, Linkup, Supabase, LLM provider). Never commit it.
- Python venv at `.venv` with detector + backend deps installed.
- Supabase seeded: 12 tickers, price_bars, anomaly_points (Bollinger breakouts).
- Pipeline `pipeline/whystreet.pipe` deployed/runnable on RocketRide Cloud.

## Start everything (2 terminals)

```bash
# 0) activate venv (from whystreet/)
source .venv/bin/activate

# 1) Backend  (FastAPI :8000) — starts the RocketRide pipeline, serves /api/analyze
python -m uvicorn backend.app:app --port 8000
#   health check:  curl localhost:8000/api/health

# 2) Frontend (Vite :5173) — proxies /api → :8000
cd frontend && npm run dev
#   open http://localhost:5173
```

Then: pick a ticker → click any point (or a highlighted breakout) → **Explain why →** →
the agent calls Linkup live and returns a grounded causal graph + cited reasons.

## Re-seed / re-detect (optional)
```bash
cd detector
python seed.py            # fetch Yahoo + detect + write all tickers
python redetect.py        # re-run detection from DB prices (after tuning detector.py)
```

## Smoke-test the pipeline alone
```bash
python check_pipeline.py  # connect → run pipe → one question → print graph
```

## Swap the LLM provider (provider-agnostic)
The pipeline LLM reads 3 env vars — change them in `.env`, no `.pipe` edit needed:
```env
ROCKETRIDE_LLM_KEY=...
ROCKETRIDE_LLM_BASE_URL=https://api.groq.com/openai/v1      # Groq (free, 100k tok/day/model)
ROCKETRIDE_LLM_MODEL=llama-3.3-70b-versatile
# Higher free limits → Cerebras: base https://api.cerebras.ai/v1, model llama-3.3-70b
```

## Known gotchas (this machine)
- **Zscaler proxy** breaks Python TLS verification → backend & check_pipeline monkeypatch
  `ssl.create_default_context` (dev-only); Supabase writes use direct Postgres (psycopg2),
  not the REST client. None of this affects the Cloud deployment or the browser.
- **RocketRide `.env` parser keeps NO inline comments** — one `KEY=value` per line only.
- **Groq free tier**: ~100k tokens/day per model + small per-request cap. If analyze returns
  "unparseable output", the LLM was rate-limited — wait for daily reset or switch provider.
