from fastapi import FastAPI

app = FastAPI(
    title="Tuition API",
    version="1.0.0",
    description="University tuition REST API.",
)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}