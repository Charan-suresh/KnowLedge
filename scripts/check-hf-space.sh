#!/bin/bash
# Quick diagnostic for HF Space status

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  HF Space Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HF_SPACE_URL="https://charan-ml-knowledge-inference.hf.space"

echo "1. Checking HF Space health..."
curl -s "$HF_SPACE_URL/api/health" | python3 -m json.tool
echo ""

echo "2. Testing text generation..."
curl -s -X POST "$HF_SPACE_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?", "model": "e4b", "max_tokens": 50}' \
  | python3 -m json.tool
echo ""

echo "3. Checking your app status..."
curl -s "https://knowledge-sv13.onrender.com/api/status" | python3 -m json.tool
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
