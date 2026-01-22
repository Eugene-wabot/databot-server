from fastapi import FastAPI, Request
from fastapi.responses import Response
import pandas as pd

app = FastAPI()

# Load Excel once at startup
df = pd.read_excel("Autoreplies_app.xlsx", dtype=str)

@app.post("/whatsauto")
async def whatsauto(request: Request):
    form = await request.form()
    message = form.get("message", "").strip()

    if not message:
        return Response("", media_type="text/plain; charset=utf-8")

    message_lower = message.lower()

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

    return Response(
        reply_text,
        media_type="text/plain; charset=utf-8"
    )
