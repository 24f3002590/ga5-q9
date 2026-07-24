import os
import json
import httpx

from prompts import SYSTEM_PROMPT


AIPIPE_BASE_URL = os.getenv(
    "AIPIPE_BASE_URL",
    "https://aipipe.org/openai/v1",
)

MODEL = os.getenv(
    "AIPIPE_MODEL",
    "gpt-4.1-mini",
)

API_KEY = os.getenv("AIPIPE_API_KEY")


class AIError(Exception):
    pass


async def call_model(dossier: dict, allowed_actions: list):
    """
    Ask the model to choose one safe action.
    """

    if not API_KEY:
        raise AIError("AIPIPE_API_KEY not configured")

    user_prompt = {
        "allowed_actions": allowed_actions,
        "dossier": dossier,
    }

    payload = {
        "model": MODEL,
        "temperature": 0,
        "response_format": {
            "type": "json_object"
        },
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(user_prompt, ensure_ascii=False),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45) as client:

        response = await client.post(
            f"{AIPIPE_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        raise AIError(response.text)

    body = response.json()

    try:
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)

    except Exception as e:
        raise AIError(f"Invalid AI response: {e}")
