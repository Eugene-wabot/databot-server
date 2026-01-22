from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import os
from openai import OpenAI

app = FastAPI()

# ===============================
# LOAD EXCEL (NAVIGATION ENGINE)
# ===============================
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)
df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()

# ===============================
# OPENAI CLIENT (INTERPRETER ONLY)
# ===============================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_intent(message: str) -> str:
    """
    Detect ONLY high-level intent.
    Returns: compare | explain | how_it_works | none
    """
    prompt = f"""
Classify the user's message into ONE of the following intents:
- compare
- explain
- how_it_works
- none

Return ONLY the intent word, nothing else.

User message:
"{message}"
"""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return only one word."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip().lower()


# ===============================
# WHATSAPP ENDPOINT
# ===============================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return Response(
            json.dumps({"reply": ""}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ===============================
    # STEP 2.1 — INTENT INTERCEPTOR
    # ===============================
    try:
        intent = detect_intent(message)
        print("AI INTENT:", intent)
    except Exception as e:
        print("AI ERROR:", e)
        intent = "none"

    # ---- INTERCEPT ADVANCED INTENTS ----
    if intent == "compare":
        reply_text = (
            "I can help compare buildings.\n"
            "Please specify the bedroom type (e.g. 1BR, 2BR, or overall)."
        )
        return Response(
            json.dumps({"reply": reply_text}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    if intent == "explain":
        reply_text = (
            "I can explain reports, ROI, or how to read the data.\n"
            "Please tell me what you’d like explained."
        )
        return Response(
            json.dumps({"reply": reply_text}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    if intent == "how_it_works":
        reply_text = (
            "This system uses reference numbers to navigate.\n"
            "Copy and paste any reference number to continue."
        )
        return Response(
            json.dumps({"reply": reply_text}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ===============================
    # DEFAULT — EXCEL NAVIGATION
    # ===============================
    message_clean = message.lower()

    exact_match = df[df.iloc[:, 0].str.lower() == message_clean]

    if len(exact_match) == 1:
        reply_text = exact_match.iloc[0, 1]
    else:
        fallback = df[
            df.iloc[:, 0].str.lower().str.contains(message_clean, na=False)
        ]
        reply_text = fallback.iloc[0, 1] if not fallback.empty else ""

    return Response(
        json.dumps({"reply": reply_text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
