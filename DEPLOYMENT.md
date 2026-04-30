# Deployment Guide

## Deploy to Render (Production)

### 1. Deploy HF Space First

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Create a new Space with these settings:
   - **SDK**: Gradio
   - **Hardware**: CPU Basic (free tier)
3. Upload all files from `hf_space/` folder
4. Wait for the Space to build and start
5. Copy your Space URL (e.g., `https://your-username-your-space-name.hf.space`)

### 2. Deploy to Render

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Render will auto-detect `render.yaml`
6. Add environment variable:
   - **Key**: `HF_SPACE_URL`
   - **Value**: Your HF Space URL from step 1
7. Click "Create Web Service"

### 3. Verify Deployment

Visit `https://your-app.onrender.com/api/status` — you should see:

```json
{
  "ready": true,
  "model": "hf-space-model",
  "ollama_running": true
}
```

## Environment Variables

### Required for Production

| Variable | Value | Description |
|----------|-------|-------------|
| `INFERENCE_BACKEND` | `hf_space` | Use HF Space (set by default in render.yaml) |
| `HF_SPACE_URL` | `https://...hf.space` | Your deployed HF Space URL |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `false` | Enable demo data |
| `COURSE_ID` | `CS301` | Course identifier |
| `UNIVERSITY_SERVER_URL` | - | Sync endpoint (optional) |

## Local Development

For local development with HF Space:

```bash
cp .env.example .env
# Edit .env and set:
# INFERENCE_BACKEND=hf_space
# HF_SPACE_URL=https://your-username-your-space-name.hf.space

pip install -r requirements.txt
uvicorn knowledge.main:app --reload
```

For offline development with Ollama:

```bash
cp .env.example .env
# Edit .env and set:
# INFERENCE_BACKEND=ollama
# OLLAMA_BASE_URL=http://localhost:11434

ollama pull gemma4:e4b
ollama serve

pip install -r requirements.txt
uvicorn knowledge.main:app --reload
```

## Troubleshooting

### "HF Space error: Connection refused"

- Your HF Space is still starting up (cold start takes 20-30 seconds)
- Check Space logs at `https://huggingface.co/spaces/your-username/your-space-name/logs`

### "Inference backend is not configured"

- Set `HF_SPACE_URL` environment variable in Render dashboard
- Redeploy the service

### "Model not loaded"

- Check HF Space health: `curl https://your-space.hf.space/api/health`
- Restart the Space if needed
