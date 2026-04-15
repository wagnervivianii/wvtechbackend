from fastapi import FastAPI

app = FastAPI(
    title="WV Tech Solutions API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "wvtechsolutions-backend",
    }