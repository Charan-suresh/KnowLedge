# Cloud Run deployment for Ollama

This folder contains scripts and instructions to deploy Ollama + Gemma 4 on Google Cloud Run and connect it to the Render-hosted FastAPI app.

## One-time deployment steps

1. Push all code changes to GitHub `main`.
2. Run `gcloud auth login`.
3. Edit `PROJECT_ID` in `cloud-run/deploy-ollama.sh`.
4. Run `./cloud-run/deploy-ollama.sh`.
5. Copy `OLLAMA_BASE_URL` and `OLLAMA_AUTH_TOKEN` from script output.
6. Go to Render and deploy from `render.yaml`.
7. In Render environment variables add:
   - `OLLAMA_BASE_URL`
   - `OLLAMA_AUTH_TOKEN`
8. Trigger a manual redeploy in Render.
9. Run `python scripts/verify_deployment.py https://your-app.onrender.com`.
10. Set up a service account for a longer-lived token (instructions below).
11. Run `./cloud-run/refresh-token.sh` around 10 minutes before judging starts, then every hour if still using identity tokens.
12. Add your live URL to your README and submission write-up.

## Refreshing token during judging

Google identity tokens expire every hour:

```bash
./cloud-run/refresh-token.sh
```

## Longer-lived approach: dedicated invoker service account

Identity tokens generated from your interactive user session are short-lived. For longer operation, create a service account with Cloud Run Invoker role:

```bash
# Create service account
gcloud iam service-accounts create knowledge-invoker \
  --display-name "KnowLedge Cloud Run Invoker"

# Grant Cloud Run Invoker role
gcloud run services add-iam-policy-binding knowledge-ollama \
  --region us-central1 \
  --member "serviceAccount:knowledge-invoker@PROJECT_ID.iam.gserviceaccount.com" \
  --role "roles/run.invoker"

# Create and download key
gcloud iam service-accounts keys create cloud-run/invoker-key.json \
  --iam-account knowledge-invoker@PROJECT_ID.iam.gserviceaccount.com

# Generate token from key
gcloud auth activate-service-account --key-file=cloud-run/invoker-key.json
gcloud auth print-identity-token
```

Add `cloud-run/invoker-key.json` to `.gitignore` and never commit it.
