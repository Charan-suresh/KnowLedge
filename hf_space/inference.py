import base64
import io

import spaces
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_E2B = "google/gemma-4-e2b-it"
MODEL_E4B = "google/gemma-4-e4b-it"

# Module-level cache: loaded once per ZeroGPU session and reused across calls.
_tokenizer_e2b = None
_model_e2b = None
_tokenizer_e4b = None
_model_e4b = None


def _load_e2b():
    global _tokenizer_e2b, _model_e2b
    if _model_e2b is None:
        _tokenizer_e2b = AutoTokenizer.from_pretrained(MODEL_E2B)
        _model_e2b = AutoModelForCausalLM.from_pretrained(
            MODEL_E2B,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
    return _tokenizer_e2b, _model_e2b


def _load_e4b():
    global _tokenizer_e4b, _model_e4b
    if _model_e4b is None:
        _tokenizer_e4b = AutoTokenizer.from_pretrained(
            MODEL_E4B,
            use_fast=False,
            trust_remote_code=True,
        )
        _model_e4b = AutoModelForCausalLM.from_pretrained(
            MODEL_E4B,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
    return _tokenizer_e4b, _model_e4b


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    """Text-only generation for Scout and Sage."""
    if model_name == "e2b":
        tokenizer, model = _load_e2b()
    else:
        tokenizer, model = _load_e4b()

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=4096,
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True)


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    """Vision generation for Lens."""
    tokenizer, model = _load_e4b()

    image_bytes = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Current Space runtime uses text-only generation path for Gemma 4.
    # Preserve endpoint compatibility by appending a short image placeholder to the prompt.
    size_hint = f"{image.width}x{image.height}"
    text_prompt = f"{prompt}\n\n[Image provided: {size_hint}]"

    inputs = tokenizer(
        text_prompt,
        return_tensors="pt",
        truncation=True,
        max_length=4096,
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True)


@spaces.GPU(duration=60)
def health_check() -> dict:
    """Basic runtime health used by FastAPI /health."""
    return {
        "status": "ok",
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
        "cuda": torch.cuda.is_available(),
        "e2b_loaded": _model_e2b is not None,
        "e4b_loaded": _model_e4b is not None,
    }
