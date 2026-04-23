import sys
sys.path.append("hf_space")
from hf_space.inference import generate_text

try:
    print(generate_text("e4b", "Hello, who are you?"))
except Exception as e:
    print("ERROR:", repr(e))
