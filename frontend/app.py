"""
Frontend Streamlit - Generador de Presupuestos desde Audio y Texto.
Interfaz moderna, intuitiva y responsive para técnicos y comerciales en campo.
"""

import base64
import json
import os
import requests
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN GENERAL DE LA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="VoiceQuote | Presupuestos desde Audio o Texto",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyectar estilos CSS modernos (Glassmorphic & Clean Corporate)
st.markdown("""
<style>
    /* Estilos globales */
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3b82f6, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #64748b;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.7);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .badge-status {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-green {
        background-color: #dcfce7;
        color: #15803d;
    }
    .badge-red {
        background-color: #fee2e2;
        color: #b91c1c;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #1e1b4b;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# BARRA LATERAL: CONFIGURACIÓN DE EMPRESA Y BACKEND
# ==============================================================================
with st.sidebar:
    st.markdown("### 🏢 Tu Empresa Emisora")
    st.caption("Estos datos aparecerán en la cabecera y pie de tus presupuestos.")

    api_url = st.text_input("URL del Servidor API", value="http://localhost:8001")

    # Verificación de conexión con el backend
    try:
        health_resp = requests.get(f"{api_url}/api/health", timeout=1.5)
        if health_resp.status_code == 200:
            st.markdown('<span class="badge-status badge-green">● Backend Conectado</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-status badge-red">● Backend no responde</span>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<span class="badge-status badge-red">● Servidor Desconectado</span>', unsafe_allow_html=True)
        st.caption("Asegúrate de ejecutar: `uvicorn app.main:app --reload`")

    st.markdown("---")

    emp_nombre = st.text_input("Razón Social", value="Soluciones Técnicas & Comerciales S.L.")
    emp_cif = st.text_input("NIF / CIF", value="B-98765432")
    emp_dir = st.text_input("Dirección", value="Calle Innovación 45, Planta 2, 28001 Madrid")
    emp_tel = st.text_input("Teléfono", value="+34 912 345 678")
    emp_email = st.text_input("Email", value="contacto@solucionestecnicas.es")
    emp_iban = st.text_input("Cuenta IBAN para cobro", value="ES91 2100 0418 4502 0005 1332")
    default_tax = st.number_input("IVA por Defecto (%)", min_value=0.0, max_value=30.0, value=21.0, step=0.5)

    company_payload = {
        "name": emp_nombre,
        "cif_nif": emp_cif,
        "address": emp_dir,
        "phone": emp_tel,
        "email": emp_email,
        "web": "www.solucionestecnicas.es",
        "iban": emp_iban
    }


# ==============================================================================
# ESTADO DE SESIÓN
# ==============================================================================
if "current_budget" not in st.session_state:
    st.session_state.current_budget = None

if "last_transcription" not in st.session_state:
    st.session_state.last_transcription = ""

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None


# ==============================================================================
# PANEL PRINCIPAL
# ==============================================================================
st.markdown('<div class="main-title">💼 VoiceQuote - Presupuestos al Instante</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Graba un audio o escribe una nota rápida sobre el trabajo. La IA extraerá los datos y compilará un presupuesto en PDF impecable.</div>', unsafe_allow_html=True)

# Pestañas de Entrada: Audio vs Texto
tab_audio, tab_text = st.tabs(["🎙️ Grabar o Subir Audio", "✍️ Nota Rápida de Texto"])

# ------------------------------------------------------------------------------
# PESTAÑA 1: AUDIO
# ------------------------------------------------------------------------------
with tab_audio:
    st.markdown("#### 1. Captura de Voz")
    col_rec, col_up = st.columns([1, 1])

    audio_file_to_process = None

    with col_rec:
        st.markdown("**Opción A: Grabar directamente desde el micrófono**")
        # st.audio_input disponible en versiones modernas de Streamlit
        try:
            recorded_audio = st.audio_input("Pulsa para grabar tu nota de voz")
            if recorded_audio is not None:
                audio_file_to_process = recorded_audio
        except AttributeError:
            st.info("💡 Graba con la grabadora de tu móvil/PC y sube el archivo a la derecha.")

    with col_up:
        st.markdown("**Opción B: Subir archivo de audio existente**")
        uploaded_file = st.file_uploader(
            "Selecciona archivo de audio",
            type=["mp3", "m4a", "wav", "ogg", "webm", "aac"],
            help="Soporta notas de voz de WhatsApp, grabadora del móvil o archivos de audio estándar."
        )
        if uploaded_file is not None:
            audio_file_to_process = uploaded_file

    if audio_file_to_process is not None:
        st.audio(audio_file_to_process)
        if st.button("🚀 Transcribir y Generar Presupuesto", type="primary", use_container_width=True):
            with st.spinner("🎧 Transcribiendo audio con Whisper y estructurando conceptos comerciales..."):
                try:
                    # Enviar al endpoint de audio
                    files = {"file": (audio_file_to_process.name, audio_file_to_process.getvalue(), "audio/mpeg")}
                    data = {"tax_percent": str(default_tax)}
                    resp = requests.post(f"{api_url}/api/generate-budget-from-audio", files=files, data=data)

                    if resp.status_code == 200:
                        st.session_state.current_budget = resp.json()
                        # Inyectar datos de la empresa del sidebar
                        st.session_state.current_budget["company"] = company_payload
                        st.success("¡Presupuesto estructurado con éxito!")
                        st.rerun()
                    else:
                        st.error(f"Error del servidor ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.error(f"Fallo de conexión con el backend: {str(e)}")

# ------------------------------------------------------------------------------
# PESTAÑA 2: TEXTO RÁPIDO
# ------------------------------------------------------------------------------
with tab_text:
    st.markdown("#### 1. Nota de Texto o Apunte Comercial")
    
    # Plantillas de ejemplo para pruebas rápidas
    example_options = {
        "Seleccionar ejemplo de prueba...": "",
        "Reforma y Fontanería": (
            "Presupuesto para Juan Pérez en Calle Mayor 12. Necesita sustitución de bañera por plato de ducha de resina "
            "antideslizante de 120x70 por 350 euros. Incluir mano de obra de albañilería y fontanería, estimamos 16 horas "
            "a 35 euros la hora. Además mampara de cristal templado serigrafiada por 280 euros con un 10% de descuento. "
            "Desescombro y retirada al punto limpio 90 euros. Condiciones de pago: 40% al inicio y 60% al finalizar la instalación. "
            "Garantía de 2 años en estanqueidad."
        ),
        "Instalación de Paneles Solares": (
            "Cliente: Agroalimentaria del Sur S.A. CIF A-41223344. Dirección en Polígono Industrial Oeste nave 4, Sevilla. "
            "Instalación solar fotovoltaica autoconsumo 10kW. 22 paneles monocristalinos 450W a 140 euros cada uno. "
            "Inversor híbrido trifásico 10kW por 1850 euros. Estructura coplanar de aluminio para cubierta 600 euros. "
            "Mano de obra especializada montaje y legalización boletín eléctrico 1400 euros. Aplicar descuento especial de apertura "
            "del 5% en los paneles solares. Pago: 30% a la firma, 50% al montaje y 20% tras puesta en marcha."
        ),
        "Desarrollo Web & Marketing Digital": (
            "Presupuesto para Clínica Dental Sonrisas, contacto Dra. Marta Gómez, email info@clinicasonrisas.es. "
            "Diseño y desarrollo de web corporativa en WordPress con gestor de citas online: 1200 euros. "
            "Optimización SEO local y configuración de Google Business Profile: 350 euros. "
            "Redacción de textos persuasivos y copywriting médico: 8 horas a 45 euros/hora. "
            "Mantenimiento técnico y soporte durante el primer trimestre bonificado al 100%. "
            "Forma de pago: 50% al encargo y 50% tras publicación en dominio definitivo."
        )
    }

    selected_example = st.selectbox("Cargar ejemplo predefinido:", list(example_options.keys()))
    default_text_val = example_options[selected_example] if selected_example != "Seleccionar ejemplo de prueba..." else ""

    text_input = st.text_area(
        "Pega o escribe las notas del trabajo, cliente, precios y condiciones:",
        value=default_text_val,
        height=140,
        placeholder="Ej: Presupuesto para Carlos Gómez. Arreglar caldera Ferroli: cambio de vaso de expansión 120€, 3 horas de técnico a 45€/h, desplazamiento 30€. Pago al contado."
    )

    if st.button("🚀 Procesar Nota y Generar Presupuesto", type="primary", use_container_width=True):
        if not text_input or len(text_input.strip()) < 10:
            st.warning("Por favor introduce una descripción más detallada.")
        else:
            with st.spinner("🤖 Analizando notas comerciales con Inteligencia Artificial..."):
                try:
                    payload = {
                        "raw_text": text_input,
                        "tax_percent": default_tax,
                        "company_overrides": company_payload
                    }
                    resp = requests.post(f"{api_url}/api/generate-budget-from-text", json=payload)
                    if resp.status_code == 200:
                        st.session_state.current_budget = resp.json()
                        st.session_state.current_budget["company"] = company_payload
                        st.success("¡Presupuesto generado con éxito!")
                        st.rerun()
                    else:
                        st.error(f"Error del servidor ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.error(f"Fallo de conexión con el backend: {str(e)}")


# ==============================================================================
# SECCIÓN 2: REVISIÓN Y EDICIÓN DEL PRESUPUESTO
# ==============================================================================
if st.session_state.current_budget is not None:
    budget = st.session_state.current_budget

    st.markdown("---")
    st.markdown("### 📋 2. Revisión y Ajustes del Presupuesto")
    st.caption("Puedes modificar cualquier dato antes de compilar el documento final.")

    # Encabezado del documento
    col_id, col_title, col_valid = st.columns([2, 4, 2])
    with col_id:
        budget["budget_id"] = st.text_input("Código Presupuesto", value=budget.get("budget_id", ""))
    with col_title:
        budget["title"] = st.text_input("Título / Asunto", value=budget.get("title", ""))
    with col_valid:
        budget["valid_until"] = st.text_input("Válido Hasta", value=budget.get("valid_until", ""))

    # Datos del Cliente
    with st.expander("👤 Datos del Cliente Destinatario", expanded=True):
        c_col1, c_col2, c_col3 = st.columns(3)
        client = budget.get("client", {})
        with c_col1:
            client["name"] = st.text_input("Nombre / Razón Social", value=client.get("name", ""))
            client["cif_nif"] = st.text_input("NIF / CIF", value=client.get("cif_nif", ""))
        with c_col2:
            client["contact_person"] = st.text_input("Persona de Contacto", value=client.get("contact_person", ""))
            client["phone"] = st.text_input("Teléfono", value=client.get("phone", ""))
        with c_col3:
            client["email"] = st.text_input("Correo Electrónico", value=client.get("email", ""))
            client["address"] = st.text_input("Dirección de Obra / Fiscal", value=client.get("address", ""))
        budget["client"] = client

    # Partidas Presupuestadas (Tabla Dinámica y Editable)
    st.markdown("#### 📦 Conceptos y Partidas")
    items = budget.get("items", [])
    updated_items = []

    for idx, item in enumerate(items):
        with st.container():
            icol1, icol_cat, icol2, icol3, icol4, icol5 = st.columns([3.5, 1.8, 1.2, 1.5, 1.2, 1.8])
            with icol1:
                desc = st.text_input(
                    f"Concepto #{idx+1}",
                    value=item.get("description", item.get("concepto", "")),
                    key=f"desc_{idx}",
                    help="Nombre limpio del trabajo o material sin precios ni cantidades añadidas."
                )
            with icol_cat:
                raw_cat = item.get("category", item.get("categoria", "Materiales"))
                cat_idx = 0 if raw_cat == "Mano de Obra" else 1
                cat = st.selectbox(
                    f"Categoría #{idx+1}",
                    options=["Mano de Obra", "Materiales"],
                    index=cat_idx,
                    key=f"cat_{idx}"
                )
            with icol2:
                qty = st.number_input(
                    f"Cant.",
                    value=float(item.get("quantity", item.get("cantidad", 1.0))),
                    min_value=0.01,
                    step=0.5,
                    key=f"qty_{idx}"
                )
            with icol3:
                price = st.number_input(
                    f"P. Unit. (€)",
                    value=float(item.get("unit_price", item.get("precio_unitario", 0.0))),
                    min_value=0.0,
                    step=5.0,
                    key=f"prc_{idx}"
                )
            with icol4:
                dto = st.number_input(
                    f"Dto. (%)",
                    value=float(item.get("discount_percent", item.get("descuento_porcentaje", 0.0))),
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=f"dto_{idx}"
                )
            with icol5:
                line_subtotal = round(qty * price * (1 - dto / 100.0), 2)
                st.markdown(f"**Total Línea:**")
                st.markdown(f"### {line_subtotal:.2f} €")

            updated_items.append({
                "description": desc,
                "category": cat,
                "quantity": qty,
                "unit_price": price,
                "discount_percent": dto,
                "subtotal": line_subtotal
            })

    budget["items"] = updated_items

    # Recalcular totales con precisión matemática
    subtotal_calculado = round(sum(it["subtotal"] for it in updated_items), 2)
    tax_perc = float(budget.get("tax_percent", default_tax))
    tax_amount = round(subtotal_calculado * (tax_perc / 100.0), 2)
    total_general = round(subtotal_calculado + tax_amount, 2)

    raw_sin_dto = sum(round(it["quantity"] * it["unit_price"], 2) for it in updated_items)
    ahorro_dto = round(raw_sin_dto - subtotal_calculado, 2)

    budget["subtotal"] = subtotal_calculado
    budget["discount_total"] = ahorro_dto
    budget["tax_percent"] = tax_perc
    budget["tax_amount"] = tax_amount
    budget["total_amount"] = total_general
    budget["company"] = company_payload

    # Tarjetas de Totales Financieros
    st.markdown("#### 💰 Resumen Financiero")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Base Imponible", f"{subtotal_calculado:.2f} €")
    m2.metric("Ahorro Descuentos", f"-{ahorro_dto:.2f} €" if ahorro_dto > 0 else "0.00 €")
    m3.metric(f"I.V.A. ({tax_perc:.1f}%)", f"{tax_amount:.2f} €")
    m4.metric("TOTAL A PAGAR", f"{total_general:.2f} €")

    # Condiciones y Garantías
    with st.expander("📝 Condiciones de Pago y Cláusulas", expanded=False):
        budget["payment_terms"] = st.text_area("Condiciones de Pago", value=budget.get("payment_terms", ""))
        budget["notes"] = st.text_area("Garantías y Notas", value=budget.get("notes", ""))

    st.session_state.current_budget = budget

    # ==============================================================================
    # SECCIÓN 3: GENERACIÓN Y VISUALIZADOR DEL PDF
    # ==============================================================================
    st.markdown("---")
    st.markdown("### 🖨️ 3. Generar y Descargar Presupuesto en PDF")

    col_btn, col_down = st.columns([1, 1])

    with col_btn:
        if st.button("📄 Compilar Documento PDF Final", type="primary", use_container_width=True):
            with st.spinner("Generando PDF con diseño glassmorphism..."):
                try:
                    pdf_resp = requests.post(f"{api_url}/api/render-pdf", json=budget)
                    if pdf_resp.status_code == 200:
                        st.session_state.pdf_bytes = pdf_resp.content
                        st.success("¡PDF generado correctamente!")
                    else:
                        st.error(f"Fallo al compilar PDF ({pdf_resp.status_code}): {pdf_resp.text}")
                except Exception as e:
                    st.error(f"Error conectando al servicio de PDF: {str(e)}")

    with col_down:
        if st.session_state.pdf_bytes is not None:
            filename = f"{budget.get('budget_id', 'Presupuesto')}.pdf"
            st.download_button(
                label=f"⬇️ Descargar {filename}",
                data=st.session_state.pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )

    # Previsualización Embebida del PDF
    if st.session_state.pdf_bytes is not None:
        st.markdown("#### Vista Previa del Documento:")
        b64_pdf = base64.b64encode(st.session_state.pdf_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="700" type="application/pdf" style="border-radius: 8px; border: 1px solid #cbd5e1;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

