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

    # Case-insensitive contains match on Column A
    matches = df[df.iloc[:, 0].str.contains(message, case=False, na=False)]

    if not matches.empty:
        reply_text = matches.iloc[0, 1]
    else:
        reply_text = ""

    return JSONResponse({
        "reply": reply_text
    })
