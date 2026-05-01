import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from inference import generate_text, generate_with_image, health_check, load_model
except ModuleNotFoundError:
    from .inference import generate_text, generate_with_image, health_check, load_model

logger = logging.getLogger(__name__)


def _preload_model() -> None:
    """Load the model in the background at startup so the first inference request
    doesn't pay the full cold-start cost."""
    try:
        load_model()
        logger.info("Model preloaded at startup")
    except Exception:
        logger.exception("Background model preload failed — will retry on first request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_preload_model, daemon=True, name="model-preloader").start()
    yield


app = FastAPI(lifespan=lifespan)


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "e4b"
    max_tokens: int = 512


class VisionRequest(BaseModel):
    prompt: str
    image_base64: str
    model: str = "e4b"
    max_tokens: int = 512


@app.get("/")
def root():
    return {"message": "KnowLedge Inference API is running"}


@app.get("/api/health")
def health():
    # health_check() is now non-blocking — just reports current load state
    return health_check()


@app.post("/api/generate")
def generate(req: GenerateRequest):
    model_name = "e2b" if "e2b" in req.model.lower() else "e4b"
    try:
        response = generate_text(model_name, req.prompt, req.max_tokens)
        return {"response": response}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Text generation error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/generate_vision")
def generate_vision(req: VisionRequest):
    try:
        response = generate_with_image(req.prompt, req.image_base64, req.max_tokens)
        return {"response": response}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Vision generation error")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
