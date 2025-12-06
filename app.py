import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
import plotly.express as px
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILO ---
st.set_page_config(page_title="Logistics Manager", layout="wide", initial_sidebar_state="collapsed")

# CSS PERSONALIZADO PARA DISEÑO MINIMALISTA Y ELEGANTE
st.markdown("""
    <style>
    /* Fuente y fondo general */
    .stApp {
        background-color: #FAFAFA;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    /* Estilo de las Métricas Superiores */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        text-align: center;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #666;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #1E88E5;
        font-weight: 700;
    }
    /* Limpiar encabezado */
    header {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    
    /* Estilo para la tabla de totales laterales */
    .weekly-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #3788d8;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .weekly-title { font-weight: bold; color: #333; font-size: 1rem; }
    .weekly-stat { font-size: 0.9rem; color: #555; display: flex; justify-content: space-between;}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN A BASE DE DATOS ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def cargar_datos():
    conn = get_connection()
    query = "SELECT * FROM registro_diario"
    df = pd.read_sql(query, conn)
    conn.close()
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
    return df

def guardar_registro(fecha, paquetes, masters, proveedor, comentarios):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
    INSERT INTO registro_diario (fecha, paquetes, masters, proveedor, comentarios)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    paquetes=%s, masters=%s, proveedor=%s, comentarios=%s
    """
    vals = (fecha, paquetes, masters, proveedor, comentarios, paquetes, masters, proveedor, comentarios)
    cursor.execute(query, vals)
    conn.commit()
    conn.close()

# --- 3. VENTANA MODAL (DIALOG) PARA INGRESO DE DATOS ---
@st.dialog("📝 Gestionar Registro")
def modal_registro(fecha_default, datos_existentes=None):
    # Si hay datos previos, pre-llenamos el formulario
    def_paq = datos_existentes['paquetes'] if datos_existentes else 0
    def_mast = datos_existentes['masters'] if datos_existentes else 0
    def_prov = datos_existentes['proveedor'] if datos_existentes else ""
    def_com = datos_existentes['comentarios'] if datos_existentes else ""

    st.write(f"Registro para el día: **{fecha_default}**")
    
    with st.form("form_modal"):
        c1, c2 = st.columns(2)
        paq = c1.number_input("Paquetes", min_value=0, value=def_paq, step=1)
        mast = c2.number_input("Másters", min_value=0, value=def_mast, step=1)
        prov = st.text_input("Proveedor", value=def_prov, placeholder="Ej. DHL, Fedex...")
        com = st.text_area("Comentarios", value=def_com, height=100)
        
        btn_guardar = st.form_submit_button("💾 Guardar Cambios", use_container_width=True)
        
        if btn_guardar:
            guardar_registro(fecha_default, paq, mast, prov, com)
            st.success("Guardado exitosamente")
            st.session_state['data_changed'] = True # Bandera para recargar
            st.rerun()

# --- 4. LÓGICA PRINCIPAL ---

# Estado para controlar recargas
if 'data_changed' not in st.session_state:
    st.session_state['data_changed'] = False

df = cargar_datos()

# --- SECCIÓN SUPERIOR: SELECTOR DE MES Y TOTALES GLOBALES ---
col_title, col_metrics = st.columns([1, 2])

with col_title:
    st.title("📅 Calendario")
    # Filtros de mes/año para calcular los totales globales de la vista
    hoy = date.today()
    c_mes, c_anio = st.columns(2)
    sel_mes = c_mes.selectbox("Mes", range(1, 13), index=hoy.month-1)
    sel_anio = c_anio.number_input("Año", value=hoy.year, step=1)

# Calcular totales del mes seleccionado
if not df.empty:
    df_mes = df[(df['fecha'].dt.month == sel_mes) & (df['fecha'].dt.year == sel_anio)]
    total_p = df_mes['paquetes'].sum()
    total_m = df_mes['masters'].sum()
else:
    df_mes = pd.DataFrame()
    total_p, total_m = 0, 0

with col_metrics:
    # Mostramos los totales GRANDES al lado del título
    m1, m2, m3 = st.columns(3)
    m1.metric("TOTAL PAQUETES (Mes)", f"{total_p:,}")
    m2.metric("TOTAL MÁSTERS (Mes)", f"{total_m:,}")
    m3.metric("Días Operativos", len(df_mes))

st.markdown("---")

# --- SECCIÓN CENTRAL: CALENDARIO Y TOTALES SEMANALES ---
col_cal, col_resumen = st.columns([3, 1], gap="medium")

with col_cal:
    # Preparar eventos
    events = []
    if not df.empty:
        for _, row in df.iterrows():
            events.append({
                "title": f"📦{row['paquetes']} | 🧱{row['masters']}",
                "start": row['fecha_str'],
                "allDay": True,
                "backgroundColor": "#FFFFFF", 
                "borderColor": "#E0E0E0",
                "textColor": "#333333",
                "extendedProps": {
                    "paquetes": row['paquetes'],
                    "masters": row['masters'],
                    "proveedor": row['proveedor'],
                    "comentarios": row['comentarios']
                }
            })

    # Opciones visuales del calendario (Minimalista)
    cal_options = {
        "editable": False,
        "selectable": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth"
        },
        "initialDate": f"{sel_anio}-{sel_mes:02d}-01", # Sincronizar con selectores
        "contentHeight": 650, # Calendario más grande
        "locale": "es" # Español
    }

    cal_state = calendar(events=events, options=cal_options, key="main_calendar")

    # DETECCIÓN DE CLICS (Para abrir la ventana modal)
    if cal_state.get("dateClick"):
        clicked_date = cal_state["dateClick"]["dateStr"]
        modal_registro(clicked_date)
        
    elif cal_state.get("eventClick"):
        # Si clica en un evento existente, abrimos modal con datos cargados
        clicked_event = cal_state["eventClick"]["event"]
        clicked_date = clicked_event["start"]
        props = clicked_event["extendedProps"]
        modal_registro(clicked_date, props)

with col_resumen:
    st.subheader("📊 Totales x Semana")
    st.markdown("Resumen de la vista actual")
    
    if not df_mes.empty:
        # Calcular semanas y totales
        df_mes['Semana'] = df_mes['fecha'].dt.isocalendar().week
        resumen_semanal = df_mes.groupby('Semana')[['paquetes', 'masters']].sum().sort_index()
        
        # Renderizar tarjetas bonitas por semana
        for semana, row in resumen_semanal.iterrows():
            st.markdown(f"""
            <div class="weekly-card">
                <div class="weekly-title">Semana {semana}</div>
                <hr style="margin: 5px 0;">
                <div class="weekly-stat"><span>📦 Paquetes:</span> <strong>{row['paquetes']}</strong></div>
                <div class="weekly-stat"><span>🧱 Másters:</span> <strong>{row['masters']}</strong></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No hay datos en este mes para mostrar resumen semanal.")

# --- PESTAÑA EXTRA DE ANÁLISIS (Abajo, separada) ---
st.markdown("---")
with st.expander("📈 Ver Dashboard Completo de Análisis Gráfico", expanded=False):
    if not df.empty:
        tab1, tab2 = st.tabs(["Evolución", "Por Proveedor"])
        with tab1:
            fig = px.bar(df_mes, x='fecha', y=['paquetes', 'masters'], barmode='group', title="Evolución Diaria del Mes")
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            prov_sum = df_mes.groupby('proveedor')['paquetes'].sum().reset_index()
            fig2 = px.pie(prov_sum, values='paquetes', names='proveedor', title="Distribución de Paquetes")
            st.plotly_chart(fig2, use_container_width=True)
