"""
KnowLedge Inference — inference.py

Runs on CPU using transformers library for better HF Spaces compatibility.

Model backends
--------------
E4B  : unsloth/gemma-4-4b-it loaded via transformers (CPU).
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


MODEL_REPO = "unsloth/gemma-4-4b-it"

_tokenizer = None
_model = None
logger = logging.getLogger(__name__)


def load_model():
    global _tokenizer, _model
    if _model is None:
        if AutoTokenizer is None or AutoModelForCausalLM is None:
            raise RuntimeError(
                "transformers is not installed. "
                "Add it to hf_space/requirements.txt."
            )
        
        logger.info(f"Loading model {MODEL_REPO}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_REPO,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else "cpu",
            trust_remote_code=True
        )
        logger.info("Model loaded successfully")
    
    return _tokenizer, _model


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    try:
        tokenizer, model = load_model()
        
        # Format prompt for Gemma
        formatted_prompt = f"<bos><start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        
        inputs = tokenizer(formatted_prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                top_p=0.95,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        # Decode only the new tokens
        response = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], 
            skip_special_tokens=True
        )
        
        return response.strip()

    except Exception:
        logger.exception("Text generation failed")
        raise


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    try:
        # For now, treat as text-only since Gemma 4 vision support varies
        text_prompt = f"{prompt}\n\n[Image provided - analyzing as text prompt]"
        return generate_text("e4b", text_prompt, max_new_tokens)

    except Exception:
        logger.exception("Vision generation failed")
        raise


@spaces.GPU(duration=60)
def health_check() -> dict:
    try:
        tokenizer, model = load_model()
        return {
            "status": "ok",
            "model_loaded": True,
            "backend": "transformers",
            "model_repo": MODEL_REPO,
            "device": str(next(model.parameters()).device) if model else "unknown"
        }
    except Exception as e:
        return {
            "status": "error", 
            "model_loaded": False,
            "backend": "transformers",
            "model_repo": MODEL_REPO,
            "error": str(e)
        }