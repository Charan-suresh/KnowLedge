import os
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="KnowLedge | Gemma 4 for Good",
    page_icon="🦉",
    layout="wide",
    initial_sidebar_state="expanded",
)


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


CUSTOM_CSS = """
<style>
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
        st.markdown(
            """
            <div class="codebox">
            Student paste → Scout → SQLite ledger → Sage dialogue → Integrity check → Weekly sync → Instructor report
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tabs[2]:
        st.subheader("How to run locally")
        st.markdown(
            """
            ```bash
            python3 -m venv .venv
            source .venv/bin/activate
            pip install -r requirements.txt
            ollama serve
            python -m uvicorn knowledge.main:app --host 127.0.0.1 --port 8000
            ```

            Optional curriculum ingestion:

            ```bash
            python -m knowledge.vectorize path/to/course_material.pdf
            ```
            """
        )

        st.subheader("How to deploy on Hugging Face Spaces")
        st.markdown(
            """
            1. Create a new Space and choose **Streamlit** as the SDK.
            2. Push this repository's `app.py` to the Space.
            3. Add `streamlit` to `requirements.txt`.
            4. Set `KNOWLEDGE_API_URL` as a Space secret if you want the demo to call a live backend.
            5. Share the Space URL as the Kaggle live-demo link.
            """
        )

    with tabs[3]:
        st.subheader("What to emphasize in the write-up")
        st.markdown(
            """
            - It is offline-first and privacy-preserving.
            - It uses Gemma for both concept extraction and Socratic clearing.
            - It checks for gaming behavior instead of blindly accepting answers.
            - It provides a judge-friendly public demo URL with no setup required.
            """
        )
        if use_live_data:
            st.markdown(
                f'<div class="judge-box"><strong>Connected backend:</strong> {backend_url}<br><strong>Sync status:</strong> {sync_status.get("last_sync", {}).get("status", "unknown")}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="judge-box"><strong>Demo mode:</strong> this app still renders without a backend, so judges never hit a blank page.</div>',
                unsafe_allow_html=True,
            )

with right:
    st.subheader("Live Snapshot")
    st.markdown(
        f"""
        <div class="card">
            <div class="small-note"><strong>Mode:</strong> {"Live backend" if use_live_data else "Demo fallback"}</div>
            <div class="small-note"><strong>Active concepts:</strong> {active}</div>
            <div class="small-note"><strong>Cleared concepts:</strong> {cleared}</div>
            <div class="small-note"><strong>Integrity sessions:</strong> {integrity.get("sessions_with_signatures", 0)}/{integrity.get("sessions_total", 0)}</div>
            <div class="small-note"><strong>Space mode:</strong> {space_mode}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.subheader("Concept Heatmap")
    heatmap_df = pd.DataFrame(heatmap)
    if not heatmap_df.empty:
        st.bar_chart(heatmap_df.set_index("concept")["count"])
    else:
        st.info("No concepts yet.")

    st.write("")
    st.subheader("Live Link")
    if backend_url:
        st.code(backend_url, language="text")
    else:
        st.code("Add KNOWLEDGE_API_URL to connect a live backend", language="text")

    st.caption("Use this Space URL as the live demo link in Kaggle.")
