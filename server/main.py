from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import apps, auth, questions
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="大模型应用自动调优平台",
    description="应用接入 → 测试集切分 → 评测闭环调优",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(apps.router)
app.include_router(questions.router)


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}


@app.get("/", tags=["meta"])
def index():
    return {
        "name": app.title,
        "version": app.version,
        "routes": sorted(
            f"{sorted(r.methods)[0]} {r.path}"
            for r in app.routes
            if getattr(r, "methods", None) and r.path.startswith(("/auth", "/apps", "/health"))
        ),
    }


if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
