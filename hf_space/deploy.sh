#!/bin/bash
# KnowLedge - Hugging Face Space deployment guide
# Run each block manually in sequence.
# Prerequisites: huggingface_hub installed, HF account created

# -- Step 1: Install HF CLI -------------------------------------------------
pip install huggingface_hub

# -- Step 2: Login to Hugging Face ------------------------------------------
huggingface-cli login
# Paste your HF token when prompted
# Get token at: https://huggingface.co/settings/tokens
# Token needs "write" permission

# -- Step 3: Create the Space ------------------------------------------------
python3 - << 'EOF'
from huggingface_hub import HfApi
api = HfApi()
api.create_repo(
    repo_id="knowledge-inference",   # becomes: your-username/knowledge-inference
    repo_type="space",
    space_sdk="gradio",
    private=False,                    # must be public for free ZeroGPU
    exist_ok=True,
)
print("Space created successfully")
EOF

# -- Step 4: Upload Space files ----------------------------------------------
python3 - << 'EOF'
from huggingface_hub import HfApi
import os

api = HfApi()
space_id = f"{api.whoami()['name']}/knowledge-inference"
base_dir = os.getcwd()

files = ["app.py", "inference.py", "requirements.txt", "README.md"]
for f in files:
    path = os.path.join(base_dir, f)
    api.upload_file(
        path_or_fileobj=path,
        path_in_repo=f,
        repo_id=space_id,
        repo_type="space",
    )
    print(f"Uploaded: {f}")

print(f"\nSpace URL: https://huggingface.co/spaces/{space_id}")
print(f"API URL:   https://{space_id.replace('/', '-')}.hf.space")
EOF

# -- Step 5: Enable ZeroGPU --------------------------------------------------
# Go to: https://huggingface.co/spaces/YOUR-USERNAME/knowledge-inference/settings
# Under "Space Hardware" -> select "ZeroGPU (NVIDIA H200)"
# This cannot be done via API - must be done in the HF web UI
echo "-> Manually enable ZeroGPU in Space settings:"
echo "  https://huggingface.co/spaces/$(huggingface-cli whoami)/knowledge-inference/settings"

# -- Step 6: Get your Space API URL ------------------------------------------
# After deployment (~3-5 minutes for build), your endpoints are:
# Text:   POST https://your-username-knowledge-inference.hf.space/api/generate
# Vision: POST https://your-username-knowledge-inference.hf.space/api/generate_vision
# Health: GET  https://your-username-knowledge-inference.hf.space/api/health

# -- Step 7: Set Render env vars ---------------------------------------------
# In Render dashboard -> your service -> Environment:
# INFERENCE_BACKEND = hf_space
# HF_SPACE_URL      = your-username/knowledge-inference
# Then trigger a manual redeploy on Render.

echo "Deployment complete. Set HF_SPACE_URL in Render and redeploy."
