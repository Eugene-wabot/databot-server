from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import time
import re

app = FastAPI()

# Load data
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

# In-memory session store (Phase 1 only)
SESSION = {}
SESSION_TTL = 300  # seconds

def now():
    return int(time.time())

def clean_sessions():
    expired = [k for k, v in SESSION.items() if now() - v["ts"] > SESSION_TTL]
    for k in expired:
        del SESSION[k]

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

def extract_reference(text):
    m = re.search(r"\b\d{6,8}\b", text)
    return m.group() if m else None

def find_keyword_rows(message):
    msg = normalize(message)
    matches = []
    for _, row in df.iterrows():
        for kw in str(row.iloc[0]).split(","):
            if normalize(kw) and normalize(kw) in msg:
                matches.append(row)
                break
    return matches

def reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()
    sender = form.get("sender", "default")

    clean_sessions()

    if not message:
        return reply("")

    msg_norm = normalize(message)

    # ---- STEP 1: reference number handling (continuation-aware) ----
    ref = extract_reference(message)
    if ref:
        row = df[df.iloc[:, 0].str.contains(ref, na=False)]
        if not row.empty:
            # Check for continuation memory
            if sender in SESSION:
                ctx = SESSION.pop(sender)
                resolved_ids = ctx["resolved_ids"] + [row.iloc[0]["building_id"]]
                intent = ctx["intent"]

                if intent == "compare_investment":
                    return reply(
                        f"Buildings selected.\n"
                        f"Now specify bedroom type (Studio / 1 / 2 / 3).\n\n"
                        f"Example:\nCompare ROI 1 bedroom"
                    )

            return reply(row.iloc[0, 1])

    # ---- STEP 2: keyword resolution ----
    matches = find_keyword_rows(message)

    if not matches:
        return reply(
            "I didn’t find a specific building or reference number.\n\n"
            "You can try:\n"
            "- sending a building name\n"
            "- sending a reference number\n"
            "- asking to compare two buildings\n\n"
            "Example:\nCompare Burj Crown and 25hours"
        )

    # Separate by structural type
    ambiguity = [r for r in matches if r["structural_type"] == "ambiguity_menu"]
    profiles = [r for r in matches if r["structural_type"] == "profile_menu"]

    # ---- STEP 3: ambiguity handling with memory ----
    if ambiguity:
        resolved = [r["building_id"] for r in profiles]

        SESSION[sender] = {
            "intent": "compare_investment" if "compare" in msg_norm or "investment" in msg_norm else "unknown",
            "resolved_ids": resolved,
            "ts": now()
        }

        return reply(ambiguity[0].iloc[1])

    # ---- STEP 4: normal profile menu ----
    return reply(profiles[0].iloc[1])
