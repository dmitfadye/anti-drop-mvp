import httpx

response = httpx.post(
    "http://127.0.0.1:8000/api/sim",
    json={
        "old_phone": "+79160000002",
        "new_phone": "+79160000003",
        "otp_ok_old": True,
        "otp_ok_new": True
    },
    headers={"X-Sandbox-Subject": "alice"}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")