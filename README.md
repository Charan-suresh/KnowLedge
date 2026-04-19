# KnowLedge

KnowLedge is a local-first learning platform for tracking borrowed understanding, clearing it through Socratic dialogue, and reporting aggregate progress. The repository now contains two codebases:

- The desktop/web app and backend live at the repository root in the `knowledge/` package.
- The mobile companion app lives in `knowledge-mobile/`.

The backend is designed to run locally with Ollama, SQLite, and ChromaDB. The mobile workspace is an Expo app scaffold with the same product model and a native inference bridge stub for future Android and iOS work.

## Repository Layout

- `knowledge/` - FastAPI backend, orchestration, sync, integrity, and template rendering.
- `knowledge_dashboard.html` - Standalone dashboard prototype used during UI work.
- `knowledge-mobile/` - Expo + React Native companion app.
- `cdt_vectorstore/` - Local ChromaDB persistence.
- `requirements.txt` - Python dependencies for the backend.

## Backend Setup

### 1. Create and activate a Python environment

Use the environment manager you already have, or create one with your preferred tool. If you are using `venv`, a typical setup looks like this:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Ollama

KnowLedge expects a local Ollama server.

```bash
ollama serve
```

If you plan to use the default Gemma models, make sure the tags you reference in `knowledge/config.py` are available in your Ollama install.

### 4. Run the backend

```bash
python -m uvicorn knowledge.main:app --host 127.0.0.1 --port 8000
```

The main views are available at:

- `http://127.0.0.1:8000/ledger`
- `http://127.0.0.1:8000/progress`
- `http://127.0.0.1:8000/reports`
- `http://127.0.0.1:8000/help`

### 5. Optional: ingest syllabus material into ChromaDB

```bash
python -m knowledge.vectorize path/to/course_material.pdf
```

This populates the local vector store in `cdt_vectorstore/` for RAG-backed Sage responses.

## Mobile Setup

The mobile app is self-contained in `knowledge-mobile/`.

```bash
cd knowledge-mobile
npm install
npx expo start
```

For native builds or device testing:

```bash
npm run android
npm run ios
```

The mobile app supports three runtime modes:

- `on_device_full`
- `on_device_scout`
- `server_only`

Mode detection and model readiness are handled in the app settings, and the native Gemma bridge is scaffolded for future Android/iOS implementation.

## Configuration Notes

The backend reads its main settings from `knowledge/config.py` and environment variables. The most important ones are:

- `OLLAMA_HOST`
- `SCOUT_MODEL`
- `SAGE_MODEL`
- `LENS_MODEL`
- `DB_PATH`
- `CHROMA_PATH`
- `SYNC_ON_WIFI_ONLY`

The mobile app has its own Expo configuration in `knowledge-mobile/app.config.js` and `knowledge-mobile/app.json`.

## Testing

Backend smoke and contract tests are available in `tests/`.

```bash
python -m pytest
```

If you only want a quick sanity check, the lightweight smoke scripts in the root of the repository can also be run directly.

## Notes

- The project is designed to run offline-first wherever possible.
- Sync is privacy-preserving and only shares concept-level aggregates.
- The current mobile native inference module is scaffolded, not fully implemented.
- If you are changing the backend schema, start by reviewing `knowledge/db.py` and `knowledge/main.py`.
