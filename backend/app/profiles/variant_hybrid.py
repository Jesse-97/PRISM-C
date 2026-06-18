"""Changes only the retrieval strategy: dense-only -> hybrid dense+BM25 with RRF fusion."""


def retrieve(query, k):
    raise NotImplementedError


def synthesize(query, chunks):
    raise NotImplementedError
