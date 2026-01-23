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

# normalize Column A (keywords / refs)
df["_colA_norm"] = df.iloc[:, 0].astype(str).str.lower()

# ---------- OPENAI ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ANALYTICAL_KEYWORDS = [
    "compare", "better", "best", "roi", "investment",
    "average", "highest", "lowest", "top"
]

def needs_ai(message_lower: str) -> bool:
    return any(k in message_lower for k in ANALYTICAL_KEYWORDS)

# ---------- AI HANDLER ----------
def ai_handle(message: str) -> str:
    prompt = f"""
You are a strict controller for a real estate WhatsApp bot.

Rules:
- Use metadata only
- Do NOT invent data
- Do NOT rewrite reports
- ROI requires bedroom_type
- Max 2 buildings

User message:
"{message}"

Reply ONLY in JSON:
{{"action":"clarify","text":"..."}}
OR
{{"action":"reports","rows":[ROW_INDEXES]}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        return ""

    if data.get("action") == "clarify":
        return data.get("text", "")

    if data.get("action") == "reports":
        out = []
        for idx in data.get("rows", []):
            try:
                out.append(df.iloc[int(idx), 1])
            except Exception:
                pass
        return "\n\n".join(out)

    return ""

# ---------- ENDPOINT ----------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return Response(
            json.dumps({"reply": ""}),
            media_type="application/json; charset=utf-8"
        )

    message_lower = message.lower()

    # ---------- STAGE 1: PURE REFERENCE NUMBER ----------
    if re.fullmatch(r"\d{7}", message):
        match = df[df["_colA_norm"] == message]
        if not match.empty:
            return Response(
                json.dumps({"reply": match.iloc[0, 1]}, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

    # ---------- STAGE 2: EXACT WHOLE-WORD MATCH (RESTORED) ----------
    word_pattern = re.compile(rf"\b{re.escape(message_lower)}\b")

    exact_matches = df[
        df["_colA_norm"].apply(
            lambda x: isinstance(x, str) and bool(word_pattern.search(x))
        )
    ]

    if not exact_matches.empty:
        return Response(
            json.dumps({"reply": exact_matches.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- STAGE 3: LEGACY FALLBACK MATCH ----------
    fallback_matches = df[
        df["_colA_norm"].apply(
            lambda x: isinstance(x, str) and (
                x in message_lower or message_lower in x
            )
        )
    ]

    # ---------- FAST PATH (NO AI) ----------
    if not fallback_matches.empty and not needs_ai(message_lower):
        return Response(
            json.dumps({"reply": fallback_matches.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- AI PATH ----------
    if needs_ai(message_lower):
        ai_reply = ai_handle(message)
        return Response(
            json.dumps({"reply": ai_reply}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ---------- FINAL FALLBACK ----------
    if not fallback_matches.empty:
        return Response(
            json.dumps({"reply": fallback_matches.iloc[0, 1]}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    return Response(
        json.dumps({"reply": ""}),
        media_type="application/json; charset=utf-8"
    )
