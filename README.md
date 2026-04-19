

# KnowLedge

KnowLedge is a local-first learning verification platform built for the Gemma 4 for Good hackathon.

## Live demo

**Try it now -> https://knowledge.onrender.com**

Powered by Gemma 4 E4B on Google Cloud Run GPU.
Full Sage sessions, Lens camera verification, and real
comprehension debt tracking - all working in your browser.

It helps students turn borrowed understanding into real mastery. The system tracks concepts that appear in pasted work, guides the learner through Socratic clearing sessions, verifies understanding with multimodal checks, and shares only privacy-preserving aggregates with instructors.

## Why This Project Exists

Most AI learning tools optimize for speed. KnowLedge optimizes for retention and accountability.

The core idea is simple:

- If a student copies a concept without understanding it, the concept is logged as learning debt.
- If the student can explain it clearly in their own words, the concept is cleared.
- If the explanation still fails integrity checks, the concept stays under review.

The result is a system that uses AI to force better learning rather than passive answer collection.

## What Judges Should Look For

- A polished desktop/web experience with Ledger, Progress, Reports, and Help views.
- Offline-first design using local SQLite, Ollama, and ChromaDB.
- Privacy-preserving instructor sync that shares only concept-level summaries.
- Integrity checks that combine session fingerprints, anti-spoof signals, and multimodal verification.
- A separate Expo mobile companion app with the same product model.

## Product Overview

KnowLedge has three main workflows:

1. Scout detects concepts in pasted material and logs them to the ledger.
2. Sage runs a Socratic clearing session until the student can explain the concept themselves.
3. Lens checks handwritten or visual work and helps flag concepts that still need review.

There is also a weekly instructor sync path that exports only anonymous, aggregate concept data.

## Repository Structure

- `knowledge/` - FastAPI backend, orchestration, sync, integrity, RAG, and templates.
- `knowledge-mobile/` - Expo + React Native companion app.
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

## Mobile Companion

The mobile app lives in `knowledge-mobile/` and is separate from the backend.

```bash
cd knowledge-mobile
npm install
npx expo start
```

If you want a device build:

```bash
npm run android
npm run ios
```

The mobile app supports three runtime modes:

- `on_device_full`
- `on_device_scout`
- `server_only`

The native Gemma bridge is scaffolded for future Android and iOS implementation.

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

The Expo app has its own config in `knowledge-mobile/app.config.js` and `knowledge-mobile/app.json`.

## Testing

Run the backend tests with:

```bash
python -m pytest
```

There are also lightweight smoke scripts in the repository root for quick local checks.

## Notes for Reviewers

- The project is intentionally offline-first.
- Sync only shares aggregate concept data.
- The mobile native inference layer is scaffolded, not fully implemented.
- The main app is in the `knowledge/` package; the mobile app is an independent companion workspace.
