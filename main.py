from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# ---------------- Helpers ----------------
def normalize(text: str) -> str:
    return (
        str(text)
        .replace("\u00a0", " ")
        .replace("\n", " ")
        .lower()
        .strip()
    )

def wa_reply(text: str) -> Response:
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

# ---------------- Layer 0 keywords ----------------
rows = []
for _, row in df.iterrows():
    if not isinstance(row.iloc[0], str):
        continue

    keywords = [normalize(k) for k in row.iloc[0].split(",") if normalize(k)]
    rows.append({
        "keywords": keywords,
        "reply": row.iloc[1],
        "building_id": row.get("building_id")
    })

# ---------------- AI intent ----------------
AI_INTENT_KEYWORDS = [
    "compare", "vs", "versus",
    "better", "best",
    "roi", "investment", "yield"
]

def ai_intent_detected(msg: str) -> bool:
    return any(k in msg for k in AI_INTENT_KEYWORDS)

# ---------------- Bedroom parsing (flexible) ----------------
def extract_bedroom(msg: str):
    if "studio" in msg:
        return "studio"

    patterns = {
        "1": [r"\b1\s*br\b", r"\b1\s*bed", r"\bone\b"],
        "2": [r"\b2\s*br\b", r"\b2\s*bed", r"\btwo\b"],
        "3": [r"\b3\s*br\b", r"\b3\s*bed", r"\bthree\b"],
        "4": [r"\b4\s*br\b", r"\b4\s*bed", r"\bfour\b"],
    }

    for k, pats in patterns.items():
        for p in pats:
            if re.search(p, msg):
                return k
    return None

# ---------------- Layer 2: ROI comparison ----------------
def layer2_compare_roi(building_ids, bedroom):
    subset = df[
        (df["building_id"].isin(building_ids)) &
        (df["bedroom_type"] == bedroom) &
        (df["Gross_roi"].notna())
    ]

    if len(subset) != 2:
        return None

    a, b = subset.iloc[0], subset.iloc[1]

    roi_a, roi_b = float(a["Gross_roi"]), float(b["Gross_roi"])
    rent_a, rent_b = a["Median_rent"], b["Median_rent"]

    winner = a if roi_a > roi_b else b

    reply = (
        f"{a['building_name']} ({bedroom}BR): ROI {roi_a:.2f}%, "
        f"Median rent {rent_a}\n"
        f"{b['building_name']} ({bedroom}BR): ROI {roi_b:.2f}%, "
        f"Median rent {rent_b}\n\n"
        f"{winner['building_name']} performs better mainly due to "
        f"{'stronger rental levels' if winner['Median_rent'] else 'pricing dynamics'}."
    )
    return reply

# ---------------- Main endpoint ----------------
@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()
    if not message:
        return wa_reply("")

    msg = normalize(message)

    # ---------- Layer 0: reference number ----------
    ref = re.search(r"\b(\d{7})\b", msg)
    if ref:
        for r in rows:
            if ref.group(1) in r["keywords"]:
                return wa_reply(r["reply"])

    # ---------- Layer 0: keyword match ----------
    matched_buildings = []
    for r in rows:
        for kw in r["keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", msg):
                matched_buildings.append(r["building_id"])
                return wa_reply(r["reply"])

    # ---------- Layer 2: ROI compare ----------
    if ai_intent_detected(msg):
        bedroom = extract_bedroom(msg)
        building_ids = list(
            df[df["key_word"].apply(lambda x: any(k in msg for k in normalize(x).split(",")))]
            ["building_id"].unique()
        )

        if len(building_ids) == 2 and bedroom:
            result = layer2_compare_roi(building_ids, bedroom)
            if result:
                return wa_reply(result)

        return wa_reply(
            "To compare ROI, please specify:\n"
            "- exactly 2 buildings\n"
            "- bedroom type\n\n"
            "Example:\n"
            "Compare Burj Crown and 25hours ROI 1 bedroom"
        )

    # ---------- AI fallback ----------
    return wa_reply(
        "I didn’t find a specific building or reference number.\n\n"
        "You can try:\n"
        "- sending a building name\n"
        "- sending a reference number\n"
        "- asking to compare two buildings"
    )
