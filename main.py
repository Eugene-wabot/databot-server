from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import pandas as pd
import re

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return JSONResponse({"reply": ""}, ensure_ascii=False)

    message_lower = message.lower()

    # ---------- STAGE 1: exact whole-word match ----------
    word_pattern = re.compile(rf"\b{re.escape(message_lower)}\b")

    exact_matches = df[
        df.iloc[:, 0]
        .str.lower()
        .apply(lambda x: isinstance(x, str) and bool(word_pattern.search(x)))
    ]

    if not exact_matches.empty:
        return JSONResponse(
            {"reply": exact_matches.iloc[0, 1]},
            ensure_ascii=False
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

    return JSONResponse(
        {"reply": reply_text},
        ensure_ascii=False
    )
