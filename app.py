import os
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import httpx
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Sample Data (Fallback when backend is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_LEDGER: List[Dict[str, Any]] = [
    {"concept": "Recursion base case", "status": "on_loan", "confidence": 0.92, "source_text": "Borrowed from AI explanation"},
    {"concept": "Binary search invariants", "status": "clear", "confidence": 0.88, "source_text": "Explained in own words"},
    {"concept": "Gradient descent", "status": "persists", "confidence": 0.79, "source_text": "Needs another clearing session"},
    {"concept": "RAG retrieval", "status": "on_loan", "confidence": 0.84, "source_text": "Added during prompt work"},
]

SAMPLE_HEATMAP = [
    {"concept": "Recursion base case", "count": 9},
    {"concept": "Binary search invariants", "count": 4},
    {"concept": "Gradient descent", "count": 7},
]

SAMPLE_METRICS = {
    "active": 2,
    "cleared": 1,
    "persists": 1,
    "debt_score": 67,
    "pending_sync": 0,
    "spoof_attempts": 3,
}


# ─────────────────────────────────────────────────────────────────────────────
# Backend Integration
# ─────────────────────────────────────────────────────────────────────────────

def backend_snapshot(base_url: str) -> Optional[Dict[str, Any]]:
    """Fetch live data from the knowledge backend API."""
    base = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=6.0) as client:
            state = client.get(f"{base}/api/state", timeout=6.0).json()
            sync = client.get(f"{base}/api/sync/status", timeout=6.0).json()
            integrity = client.get(f"{base}/api/integrity/report", timeout=6.0).json()
            return {"state": state, "sync": sync, "integrity": integrity}
    except Exception:
        return None


def scout_demo(pasted_text: str) -> Tuple[str, str]:
    """Simulate Scout tagging concepts from pasted text."""
    if not pasted_text.strip():
        return "", "Paste some text to see Scout extract concepts."
    
    extracted_concepts = []
    keywords = ["recursion", "binary search", "gradient descent", "rag", "algorithm", "model", "training", "inference"]
    for keyword in keywords:
        if keyword.lower() in pasted_text.lower():
            extracted_concepts.append(keyword.capitalize())
    
    if not extracted_concepts:
        extracted_concepts = ["Learning (inferred from context)"]
    
    result = f"**Scout detected {len(extracted_concepts)} concept(s):**\n\n"
    for concept in extracted_concepts:
        result += f"- {concept} (confidence: ~85%)\n"
    
    status = f"✅ Tagged {len(extracted_concepts)} concept(s) → added to your ledger"
    return result, status


def sage_demo(concept: str, user_response: str) -> str:
    """Simulate Sage Socratic dialogue."""
    if not concept.strip():
        return "Enter a concept to start a clearing session."
    
    if not user_response.strip():
        return f"🦉 **Sage**: Let's talk about {concept}. Can you explain it in your own words?"
    
    quality_score = len(user_response.split()) / 10
    if quality_score < 2:
        return f"🦉 **Sage**: That's a start. But can you go deeper? What makes {concept} special or different?"
    elif quality_score < 4:
        return f"🦉 **Sage**: Good effort! Now, why would someone use {concept} in practice? When does it matter?"
    else:
        return f"✅ **Sage**: Excellent! You've clearly understood {concept}. This concept is now **CLEARED** in your ledger."


def get_ledger_display() -> pd.DataFrame:
    """Return the current ledger as a DataFrame for display."""
    backend_url = os.environ.get("KNOWLEDGE_API_URL", "").strip()
    snapshot = backend_snapshot(backend_url) if backend_url else None
    ledger = snapshot["state"]["debts"] if snapshot else SAMPLE_LEDGER
    
    df = pd.DataFrame(ledger)
    if not df.empty:
        df = df[["concept", "status", "confidence"]]
    return df


def get_metrics() -> Tuple[int, int, int, int]:
    """Return key metrics: active, cleared, persists, debt_score."""
    backend_url = os.environ.get("KNOWLEDGE_API_URL", "").strip()
    snapshot = backend_snapshot(backend_url) if backend_url else None
    ledger = snapshot["state"]["debts"] if snapshot else SAMPLE_LEDGER
    
    active = sum(1 for row in ledger if row.get("status") in {"on_loan", "persists"})
    cleared = sum(1 for row in ledger if row.get("status") in {"clear", "owned"})
    persists = sum(1 for row in ledger if row.get("status") == "persists")
    debt_score = round(((active + persists) / max(len(ledger), 1)) * 100) if ledger else 0
    
    return active, cleared, persists, debt_score


