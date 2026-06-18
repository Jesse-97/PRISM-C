# PRISM Model Comparison Tool — Architecture Plan

## 0. Scope (locked)

Purely a Profinch-facing contribution. The deliverable is a tool that lets
the pre-sales engineering team and technical mentor see, side by side, how
different model choices affect PRISM-style retrieval and synthesis on
quality, latency, and cost — without touching production PRISM or real
client RFP data. No academic framing, no report-writing concerns.

## 1. What "dummy PRISM" means here

Not a full clone. Scope is deliberately narrow: just the 5-stage retrieval
pipeline PRISM's own documentation describes — query embedding, candidate
filtering, cosine similarity search, cross-encoder reranking, threshold +
synthesis — running against a **synthetic** knowledge base of RFP-style
Q&A pairs. The synthetic data mimics the real KB's structure (same five
columns: serial number, question, RFP-level tag, module, answer) but
contains no actual Profinch client content. This matters beyond compliance
hygiene — a tool meant to be demoed around the team shouldn't carry data
that shouldn't leave its original access controls, even informally.

Explicitly out of scope: authentication, batch Excel processing, SharePoint
integration, multilingual translation, audit logging. None of that is what's
being compared, and building it would be scope creep dressed up as fidelity.

## 2. Two modes, not one

- **Eval mode**: a frozen synthetic eval set (with gold answers) runs
  against every architecture profile. Produces recall@5, MRR, faithfulness,
  and latency p95 per profile, stored per run. This is the evidence — the
  only output that should ever appear in a recommendation to the team.
- **Ad-hoc / demo mode**: type any question, pick 2+ profiles, see answers,
  latency, and cost side by side with no gold answer required. This exists
  for live demos to the pre-sales team or mentor. It is qualitative, not
  evidence, and should never be cited as a finding on its own.

The risk worth naming directly: a clean side-by-side UI makes ad-hoc mode
feel more authoritative than it is. Treat it as a way to *show* the eval
mode results convincingly, not as a second source of conclusions.

## 3. Architecture profiles (locked at three, unchanged rationale)

| Profile | Axis changed | Held constant | Hypothesis |
|---|---|---|---|
| `variant_embed` | Embedder: BGE-base → BGE-large / e5-large | reranker, synthesis model, chunking | Does a larger embedder raise Recall@5 on banking-jargon queries? |
| `variant_hybrid` | Retrieval: dense-only → hybrid dense+BM25 (RRF fusion) | embedder, reranker, synthesis model | Does lexical matching recover product-name queries dense retrieval misses? |
| `variant_llm` | Synthesis: Gemma 4B local → Cohere Command R (OCI) | embedder, retrieval, reranker | Does a stronger synthesis model raise faithfulness enough to justify cost/latency? |

`baseline` (BGE-base + cosine + MiniLM-L-6 reranker + Gemma 4B) is the
reference point for all three — never modified once eval mode is working.

## 4. System design

**Backend**: FastAPI, structured to mirror PRISM's actual `app/` layout
(routes / services / models split) so it reads familiarly to whoever at
Profinch reviews it later. Each profile is a self-contained module
implementing the same two-function interface as before.

**Frontend**: minimal React app — one screen, not a clone of PRISM's full
UI. Query box, profile selector (checkboxes for 2+ profiles), side-by-side
result cards, a metrics panel that switches between ad-hoc display (answer,
latency, cost) and eval display (recall/MRR/faithfulness table) depending
on mode.

```
prism-compare/
  CLAUDE.md
  ARCHITECTURE.md
  backend/
    app/
      routes/
        compare_routes.py     # POST /compare — ad-hoc, runs query against N profiles
        eval_routes.py        # POST /eval/run, GET /eval/report
      services/
        retrieval_service.py  # profile-aware: dispatches to the right profile module
        synthesis_service.py
        metrics_service.py    # recall@5, mrr, faithfulness, latency, cost
      profiles/
        baseline.py
        variant_embed.py
        variant_hybrid.py
        variant_llm.py
      core/
        config.py             # .env-driven, no hardcoded keys
      main.py
    requirements.txt
  frontend/
    src/
      pages/
        ComparePage.jsx
      components/
        ProfileSelector.jsx
        ResultCard.jsx
        MetricsPanel.jsx
  data/
    synthetic_kb.jsonl        # synthetic RFP-style Q&A — NEVER real client content
    eval_questions.jsonl      # frozen eval set with gold answers, same synthetic domain
  results/
    runs/                     # stored eval-mode run output, source of truth for the writeup
```

## 5. API surface

- `POST /compare` — `{query, profiles: [...], mode: "adhoc"}` → array of
  `{profile, answer, chunks, confidence, latency_ms, cost_estimate}`
- `POST /eval/run` — `{profile}` → runs the frozen eval set against that
  profile, stores results, returns aggregate metrics
- `GET /eval/report` — aggregate comparison table across every profile run
  so far, sourced only from `results/runs/`, never from ad-hoc calls

## 6. Phased milestones

1. **Phase 0** — synthetic KB + frozen eval set + `baseline` profile +
   `/eval/run` produces a complete metrics row. Blocking gate, same as before.
2. **Phase 1** — `variant_embed` implemented, eval mode run, results stored
3. **Phase 2** — `variant_hybrid` implemented, eval mode run, results stored
4. **Phase 3** — `variant_llm` implemented, eval mode run, results stored
5. **Phase 4** — frontend comparison screen wired to `/compare` and
   `/eval/report`; ad-hoc mode only ships once eval mode already has results
   for all four profiles, so the demo has real numbers behind it
6. **Phase 5** — write the actual recommendation for Profinch from
   `/eval/report` output, framed in the same cost/latency terms as the
   earlier OCI-vs-local model comparison

## 7. Risks

- **Demo polish creating false confidence** [Likely] — the side-by-side UI
  will look convincing even with thin eval coverage. Ad-hoc mode does not
  ship to anyone outside the dev loop until eval mode has real numbers.
- **Synthetic KB drifting into real content** [Certain risk if unmanaged] —
  it's tempting to paraphrase a real past RFP answer "for realism." Don't.
  Write the synthetic set from scratch or use clearly fictional banking
  scenarios.
- **Faithfulness metric is itself LLM-judged** [Certain] — spot-check 10-15
  judged cases by hand before trusting it at scale.
- **Variant LLM swap conflating model quality with prompt differences**
  [Likely] — the synthesis prompt template must be identical across
  `baseline`, `variant_embed`, and `variant_hybrid`; only `variant_llm` may
  change it, and only if the prompt itself is the documented variable.
- **Scope creep toward a full PRISM clone** [Certain risk] — the moment
  someone asks "should we also add batch upload to make it feel more real,"
  the answer is no — that's not what's being measured.
