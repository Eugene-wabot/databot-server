from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

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

    # ---------- STAGE 1: exact whole-word match ----------
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

    # ---------- STAGE 2: fallback (legacy behavior) ----------
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