# ─────────────────────────────────────────────────────────────────────────────
# Gradio Interface
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="KnowLedge | Gemma 4 for Good",
    theme=gr.themes.Soft(
        primary_hue="slate",
        secondary_hue="amber",
    ),
) as demo:
    
    gr.Markdown(
        """
        # 🦉 KnowLedge
        
        **A local-first learning verification system for the Gemma 4 for Good hackathon.**
        
        KnowLedge turns pasted AI-assisted work into a guided mastery loop:
        - **Scout** extracts concepts from text
        - **Sage** clears them through Socratic dialogue
        - **Lens** verifies understanding with integrity checks
        - **Reports** share only anonymous aggregates with instructors
        """
    )
    
    with gr.Row():
        active, cleared, persists, debt_score = get_metrics()
        
        with gr.Column(scale=1):
            gr.Markdown(f"### 📊 Active\n\n**{active}** concepts on loan or persisting")
        with gr.Column(scale=1):
            gr.Markdown(f"### ✅ Cleared\n\n**{cleared}** owned concepts")
        with gr.Column(scale=1):
            gr.Markdown(f"### 🎯 Debt Score\n\n**{debt_score}%** (lower is better)")
        with gr.Column(scale=1):
            gr.Markdown(f"### 🛡️ Integrity\n\n**{SAMPLE_METRICS['spoof_attempts']}** spoof signals detected")
    
    with gr.Tabs():
        
        # ─────────────────────────────────────────────────────────────────────
        # Tab 1: Scout Demo
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🔍 Scout — Extract Concepts"):
            gr.Markdown(
                """
                **Scout** automatically finds concepts inside pasted text. Try pasting an explanation or code snippet below.
                """
            )
            
            with gr.Row():
                with gr.Column(scale=2):
                    pasted_text = gr.Textbox(
                        label="Paste AI-assisted work or notes here",
                        placeholder="e.g., 'Recursion works by dividing a problem into smaller subproblems until reaching a base case...'",
                        lines=6,
                    )
                with gr.Column(scale=1):
                    scout_btn = gr.Button("🚀 Run Scout", size="lg")
            
            scout_output = gr.Markdown("Paste something to get started.")
            scout_status = gr.Textbox(label="Status", interactive=False, value="Ready.")
            
            scout_btn.click(
                scout_demo,
                inputs=[pasted_text],
                outputs=[scout_output, scout_status],
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # Tab 2: Sage Demo
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🦉 Sage — Socratic Clearing"):
            gr.Markdown(
                """
                **Sage** guides you through a Socratic clearing session. Pick a concept and explain it in your own words.
                """
            )
            
            concept_input = gr.Textbox(
                label="Concept to clear",
                placeholder="e.g., 'Binary Search'",
                value="Recursion",
            )
            
            response_input = gr.Textbox(
                label="Your explanation",
                placeholder="Explain the concept in your own words. Be as detailed as you can.",
                lines=4,
            )
            
            sage_btn = gr.Button("💭 Get Sage Response", size="lg")
            sage_output = gr.Markdown()
            
            sage_btn.click(
                sage_demo,
                inputs=[concept_input, response_input],
                outputs=[sage_output],
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # Tab 3: Live Ledger
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("📖 Live Ledger"):
            gr.Markdown(
                """
                This is your concept ledger. Every concept you study is tracked here with its status:
                - **on_loan**: You pasted it but haven't cleared it yet.
                - **clear**: You explained it to Sage and passed.
                - **persists**: Lens found gaps, needs another session.
                """
            )
            
            ledger_df = get_ledger_display()
            ledger_table = gr.Dataframe(
                value=ledger_df,
                interactive=False,
                wrap=True,
            )
            
            refresh_btn = gr.Button("🔄 Refresh Ledger")
            refresh_btn.click(
                lambda: get_ledger_display(),
                outputs=[ledger_table],
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # Tab 4: Architecture & Setup
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🏗️ Architecture"):
            gr.Markdown(
                """
                ## System Design
                
                **Backend Stack:**
                - FastAPI for the web server
                - SQLite for concept ledger persistence
                - ChromaDB for curriculum context (RAG)
                - Ollama for local Gemma inference
                - Privacy-preserving sync with concept-level aggregates only
                
                **Key Features:**
                - Offline-first (no cloud dependency)
                - Session fingerprinting to detect gaming behavior
                - Anti-spoof scoring on Lens uploads
                - No student identifiers in instructor reports
                
                ## Quick Local Setup
                
                ```bash
                python3 -m venv .venv
                source .venv/bin/activate
                pip install -r requirements.txt
                
                # Terminal 1: Start Ollama
                ollama serve
                
                # Terminal 2: Start the backend
                python -m uvicorn knowledge.main:app --host 127.0.0.1 --port 8000
                
                # Optional: Load curriculum material
                python -m knowledge.vectorize path/to/course.pdf
                ```
                
                ## Deploy on Hugging Face Spaces
                
                1. Create a new Space with **Gradio** SDK
                2. Push this repo to the Space
                3. Set `KNOWLEDGE_API_URL` environment variable (optional, for live backend)
                4. Share the Space URL as your Kaggle demo link
                """
            )
        
        # ─────────────────────────────────────────────────────────────────────
        # Tab 5: For Judges
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🎯 For Kaggle Judges"):
            gr.Markdown(
                """
                ## What Makes KnowLedge Different
                
                Most AI tutoring tools are **answer machines**. KnowLedge is a **verification system**.
                
                ### The Problem
                - Students copy AI-generated code without understanding
                - Traditional quizzes can be gamed with a second AI
                - Instructors have no way to detect this pattern
                
                ### The KnowLedge Solution
                - **Scout** logs every concept you borrow from AI
                - **Sage** forces you to explain it yourself before you own it
                - **Lens** checks handwritten work for logic gaps
                - **Integrity** fingerprints your session to catch repeat gaming
                - **Sync** gives instructors only concept-level aggregates (privacy-first)
                
                ### Why This Matters
                - Fixes a **real problem** in modern education
                - Uses **Gemma 4** for both extraction and dialogue
                - Runs **fully offline** for maximum privacy
                - Provides a **zero-setup** public demo (this Space)
                
                ### Key Metrics
                - **Debt Score**: How much of your work is still "borrowed"
                - **Spoof Attempts**: Session fingerprinting detects copy-paste patterns
                - **Integrity Signals**: Anti-gaming scoring from Lens
                
                This is what judges should look for. Not an answering machine. A **learning enforcer**.
                """
            )


# Launch the Gradio interface
if __name__ == "__main__":
    demo.launch()
:root {
    --bg: #f5f0e8;
    --panel: #ffffff;
    --ink: #1c1a14;
    --muted: #7a7565;
    --teal: #0e7a6e;
    --amber: #d4820a;
    --coral: #c94a3a;
    --rule: rgba(28, 26, 20, 0.12);
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.hero {
    background: linear-gradient(135deg, rgba(14,122,110,0.10), rgba(212,130,10,0.10));
    border: 1px solid var(--rule);
    border-radius: 24px;
    padding: 2rem;
    margin-bottom: 1.25rem;
}

.hero h1 {
    color: var(--ink);
    font-size: 3rem;
    line-height: 1;
    margin-bottom: 0.5rem;
}

.hero p {
    color: var(--muted);
    font-size: 1.02rem;
    line-height: 1.6;
    max-width: 58rem;
}

.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin-top: 1rem;
}

.badge {
    display: inline-block;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--rule);
    background: rgba(255,255,255,0.72);
    color: var(--ink);
    font-size: 0.85rem;
}

.card {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: 18px;
    padding: 1rem;
    box-shadow: 0 10px 30px rgba(28, 26, 20, 0.06);
}

.metric {
    background: white;
    border: 1px solid var(--rule);
    border-radius: 18px;
    padding: 1rem;
    min-height: 130px;
}

.metric-label {
    color: var(--muted);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.35rem;
}

.metric-value {
    color: var(--ink);
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.35rem;
}

.metric-sub {
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.4;
}

.judge-box {
    border-left: 4px solid var(--teal);
    padding: 0.85rem 1rem;
    background: rgba(14, 122, 110, 0.06);
    border-radius: 12px;
}

.small-note {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.55;
}

.codebox {
    background: #1c1a14;
    color: #f5f0e8;
    border-radius: 14px;
    padding: 1rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.9rem;
    overflow-x: auto;
}
</style>
"""


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def backend_snapshot(base_url: str) -> Optional[Dict[str, Any]]:
    base = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=6.0) as client:
            state = client.get(f"{base}/api/state").json()
            sync = client.get(f"{base}/api/sync/status").json()
            integrity = client.get(f"{base}/api/integrity/report").json()
            return {"state": state, "sync": sync, "integrity": integrity}
    except Exception:
        return None


backend_url = os.environ.get("KNOWLEDGE_API_URL", "").strip()
space_mode = os.environ.get("SPACE_MODE", "demo").strip().lower()
snapshot = backend_snapshot(backend_url) if backend_url else None
use_live_data = snapshot is not None
ledger = snapshot["state"]["debts"] if use_live_data else SAMPLE_LEDGER
heatmap = snapshot["state"]["heatmap"] if use_live_data else SAMPLE_HEATMAP
sync_status = snapshot["sync"] if use_live_data else {"pending_count": SAMPLE_METRICS["pending_sync"], "last_sync": {"status": "sent"}}
integrity = snapshot["integrity"] if use_live_data else {"spoof_attempts": SAMPLE_METRICS["spoof_attempts"], "sessions_with_signatures": 8, "sessions_total": 10}

active = sum(1 for row in ledger if row.get("status") in {"on_loan", "persists"})
cleared = sum(1 for row in ledger if row.get("status") in {"clear", "owned"})
persists = sum(1 for row in ledger if row.get("status") == "persists")
debt_score = round(((active + persists) / max(len(ledger), 1)) * 100) if ledger else 0

st.markdown(
    """
    <div class="hero">
        <h1>KnowLedge</h1>
        <p>
            A local-first learning verification system for the Gemma 4 for Good hackathon.
            KnowLedge turns pasted AI-assisted work into a guided mastery loop: Scout extracts concepts,
            Sage clears them through Socratic dialogue, and Lens verifies understanding with integrity checks.
        </p>
        <div class="badge-row">
            <span class="badge">FastAPI backend</span>
            <span class="badge">SQLite + ChromaDB</span>
            <span class="badge">Ollama + Gemma</span>
            <span class="badge">Privacy-preserving sync</span>
            <span class="badge">Expo companion app</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if use_live_data:
    st.success("Live backend connected. This Space can be used as a zero-setup demo front door.")
else:
    if backend_url:
        st.warning(f"Backend URL set, but the app could not reach {backend_url}. Showing demo data instead.")
    else:
        st.info("Demo mode is active. Add KNOWLEDGE_API_URL in Hugging Face Spaces to connect to your hosted backend.")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f'<div class="metric"><div class="metric-label">Active Concepts</div><div class="metric-value">{active}</div><div class="metric-sub">currently on loan or persisting</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric"><div class="metric-label">Cleared</div><div class="metric-value">{cleared}</div><div class="metric-sub">concepts owned by the student</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric"><div class="metric-label">Debt Score</div><div class="metric-value">{debt_score}%</div><div class="metric-sub">lower is better</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric"><div class="metric-label">Pending Sync</div><div class="metric-value">{sync_status.get("pending_count", 0)}</div><div class="metric-sub">weekly aggregate queue</div></div>', unsafe_allow_html=True)
with col5:
    st.markdown(f'<div class="metric"><div class="metric-label">Spoof Signals</div><div class="metric-value">{integrity.get("spoof_attempts", 0)}</div><div class="metric-sub">anti-gaming checks</div></div>', unsafe_allow_html=True)

left, right = st.columns([1.15, 0.85], gap="large")

with left:
    tabs = st.tabs(["Live Demo", "Architecture", "How to Run", "Judge Notes"])

    with tabs[0]:
        st.subheader("What judges can test")
        st.write("KnowLedge is designed to show a complete learning-verification loop, not just a chatbot.")
        st.markdown(
            """
            1. Paste a concept or AI-assisted explanation.
            2. Scout extracts the concepts and logs them to the ledger.
            3. Sage asks clarifying questions until the concept is cleared.
            4. Lens and integrity checks keep the workflow honest.
            5. Reports share only anonymous aggregates.
            """
        )
        demo_rows = pd.DataFrame(ledger)[["concept", "status", "confidence"]] if ledger else pd.DataFrame(columns=["concept", "status", "confidence"])
        st.dataframe(demo_rows, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Product Architecture")
        st.markdown(
            """
            - **Scout** finds concepts inside pasted text.
            - **Sage** runs the Socratic clearing loop.
            - **Lens** checks handwritten or visual reasoning.
            - **Sync** exports only concept-level aggregates.
            - **Integrity** uses fingerprints and anti-spoof scoring.
                """
            )


# Launch the Gradio interface
if __name__ == "__main__":
    demo.launch()
