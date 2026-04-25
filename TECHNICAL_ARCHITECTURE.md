# Technical Architecture

KnowLedge now uses a single local Ollama model with role-switching system prompts.

- `knowledge/prompts.py` stores the only per-role configuration.
- `knowledge/ollama_client.py` resolves the best available local model and handles chat/status calls.
- `knowledge/init_db.py` manages the SQLite schema.
- `knowledge/seed_demo.py` loads optional demo data.
- `knowledge/main.py` serves the ledger, progress, Scout, Sage, Lens, Solo, and status routes.
