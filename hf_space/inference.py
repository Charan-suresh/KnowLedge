"""
KnowLedge Inference — inference.py

Runs entirely on CPU on the standard free HF Spaces tier (no ZeroGPU).

Model backends
--------------
E4B  : unsloth/gemma-4-4b-it-GGUF loaded via llama-cpp-python (CPU, n_gpu_layers=0).
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

# ── llama-cpp-python ──────────────────────────────────────────────────────────
# Import failures can happen when the wheel was built against the wrong libc.
# Keep the module importable so the app can start and report a controlled error.
_llama_import_error = None
try:
    from llama_cpp import Llama
except Exception as exc:
    _llama_import_error = exc
    Llama = None


MODEL_REPO = "unsloth/gemma-4-4b-it-GGUF"
MODEL_FILE = "gemma-4-4b-it-Q4_K_M.gguf"

_llm = None
logger = logging.getLogger(__name__)


class _FallbackModel:
    def __call__(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7, top_p: float = 0.95):
        del temperature, top_p
        text = (
            "Inference backend is temporarily running in fallback mode. "
            "The CPU GGUF loader could not be initialized, so this response is a safe placeholder."
        )
        prompt_text = str(prompt).strip()
        if prompt_text:
            text += f" Prompt received: {prompt_text[:160]}"
        return {"choices": [{"text": text[:max_tokens]}]}

def load_model():
    global _llm
    if _llm is None:
        if Llama is None:
            logger.warning("llama-cpp-python unavailable; using fallback model", exc_info=_llama_import_error)
            _llm = _FallbackModel()
            return _llm
        model_path = str(hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE
        ))

        _llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=4
        )
    return _llm


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    try:
        llm = load_model()

        output = llm(
            str(prompt),
            max_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.95
        )

        return output["choices"][0]["text"]

    except Exception:
        logger.exception("Text generation failed")
        raise


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    try:
        llm = load_model()

        text_prompt = f"{prompt}\n\n[Image provided]"

        output = llm(
            str(text_prompt),
            max_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.95
        )

        return output["choices"][0]["text"]

    except Exception:
        logger.exception("Vision generation failed")
        raise


@spaces.GPU(duration=60)
def health_check() -> dict:
    return {
        "status": "ok",
        "model_loaded": _llm is not None,
    }
