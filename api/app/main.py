from fastapi import FastAPI

from app.errors import register_error_handlers

app = FastAPI(
    title="Tuition API",
    version="1.0.0",
    description="University tuition REST API.",
)

register_error_handlers(app)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}