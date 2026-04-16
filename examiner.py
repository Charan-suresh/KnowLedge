import streamlit as st
import sqlite3
import ollama
import json
import io
import base64
from PIL import Image, ImageDraw
from datetime import datetime

DB_NAME = "cdt_core.db"
MODEL_NAME = "gemma-4-E4B"

# --- Database Helpers ---
def fetch_cleared_concepts():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, concept_tag FROM debt_log WHERE status = 'cleared'")
        return cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"DB Error: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def mark_persistent_reliance(debt_id: int):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE debt_log SET status = 'Persistent Reliance' WHERE id = ?", (debt_id,))
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        if 'conn' in locals():
            conn.close()

# --- Page Config ---
st.set_page_config(page_title="The Examiner", layout="wide")
st.title("👁️ The Examiner")
st.markdown("Multimodal Verification & Sanctuary Environment (- Week 4)")

tab1, tab2 = st.tabs(["Vision Analysis Pipeline", "Exam Sanctuary"])

# --- TAB 1: Vision Analysis ---
with tab1:
    st.header("📸 Handwritten Concept Diagnostics")
    
    concept_target = st.text_input("What concept are we analyzing?", placeholder="e.g., Recursion Base Case")
    
    col1, col2 = st.columns(2)
    with col1:
        img_buffer = st.camera_input("Capture Handwritten Work")
        audio_buffer = None
        # `st.audio_input` requires newer Streamlit versions. 
        if hasattr(st, 'audio_input'):
            audio_buffer = st.audio_input("Record Explanation (Optional)")
        else:
            st.info("Audio microphone input requires Streamlit >= 1.38.")
            
    with col2:
        st.write("**Analysis Overlay**")
        if img_buffer and concept_target:
            if st.button("Run Examiner Analysis"):
                with st.spinner("Analyzing visually via Ollama..."):
                    try:
                        # Prepare image
                        img = Image.open(img_buffer)
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format='PNG')
                        b64_image = base64.b64encode(img_bytes.getvalue()).decode()

                        # Construct prompt strictly requesting coordinates and explanation
                        vision_prompt = f"""
                        Analyze this handwritten work for the concept: [{concept_target}].
                        Identify the exact step where the logic fails.
                        Return a strict JSON object with this exact format, nothing else:
                        {{
                            "x": 100,
                            "y": 150,
                            "width": 200,
                            "height": 50,
                            "explanation": "Brief explanation of the misconception here."
                        }}
                        Use approximate pixel coordinates assuming the image is {img.width}x{img.height}.
                        """
                        
                        client = ollama.Client()
                        # Some versions of Ollama handle multimodal this way:
                        response = client.chat(
                            model=MODEL_NAME,
                            messages=[{
                                'role': 'user', 
                                'content': vision_prompt,
                                'images': [b64_image]
                            }],
                            format='json'
                        )
                        
                        raw_json = response.get('message', {}).get('content', '')
                        data = json.loads(raw_json)
                        
                        # Draw bounding box
                        draw = ImageDraw.Draw(img)
                        x, y, w, h = data.get('x', 0), data.get('y', 0), data.get('width', 0), data.get('height', 0)
                        
                        # Only draw if coords are plausible
                        if w > 0 and h > 0:
                            draw.rectangle([(x, y), (x + w, y + h)], outline="red", width=5)
                            
                        st.image(img, caption="Examiner Annotations", use_container_width=True)
                        st.error(f"**Misconception Detected**: {data.get('explanation', 'Unknown error.')}")
                        
                        # Extract Native Audio Feedback if supported by Ollama format
                        audio_data = response.get('message', {}).get('audio')
                        if audio_data:
                            try:
                                audio_bytes = base64.b64decode(audio_data)
                                st.audio(audio_bytes, format='audio/wav')
                                st.success("Played native audio feedback.")
                            except:
                                st.info("Audio stream returned but could not be parsed natively.")
                        else:
                            st.info("No native audio stream returned by the model in this environment.")
                            
                    except json.JSONDecodeError:
                        st.error("Failed to parse coordinates from the vision model. Returning plain text response.")
                        st.write(raw_json)
                    except Exception as e:
                        st.error(f"Error connecting to vision model: {e}")


# --- TAB 2: Exam Sanctuary ---
with tab2:
    st.header("🏛️ Sanctuary Environment")
    st.markdown("Prove you actually understand previously 'Cleared' concepts without AI assistance.")
    
    cleared = fetch_cleared_concepts()
    if not cleared:
        st.info("You don't have any cleared concepts to be examined on right now.")
    else:
        # Simple selection mechanism
        exam_target = st.selectbox("Select a concept to verify:", [c[1] for c in cleared])
        debt_id = next(c[0] for c in cleared if c[1] == exam_target)
        
        st.write(f"Explain how **{exam_target}** works, from start to finish. (No pasting allowed!)")
        
        # We can't strictly stop OS paste without JS hacks, but we can block standard shortcuts visually
        student_exam_input = st.text_area("Your Independent Answer:", height=200, key="sanctuary_input")
        
        if st.button("Submit to the Examiner"):
            if len(student_exam_input) < 10:
                st.warning("Please provide a more comprehensive answer.")
            else:
                with st.spinner("Evaluating Sanctuary response..."):
                    eval_prompt = f"""
                    You are a strict examiner. The student is trying to prove they understand: {exam_target}.
                    Their response: {student_exam_input}
                    
                    Do they completely understand the concept? Return a JSON object with:
                    {{
                        "pass": true/false,
                        "feedback": "brief critique"
                    }}
                    """
                    try:
                        client = ollama.Client()
                        eval_response = client.chat(
                            model=MODEL_NAME,
                            messages=[{'role': 'user', 'content': eval_prompt}],
                            format='json'
                        )
                        eval_data = json.loads(eval_response.get('message', {}).get('content', '{}'))
                        
                        if eval_data.get('pass'):
                            st.success("✅ **Passed!** True comprehension established.")
                            st.write(eval_data.get('feedback'))
                        else:
                            st.error("❌ **Failed!** Your answer lacks strict comprehension.")
                            st.write(f"Feedback: {eval_data.get('feedback')}")
                            st.warning("🚨 Marking this concept as **Persistent Reliance** in the Debt Log.")
                            mark_persistent_reliance(debt_id)
                            
                    except Exception as e:
                        st.error(f"Error during evaluation: {e}")
