from fastapi import FastAPI
from pydantic import BaseModel
from inference import generate_text, generate_with_image, health_check
import uvicorn

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
    return health_check()


@app.post("/api/generate")
def generate(req: GenerateRequest):
    model_name = "e2b" if "e2b" in req.model.lower() else "e4b"
    response = generate_text(model_name, req.prompt, req.max_tokens)
    return {"response": response}


@app.post("/api/generate_vision")
def generate_vision(req: VisionRequest):
    response = generate_with_image(
        req.prompt,
        req.image_base64,
        req.max_tokens,
    )
    return {"response": response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
