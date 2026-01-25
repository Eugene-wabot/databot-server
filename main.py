from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# ===============================
# Load Excel once
# ===============================
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# ===============================
# Helpers
# ===============================
def normalize(text: str) -> str:
    return (
        str(text)
        .replace("\u00a0", " ")
        .replace("\n", " ")
        .lower()
        .strip()
    )

def wa_reply(text: str) -> Response:
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

# ===============================
# Prepare keywords from Column A
# ===============================
rows = []

for _, row in df.iterrows():
    col_a = row.iloc[0]
    col_b = row.iloc[1]

    if not isinstance(col_a, str):
        continue

    # Column A is comma-separated keywords (authoritative)
    keywords = [
        normalize(k)
        for k in col_a.split(",")
        if normalize(k)
    ]

    rows.append({
        "keywords": keywords,
        "reply": col_b
    })

# ===============================
# AI intent detection (Layer 1)
# ===============================
AI_INTENT_KEYWORDS = [
    "compare", "vs", "versus",
    "better", "best",
    "which", "what", "why", "how",
    "roi", "investment", "yield", "average"
]

def ai_intent_detected(message: str) -> bool:
    return any(k in message for k in AI_INTENT_KEYWORDS)

# ===============================
# AI stub replies (NO metadata yet)
# ===============================
def ai_analysis_stub(message: str) -> str:
    return (
        "I can help with comparisons and investment analysis.\n\n"
        "To proceed, please specify:\n"
        "- exactly 2 buildings\n"
        "- bedroom type (Studio / 1 / 2 / 3)\n\n"
        "Example:\n"
        "Compare Burj Crown and 25hours ROI 1 bedroom"
    )

def ai_fallback_stub() -> str:
    return (
        "I didn’t find a specific building or reference number.\n\n"
        "You can try:\n"
        "- sending a building name (e.g. Burj Crown)\n"
        "- sending a reference number\n"
        "- asking to compare two buildings\n\n"
        "Example:\n"
        "Compare Burj Crown and 25hours"
    )

# ===============================
# Main endpoint
# ===============================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return wa_reply("")

    msg = normalize(message)

    # -------------------------------------------------
    # LAYER 1 — AI intent (OVERRIDES Layer 0)
    # -------------------------------------------------
    if ai_intent_detected(msg):
        return wa_reply(ai_analysis_stub(message))

    # -------------------------------------------------
    # LAYER 0 — Reference number anywhere in message
    # -------------------------------------------------
    ref_search = re.search(r"\b(\d{7})\b", msg)
    if ref_search:
        ref = ref_search.group(1)
        for row in rows:
            if ref in row["keywords"]:
                return wa_reply(row["reply"])

    # -------------------------------------------------
    # LAYER 0 — Keyword / phrase anywhere in message
    # -------------------------------------------------
    for row in rows:
        for kw in row["keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", msg):
                return wa_reply(row["reply"])

    # -------------------------------------------------
    # LAYER 1 — AI fallback helper
    # -------------------------------------------------
    return wa_reply(ai_fallback_stub())
