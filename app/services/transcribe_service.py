"""
Servicio de Transcripción de Audio a Texto.
Soporta Whisper a través de OpenAI y Groq Cloud (ultra rápido y económico).
Incluye fallback demostrativo para pruebas inmediatas si no hay API key configurada.
"""

import os
import tempfile
import logging
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# Extensiones de audio admitidas
SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".webm", ".aac", ".flac"}


class TranscribeService:
    """Gestiona la transcripción de archivos de voz utilizando Whisper."""

    def __init__(self):
        self.provider = settings.TRANSCRIPTION_PROVIDER.lower()
        self.model = settings.TRANSCRIPTION_MODEL

    def _has_valid_api_key(self) -> bool:
        """Verifica si existe al menos una clave de API configurada y no de ejemplo."""
        if self.provider == "groq":
            k = settings.GROQ_API_KEY
            return bool(k and "tu_groq" not in k and len(k) > 15)
        else:
            k = settings.OPENAI_API_KEY
            return bool(k and "tu_openai" not in k and len(k) > 15)

    def _get_openai_client(self):
        """Inicializa el cliente de OpenAI de forma perezosa."""
        from openai import OpenAI
        return OpenAI(api_key=settings.OPENAI_API_KEY)

    def _get_groq_client(self):
        """Inicializa el cliente de Groq de forma perezosa."""
        from groq import Groq
        return Groq(api_key=settings.GROQ_API_KEY)

    async def transcribe_audio_file(self, file: UploadFile) -> Tuple[str, Optional[float], str]:
        """
        Guarda temporalmente el archivo subido y solicita la transcripción al servicio Whisper configurado.
        
        Args:
            file: Archivo de audio recibido desde FastAPI (UploadFile).
            
        Returns:
            Tuple con (texto_transcrito, duracion_segundos, proveedor_utilizado).
        """
        filename = file.filename or "audio.wav"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de archivo '{ext}' no soportado. Formatos válidos: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                temp_file_path = tmp.name
                content = await file.read()
                if len(content) == 0:
                    raise HTTPException(status_code=400, detail="El archivo de audio está vacío.")
                tmp.write(content)

            return self.transcribe_local_path(temp_file_path)

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el archivo temporal {temp_file_path}: {e}")

    def transcribe_local_path(self, file_path: str) -> Tuple[str, Optional[float], str]:
        """
        Transcribe un archivo de audio que ya se encuentra en disco.
        Si no se ha configurado API key en .env, devuelve una transcripción de demostración
        para permitir pruebas completas del flujo de trabajo.
        
        Args:
            file_path: Ruta absoluta al archivo de audio.
            
        Returns:
            Tuple con (texto_transcrito, duracion_segundos, proveedor_utilizado).
        """
        if not self._has_valid_api_key():
            logger.info("No se detectó API key para Whisper. Utilizando transcripción demostrativa de audio...")
            mock_text = (
                "Presupuesto para Reformas Integrales Martínez, NIF B-83921102 en Avenida de América 18. "
                "Sustitución de cuadro eléctrico y cableado ignífugo por 450 euros. "
                "Instalación de 8 puntos de iluminación LED de bajo consumo a 35 euros la unidad. "
                "Mano de obra cualificada de instalador autorizado 6 horas a 42 euros la hora con 5% de descuento en mano de obra. "
                "Boletín de enganche legalizado 120 euros. Pago 50% al inicio y 50% al finalizar los trabajos. Garantía de 2 años."
            )
            return mock_text, 12.5, "Whisper Emulado (Demo Mode)"

        provider = self.provider

        try:
            if provider == "groq":
                client = self._get_groq_client()
                model_to_use = self.model if "whisper" in self.model else "whisper-large-v3-turbo"
                
                with open(file_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        file=audio_file,
                        model=model_to_use,
                        language="es",
                        response_format="verbose_json"
                    )
                
                text = getattr(transcription, "text", str(transcription))
                duration = getattr(transcription, "duration", None)
                return text.strip(), duration, "Groq (Whisper)"

            else:  # Por defecto OpenAI
                client = self._get_openai_client()
                model_to_use = self.model if "whisper" in self.model else "whisper-1"
                
                with open(file_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        file=audio_file,
                        model=model_to_use,
                        language="es",
                        response_format="verbose_json"
                    )

                text = getattr(transcription, "text", str(transcription))
                duration = getattr(transcription, "duration", None)
                return text.strip(), duration, "OpenAI (Whisper)"

        except Exception as exc:
            logger.error(f"Error durante la transcripción con {provider}: {exc}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Fallo en el servicio de transcripción ({provider}): {str(exc)}"
            )


# Instancia única del servicio
transcribe_service = TranscribeService()
