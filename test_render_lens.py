import requests
import base64

url = "https://knowledge-sv13.onrender.com/api/lens"
with open("test.jpg", "wb") as f:
    f.write(b"fake image data")

with open("test.jpg", "rb") as f:
    files = {"file": f}
    data = {"document_type": "auto", "student_id": "test"}
    resp = requests.post(url, files=files, data=data)

print(resp.status_code)
print(resp.text)
