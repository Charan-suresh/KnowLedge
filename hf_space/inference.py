"""
KnowLedge Inference — inference.py

Runs entirely on CPU on the standard free HF Spaces tier (no ZeroGPU).

Model backends
--------------
Text : Quantized Gemma 2B GGUF via llama-cpp-python (CPU-only).
"""

import base64
import io
import logging
import os

from PIL import Image
from huggingface_hub import hf_hub_download

# ── spaces stub — GPU decorator is a no-op on the free CPU tier ───────────────
try:
    import spaces
except ModuleNotFoundError:
    class _SpacesStub:
        @staticmethod
        def GPU(duration: int = 0):
            def decorator(fn):
                return fn
            return decorator

    spaces = _SpacesStub()

# ── llama-cpp backend ─────────────────────────────────────────────────────────
_llama_import_error = None
try:
    from llama_cpp import Llama
except Exception as exc:
    _llama_import_error = exc
    Llama = None

MODEL_REPO = os.getenv("GEMMA_2B_GGUF_REPO", "bartowski/gemma-2-2b-it-GGUF")
MODEL_FILE = os.getenv("GEMMA_2B_GGUF_FILE", "gemma-2-2b-it-Q4_K_M.gguf")

# Try common filename variants in case upstream naming changes.
MODEL_FILE_CANDIDATES = [
    MODEL_FILE,
    "gemma-2-2b-it-Q4_K_M.gguf",
    "gemma-2-2b-it-Q5_K_M.gguf",
    "gemma-2-2b-it-Q8_0.gguf",
]

_llm = None
_last_model_error = ""
logger = logging.getLogger(__name__)


class _FallbackModel:
    def __call__(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7, top_p: float = 0.95):
        del temperature, top_p
        text = (
            "Inference backend is temporarily running in fallback mode. "
            "The Gemma 2B GGUF model could not be initialized on this runtime."
        )
        prompt_text = str(prompt).strip()
        if prompt_text:
            text += f" Prompt received: {prompt_text[:160]}"
        return {"choices": [{"text": text[:max_tokens]}]}


def _download_model_file() -> str:
    last_error = None
    seen = set()
    for filename in MODEL_FILE_CANDIDATES:
        if filename in seen:
            continue
        seen.add(filename)
        try:
            return str(hf_hub_download(repo_id=MODEL_REPO, filename=filename))
        except Exception as exc:
            last_error = exc
            logger.warning("Failed to download GGUF file '%s' from %s", filename, MODEL_REPO)

    raise RuntimeError(
        f"Could not download a GGUF file from '{MODEL_REPO}'. "
        f"Tried: {MODEL_FILE_CANDIDATES}. Last error: {last_error}"
    )


def load_model():
    global _llm, _last_model_error
    if _llm is None:
        if Llama is None:
            _last_model_error = f"llama-cpp import failed: {_llama_import_error}"
            logger.error(_last_model_error)
            _llm = _FallbackModel()
            return _llm

        try:
            model_path = _download_model_file()
            _llm = Llama(
                model_path=model_path,
                n_ctx=int(os.getenv("GEMMA_2B_CTX", "4096")),
                n_threads=int(os.getenv("GEMMA_2B_THREADS", "4")),
                n_gpu_layers=0,
            )
            _last_model_error = ""
        except Exception:
            logger.exception("Gemma 2B GGUF initialization failed; falling back")
            _last_model_error = "gguf initialization failed; check Space logs for traceback"
            _llm = _FallbackModel()
    return _llm


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    del model_name
    try:
        llm = load_model()
        output = llm(
            str(prompt),
            max_tokens=min(max_new_tokens, 512),
            temperature=0.7,
            top_p=0.95,
        )
        return output["choices"][0]["text"].strip()

    except Exception:
        logger.exception("Text generation failed")
        raise


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    try:
        _ = Image.open(io.BytesIO(base64.b64decode(image_base64)))
        text_prompt = f"{prompt}\n\n[Image provided and parsed on client-side.]"
        return generate_text("e2b", text_prompt, max_new_tokens)

    except Exception:
        logger.exception("Vision generation failed")
        raise


@spaces.GPU(duration=60)
def health_check() -> dict:
    return {
        "status": "ok",
        "model_loaded": _llm is not None and not isinstance(_llm, _FallbackModel),
        "backend": "llama-cpp",
        "model_repo": MODEL_REPO,
        "model_file": MODEL_FILE,
        "model_error": _last_model_error or None,
    }
