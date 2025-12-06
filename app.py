import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Logístico", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS MEJORADO ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Calendario con altura forzada y celdas interactivas */
    .fc {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        height: 750px !important; 
    }
    
    /* Asegurar que los días vacíos reaccionen al cursor */
    .fc-daygrid-day-frame { cursor: pointer; } 

    /* Estilo Tarjetas de Semana (Lateral) */
    .week-card {
        background-color: #ffffff;
        border-left: 5px solid #2c3e50;
        border-right: 1px solid #eee;
        border-top: 1px solid #eee;
        border-bottom: 1px solid #eee;
        padding: 12px;
        margin-bottom: 12px;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .week-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .week-title { font-weight: 800; color: #2c3e50; font-size: 1rem; }
    .week-dates { font-size: 0.75rem; color: #888; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;}
    
    .stat-row { 
        display: flex; justify-content: space-between; 
        font-size: 0.9rem; margin-top: 4px; border-bottom: 1px dashed #eee; padding-bottom: 4px;
    }
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
    # Insertar o Actualizar
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

# --- 4. FUNCIONES DE FECHA (SEMANAS EN ESPAÑOL) ---
def get_week_details(year, week_num):
    """Calcula fecha inicio (lun) y fin (dom) de una semana ISO"""
    try:
        # Primer día de la semana (Lunes)
        d_start = date.fromisocalendar(year, week_num, 1)
        # Último día de la semana (Domingo)
        d_end = d_start + timedelta(days=6)
        
        # Diccionario manual de meses para asegurar español
        meses = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 
                 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
        
        mes_nombre = meses[d_start.month]
        
        # Formato: "01 Dic - 07 Dic"
        rango = f"{d_start.day} {meses[d_start.month]} - {d_end.day} {meses[d_end.month]}"
        return mes_nombre, rango
    except:
        return "", ""

# --- 5. VENTANA MODAL ---
@st.dialog("📝 Gestionar Día")
def modal_registro(fecha_str, datos=None):
    # Intentar parsear la fecha para título bonito
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        meses_full = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        titulo = f"{fecha_obj.day} de {meses_full[fecha_obj.month]}, {fecha_obj.year}"
    except:
        titulo = fecha_str

    st.markdown(f"### 📅 {titulo}")
    
    # Precarga de datos (si es edición) o ceros (si es nuevo)
    d_paq = datos['paquetes'] if datos else 0
    d_mast = datos['masters'] if datos else 0
    d_prov = datos['proveedor'] if datos else ""
    d_com = datos['comentarios'] if datos else ""

    with st.form("mi_formulario"):
        c1, c2 = st.columns(2)
        paq = c1.number_input("📦 Paquetes", min_value=0, value=d_paq, step=1)
        mast = c2.number_input("🧱 Másters", min_value=0, value=d_mast, step=1)
        prov = st.text_input("🚚 Proveedor", value=d_prov, placeholder="Ej. DHL")
        com = st.text_area("💬 Comentarios", value=d_com)
        
        if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
            guardar_registro(fecha_str, paq, mast, prov, com)
            st.rerun()

# --- 6. INTERFAZ PRINCIPAL ---
df = cargar_datos()

# Título y KPIs
st.title("Sistema de Control Logístico")
if not df.empty:
    hoy = date.today()
    df_mes = df[df['fecha'].dt.month == hoy.month]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📦 Paquetes Mes", f"{df_mes['paquetes'].sum():,}")
    c2.metric("🧱 Másters Mes", f"{df_mes['masters'].sum():,}")
    c3.metric("Días Operativos", len(df_mes))
    c4.metric("Promedio Paq/Día", int(df_mes['paquetes'].mean()) if not df_mes.empty else 0)

st.divider()

col_izq, col_der = st.columns([4, 1.2], gap="medium")

with col_izq:
    # 1. Preparar Eventos
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

    # 2. Configurar Calendario (Opciones Críticas)
    cal_options = {
        "editable": False,
        "selectable": True,  # ESTO HABILITA EL CLIC EN CELDA VACÍA
        "navLinks": False,   # Desactivar links a día individual para no confundir clicks
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth"
        },
        "initialView": "dayGridMonth",
        "height": "750px",
        "locale": "es"
    }

    state = calendar(events=events, options=cal_options, key="mi_calendario_final")

    # 3. Lógica de Clic (A PRUEBA DE FALLOS)
    if state.get("dateClick") is not None:
        # Clic en fondo blanco (Nuevo registro)
        fecha_clic = state["dateClick"]["dateStr"]
        modal_registro(fecha_clic)
        
    elif state.get("eventClick") is not None:
        # Clic en evento (Editar registro)
        datos = state["eventClick"]["event"]
        fecha_clic = datos["start"].split("T")[0]
        props = datos.get("extendedProps", {})
        modal_registro(fecha_clic, props)

with col_der:
    st.subheader("🗓️ Totales Semanales")
    st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
    
    if not df.empty:
        # Agregamos columnas de año y semana para agrupar bien
        df['year'] = df['fecha'].dt.year
        df['week'] = df['fecha'].dt.isocalendar().week
        
        # Agrupar ordenando por fecha descendente (más reciente arriba)
        resumen = df.groupby(['year', 'week'])[['paquetes', 'masters']].sum().sort_index(ascending=False)
        
        if resumen.empty:
            st.info("No hay datos recientes.")
        else:
            # Iterar y crear las tarjetas bonitas
            for (year, week), fila in resumen.iterrows():
                # Obtener detalles de fechas
                mes_str, rango_str = get_week_details(year, week)
                
                st.markdown(f"""
                <div class="week-card">
                    <div class="week-header">
                        <span class="week-title">Semana {week} <small style="color:#888; font-weight:normal;">({mes_str})</small></span>
                    </div>
                    <div class="week-dates">📅 {rango_str}</div>
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
        st.info("👋 ¡Bienvenido! Haz clic en cualquier día del calendario para comenzar.")
