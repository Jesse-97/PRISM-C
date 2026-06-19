"""Computes recall@5, MRR, faithfulness, and latency for eval runs."""

from app.core import config
from app.core.types import Chunk

JUDGE_PROMPT_TEMPLATE = """Is every claim in the answer fully supported by the provided chunks? Answer 0 or 1.

Context:
{context}

Answer:
{answer}"""


def recall_at_k(retrieved_ids: list[str], gold_ids: list[str], k: int = 5) -> float:
    return 1.0 if any(rid in gold_ids for rid in retrieved_ids[:k]) else 0.0


def mrr(retrieved_ids: list[str], gold_ids: list[str]) -> float:
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in gold_ids:
            return 1.0 / rank
    return 0.0


def latency_percentile(latencies_ms: list[float], p: float = 95) -> float:
    if not latencies_ms:
        return 0.0
    data = sorted(latencies_ms)
    n = len(data)
    if n == 1:
        return float(data[0])
    rank = (p / 100) * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    frac = rank - lower
    return data[lower] + (data[upper] - data[lower]) * frac


def _format_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.question}\n{c.answer}" for i, c in enumerate(chunks))


def judge_faithfulness(query: str, chunks: list[Chunk], answer: str) -> bool | None:
    # TEMPORARY: stubbed pending ANTHROPIC_API_KEY, see CLAUDE.md for the real spec
    if not config.ANTHROPIC_API_KEY:
        print(
            f"[judge_faithfulness] SKIPPED — ANTHROPIC_API_KEY not set, "
            f"faithfulness not scored for query={query!r}",
            flush=True,
        )
        return None

    import anthropic

    prompt = JUDGE_PROMPT_TEMPLATE.format(context=_format_context(chunks), answer=answer)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=config.ANTHROPIC_JUDGE_MODEL,
            max_tokens=4,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"Anthropic judge call failed with status {exc.status_code}: {exc.message}"
        ) from exc

    verdict = response.content[0].text.strip()
    return verdict.startswith("1")
