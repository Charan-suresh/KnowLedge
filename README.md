# KnowLedge

KnowLedge is a local-first learning debt tracker. It now runs a single Ollama-backed model for all four roles:

- `Scout` extracts concepts
- `Sage` runs Socratic clearing
- `Lens` checks handwritten notes and diagrams
- `Solo` scores recall answers

## Local setup

1. Install Ollama.
2. Pull `gemma4:e4b-q4_K_M`.
3. Start `ollama serve`.
4. Install dependencies from `requirements.txt`.
5. Run the app with `uvicorn knowledge.main:app --reload`.

The app will automatically fall back across these available models:

`gemma4:e4b-q4_K_M -> gemma4:e4b -> gemma3:4b -> gemma3:1b`
