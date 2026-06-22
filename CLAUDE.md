# prism-compare — PRISM Model Comparison Tool

## What this repo is

A Profinch-internal tool for comparing alternative retrieval/synthesis
architectures against a local baseline (BGE-base bi-encoder, cosine
similarity, ms-marco-MiniLM-L-6-v2 cross-encoder, Gemma 4B via Ollama
for synthesis). It runs a scaled-down replica of PRISM's 5-stage retrieval
pipeline against a synthetic knowledge base, plus a small FastAPI + React
app for running and viewing comparisons.

The baseline intentionally uses Gemma 4B (not PRISM's production Claude
Haiku) to keep the default pipeline fully local and zero-cost. Claude Haiku
appears only in variant_llm as one of the tested alternatives.

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

## Constants held across all profiles

- **Reranker**: ms-marco-MiniLM-L-6-v2 in every profile, never swapped.
  If a reranker comparison is needed later, it becomes a new axis with its
  own variant file — it is never mixed into an existing variant.
- **Synthesis prompt template**: identical across `baseline`, `variant_embed`,
  and `variant_hybrid`. Only `variant_llm` may change it, and only because
  the model itself is the tested variable, not the prompt.
- **Confidence threshold**: 0.5 on reranker score for all profiles.

## Locked variant list — do not add a fourth without explicit instruction

- `variant_embed` — embedder swap only (BGE-base local → Cohere Embed 4 via OCI)
- `variant_hybrid` — retrieval strategy swap only (dense-only → hybrid
  dense+BM25 with Reciprocal Rank Fusion; RRF k=60 unless tuning is
  explicitly requested)
- `variant_llm` — synthesis model swap only (Gemma 4B → Cohere Command R
  via OCI, and optionally Claude Haiku via Anthropic API)

## Interface contract — every profile module must implement this exactly

```python
from typing import List
from app.core.types import Chunk

def retrieve(query: str, k: int) -> List[Chunk]: ...
def synthesize(query: str, chunks: List[Chunk]) -> str: ...
```

`retrieval_service.py` dispatches to the active profile's module via these
two functions only. A profile needing extra setup (different model load,
different client) does that inside its own module at import time.

## Profile selection at runtime

Active profile is set via:
- API parameter: `POST /compare` and `POST /eval/run` accept a `profile`
  field in the request body (one of: `baseline`, `variant_embed`,
  `variant_hybrid`, `variant_llm`)
- CLI: `python -m scripts.run_eval --profile baseline`
- Default: `baseline` if no profile is specified

There is no global env var for active profile. Each request/run chooses
its own profile explicitly.

## Eval methodology

### Eval set requirements
- Minimum **50 questions** in `data/eval_questions.jsonl` for a valid run.
  Fewer than 50 triggers a warning. Fewer than 20 aborts the run.
- Each entry must have: `id`, `query`, `gold_answer`, `gold_doc_ids`
  (list of synthetic_kb entry IDs that contain the answer).

### Metrics definitions
- **Recall@5**: fraction of queries where at least one gold doc appears
  in the top 5 retrieved chunks.
- **MRR** (Mean Reciprocal Rank): average of 1/rank for the first gold
  doc in retrieved results. 0 if no gold doc is retrieved.
- **Faithfulness**: LLM-as-judge binary score (0 or 1) per query. The
  judge (Claude Haiku via Anthropic API) receives the retrieved chunks
  and the synthesized answer, then answers: "Is every claim in the
  answer fully supported by the provided chunks? Answer 0 or 1." Judge
  prompt template lives in `metrics_service.py` and is frozen after
  Phase 0 completes.
- **Latency p50/p95**: wall-clock time per query in milliseconds,
  measured from retrieve() entry to synthesize() return.
- **Cost per query**: estimated token cost in USD, computed from model
  pricing tables in `config.py`. Local models (Gemma 4B, embedders,
  reranker) are $0.

### Run output
- Each eval run writes a timestamped JSON file to `results/runs/`
  named `{profile}_{YYYYMMDD_HHMMSS}.json`.
- Never overwrites — every run is a new file.
- The JSON contains: profile name, timestamp, per-query scores, and
  aggregate metrics. This is the source of truth for any writeup.

## Synthetic knowledge base

`data/synthetic_kb.jsonl` contains fictional (never real Profinch client)
banking Q&A pairs. Questions must cover core banking implementation
topics — module configuration, integration specifications, compliance
requirements, transaction processing workflows, GL posting rules,
maker-checker flows, EOD batch processing — not retail banking products
or generic FAQ.

Each entry: `id`, `question`, `answer`, `module_tag`, `topic_tag`.

## Error handling

- If Ollama is unreachable, `baseline.py` and any Ollama-dependent profile
  must raise `RuntimeError("Ollama not reachable at {host}:{port}")` —
  never return empty strings or fall through silently.
- If Cohere/Anthropic API calls fail in `variant_llm`, raise
  `RuntimeError` with the HTTP status and error message.
- If `data/eval_questions.jsonl` is missing or malformed, `/eval/run`
  returns HTTP 422 with a human-readable error, not a stack trace.

## Directory structure

```
backend/app/
  routes/         compare_routes.py (POST /compare)
                  eval_routes.py (POST /eval/run, GET /eval/report)
  services/       retrieval_service.py, synthesis_service.py, metrics_service.py
  profiles/       baseline.py, variant_embed.py, variant_hybrid.py, variant_llm.py
  core/           config.py — .env-driven, no hardcoded keys
                  types.py — Chunk dataclass, shared type definitions
  main.py
frontend/src/
  pages/          ComparePage.jsx
  components/     ProfileSelector.jsx, ResultCard.jsx, MetricsPanel.jsx
data/
  synthetic_kb.jsonl      — synthetic RFP-style Q&A, NEVER real client content
  eval_questions.jsonl    — frozen eval set with gold answers, same synthetic domain
results/runs/             — eval-mode output, one JSON per run, never overwritten
```

## Commands

- `uvicorn app.main:app --reload --port 8001` — run the backend (port 8001,
  not 8000, to avoid colliding with a real PRISM instance on the same box)
- `npm run dev` — run the frontend (Vite)
- `pytest backend/app/services/` — unit tests for metrics_service
- `python -m scripts.run_eval --profile baseline` — CLI shortcut for eval
  mode without going through the UI

## Stack

- Python 3.11.x, FastAPI, Uvicorn
- React + Vite frontend, intentionally minimal — one comparison screen
- `sentence-transformers` for embeddings, `rank_bm25` for BM25 in hybrid variant
- FAISS for vector indexing (not NumPy — even at small scale, FAISS
  provides consistent benchmarking behavior)
- Local models via Ollama (Gemma 4B baseline synthesis)
- Hosted calls: Cohere Command R via OCI SDK, Claude Haiku via Anthropic SDK
- All API keys in `.env` via `python-dotenv` — never hardcoded
- No MongoDB — `results/runs/` as JSON files at this scale
- No Docker requirement — runs directly in a Python venv

## Don't

- Don't put real Profinch client RFP content into `synthetic_kb.jsonl` or
  `eval_questions.jsonl` — write fictional banking scenarios from scratch
- Don't implement more than one changed axis in a single variant
- Don't let ad-hoc mode results get cited in any report, commit message, or
  recommendation — eval mode only
- Don't add a fourth variant without being asked — flag it as future work
- Don't build auth, batch upload, SharePoint, translation, or audit logging
- Don't skip writing `/eval/run` output to `results/runs/`
- Don't use `python 3.12+` features — pin to 3.11.x for consistency with PRISM
- Don't share mutable state between profile modules
