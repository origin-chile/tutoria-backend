import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    system: Optional[str] = None
    max_tokens: Optional[int] = 1000

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="API key no configurada")
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": req.max_tokens,
        "messages": [m.dict() for m in req.messages],
    }
    if req.system:
        payload["system"] = req.system
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.get("/tutor")
def tutor():
    return FileResponse("tutor.html")

@app.get("/cv")
def cv():
    if os.path.exists("cv.html"):
        return FileResponse("cv.html")
    return HTMLResponse("<h2>CV tool próximamente</h2>")

@app.get("/")
def root():
    return FileResponse("tutor.html")
