from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import pandas as pd

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return JSONResponse({"reply": ""})

    message_lower = message.lower()

    # Bidirectional matching:
    # 1) Column A contains message
    # 2) Message contains Column A
    matches = df[
        df.iloc[:, 0].str.lower().str.contains(message_lower, na=False)
        |
        df.iloc[:, 0].apply(
            lambda x: isinstance(x, str) and x.lower() in message_lower
        )
    ]

    if not matches.empty:
        reply_text = matches.iloc[0, 1]
    else:
        reply_text = ""

    return JSONResponse({
        "reply": reply_text
    })
