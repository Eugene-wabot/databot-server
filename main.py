from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto():
    return JSONResponse({
        "reply": "SERVER OK"
    })
