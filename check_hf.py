import os

from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
print(api.repo_info(repo_id="charan-ml/knowledge-inference", repo_type="space"))
