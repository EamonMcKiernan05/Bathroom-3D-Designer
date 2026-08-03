"""FastAPI app entrypoint."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from .routers import designs, plans, products, textures

# Project root: apps/api/app/<file> -> repo root (4 levels up)
ROOT = Path(__file__).resolve().parent.parent.parent.parent
ASSETS = ROOT / "assets"

app = FastAPI(title="Bathroom Designer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — auth deferred until public launch
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(textures.router)
app.include_router(designs.router)
app.include_router(plans.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok", "service": "bathroom-designer-api"}


# Demo asset serving — replaces MinIO for local dev (doc 04 §3: MinIO in production).
# GLB models + textures served straight from the repo assets dir.
for mount, rel in (("/models", "models"), ("/textures", "textures"), ("/thumbnails", "thumbnails")):
    p = ASSETS / rel
    p.mkdir(parents=True, exist_ok=True)
    app.mount(mount, StaticFiles(directory=p), name=rel)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
