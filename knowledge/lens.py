import json
import base64
from dataclasses import dataclass
from typing import Optional, List
import re
import logging
from PIL import Image
import io
import httpx
from . import config
from .agents.inference_router import chat

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


logger = logging.getLogger(__name__)

ALLOWED_LENS_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}

@dataclass
class ExaminerResult:
    x: int
    y: int
    width: int
    height: int
    explanation: str
    handwritten: bool = False
    has_issue: bool = False
    confidence: float = 0.0
    audio_bytes: Optional[bytes] = None


def _strip_data_uri_prefix(image_b64: str) -> str:
    value = (image_b64 or "").strip()
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1].strip()
    return value


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1"}:
            return True
        if v in {"false", "no", "0", ""}:
            return False
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _parse_json_payload(raw: str) -> dict:
    content = (raw or "").strip()
    if not content:
        return {}

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    fenced = content.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(fenced)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}

    return {}


def _ollama_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.OLLAMA_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {config.OLLAMA_AUTH_TOKEN}"
    return headers


def _select_vision_model() -> str:
    configured = (config.LENS_MODEL or "").strip()
    if config.INFERENCE_BACKEND != "ollama":
        return configured

    models = config.fetch_ollama_models(config.OLLAMA_BASE_URL)
    multimodal_keywords = ("llava", "gemma3", "vision", "moondream", "bakllava")
    for name in models:
        lowered = (name or "").lower()
        if any(k in lowered for k in multimodal_keywords):
            return name
    return configured


def _vision_chat_json(prompt: str, image_b64: str, model_name: str) -> dict:
    clean_b64 = _strip_data_uri_prefix(image_b64)
    if config.INFERENCE_BACKEND == "ollama":
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": [clean_b64],
            "stream": False,
        }
        url = f"{config.OLLAMA_BASE_URL}/api/generate"
        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(url, json=payload, headers=_ollama_headers())
                if response.status_code >= 400:
                    logger.error("Lens Ollama failure status=%s body=%s", response.status_code, response.text)
                    response.raise_for_status()
                return response.json()
        except Exception:
            logger.exception("Lens Ollama vision request failed; falling back to chat interface")

    response = chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt, "images": [clean_b64]}],
        format="json",
    )
    return response


def _render_pdf_pages(pdf_bytes: bytes) -> tuple[list[bytes], str]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for PDF support. Install pymupdf.")
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(document)
    if total_pages == 0:
        return [], ""

    note = ""
    if total_pages <= 5:
        indices = list(range(total_pages))
    else:
        indices = [0, 1, 2, total_pages - 2, total_pages - 1]
        note = "large document — showing representative pages."

    page_images: list[bytes] = []
    for idx in indices:
        page = document.load_page(idx)
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        pil_image = Image.open(io.BytesIO(png_bytes))
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        page_images.append(buf.getvalue())
    return page_images, note


def _handwriting_prompt(expected_elements: List[str]) -> str:
    return (
        "Analyze this image carefully. Answer each question with YES or NO \n"
        "and a brief reason:\n"
        "1. Is this a handwritten document (not typed or digitally generated)?\n"
        "2. Does it contain a diagram, sketch, or visual representation?\n"
        f"3. Can you identify any of these elements: {expected_elements}?\n"
        "4. Does the handwriting appear to be genuine (irregular strokes, \n"
        "natural pen pressure variation, imperfect lines)?\n\n"
        "Then provide:\n"
        "- elements_found: list only elements you can clearly see\n"
        "- is_handwritten: true/false\n"
        "- confidence: 0.0 to 1.0\n"
        "- reason: one sentence explaining your confidence\n\n"
        "Respond ONLY in JSON. No preamble."
    )


def _verify_single_image(image_bytes: bytes, concept: str, expected_elements: Optional[List[str]] = None) -> ExaminerResult:
    expected = [x for x in (expected_elements or [concept]) if str(x).strip()]
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    model_name = _select_vision_model()
    raw = _vision_chat_json(_handwriting_prompt(expected), image_b64, model_name)
    raw_json = (raw.get("response") or (raw.get("message", {}) or {}).get("content", "") or "").strip()
    data = _parse_json_payload(raw_json)

    if not data:
        return ExaminerResult(
            x=0,
            y=0,
            width=0,
            height=0,
            explanation="Could not parse model response from Lens.",
            handwritten=False,
            has_issue=False,
            confidence=0.0,
            audio_bytes=None,
        )

    confidence = float(data.get("confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    handwritten = _to_bool(data.get("is_handwritten", data.get("handwritten", False)))
    # Heuristic override for low-confidence handwriting outputs.
    if handwritten and confidence < 0.5:
        handwritten = False

    elements_found = data.get("elements_found", [])
    if isinstance(elements_found, list):
        found_text = ", ".join(str(x) for x in elements_found if str(x).strip())
    else:
        found_text = ""
    reason = str(data.get("reason", "")).strip()
    explanation = reason or "Lens analysis complete."
    if handwritten and not _to_bool(data.get("has_issue", False)) and not reason:
        explanation = "Handwritten notes recognized; no obvious logic failure detected."
    if found_text:
        explanation = f"{explanation} Elements found: {found_text}."

    return ExaminerResult(
        x=int(data.get("x", 0) or 0),
        y=int(data.get("y", 0) or 0),
        width=int(data.get("width", 0) or 0),
        height=int(data.get("height", 0) or 0),
        explanation=explanation,
        handwritten=handwritten,
        has_issue=not handwritten,
        confidence=confidence,
        audio_bytes=None,
    )

def verify_image(image_bytes: bytes, concept: str) -> ExaminerResult:
    """
    Runs gemma-4-E4B vision to parse handwritten exams and verify understanding.
    Returns the coordinates of the misconception and an explanation.
    """
    try:
        # Validate the image can be opened before calling the model.
        Image.open(io.BytesIO(image_bytes))
        return _verify_single_image(image_bytes, concept, expected_elements=[concept])
    except json.JSONDecodeError:
        return ExaminerResult(0, 0, 0, 0, "Failed to parse coordinates from vision model.")
    except Exception as e:
        return ExaminerResult(0, 0, 0, 0, f"Error connecting to vision model: {e}")


def verify_document(file_bytes: bytes, concept: str, mime_type: str) -> ExaminerResult:
    media_type = (mime_type or "").strip().lower()
    if media_type not in ALLOWED_LENS_MIME_TYPES:
        raise ValueError("Lens supports images (JPG, PNG, WEBP) and PDF files.")

    if media_type == "application/pdf":
        page_images, note = _render_pdf_pages(file_bytes)
        if not page_images:
            return ExaminerResult(0, 0, 0, 0, "PDF has no renderable pages.", handwritten=False, has_issue=True, confidence=0.0)

        page_results = [verify_image(page, concept) for page in page_images]
        handwritten_any = any(r.handwritten for r in page_results)
        issue_any = any(r.has_issue for r in page_results)
        confidence_avg = sum(r.confidence for r in page_results) / len(page_results)
        explanation_parts = [f"Page {idx + 1}: {r.explanation}" for idx, r in enumerate(page_results)]
        if note:
            explanation_parts.append(note)
        return ExaminerResult(
            x=0,
            y=0,
            width=0,
            height=0,
            explanation=" ".join(explanation_parts),
            handwritten=handwritten_any,
            has_issue=issue_any,
            confidence=max(0.0, min(1.0, confidence_avg)),
            audio_bytes=None,
        )

    return verify_image(file_bytes, concept)
