from fastapi import FastAPI

from app.routes import compare_routes, eval_routes

app = FastAPI()

app.include_router(compare_routes.router)
app.include_router(eval_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
