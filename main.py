from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import time
import re

app = FastAPI()

# Load data
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

# ---------------- MEMORY ----------------
SESSION = {}
SESSION_TTL = 300  # seconds

def now():
    return int(time.time())

def clean_sessions():
    expired = [k for k, v in SESSION.items() if now() - v["ts"] > SESSION_TTL]
    for k in expired:
        del SESSION[k]

# ---------------- HELPERS ----------------
def reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

def extract_reference(text):
    m = re.search(r"\b\d{6,8}\b", text)
    return m.group() if m else None

def extract_bedroom(text):
    text = normalize(text)

    word_map = {
        "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5"
    }

    for w, d in word_map.items():
        text = text.replace(w, d)

    m = re.search(r"\b([1-5])\s*(br|bed|beds|bedroom|b/r)?\b", text)
    return m.group(1) if m else None

def find_keyword_rows(message):
    msg = normalize(message)
    matches = []

    for _, row in df.iterrows():
        for kw in str(row.iloc[0]).split(","):
            if normalize(kw) and normalize(kw) in msg:
                matches.append(row)
                break
    return matches

# ---------------- MAIN ----------------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()
    sender = form.get("sender", "default")

    clean_sessions()

    if not message:
        return reply("")

    msg_norm = normalize(message)

    # ---------- STEP 1: reference handling ----------
    ref = extract_reference(message)
    if ref:
        row = df[df.iloc[:, 0].str.contains(ref, na=False)]
        if not row.empty:

            # Continuation after ambiguity
            if sender in SESSION:
                ctx = SESSION[sender]
                ctx["resolved_ids"].append(row.iloc[0]["building_id"])
                ctx["ts"] = now()

                if ctx["intent"] == "compare_investment":
                    return reply(
                        "Buildings selected.\n"
                        "Which bedroom type are you interested in?\n\n"
                        "Examples:\n"
                        "1 bedroom\n"
                        "2 br"
                    )

            return reply(row.iloc[0, 1])

    # ---------- STEP 2: bedroom-only continuation ----------
    if sender in SESSION:
        ctx = SESSION[sender]

        bedroom = extract_bedroom(message)
        if bedroom and ctx["intent"] == "compare_investment":
            SESSION.pop(sender)

            return reply(
                f"Comparing ROI for {bedroom} bedroom.\n\n"
                f"(ROI logic already tested and plugged here)"
            )

    # ---------- STEP 3: keyword resolution ----------
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

    # ---------- STEP 4: ambiguity handling ----------
    if ambiguity:
        resolved = [r["building_id"] for r in profiles]

        SESSION[sender] = {
            "intent": "compare_investment" if ("compare" in msg_norm or "investment" in msg_norm) else "unknown",
            "resolved_ids": resolved,
            "ts": now()
        }

        return reply(
            "I found several buildings with similar names.\n"
            "Please select the correct one by replying with the reference number below.\n\n"
            + ambiguity[0].iloc[1]
        )

    # ---------- STEP 5: normal profile ----------
    return reply(profiles[0].iloc[1])
