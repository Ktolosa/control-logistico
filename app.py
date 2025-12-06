import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Logístico", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS PARA ESTILO Y ALTURA ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Calendario Grande y Clickeable */
    .fc {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        height: 750px !important; 
    }
    
    /* Estilo Tarjetas de Semana (Derecha) */
    .week-card {
        background-color: #f8f9fa;
        border-left: 5px solid #2c3e50;
        padding: 12px;
        margin-bottom: 12px;
        border-radius: 5px;
        border: 1px solid #eee;
        border-left-width: 5px;
    }
    .week-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    .week-title { font-weight: bold; color: #2c3e50; font-size: 1rem; }
    .week-dates { font-size: 0.75rem; color: #666; font-weight: 500; text-transform: uppercase; margin-bottom: 8px; }
    
    .stat-row { display: flex; justify-content: space-between; font-size: 0.9rem; padding: 2px 0; border-bottom: 1px dashed #eee; }
    .val-paq { color: #2980b9; font-weight: bold; }
    .val-mast { color: #d35400; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN BASE DE DATOS ---
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
        df = pd.read_sql("SELECT * FROM registro_diario", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except:
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

# --- 4. CALCULAR FECHAS DE SEMANA (Lunes a Domingo) ---
def get_week_details(year, week_num):
    try:
        # Primer día de la semana (Lunes)
        d_start = date.fromisocalendar(year, week_num, 1)
        # Último día (Domingo)
        d_end = d_start + timedelta(days=6)
        
        meses = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 
                 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
        
        # Ejemplo: "02 Dic - 08 Dic"
        rango = f"{d_start.day} {meses[d_start.month]} - {d_end.day} {meses[d_end.month]}"
        return meses[d_start.month], rango
    except:
        return "", ""

# --- 5. VENTANA MODAL (POPUP) ---
@st.dialog("📝 Gestionar Día")
def modal_registro(fecha_str, datos=None):
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        st.markdown(f"### 📅 {fecha_obj.strftime('%d / %m / %Y')}")
    except:
        st.write(f"Fecha: {fecha_str}")

    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("mi_form"):
        c1, c2 = st.columns(2)
        paq = c1.number_input("📦 Paquetes", min_value=0, value=d_paq, step=1)
        mast = c2.number_input("🧱 Másters", min_value=0, value=d_mast, step=1)
        prov = st.text_input("🚚 Proveedor", value=d_prov, placeholder="Ej: DHL")
        com = st.text_area("💬 Notas", value=d_com)
        
        if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
            guardar_registro(fecha_str, paq, mast, prov, com)
            st.rerun()

# --- 6. INTERFAZ PRINCIPAL ---
df = cargar_datos()

st.title("Sistema de Control Logístico")

# Métricas rápidas arriba
if not df.empty:
    hoy = date.today()
    df_mes = df[df['fecha'].dt.month == hoy.month]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Paquetes (Mes)", f"{df_mes['paquetes'].sum():,}")
    col2.metric("🧱 Másters (Mes)", f"{df_mes['masters'].sum():,}")
    col3.metric("📅 Días con Datos", len(df_mes))
    prom = int(df_mes['paquetes'].mean()) if not df_mes.empty else 0
    col4.metric("📊 Promedio Diario", prom)

st.divider()

# Layout: Calendario (Izquierda) - Totales (Derecha)
col_cal, col_sidebar = st.columns([4, 1.2], gap="medium")

with col_cal:
    # Preparar eventos
    events = []
    if not df.empty:
        for _, row in df.iterrows():
            # Evento Azul (Paquetes)
            if row['paquetes'] > 0:
                events.append({
                    "title": f"📦 {row['paquetes']}",
                    "start": row['fecha_str'],
                    "backgroundColor": "#3788d8",
                    "borderColor": "#3788d8",
                    "allDay": True,
                    "extendedProps": {"paquetes": row['paquetes'], "masters": row['masters'], "proveedor": row['proveedor'], "comentarios": row['comentarios']}
                })
            # Evento Naranja (Masters)
            if row['masters'] > 0:
                events.append({
                    "title": f"🧱 {row['masters']}",
                    "start": row['fecha_str'],
                    "backgroundColor": "#e67e22",
                    "borderColor": "#e67e22",
                    "allDay": True,
                    "extendedProps": {"paquetes": row['paquetes'], "masters": row['masters'], "proveedor": row['proveedor'], "comentarios": row['comentarios']}
                })

    cal_options = {
        "editable": False,
        "selectable": True, # IMPORTANTE: Permite clic en celda vacía
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth"
        },
        "initialView": "dayGridMonth",
        "height": "750px",
        "locale": "es"
    }

    state = calendar(events=events, options=cal_options, key="mi_calendario")

    # --- LÓGICA DE CLIC SEGURA (AQUÍ ESTÁ EL ARREGLO) ---
    
    # 1. Obtenemos el objeto de clic de forma segura
    date_click = state.get("dateClick")
    event_click = state.get("eventClick")

    # 2. Verificamos explícitamente qué tipo de clic fue
    if date_click and isinstance(date_click, dict) and "dateStr" in date_click:
        # Clic en día vacío (Nuevo)
        modal_registro(date_click["dateStr"])
        
    elif event_click and isinstance(event_click, dict) and "event" in event_click:
        # Clic en evento (Editar)
        evento = event_click["event"]
        if "start" in evento:
            fecha_limpia = evento["start"].split("T")[0]
            props = evento.get("extendedProps", {})
            modal_registro(fecha_limpia, props)

with col_sidebar:
    st.subheader("🗓️ Totales Semana")
    st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
    
    if not df.empty:
        # Añadir columnas para agrupar
        df['year'] = df['fecha'].dt.year
        df['week'] = df['fecha'].dt.isocalendar().week
        
        # Agrupar datos (orden descendente para ver lo más nuevo arriba)
        resumen = df.groupby(['year', 'week'])[['paquetes', 'masters']].sum().sort_index(ascending=False)
        
        if resumen.empty:
            st.info("Sin datos recientes.")
        else:
            for (year, week), fila in resumen.iterrows():
                # Calcular fechas de inicio y fin de esa semana
                mes_nom, rango_fechas = get_week_details(year, week)
                
                st.markdown(f"""
                <div class="week-card">
                    <div class="week-header">
                        <span class="week-title">Semana {week} <span style="font-weight:normal; color:#555;">({mes_nom})</span></span>
                    </div>
                    <div class="week-dates">📅 {rango_fechas}</div>
                    
                    <div class="stat-row">
                        <span>📦 Paquetes</span>
                        <span class="val-paq">{fila['paquetes']}</span>
                    </div>
                    <div class="stat-row" style="border:none;">
                        <span>🧱 Másters</span>
                        <span class="val-mast">{fila['masters']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("👈 Registra datos en el calendario.")

st.divider()
with st.expander("📈 Ver Dashboard de Análisis"):
    if not df.empty:
        import plotly.express as px
        t1, t2 = st.tabs(["Evolución", "Proveedores"])
        with t1:
            fig = px.line(df, x='fecha', y=['paquetes', 'masters'], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with t2:
            st.bar_chart(df.groupby('proveedor')['paquetes'].sum())
