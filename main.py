from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import json
import re

app = FastAPI()

# =========================
# Load data
# =========================
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str).fillna("")

# =========================
# In-memory session store
# =========================
SESSIONS = {}

def get_session(user_id):
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {
            "pending_ambiguities": [],
            "resolved_buildings": [],
            "awaiting_bedroom": False
        }
    return SESSIONS[user_id]

def reset_session(user_id):
    SESSIONS[user_id] = {
        "pending_ambiguities": [],
        "resolved_buildings": [],
        "awaiting_bedroom": False
    }

# =========================
# Helpers
# =========================
def json_reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

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

def find_keyword_rows(message):
    message = message.lower()
    matches = []
    for _, row in df.iterrows():
        keywords = [k.strip().lower() for k in row["keyword"].split(",")]
        for kw in keywords:
            if kw and kw in message:
                matches.append(row)
                break
    return matches

def build_ambiguity_queue(rows):
    queue = []
    seen = set()
    for r in rows:
        if r["structural_type"] == "ambiguity_menu":
            key = r["keyword"]
            if key not in seen:
                queue.append({
                    "keyword": key,
                    "menu_text": r["reply"]
                })
                seen.add(key)
    return queue

def find_row_by_ref(ref):
    match = df[df["keyword"].str.strip() == ref]
    return None if match.empty else match.iloc[0]

# =========================
# Endpoint
# =========================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()
    user_id = form.get("from", "default")

    if not message:
        return json_reply("")

    session = get_session(user_id)

    # =========================
    # STEP 1 — Reference reply (ambiguity resolution)
    # =========================
    if message.isdigit() and session["pending_ambiguities"]:
        active = session["pending_ambiguities"][0]
        if message not in active["menu_text"]:
            return json_reply("Please reply with one of the listed reference numbers.")

        row = find_row_by_ref(message)
        if not row:
            return json_reply("Invalid reference number.")

        session["resolved_buildings"].append(row)
        session["pending_ambiguities"].pop(0)

        if session["pending_ambiguities"]:
            next_menu = session["pending_ambiguities"][0]["menu_text"]
            return json_reply(
                "Please select the next building by replying with the reference number below:\n\n"
                + next_menu
            )

        session["awaiting_bedroom"] = True
        return json_reply(
            "Buildings selected.\nWhich bedroom type are you interested in?\n\nExamples:\n1 bedroom\n2 br"
        )

    # =========================
    # STEP 2 — Bedroom reply
    # =========================
    if session["awaiting_bedroom"]:
        bedroom = extract_bedroom(message)
        if not bedroom:
            return json_reply("Please specify bedroom type (Studio / 1 / 2 / 3).")

        # ROI logic placeholder (already implemented in your version)
        reset_session(user_id)
        return json_reply(f"Comparing ROI for {bedroom} bedroom.\n\n(ROI logic already plugged here)")

    # =========================
    # STEP 3 — Fresh message (no memory)
    # =========================
    matched_rows = find_keyword_rows(message)

    if not matched_rows:
        return json_reply(
            "I didn’t find a specific building or reference number.\n\n"
            "You can try:\n"
            "- sending a building name\n"
            "- sending a reference number\n"
            "- asking to compare two buildings"
        )

    ambiguity_queue = build_ambiguity_queue(matched_rows)

    if ambiguity_queue:
        session["pending_ambiguities"] = ambiguity_queue
        first = ambiguity_queue[0]["menu_text"]
        return json_reply(
            "I found several buildings with similar names.\n"
            "Please select the correct one by replying with the reference number below.\n\n"
            + first
        )

    # =========================
    # STEP 4 — Direct match (profile / report)
    # =========================
    row = matched_rows[0]
    reset_session(user_id)
    return json_reply(row["reply"])
