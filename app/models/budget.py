"""
Modelos de Datos y Esquemas Pydantic para el Sistema de Presupuestos.
Define las entidades comerciales, validaciones y cálculos automáticos.
"""

from datetime import date, timedelta
from typing import List, Optional
import uuid
import re
from pydantic import BaseModel, Field, field_validator, model_validator, AliasChoices


def clean_concepto(text: str) -> str:
    """
    Elimina precios, unidades, menciones de descuentos o etiquetas numéricas
    dejando únicamente el nombre limpio del concepto o servicio.
    """
    if not text:
        return "Servicio profesional"
    cleaned = text.strip()
    
    # 1. Eliminar menciones de precios ("por 350 euros", "a 35 € la hora", "coste 120€", etc.)
    cleaned = re.sub(
        r"\s*(?:por|a|de|coste|precio)?\s*\d+(?:[.,]\d+)?\s*(?:€|euros?|eur)(?:\s*(?:la\s+hora|\/h|unidad|ud|cada\s+uno))?",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    
    # 2. Eliminar coletillas de horas / cantidades ("estimamos 16 horas", "10 unidades", etc.)
    cleaned = re.sub(
        r"\s*(?:estimamos\s+)?\d+(?:[.,]\d+)?\s*(?:horas|hora|unidades|paneles|puntos|h\b)\s*(?:a|de)?",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    
    # 3. Eliminar coletillas de descuento en el texto ("con un 10% de descuento", "dto 5%", etc.)
    cleaned = re.sub(
        r"\s*(?:con\s+)?(?:un\s+)?\d+(?:[.,]\d+)?\s*%\s*(?:de\s+descuento|dto\.?|bonificado\s+al\s+100%)",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    
    # 4. Eliminar prefijos residuales de conversación
    cleaned = re.sub(
        r"^(?:necesita\s+|se\s+requiere\s+|hay\s+que\s+|además\s+|también\s+|incluir\s+)+",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"[\s,;:\.\-]+$", "", cleaned).strip()
    
    return cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()


class ClientInfo(BaseModel):
    """Información del cliente destinatario del presupuesto."""
    name: str = Field(..., description="Nombre comercial o persona física del cliente")
    cif_nif: Optional[str] = Field(default="", description="CIF, NIF, DNI o ID fiscal del cliente")
    address: Optional[str] = Field(default="", description="Dirección fiscal o de ejecución de obra/servicio")
    phone: Optional[str] = Field(default="", description="Teléfono de contacto")
    email: Optional[str] = Field(default="", description="Correo electrónico de contacto")
    contact_person: Optional[str] = Field(default="", description="Persona o cargo de referencia")


class CompanyInfo(BaseModel):
    """Información de la empresa emisora del presupuesto."""
    name: str = Field(default="Soluciones Técnicas & Comerciales S.L.")
    cif_nif: str = Field(default="B-98765432")
    address: str = Field(default="Calle Innovación 45, Planta 2, 28001 Madrid")
    phone: str = Field(default="+34 912 345 678")
    email: str = Field(default="contacto@solucionestecnicas.es")
    web: Optional[str] = Field(default="www.solucionestecnicas.es")
    iban: Optional[str] = Field(default="ES91 2100 0418 4502 0005 1332")
    logo_data: Optional[str] = Field(default=None, description="SVG o Base64 Data URL del logotipo")


class BudgetItem(BaseModel):
    """Línea de concepto, servicio o material incluido en el presupuesto."""
    description: str = Field(
        ...,
        validation_alias=AliasChoices("concepto", "description"),
        description="Nombre limpio del concepto o trabajo a realizar (sin precios ni cantidades dentro)"
    )
    category: str = Field(
        default="Materiales",
        validation_alias=AliasChoices("categoria", "category"),
        description="Categoría estricta: 'Mano de Obra' o 'Materiales'"
    )
    quantity: float = Field(
        default=1.0,
        ge=0.01,
        validation_alias=AliasChoices("cantidad", "quantity"),
        description="Horas o unidades del concepto"
    )
    unit_price: float = Field(
        default=0.0,
        ge=0.0,
        validation_alias=AliasChoices("precio_unitario", "unit_price"),
        description="Precio unitario neto sin impuestos"
    )
    discount_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        validation_alias=AliasChoices("descuento_porcentaje", "discount_percent"),
        description="Porcentaje de descuento aplicable a la línea"
    )
    subtotal: float = Field(default=0.0, description="Importe neto calculado de la línea")

    @model_validator(mode="after")
    def sanitize_and_calculate(self) -> "BudgetItem":
        """Limpia el texto del concepto, normaliza la categoría y calcula el subtotal exacto."""
        # Limpieza estricta del concepto
        self.description = clean_concepto(self.description)

        # Normalización estricta de la categoría: solo 'Mano de Obra' o 'Materiales'
        cat_lower = (self.category or "").lower()
        if any(term in cat_lower for term in ["obra", "mano", "hora", "instalador", "montaje", "trabajo", "servicio", "técnico", "consultoría", "desarrollo", "diseño"]):
            self.category = "Mano de Obra"
        else:
            self.category = "Materiales"

        # Cálculo matemático del subtotal
        raw_price = self.quantity * self.unit_price
        discount_factor = 1.0 - (self.discount_percent / 100.0)
        self.subtotal = round(raw_price * discount_factor, 2)
        return self


class Budget(BaseModel):
    """Documento de Presupuesto / Oferta Comercial Completa."""
    budget_id: str = Field(
        default_factory=lambda: f"PRES-{date.today().year}-{uuid.uuid4().hex[:6].upper()}",
        description="Identificador correlativo del presupuesto"
    )
    title: str = Field(default="Presupuesto de Servicios Profesionales", description="Título o resumen del proyecto")
    issue_date: str = Field(
        default_factory=lambda: date.today().strftime("%d/%m/%Y"),
        description="Fecha de emisión (formato DD/MM/AAAA)"
    )
    valid_until: str = Field(
        default_factory=lambda: (date.today() + timedelta(days=15)).strftime("%d/%m/%Y"),
        description="Fecha límite de validez de la oferta (formato DD/MM/AAAA)"
    )
    client: ClientInfo = Field(..., description="Datos del cliente")
    company: CompanyInfo = Field(default_factory=CompanyInfo, description="Datos de la empresa emisora")
    items: List[BudgetItem] = Field(default_factory=list, description="Lista de partidas presupuestadas")
    
    # Resumen Económico
    currency: str = Field(default="EUR", description="Moneda (EUR, USD, etc.)")
    currency_symbol: str = Field(default="€", description="Símbolo de la divisa")
    subtotal: float = Field(default=0.0, description="Base imponible total")
    discount_total: float = Field(default=0.0, description="Ahorro total por descuentos aplicados")
    tax_percent: float = Field(default=21.0, description="Porcentaje de IVA o impuesto indirecto")
    tax_amount: float = Field(default=0.0, description="Cuota del impuesto (IVA)")
    total_amount: float = Field(default=0.0, description="Total general a pagar (Base + Impuestos)")
    
    # Condiciones Comerciales
    payment_terms: str = Field(
        default="50% al aceptar el presupuesto y 50% a la finalización de los trabajos mediante transferencia bancaria.",
        description="Forma y plazos de pago"
    )
    notes: Optional[str] = Field(
        default="Garantía de 12 meses sobre los trabajos realizados. Presupuesto sujeto a disponibilidad de materiales.",
        description="Notas adicionales, alcance o cláusulas de garantía"
    )

    @model_validator(mode="after")
    def compute_totals(self) -> "Budget":
        """Garantiza la consistencia matemática irrefutable del presupuesto."""
        calculated_subtotal = round(sum(item.subtotal for item in self.items), 2)
        raw_total_without_discount = sum(round(item.quantity * item.unit_price, 2) for item in self.items)
        self.discount_total = round(raw_total_without_discount - calculated_subtotal, 2)
        
        self.subtotal = calculated_subtotal
        self.tax_amount = round(self.subtotal * (self.tax_percent / 100.0), 2)
        self.total_amount = round(self.subtotal + self.tax_amount, 2)
        
        if self.currency.upper() == "EUR" and not self.currency_symbol:
            self.currency_symbol = "€"
        elif self.currency.upper() == "USD" and not self.currency_symbol:
            self.currency_symbol = "$"
            
        return self


# Esquemas de Solicitudes y Respuestas API
class TextBudgetRequest(BaseModel):
    """Cuerpo de solicitud para generar presupuesto a partir de texto libre."""
    raw_text: str = Field(..., min_length=5, description="Texto transcrito o redactado sobre el trabajo")
    tax_percent: Optional[float] = Field(default=None, description="IVA a aplicar (omite para usar el valor por defecto)")
    company_overrides: Optional[CompanyInfo] = Field(default=None, description="Sobrescribir datos de la empresa si es necesario")


class TranscriptionResponse(BaseModel):
    """Respuesta con el texto transcrito de un audio."""
    text: str = Field(..., description="Texto transcrito por Whisper")
    duration_seconds: Optional[float] = Field(default=None, description="Duración aproximada del audio")
    provider_used: str = Field(..., description="Proveedor que procesó el audio (OpenAI o Groq)")
