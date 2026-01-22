from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import os
from openai import OpenAI
import re

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
# IN-MEMORY CONTEXT
# ===============================
user_context = {}

def detect_intent_and_slots(message: str) -> dict:
    prompt = f"""
Extract intent and slots.

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
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return json.loads(r.choices[0].message.content)


def find_report(building: str, bedroom: str) -> str:
    building = building.lower().strip()
    bedroom_num = re.sub(r"[^\d]", "", bedroom)

    # 1) Find building profile
    profile = df[df.iloc[:, 0].str.lower() == building]
    if profile.empty:
        return ""

    text = profile.iloc[0, 1]
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    in_block = False

    for line in lines:
        l = line.lower()

        # Enter correct bedroom block
        if re.search(rf"\*{bedroom_num}\s*b/r\*", l):
            in_block = True
            continue

        # Exit when next bedroom header appears
        if in_block and re.search(r"\*\d+\s*b/r\*", l):
            break

        # Inside block → find Sales reference
        if in_block and "sales" in l:
            for token in line.split():
                if token.isdigit() and len(token) == 7:
                    report = df[df.iloc[:, 0] == token]
                    if not report.empty:
                        return report.iloc[0, 1]

    return ""


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

    ctx = user_context.get(phone, {
        "mode": None,
        "buildings": [],
        "bedroom": None
    })

    try:
        parsed = detect_intent_and_slots(message)
    except Exception:
        parsed = {"intent": "none", "buildings": [], "bedroom": None}

    # ===============================
    # COMPARE FLOW
    # ===============================
    if parsed["intent"] == "compare" or ctx["mode"] == "compare":
        ctx["mode"] = "compare"

        if parsed["buildings"]:
            ctx["buildings"] = parsed["buildings"]
        if parsed["bedroom"]:
            ctx["bedroom"] = parsed["bedroom"]

        user_context[phone] = ctx

        if len(ctx["buildings"]) < 2:
            return Response(
                json.dumps({"reply": "Please specify the two buildings to compare."},
                           ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

        if not ctx["bedroom"]:
            return Response(
                json.dumps({"reply": "Please specify the bedroom type (e.g. 1BR, 2BR, or overall)."},
                           ensure_ascii=False),
                media_type="application/json; charset=utf-8"
            )

        # ===============================
        # STEP 2.3 — EXECUTE
        # ===============================
        b1, b2 = ctx["buildings"][:2]
        bedroom = ctx["bedroom"]

        r1 = find_report(b1, bedroom)
        r2 = find_report(b2, bedroom)

        reply_text = (
            f"Below is a side-by-side view for *{bedroom}* apartments.\n"
            f"Data is shown as reported, without modification.\n\n"
            f"*{b1.upper()}*\n{r1}\n\n"
            f"*{b2.upper()}*\n{r2}"
        )

        user_context.pop(phone, None)

        return Response(
            json.dumps({"reply": reply_text}, ensure_ascii=False),
            media_type="application/json; charset=utf-8"
        )

    # ===============================
    # DEFAULT — EXCEL NAVIGATION
    # ===============================
    msg = message.lower()

    exact = df[df.iloc[:, 0].str.lower() == msg]
    if len(exact) == 1:
        reply_text = exact.iloc[0, 1]
    else:
        fallback = df[df.iloc[:, 0].str.lower().str.contains(msg, na=False)]
        reply_text = fallback.iloc[0, 1] if not fallback.empty else ""

    return Response(
        json.dumps({"reply": reply_text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )
