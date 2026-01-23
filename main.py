from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json
import os
from openai import OpenAI

app = FastAPI()

# ---------- LOAD DATA ----------
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# Column A = keywords / reference numbers
df["_key"] = df.iloc[:, 0].astype(str).str.lower()

# ---------- OPENAI ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AI_KEYWORDS = [
    "compare", "vs", "better", "best", "roi", "investment",
    "average", "highest", "lowest", "top"
]

def needs_ai(text: str) -> bool:
    return any(k in text for k in AI_KEYWORDS)

# ---------- AI (ISOLATED & SAFE) ----------
def ai_handle(message: str) -> str:
    # For now: DO NOT SELECT DATA
    # Only ask clarification or refuse invalid scope
    return (
        "I can help with comparisons and ROI questions.\n"
        "Please specify:\n"
        "- 2 buildings\n"
        "- bedroom type (Studio / 1 / 2 / 3)\n"
        "Example:\n"
        "Compare 25hours and Attareen ROI 1 bedroom"
    )

# ---------- ENDPOINT ----------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return Response(json.dumps({"reply": ""}), media_type="application/json")

    msg = message.lower()

    # ---------- STAGE 1: PURE REFERENCE NUMBER ----------
    if re.fullmatch(r"\d{7}", msg):
        m = df[df["_key"] == msg]
        if not m.empty:
            return Response(
                json.dumps({"reply": m.iloc[0, 1]}, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- STAGE 2: EXACT WHOLE-WORD MATCH ----------
    pattern = re.compile(rf"\b{re.escape(msg)}\b")

    exact = df[df["_key"].apply(lambda x: bool(pattern.search(x)))]
    if not exact.empty and not needs_ai(msg):
        return Response(
            json.dumps({"reply": exact.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- STAGE 3: LEGACY FALLBACK MATCH ----------
    fallback = df[
        df["_key"].apply(lambda x: x in msg or msg in x)
    ]

    # ---------- NORMAL MODE (NO AI) ----------
    if not fallback.empty and not needs_ai(msg):
        return Response(
            json.dumps({"reply": fallback.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- AI MODE (ONLY HERE) ----------
    if needs_ai(msg):
        ai_reply = ai_handle(message)
        return Response(
            json.dumps({"reply": ai_reply}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- FINAL FALLBACK ----------
    if not fallback.empty:
        return Response(
            json.dumps({"reply": fallback.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    return Response(json.dumps({"reply": ""}), media_type="application/json")
