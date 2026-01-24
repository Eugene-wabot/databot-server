from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# ---------- LOAD & NORMALIZE DATA ----------
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

def normalize(text: str) -> str:
    return (
        text.replace("\u00a0", " ")
            .strip()
            .lower()
    )

# Normalize Column A ONCE
df["_key"] = (
    df.iloc[:, 0]
      .astype(str)
      .apply(lambda x: normalize(x.replace(".0", "")))
)

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "")

    if not message:
        payload = {"reply": ""}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    message_norm = normalize(message)

    # ---------- STAGE 1: exact reference number ----------
    if re.fullmatch(r"\d{7}", message_norm):
        ref_match = df[df["_key"] == message_norm]
        if not ref_match.empty:
            payload = {"reply": ref_match.iloc[0, 1]}
            return Response(
                json.dumps(payload, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- STAGE 2: keyword anywhere in message ----------
    keyword_matches = df[
        df["_key"].apply(lambda k: k and k in message_norm)
    ]

    if not keyword_matches.empty:
        payload = {"reply": keyword_matches.iloc[0, 1]}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- NO MATCH ----------
    payload = {"reply": "Please rephrase, I didn’t find anything."}
    return Response(
        json.dumps(payload, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
