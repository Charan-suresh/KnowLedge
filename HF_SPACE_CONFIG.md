# Hugging Face Space Configuration

## Your HF Space Details

**Space Name**: [Your Space Name Here]
**Space URL**: [Your Space URL Here]

Example format: `https://charan-suresh-knowledge-inference.hf.space`

## Quick Setup

1. **Deploy HF Space**:
   ```bash
   cd hf_space/
   # Upload these files to your HF Space:
   # - app.py
   # - inference.py
   # - requirements.txt
   # - README.md
   ```

2. **Configure Render**:
   - Go to Render Dashboard → Your Service → Environment
   - Add variable: `HF_SPACE_URL` = `[your space URL]`
   - Redeploy

3. **Test**:
   ```bash
   curl https://your-space.hf.space/api/health
   curl https://your-app.onrender.com/api/status
   ```

## HF Space Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Welcome message |
| `/api/health` | GET | Health check |
| `/api/generate` | POST | Text generation (Scout, Sage, Solo) |
| `/api/generate_vision` | POST | Vision generation (Lens) |

## Render Environment Variables

```bash
# Required
HF_SPACE_URL=https://your-username-your-space-name.hf.space

# Optional
DEMO_MODE=false
COURSE_ID=CS301
```

## Troubleshooting

- **Space not responding**: Wait 30s for cold start
- **Model not loaded**: Check Space logs on HF
- **Connection timeout**: Increase timeout in config.py (currently 120s)
