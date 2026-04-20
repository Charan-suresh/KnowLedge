from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

try:
    from inference import generate_text, generate_with_image, health_check
except ModuleNotFoundError:
    from .inference import generate_text, generate_with_image, health_check

app = FastAPI()


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "e2b"
    max_tokens: int = 512


class VisionRequest(BaseModel):
    prompt: str
    image_base64: str
    max_tokens: int = 512


@app.get("/")
def root():
    return {"message": "KnowLedge Inference API is running"}


@app.get("/api/health")
def health():
    try:
        return health_check()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        model_name = "e2b" if "e2b" in req.model.lower() else "e4b"
        response = generate_text(model_name, req.prompt, req.max_tokens)
        return {"response": response}
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/api/generate_vision")
def generate_vision(req: VisionRequest):
    try:
        response = generate_with_image(
            req.prompt,
            req.image_base64,
            req.max_tokens,
        )
        return {"response": response}
    except Exception as exc:
        return {"error": str(exc)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
