# 💼 VoiceQuote: Generador de Presupuestos desde Audio y Texto (Micro-SaaS)

Sistema completo y modular de generación automatizada de presupuestos y propuestas comerciales diseñado para técnicos de campo, instaladores y comerciales. Permite dictar una nota de voz o escribir un texto rápido para obtener de forma inmediata un presupuesto estructurado con precisión matemática y compilado en un PDF profesional con diseño contemporáneo *glassmorphism*.

---

## 🏛️ Arquitectura del Sistema

```
├── app/
│   ├── __init__.py
│   ├── config.py                 # Parámetros y variables de entorno (Pydantic BaseSettings)
│   ├── main.py                   # Servidor FastAPI (Endpoints REST, CORS, validación)
│   ├── models/
│   │   ├── __init__.py
│   │   └── budget.py             # Modelos de dominio Pydantic (Validación matemática y cálculo exacto)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcribe_service.py # Transcripción Whisper (Soporte OpenAI y Groq Cloud)
│   │   ├── ai_service.py         # Extracción comercial inteligente con LLMs estructurados
│   │   └── pdf_service.py        # Renderizado Jinja2 y compilación PDF (WeasyPrint / xhtml2pdf)
│   └── templates/
│       ├── budget_template.html  # Plantilla HTML/CSS editorial (glassmorphism/corporate)
│       └── assets/               # Recursos visuales y logotipos
├── frontend/
│   ├── __init__.py
│   └── app.py                    # Interfaz Streamlit (Grabación en vivo, editor y visor PDF)
├── .env.example                  # Plantilla de variables de entorno
├── requirements.txt              # Dependencias de producción
└── README.md
```

---

## 🚀 Puesta en Marcha Rápida

### 1. Clonar el repositorio y crear entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar en Windows
.\venv\Scripts\activate

# Activar en Linux / macOS
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y configura tus credenciales:

```bash
cp .env.example .env   # En Linux / Mac
copy .env.example .env # En Windows PowerShell / CMD
```

Edita `.env` con tus claves de API (`OPENAI_API_KEY` o `GROQ_API_KEY`) y personaliza los datos comerciales de tu empresa emisora (nombre, CIF, teléfono, dirección, IBAN bancario).

---

## 🖥️ Ejecución de la Aplicación

### Terminal 1: Iniciar el Servidor Backend (FastAPI)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Documentación interactiva Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Endpoint de verificación: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Terminal 2: Iniciar la Interfaz Web (Streamlit)

```bash
streamlit run frontend/app.py
```

Accede a [http://localhost:8501](http://localhost:8501) en tu navegador.

---

## 📡 Endpoints de la API REST

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Estado del backend |
| `POST` | `/api/transcribe` | Sube un archivo de audio (`.mp3`, `.m4a`, `.wav`, etc.) y recibe el texto transcrito con Whisper |
| `POST` | `/api/generate-budget-from-text` | Envía texto libre o transcrito y recibe el JSON estructurado del presupuesto |
| `POST` | `/api/generate-budget-from-audio` | Pipeline directo: Audio -> Transcripción -> Presupuesto JSON |
| `POST` | `/api/render-pdf` | Envía el JSON del presupuesto (incluso editado) y descarga el archivo binario PDF |
| `POST` | `/api/generate-pdf-from-audio` | Flujo todo-en-uno: Envía nota de audio y recibe directamente el PDF compilado |
| `POST` | `/api/generate-pdf-from-text` | Flujo todo-en-uno: Envía texto comercial y recibe directamente el PDF compilado |

---

## 🛠️ Tecnologías Empleadas

- **FastAPI**: Backend asíncrono de alto rendimiento con validación automática y esquemas OpenAPI.
- **Pydantic v2**: Modelos fuertemente tipados con validadores matemáticos que garantizan la exactitud contable de bases imponibles, descuentos e IVA.
- **Whisper (OpenAI / Groq)**: Transcripción precisa de audios técnicos con términos sectoriales en español.
- **Jinja2 + xhtml2pdf / WeasyPrint**: Motor dual de compilación PDF: calidad editorial moderna con fallback 100% Python compatible en cualquier sistema operativo sin dependencias externas.
- **Streamlit**: Interfaz web responsiva con grabador de audio, editor interactivo en tiempo real y visualizador de PDF incrustado.

