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
    "compare", "vs", "better", "best",
    "which", "what", "why", "how",
    "top", "average", "roi", "investment"
]

def needs_ai(text: str) -> bool:
    return any(k in text for k in AI_KEYWORDS)

# ---------- AI HANDLER (STUB, SAFE) ----------
def ai_handle(message: str) -> str:
    return (
        "I can help with comparisons and investment questions.\n"
        "Please be specific.\n\n"
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

    # ---------- RULE 1: REFERENCE NUMBER ----------
    if re.fullmatch(r"\d{7}", msg):
        m = df[df["_key"] == msg]
        if not m.empty:
            return Response(
                json.dumps({"reply": m.iloc[0, 1]}, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- RULE 2: AI OVERRIDE ----------
    if needs_ai(msg):
        ai_reply = ai_handle(message)
        return Response(
            json.dumps({"reply": ai_reply}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- RULE 3: KEYWORD WINS ----------
    matches = df[df["_key"].apply(lambda k: k and k in msg)]

    if not matches.empty:
        return Response(
            json.dumps({"reply": matches.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- DEFAULT ----------
    return Response(json.dumps({"reply": ""}), media_type="application/json")
