import streamlit as st
import sqlite3
import ollama
from datetime import datetime
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = "cdt_core.db"
MODEL_NAME = "gemma-4-E2B"

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS debt_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                concept_tag TEXT,
                source_type TEXT,
                confidence_score REAL,
                status TEXT DEFAULT 'borrowed'
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def log_debt_to_db(concept_tag: str, confidence_score: float, source_type: str = "AI-pasted"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        cursor.execute('''
            INSERT INTO debt_log (timestamp, concept_tag, source_type, confidence_score, status)
            VALUES (?, ?, ?, ?, 'borrowed')
        ''', (now, concept_tag, source_type, confidence_score))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error inserting into db: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def fetch_borrowed_debts():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT concept_tag, confidence_score, timestamp 
            FROM debt_log 
            WHERE status = 'borrowed'
            ORDER BY timestamp DESC
        ''')
        rows = cursor.fetchall()
        return rows
    except sqlite3.Error as e:
        logger.error(f"Error fetching from db: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def process_student_input(text: str):
    """
    Analyzes student input using gemma-4-E2B via Ollama.
    Extracts concepts using native function calling and logs them to the db.
    """
    tools = [{
        'type': 'function',
        'function': {
            'name': 'log_comprehension_concepts',
            'description': 'Identifies and extracts academic concepts mentioned in the text that the student might be borrowing or learning. Return a list of concepts with a confidence score.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'concepts': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'concept_tag': {
                                    'type': 'string',
                                    'description': 'The name of the learning concept, e.g., "Recursion Base Case" or "For Loop"'
                                },
                                'confidence_score': {
                                    'type': 'number',
                                    'description': 'Confidence score between 0.0 and 1.0 indicating how clearly the concept is present in the text.'
                                }
                            },
                            'required': ['concept_tag', 'confidence_score']
                        }
                    }
                },
                'required': ['concepts']
            }
        }
    }]
    
    SYSTEM_PROMPT = (
        "You are 'The Sentinel', a background observer. Your task is to analyze the student's text "
        "and calmly identify any academic or technical concepts being used or discussed. "
        "Do not be punitive; treat these as 'borrowed' concepts for knowledge tracking. "
        "Use the native function calling tool to log these concepts."
    )

    try:
        # Check if ollama is available
        client = ollama.Client()
        # Ensure we can list models (basic connection test)
        client.list()
        
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': f"Analyze this student input:\n\n{text}"}
            ],
            tools=tools
        )
        
        # Check if the model triggered our tool
        # The ollama python library returns tool_calls in message.tool_calls
        message = response.get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        concepts_logged = 0
        
        if tool_calls:
            for tool in tool_calls:
                function_call = tool.get('function', {})
                if function_call.get('name') == 'log_comprehension_concepts':
                    arguments = function_call.get('arguments', {})
                    concepts = arguments.get('concepts', [])
                    for concept in concepts:
                        tag = concept.get('concept_tag')
                        score = concept.get('confidence_score')
                        if tag and score is not None:
                            log_debt_to_db(tag, float(score))
                            concepts_logged += 1
            return concepts_logged, None
        else:
            # Model didn't use the tool, maybe it replied directly. 
            # In a strict pipeline, this might be a fail, but we'll return 0 
            return 0, "No tools triggered by the model."

    except ConnectionError as e:
        logger.error(f"Connection Error: {e}")
        return 0, "Connection to Ollama failed. Is Ollama server running locally?"
    except Exception as e:
        logger.error(f"Unexpected error interfacing with Ollama: {e}")
        return 0, f"Error: {str(e)}"

# UI Code Below
st.set_page_config(page_title="The Sentinel (CDT Week 2)", layout="wide")

# Initialize DB once on startup
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

st.title("🛡️ The Sentinel")
st.subheader("Background Comprehension Debt Tracker")
st.markdown("Paste or type your notes, code, or ideas below. The Sentinel uses `gemma-4-E2B` locally to extract concepts silently.")

# Main Input Area
student_input = st.text_area("Student Input Area", height=300, placeholder="Type or paste your work here...")

if st.button("Process Input (Simulate Sentinel Poll)"):
    if not student_input.strip():
        st.warning("Please enter some text to process.")
    else:
        with st.spinner(f"Analyzing via {MODEL_NAME}..."):
            count, err = process_student_input(student_input)
            if err:
                st.error(f"Failed to process: {err}")
            elif count > 0:
                st.success(f"Successfully extracted and logged {count} 'borrowed' concepts!")
            else:
                st.info("No concepts extracted. The model didn't identify any clear academic concepts.")

# Sidebar - Debt Dashboard
st.sidebar.title("📈 Current Debt Dashboard")
st.sidebar.markdown("Tracking *Comprehension Debt*")

debts = fetch_borrowed_debts()
if debts:
    for d in debts:
        tag, score, timestamp = d
        # Just getting the time portion for cleaner display
        short_time = timestamp.split('T')[1][:5] if 'T' in timestamp else timestamp
        st.sidebar.card = st.sidebar.container()
        with st.sidebar.card:
            st.markdown(f"**{tag}**")
            st.caption(f"Score: {score:.2f} | Time: {short_time}")
            st.divider()
else:
    st.sidebar.info("No borrowed concepts yet.")
