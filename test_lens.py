import requests

with open("test.jpg", "wb") as f:
    f.write(b"fake image data")

with open("test.jpg", "rb") as f:
    files = {"file": f}
    data = {"document_type": "auto", "student_id": "test"}
    r = requests.post("http://127.0.0.1:8000/api/lens", files=files, data=data)
    print(r.status_code, r.text)
