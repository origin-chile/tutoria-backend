# TutorIA + CVpro — Backend

Servidor FastAPI que conecta los dos productos con la API de Anthropic de forma segura.

## Estructura

```
tutoria-backend/
├── main.py              # Servidor FastAPI
├── requirements.txt     # Dependencias Python
├── static/
│   ├── tutor.html       # Tutor universitario + media
│   └── cv.html          # CV + entrevistas
└── README.md
```

---

## Despliegue en Render.com (gratis)

### Paso 1 — Sube el proyecto a GitHub

1. Ve a github.com → New repository → llámalo `tutoria-backend`
2. En tu computador, abre la terminal en la carpeta del proyecto y ejecuta:

```bash
git init
git add .
git commit -m "primer commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/tutoria-backend.git
git push -u origin main
```

### Paso 2 — Crea el servicio en Render

1. Ve a render.com → Sign up con GitHub
2. Click **New +** → **Web Service**
3. Conecta tu repo `tutoria-backend`
4. Configura:
   - **Name:** tutoria-backend
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click **Add Environment Variable**:
   - Key: `ANTHROPIC_API_KEY`
   - Value: tu API key de console.anthropic.com
6. Click **Create Web Service**

En ~3 minutos tendrás una URL tipo:
`https://tutoria-backend.onrender.com`

### Paso 3 — Acceder a los productos

- **Tutor:** `https://tutoria-backend.onrender.com/tutor`
- **CV:** `https://tutoria-backend.onrender.com/cv`

---

## Probar localmente

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Iniciar servidor
uvicorn main:app --reload --port 8000
```

Luego abre:
- http://localhost:8000/tutor
- http://localhost:8000/cv

---

## Dominio propio (opcional)

1. Compra `tutoria.cl` en NIC Chile (~$10 USD/año)
2. En Render → Settings → Custom Domains → agrega tu dominio
3. Apunta el DNS de NIC Chile al valor que te da Render

---

## API key de Anthropic

1. Ve a console.anthropic.com
2. Settings → API Keys → Create Key
3. Guárdala — solo se muestra una vez
4. Agrégala como variable de entorno en Render (nunca en el código)
