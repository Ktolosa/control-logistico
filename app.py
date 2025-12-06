import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, timedelta, datetime
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN E IMPORTACIONES ---
st.set_page_config(page_title="Gestión Logística", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS AVANZADO (PARA INTEGRACIÓN VISUAL) ---
st.markdown("""
    <style>
    /* Ajustes generales */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Estilo del Calendario */
    .fc {
        background-color: white;
        border-radius: 8px 0 0 8px; /* Bordes redondeados solo a la izquierda */
        box-shadow: -2px 2px 5px rgba(0,0,0,0.05);
        border-right: none;
    }
    .fc-toolbar-title { font-size: 1.2rem !important; text-transform: capitalize; }
    .fc-col-header-cell { background-color: #f8f9fa; padding: 10px 0; }
    
    /* Estilo de la Columna de Totales (Lateral) */
    .totals-sidebar {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
        border-left: none;
        border-radius: 0 8px 8px 0; /* Bordes redondeados solo a la derecha */
        height: 750px; /* Misma altura forzada que el calendario */
        padding: 10px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }
    
    .total-card {
        background-color: white;
        border-left: 4px solid #2c3e50;
        padding: 10px;
        margin-bottom: 15px; /* Espacio para intentar alinear con las semanas */
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-size: 0.85rem;
    }
    .total-card h4 { margin: 0 0 5px 0; font-size: 0.9rem; color: #333; }
    .stat-row { display: flex; justify-content: space-between; margin-bottom: 2px; }
    .stat-label { color: #666; }
    .stat-val { font-weight: bold; }
    
    /* Estilo de métricas superiores */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. BASE DE DATOS ---
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
    cursor.execute(query, (fecha, paquetes, masters, proveedor, comentarios, paquetes, masters, proveedor, comentarios))
    conn.commit()
    conn.close()

# --- 4. VENTANA FLOTANTE (SOLUCIÓN CLIC) ---
@st.dialog("📝 Editar Registro")
def modal_registro(fecha_sel, datos=None):
    # Convertir string a objeto date para mostrar bonito
    fecha_obj = datetime.strptime(fecha_sel, '%Y-%m-%d').date()
    st.markdown(f"### 📅 {fecha_obj.strftime('%A %d de %B, %Y')}")
    
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("entry_form"):
        c1, c2 = st.columns(2)
        paq = c1.number_input("📦 Cantidad Paquetes", min_value=0, value=d_paq, step=1)
        mast = c2.number_input("🧱 Cantidad Másters", min_value=0, value=d_mast, step=1)
        prov = st.text_input("🚚 Proveedor", value=d_prov, placeholder="Ej: DHL")
        com = st.text_area("💬 Comentarios / Incidencias", value=d_com)
        
        col_b1, col_b2 = st.columns([1,1])
        with col_b1:
            if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
                guardar_registro(fecha_sel, paq, mast, prov, com)
                st.rerun()

# --- 5. LOGICA PRINCIPAL ---
df = cargar_datos()

# --- CABECERA DE TOTALES GLOBALES ---
st.title("Sistema de Control Logístico")

if not df.empty:
    # Filtros rápidos para métricas
    hoy = date.today()
    mes_actual = hoy.month
    df_mes = df[df['fecha'].dt.month == mes_actual]
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Paquetes (Mes)", f"{df_mes['paquetes'].sum():,}")
    m2.metric("🧱 Másters (Mes)", f"{df_mes['masters'].sum():,}")
    m3.metric("📅 Días Operados", len(df_mes))
    m4.metric("📊 Promedio Diario", f"{int(df_mes['paquetes'].mean()) if not df_mes.empty else 0}")

st.divider()

# --- LAYOUT PRINCIPAL: CALENDARIO + COLUMNA TOTALES ---
col_cal, col_totales = st.columns([5, 1], gap="small")

with col_cal:
    events = []
    if not df.empty:
        for _, row in df.iterrows():
            # EVENTO 1: PAQUETES (AZUL)
            if row['paquetes'] > 0:
                events.append({
                    "title": f"📦 {row['paquetes']}",
                    "start": row['fecha_str'],
                    "color": "#3788d8", # Azul
                    "textColor": "white",
                    "allDay": True,
                    "extendedProps": {
                        "paquetes": row['paquetes'], "masters": row['masters'],
                        "proveedor": row['proveedor'], "comentarios": row['comentarios']
                    }
                })
            # EVENTO 2: MASTERS (NARANJA) - SEPARADO PARA MEJOR DISEÑO
            if row['masters'] > 0:
                events.append({
                    "title": f"🧱 {row['masters']}",
                    "start": row['fecha_str'],
                    "color": "#f39c12", # Naranja
                    "textColor": "white",
                    "allDay": True,
                    "extendedProps": {
                        "paquetes": row['paquetes'], "masters": row['masters'],
                        "proveedor": row['proveedor'], "comentarios": row['comentarios']
                    }
                })
            # Si ambos son 0 pero hay registro (comentario), ponemos gris
            if row['paquetes'] == 0 and row['masters'] == 0:
                events.append({
                    "title": "📝 Nota",
                    "start": row['fecha_str'],
                    "color": "#95a5a6",
                    "extendedProps": {
                        "paquetes": row['paquetes'], "masters": row['masters'],
                        "proveedor": row['proveedor'], "comentarios": row['comentarios']
                    }
                })

    cal_options = {
        "editable": False,
        "selectable": True, # IMPORTANTE PARA EL CLIC
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth"
        },
        "initialView": "dayGridMonth",
        "height": "750px", # Altura fija sincronizada
        "locale": "es",
        "dayMaxEvents": 3 # Si hay más de 3, muestra "+more"
    }

    state = calendar(events=events, options=cal_options, key="mi_calendario_pro")

    # --- LÓGICA DE DETECCIÓN DE CLIC MEJORADA ---
    if state.get("dateClick"):
        # Clic en celda vacía
        fecha = state["dateClick"]["dateStr"]
        modal_registro(fecha)
    
    elif state.get("eventClick"):
        # Clic en un evento existente
        datos_evento = state["eventClick"]["event"]
        fecha = datos_evento["start"].split("T")[0]
        # Recuperamos los datos guardados en 'extendedProps'
        props = datos_evento.get("extendedProps", {})
        modal_registro(fecha, props)

with col_totales:
    st.markdown('<div class="totals-sidebar">', unsafe_allow_html=True)
    st.markdown("### 🗓️ Totales Semanales")
    st.markdown("<small>Resumen de la vista actual</small><hr>", unsafe_allow_html=True)
    
    if not df.empty:
        # Calcular semanas presentes en los datos
        df['semana'] = df['fecha'].dt.isocalendar().week
        # Agrupamos
        resumen = df.groupby('semana')[['paquetes', 'masters']].sum().sort_index()
        
        # Generamos las "Tarjetas" visuales
        if resumen.empty:
            st.info("Sin datos")
        else:
            for semana, fila in resumen.iterrows():
                st.markdown(f"""
                <div class="total-card">
                    <h4>Semana {semana}</h4>
                    <div class="stat-row">
                        <span class="stat-label">📦 Paq:</span>
                        <span class="stat-val">{fila['paquetes']}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">🧱 Mast:</span>
                        <span class="stat-val">{fila['masters']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.write("Registra datos para ver totales.")
    
    st.markdown('</div>', unsafe_allow_html=True)
