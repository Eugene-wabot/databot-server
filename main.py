from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/whatsauto")
async def whatsauto(request: Request):
    try:
        form = await request.form()
        data = dict(form)
    except:
        data = {}

    return JSONResponse({
        "reply": f"FORM DATA:\n{data}"
    })
