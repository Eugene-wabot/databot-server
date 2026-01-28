from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import time
import re

app = FastAPI()

df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

SESSION = {}
SESSION_TTL = 300

# ---------- helpers ----------
def now():
    return int(time.time())

def reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

def clean_sessions():
    for k in list(SESSION.keys()):
        if now() - SESSION[k]["ts"] > SESSION_TTL:
            del SESSION[k]

def extract_reference(text):
    m = re.search(r"\b\d{6,8}\b", text)
    return m.group() if m else None

def extract_bedroom(text):
    text = normalize(text)
    text = text.replace("one", "1").replace("two", "2").replace("three", "3") \
               .replace("four", "4").replace("five", "5")
    m = re.search(r"\b([1-5])\s*(br|bed|beds|bedroom|b/r)?\b", text)
    return m.group(1) if m else None

def find_keyword_rows(message):
    msg = normalize(message)
    rows = []
    for _, r in df.iterrows():
        for kw in str(r.iloc[0]).split(","):
            if normalize(kw) and normalize(kw) in msg:
                rows.append(r)
                break
    return rows

# ---------- main ----------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()
    sender = form.get("sender", "default")

    clean_sessions()

    if not message:
        return reply("")

    msg_norm = normalize(message)

    # ---- reference reply (ambiguity continuation) ----
    ref = extract_reference(message)
    if ref:
        row = df[df.iloc[:, 0].str.contains(ref, na=False)]
        if not row.empty:
            if sender in SESSION:
                ctx = SESSION[sender]
                ctx["resolved_ids"].append(row.iloc[0]["building_id"])
                ctx["ts"] = now()

                if ctx["pending_ambiguities"]:
                    next_amb = ctx["pending_ambiguities"].pop(0)
                    return reply(
                        "Please select the next building by replying with its reference number:\n\n"
                        + next_amb.iloc[1]
                    )

                return reply(
                    "Buildings selected.\n"
                    "Which bedroom type are you interested in?\n\n"
                    "Examples:\n1 bedroom\n2 br"
                )

            return reply(row.iloc[0, 1])

    # ---- bedroom continuation ----
    if sender in SESSION:
        ctx = SESSION[sender]
        bedroom = extract_bedroom(message)
        if bedroom and not ctx["pending_ambiguities"]:
            SESSION.pop(sender)
            return reply(
                f"Comparing ROI for {bedroom} bedroom.\n\n"
                f"(ROI logic already plugged here)"
            )

    # ---- keyword resolution ----
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

    ambiguity = [r for r in matches if r["structural_type"] == "ambiguity_menu"]
    profiles = [r for r in matches if r["structural_type"] == "profile_menu"]

    # ---- dual ambiguity handling ----
    if ambiguity:
        SESSION[sender] = {
            "intent": "compare_investment" if ("compare" in msg_norm or "investment" in msg_norm) else "unknown",
            "resolved_ids": [r["building_id"] for r in profiles],
            "pending_ambiguities": ambiguity,
            "ts": now()
        }

        first = ambiguity[0]
        return reply(
            "I found multiple buildings with similar names.\n"
            "Please select the correct one by replying with the reference number below.\n\n"
            + first.iloc[1]
        )

    # ---- normal profile ----
    return reply(profiles[0].iloc[1])
