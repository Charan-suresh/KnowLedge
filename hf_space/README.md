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
---

# KnowLedge Inference API

Gemma 4 E2B + E4B inference backend for the
[KnowLedge](https://github.com/Charan-suresh/KnowLedge) learning ledger.

Part of the Kaggle Gemma 4 Good Hackathon submission.

## Endpoints

| Endpoint | Model | Used by |
|---|---|---|
| `/api/generate` | E2B or E4B | Scout (concept tagging), Sage (Socratic dialogue) |
| `/api/generate_vision` | E4B vision | Lens (handwriting verification) |
| `/api/health` | - | FastAPI health check |

## Not for direct use

This Space is called programmatically by the KnowLedge FastAPI backend
deployed on Render. It is not a chat interface.

## Deployment note

Deploy these files to a separate Hugging Face Space repository.
Do not import from the `knowledge/` package inside the Space app.
