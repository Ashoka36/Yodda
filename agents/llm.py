import requests
from fastapi import HTTPException
from config.settings import NVIDIA_API_URL, NVIDIA_API_KEY, DEFAULT_MODEL

def call_llm(prompt: str, endpoint: str = None, key: str = None, model: str = None):
    endpoint = endpoint or NVIDIA_API_URL
    key = key or NVIDIA_API_KEY
    model = model or DEFAULT_MODEL

    if not key or not key.startswith("nvapi-"):
        raise HTTPException(500, "Invalid or missing NVIDIA API key")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
        "stream": False
    }

    full_url = f"{endpoint}/chat/completions"
    response = requests.post(full_url, headers=headers, json=data)

    if response.status_code != 200:
        error_text = response.text
        raise HTTPException(500, f"NVIDIA API error: {response.status_code} - {error_text}")

    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise HTTPException(500, "Unexpected NVIDIA response format")
