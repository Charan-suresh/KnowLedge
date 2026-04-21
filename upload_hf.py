import os

from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
space_id = "charan-ml/knowledge-inference"
base_dir = os.path.abspath("hf_space")

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
