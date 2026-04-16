import streamlit as st
import sqlite3
import ollama
from datetime import datetime
from retrieval import get_relevant_context

DB_NAME = "cdt_core.db"
MODEL_NAME = "gemma-4-E4B"

def upgrade_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Check if cleared_at exists
        cursor.execute("PRAGMA table_info(debt_log)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'cleared_at' not in columns:
            cursor.execute("ALTER TABLE debt_log ADD COLUMN cleared_at TEXT")
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error checking/upgrading db schema: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def get_oldest_borrowed_debt():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, concept_tag, timestamp 
            FROM debt_log 
            WHERE status = 'borrowed'
            ORDER BY timestamp ASC
            LIMIT 1
        ''')
        return cursor.fetchone()
    except sqlite3.Error as e:
        st.error(f"Error fetching debt: {e}")
        return None
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def mark_debt_cleared(debt_id: int):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        cursor.execute('''
            UPDATE debt_log 
            SET status = 'cleared', cleared_at = ? 
            WHERE id = ?
        ''', (now, debt_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error clearing debt: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()


st.set_page_config(page_title="The Debt Collector", layout="wide")
upgrade_db()

st.title("🕵️‍♂️ The Debt Collector")
st.subheader("Socratic Clearing Agent")

# Initialize Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_debt" not in st.session_state:
    debt = get_oldest_borrowed_debt()
    st.session_state.current_debt = debt
    st.session_state.debt_cleared = False
    
    if debt:
        # Initialize context for the debt
        context = get_relevant_context(debt[1])
        st.session_state.course_context = context

if not st.session_state.current_debt:
    st.info("No 'borrowed' concepts found in the debt log! You're all caught up! 🎉")
    st.stop()

debt_id, concept, timestamp = st.session_state.current_debt

st.markdown(f"**Current Target Concept:** `{concept}` (Logged: {timestamp.split('T')[1][:5] if 'T' in timestamp else timestamp})")

if st.session_state.debt_cleared:
    st.success(f"🎉 Fantastic! The logic gap for **{concept}** has been filled and cleared!")
    if st.button("Load Next Concept"):
        del st.session_state.current_debt
        del st.session_state.chat_history
        st.rerun()
    st.stop()

# Define the system prompt with context
context_str = st.session_state.course_context if st.session_state.course_context else "No specific course context found locally."

system_prompt = f"""You are the Debt Collector. Your goal is to clear comprehension debt for heavily borrowed concept: '{concept}'. 
Use the provided context to ask questions that lead the student to the answer. 
If they are wrong, point out why their logic is inconsistent based on the Context. 
Never give the answer directly.
If you determine the student has demonstrated sufficient understanding and has "cleared" the concept, you MUST call the `verify_comprehension` tool.

Context:
{context_str}
"""

for msg in st.session_state.chat_history:
    role = msg["role"]
    if role in ["system", "tool"]: continue # hide internal routing
    with st.chat_message(role):
        st.write(msg["content"])

user_input = st.chat_input(f"Let's talk about {concept}...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Call Ollama
    with st.spinner("Analyzing your response..."):
        # We need to pass system prompt inside the messages array
        messages = [{"role": "system", "content": system_prompt}] + st.session_state.chat_history
        
        tools = [{
            'type': 'function',
            'function': {
                'name': 'verify_comprehension',
                'description': 'Call this tool ONLY when you determine the student has successfully demonstrated understanding of the concept and filled their logic gap.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'reasoning': {
                            'type': 'string',
                            'description': 'Brief explanation of why the student has cleared the concept.'
                        }
                    },
                    'required': ['reasoning']
                }
            }
        }]

        try:
            client = ollama.Client()
            response = client.chat(
                model=MODEL_NAME,
                messages=messages,
                tools=tools
            )
            
            message = response.get('message', {})
            tool_calls = message.get('tool_calls', [])
            
            cleared = False
            if tool_calls:
                for tool in tool_calls:
                    if tool.get('function', {}).get('name') == 'verify_comprehension':
                        cleared = True
                        break

            if cleared:
                mark_debt_cleared(debt_id)
                st.session_state.debt_cleared = True
                st.rerun()
            else:
                ai_response = message.get('content', '')
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                with st.chat_message("assistant"):
                    st.write(ai_response)
                
        except Exception as e:
            st.error(f"Error communicating with local Ollama ({MODEL_NAME}): {e}")
