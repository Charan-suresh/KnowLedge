"""
KnowLedge Inference — inference.py

Runs entirely on CPU on the standard free HF Spaces tier (no ZeroGPU).

Model backends
--------------
Text : Gemma via transformers (CPU-safe, no llama-cpp native binaries).
"""

import base64
import io
import logging
import os

from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

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

# ── transformers backend ──────────────────────────────────────────────────────
TEXT_MODEL_ID = os.getenv("GEMMA_TEXT_MODEL", "google/gemma-2-2b-it")

_bundle = None
logger = logging.getLogger(__name__)


class _ModelBundle:
    def __init__(self, tokenizer: AutoTokenizer, model: AutoModelForCausalLM):
        self.tokenizer = tokenizer
        self.model = model


def load_model() -> _ModelBundle:
    global _bundle
    if _bundle is None:
        try:
            tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_ID)
            model = AutoModelForCausalLM.from_pretrained(
                TEXT_MODEL_ID,
                torch_dtype=torch.float32,
            )
            model.eval()
            _bundle = _ModelBundle(tokenizer=tokenizer, model=model)
        except Exception as exc:
            logger.exception("Transformers model initialization failed")
            raise RuntimeError(
                f"Failed to initialize transformers model '{TEXT_MODEL_ID}': {exc}"
            ) from exc
    return _bundle


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    del model_name
    try:
        bundle = load_model()
        text_prompt = str(prompt)

        inputs = bundle.tokenizer(text_prompt, return_tensors="pt")
        with torch.no_grad():
            output_ids = bundle.model.generate(
                **inputs,
                max_new_tokens=min(max_new_tokens, 256),
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
                pad_token_id=bundle.tokenizer.eos_token_id,
            )

        generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        response = bundle.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        return response or ""

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
        "model_loaded": _bundle is not None,
        "backend": "transformers",
        "model": TEXT_MODEL_ID,
    }
