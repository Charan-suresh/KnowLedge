#!/bin/bash
set -e

# -- Configuration -- edit these before running -------------------------
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
SERVICE_NAME="knowledge-ollama"
IMAGE="ollama/ollama:latest"
# ----------------------------------------------------------------------

echo "-> Setting project..."
gcloud config set project "$PROJECT_ID"

echo "-> Enabling required APIs..."
gcloud services enable run.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com

echo "-> Deploying Ollama to Cloud Run with GPU..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --memory 16Gi \
  --cpu 4 \
  --port 11434 \
  --timeout 300 \
  --concurrency 4 \
  --min-instances 0 \
  --max-instances 1 \
  --set-env-vars OLLAMA_NUM_PARALLEL=4,OLLAMA_MAX_LOADED_MODELS=2 \
  --no-allow-unauthenticated \
  --region "$REGION"

echo "-> Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --format 'value(status.url)')
echo "Ollama URL: $SERVICE_URL"

echo "-> Generating auth token for Render..."
AUTH_TOKEN=$(gcloud auth print-identity-token)
echo ""
echo "======================================================"
echo "  Add these to Render environment variables:"
echo ""
echo "  OLLAMA_BASE_URL=$SERVICE_URL"
echo "  OLLAMA_AUTH_TOKEN=$AUTH_TOKEN"
echo "======================================================"
echo ""

echo "-> Pulling Gemma 4 models (this takes 5-10 minutes)..."
curl -X POST "$SERVICE_URL/api/pull" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "gemma4:e2b"}' \
  --max-time 600

echo ""
curl -X POST "$SERVICE_URL/api/pull" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "gemma4:e4b"}' \
  --max-time 600

echo ""
echo "-> Verifying models are available..."
curl "$SERVICE_URL/api/tags" \
  -H "Authorization: Bearer $AUTH_TOKEN"

echo ""
echo "✓ Cloud Run deployment complete."
echo "  Ollama is running at: $SERVICE_URL"
echo "  Copy OLLAMA_BASE_URL and OLLAMA_AUTH_TOKEN into Render."
