# KnowLedge

KnowLedge is a local-first learning debt tracker. It uses Gemma 4 models for all four roles:

- `Scout` extracts concepts
- `Sage` runs Socratic clearing
- `Lens` checks handwritten notes and diagrams
- `Solo` scores recall answers

## Deployment

**Production (Render)**: Uses Hugging Face Space with Gemma 4 E4B by default.

**Local development**: Can use either HF Space or local Ollama.

## Local setup

### Option 1: Use HF Space (Recommended)

1. Deploy the `hf_space/` folder to a Hugging Face Space
2. Copy `.env.example` to `.env`
3. Set `INFERENCE_BACKEND=hf_space`
4. Set `HF_SPACE_URL=https://your-username-your-space-name.hf.space`
5. Install dependencies: `pip install -r requirements.txt`
6. Run: `uvicorn knowledge.main:app --reload`

### Option 2: Use local Ollama (Offline mode)

1. Install Ollama
2. Pull `gemma4:e4b`: `ollama pull gemma4:e4b`
3. Start `ollama serve`
4. Copy `.env.example` to `.env`
5. Set `INFERENCE_BACKEND=ollama`
6. Install dependencies: `pip install -r requirements.txt`
7. Run: `uvicorn knowledge.main:app --reload`

The app will automatically fall back across these available models:

`gemma4:e4b -> gemma3:4b -> gemma3:1b`
