import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, timedelta
import plotly.express as px
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Logístico", layout="wide", initial_sidebar_state="expanded")

# --- 2. ESTILOS CSS (Aquí arreglamos el problema de altura) ---
st.markdown("""
    <style>
    /* 1. Forzar altura del calendario para que no se vea vacío */
    .fc {
        height: 750px !important; /* Altura fija obligatoria */
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 2. Estilo de las tarjetas de métricas */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px;
        border-radius: 8px;
    }
    
    /* 3. Ocultar espacios vacíos extra */
    .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN A BASE DE DATOS (Integrada) ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def cargar_datos():
    try:
        conn = get_connection()
        query = "SELECT * FROM registro_diario"
        df = pd.read_sql(query, conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        # Si falla la conexión, devolvemos DataFrame vacío para no romper la app
        return pd.DataFrame()

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

# --- 4. VENTANA EMERGENTE (MODAL) ---
@st.dialog("📝 Editar Registro")
def modal_registro(fecha_sel, datos=None):
    st.write(f"Gestionando fecha: **{fecha_sel}**")
    
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("entry_form"):
        c1, c2 = st.columns(2)
        paq = c1.number_input("📦 Paquetes", min_value=0, value=d_paq)
        mast = c2.number_input("🧱 Másters", min_value=0, value=d_mast)
        prov = st.text_input("🚚 Proveedor", value=d_prov)
        com = st.text_area("💬 Comentarios", value=d_com)
        
        if st.form_submit_button("💾 Guardar"):
            guardar_registro(fecha_sel, paq, mast, prov, com)
            st.rerun()

# --- 5. LOGICA PRINCIPAL (MENÚ LATERAL) ---
df = cargar_datos()

# CREAMOS EL MENÚ DE NAVEGACIÓN MANUALMENTE
st.sidebar.title("Navegación")
opcion = st.sidebar.radio("Ir a:", ["📅 Calendario", "📊 Dashboard de Análisis"], index=0)

st.sidebar.markdown("---")
# Botón de emergencia para llenar datos si la tabla está vacía
if st.sidebar.button("🛠️ Generar Datos de Prueba"):
    import random
    fechas = [date.today() + timedelta(days=i) for i in range(-5, 5)]
    for f in fechas:
        guardar_registro(f, random.randint(100,800), random.randint(10,50), 
                         random.choice(['DHL', 'FedEx', 'UPS']), "Dato de prueba")
    st.sidebar.success("¡Datos creados! Recargando...")
    st.rerun()

# --- VISTA 1: CALENDARIO ---
if opcion == "📅 Calendario":
    # Cabecera con totales rápidos
    c_title, c_kpi = st.columns([2, 1])
    with c_title:
        st.title(f"Calendario Logístico | {date.today().strftime('%B %Y')}")
    with c_kpi:
        if not df.empty:
            st.metric("Total Global", f"📦 {df['paquetes'].sum():,}")

    # Preparar Eventos
    events = []
    if not df.empty:
        # Eventos Diarios
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
        
        # Eventos de Resumen Semanal
        df['year_week'] = df['fecha'].dt.strftime('%Y-%U')
        resumen = df.groupby('year_week')[['paquetes', 'masters']].sum()
        for yw, row in resumen.iterrows():
            last_date = df[df['year_week'] == yw]['fecha'].max().strftime('%Y-%m-%d')
            events.append({
                "title": f"∑: 📦{row['paquetes']} | 🧱{row['masters']}",
                "start": last_date,
                "color": "#212529", # Negro
                "display": "block",
                "extendedProps": {"type": "summary"}
            })

    # CONFIGURACIÓN DEL CALENDARIO (CSS Height arreglado)
    cal_options = {
        "editable": False,
        "selectable": True,
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
        "initialView": "dayGridMonth",
        "locale": "es"
    }

    # Renderizar Calendario
    state = calendar(events=events, options=cal_options, key="mi_calendario")

    # Manejar Clics
    if state.get("dateClick"):
        clicked_data = state["dateClick"]
        if isinstance(clicked_data, dict) and "dateStr" in clicked_data:
            modal_registro(clicked_data["dateStr"])
            
    elif state.get("eventClick"):
        clicked_event = state["eventClick"]
        if isinstance(clicked_event, dict) and "event" in clicked_event:
            ev = clicked_event["event"]
            if ev.get("extendedProps", {}).get("type") == "data":
                date_part = ev["start"].split("T")[0]
                modal_registro(date_part, ev["extendedProps"])

# --- VISTA 2: DASHBOARD ---
elif opcion == "📊 Dashboard de Análisis":
    st.title("Tablero de Control e Inteligencia")
    
    if df.empty:
        st.warning("No hay datos registrados. Ve al Calendario y registra actividad.")
    else:
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            mes = st.selectbox("Mes", range(1,13), index=date.today().month-1)
        with col_f2:
            anio = st.number_input("Año", value=date.today().year)
            
        df_filt = df[(df['fecha'].dt.month == mes) & (df['fecha'].dt.year == anio)]
        
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Paquetes (Mes)", df_filt['paquetes'].sum())
        k2.metric("Másters (Mes)", df_filt['masters'].sum())
        k3.metric("Promedio Diario", int(df_filt['paquetes'].mean()) if not df_filt.empty else 0)
        k4.metric("Días Operados", len(df_filt))
        
        st.markdown("---")
        
        # Gráficas
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Tendencia Mensual")
            fig = px.line(df_filt, x='fecha', y=['paquetes', 'masters'], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("Proveedores")
            df_prov = df_filt.groupby('proveedor')['paquetes'].sum().reset_index()
            fig2 = px.pie(df_prov, values='paquetes', names='proveedor', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
            
        st.subheader("Resumen Semanal")
        df_filt['Semana'] = df_filt['fecha'].dt.isocalendar().week
        st.bar_chart(df_filt.groupby('Semana')['paquetes'].sum())
