# 🧠 Comprehension Debt Tracker (CDT)

> **CDT** is an entirely offline, AI-driven educational ecosystem that prevents student "AI reliance." It passively tracks copied material as "Comprehension Debt," strictly clears that debt via an interactive Socratic chatbot, and verifies persistent understanding using multi-modal Computer Vision and Native Audio.

---

## 🚀 Features

### 🛡️ Phase 1: **The Sentinel** (Passive Tracking)
A background observer that intercepts student code/notes. Instead of passively passing them, it analyzes the components and secretly logs missing conceptual knowledge into a local database as "Comprehension Debt".
- Tracks the specific concepts a student is interacting with but hasn't fully mastered.
- Driven by `gemma-4-E2B` with **Native Function Calling**.

### 🕵️‍♂️ Phase 2: **The Debt Collector** (Socratic Clearance)
At the end of the week, the student faces The Debt Collector. It queries the local **ChromaDB** RAG index (populated with course materials) to engage in a rigorous Socratic dialogue.
- **Never gives the direct answer.** It guides the student to fill their own logic gaps.
- Marks the debt as 'Cleared' once the LLM evaluator confirms complete mastery. 
- Driven by `gemma-4-E4B`.

### 👁️ Phase 3: **The Examiner** (Multimodal Verification)
Testing genuine mastery via an offline "Sanctuary" environment.
- **Vision Integration**: Point your webcam at a handwritten equation or flowchart. The model identifies the precise logical flaw and physically draws a bounding box on the image overlay.
- **Native Audio Integration**: Listens to the student's explanations natively.
- **Persistent Reliance Tracker**: Automatically relapses 'cleared' concepts if the student demonstrates dependency within unassisted mode.

---

## 🛠️ Technology Stack
* **LLM Engine**: [Ollama](https://ollama.com/) (100% Local offline inference)
* **Models**: `gemma-4-E2B`, `gemma-4-E4B` (Text, Vision, Native Audio)
* **Frontend**: Streamlit
* **Vector Database**: ChromaDB (Persistent local embeddings)
* **Relational State**: SQLite (`cdt_core.db`)
* **Computer Vision**: Pillow

---

## 💻 Quick Start

### 1. Prerequisites
Ensure you have Python 3.9+ and Ollama installed. Pull the required models:
```bash
ollama run gemma-4-E2B
ollama run gemma-4-E4B
```

Clone the repository and install dependencies:
```bash
git clone https://github.com/Charan-suresh/CDT.git
cd CDT
pip3 install -r requirements.txt
```
*(Note: If creating a `requirements.txt`, include `streamlit`, `ollama`, `chromadb`, `pdfplumber`, `pillow`.)*

### 2. Ingest the Syllabus 📚
Vectorize your course materials (e.g., `Dsa.pdf`) into ChromaDB:
```bash
python3 vectorize.py ./Dsa.pdf
```

### 3. Run the Tools ⚙️
Be sure to spin up the background Ollama daemon (`ollama serve`) first.
- **Sentinel**: `python3 -m streamlit run sentinel.py`
- **Debt Collector**: `python3 -m streamlit run debt_collector.py`
- **Examiner**: `python3 -m streamlit run examiner.py`

---
*Built as a proof-of-concept for the intersection of highly localized Agentic AI and deeply structured Educational Psychology frameworks.*
