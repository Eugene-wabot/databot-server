from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import re

app = FastAPI()

# =========================
# Load Excel (column-safe)
# =========================
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

# Column positions (IMPORTANT)
COL_KEYWORD = 0      # Column A
COL_REPLY = 1        # Column B
COL_STRUCT = df.columns.get_loc("structural_type")

# =========================
# In-memory sessions
# =========================
SESSIONS = {}

def get_session(uid):
    if uid not in SESSIONS:
        SESSIONS[uid] = {
            "pending_ambiguities": [],
            "resolved_refs": [],
            "awaiting_bedroom": False
        }
    return SESSIONS[uid]

def reset_session(uid):
    SESSIONS[uid] = {
        "pending_ambiguities": [],
        "resolved_refs": [],
        "awaiting_bedroom": False
    }

def reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

# =========================
# Helpers
# =========================
def extract_bedroom(text):
    text = text.lower()
    patterns = {
        "studio": r"\bstudio\b",
        "1": r"\b1\s*(br|bed|bedroom|b/r)?\b",
        "2": r"\b2\s*(br|bed|bedroom|b/r)?\b",
        "3": r"\b3\s*(br|bed|bedroom|b/r)?\b",
        "4": r"\b4\s*(br|bed|bedroom|b/r)?\b",
    }
    for k, p in patterns.items():
        if re.search(p, text):
            return k
    return None

def find_matching_rows(message):
    msg = message.lower()
    rows = []

    for _, row in df.iterrows():
        keywords = [k.strip().lower() for k in row.iloc[COL_KEYWORD].split(",")]
        for kw in keywords:
            if kw and kw in msg:
                rows.append(row)
                break
    return rows

def build_ambiguity_queue(rows):
    queue = []
    seen = set()

    for r in rows:
        if r.iloc[COL_STRUCT] == "ambiguity_menu":
            key = r.iloc[COL_KEYWORD]
            if key not in seen:
                queue.append({
                    "menu": r.iloc[COL_REPLY],
                    "refs": extract_refs(r.iloc[COL_REPLY])
                })
                seen.add(key)
    return queue

def extract_refs(text):
    return re.findall(r"\b\d{7}\b", text)

def find_row_by_ref(ref):
    for _, r in df.iterrows():
        if ref == r.iloc[COL_KEYWORD].strip():
            return r
    return None

# =========================
# Endpoint
# =========================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    msg = form.get("message", "").strip()
    uid = form.get("from", "default")

    if not msg:
        return reply("")

    session = get_session(uid)

    # =========================
    # 1️⃣ Ambiguity resolution
    # =========================
    if msg.isdigit() and session["pending_ambiguities"]:
        active = session["pending_ambiguities"][0]

        if msg not in active["refs"]:
            return reply("Please reply with one of the listed reference numbers.")

        session["resolved_refs"].append(msg)
        session["pending_ambiguities"].pop(0)

        if session["pending_ambiguities"]:
            return reply(
                "Please select the next building by replying with the reference number below:\n\n"
                + session["pending_ambiguities"][0]["menu"]
            )

        session["awaiting_bedroom"] = True
        return reply(
            "Buildings selected.\nWhich bedroom type are you interested in?\n\n"
            "Examples:\n1 bedroom\n2 br"
        )

    # =========================
    # 2️⃣ Bedroom follow-up
    # =========================
    if session["awaiting_bedroom"]:
        bed = extract_bedroom(msg)
        if not bed:
            return reply("Please specify bedroom type (Studio / 1 / 2 / 3).")

        reset_session(uid)
        return reply(f"Comparing ROI for {bed} bedroom.\n\n(ROI logic already plugged here)")

    # =========================
    # 3️⃣ Fresh message
    # =========================
    matched = find_matching_rows(msg)

    if not matched:
        return reply(
            "I didn’t find a specific building or reference number.\n\n"
            "You can try:\n"
            "- sending a building name\n"
            "- sending a reference number\n"
            "- asking to compare two buildings"
        )

    ambiguity_queue = build_ambiguity_queue(matched)

    if ambiguity_queue:
        session["pending_ambiguities"] = ambiguity_queue
        return reply(
            "I found several buildings with similar names.\n"
            "Please select the correct one by replying with the reference number below.\n\n"
            + ambiguity_queue[0]["menu"]
        )

    # =========================
    # 4️⃣ Direct hit
    # =========================
    reset_session(uid)
    return reply(matched[0].iloc[COL_REPLY])
