import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

SYNTHETIC_KB_PATH = Path(
    os.getenv("SYNTHETIC_KB_PATH", str(PROJECT_ROOT / "data" / "synthetic_kb.jsonl"))
)
EVAL_QUESTIONS_PATH = Path(
    os.getenv("EVAL_QUESTIONS_PATH", str(PROJECT_ROOT / "data" / "eval_questions.jsonl"))
)
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", str(PROJECT_ROOT / "results" / "runs")))

BGE_MODEL_NAME = os.getenv("BGE_MODEL_NAME", "BAAI/bge-base-en-v1.5")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
RERANKER_CANDIDATES_MULTIPLIER = int(os.getenv("RERANKER_CANDIDATES_MULTIPLIER", "4"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

ANTHROPIC_JUDGE_MODEL = os.getenv("ANTHROPIC_JUDGE_MODEL", "claude-haiku-4-5-20251001")
