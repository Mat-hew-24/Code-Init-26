import requests

BACKEND_URL = "https://api.gridx.io/register"

# def register_node(payload, token):
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#     r = requests.post(BACKEND_URL, json=payload, headers=headers, timeout=10)
#     r.raise_for_status()
#     return r.json()

def register_node(payload, token):
    print("\n📡 MOCK REGISTER_NODE CALLED")
    print("TOKEN:", token[:6], "...")
    print("PAYLOAD SENT TO BACKEND:")
    print(payload)
    return {"status": "ok"}

