"""
KnowLedge Inference Space — hf_space/app.py

Architecture:
  FastAPI provides the REST endpoints (/api/generate, /api/generate_vision, /api/health).
  Gradio is mounted at the root so the HF Space is recognised as sdk:gradio, which lets
  it serve traffic on port 7860 without a custom Dockerfile.

  Inference runs entirely on CPU on the standard free HF Spaces tier:
    - E4B  : unsloth/gemma-4-E4B-it-GGUF  (UD-IQ3_XXS, ~2.5 GB, llama-cpp-python)
    - E2B  : google/gemma-4-e2b-it         (float32, transformers)

Render backend calls the FastAPI endpoints via httpx.
Visiting the Space URL in a browser shows the Gradio landing page.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import gradio as gr
except ModuleNotFoundError:
    gr = None

try:
    from inference import generate_text, generate_with_image, health_check
except ModuleNotFoundError:
    from .inference import generate_text, generate_with_image, health_check


# ── FastAPI application ───────────────────────────────────────────────────────

_api = FastAPI(title="KnowLedge Inference API", version="1.0.0")

# Allow the Render backend (and any browser preview) to call these endpoints.
_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "e2b"
    max_tokens: int = 512


class VisionRequest(BaseModel):
    prompt: str
    image_base64: str
    max_tokens: int = 512


@_api.get("/api/health")
def health():
    """Health check — called by the Render backend before every inference batch."""
    try:
        return health_check()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@_api.post("/api/generate")
def generate(req: GenerateRequest):
    """Text generation endpoint used by Scout (concept tagging) and Sage (dialogue)."""
    try:
        model_name = "e2b" if "e2b" in req.model.lower() else "e4b"
        response = generate_text(model_name, req.prompt, req.max_tokens)
        return {"response": response}
    except Exception as exc:
        return {"error": str(exc)}


@_api.post("/api/generate_vision")
def generate_vision(req: VisionRequest):
    """Vision generation endpoint used by Lens (handwriting verification)."""
    try:
        response = generate_with_image(
            req.prompt,
            req.image_base64,
            req.max_tokens,
        )
        return {"response": response}
    except Exception as exc:
        return {"error": str(exc)}


# ── Gradio UI ─────────────────────────────────────────────────────────────────
# A minimal Gradio interface is required so that:
#   1. The HF Space is recognised as sdk:gradio and served on port 7860.
#   2. The Space shows a readable landing page instead of a blank iframe.
# No ZeroGPU needed — inference runs on CPU via llama-cpp-python (GGUF).

if gr is not None:
    with gr.Blocks(title="KnowLedge Inference API") as demo:
        gr.Markdown(
            """
            # 🦉 KnowLedge Inference API

            Gemma 4 **E2B** + **E4B** inference backend for the
            [KnowLedge](https://github.com/Charan-suresh/KnowLedge) learning ledger.

            Part of the **Kaggle Gemma 4 for Good** hackathon submission.

            ---

            This Space is a **REST API backend** — it is called programmatically by the
            KnowLedge FastAPI service deployed on Render. It is not a chat interface.

            | Endpoint | Method | Used by |
            |---|---|---|
            | `/api/generate` | POST | Scout (concept tagging), Sage (Socratic dialogue) |
            | `/api/generate_vision` | POST | Lens (handwriting verification) |
            | `/api/health` | GET | Render backend health check |

            ### Payload format — `/api/generate`
            ```json
            { "model": "e2b", "prompt": "...", "max_tokens": 512 }
            ```

            ### Payload format — `/api/generate_vision`
            ```json
            { "prompt": "...", "image_base64": "<base64>", "max_tokens": 512 }
            ```
            """
        )

    # Mount the Gradio interface into the FastAPI app.
    # FastAPI routes registered above (/api/*) take priority over Gradio routes.
    # Gradio occupies the root path ("/") for the HF Space iframe.
    app = gr.mount_gradio_app(_api, demo, path="/")
else:
    # Local fallback for test and dev environments without gradio installed.
    app = _api


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
