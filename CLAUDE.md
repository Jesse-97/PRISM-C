# prism-compare — PRISM Model Comparison Tool

## What this repo is

A Profinch-internal tool for comparing alternative retrieval/synthesis
architectures against PRISM's production baseline (BGE-base bi-encoder,
cosine similarity, ms-marco-MiniLM-L-6 cross-encoder, Gemma 4B / Claude
Haiku synthesis). It runs a scaled-down replica of PRISM's 5-stage retrieval
pipeline against a synthetic knowledge base, plus a small FastAPI + React
app for running and viewing comparisons. See ARCHITECTURE.md before
changing structure.

## Two modes — never blur them

- **Eval mode**: runs the frozen `data/eval_questions.jsonl` set (with gold
  answers) against a profile, computing recall@5, MRR, faithfulness, and
  latency p95. This is the only output allowed in any recommendation.
- **Ad-hoc mode**: live query against 2+ profiles for demo purposes, no
  gold answer, no recall/MRR/faithfulness — just answer, latency, cost.
  Never treat ad-hoc results as evidence in a writeup or commit message.

## Hard gate: eval before variants

Do not implement `variant_embed`, `variant_hybrid`, or `variant_llm` until
`baseline` runs cleanly through `/eval/run` and produces a complete metrics
row in `results/runs/`. If asked to build a variant before this gate is
satisfied, push back and ask for the baseline eval run to be finished first.

## Locked scope — this is NOT a PRISM clone

Do not implement authentication, batch Excel upload, SharePoint integration,
multilingual translation, or audit logging. None of that is part of what's
being compared. If asked to add one of these "to make it feel more real,"
flag it as out of scope rather than building it.

## Locked variant list — do not add a fourth without explicit instruction

- `variant_embed` — embedder swap only (BGE-base → BGE-large / e5-large)
- `variant_hybrid` — retrieval strategy swap only (dense+BM25 with RRF)
- `variant_llm` — synthesis model swap only (Gemma 4B → Cohere Command R)

Reranker is held constant across all three by design.

## Interface contract — every profile module must implement this exactly

```python
def retrieve(query: str, k: int) -> List[Chunk]: ...
def synthesize(query: str, chunks: List[Chunk]) -> str: ...
```

`retrieval_service.py` dispatches to the active profile's module via these
two functions only. A profile needing extra setup (different model load,
different client) does that inside its own module at import time.

## Directory structure

```
backend/app/
  routes/         compare_routes.py (POST /compare), eval_routes.py (POST /eval/run, GET /eval/report)
  services/       retrieval_service.py, synthesis_service.py, metrics_service.py
  profiles/       baseline.py, variant_embed.py, variant_hybrid.py, variant_llm.py
  core/           config.py — .env-driven, no hardcoded keys
  main.py
frontend/src/
  pages/          ComparePage.jsx
  components/     ProfileSelector.jsx, ResultCard.jsx, MetricsPanel.jsx
data/
  synthetic_kb.jsonl      — synthetic RFP-style Q&A, NEVER real client content
  eval_questions.jsonl    — frozen eval set with gold answers, same synthetic domain
results/runs/             — eval-mode output, source of truth for any writeup
```

## Commands

- `uvicorn app.main:app --reload --port 8001` — run the backend (port 8001,
  not 8000, to avoid colliding with a real PRISM instance on the same box)
- `npm run dev` — run the frontend (Vite, mirrors PRISM's own frontend tooling)
- `pytest backend/app/services/` — unit tests for metrics_service
- `python -m scripts.run_eval --profile baseline` — CLI shortcut for eval
  mode without going through the UI, useful while building a new profile

## Stack notes

- Python 3.11+, FastAPI, matching PRISM's own backend conventions
- React + Vite frontend, intentionally minimal — one comparison screen, not
  a UI clone of PRISM
- `sentence-transformers` + FAISS for embedding/retrieval profiles
- Local model calls via Ollama; hosted calls (Cohere Command R on OCI,
  Anthropic API) via their SDKs; all keys in `.env` via `python-dotenv`,
  following PRISM's existing pattern — never hardcoded
- No MongoDB requirement — `results/runs/` as JSON is sufficient at this scale

## Conventions

- Each profile module is self-contained; no shared mutable state between profiles
- `data/eval_questions.jsonl` gold answers are frozen once Phase 0 completes
- Every run logs latency (p50/p95) and token cost per query, not just accuracy
- Synthesis prompt template is identical across `baseline`, `variant_embed`,
  and `variant_hybrid` — only `variant_llm` may change it, and only because
  the model itself is the tested variable, not the prompt

## Don't

- Don't put real Profinch client RFP content into `synthetic_kb.jsonl` or
  `eval_questions.jsonl` — write fictional banking scenarios from scratch
- Don't implement more than one changed axis in a single variant
- Don't let ad-hoc mode results get cited in any report, commit message, or
  recommendation — eval mode only
- Don't add a fourth variant without being asked — flag it as future work
- Don't build auth, batch upload, SharePoint, translation, or audit logging
  into this repo — out of scope, see ARCHITECTURE.md section 1
- Don't skip writing `/eval/run` output to `results/runs/` — every
  comparison must be reproducible from stored JSON, not just shown live
