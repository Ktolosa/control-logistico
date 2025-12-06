import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Logístico", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS PARA CORREGIR VISUALES ---
st.markdown("""
    <style>
    /* Ajuste del contenedor general */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Estilo para Forzar Altura y Diseño del Calendario */
    .fc {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        height: 750px !important; /* Altura Fija */
    }
    
    /* Estilo para las tarjetas de totales a la derecha */
    div.css-1r6slb0 {border: none;} /* Quitar bordes extra de streamlit */
    
    .week-card {
        background-color: #f8f9fa;
        border-left: 5px solid #2c3e50;
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 4px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .week-title { font-weight: bold; color: #333; font-size: 1rem; margin-bottom: 5px;}
    .week-data { display: flex; justify-content: space-between; font-size: 0.9rem;}
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
    except Exception as e:
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
    cursor.execute(query, (fecha, paquetes, masters, proveedor, comentarios, paquetes, masters, proveedor, comentarios))
    conn.commit()
    conn.close()

# --- 4. VENTANA MODAL (SOLUCIÓN FLOTANTE) ---
@st.dialog("📝 Gestionar Registro")
def modal_registro(fecha_str, datos=None):
    # Convertimos string a fecha para mostrarlo bonito en el título
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        st.markdown(f"### {fecha_obj.strftime('%d de %B, %Y')}")
    except:
        st.markdown(f"### {fecha_str}")
        fecha_obj = fecha_str # Fallback

    # Datos por defecto (si es nuevo o edición)
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("form_edicion"):
        col1, col2 = st.columns(2)
        nuevo_paq = col1.number_input("📦 Paquetes", min_value=0, value=d_paq, step=1)
        nuevo_mast = col2.number_input("🧱 Másters", min_value=0, value=d_mast, step=1)
        nuevo_prov = st.text_input("🚚 Proveedor", value=d_prov, placeholder="Ej. DHL")
        nuevo_com = st.text_area("💬 Notas", value=d_com)
        
        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
            guardar_registro(fecha_str, nuevo_paq, nuevo_mast, nuevo_prov, nuevo_com)
            st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---
df = cargar_datos()

# Título y Métricas Globales (Arriba)
st.title("Sistema de Control Logístico")

if not df.empty:
    hoy = date.today()
    df_mes = df[df['fecha'].dt.month == hoy.month]
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📦 Paquetes (Este Mes)", f"{df_mes['paquetes'].sum():,}")
    k2.metric("🧱 Másters (Este Mes)", f"{df_mes['masters'].sum():,}")
    k3.metric("Promedio Diario", int(df_mes['paquetes'].mean()) if not df_mes.empty else 0)
    k4.metric("Días Operados", len(df_mes))

st.divider()

# --- LAYOUT DIVIDIDO: CALENDARIO (Izquierda) | TOTALES (Derecha) ---
# Usamos proporción 4:1 para dar buen espacio al calendario
col_calendario, col_sidebar_totales = st.columns([4, 1], gap="medium")

with col_calendario:
    # Preparar eventos para el calendario visual
    events = []
    if not df.empty:
        for _, row in df.iterrows():
            # Evento Azul: Paquetes
            if row['paquetes'] > 0:
                events.append({
                    "title": f"📦 {row['paquetes']}",
                    "start": row['fecha_str'],
                    "backgroundColor": "#3788d8",
                    "borderColor": "#3788d8",
                    "allDay": True,
                    "extendedProps": {
                        "paquetes": row['paquetes'], "masters": row['masters'],
                        "proveedor": row['proveedor'], "comentarios": row['comentarios']
                    }
                })
            # Evento Naranja: Másters
            if row['masters'] > 0:
                events.append({
                    "title": f"🧱 {row['masters']}",
                    "start": row['fecha_str'],
                    "backgroundColor": "#f39c12",
                    "borderColor": "#f39c12",
                    "allDay": True,
                    # No repetimos props aquí para evitar duplicar logica de clic
                })

    cal_options = {
        "editable": False,
        "selectable": True, # ¡CRUCIAL PARA PODER DAR CLIC!
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,listWeek"
        },
        "initialView": "dayGridMonth",
        "height": "750px",
        "locale": "es"
    }

    state = calendar(events=events, options=cal_options, key="calendario_principal")

    # --- LÓGICA DE CLIC CORREGIDA (SOLUCIÓN KEYERROR) ---
    # Verificamos cuidadosamente qué devolvió el componente antes de acceder
    
    # CASO 1: Clic en celda vacía (Date Click)
    if state.get("dateClick") is not None:
        click_data = state["dateClick"]
        if isinstance(click_data, dict) and "dateStr" in click_data:
            fecha_clic = click_data["dateStr"]
            modal_registro(fecha_clic)

    # CASO 2: Clic en evento existente (Event Click)
    elif state.get("eventClick") is not None:
        click_data = state["eventClick"]
        if isinstance(click_data, dict) and "event" in click_data:
            evento = click_data["event"]
            fecha_clic = evento["start"].split("T")[0] # Limpiar la T de tiempo
            
            # Buscar datos guardados (props)
            props = evento.get("extendedProps", {})
            modal_registro(fecha_clic, props)

with col_sidebar_totales:
    st.subheader("📊 Totales Semana")
    st.write("Resumen acumulado:")
    
    if not df.empty:
        # Calcular semana del año
        df['semana_num'] = df['fecha'].dt.isocalendar().week
        # Agrupar datos por semana
        resumen = df.groupby('semana_num')[['paquetes', 'masters']].sum().sort_index(ascending=False)
        
        # Mostrar como tarjetas HTML limpias
        for semana, fila in resumen.iterrows():
            st.markdown(f"""
            <div class="week-card">
                <div class="week-title">Semana {semana}</div>
                <div class="week-data">
                    <span style="color:#0056b3;">📦 {fila['paquetes']} Paq</span>
                    <span style="color:#d35400;">🧱 {fila['masters']} Mast</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.info("Registra datos en el calendario para ver los totales aquí.")

# --- SECCIÓN EXTRA: DASHBOARD (Abajo) ---
st.divider()
with st.expander("📈 Ver Gráficos de Análisis Detallado"):
    if not df.empty:
        import plotly.express as px
        tab1, tab2 = st.tabs(["Evolución Diaria", "Por Proveedor"])
        with tab1:
            fig = px.line(df, x='fecha', y=['paquetes', 'masters'], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            prov = df.groupby('proveedor')['paquetes'].sum().reset_index()
            fig2 = px.pie(prov, values='paquetes', names='proveedor')
            st.plotly_chart(fig2, use_container_width=True)
