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

    if message == "1006828":
        row = df[df.iloc[:, 0] == "1006828"]
        if not row.empty:
            reply_text = row.iloc[0, 1]
        else:
            reply_text = "Reference 1006828 not found in Excel"
    else:
        reply_text = "Send 1006828 to test Excel output"

    return JSONResponse({
        "reply": reply_text
    })
