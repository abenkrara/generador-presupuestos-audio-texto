"""
Servicio de Generación de Presupuestos en PDF.
Utiliza Jinja2 para la inyección de datos en plantillas HTML y un motor de renderizado PDF robusto
(con soporte principal en WeasyPrint y fallback transparente en xhtml2pdf / pdfkit).
"""

import io
import os
import logging
from pathlib import Path
from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.budget import Budget

logger = logging.getLogger(__name__)

# Configuración de rutas de plantillas
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class PDFService:
    """Gestiona la renderización HTML con Jinja2 y la compilación a formato binario PDF."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"])
        )
        self.template_name = "budget_template.html"

    def render_html(self, budget: Budget) -> str:
        """Renderiza el documento HTML combinando la plantilla Jinja2 con el modelo Budget."""
        try:
            template = self.env.get_template(self.template_name)
            return template.render(budget=budget)
        except Exception as e:
            logger.error(f"Error renderizando plantilla Jinja2: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error renderizando plantilla HTML: {str(e)}")

    def generate_pdf(self, budget: Budget) -> bytes:
        """
        Genera el archivo PDF a partir del presupuesto.
        Prueba primero WeasyPrint (calidad editorial CSS3); si no está disponible o falta GTK,
        utiliza xhtml2pdf (100% Python nativo, compatible con cualquier sistema operativo).
        
        Args:
            budget: Modelo completo del presupuesto.
            
        Returns:
            bytes con el contenido del archivo PDF listo para enviar al cliente.
        """
        html_content = self.render_html(budget)

        # 1. Intentar compilar con WeasyPrint
        try:
            from weasyprint import HTML  # type: ignore
            logger.info("Generando PDF con WeasyPrint...")
            pdf_bytes = HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf()
            return pdf_bytes
        except (ImportError, OSError) as wp_err:
            logger.info(f"WeasyPrint no disponible o sin librerías nativas ({wp_err}). Usando motor xhtml2pdf...")

        # 2. Fallback a xhtml2pdf (Pure Python)
        try:
            from xhtml2pdf import pisa  # type: ignore
            logger.info("Generando PDF con xhtml2pdf...")
            pdf_buffer = io.BytesIO()
            pisa_status = pisa.CreatePDF(
                src=html_content,
                dest=pdf_buffer,
                encoding="utf-8"
            )

            if pisa_status.err:
                raise RuntimeError(f"xhtml2pdf reportó errores en la compilación: {pisa_status.err}")

            return pdf_buffer.getvalue()

        except ImportError:
            pass
        except Exception as pisa_err:
            logger.error(f"Error compilando con xhtml2pdf: {pisa_err}", exc_info=True)

        # 3. Fallback adicional con pdfkit si está instalado wkhtmltopdf
        try:
            import pdfkit  # type: ignore
            logger.info("Intentando compilar con pdfkit...")
            pdf_bytes = pdfkit.from_string(html_content, False)
            return pdf_bytes
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=(
                "No se encontró un motor de PDF funcional en el sistema. "
                "Por favor instala 'xhtml2pdf' (`pip install xhtml2pdf`) o las dependencias de 'weasyprint'."
            )
        )


# Instancia única del servicio
pdf_service = PDFService()

