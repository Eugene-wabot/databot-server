from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import os
from openai import OpenAI

app = FastAPI()

# ===============================
# LOAD EXCEL
# ===============================
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)
df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()

# ===============================
# OPENAI CLIENT
# ===============================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ===============================
# IN-MEMORY CONTEXT (PER SENDER)
# ===============================
user_context = {}  # phone -> context dict

def detect_intent_and_slots(message: str) -> dict:
    prompt = f"""
Extract intent and slots from the message.

Intent:
- compare
- none

Slots:
- buildings (list)
- bedroom (string or null)

Return STRICT JSON:
{{
  "intent": "...",
  "buildings": [],
  "bedroom": null
}}

Message:
"{message}"
"""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return json.loads(response.choices[0].message.content)


@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()
    phone = form.get("phone", "unknown")

    if not message:
        return Response(
            json.dumps({"reply": ""}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # Load or init context
    ctx = user_context.get(phone, {
        "mode": None,
        "buildings": [],
        "bedroom": None
    })

    # ===============================
    # AI PARSE
    # ===============================
    try:
        parsed = detect_intent_and_slots(message)
    except Exception:
        parsed = {"intent": "none", "buildings": [], "bedroom": None}

    # ===============================
    # START / CONTINUE COMPARE FLOW
    # ===============================
    if parsed["intent"] == "compare" or ctx["mode"] == "compare":
        ctx["mode"] = "compare"

        # Fill slots if provided
        if parsed["buildings"]:
            ctx["buildings"] = parsed["buildings"]
        if parsed["bedroom"]:
            ctx["bedroom"] = parsed["bedroom"]

        user_context[phone] = ctx

        # Ask for missing info
        if len(ctx["buildings"]) < 2:
            return Response(
                json.dumps({
                    "reply": "Please specify the two buildings you want to compare."
                }, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

        if not ctx["bedroom"]:
            return Response(
                json.dumps({
                    "reply": "Please specify the bedroom type (e.g. 1BR, 2BR, or overall)."
                }, ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

        # All required info collected (STOP HERE FOR NOW)
        reply_text = (
            f"Got it.\n"
            f"Comparison request:\n"
            f"- Buildings: {ctx['buildings'][0]} vs {ctx['buildings'][1]}\n"
            f"- Bedroom: {ctx['bedroom']}\n\n"
            f"Comparison logic will be applied next."
        )

        return Response(
            json.dumps({"reply": reply_text}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ===============================
    # DEFAULT — EXCEL NAVIGATION
    # ===============================
    message_clean = message.lower()

    exact = df[df.iloc[:, 0].str.lower() == message_clean]
    if len(exact) == 1:
        reply_text = exact.iloc[0, 1]
    else:
        fallback = df[df.iloc[:, 0].str.lower().str.contains(message_clean, na=False)]
        reply_text = fallback.iloc[0, 1] if not fallback.empty else ""

    return Response(
        json.dumps({"reply": reply_text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
