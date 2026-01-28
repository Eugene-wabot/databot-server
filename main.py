from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import time
import re

app = FastAPI()

df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

# ---------------- MEMORY ----------------
SESSION = {}
SESSION_TTL = 300

def now():
    return int(time.time())

def clean_sessions():
    for k in list(SESSION.keys()):
        if now() - SESSION[k]["ts"] > SESSION_TTL:
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

    # ---------- STEP 1: reference continuation ----------
    ref = extract_reference(message)
    if ref:
        row = df[df.iloc[:, 0].str.contains(ref, na=False)]
        if not row.empty:
            selected_building_id = row.iloc[0]["building_id"]

            if sender in SESSION:
                ctx = SESSION[sender]

                # mark ambiguity resolved
                for amb in ctx["pending_ambiguities"]:
                    if amb["building_id"] == selected_building_id:
                        amb["resolved"] = True
                        ctx["resolved_ids"].append(selected_building_id)
                        ctx["ts"] = now()
                        break

                # find next unresolved ambiguity
                for amb in ctx["pending_ambiguities"]:
                    if not amb["resolved"]:
                        return reply(
                            "Please select the next building by replying with the reference number below:\n\n"
                            + amb["menu_text"]
                        )

                # all ambiguities resolved
                return reply(
                    "Buildings selected.\n"
                    "Which bedroom type are you interested in?\n\n"
                    "Examples:\n1 bedroom\n2 br"
                )

            return reply(row.iloc[0, 1])

    # ---------- STEP 2: bedroom continuation ----------
    if sender in SESSION:
        ctx = SESSION[sender]
        bedroom = extract_bedroom(message)

        if bedroom and all(a["resolved"] for a in ctx["pending_ambiguities"]):
            SESSION.pop(sender)
            return reply(
                f"Comparing ROI for {bedroom} bedroom.\n\n"
                "(ROI logic already plugged here)"
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

    # group by building_id
    buildings = {}
    for r in matches:
        bid = r["building_id"]
        buildings.setdefault(bid, []).append(r)

    resolved_ids = []
    pending_ambiguities = []

    for bid, rows in buildings.items():
        amb_row = next((r for r in rows if r["structural_type"] == "ambiguity_menu"), None)
        prof_row = next((r for r in rows if r["structural_type"] == "profile_menu"), None)

        if amb_row:
            pending_ambiguities.append({
                "building_id": bid,
                "menu_text": amb_row.iloc[1],
                "resolved": False
            })
        elif prof_row:
            resolved_ids.append(bid)

    if pending_ambiguities:
        SESSION[sender] = {
            "intent": "compare_investment" if ("compare" in msg_norm or "investment" in msg_norm) else "unknown",
            "resolved_ids": resolved_ids,
            "pending_ambiguities": pending_ambiguities,
            "ts": now()
        }

        first = pending_ambiguities[0]
        return reply(
            "I found several buildings with similar names.\n"
            "Please select the correct one by replying with the reference number below.\n\n"
            + first["menu_text"]
        )

    # ---------- STEP 4: normal profile ----------
    return reply(matches[0].iloc[1])
