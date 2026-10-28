"""
Módulo de Configuración de la Aplicación.
Centraliza variables de entorno y parámetros operativos mediante Pydantic Settings.
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Configuración de Proveedores IA
    LLM_PROVIDER: Literal["openai", "groq"] = Field(
        default="openai",
        description="Proveedor de LLM para extracción estructurada: 'openai' o 'groq'"
    )
    TRANSCRIPTION_PROVIDER: Literal["openai", "groq"] = Field(
        default="openai",
        description="Proveedor de Transcripción de Audio: 'openai' o 'groq'"
    )

    # Claves de API
    OPENAI_API_KEY: str = Field(default="", description="API Key de OpenAI")
    GROQ_API_KEY: str = Field(default="", description="API Key de Groq")

    # Modelos de LLM y Whisper
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="Modelo LLM")
    TRANSCRIPTION_MODEL: str = Field(default="whisper-1", description="Modelo Whisper")

    # Datos por defecto de la empresa emisora
    EMPRESA_NOMBRE: str = Field(default="Soluciones Técnicas & Comerciales S.L.")
    EMPRESA_CIF: str = Field(default="B-98765432")
    EMPRESA_DIRECCION: str = Field(default="Calle Innovación 45, Planta 2, 28001 Madrid")
    EMPRESA_TELEFONO: str = Field(default="+34 912 345 678")
    EMPRESA_EMAIL: str = Field(default="contacto@solucionestecnicas.es")
    EMPRESA_WEB: str = Field(default="www.solucionestecnicas.es")
    EMPRESA_IBAN: str = Field(default="ES91 2100 0418 4502 0005 1332")

    # Parámetros comerciales por defecto
    DEFAULT_TAX_PERCENT: float = Field(default=21.0, description="Porcentaje de IVA por defecto")
    DEFAULT_CURRENCY: str = Field(default="EUR", description="Moneda por defecto (EUR, USD, etc.)")
    DEFAULT_VALIDITY_DAYS: int = Field(default=15, description="Días de validez del presupuesto")

    # Parámetros del Servidor
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8001)
    FRONTEND_PORT: int = Field(default=8502)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Instancia única de configuración para toda la aplicación
settings = Settings()

