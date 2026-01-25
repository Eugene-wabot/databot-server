from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# ---------------- Utilities ----------------
def normalize(t):
    return (
        str(t)
        .replace("\u00a0", " ")
        .replace("\n", " ")
        .lower()
        .strip()
    )

def reply(text):
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

# ---------------- Preload Layer 0 keyword rows ----------------
KEYWORD_ROWS = []
for _, row in df.iterrows():
    if not isinstance(row.get("key_word"), str):
        continue
    keywords = [normalize(k) for k in row["key_word"].split(",") if normalize(k)]
    KEYWORD_ROWS.append({
        "keywords": keywords,
        "reply": row["report"],
        "building_id": row.get("building_id"),
        "structural_type": row.get("structural_type")
    })

# ---------------- AI intent detection ----------------
AI_INTENT_WORDS = [
    "compare", "vs", "versus",
    "better", "best",
    "roi", "investment", "yield"
]

def is_ai_intent(msg):
    return any(w in msg for w in AI_INTENT_WORDS)

# ---------------- Bedroom extraction ----------------
def extract_bedroom(msg):
    msg = msg.lower()

    if "studio" in msg:
        return "studio"

    patterns = {
        "1": [r"\b1\s*br\b", r"\b1\s*bed", r"\bone\b"],
        "2": [r"\b2\s*br\b", r"\b2\s*bed", r"\btwo\b"],
        "3": [r"\b3\s*br\b", r"\b3\s*bed", r"\bthree\b"],
        "4": [r"\b4\s*br\b", r"\b4\s*bed", r"\bfour\b"],
    }

    for b, pats in patterns.items():
        for p in pats:
            if re.search(p, msg):
                return b
    return None

# ---------------- Layer 2: ROI comparison ----------------
def compare_roi(building_ids, bedroom):
    bedroom = str(bedroom).lower().strip()

    subset = df[
        (df["building_id"].isin(building_ids)) &
        (df["bedroom_type"].astype(str).str.lower().str.strip() == bedroom) &
        (df["Gross_roi"].notna())
    ]

    if len(subset) != 2:
        return None

    a, b = subset.iloc[0], subset.iloc[1]

    roi_a, roi_b = float(a["Gross_roi"]), float(b["Gross_roi"])
    rent_a, rent_b = a["Median_rent"], b["Median_rent"]

    winner = a if roi_a > roi_b else b

    return (
        f"{a['building_name']} ({bedroom}BR): ROI {roi_a:.2f}%, "
        f"Median rent {rent_a}\n"
        f"{b['building_name']} ({bedroom}BR): ROI {roi_b:.2f}%, "
        f"Median rent {rent_b}\n\n"
        f"{winner['building_name']} offers better investment returns "
        f"primarily due to stronger rental performance."
    )

# ---------------- Main endpoint ----------------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return reply("")

    msg = normalize(message)

    # ==================================================
    # LAYER 2 — AI / ANALYTICAL REQUESTS (FIRST)
    # ==================================================
    if is_ai_intent(msg):
        bedroom = extract_bedroom(msg)

        matched_ids = set()
        menu_rows = df[df["structural_type"] == "menu"]

        for _, row in menu_rows.iterrows():
            keywords = [normalize(k) for k in row["key_word"].split(",") if normalize(k)]
            if any(k in msg for k in keywords):
                matched_ids.add(row["building_id"])

        if len(matched_ids) == 2 and bedroom:
            result = compare_roi(list(matched_ids), bedroom)
            if result:
                return reply(result)
            else:
                return reply(
                    "I found both buildings, but ROI data for this bedroom "
                    "is missing or inconsistent."
                )

        return reply(
            "To analyze investment or ROI, please specify:\n"
            "- exactly 2 buildings\n"
            "- bedroom type\n\n"
            "Example:\n"
            "Compare Burj Crown and DT1 ROI 1 bedroom"
        )

    # ==================================================
    # LAYER 0 — ORIGINAL DATABOT BEHAVIOR
    # ==================================================

    # --- Reference number ---
    ref = re.search(r"\b\d{7}\b", msg)
    if ref:
        for r in KEYWORD_ROWS:
            if ref.group() in r["keywords"]:
                return reply(r["reply"])

    # --- Keyword match anywhere ---
    for r in KEYWORD_ROWS:
        for kw in r["keywords"]:
            if kw in msg:
                return reply(r["reply"])

    # ==================================================
    # FALLBACK
    # ==================================================
    return reply(
        "I didn’t find a specific building or reference number.\n\n"
        "You can try:\n"
        "- sending a building name\n"
        "- sending a reference number\n"
        "- asking to compare two buildings"
    )
