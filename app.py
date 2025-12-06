import streamlit as st
from streamlit_calendar import calendar
from datetime import date, timedelta
import utils # Tu archivo de conexión
import pandas as pd

# --- CONFIGURACIÓN VISUAL (CORREGIDA) ---
# Cambiamos a "expanded" para que siempre veas el menú lateral al entrar
st.set_page_config(page_title="Calendario Logístico", layout="wide", initial_sidebar_state="expanded")

# CSS MEJORADO: Fuerza la altura y mejora la visibilidad
st.markdown("""
    <style>
        /* Ajuste del contenedor principal */
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        
        /* Ocultar el menú hamburguesa de arriba a la derecha (opcional, para limpieza) */
        header { visibility: hidden; }
        
        /* Estilo para los botones del calendario */
        .fc-toolbar-title { font-size: 1.5rem !important; }
        .fc-button { background-color: #3788d8 !important; border: none !important; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIÓN: VENTANA EMERGENTE (MODAL) ---
@st.dialog("📝 Gestionar Día")
def modal_registro(fecha_seleccionada, datos=None):
    st.write(f"Gestionando fecha: **{fecha_seleccionada}**")
    
    # Valores por defecto
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        paq = c1.number_input("📦 Paquetes", min_value=0, value=d_paq, step=1)
        mast = c2.number_input("🧱 Másters", min_value=0, value=d_mast, step=1)
        prov = st.text_input("🚚 Proveedor", value=d_prov)
        com = st.text_area("💬 Comentarios", value=d_com)
        
        if st.form_submit_button("Guardar Cambios", use_container_width=True):
            utils.guardar_registro(fecha_seleccionada, paq, mast, prov, com)
            st.rerun()

# --- BARRA LATERAL (AYUDA Y DATOS) ---
with st.sidebar:
    st.title("⚙️ Opciones")
    st.info("👈 Para ir a los Gráficos, busca 'Dashboard' en este menú lateral.")
    
    st.write("---")
    st.write("**¿Calendario Vacío?**")
    if st.button("Generar Datos de Prueba 🎲"):
        # Generamos 5 datos aleatorios para probar
        fechas = [date.today() + timedelta(days=i) for i in range(-2, 3)]
        import random
        for f in fechas:
            utils.guardar_registro(
                f, 
                random.randint(100, 500), 
                random.randint(10, 50), 
                random.choice(["DHL", "FedEx", "Ups"]), 
                "Prueba automática"
            )
        st.success("¡Datos generados! Recargando...")
        st.rerun()

# --- LÓGICA PRINCIPAL ---
try:
    df = utils.cargar_datos()
except Exception as e:
    st.error("Error conectando a utils. Asegúrate de que utils.py existe.")
    df = pd.DataFrame()

# CABECERA Y TOTALES VISIBLES
hoy = date.today()
col_head1, col_head2 = st.columns([3, 1])

with col_head1:
    st.markdown(f"## 📅 Logística | {hoy.strftime('%B %Y')}")

with col_head2:
    if not df.empty:
        tot_p = df['paquetes'].sum()
        tot_m = df['masters'].sum()
        st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:10px; border-radius:10px; text-align:center;">
            <b>TOTAL GLOBAL</b><br>
            📦 {tot_p:,} | 🧱 {tot_m:,}
        </div>
        """, unsafe_allow_html=True)

# PREPARACIÓN DE EVENTOS
events = []
if not df.empty:
    # 1. Eventos Diarios
    for _, row in df.iterrows():
        events.append({
            "title": f"📦{row['paquetes']} | 🧱{row['masters']}",
            "start": row['fecha_str'],
            "color": "#3788d8",
            "extendedProps": {
                "type": "data",
                "paquetes": row['paquetes'],
                "masters": row['masters'],
                "proveedor": row['proveedor'],
                "comentarios": row['comentarios']
            }
        })
    
    # 2. Resumen Semanal (Totales al final de la semana)
    df['year_week'] = df['fecha'].dt.strftime('%Y-%U')
    resumen = df.groupby('year_week')[['paquetes', 'masters']].sum()
    
    for year_week, row in resumen.iterrows():
        # Aproximación visual para poner el total en el último día registrado de esa semana
        last_date = df[df['year_week'] == year_week]['fecha'].max().strftime('%Y-%m-%d')
        
        events.append({
            "title": f"∑ SEM: 📦{row['paquetes']} | 🧱{row['masters']}",
            "start": last_date,
            "color": "#262730", # Negro/Gris oscuro
            "display": "block",
            "textColor": "#FFF",
            "extendedProps": {"type": "summary"}
        })

# CONFIGURACIÓN DEL CALENDARIO (AQUÍ ESTÁ EL ARREGLO VISUAL)
cal_options = {
    "editable": False,
    "selectable": True,
    "headerToolbar": {
        "left": "today prev,next",
        "center": "title",
        "right": "dayGridMonth,listWeek" 
    },
    "initialView": "dayGridMonth",
    "height": "750px", # <--- ESTO ARREGLA EL PROBLEMA DE QUE SE VEA APLASTADO
    "locale": "es"
}

state = calendar(events=events, options=cal_options, key="main_cal")

# MANEJO DE CLICS
if state.get("dateClick"):
    date_clicked = state["dateClick"]["dateStr"]
    modal_registro(date_clicked)

elif state.get("eventClick"):
    event = state["eventClick"]["event"]
    props = event.get("extendedProps", {})
    if props.get("type") == "data":
        fecha = event["start"].split("T")[0]
        modal_registro(fecha, props)
