#!/bin/bash
# Run this once per hour during the judging period, or set up a cron job.
# Requires Render API key: https://render.com/docs/api

RENDER_API_KEY="your-render-api-key"
RENDER_SERVICE_ID="your-render-service-id"

NEW_TOKEN=$(gcloud auth print-identity-token)

echo "-> Refreshing OLLAMA_AUTH_TOKEN on Render..."
curl -X PATCH "https://api.render.com/v1/services/$RENDER_SERVICE_ID/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "[{\"key\": \"OLLAMA_AUTH_TOKEN\", \"value\": \"$NEW_TOKEN\"}]"

echo ""
echo "✓ Token refreshed. Valid for 1 hour."
