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

# ================= BEDROOM EXTRACTION =================
def extract_bedroom(msg):
    msg = msg.lower()

    if re.search(r"\bstudio\b", msg):
        return "studio"

    bedroom_map = {
        "1": ["1", "one"],
        "2": ["2", "two"],
        "3": ["3", "three"],
        "4": ["4", "four"],
        "5": ["5", "five"],
    }

    for br, tokens in bedroom_map.items():
        for t in tokens:
            patterns = [
                rf"\b{t}\s*br\b",
                rf"\b{t}br\b",
                rf"\b{t}\s*b/r\b",
                rf"\b{t}b/r\b",
                rf"\b{t}\s*bed\b",
                rf"\b{t}bed\b",
                rf"\b{t}\s*bedroom\b",
                rf"\b{t}\s*bed\s*room\b",
            ]
            for p in patterns:
                if re.search(p, msg):
                    return br
    return None

# ================= AI INTENT =================
AI_INTENT_WORDS = [
    "compare", "vs", "versus",
    "roi", "investment", "yield",
    "better", "best", "good investment"
]

def is_ai_intent(msg):
    return any(w in msg for w in AI_INTENT_WORDS)

# ================= ROI FETCH =================
def get_roi_rows(building_ids, bedroom):
    return df[
        (df["building_id"].isin(building_ids)) &
        (df["bedroom_type"].astype(str).str.lower() == bedroom) &
        (df["Gross_roi"].notna()) &
        (df["structural_type"] == "report")
    ]

# ================= PRELOAD KEYWORDS =================
ROUTES = []

for _, row in df.iterrows():
    if not isinstance(row.get("key_word"), str):
        continue

    ROUTES.append({
        "keywords": [normalize(k) for k in row["key_word"].split(",") if k.strip()],
        "reply": row["report"],
        "structural_type": row["structural_type"],
        "building_id": row.get("building_id"),
        "area": row.get("area")
    })

# ================= MAIN ENDPOINT =================
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return reply("")

    msg = normalize(message)

    # ==================================================
    # 1️⃣ AMBIGUITY MENU (HIGHEST PRIORITY)
    # ==================================================
    for r in ROUTES:
        if r["structural_type"] == "ambiguity_menu":
            if any(k in msg for k in r["keywords"]):
                return reply(r["reply"])

    # ==================================================
    # 2️⃣ PROFILE MENU (BUILDING)
    # ==================================================
    matched_profile = None
    for r in ROUTES:
        if r["structural_type"] == "profile_menu":
            if any(k in msg for k in r["keywords"]):
                matched_profile = r
                break

    # ==================================================
    # 3️⃣ AREA MENU
    # ==================================================
    for r in ROUTES:
        if r["structural_type"] == "area_menu":
            if any(k in msg for k in r["keywords"]):
                return reply(r["reply"])

    # ==================================================
    # 4️⃣ AI LOGIC (ONLY IF PROFILE IDENTIFIED)
    # ==================================================
    if matched_profile and is_ai_intent(msg):
        building_id = matched_profile["building_id"]
        bedroom = extract_bedroom(msg)

        # ---------- SINGLE BUILDING ----------
        if building_id:
            # default bedroom → 1
            if not bedroom:
                bedroom = "1"

                subset = get_roi_rows([building_id], bedroom)
                if len(subset) == 0:
                    return reply("ROI data is unavailable for this building.")

                row = subset.iloc[0]

                text = (
                    f"{row['building_name']} (1BR): Gross ROI "
                    f"{parse_percent(row['Gross_roi']):.2f}%, "
                    f"Median rent {row['Median_rent']}.\n\n"
                    "Since you didn’t specify the number of bedrooms, I’ve provided "
                    "the 1-bedroom ROI report along with the building profile so you "
                    "can navigate this building and generate any available report.\n"
                    "Just send back the corresponding reference number."
                )

                return reply(text + "\n\n" + row["report"] + "\n\n" + matched_profile["reply"])

            subset = get_roi_rows([building_id], bedroom)
            if len(subset) == 0:
                return reply("ROI data is unavailable for this bedroom type.")

            row = subset.iloc[0]
            return reply(
                f"{row['building_name']} ({bedroom}BR): Gross ROI "
                f"{parse_percent(row['Gross_roi']):.2f}%, "
                f"Median rent {row['Median_rent']}.\n\n"
                + row["report"]
            )

    # ==================================================
    # 5️⃣ FALLBACK TO PROFILE MENU
    # ==================================================
    if matched_profile:
        return reply(matched_profile["reply"])

    # ==================================================
    # 6️⃣ REFERENCE NUMBER (GLOBAL)
    # ==================================================
    ref = re.search(r"\b\d{7}\b", msg)
    if ref:
        for r in ROUTES:
            if ref.group() in r["keywords"]:
                return reply(r["reply"])

    # ==================================================
    # 7️⃣ FALLBACK
    # ==================================================
    return reply(
        "I didn’t find a specific building or reference number.\n\n"
        "You can try:\n"
        "- sending a building name\n"
        "- sending a reference number\n"
        "- asking an investment question"
    )
