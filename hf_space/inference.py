"""
KnowLedge Inference — inference.py

Runs on CPU using transformers library for better HF Spaces compatibility.

Model backends
--------------
E4B  : google/gemma-4-E4B-it loaded via transformers (CPU or GPU).
"""

import logging
from typing import Optional

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

# ── transformers ──────────────────────────────────────────────────────────────
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
except ModuleNotFoundError:
    AutoTokenizer = None
    AutoModelForCausalLM = None
    torch = None


MODEL_REPO = "google/gemma-4-E4B-it"

_tokenizer = None
_model = None
_load_error: Optional[str] = None
logger = logging.getLogger(__name__)


def load_model():
    global _tokenizer, _model, _load_error
    if _model is not None:
        return _tokenizer, _model

    if AutoTokenizer is None or AutoModelForCausalLM is None:
        raise RuntimeError(
            "transformers is not installed. "
            "Add it to hf_space/requirements.txt."
        )

    logger.info(f"Loading model {MODEL_REPO}...")
    _load_error = None
    try:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_REPO,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else "cpu",
            trust_remote_code=True,
        )
        logger.info("Model loaded successfully")
    except Exception as exc:
        _load_error = str(exc)
        _model = None
        _tokenizer = None
        logger.exception("Model load failed")
        raise

    return _tokenizer, _model


def health_check() -> dict:
    """Non-blocking health check — reports current load state without triggering a load."""
    loaded = _model is not None
    result = {
        "status": "ok" if loaded else ("error" if _load_error else "loading"),
        "model_loaded": loaded,
        "backend": "transformers",
        "model_repo": MODEL_REPO,
        "model_file": MODEL_REPO,
    }
    if loaded and torch is not None:
        try:
            result["device"] = str(next(_model.parameters()).device)
        except Exception:
            result["device"] = "unknown"
    if _load_error:
        result["error"] = _load_error
    return result


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    tokenizer, model = load_model()

    # Format prompt for Gemma chat template
    formatted_prompt = (
        f"<bos><start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
    )

    inputs = tokenizer(formatted_prompt, return_tensors="pt")

    # Move inputs to the same device as the model
    if torch.cuda.is_available():
        try:
            target_device = next(model.parameters()).device
            inputs = {k: v.to(target_device) for k, v in inputs.items()}
        except Exception:
            pass  # best-effort; let model.generate raise if there's still a mismatch

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the newly generated tokens
    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    return response.strip()


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    """
    Vision inference. Gemma 4 E4B is multimodal; we pass the image via the
    transformers AutoProcessor when available, otherwise fall back to text-only.
    """
    try:
        from transformers import AutoProcessor
        import base64, io
        from PIL import Image

        tokenizer, model = load_model()

        # Try loading a processor (supports vision inputs)
        try:
            processor = AutoProcessor.from_pretrained(MODEL_REPO, trust_remote_code=True)
        except Exception:
            processor = None

        if processor is not None:
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            inputs = processor(text=prompt, images=image, return_tensors="pt")
            if torch.cuda.is_available():
                try:
                    target_device = next(model.parameters()).device
                    inputs = {k: v.to(target_device) for k, v in inputs.items()}
                except Exception:
                    pass
            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
            input_len = inputs["input_ids"].shape[1]
            response = processor.decode(outputs[0][input_len:], skip_special_tokens=True)
            return response.strip()

    except Exception:
        logger.warning("Vision processor unavailable — falling back to text-only", exc_info=True)

    # Text-only fallback (image content described in prompt)
    text_prompt = f"{prompt}\n\n[Note: image could not be processed — responding based on text context only]"
    return generate_text("e4b", text_prompt, max_new_tokens)
