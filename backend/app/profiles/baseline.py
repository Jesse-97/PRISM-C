"""Reference profile: BGE-base + cosine similarity + MiniLM-L-6 reranker + Gemma 4B. No axis changed; this is the baseline."""

import json
import time

import faiss
import httpx
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.core import config
from app.core.types import Chunk

SYNTHESIS_PROMPT_TEMPLATE = """You are answering a question using ONLY the context chunks below. \
Do not use any outside knowledge and never invent information that is not present in the context.

If the context does not contain the answer, respond exactly with: Not found in knowledge base

If the answer involves multiple steps, present them as a numbered list.

Context:
{context}

Question: {query}

Answer:"""

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

with config.SYNTHETIC_KB_PATH.open("r", encoding="utf-8") as _f:
    _KB_ENTRIES = [json.loads(line) for line in _f if line.strip()]

_BGE_MODEL = SentenceTransformer(config.BGE_MODEL_NAME)

_PASSAGE_EMBEDDINGS = _BGE_MODEL.encode(
    [entry["question"] for entry in _KB_ENTRIES],
    normalize_embeddings=True,
    convert_to_numpy=True,
).astype("float32")

_INDEX = faiss.IndexFlatIP(_PASSAGE_EMBEDDINGS.shape[1])
_INDEX.add(_PASSAGE_EMBEDDINGS)

_RERANKER = CrossEncoder(config.RERANKER_MODEL_NAME)


def retrieve(query: str, k: int) -> tuple[list[Chunk], float]:
    start = time.perf_counter()

    query_vec = _BGE_MODEL.encode(
        [QUERY_PREFIX + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    num_candidates = k * config.RERANKER_CANDIDATES_MULTIPLIER
    _, indices = _INDEX.search(query_vec, num_candidates)
    candidates = [_KB_ENTRIES[i] for i in indices[0] if i != -1]

    pairs = [(query, c["question"] + " " + c["answer"]) for c in candidates]
    rerank_scores = _RERANKER.predict(pairs)

    ranked = sorted(zip(candidates, rerank_scores), key=lambda pair: pair[1], reverse=True)[:k]

    chunks = [
        Chunk(
            id=c["id"],
            question=c["question"],
            answer=c["answer"],
            module=c["module"],
            score=float(score),
        )
        for c, score in ranked
    ]

    retrieval_ms = (time.perf_counter() - start) * 1000
    return chunks, retrieval_ms


def _format_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.question}\n{c.answer}" for i, c in enumerate(chunks))


def synthesize(query: str, chunks: list[Chunk]) -> tuple[str, float]:
    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(query=query, context=_format_context(chunks))

    start = time.perf_counter()
    try:
        response = httpx.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=300,
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(f"Ollama not reachable at {config.OLLAMA_HOST}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama request failed with status {response.status_code}: {response.text}"
        )

    synthesis_ms = (time.perf_counter() - start) * 1000
    return response.json()["response"], synthesis_ms
