---
title: KnowLedge Inference API
emoji: 📖
colorFrom: yellow
colorTo: green
sdk: gradio
python_version: 3.10.16
sdk_version: 4.44.1
app_file: app.py
pinned: true
license: apache-2.0
tags:
  - gemma
  - gemma-4
  - education
  - inference-api
  - knowledge
  - hackathon
short_description: Gemma 4 GGUF inference backend for KnowLedge
---

# KnowLedge Inference API

Gemma 4 E2B + quantized E4B inference backend for the
[KnowLedge](https://github.com/Charan-suresh/KnowLedge) learning ledger.

Part of the Kaggle Gemma 4 Good Hackathon submission.

## Endpoints

| Endpoint | Model | Used by |
|---|---|---|
| `/api/generate` | E2B or E4B | Scout (concept tagging), Sage (Socratic dialogue) |
| `/api/generate_vision` | E4B vision | Lens (handwriting verification) |
| `/api/health` | - | FastAPI health check |

## Architecture

This Space uses **Gradio + FastAPI** together via `gr.mount_gradio_app`:

- The **Gradio** wrapper satisfies HF Spaces `sdk: gradio` requirements so the Space is hosted on port 7860 without a custom Dockerfile.
- The **FastAPI** layer exposes the REST endpoints the Render backend calls via `httpx`.
- Inference runs entirely on **CPU** on the standard free HF Spaces tier — no ZeroGPU required.

| Model | Backend | Notes |
|---|---|---|
| E4B | `llama-cpp-python` GGUF | `UD-IQ3_XXS` quant, ~2.5 GB RAM, fast-ish on CPU |
| E2B | HuggingFace `transformers` | float32, ~8 GB RAM, slower on CPU |

Override the E4B GGUF file with the `GEMMA_E4B_GGUF_FILE` Space secret if you want a different quantisation.

## Not for direct use

This Space is called programmatically by the KnowLedge FastAPI backend
deployed on Render. It is not a chat interface.

## Deployment note

Deploy the files inside `hf_space/` to a separate Hugging Face Space repository.
Do **not** deploy the root `app.py` here — that file is the standalone Gradio demo
that connects back to the Render backend, not the inference backend itself.

## Required setup

1. **No special hardware needed** — leave the Space on the default free CPU tier.
2. Set the **`HF_TOKEN`** Space secret (Settings → Repository secrets) to a token that has accepted the Gemma 4 terms on HuggingFace. This is required for `google/gemma-4-e2b-it` (gated model) to download at runtime.
3. On **Render**, set:
   - `INFERENCE_BACKEND=hf_space`
   - `HF_SPACE_URL=charan-ml/knowledge-inference`

### Optional env vars (Space secrets)

| Variable | Default | Effect |
|---|---|---|
| `GEMMA_E4B_GGUF_FILE` | `gemma-4-E4B-it-UD-IQ3_XXS.gguf` | Switch to a different GGUF quant |
| `GEMMA_E4B_CTX` | `4096` | llama-cpp context window |
| `GEMMA_E4B_THREADS` | `4` | CPU threads for llama-cpp |
