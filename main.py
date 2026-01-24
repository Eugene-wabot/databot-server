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

    # ---------- STAGE 1: exact reference number (7 digits) ----------
    if re.fullmatch(r"\d{7}", message_lower):
        ref_match = df[df.iloc[:, 0].str.lower() == message_lower]
        if not ref_match.empty:
            payload = {"reply": ref_match.iloc[0, 1]}
            return Response(
                json.dumps(payload, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- STAGE 2: keyword anywhere in message ----------
    keyword_matches = df[
        df.iloc[:, 0]
          .str.lower()
          .apply(lambda k: isinstance(k, str) and k in message_lower)
    ]

    if not keyword_matches.empty:
        payload = {"reply": keyword_matches.iloc[0, 1]}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- STAGE 3: explicit no-match reply ----------
    payload = {"reply": "Please rephrase, I didn’t find anything."}
    return Response(
        json.dumps(payload, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
