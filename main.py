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

# Normalize helpers
def norm(x):
    if not isinstance(x, str):
        return ""
    return x.strip().lower()

df["_colA_norm"] = df.iloc[:, 0].astype(str).str.lower()

# ---------- OPENAI ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- AI INTENT CHECK ----------
ANALYTICAL_KEYWORDS = [
    "compare", "better", "best", "roi", "investment",
    "average", "highest", "lowest", "top"
]

def needs_ai(message_lower: str) -> bool:
    return any(k in message_lower for k in ANALYTICAL_KEYWORDS)

# ---------- AI HANDLER ----------
def ai_handle(message: str) -> str:
    """
    AI decides what to do.
    It must return either:
    - clarification text
    - or concatenated Column B reports
    """
    prompt = f"""
You are a strict controller for a real estate WhatsApp bot.

Rules:
- Do NOT invent data
- Do NOT summarize reports
- Use metadata only
- ROI requires bedroom_type
- Max 2 buildings for comparison

User message:
"{message}"

Reply with JSON only:
{{"action":"clarify","text":"..."}}
OR
{{"action":"reports","rows":[ROW_INDEXES]}}

ROW_INDEXES are integer indexes from the dataframe.
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except Exception:
        return ""

    if data.get("action") == "clarify":
        return data.get("text", "")

    if data.get("action") == "reports":
        texts = []
        for idx in data.get("rows", []):
            try:
                texts.append(df.iloc[int(idx), 1])
            except Exception:
                pass
        return "\n\n".join(texts)

    return ""

# ---------- ENDPOINT ----------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return Response(json.dumps({"reply": ""}), media_type="application/json")

    message_lower = message.lower()

    # ---------- STAGE 1: REFERENCE NUMBER ----------
    if re.fullmatch(r"\d{7}", message):
        match = df[df["_colA_norm"] == message]
        if not match.empty:
            return Response(
                json.dumps({"reply": match.iloc[0, 1]}, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- STAGE 2: FAST KEYWORD MATCH ----------
    fallback_matches = df[
        df["_colA_norm"].str.contains(message_lower, na=False)
        |
        df["_colA_norm"].apply(lambda x: x in message_lower)
    ]

    if not fallback_matches.empty and not needs_ai(message_lower):
        return Response(
            json.dumps({"reply": fallback_matches.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- STAGE 3: AI ----------
    ai_reply = ai_handle(message)
    return Response(
        json.dumps({"reply": ai_reply}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
