# WhyStreet — Grounded Volatility Explainer

Investors see stocks go up and down without understanding **why**. WhyStreet automatically
detects sharp price-move points, then runs a live pipeline on **RocketRide Cloud** that calls
**Linkup** to explain the cause as a **causal chain** — every reason has a **source URL + confidence**.

> Built for **HackWithSeattle 2.0**. Track: Open Innovation (touches Market Intel + Fact-Checking).

## How it works

```
Detector (pure math) detects volatility points
   │  ┌── click a point (demo/browse)
   │  └── scheduler auto-detects (realtime)   → same pipeline
   ▼
RocketRide Cloud pipeline (live):
   Linkup Search → Fetch → Research (trace the causal chain)
   → LLM Structurer (JSON reasons + graph, keeps source_url)
   → Verifier (drops claims without a source)
   ▼
Output: reasons list (↑/↓ + confidence + link) + causal graph (every edge has a source)
```

## Technologies

- **RocketRide Cloud** — hosts the multi-agent pipeline, observability, always-on endpoint.
- **Linkup** — live web grounding (Search + Fetch + Research), every claim sourced.
- Frontend: React + Vite (deploy Vercel). Data/cache: Supabase. Detector: Python.

## Structure

```
detector/    Python — fetch Yahoo prices, detect volatility points, seed Supabase
pipeline/    RocketRide pipeline (.pipe) + prompts (structurer, verifier)
supabase/    schema.sql
frontend/    React + Vite app
```

## Run locally (dev)

```bash
cp .env.example .env      # fill in RocketRide token, Linkup key, Supabase keys
# Detector
cd detector && pip install -r requirements.txt && python seed_supabase.py
# Frontend
cd frontend && npm install && npm run dev
```

## Grounding & anti-hallucination

Every factual claim is traceable to a `source_url` taken from Linkup content in that same run.
The Verifier node drops every reason/edge without a source before it's ever displayed.

## Links

- Detailed design docs: see the `docs/` folder in the parent workspace.
- Inspiration: the original OttoTrade (https://github.com/jasonnugget/Ottotrade) — this version
  replaces the static curated dataset with live, cited web grounding + a production pipeline.
