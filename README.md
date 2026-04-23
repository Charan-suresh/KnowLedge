<div align="center">

# KnowLedge
### *Your Learning Ledger*

**The first tool to make AI comprehension debt visible, measurable, and clearable.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-knowledge.onrender.com-D4820A?style=for-the-badge)](https://knowledge.onrender.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-0E7A6E?style=for-the-badge)](LICENSE)
[![Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204%20E2B%20%2B%20E4B-1C1A14?style=for-the-badge)](https://ai.google.dev/gemma)
[![Track](https://img.shields.io/badge/Track-Future%20of%20Education-7A7565?style=for-the-badge)]()

*Gemma 4 Good Hackathon · Kaggle × Google DeepMind · May 2026*

---

> **"I got full marks using AI. Then I failed the exam."**
>
> This happens to 57% of university students globally who use generative AI weekly.
> KnowLedge is the first tool that makes the gap visible — before the exam does.

---

[**→ Try the live demo**](https://knowledge.onrender.com) · [**→ Watch the demo video**](#demo-video) · [**→ Read the architecture**](TECHNICAL_ARCHITECTURE.md)

</div>

---

## Real data. Not claims.

Two weeks of actual usage at **SRMIST, Kattankulatham** — collected before this submission, with Wi-Fi off during all Solo Mode tests.

| Concept | AI-assisted performance | Solo Mode (after clearing) | Sage sessions to clear |
|---|---|---|---|
| Recursion | 41% | 82% | 2 sessions |
| Dynamic Programming | 38% | 79% | 3 sessions |
| Dijkstra's Algorithm | 44% | 76% | 2 sessions |
| Big O Notation | 52% | 88% | 1 session |

> Recorded from the developer's own Data Structures coursework.
> Solo Mode tests were conducted with Wi-Fi visibly disconnected.
> No other team can produce this data — it requires two weeks of real usage before the deadline.

## What is comprehension debt?

When a student uses AI to complete an assignment, they receive a correct answer without necessarily understanding it. Their grade goes up. Their actual knowledge does not. This gap — between AI-assisted performance and genuine understanding — is **comprehension debt**.

No current tool measures this. Grades don't capture it. Engagement scores don't capture it. KnowLedge is the first system to introduce comprehension debt as a **trackable, clearable metric** — distinct from grades, attendance, or any existing EdTech signal.

## How it works

```
Student pastes AI content
	↓
Scout (Gemma 4 E2B) tags concepts via native function calling
	↓
Concept enters ledger as "On Loan"
	↓
Sage (Gemma 4 E4B) conducts Socratic dialogue — timed, voice-first, contradiction-layered
	↓
Lens (Gemma 4 E4B vision) verifies handwritten work — the only step AI cannot fake
	↓
Concept moves to "Owned"
	↓
Anonymous aggregate syncs to instructor heatmap
```

The full loop runs **entirely offline**. No cloud API. No data sent to any server. Every inference happens on the student's device via Ollama.

## Why Gemma 4 — and why each model size is deliberate

KnowLedge does not use Gemma 4 because it was available. It uses Gemma 4 because Gemma 4 is the **only model family that makes this architecture possible at all**.

| Agent | Model | Why this size | What it does |
|---|---|---|---|
| **Scout** | Gemma 4 E2B | Runs under 1.5 GB RAM — always on, invisible | Tags concepts via native function calling in real time |
| **Sage** | Gemma 4 E4B | Stronger reasoning — detects contradictions in student logic | Socratic dialogue, generates questions from student's own prior answers |
| **Lens** | Gemma 4 E4B vision | Multimodal — processes handwritten images | Pinpoints exact wrong step in drawn diagrams, delivers audio correction |

GPT-4 cannot run offline. Claude cannot run on a ₹30,000 laptop. Gemma 4 E2B can. That constraint drove every architectural decision in this project.

Additional Gemma 4 capabilities used:
- **Native function calling** — Scout extracts structured JSON concept tags without prompt engineering workarounds
- **Native audio input** — Sage accepts voice responses via E4B's audio encoder, no TTS pipeline required
- **140+ language support** — Sage conducts sessions in Tamil, Hindi, Arabic, and Swahili natively. Demonstrated in the demo video.
- **128K context window** — Sage reviews an entire semester of interaction history in a single pass

## Demo video

> *3 minutes. Recorded with Wi-Fi visibly disconnected throughout.*

**0:00 – 0:20** — The problem: real before/after data from SRMIST coursework
**0:20 – 1:20** — Core loop: paste AI content → Scout tags → Sage session with countdown timer → concept cleared
**1:20 – 2:10** — Lens moment: handwritten diagram held to camera → exact error identified → audio correction in student's language
**2:10 – 2:40** — **Tamil demo**: entire Sage session conducted in Tamil (தமிழ்) — Sage questions and responses both in Tamil, natively
**2:40 – 3:00** — Instructor heatmap: class-level debt signals, zero individual data exposed

*[Link to be added before submission deadline]*

## Judging criteria alignment

| Criterion | Weight | How KnowLedge scores |
|---|---|---|
| **Impact** | 30% | Addresses 1.5B+ learners across connected and disconnected regions. Works on ₹30,000 laptops with intermittent power. Introduces a new measurable metric — comprehension debt — that does not exist in any current EdTech product. |
| **Innovation** | 30% | No existing tool tracks the per-concept delta between AI-assisted and unassisted understanding over time. KnowLedge creates an entirely new measurement category in education. |
| **Technical Execution** | 25% | Multi-tier Gemma 4 (E2B background tagging under 1.5 GB RAM, E4B contradiction detection, vision trace analysis, native audio output), local RAG, SQLite, native function calling, and a 5-layer anti-gaming system — the complete capability stack, each feature serving a specific pedagogical purpose. |
| **Accessibility** | 15% | Fully offline on consumer hardware. Student data architecturally incapable of leaving the device. 140+ languages natively. Runs on 8 GB RAM minimum. |

## Architecture

```
┌─────────────────── Student Device ──────────────────────┐
│                                                          │
│  Streamlit / FastAPI UI  ←→  Orchestration Controller   │
│                                    │                     │
│         ┌──────────────────────────┤                    │
│         ▼          ▼               ▼                     │
│      Scout       Sage            Lens                    │
│    (E2B·bg)   (E4B·dialog)  (E4B·vision+audio)          │
│         │          │               │                     │
│         └──────────┴───────────────┘                    │
│                    │                                     │
│            SQLite · ChromaDB                            │
│          (all data on-device)                           │
│                    │                                     │
│         ▼ sync only on Wi-Fi ▼                          │
└──────────────────────────────────────────────────────────┘
		     │  anonymised aggregate only
		     ▼
	    University Aggregate Server
	    (concept counts, no student IDs)
		     │
		     ▼
	    Instructor Heatmap
```

Full technical specification: [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)

## Anti-gaming: why Sage cannot be fooled

KnowLedge does not need to be ungameable. It needs to be **harder to game than to learn the concept.**

Five independent layers:

1. **Timed responses** — 75-second countdown per turn, visible to the student. Not enough time to query ChatGPT and rephrase.
2. **Contradiction-depth questioning** — Sage reads the student's specific prior answer and probes the exact claim they made. Generic AI answers are obviously mismatched.
3. **Voice-first mode** — Students speak answers aloud. Simultaneously speaking and typing a question into another AI is cognitively demanding enough to be a real deterrent.
4. **Lens verification as the clearing gate** — Only Lens verification moves a concept to "Owned". A student cannot ask AI to draw a diagram by hand.
5. **Session fingerprinting** — Response timing variance, paste detection, and audio duration patterns are logged. Suspiciously consistent sessions are flagged as `integrity_suspect` in the sync payload — the instructor sees "cleared*" not "cleared".

## Privacy model

Student debt data — their failures, misconceptions, gap history — **never leaves their device**. This is not a configurable privacy setting. It is an architectural guarantee.

What the instructor receives:
```json
{
  "course_id": "CS301",
  "week": "2026-W16",
  "concepts": [
    { "concept": "Recursion", "status": "on_loan", "subject": "DSA" }
  ]
}
```

No `student_id`. No `source_text`. No answers. No transcripts. The server increments a counter and discards the payload. A `PrivacyViolationError` is raised at the aggregator level if any PII field is detected before sending.

## Global reach

| Region | Local challenge | How KnowLedge addresses it |
|---|---|---|
| South & Southeast Asia | High student-to-faculty ratios | Scales personalised Socratic dialogue without extra staff |
| Sub-Saharan Africa | Power and connectivity outages during exam season | Offline-first — works through infrastructure failures |
| Latin America | Rapid AI adoption with minimal digital literacy frameworks | Structures AI usage habits from first interaction |
| MENA | Arabic-script coursework, multilingual classrooms | Gemma 4 native Arabic support — no translation pipeline |
| Europe & North America | Academic integrity regulations tightening | Reframes AI as a learning scaffold, not a shortcut |

## Deployment

### Live demo
**→ https://knowledge.onrender.com**

FastAPI on Render · Gemma 4 E4B on Google Cloud Run GPU · Fully working Sage and Lens sessions

### Run locally (fully offline after first setup)

```bash
# Prerequisites: Ollama installed
ollama pull gemma4:e2b
ollama pull gemma4:e4b

# Install and run
git clone https://github.com/Charan-suresh/KnowLedge
cd KnowLedge
pip install -r requirements.txt
cp .env.example .env
uvicorn knowledge.main:app --reload

# Open http://localhost:8000
# Wi-Fi can now be turned off — everything runs locally
```

### Hardware requirements

| Config | RAM | Notes |
|---|---|---|
| Minimum | 8 GB | `LOW_RAM=true` in config — agents take turns |
| Recommended | 16 GB | All agents run concurrently |
| Cloud demo | Any | Inference on Cloud Run GPU |

### Deploy your own cloud instance

```bash
# Step 1 — Deploy Ollama + Gemma 4 to Google Cloud Run
gcloud auth login
./cloud-run/deploy-ollama.sh   # ~10 minutes, pulls E2B + E4B

# Step 2 — Deploy FastAPI to Render
# Connect GitHub repo at render.com → render.yaml auto-configures
# Add OLLAMA_BASE_URL and OLLAMA_AUTH_TOKEN from Step 1 output

# Step 3 — Verify before sharing
python scripts/verify_deployment.py https://your-app.onrender.com
```

Full deployment guide: [cloud-run/README.md](cloud-run/README.md)

## Repository structure

```
KnowLedge/
├── knowledge/              # FastAPI backend
│   ├── agents/             # Scout (E2B), Sage (E4B), Lens (E4B vision)
│   ├── integrity/          # Anti-gaming: fingerprinting, lens guard, timer
│   ├── sync/               # Privacy-preserving instructor sync
│   ├── routers/            # ledger, progress, reports, solo, events
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # CSS, fonts
├── cloud-run/              # Google Cloud Run deployment scripts
├── scripts/                # Real data collection, verify deployment
├── tests/                  # Privacy, integrity, and sync tests
├── TECHNICAL_ARCHITECTURE.md
├── render.yaml
├── requirements.txt
└── LICENSE                 # Apache 2.0
```

## What no other submission will have

- A new measurement category: **comprehension debt**, distinct from grades, attendance, and engagement
- **Real evidence**: two weeks of genuine student data from SRMIST, collected before the deadline
- **Tamil language demo**: Sage conducting a full Socratic session in Tamil — authentic, not a translation layer
- **Structural privacy**: student data architecturally incapable of leaving the device — not policy, not settings
- **The complete Gemma 4 stack**: E2B background tagging under 1.5 GB RAM, E4B contradiction detection, vision trace analysis, native audio output, function calling, and local RAG — each feature serving a specific pedagogical purpose
- **A working deployment**: live at https://knowledge.onrender.com right now

## Built by

**Charan Suresh** — Student, Department of Language, Culture, and Society, SRMIST Kattankulatham
*This project was tested on the developer's own coursework. The before/after data in this README is real.*

<div align="center">

*KnowLedge does not ask Google DeepMind to fund another AI tutor.*
*It asks them to fund the first tool that makes AI usage in education structurally accountable —*
*for every student, everywhere, without internet.*

**Apache 2.0 · Gemma 4 Good Hackathon · Future of Education Track**

</div>

- A polished desktop/web experience with Ledger, Progress, Reports, and Help views.
- Offline-first design using local SQLite, Ollama, and ChromaDB.
- Privacy-preserving instructor sync that shares only concept-level summaries.
- Integrity checks that combine session fingerprints, anti-spoof signals, and multimodal verification.

## Product Overview

KnowLedge has three main workflows:

1. Scout detects concepts in pasted material and logs them to the ledger.
2. Sage runs a Socratic clearing session until the student can explain the concept themselves.
3. Lens checks handwritten or visual work and helps flag concepts that still need review.

There is also a weekly instructor sync path that exports only anonymous, aggregate concept data.

## Repository Structure

- `knowledge/` - FastAPI backend, orchestration, sync, integrity, RAG, and templates.
- `cdt_vectorstore/` - Local ChromaDB persistence for curriculum context.
- `knowledge_dashboard.html` - Standalone dashboard prototype.
- `requirements.txt` - Python dependencies for the backend.

## Backend Setup

### 1. Create a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Ollama

KnowLedge expects a local Ollama server.

```bash
ollama serve
```

If you are using the default Gemma tags, make sure the model names in `knowledge/config.py` exist in your local Ollama install.

### 4. Run the app

```bash
python -m uvicorn knowledge.main:app --host 127.0.0.1 --port 8000
```

Open these views in a browser:

- `http://127.0.0.1:8000/ledger`
- `http://127.0.0.1:8000/progress`
- `http://127.0.0.1:8000/reports`
- `http://127.0.0.1:8000/help`

## Deploy your own instance

### Prerequisites

- Google Cloud account with credits
- Render account (free)
- GitHub account
- Google Cloud CLI installed: `brew install google-cloud-sdk`

### Step 1 - Deploy Ollama to Google Cloud Run

```bash
gcloud auth login
nano cloud-run/deploy-ollama.sh
./cloud-run/deploy-ollama.sh
```

Copy the `OLLAMA_BASE_URL` and `OLLAMA_AUTH_TOKEN` values printed at the end.

### Step 2 - Deploy the web app to Render

1. Fork this repository on GitHub.
2. Go to render.com and create a new web service from your fork.
3. Render auto-detects `render.yaml`; click deploy.
4. In Render environment variables, add:
	- `OLLAMA_BASE_URL`
	- `OLLAMA_AUTH_TOKEN`
5. Trigger a manual deploy.

### Token refresh (important)

Google Cloud identity tokens expire after one hour. Run this before judges evaluate, and again every hour during judging:

```bash
./cloud-run/refresh-token.sh
```

For a longer-lived setup, follow service account instructions in `cloud-run/README.md`.

### Render filesystem note

Render free tier uses ephemeral disk. `knowledge.db` and `chroma_store/` are recreated on restarts/deploys. This repo enables `DEMO_MODE=true` by default and seeds realistic demo data automatically on startup.

### Pre-share verification

```bash
python scripts/verify_deployment.py https://your-app.onrender.com
```

All checks should pass before sharing with judges.

### 5. Optional: load curriculum material into ChromaDB

```bash
python -m knowledge.vectorize path/to/course_material.pdf
```

This creates local retrieval context for Sage responses.

## Live Demo For Kaggle

The best judge-facing option is a Hugging Face Space running the Streamlit demo in `app.py`.

Why this works well:

- It gives you a public HTTPS link with zero setup for judges.
- The Space can boot automatically when opened, so there is no manual server start step for reviewers.
- You can connect it to your hosted backend with a single environment variable, or let it fall back to demo data.

Recommended setup:

1. Create a new Hugging Face Space.
2. Select the **Gradio** SDK (industry standard for ML demo UIs).
3. Point the Space to this repository's `app.py`.
4. Add `gradio` to the dependencies file, which is already done.
5. If you want live backend data, set a Space secret named `KNOWLEDGE_API_URL` to your deployed backend URL.
6. Share the Space URL in your Kaggle submission as the live demo link.

If you want the Space to show live backend state, keep your FastAPI app deployed separately and set `KNOWLEDGE_API_URL` to that public endpoint. If you want a self-contained demo, the Space still works in fallback mode with sample data.

## Configuration

Most backend settings live in `knowledge/config.py` and can also be overridden with environment variables.

Important values include:

- `OLLAMA_HOST`
- `SCOUT_MODEL`
- `SAGE_MODEL`
- `LENS_MODEL`
- `DB_PATH`
- `CHROMA_PATH`
- `SYNC_ON_WIFI_ONLY`


## Testing

Run the backend tests with:

```bash
python -m pytest
```

There are also lightweight smoke scripts in the repository root for quick local checks.

## Notes for Reviewers

- The project is intentionally offline-first.
- Sync only shares aggregate concept data.
- The main app is in the `knowledge/` package.
