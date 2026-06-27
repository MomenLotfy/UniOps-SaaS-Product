import os
import requests

url = "https://router.bynara.id/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {os.environ['BYNARA_API_KEY']}",
    "Content-Type": "application/json",
}

payload = {
    "model": "mistral-large",
    "messages": [
        {
            "role": "user",
            "content": "Hello"
        }
    ]
}

r = requests.post(url, headers=headers, json=payload)

print(r.status_code)
print(r.text)
