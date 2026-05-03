"""
KnowLedge Inference — inference.py

Requires transformers>=5.0.0.  Gemma 4 (E4B) is a multimodal model whose
architecture is Gemma4ForConditionalGeneration (added in transformers 5.x).

ZeroGPU pattern
---------------
* Model loaded on CPU at startup with torch_dtype=torch.bfloat16 (~8 GB RAM).
* Each @spaces.GPU() call gets a real CUDA device; we move model → cuda there,
  run generation, then move back → cpu and empty the cache so the next request
  can reuse the shared GPU slot.
* health_check() is lightweight — it never triggers model download.
"""
import base64, io, logging, sys, re

logger = logging.getLogger(__name__)

try:
    import spaces
except ModuleNotFoundError:
    class _SpacesStub:
        @staticmethod
        def GPU(duration: int = 60):
            def decorator(fn): return fn
            return decorator
    spaces = _SpacesStub()

_import_error = None
HAS_TRANSFORMERS = False
Gemma4Processor = None
AutoModelForCausalLM = None
torch = None

try:
    from transformers import Gemma4Processor, AutoModelForCausalLM
    import torch
    HAS_TRANSFORMERS = True
except Exception as _e:
    _import_error = f"{type(_e).__name__}: {_e}"

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

MODEL_REPO = "unsloth/gemma-4-E4B-it"
_processor = None
_model = None


def load_model():
    """Load model on CPU with bfloat16 (lazy, once only)."""
    global _processor, _model
    if _model is not None:
        return _processor, _model
    if not HAS_TRANSFORMERS:
        raise RuntimeError(f"transformers import failed: {_import_error}")
    logger.info("Loading %s on CPU (bfloat16)…", MODEL_REPO)
    _processor = Gemma4Processor.from_pretrained(MODEL_REPO)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_REPO,
        torch_dtype=torch.bfloat16,   # ~8 GB — NOT dtype= which is silently ignored
        low_cpu_mem_usage=True,        # stream weights, lower peak RAM
    )
    _model.eval()
    logger.info("Model loaded. Device: %s", next(_model.parameters()).device)
    return _processor, _model


@spaces.GPU(duration=90)
def generate_text(model_name: str, prompt: str, max_new_tokens: int = 512) -> str:
    processor, model = load_model()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("generate_text: device=%s cuda_available=%s", device, torch.cuda.is_available())
    model.to(device)
    try:
        messages = [
            {"role": "system", "content": "You are a helpful educational assistant."},
            {"role": "user",   "content": prompt},
        ]
        try:
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            inputs = processor(text=text, return_tensors="pt").to(device)
        except TypeError:
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = processor(text, return_tensors="pt").to(device)

        input_len = inputs["input_ids"].shape[-1]
        eos = (
            processor.tokenizer.eos_token_id
            if hasattr(processor, "tokenizer")
            else processor.eos_token_id
        )
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=1.0, top_p=0.95, top_k=64, do_sample=True,
                pad_token_id=eos,
            )
        raw = processor.decode(outputs[0][input_len:], skip_special_tokens=True)
        return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    finally:
        model.to("cpu")
        if device == "cuda" and torch is not None:
            torch.cuda.empty_cache()


@spaces.GPU(duration=120)
def generate_with_image(prompt: str, image_base64: str, max_new_tokens: int = 512) -> str:
    processor, model = load_model()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("generate_with_image: device=%s cuda_available=%s", device, torch.cuda.is_available())
    model.to(device)
    try:
        try:
            image = Image.open(io.BytesIO(base64.b64decode(image_base64))).convert("RGB")
        except Exception:
            return generate_text("e4b", prompt, max_new_tokens)
        try:
            messages = [{"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text": prompt},
            ]}]
            inputs = processor.apply_chat_template(
                messages, tokenize=True, return_dict=True,
                return_tensors="pt", add_generation_prompt=True,
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except Exception:
            return generate_text("e4b", prompt, max_new_tokens)
        input_len = inputs["input_ids"].shape[-1]
        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=max_new_tokens,
                temperature=1.0, top_p=0.95, top_k=64, do_sample=True,
            )
        raw = processor.decode(outputs[0][input_len:], skip_special_tokens=True)
        return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    finally:
        model.to("cpu")
        if device == "cuda" and torch is not None:
            torch.cuda.empty_cache()


def health_check() -> dict:
    """Lightweight health check — does NOT trigger model download."""
    import transformers
    has_cuda = torch.cuda.is_available() if torch is not None else False
    return {
        "backend": "transformers",
        "transformers_version": transformers.__version__,
        "model_repo": MODEL_REPO,
        "has_transformers": HAS_TRANSFORMERS,
        "import_error": _import_error,
        "python": sys.version,
        "cuda_available": has_cuda,
        "model_loaded": _model is not None,
        "status": "ok" if HAS_TRANSFORMERS else "error",
        "device": str(next(_model.parameters()).device) if _model is not None else "not_loaded_yet",
    }
