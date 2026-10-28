"""
Servicio de Extracción Inteligente con Modelos de Lenguaje (LLM).
Convierte notas de voz y textos informales en presupuestos estructurados (Pydantic / JSON).
Exige al modelo una lista estricta de partidas con 'concepto' limpio, 'categoria', 'cantidad',
'precio_unitario' y 'descuento_porcentaje'.
"""

import json
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
import uuid

from fastapi import HTTPException
from app.config import settings
from app.models.budget import Budget, BudgetItem, ClientInfo, CompanyInfo, clean_concepto

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un Arquitecto de Software y Consultor Comercial Senior experto en elaboración de presupuestos profesionales.
Tu tarea es analizar el texto transcrito de una nota de voz o apunte técnico y estructurar un PRESUPUESTO COMERCIAL IMPECABLE en formato JSON.

Debes responder ÚNICAMENTE con un objeto JSON válido con la siguiente estructura estricta:
{
  "title": "Título descriptivo y conciso del proyecto o trabajo a realizar",
  "client": {
    "name": "Nombre o Razón Social del cliente (si no se menciona, usa 'Cliente Particular')",
    "cif_nif": "NIF/CIF si aparece o cadena vacía",
    "address": "Dirección fiscal o de la obra o cadena vacía",
    "phone": "Teléfono si aparece o cadena vacía",
    "email": "Email si aparece o cadena vacía",
    "contact_person": "Persona de contacto si se menciona o cadena vacía"
  },
  "items": [
    {
      "concepto": "Nombre limpio del concepto, servicio o material",
      "cantidad": 1.0,
      "precio_unitario": 50.0,
      "descuento_porcentaje": 0.0,
      "categoria": "Mano de Obra"
    }
  ],
  "tax_percent": 21.0,
  "payment_terms": "Condiciones y plazos de pago acordados",
  "notes": "Observaciones, garantías y condiciones del servicio"
}

REGLAS CRÍTICAS Y OBLIGATORIAS PARA LA TABLA DE CONCEPTOS ('items'):
1. 'concepto' (string): Debe contener ÚNICAMENTE el nombre limpio y descriptivo del trabajo, servicio o material.
   - PROHIBIDO incluir precios dentro del concepto (NUNCA escribas "por 350€", "a 35 euros la hora", "coste 100€").
   - PROHIBIDO incluir cantidades o unidades dentro del concepto (NUNCA escribas "16 horas de fontanería", "22 unidades").
   - PROHIBIDO incluir etiquetas o porcentajes de descuento dentro del concepto (NUNCA escribas "con 10% de descuento").
   - Ejemplo CORRECTO: "Plato de ducha de resina antideslizante 120x70"
   - Ejemplo INCORRECTO: "Plato de ducha de resina antideslizante 120x70 por 350 euros"
   - Ejemplo CORRECTO: "Mano de obra especializada de fontanería y albañilería"
   - Ejemplo INCORRECTO: "16 horas de fontanería y albañilería a 35 euros la hora"

2. 'categoria' (string): Solo se permite estrictamente uno de estos dos valores exactos:
   - "Mano de Obra" -> Para trabajos técnicos, montaje, desmontaje, horas de operario, consultoría, instalación o mano de obra.
   - "Materiales" -> Para piezas, suministros, equipos, productos físicos, canaletas, cables, mamparas o licencias.

3. 'cantidad' (float o integer): El número de horas, unidades o metros. Si es un servicio cerrado o paquete a precio alzado, el valor debe ser 1.0.

4. 'precio_unitario' (float): El precio neto por unidad o por hora (sin IVA y sin aplicar aún el descuento).

5. 'descuento_porcentaje' (float): Porcentaje numérico entre 0.0 y 100.0 (ejemplo: si el texto dice "hazle un 10% de descuento", pon 10.0; si no hay descuento, pon 0.0).

