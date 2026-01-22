from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json
import os
from openai import OpenAI

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_intent(message: str) -> dict:
    """
    AI intent classifier.
    Returns JSON only. No user-facing text.
    """
    prompt = f"""
You are an intent classifier for a real-estate WhatsApp bot.

Classify the user's message into ONE of these intents:
- lookup (asking about one building / reference)
- compare (asking to compare two or more buildings)
- help (asking how to use the bot)
- unknown

Extract building names or references if present.

Return STRICT JSON only in this format:
{{
  "intent": "...",
  "entities": []
}}

User message:
\"{message}\"
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You return JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return json.loads(response.choices[0].message.content)

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return Response(
            json.dumps({"reply": ""}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # 🔍 AI intent detection (currently passive)
    try:
        intent_data = detect_intent(message)
        print("AI INTENT:", intent_data)
    except Exception as e:
        print("AI ERROR:", e)

    # ---- EXISTING DATABOT LOGIC (unchanged) ----

    message_lower = message.lower()

    word_pattern = re.compile(rf"\b{re.escape(message_lower)}\b")

    exact_matches = df[
        df.iloc[:, 0]
        .str.lower()
        .apply(lambda x: isinstance(x, str) and bool(word_pattern.search(x)))
    ]

    if not exact_matches.empty:
        reply_text = exact_matches.iloc[0, 1]
    else:
        fallback_matches = df[
            df.iloc[:, 0].str.lower().str.contains(message_lower, na=False)
            |
            df.iloc[:, 0].apply(
                lambda x: isinstance(x, str) and x.lower() in message_lower
            )
        ]
        reply_text = fallback_matches.iloc[0, 1] if not fallback_matches.empty else ""

    return Response(
        json.dumps({"reply": reply_text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
