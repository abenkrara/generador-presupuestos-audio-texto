"""
Servidor Principal FastAPI - Generador de Presupuestos Inteligente.
Proporciona endpoints REST para transcripción, extracción comercial y compilación de PDF.
"""

import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.budget import (
    Budget,
    CompanyInfo,
    TextBudgetRequest,
    TranscriptionResponse,
)
from app.services.transcribe_service import transcribe_service
from app.services.ai_service import ai_service
from app.services.pdf_service import pdf_service

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app.main")

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="Generador de Presupuestos desde Audio y Texto",
    description="Micro-SaaS para técnicos y comerciales: transforma notas de voz en presupuestos profesionales en PDF.",
    version="1.0.0"
)

# Habilitar CORS para integración con Streamlit y clientes web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Información"])
async def root():
    """Endpoint raíz con metadatos del servicio."""
    return {
        "service": "Generador de Presupuestos desde Audio / Texto",
        "status": "online",
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER,
        "transcription_provider": settings.TRANSCRIPTION_PROVIDER,
        "documentation": "/docs"
    }


@app.get("/api/health", tags=["Salud"])
async def health_check():
    """Comprobación de estado operativo del servicio."""
    return {"status": "ok", "app": "budget-generator"}


@app.post(
    "/api/transcribe",
    response_model=TranscriptionResponse,
    tags=["Audio & Transcripción"],
    summary="Transcribir archivo de voz a texto plano"
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Archivo de audio (.mp3, .m4a, .wav, .ogg, .webm)")
):
    """Recibe un archivo de audio de notas de voz y devuelve el texto transcrito con Whisper."""
    try:
        text, duration, provider = await transcribe_service.transcribe_audio_file(file)
        return TranscriptionResponse(
            text=text,
            duration_seconds=duration,
            provider_used=provider
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error procesando transcripción: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado al transcribir el audio: {str(exc)}")


@app.post(
    "/api/generate-budget-from-text",
    response_model=Budget,
    tags=["Extracción Comercial & IA"],
    summary="Generar presupuesto estructurado a partir de texto"
)
async def generate_budget_from_text(payload: TextBudgetRequest):
    """
    Analiza una nota de trabajo o transcripción mediante LLM y devuelve el presupuesto
    completamente estructurado y validado matemáticamente.
    """
    try:
        budget = ai_service.extract_budget_from_text(
            raw_text=payload.raw_text,
            tax_percent_override=payload.tax_percent,
            company_override=payload.company_overrides
        )
        return budget
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error extrayendo presupuesto desde texto: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al estructurar presupuesto: {str(exc)}")


@app.post(
    "/api/generate-budget-from-audio",
    response_model=Budget,
    tags=["Pipeline Integral"],
    summary="Flujo completo: Audio -> Transcripción -> Presupuesto JSON"
)
async def generate_budget_from_audio(
    file: UploadFile = File(..., description="Audio con la nota del comercial/técnico"),
    tax_percent: Optional[float] = Form(default=None, description="IVA personalizado opcional")
):
    """
    Recibe directamente un archivo de audio, lo transcribe mediante Whisper
    y extrae el presupuesto estructurado listo para revisar o editar.
    """
    try:
        text, _, _ = await transcribe_service.transcribe_audio_file(file)
        budget = ai_service.extract_budget_from_text(
            raw_text=text,
            tax_percent_override=tax_percent
        )
        return budget
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error en flujo audio -> JSON: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fallo en procesamiento de audio: {str(exc)}")


@app.post(
    "/api/render-pdf",
    tags=["PDF"],
    summary="Compilar presupuesto estructurado a documento PDF"
)
async def render_pdf(budget: Budget):
    """
    Toma un objeto Budget (pudiendo haber sido editado previamente en el frontend)
    y compila el PDF profesional con el diseño comercial moderno.
    """
    try:
        pdf_bytes = pdf_service.generate_pdf(budget)
        filename = f"{budget.budget_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error compilando PDF: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fallo al generar el archivo PDF: {str(exc)}")


@app.post(
    "/api/generate-pdf-from-audio",
    tags=["Pipeline Integral"],
    summary="Audio Directo -> Archivo PDF Final"
)
async def generate_pdf_from_audio(
    file: UploadFile = File(..., description="Audio con la nota del trabajo"),
    tax_percent: Optional[float] = Form(default=None)
):
    """
    Atajo todo-en-uno: Envía una nota de voz y descarga directamente el PDF comercial final.
    """
    try:
        text, _, _ = await transcribe_service.transcribe_audio_file(file)
        budget = ai_service.extract_budget_from_text(raw_text=text, tax_percent_override=tax_percent)
        pdf_bytes = pdf_service.generate_pdf(budget)
        filename = f"{budget.budget_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error en endpoint directo audio -> PDF: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en pipeline directo de audio a PDF: {str(exc)}")


@app.post(
    "/api/generate-pdf-from-text",
    tags=["Pipeline Integral"],
    summary="Texto Directo -> Archivo PDF Final"
)
async def generate_pdf_from_text(payload: TextBudgetRequest):
    """
    Atajo todo-en-uno: Envía texto comercial y descarga directamente el PDF profesional.
    """
    try:
        budget = ai_service.extract_budget_from_text(
            raw_text=payload.raw_text,
            tax_percent_override=payload.tax_percent,
            company_override=payload.company_overrides
        )
        pdf_bytes = pdf_service.generate_pdf(budget)
        filename = f"{budget.budget_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error en endpoint directo texto -> PDF: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en pipeline directo de texto a PDF: {str(exc)}")


# Bloque de inicio autónomo
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)

