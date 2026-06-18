"""Reference profile: BGE-base + cosine similarity + MiniLM-L-6 reranker + Gemma 4B. No axis changed; this is the baseline."""


def retrieve(query, k):
    raise NotImplementedError


def synthesize(query, chunks):
    raise NotImplementedError
