from fastapi import FastAPI

from app.api import file, stream
from app.core.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(file.router)
app.include_router(stream.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
