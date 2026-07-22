"""Minimal Crawler API Service placeholder."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Intelligence Crawler Service")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str):
    """Placeholder endpoint - crawler service not yet implemented."""
    return JSONResponse(
        status_code=501,
        content={"error": "Crawler service placeholder - not implemented yet", "path": path}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8768)