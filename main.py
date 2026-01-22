from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto(request: Request):
    data = await request.json()
    message = data.get("message", "")

    reply = "✅ Server is working.\nYou said:\n" + message
    return PlainTextResponse(reply)
