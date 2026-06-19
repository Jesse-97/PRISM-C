from dataclasses import dataclass


@dataclass
class Chunk:
    id: str
    question: str
    answer: str
    module: str
    score: float