6. Respeta escrupulosamente los importes y datos comerciales dichos en la nota.
7. NO agregues formato markdown con bloques de código (```json). Devuelve exclusivamente el string JSON parseable.
"""


class AIService:
    """Gestiona la interacción con LLMs (OpenAI y Groq) para la extracción estructurada."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL

    def _has_valid_api_key(self) -> bool:
        """Verifica si existe al menos una clave de API configurada y no de ejemplo."""
        if self.provider == "groq":
            k = settings.GROQ_API_KEY
            return bool(k and "tu_groq" not in k and len(k) > 15)
        else:
            k = settings.OPENAI_API_KEY
            return bool(k and "tu_openai" not in k and len(k) > 15)

    def _extract_heuristically(
        self,
        raw_text: str,
        tax_percent_override: Optional[float] = None,
        company_override: Optional[CompanyInfo] = None
    ) -> Budget:
        """
        Extractor heurístico de alta precisión que normaliza los conceptos según las reglas estrictas
        cuando no se dispone de API key externa.
        """
        logger.info("Extrayendo presupuesto mediante analizador estricto...")

        # 1. Identificar Cliente
        client_name = "Cliente Particular"
        name_match = re.search(
            r"(?:cliente|presupuesto para|para|empresa)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ][\w\s\.\&]+?)(?=[,\.\n]|\s+(?:cif|nif|en|con|tel|dirección))",
            raw_text,
            re.IGNORECASE
        )
        if name_match:
            cand = name_match.group(1).strip()
            if 2 < len(cand) < 60:
                client_name = cand

        cif_match = re.search(r"\b([A-HJ-NP-SUVW][0-9]{7}[0-9A-J]|[0-9]{8}[A-Z]|[A-Z]-[0-9]{7,8})\b", raw_text, re.IGNORECASE)
        cif_nif = cif_match.group(1).upper() if cif_match else ""

        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", raw_text)
        email = email_match.group(0) if email_match else ""

        phone_match = re.search(r"(?:\+?34\s*)?[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}", raw_text)
        phone = phone_match.group(0) if phone_match else ""

        addr_match = re.search(
            r"(?:en|dirección|calle|avda|avenida|polígono)\s+([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s,ºª]+?)(?=[,\.\n]|\s+necesita|\s+instalación|\s+presupuesto|\s+cif)",
            raw_text,
            re.IGNORECASE
        )
        address = addr_match.group(0).strip() if addr_match else ""

        client = ClientInfo(
            name=client_name,
            cif_nif=cif_nif,
            address=address,
            phone=phone,
            email=email,
            contact_person=""
        )

        # 2. Extraer Conceptos Limpios
        items: List[BudgetItem] = []
        sentences = [s.strip() for s in re.split(r"[;\.\n]", raw_text) if s.strip()]

        for s in sentences:
            price_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:€|euros|euro)", s, re.IGNORECASE)
            hours_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:horas|hora|unidades|paneles|puntos|h\b)", s, re.IGNORECASE)
            discount_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:de\s+descuento|dto)", s, re.IGNORECASE)

            if price_match:
                price = float(price_match.group(1).replace(",", "."))
                qty = float(hours_match.group(1).replace(",", ".")) if hours_match else 1.0
                dto = float(discount_match.group(1).replace(",", ".")) if discount_match else 0.0

                # Limpiar texto del concepto eliminando cualquier mención de precio, unidades o pagos
                raw_desc = s
                raw_desc = re.sub(r"\b(?:40%|50%|60%|30%|20%|70%)\s+al\s+\w+.*", "", raw_desc, flags=re.IGNORECASE)
                raw_desc = re.sub(r"presupuesto para [^,.-]+", "", raw_desc, flags=re.IGNORECASE)
                clean_desc = clean_concepto(raw_desc)

                if len(clean_desc) > 3:
                    # Determinar categoría estricta
                    is_labor = any(
                        term in clean_desc.lower()
                        for term in ["mano de obra", "albañilería", "fontanería", "montaje", "instalación", "técnico", "horas", "boletín", "desescombro", "diseño", "desarrollo", "seo", "redacción"]
                    )
                    categoria = "Mano de Obra" if is_labor else "Materiales"

                    items.append(BudgetItem(
                        description=clean_desc,
                        category=categoria,
                        quantity=qty,
                        unit_price=price,
                        discount_percent=dto
                    ))

        # Fallback si no hubo líneas detectadas
        if not items:
            items.append(BudgetItem(
                description="Servicios técnicos y profesionales",
                category="Mano de Obra",
                quantity=1.0,
                unit_price=150.0,
                discount_percent=0.0
            ))

        # 3. Condiciones de Pago
        payment = "50% al aceptar el presupuesto y 50% a la finalización de los trabajos mediante transferencia bancaria."
        pay_match = re.search(r"((?:\d{1,2}%\s*(?:al|a la)[^.\n]+)+)", raw_text, re.IGNORECASE)
        if pay_match:
            payment = pay_match.group(1).strip().capitalize()

        # 4. Notas y Garantía
        notes = "Garantía legal sobre los trabajos ejecutados. Oferta sujeta a aceptación en el plazo de validez."
        war_match = re.search(r"(garantía[^.\n]+)", raw_text, re.IGNORECASE)
        if war_match:
            notes = war_match.group(1).strip().capitalize()

        company = company_override or CompanyInfo(
            name=settings.EMPRESA_NOMBRE,
            cif_nif=settings.EMPRESA_CIF,
            address=settings.EMPRESA_DIRECCION,
            phone=settings.EMPRESA_TELEFONO,
            email=settings.EMPRESA_EMAIL,
            web=settings.EMPRESA_WEB,
            iban=settings.EMPRESA_IBAN,
        )

        tax = tax_percent_override if tax_percent_override is not None else settings.DEFAULT_TAX_PERCENT
        budget_id = f"PRES-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"

        return Budget(
            budget_id=budget_id,
            title=f"Propuesta Técnica y Económica para {client.name}",
            issue_date=date.today().strftime("%d/%m/%Y"),
            valid_until=(date.today() + timedelta(days=settings.DEFAULT_VALIDITY_DAYS)).strftime("%d/%m/%Y"),
            client=client,
            company=company,
            items=items,
            tax_percent=tax,
            payment_terms=payment,
            notes=notes
        )

    def extract_budget_from_text(
        self,
        raw_text: str,
        tax_percent_override: Optional[float] = None,
        company_override: Optional[CompanyInfo] = None
    ) -> Budget:
        """
        Envía el texto al LLM y parsea la respuesta en una instancia fuertemente tipada de Budget.
        Aplica validaciones estrictas sobre 'concepto', 'categoria', 'cantidad', 'precio_unitario' y 'descuento_porcentaje'.
        """
        if not raw_text or len(raw_text.strip()) < 5:
            raise HTTPException(status_code=400, detail="El texto proporcionado es demasiado breve para generar un presupuesto.")

        # Si no hay clave de API configurada en .env, recurrir al extractor inteligente
        if not self._has_valid_api_key():
            return self._extract_heuristically(raw_text, tax_percent_override, company_override)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Estructura el presupuesto de esta nota de trabajo en JSON estricto. "
                    "Asegúrate de que cada 'concepto' tenga SOLO el nombre limpio (sin precios, ni horas, ni etiquetas), "
                    "y que 'categoria' sea exactamente 'Mano de Obra' o 'Materiales':\n\n"
                    f"\"\"\"\n{raw_text}\n\"\"\""
                )
            }
        ]

        provider = self.provider
        content = ""

        try:
            if provider == "groq":
                from groq import Groq
                client = Groq(api_key=settings.GROQ_API_KEY)
                model_to_use = self.model if ("llama" in self.model or "mixtral" in self.model) else "llama-3.3-70b-versatile"
                
                response = client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,  # Baja temperatura para máxima adherencia al formato
                )
                content = response.choices[0].message.content

            else:  # Por defecto OpenAI
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                model_to_use = self.model if ("gpt" in self.model) else "gpt-4o-mini"
                
                response = client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = response.choices[0].message.content

        except Exception as exc:
            logger.warning(f"Error invocando LLM con {provider}: {exc}. Usando analizador de respaldo...", exc_info=True)
            return self._extract_heuristically(raw_text, tax_percent_override, company_override)

        # Parsear JSON devuelto
        try:
            cleaned_content = content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            data = json.loads(cleaned_content)
        except Exception as json_err:
            logger.error(f"Fallo al decodificar JSON del LLM: {content}")
            return self._extract_heuristically(raw_text, tax_percent_override, company_override)

        # Extraer campos de cliente
        client_data = data.get("client", {})
        client = ClientInfo(
            name=client_data.get("name") or "Cliente Particular",
            cif_nif=client_data.get("cif_nif") or "",
            address=client_data.get("address") or "",
            phone=client_data.get("phone") or "",
            email=client_data.get("email") or "",
            contact_person=client_data.get("contact_person") or "",
        )

        # Extraer y sanear estrictamente los ítems
        raw_items = data.get("items", [])
        items: List[BudgetItem] = []

        for item_data in raw_items:
            try:
                # Soportar tanto campos en español (concepto/categoria/cantidad) como inglés
                raw_concepto = (
                    item_data.get("concepto")
                    or item_data.get("description")
                    or item_data.get("nombre")
                    or "Concepto presupuestado"
                )
                clean_name = clean_concepto(str(raw_concepto))

                raw_cat = item_data.get("categoria") or item_data.get("category") or "Materiales"
                cat_lower = str(raw_cat).lower()
                categoria = "Mano de Obra" if any(k in cat_lower for k in ["obra", "mano", "hora", "instal", "mont", "serv", "técn"]) else "Materiales"

                cantidad = float(item_data.get("cantidad", item_data.get("quantity", 1.0)))
                precio_unitario = float(item_data.get("precio_unitario", item_data.get("unit_price", 0.0)))
                descuento = float(item_data.get("descuento_porcentaje", item_data.get("discount_percent", 0.0)))

                items.append(
                    BudgetItem(
                        description=clean_name,
                        category=categoria,
                        quantity=cantidad,
                        unit_price=precio_unitario,
                        discount_percent=descuento
                    )
                )
            except Exception as item_err:
                logger.warning(f"Error procesando item del LLM: {item_data} - {item_err}")

        if not items:
            items.append(
                BudgetItem(
                    description="Servicios técnicos y profesionales",
                    category="Mano de Obra",
                    quantity=1.0,
                    unit_price=100.0,
                    discount_percent=0.0
                )
            )

        company = company_override or CompanyInfo(
            name=settings.EMPRESA_NOMBRE,
            cif_nif=settings.EMPRESA_CIF,
            address=settings.EMPRESA_DIRECCION,
            phone=settings.EMPRESA_TELEFONO,
            email=settings.EMPRESA_EMAIL,
            web=settings.EMPRESA_WEB,
            iban=settings.EMPRESA_IBAN,
        )

        tax_percent = (
            tax_percent_override
            if tax_percent_override is not None
            else float(data.get("tax_percent", settings.DEFAULT_TAX_PERCENT))
        )

        budget_id = f"PRES-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"
        issue_date = date.today().strftime("%d/%m/%Y")
        valid_until = (date.today() + timedelta(days=settings.DEFAULT_VALIDITY_DAYS)).strftime("%d/%m/%Y")

        budget = Budget(
            budget_id=budget_id,
            title=data.get("title", f"Presupuesto Comercial para {client.name}"),
            issue_date=issue_date,
            valid_until=valid_until,
            client=client,
            company=company,
            items=items,
            currency=settings.DEFAULT_CURRENCY,
            currency_symbol="€" if settings.DEFAULT_CURRENCY == "EUR" else "$",
            tax_percent=tax_percent,
            payment_terms=data.get(
                "payment_terms",
                "50% al aceptar el presupuesto y 50% a la finalización de los trabajos mediante transferencia bancaria."
            ),
            notes=data.get(
                "notes",
                "Garantía de 12 meses sobre la mano de obra. Presupuesto válido según la fecha indicada."
            )
        )

        return budget


# Instancia única del servicio
ai_service = AIService()
