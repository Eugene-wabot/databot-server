from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# ================= LOAD DATA =================
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# ================= HELPERS =================
def normalize(text):
    return (
        str(text)
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

def parse_percent(val):
    if not val:
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except:
        return None

# ================= PRELOAD KEYWORDS (LAYER 0) =================
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

# ================= AI INTENT =================
AI_INTENT_WORDS = [
    "compare", "vs", "versus",
    "roi", "investment", "yield",
    "better", "best", "good investment"
]

def is_ai_intent(msg):
    return any(w in msg for w in AI_INTENT_WORDS)

# ================= BEDROOM EXTRACTION =================
def extract_bedroom(msg):
    msg = msg.lower()

    if "studio" in msg:
        return "studio"

    patterns = {
        "1": [r"\b1\s*br\b", r"\b1\s*bed\b", r"\bone\b"],
        "2": [r"\b2\s*br\b", r"\b2\s*bed\b", r"\btwo\b"],
        "3": [r"\b3\s*br\b", r"\b3\s*bed\b", r"\bthree\b"],
        "4": [r"\b4\s*br\b", r"\b4\s*bed\b", r"\bfour\b"],
    }

    for b, pats in patterns.items():
        for p in pats:
            if re.search(p, msg):
                return b
    return None

# ================= ROI FETCH =================
def get_roi_rows(building_ids, bedroom):
    return df[
        (df["building_id"].isin(building_ids)) &
        (df["bedroom_type"].astype(str).str.lower() == bedroom) &
        (df["Gross_roi"].notna()) &
        (df["structural_type"] == "report")
    ]

# ================= MAIN ENDPOINT =================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()
    if not message:
        return reply("")

    msg = normalize(message)

    # ==========================================================
    # LAYER 2 — AI LOGIC
    # ==========================================================
    if is_ai_intent(msg):
        bedroom = extract_bedroom(msg)

        matched_ids = set()
        menu_rows = df[df["structural_type"] == "menu"]

        for _, row in menu_rows.iterrows():
            kws = [normalize(k) for k in row["key_word"].split(",") if normalize(k)]
            if any(k in msg for k in kws):
                matched_ids.add(row["building_id"])

        # -------- COMPARISON (Layer 2.1) --------
        if len(matched_ids) == 2 and bedroom:
            subset = get_roi_rows(list(matched_ids), bedroom)
            if len(subset) != 2:
                return reply("ROI data is unavailable for this comparison.")

            a, b = subset.iloc[0], subset.iloc[1]
            roi_a, roi_b = parse_percent(a["Gross_roi"]), parse_percent(b["Gross_roi"])

            if roi_a is None or roi_b is None:
                return reply("ROI data is unavailable for this comparison.")

            analysis = (
                f"{a['building_name']} ({bedroom}BR): ROI {roi_a:.2f}%, "
                f"Median rent {a['Median_rent']}\n"
                f"{b['building_name']} ({bedroom}BR): ROI {roi_b:.2f}%, "
                f"Median rent {b['Median_rent']}\n\n"
                f"{a['building_name'] if roi_a > roi_b else b['building_name']} "
                f"has the higher gross ROI for this bedroom type."
            )

            return reply(analysis + "\n\n" + a["report"] + "\n\n" + b["report"])

        # -------- SINGLE BUILDING (Layer 2.2) --------
        if len(matched_ids) == 1:
            building_id = list(matched_ids)[0]

            # Default bedroom → 1BR
            if not bedroom:
                bedroom = "1"

                subset = get_roi_rows([building_id], bedroom)
                if len(subset) == 0:
                    return reply("ROI data is unavailable for this building.")

                row = subset.iloc[0]
                roi = parse_percent(row["Gross_roi"])

                menu = df[
                    (df["building_id"] == building_id) &
                    (df["structural_type"] == "menu")
                ].iloc[0]["report"]

                text = (
                    f"{row['building_name']} (1BR): Gross ROI {roi:.2f}%, "
                    f"Median rent {row['Median_rent']}.\n\n"
                    "Since you didn’t specify the number of bedrooms, I’ve provided the "
                    "1-bedroom ROI report along with the building profile so you can "
                    "explore all available options.\n"
                    "Just reply with a reference number to open any report."
                )

                return reply(text + "\n\n" + row["report"] + "\n\n" + menu)

            subset = get_roi_rows([building_id], bedroom)
            if len(subset) == 0:
                return reply("ROI data is unavailable for this bedroom type.")

            row = subset.iloc[0]
            roi = parse_percent(row["Gross_roi"])

            return reply(
                f"{row['building_name']} ({bedroom}BR): Gross ROI {roi:.2f}%, "
                f"Median rent {row['Median_rent']}.\n\n"
                + row["report"]
            )

        return reply(
            "To analyze investment or ROI, please specify a building name.\n\n"
            "Example:\nIs Burj Crown a good investment?"
        )

    # ==========================================================
    # LAYER 0 — ORIGINAL DATABOT
    # ==========================================================
    ref = re.search(r"\b\d{7}\b", msg)
    if ref:
        for r in KEYWORD_ROWS:
            if ref.group() in r["keywords"]:
                return reply(r["reply"])

    for r in KEYWORD_ROWS:
        for kw in r["keywords"]:
            if kw in msg:
                return reply(r["reply"])

    # ==========================================================
    # FALLBACK
    # ==========================================================
    return reply(
        "I didn’t find a specific building or reference number.\n\n"
        "You can try:\n"
        "- sending a building name\n"
        "- sending a reference number\n"
        "- asking an investment or comparison question"
    )
