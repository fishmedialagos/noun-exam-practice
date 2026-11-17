"""Check OpenAI API credentials/model access without exposing the secret key."""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

key = os.environ.get("OPENAI_API_KEY")
model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
if not key:
    print("MISSING: OPENAI_API_KEY is not set. Add it to your .env file or environment.")
    sys.exit(1)

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "Reply with valid JSON only."},
        {"role": "user", "content": "Return this JSON: {\"status\":\"ok\"}"}
    ],
    "temperature": 0,
    "max_tokens": 30,
    "response_format": {"type": "json_object"}
}
try:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload, timeout=(10, 45)
    )
except requests.RequestException as exc:
    print(f"CONNECTION ERROR: {exc}")
    sys.exit(2)

if response.status_code != 200:
    try:
        detail = response.json().get("error", {}).get("message", response.text[:500])
    except ValueError:
        detail = response.text[:500]
    print(f"OPENAI ERROR ({response.status_code}): {detail}")
    sys.exit(3)

try:
    content = response.json()["choices"][0]["message"]["content"]
    import json
    parsed = json.loads(content)
except (ValueError, KeyError, IndexError, TypeError) as exc:
    print(f"UNEXPECTED RESPONSE: {exc}")
    sys.exit(4)

print(f"SUCCESS: OpenAI API is reachable. Model: {model}. JSON response: {parsed}")
