import requests
import threading
import time

url = "https://knowledge-sv13.onrender.com/api/lens"

def hit_lens():
    with open("test.jpg", "rb") as f:
        resp = requests.post(url, files={"file": f}, data={"document_type": "auto", "student_id": "test"})
    print("Lens:", resp.status_code)

t = threading.Thread(target=hit_lens)
t.start()
time.sleep(1)

# While lens is running, try to hit /api/status
try:
    resp = requests.get("https://knowledge-sv13.onrender.com/api/status", timeout=5)
    print("Status:", resp.status_code)
except Exception as e:
    print("Status check failed:", e)

t.join()
