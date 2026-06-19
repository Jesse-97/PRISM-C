"""Runs the frozen eval set against a profile and writes a metrics row to results/runs/."""

import json
import time
from datetime import datetime

from app.core import config
from app.services import metrics_service, retrieval_service, synthesis_service

MIN_QUESTIONS_ABORT = 20
MIN_QUESTIONS_WARN = 50


def _load_questions() -> list[dict]:
    if not config.EVAL_QUESTIONS_PATH.exists():
        raise ValueError(f"Eval questions file not found: {config.EVAL_QUESTIONS_PATH}")

    questions = []
    try:
        with config.EVAL_QUESTIONS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    questions.append(json.loads(line))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed eval questions file: {exc}") from exc

    for q in questions:
        for field in ("id", "query", "gold_answer", "gold_doc_ids"):
            if field not in q:
                raise ValueError(f"Eval question missing required field '{field}': {q}")

    return questions


def _retrieve_with_timing(profile: str, query: str, k: int):
    start = time.perf_counter()
    result = retrieval_service.retrieve(profile, query, k)
    # baseline.py returns (chunks, retrieval_ms) since it times itself; fall back
    # to timing the call here if a profile ever returns the bare List[Chunk] contract.
    if isinstance(result, tuple) and len(result) == 2:
        return result
    return result, (time.perf_counter() - start) * 1000


def _synthesize_with_timing(profile: str, query: str, chunks):
    start = time.perf_counter()
    result = synthesis_service.synthesize(profile, query, chunks)
    if isinstance(result, tuple) and len(result) == 2:
        return result
    return result, (time.perf_counter() - start) * 1000


def run_eval(profile: str, limit: int | None = None) -> dict:
    questions = _load_questions()
    if limit is not None:
        questions = questions[:limit]

    total = len(questions)
    if total < MIN_QUESTIONS_ABORT:
        raise ValueError(
            f"Only {total} eval questions — minimum {MIN_QUESTIONS_ABORT} required to run."
        )
    if total < MIN_QUESTIONS_WARN:
        print(
            f"[run_eval] WARNING: only {total} eval questions "
            f"(recommended minimum {MIN_QUESTIONS_WARN})",
            flush=True,
        )

    records = []
    skipped_count = 0

    for i, q in enumerate(questions, start=1):
        chunks, retrieval_ms = _retrieve_with_timing(profile, q["query"], config.RETRIEVAL_TOP_K)
        answer, synthesis_ms = _synthesize_with_timing(profile, q["query"], chunks)

        retrieved_ids = [c.id for c in chunks]
        gold_ids = q["gold_doc_ids"]

        if gold_ids:
            recall = metrics_service.recall_at_k(retrieved_ids, gold_ids, k=5)
            mrr_score = metrics_service.mrr(retrieved_ids, gold_ids)
        else:
            # No-answer query: correctly declining to answer (top chunk score below
            # the confidence threshold) counts as a hit for both recall and MRR.
            top_score = chunks[0].score if chunks else 0.0
            hit = 1.0 if top_score < config.CONFIDENCE_THRESHOLD else 0.0
            recall = hit
            mrr_score = hit

        faithfulness = metrics_service.judge_faithfulness(q["query"], chunks, answer)
        if faithfulness is None:
            skipped_count += 1

        print(
            f"[{i}/{total}] query_id={q['id']} recall={recall} mrr={mrr_score:.3f} "
            f"faithfulness={'skipped' if faithfulness is None else faithfulness} "
            f"retrieval_ms={retrieval_ms:.1f} synthesis_ms={synthesis_ms:.1f}",
            flush=True,
        )

        records.append(
            {
                "id": q["id"],
                "query": q["query"],
                "recall": recall,
                "mrr": mrr_score,
                "faithfulness": faithfulness,
                "retrieval_ms": retrieval_ms,
                "synthesis_ms": synthesis_ms,
            }
        )

    judged_scores = [r["faithfulness"] for r in records if r["faithfulness"] is not None]
    total_latencies = [r["retrieval_ms"] + r["synthesis_ms"] for r in records]

    aggregate = {
        "recall_at_5_mean": sum(r["recall"] for r in records) / total,
        "mrr_mean": sum(r["mrr"] for r in records) / total,
        "faithfulness_pass_rate": (
            sum(judged_scores) / len(judged_scores) if judged_scores else None
        ),
        "faithfulness_judge_skipped": skipped_count > 0,
        "faithfulness_skipped_count": skipped_count,
        "latency_p50": metrics_service.latency_percentile(total_latencies, p=50),
        "latency_p95": metrics_service.latency_percentile(total_latencies, p=95),
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = config.RESULTS_DIR / f"{profile}_{timestamp}.json"
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "profile": profile,
                "timestamp": timestamp,
                "per_query": records,
                "aggregate": aggregate,
            },
            f,
            indent=2,
        )

    return aggregate
