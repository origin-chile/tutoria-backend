import os
import json
import uuid
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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
TOKENS_FILE = "tokens.json"

PLAN_DAYS = {
    "prueba":  3,
    "semanal": 7,
    "mensual": 30,
}

# ─── TOKEN STORAGE ───────────────────────────────────────
def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            return json.load(f)
    return {}

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f)

def create_access_token(plan: str, flow_token: str = None):
    tokens = load_tokens()
    days = PLAN_DAYS.get(plan, 7)
    code = str(uuid.uuid4()).replace("-", "")[:16]
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    tokens[code] = {"plan": plan, "expires": expires, "flow_token": flow_token}
    if flow_token:
        tokens[f"flow_{flow_token}"] = code  # index por flow token
    save_tokens(tokens)
    return code

def validate_token(code: str):
    tokens = load_tokens()
    if code not in tokens:
        return None
    token = tokens[code]
    expires = datetime.fromisoformat(token["expires"])
    if datetime.now() > expires:
        return None
    return token

# ─── MESSAGE LIMITS ─────────────────────────────────────
PLAN_LIMITS = {"prueba": 30, "semanal": 30, "mensual": 30}
USAGE_FILE = "usage.json"

def load_usage():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE) as f:
            return json.load(f)
    return {}

def save_usage(usage):
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f)

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def check_and_increment(token_code: str):
    """Verifica límite y suma 1. Retorna (permitido, restantes)"""
    token_data = validate_token(token_code)
    if not token_data:
        return False, 0

    plan = token_data["plan"]
    limit = PLAN_LIMITS.get(plan, 30)
    today = get_today()
    usage_key = f"{token_code}_{today}"

    usage = load_usage()
    used = usage.get(usage_key, 0)

    if used >= limit:
        return False, 0

    usage[usage_key] = used + 1
    save_usage(usage)
    return True, limit - (used + 1)

# ─── AI CHAT ─────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    system: Optional[str] = None
    max_tokens: Optional[int] = 1800
    access_token: Optional[str] = None

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="API key no configurada")

    # Verificar límite si hay token (en localhost se salta)
    remaining = None
    if req.access_token:
        allowed, remaining = check_and_increment(req.access_token)
        if not allowed:
            raise HTTPException(status_code=429, detail="LIMIT_REACHED")

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

    result = resp.json()
    if remaining is not None:
        result["remaining_msgs"] = remaining
    return result

# ─── FILE UPLOAD ─────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text = ""
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        try:
            import pypdf, io
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
        raise HTTPException(status_code=400, detail="Solo PDF o TXT")
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No se pudo extraer texto")
    if len(text) > 8000:
        text = text[:8000] + "\n[Recortado]"
    return {"text": text, "chars": len(text), "filename": file.filename}

# ─── PAYMENT WEBHOOKS ────────────────────────────────────
@app.post("/api/webhook/flow")
async def webhook_flow(request: Request):
    """Flow llama aquí cuando un pago es confirmado"""
    try:
        body = await request.form()
        flow_token = body.get("token", "")
        status = int(body.get("status", 0))
        subject = body.get("subject", "semanal").lower()

        if status == 2:  # 2 = pagado en Flow
            plan = "prueba"
            if "mensual" in subject or "30" in subject:
                plan = "mensual"
            elif "semana" in subject or "7" in subject or "semanal" in subject:
                plan = "semanal"
            create_access_token(plan, flow_token)
    except Exception:
        pass
    return {"status": "ok"}

@app.post("/api/webhook/mercadopago")
async def webhook_mp(request: Request):
    """Mercado Pago webhook"""
    try:
        body = await request.json()
        if body.get("type") == "payment":
            payment_id = body.get("data", {}).get("id")
            # Por ahora crea token semanal — en producción verificar con MP API
            if payment_id:
                create_access_token("semanal", f"mp_{payment_id}")
    except Exception:
        pass
    return {"status": "ok"}

# ─── ACCESS VALIDATION ───────────────────────────────────
@app.get("/api/access/check")
async def check_access(token: str):
    """Valida un código de acceso"""
    data = validate_token(token)
    if not data:
        raise HTTPException(status_code=403, detail="Acceso inválido o expirado")
    expires = datetime.fromisoformat(data["expires"])
    days_left = (expires - datetime.now()).days
    return {"valid": True, "plan": data["plan"], "days_left": days_left, "expires": data["expires"]}

@app.get("/api/access/by-flow")
async def access_by_flow(token: str):
    """Busca código de acceso por token de Flow (para redirect post-pago)"""
    tokens = load_tokens()
    code = tokens.get(f"flow_{token}")
    if not code:
        raise HTTPException(status_code=404, detail="Token no encontrado aún")
    data = validate_token(code)
    if not data:
        raise HTTPException(status_code=403, detail="Token expirado")
    return {"code": code, "plan": data["plan"]}

@app.get("/api/access/create-manual")
async def create_manual(plan: str, secret: str):
    """Crear acceso manual (para ti, como admin)"""
    admin_secret = os.environ.get("ADMIN_SECRET", "tutoria-admin-2024")
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="No autorizado")
    code = create_access_token(plan)
    return {"code": code, "plan": plan, "days": PLAN_DAYS.get(plan, 7)}

# ─── STATIC FILES ────────────────────────────────────────
@app.get("/tutor")
def tutor():
    return FileResponse("tutor.html")

@app.get("/acceder")
def acceder():
    return FileResponse("acceder.html")

@app.get("/cv")
def cv():
    if os.path.exists("cv.html"):
        return FileResponse("cv.html")
    return HTMLResponse("<h2>CV tool próximamente</h2>")

@app.get("/")
def root():
    return FileResponse("index.html")
