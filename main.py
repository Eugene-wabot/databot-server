from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto(request: Request):
    try:
        form = await request.form()
        message = form.get("message", "")
    except:
        message = ""

    return JSONResponse({
        "reply": f"You said: {message}"
    })
