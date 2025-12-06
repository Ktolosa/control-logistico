import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Logística", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 5px; font-weight: bold; }
    /* Ajuste para que el calendario se vea bien */
    .fc { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN DB ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- CARGAR DATOS ---
def cargar_datos():
    try:
        conn = get_connection()
        # Traemos el ID también, es vital para editar
        df = pd.read_sql("SELECT id, fecha, proveedor, tipo_servicio, master_lote, paquetes, comentarios FROM registro_logistica", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        st.error(f"Error DB: {e}")
        return pd.DataFrame()

# --- GUARDAR / ACTUALIZAR (UPSERT) ---
def guardar_en_bd(id_registro, fecha, proveedor, servicio, master, paquetes, notas):
    conn = get_connection()
    cursor = conn.cursor()
    
    if id_registro is None:
        # INSERTAR NUEVO
        query = """
        INSERT INTO registro_logistica (fecha, proveedor, tipo_servicio, master_lote, paquetes, comentarios)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (fecha, proveedor, servicio, master, paquetes, notas))
        st.toast("✅ Nuevo registro creado exitosamente")
    else:
        # ACTUALIZAR EXISTENTE (EDITAR)
        query = """
        UPDATE registro_logistica 
        SET fecha=%s, proveedor=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s
        WHERE id=%s
        """
        cursor.execute(query, (fecha, proveedor, servicio, master, paquetes, notas, id_registro))
        st.toast("✏️ Registro actualizado correctamente")
        
    conn.commit()
    conn.close()

# --- LISTAS ---
PROVEEDORES = ["Mail Americas AliExpress", "Mail Americas Shein", "Imile Temu", "APG Temu", "GLC Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- VENTANA EMERGENTE (DIALOG) ---
@st.dialog("Gestión de Registro Logístico")
def formulario_emergente(datos=None):
    # Si 'datos' viene lleno, es EDICIÓN. Si viene None, es NUEVO.
    
    # Preparar valores por defecto
    default_fecha = date.today()
    default_prov = PROVEEDORES[0]
    default_serv = SERVICIOS[0]
    default_mast = ""
    default_paq = 0
    default_nota = ""
    id_actual = None

    if datos:
        # Estamos editando, sobreescribimos los defaults
        id_actual = datos.get('id')
        try:
            default_fecha = datetime.strptime(datos.get('fecha_str'), '%Y-%m-%d').date()
        except:
            default_fecha = date.today()
            
        # Validar que el proveedor exista en la lista, si no, usar el primero
        prov_db = datos.get('proveedor')
        default_prov = prov_db if prov_db in PROVEEDORES else PROVEEDORES[0]
        
        serv_db = datos.get('tipo_servicio')
        default_serv = serv_db if serv_db in SERVICIOS else SERVICIOS[0]
        
        default_mast = datos.get('master_lote', "")
        default_paq = datos.get('paquetes', 0)
        default_nota = datos.get('comentarios', "")

    # El Formulario dentro del Popup
    with st.form("form_modal"):
        c1, c2 = st.columns(2)
        with c1:
            fecha_in = st.date_input("Fecha", default_fecha)
            prov_in = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(default_prov))
            serv_in = st.selectbox("Tipo Servicio", SERVICIOS, index=SERVICIOS.index(default_serv))
        with c2:
            mast_in = st.text_input("Master / Lote", default_mast)
            paq_in = st.number_input("Paquetes", min_value=0, value=default_paq, step=1)
            nota_in = st.text_area("Notas", default_nota, height=68)
            
        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            submitted = st.form_submit_button("💾 GUARDAR", type="primary", use_container_width=True)
        
    if submitted:
        if mast_in and paq_in > 0:
            guardar_en_bd(id_actual, fecha_in, prov_in, serv_in, mast_in, paq_in, nota_in)
            st.rerun() # Recarga la página para cerrar modal y actualizar calendario
        else:
            st.error("⚠️ Falta Master o Cantidad")

# --- UI PRINCIPAL ---

st.title("📦 Sistema Logístico")

# 1. BOTÓN SUPERIOR GRANDE
col_btn, col_kpi = st.columns([1, 3])
with col_btn:
    if st.button("➕ AGREGAR NUEVO REGISTRO", type="primary"):
        formulario_emergente(None) # Llamamos al modal vacío

df = cargar_datos()

# 2. CALENDARIO Y EDICIÓN
events = []
if not df.empty:
    for _, row in df.iterrows():
        # Definir color
        color = "#3788d8"
        if "AliExpress" in row['proveedor']: color = "#e67e22"
        elif "Shein" in row['proveedor']: color = "#9b59b6"
        elif "Temu" in row['proveedor']: color = "#2ecc71"
        
        events.append({
            "id": str(row['id']), # Importante pasar el ID al calendario
            "title": f"{row['paquetes']} - {row['proveedor'].split(' ')[1]}",
            "start": row['fecha_str'],
            "backgroundColor": color,
            "borderColor": color,
            # Pasamos todos los datos en extendedProps para poder recuperarlos al editar
            "extendedProps": {
                "id": row['id'],
                "fecha_str": row['fecha_str'],
                "proveedor": row['proveedor'],
                "tipo_servicio": row['tipo_servicio'],
                "master_lote": row['master_lote'],
                "paquetes": row['paquetes'],
                "comentarios": row['comentarios']
            }
        })

cal_ops = {
    "initialView": "dayGridMonth",
    "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
    "height": "700px",
    "selectable": False, # Desactivamos seleccion de celda vacia, usamos el boton superior
    "editable": False,
}

# Dibujar calendario
calendar_state = calendar(events=events, options=cal_ops, key="cal_main")

# LÓGICA DE CLIC PARA EDITAR
if calendar_state.get("eventClick"):
    event_data = calendar_state["eventClick"]["event"]
    # Extraemos los datos guardados en extendedProps
    props = event_data.get("extendedProps", {})
    # Abrimos el MISMO modal, pero pasando los datos para que se rellene solo
    formulario_emergente(props)

# --- VISUALIZACIÓN EXTRA (ABAJO) ---
st.divider()
if not df.empty:
    st.subheader("📊 Resumen Rápido")
    tab1, tab2 = st.tabs(["Totales por Proveedor", "Datos Recientes"])
    with tab1:
        st.plotly_chart(px.bar(df, x='proveedor', y='paquetes', color='tipo_servicio', title="Paquetes por Proveedor"), use_container_width=True)
    with tab2:
        st.dataframe(df[['fecha', 'proveedor', 'master_lote', 'paquetes', 'tipo_servicio']].sort_values('fecha', ascending=False), use_container_width=True)
