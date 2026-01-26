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

def parse_percent(value):
    if value is None:
        return None
    v = str(value).strip().replace("%", "")
    try:
        return float(v)
    except:
        return None

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
    "roi", "investment", "yield", "good investment"
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

# ---------------- ROI data fetch ----------------
def get_roi_subset(building_ids, bedroom):
    bedroom = str(bedroom).lower().strip()

    subset = df[
        (df["building_id"].isin(building_ids)) &
        (df["bedroom_type"].astype(str).str.lower().str.strip() == bedroom) &
        (df["Gross_roi"].notna())
    ]

    return subset if len(subset) > 0 else None

# ---------------- Main endpoint ----------------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return reply("")

    msg = normalize(message)

    # ==================================================
    # LAYER 2 — AI / ANALYTICAL REQUESTS
    # ==================================================
    if is_ai_intent(msg):
        bedroom = extract_bedroom(msg)

        matched_ids = set()
        menu_rows = df[df["structural_type"] == "menu"]

        for _, row in menu_rows.iterrows():
            keywords = [normalize(k) for k in row["key_word"].split(",") if normalize(k)]
            if any(k in msg for k in keywords):
                matched_ids.add(row["building_id"])

        # ---------- Layer 2.1: comparison ----------
        if len(matched_ids) == 2 and bedroom:
            subset = get_roi_subset(list(matched_ids), bedroom)
            if subset is not None and len(subset) == 2:
                a, b = subset.iloc[0], subset.iloc[1]

                roi_a = parse_percent(a["Gross_roi"])
                roi_b = parse_percent(b["Gross_roi"])

                if roi_a is None or roi_b is None:
                    return reply("ROI data is unavailable for this request.")

                analysis = (
                    f"{a['building_name']} ({bedroom}BR): ROI {roi_a:.2f}%, "
                    f"Median rent {a['Median_rent']}\n"
                    f"{b['building_name']} ({bedroom}BR): ROI {roi_b:.2f}%, "
                    f"Median rent {b['Median_rent']}\n\n"
                    f"{a['building_name'] if roi_a > roi_b else b['building_name']} "
                    f"has the higher gross ROI for this bedroom type."
                )

                reports = list(subset["report"])
                return reply(analysis + "\n\n" + "\n\n".join(reports))

            return reply(
                "I found both buildings, but ROI data for this bedroom "
                "is missing or inconsistent."
            )

        # ---------- Layer 2.2: single building ----------
        if len(matched_ids) == 1:
            if not bedroom:
                return reply("Which bedroom type are you interested in?")

            subset = get_roi_subset(list(matched_ids), bedroom)
            if subset is None:
                return reply("ROI data is unavailable for this bedroom type.")

            row = subset.iloc[0]
            roi = parse_percent(row["Gross_roi"])

            if roi is None:
                return reply("ROI data is unavailable for this request.")

            analysis = (
                f"{row['building_name']} ({bedroom}BR): "
                f"Gross ROI {roi:.2f}%, Median rent {row['Median_rent']}."
            )

            return reply(analysis + "\n\n" + row["report"])

        return reply(
            "To analyze investment or ROI, please specify:\n"
            "- building name\n"
            "- bedroom type\n\n"
            "Example:\n"
            "Is Burj Crown a good investment for 1 bedroom?"
        )

    # ==================================================
    # LAYER 0 — ORIGINAL DATABOT BEHAVIOR
    # ==================================================

    ref = re.search(r"\b\d{7}\b", msg)
    if ref:
        for r in KEYWORD_ROWS:
            if ref.group() in r["keywords"]:
                return reply(r["reply"])

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
        "- asking an investment or comparison question"
    )
