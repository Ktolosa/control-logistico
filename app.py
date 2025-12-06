import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px

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
    # Asegúrate de tener tu archivo .streamlit/secrets.toml configurado
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def cargar_datos():
    try:
        conn = get_connection()
        # Cargamos todos los registros individuales
        df = pd.read_sql("SELECT * FROM registro_logistica", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

def guardar_registro(fecha, proveedor, tipo_servicio, master, paquetes, comentarios):
    conn = get_connection()
    cursor = conn.cursor()
    # Insertamos un NUEVO registro (permitiendo múltiples por día)
    query = """
    INSERT INTO registro_logistica (fecha, proveedor, tipo_servicio, master_lote, paquetes, comentarios)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    vals = (fecha, proveedor, tipo_servicio, master, paquetes, comentarios)
    cursor.execute(query, vals)
    conn.commit()
    conn.close()

# --- 4. LISTAS DESPLEGABLES ---
LISTA_PROVEEDORES = [
    "Mail Americas AliExpress", 
    "Mail Americas Shein", 
    "Imile Temu", 
    "APG Temu", 
    "GLC Temu"
]

LISTA_SERVICIOS = [
    "Aduana Propia",
    "Solo Ultima Milla"
]

# --- 5. CALCULAR FECHAS DE SEMANA ---
def get_week_details(year, week_num):
    try:
        d_start = date.fromisocalendar(year, week_num, 1)
        d_end = d_start + timedelta(days=6)
        meses = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 
                 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
        rango = f"{d_start.day} {meses[d_start.month]} - {d_end.day} {meses[d_end.month]}"
        return meses[d_start.month], rango
    except:
        return "", ""

# --- 6. VENTANA MODAL (POPUP) ---
@st.dialog("📝 Nuevo Ingreso")
def modal_registro(fecha_str):
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        st.markdown(f"### 📅 Ingreso para: {fecha_obj.strftime('%d / %m / %Y')}")
    except:
        st.write(f"Fecha: {fecha_str}")

    with st.form("mi_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            prov = st.selectbox("🚚 Proveedor", LISTA_PROVEEDORES)
            tipo = st.selectbox("⚙️ Tipo Servicio", LISTA_SERVICIOS)
        
        with col2:
            mast = st.text_input("🆔 Master / Lote", placeholder="Ej: MASTER-001")
            paq = st.number_input("📦 Cantidad Paquetes", min_value=1, step=1)
            
        com = st.text_area("💬 Notas (Opcional)", height=80)
        
        if st.form_submit_button("💾 Guardar Registro", type="primary", use_container_width=True):
            if mast and paq > 0:
                guardar_registro(fecha_str, prov, tipo, mast, paq, com)
                st.rerun()
            else:
                st.error("Falta el ID Master o Paquetes.")

# --- 7. INTERFAZ PRINCIPAL ---
df = cargar_datos()

st.title("Sistema de Control Logístico")

# Métricas rápidas arriba
if not df.empty:
    hoy = date.today()
    # Filtramos datos del mes actual
    df_mes = df[df['fecha'].dt.month == hoy.month]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Paquetes (Mes)", f"{df_mes['paquetes'].sum():,}")
    col2.metric("🚛 Entradas (Mes)", len(df_mes)) # Cantidad de registros
    
    # Proveedor Top del Mes
    if not df_mes.empty:
        top_prov = df_mes.groupby('proveedor')['paquetes'].sum().idxmax()
        col3.metric("🏆 Top Proveedor", top_prov)
    else:
        col3.metric("🏆 Top Proveedor", "-")
        
    prom = int(df_mes['paquetes'].sum() / len(df_mes['fecha'].unique())) if not df_mes.empty else 0
    col4.metric("📊 Promedio Diario", prom)

st.divider()

# Layout: Calendario (Izquierda) - Resumen Semanal (Derecha)
col_cal, col_sidebar = st.columns([4, 1.3], gap="medium")

with col_cal:
    # Preparar eventos para el calendario
    # Como ahora tenemos multiples registros por dia, los agrupamos para mostrar totales en el calendario
    events = []
    if not df.empty:
        # Agrupamos por fecha y proveedor para crear "burbujas" en el calendario
        agrupado_dia = df.groupby(['fecha_str', 'proveedor'])['paquetes'].sum().reset_index()
        
        for _, row in agrupado_dia.iterrows():
            # Asignar color según proveedor para diferenciar visualmente
            color = "#3788d8" # Azul default
            if "AliExpress" in row['proveedor']: color = "#e67e22" # Naranja
            elif "Temu" in row['proveedor']: color = "#2ecc71" # Verde
            elif "Shein" in row['proveedor']: color = "#9b59b6" # Morado
            
            events.append({
                "title": f"{row['paquetes']} - {row['proveedor'].split(' ')[-1]}", # Muestra "500 - Temu"
                "start": row['fecha_str'],
                "backgroundColor": color,
                "borderColor": color,
                "allDay": True
            })

    cal_options = {
        "editable": False,
        "selectable": True, 
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

    # --- LÓGICA DE CLIC ---
    date_click = state.get("dateClick")
    # Solo permitimos clic en día vacío o celda para agregar NUEVO registro
    # (Ya no editamos al hacer clic, solo agregamos, para soportar multiples ingresos)
    if date_click and isinstance(date_click, dict) and "dateStr" in date_click:
        modal_registro(date_click["dateStr"])

with col_sidebar:
    st.subheader("🗓️ Totales Semana")
    st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
    
    if not df.empty:
        df['year'] = df['fecha'].dt.year
        df['week'] = df['fecha'].dt.isocalendar().week
        
        # Agrupar por semana
        resumen = df.groupby(['year', 'week'])['paquetes'].sum().reset_index().sort_values(['year', 'week'], ascending=False)
        
        if resumen.empty:
            st.info("Sin datos.")
        else:
            for _, fila in resumen.iterrows():
                year, week = int(fila['year']), int(fila['week'])
                mes_nom, rango_fechas = get_week_details(year, week)
                
                # Desglose por tipo de servicio en esa semana
                df_semana = df[(df['year'] == year) & (df['week'] == week)]
                aduana = df_semana[df_semana['tipo_servicio'] == "Aduana Propia"]['paquetes'].sum()
                ultima = df_semana[df_semana['tipo_servicio'] == "Solo Ultima Milla"]['paquetes'].sum()
                
                st.markdown(f"""
                <div class="week-card">
                    <div class="week-header">
                        <span class="week-title">Semana {week} <span style="font-weight:normal;">({mes_nom})</span></span>
                    </div>
                    <div class="week-dates">📅 {rango_fechas}</div>
                    
                    <div class="stat-row">
                        <span>📦 Total Paquetes</span>
                        <span class="val-paq" style="font-size:1.1rem;">{fila['paquetes']}</span>
                    </div>
                    <div class="stat-row" style="font-size:0.8rem; color:#555;">
                        <span>🏢 Aduana Propia</span>
                        <span>{aduana}</span>
                    </div>
                    <div class="stat-row" style="font-size:0.8rem; color:#555; border:none;">
                        <span>🚚 Última Milla</span>
                        <span>{ultima}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

st.divider()

# --- 8. DASHBOARD ANALÍTICO ---
if not df.empty:
    st.header("📊 Análisis y Gráficos")
    
    tab1, tab2, tab3 = st.tabs(["Evolución", "Distribución Proveedores", "Detalle de Datos"])
    
    with tab1:
        # Gráfico de evolución diaria por Proveedor
        fig_line = px.bar(df, x='fecha', y='paquetes', color='proveedor', 
                           title="Paquetes Diarios por Proveedor (Apilado)",
                           labels={'fecha': 'Fecha', 'paquetes': 'Cantidad Paquetes'})
        st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
             # Pastel por Proveedor
            fig_pie = px.pie(df, values='paquetes', names='proveedor', title="Market Share (Paquetes)")
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            # Pastel por Servicio
            fig_pie2 = px.pie(df, values='paquetes', names='tipo_servicio', title="Tipo de Operación", hole=0.4)
            st.plotly_chart(fig_pie2, use_container_width=True)

    with tab3:
        st.dataframe(df[['fecha', 'proveedor', 'tipo_servicio', 'master_lote', 'paquetes', 'comentarios']].sort_values('fecha', ascending=False), use_container_width=True)
