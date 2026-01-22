from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto(request: Request):
    try:
        data = await request.json()
    except:
        data = {}

    return JSONResponse({
        "reply": f"RAW DATA:\n{data}"
    })
