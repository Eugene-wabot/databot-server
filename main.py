from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# Load Excel once
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

NO_MATCH_TEXT = "Please rephrase, I didn’t find anything."

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

# ---------- PREPROCESS COLUMN A ----------
# Split Column A by comma → each part is a valid keyword
rows = []

for idx, row in df.iterrows():
    col_a = row.iloc[0]
    col_b = row.iloc[1]

    if not isinstance(col_a, str):
        continue

    keywords = [
        normalize(k)
        for k in col_a.split(",")
        if normalize(k)
    ]

    rows.append({
        "keywords": keywords,
        "reply": col_b
    })

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return wa_reply("")

    msg = normalize(message)

    # ---------- MATCH ----------
    for row in rows:
        for kw in row["keywords"]:
            # exact reference number or phrase anywhere in message
            if re.search(rf"\b{re.escape(kw)}\b", msg):
                return wa_reply(row["reply"])

    return wa_reply(NO_MATCH_TEXT)
