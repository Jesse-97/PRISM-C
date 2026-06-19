import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import config
from app.services.eval_runner import run_eval

router = APIRouter()


class EvalRunRequest(BaseModel):
    profile: str = "baseline"
    limit: int | None = None


@router.post("/eval/run")
def eval_run(request: EvalRunRequest):
    try:
        return run_eval(request.profile, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/eval/report")
def eval_report():
    runs = []
    for path in config.RESULTS_DIR.glob("*.json"):
        with path.open("r", encoding="utf-8") as f:
            runs.append(json.load(f))
    runs.sort(key=lambda r: r["timestamp"], reverse=True)
    return runs
