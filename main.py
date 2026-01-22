from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto():
    return PlainTextResponse("SERVER OK")
