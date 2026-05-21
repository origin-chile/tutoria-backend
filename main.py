import os
import json
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
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
    max_tokens: Optional[int] = 1800

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="API key no configurada")
    payload = {
        "model": "claude-sonnet-4-5",
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

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Extrae texto de PDF o TXT subido por el usuario"""
    content = await file.read()
    text = ""
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error leyendo PDF: {str(e)}")
    elif filename.endswith(".txt") or filename.endswith(".md"):
        try:
            text = content.decode("utf-8")
        except:
            text = content.decode("latin-1")
    else:
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF o TXT")

    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del archivo")

    # Limitar a 8000 caracteres para no exceder el contexto
    if len(text) > 8000:
        text = text[:8000] + "\n\n[Documento recortado por longitud]"

    return {"text": text, "chars": len(text), "filename": file.filename}

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
