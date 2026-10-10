import httpx

response = httpx.get("http://127.0.0.1:8000/operator")
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")