import json
import base64
from dataclasses import dataclass
from typing import Optional
from PIL import Image
import io
from . import config
from .agents.inference_router import chat

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

def verify_image(image_bytes: bytes, concept: str) -> ExaminerResult:
    """
    Runs gemma-4-E4B vision to parse handwritten exams and verify understanding.
    Returns the coordinates of the misconception and an explanation.
    """
    try:
        # Load image to get dimensions
        img = Image.open(io.BytesIO(image_bytes))
        b64_image = base64.b64encode(image_bytes).decode()

        vision_prompt = f"""
        Analyze this student-submitted handwritten work for the concept: [{concept}].
        First determine whether the image is handwritten notes or a handwritten solution.
        If it is handwritten, say so explicitly even when the work looks correct.
        If you identify a logic mistake, point to the most relevant region.
        Return a strict JSON object with this exact format, nothing else:
        {{
            "x": 100,
            "y": 150,
            "width": 200,
            "height": 50,
            "explanation": "Brief explanation of the handwritten work or misconception.",
            "handwritten": true,
            "has_issue": false,
            "confidence": 0.92
        }}
        Use approximate pixel coordinates assuming the image is {img.width}x{img.height}.
        """
        
        response = chat(
            model=config.LENS_MODEL,
            messages=[{
                'role': 'user', 
                'content': vision_prompt,
                'images': [b64_image]
            }],
            format='json'
        )
        
        raw_json = response.get('message', {}).get('content', '')
        data = json.loads(raw_json)

        handwritten = bool(data.get("handwritten", False))
        has_issue = bool(data.get("has_issue", False))
        confidence = float(data.get("confidence", 0.0) or 0.0)
        
        # Audio feedback
        audio_data = response.get('message', {}).get('audio')
        audio_bytes = base64.b64decode(audio_data) if audio_data else None

        explanation = data.get('explanation', 'Unknown error.')
        if handwritten and not has_issue and explanation == 'Unknown error.':
            explanation = 'Handwritten notes recognized; no obvious logic failure detected.'

        return ExaminerResult(
            x=data.get('x', 0),
            y=data.get('y', 0),
            width=data.get('width', 0),
            height=data.get('height', 0),
            explanation=explanation,
            handwritten=handwritten,
            has_issue=has_issue,
            confidence=max(0.0, min(1.0, confidence)),
            audio_bytes=audio_bytes
        )
        
    except json.JSONDecodeError:
        return ExaminerResult(0, 0, 0, 0, "Failed to parse coordinates from vision model.")
    except Exception as e:
        return ExaminerResult(0, 0, 0, 0, f"Error connecting to vision model: {e}")
