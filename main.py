from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd
import re
import json

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app_metadata_sample.xlsx", dtype=str)

# Normalize Column A once (keep the full string, because it contains ref + building + tags)
df["_colA"] = (
    df.iloc[:, 0]
    .astype(str)
    .str.replace("\u00a0", " ", regex=False)
    .str.strip()
    .str.lower()
)

NO_MATCH_TEXT = "Please rephrase, I didn’t find anything."

def wa_reply(text: str) -> Response:
    return Response(
        json.dumps({"reply": text}, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()

    if not message:
        return wa_reply("")

    message_lower = (
        message.lower()
        .replace("\u00a0", " ")
        .strip()
    )

    # ---------- STAGE 1: reference number (7 digits) ----------
    # Column A might look like: "1006423, *SALES*"
    if re.fullmatch(r"\d{7}", message_lower):
        ref = message_lower
        ref_pattern = re.compile(rf"(^|[^0-9]){re.escape(ref)}([^0-9]|$)")
        ref_matches = df[df["_colA"].apply(lambda x: bool(ref_pattern.search(x)))]
        if not ref_matches.empty:
            return wa_reply(ref_matches.iloc[0, 1])

    # ---------- STAGE 2: exact whole-word match (original behavior) ----------
    # This catches cases where Column A is exactly a word/phrase.
    word_pattern = re.compile(rf"\b{re.escape(message_lower)}\b")
    exact_matches = df[df["_colA"].apply(lambda x: bool(word_pattern.search(x)))]

    if not exact_matches.empty:
        return wa_reply(exact_matches.iloc[0, 1])

    # ---------- STAGE 3: fallback (original behavior) ----------
    # 1) Column A contains the message (e.g. "burj crown" inside "1008918, burj crown, *build*")
    # 2) Or Column A is contained in the message
    fallback_matches = df[
        df["_colA"].str.contains(re.escape(message_lower), na=False)
        |
        df["_colA"].apply(lambda x: isinstance(x, str) and x in message_lower)
    ]

    if not fallback_matches.empty:
        return wa_reply(fallback_matches.iloc[0, 1])

    # ---------- NO MATCH ----------
    return wa_reply(NO_MATCH_TEXT)
