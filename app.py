import streamlit as st
from streamlit_calendar import calendar
from datetime import date
import utils # Importamos nuestro archivo de lógica
import pandas as pd

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Calendario Logístico", layout="wide", initial_sidebar_state="collapsed")

# CSS para ocultar elementos innecesarios y maximizar el calendario
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem; }
        header { visibility: hidden; }
        /* Estilo para el modal */
        div[data-testid="stDialog"] { border-radius: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- MODAL DE INGRESO DE DATOS ---
@st.dialog("📝 Gestionar Día")
def modal_registro(fecha_seleccionada, datos=None):
    st.write(f"Fecha: **{fecha_seleccionada}**")
    
    # Valores por defecto
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        paq = c1.number_input("Paquetes", min_value=0, value=d_paq)
        mast = c2.number_input("Másters", min_value=0, value=d_mast)
        prov = st.text_input("Proveedor", value=d_prov)
        com = st.text_area("Comentarios", value=d_com)
        
        if st.form_submit_button("Guardar Cambios", use_container_width=True):
            utils.guardar_registro(fecha_seleccionada, paq, mast, prov, com)
            st.rerun()

# --- LÓGICA PRINCIPAL ---
df = utils.cargar_datos()

# 1. HEADER CON TOTALES GENERALES DEL MES VISIBLE (Aproximado al mes actual por defecto)
# Nota: Para filtrar totales exactos por navegación de calendario se requiere JS avanzado, 
# aquí usamos el mes actual o todos los datos para simplificar la vista "Total Global".
hoy = date.today()
col_head1, col_head2 = st.columns([3, 1])

with col_head1:
    st.markdown(f"### 📅 Sistema Logístico | {hoy.strftime('%B %Y')}")

with col_head2:
    if not df.empty:
        # Mostramos totales globales simples en la cabecera
        tot_p = df['paquetes'].sum()
        tot_m = df['masters'].sum()
        st.markdown(f"""
        <div style="text-align: right; font-size: 0.9rem; color: #555;">
            <b>TOTAL GLOBAL:</b> 📦 {tot_p:,} | 🧱 {tot_m:,}
        </div>
        """, unsafe_allow_html=True)

# 2. PREPARACIÓN DE EVENTOS (DATOS + TOTALES SEMANALES)
events = []
if not df.empty:
    # A) Eventos Diarios (Los registros normales)
    for _, row in df.iterrows():
        events.append({
            "title": f"📦{row['paquetes']} | 🧱{row['masters']}",
            "start": row['fecha_str'],
            "color": "#3788d8", # Azul
            "extendedProps": {
                "type": "data",
                "paquetes": row['paquetes'],
                "masters": row['masters'],
                "proveedor": row['proveedor'],
                "comentarios": row['comentarios']
            }
        })
    
    # B) Eventos de Resumen Semanal (INTEGRADOS VISUALMENTE)
    # Agrupamos por semana y año para crear una "ficha" de total en el Domingo
    df['year_week'] = df['fecha'].dt.strftime('%Y-%U')
    resumen_semanal = df.groupby('year_week')[['paquetes', 'masters']].sum()
    
    for year_week, row in resumen_semanal.iterrows():
        # Encontrar el domingo de esa semana para poner la ficha ahí
        anio = int(year_week.split('-')[0])
        semana = int(year_week.split('-')[1])
        # Calculamos fecha aproximada del domingo (fin de semana)
        # Nota: Esto es una aproximación para visualización
        sunday_str = df[df['year_week'] == year_week]['fecha'].max().strftime('%Y-%m-%d')
        
        events.append({
            "title": f"∑ SEMANA: 📦{row['paquetes']} | 🧱{row['masters']}",
            "start": sunday_str,
            "color": "#2C3E50", # Gris oscuro / Negro para diferenciar
            "display": "block", # Bloque solido
            "textColor": "#ffffff",
            "extendedProps": {"type": "summary"} # Marcamos que es un resumen
        })

# 3. CONFIGURACIÓN DEL CALENDARIO
cal_options = {
    "editable": False,
    "selectable": True,
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth"
    },
    "initialView": "dayGridMonth",
    "height": "85vh", # Ocupa el 85% de la altura de la pantalla
    "locale": "es"
}

state = calendar(events=events, options=cal_options, key="main_cal")

# 4. MANEJO DE CLICS
if state.get("dateClick"):
    # Clic en celda vacía
    date_clicked = state["dateClick"]["dateStr"]
    modal_registro(date_clicked)

elif state.get("eventClick"):
    # Clic en un evento
    event = state["eventClick"]["event"]
    props = event.get("extendedProps", {})
    
    # Solo abrimos modal si es un dato real, no un resumen semanal
    if props.get("type") == "data":
        fecha = event["start"].split("T")[0]
        modal_registro(fecha, props)
