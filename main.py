from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json
import os
from openai import OpenAI

app = FastAPI()

# Load Excel once at startup (ORIGINAL)
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# ---------- OPENAI ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AI_KEYWORDS = [
    "compare", "vs", "better", "best",
    "which", "what", "why", "how",
    "top", "average", "roi", "investment"
]

def ai_should_intercept(message_lower: str) -> bool:
    return any(k in message_lower for k in AI_KEYWORDS)

def ai_reply_stub(message: str) -> str:
    # SAFE placeholder — no data access yet
    return (
        "I can help with comparisons and investment questions.\n"
        "Please be specific.\n\n"
        "Example:\n"
        "Compare 25hours and Attareen ROI 1 bedroom"
    )

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        payload = {"reply": ""}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    message_lower = message.lower()

    # =====================================================
    # === AI INTERCEPT (ONLY IF EXPLICITLY TRIGGERED) ===
    # =====================================================
    if ai_should_intercept(message_lower):
        payload = {"reply": ai_reply_stub(message)}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )
    # === END AI INTERCEPT ===

    # ---------- STAGE 1: exact whole-word match (ORIGINAL) ----------
    word_pattern = re.compile(rf"\b{re.escape(message_lower)}\b")

    exact_matches = df[
        df.iloc[:, 0]
        .str.lower()
        .apply(lambda x: isinstance(x, str) and bool(word_pattern.search(x)))
    ]

    if not exact_matches.empty:
        payload = {"reply": exact_matches.iloc[0, 1]}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- STAGE 2: fallback (ORIGINAL) ----------
    fallback_matches = df[
        df.iloc[:, 0].str.lower().str.contains(message_lower, na=False)
        |
        df.iloc[:, 0].apply(
            lambda x: isinstance(x, str) and x.lower() in message_lower
        )
    ]

    if not fallback_matches.empty:
        reply_text = fallback_matches.iloc[0, 1]
    else:
        reply_text = ""

    payload = {"reply": reply_text}
    return Response(
        json.dumps(payload, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
