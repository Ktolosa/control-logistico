import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    div.stButton > button:first-child {
        border-radius: 8px;
        transition: all 0.3s ease;
        font-weight: 600;
    }
    .stTextInput label { font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE BASE DE DATOS ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- 3. AUTENTICACIÓN ---
def verificar_login(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def admin_crear_usuario(user, pwd, role):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s)", (user, pwd, role))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def admin_toggle_usuario(user_id, estado_actual):
    conn = get_connection()
    cursor = conn.cursor()
    nuevo_estado = 0 if estado_actual else 1
    cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (nuevo_estado, user_id))
    conn.commit()
    conn.close()

# --- 4. LISTAS PREDEFINIDAS ---
PROVEEDORES_LOGISTICOS = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS_CLIENTE = ["AliExpress", "Shein", "Temu"]
TIPOS_SERVICIO = ["Aduana Propia", "Solo Ultima Milla"]

# --- 5. FUNCIONES CRUD ---
def cargar_datos_logistica():
    try:
        conn = get_connection()
        query = "SELECT * FROM registro_logistica ORDER BY fecha DESC"
        df = pd.read_sql(query, conn)
        conn.close()
        
        if not df.empty:
            # CORRECCIÓN PRINCIPAL: Forzar conversión a datetime con manejo de errores
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            # Eliminar filas donde la fecha sea NaT (Not a Time) si hubo error
            df = df.dropna(subset=['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            
        return df
    except Exception as e:
        # En caso de error, devolver DF vacío pero con columnas correctas para no romper el dashboard
        return pd.DataFrame(columns=['id', 'fecha', 'proveedor_logistico', 'plataforma_cliente', 'tipo_servicio', 'master_lote', 'paquetes', 'comentarios'])

def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection()
    cursor = conn.cursor()
    usuario_actual = st.session_state.get('user_info', {}).get('username', 'sistema')
    
    if id_reg is None: # Nuevo
        sql = """INSERT INTO registro_logistica 
                 (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        vals = (fecha, prov, plat, serv, mast, paq, com, usuario_actual)
        cursor.execute(sql, vals)
        st.toast("✨ Registro creado con éxito")
    else: # Editar
        sql = """UPDATE registro_logistica 
                 SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, 
                     master_lote=%s, paquetes=%s, comentarios=%s 
                 WHERE id=%s"""
        vals = (fecha, prov, plat, serv, mast, paq, com, id_reg)
        cursor.execute(sql, vals)
        st.toast("✏️ Registro actualizado")
    
    conn.commit()
    conn.close()

# --- 6. VENTANAS EMERGENTES (MODALES) ---

@st.dialog("📦 Gestión de Operaciones", width="large")
def modal_registro(datos=None):
    st.markdown("### Detalles del Ingreso")
    
    d_fecha = date.today()
    d_prov = PROVEEDORES_LOGISTICOS[0]
    d_plat = PLATAFORMAS_CLIENTE[0]
    d_serv = TIPOS_SERVICIO[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        d_id = datos['id']
        try: 
            # Manejo seguro de fecha al editar
            if isinstance(datos['fecha_str'], str):
                d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
            else:
                d_fecha = datos['fecha_str'] # Si ya viene como objeto date
        except: pass
        
        if datos['proveedor_logistico'] in PROVEEDORES_LOGISTICOS: d_prov = datos['proveedor_logistico']
        if datos['plataforma_cliente'] in PLATAFORMAS_CLIENTE: d_plat = datos['plataforma_cliente']
        if datos['tipo_servicio'] in TIPOS_SERVICIO: d_serv = datos['tipo_servicio']
        d_mast = datos['master_lote']
        d_paq = datos['paquetes']
        d_com = datos['comentarios']

    with st.form("form_logistica"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_in = st.date_input("Fecha de Arribo", d_fecha)
            prov_in = st.selectbox("🚛 Proveedor Logístico", PROVEEDORES_LOGISTICOS, index=PROVEEDORES_LOGISTICOS.index(d_prov))
        with c2:
            plat_in = st.selectbox("🛍️ Plataforma (Cliente)", PLATAFORMAS_CLIENTE, index=PLATAFORMAS_CLIENTE.index(d_plat))
            serv_in = st.selectbox("⚙️ Tipo de Servicio", TIPOS_SERVICIO, index=TIPOS_SERVICIO.index(d_serv))
        with c3:
            mast_in = st.text_input("📦 ID Master / Lote", d_mast)
            paq_in = st.number_input("Cantidad Paquetes", min_value=0, value=d_paq, step=1)
        
        com_in = st.text_area("Comentarios Adicionales", d_com, height=80)
        
        col_submit = st.columns([1,2,1])
        with col_submit[1]:
            submitted = st.form_submit_button("CONFIRMAR Y GUARDAR", type="primary", use_container_width=True)
            
        if submitted:
            if mast_in and paq_in > 0:
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()
            else:
                st.error("⚠️ Falta ID Master o Paquetes")

@st.dialog("📊 Centro de Análisis", width="large")
def modal_dashboard(df):
    st.markdown("### 🔎 Filtros")
    
    # 1. VALIDACIÓN PREVIA Y CONVERSIÓN SEGURA
    if df.empty or 'fecha' not in df.columns:
        st.warning("No hay datos suficientes para generar gráficos.")
        return

    # Aseguramos que sea datetime, si falla pone NaT
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha']) # Eliminamos lo que no sea fecha
    
    if df.empty:
        st.warning("Los datos de fecha no son válidos.")
        return

    # Diccionario para meses en Español
    meses_map = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    df['mes_num'] = df['fecha'].dt.month
    df['nombre_mes'] = df['mes_num'].map(meses_map)
    
    cf1, cf2, cf3, cf4 = st.columns(4)
    with cf1: filtro_prov = st.multiselect("Proveedor", df['proveedor_logistico'].unique())
    with cf2: filtro_plat = st.multiselect("Plataforma", df['plataforma_cliente'].unique())
    with cf3: 
        # Usamos la columna mapeada en español
        lista_meses = df['nombre_mes'].unique().tolist()
        filtro_mes = st.multiselect("Mes", lista_meses)
    with cf4: serv_filtro = st.multiselect("Servicio", df['tipo_servicio'].unique())
        
    df_filtered = df.copy()
    if filtro_prov: df_filtered = df_filtered[df_filtered['proveedor_logistico'].isin(filtro_prov)]
    if filtro_plat: df_filtered = df_filtered[df_filtered['plataforma_cliente'].isin(filtro_plat)]
    if filtro_mes: df_filtered = df_filtered[df_filtered['nombre_mes'].isin(filtro_mes)]
    if serv_filtro: df_filtered = df_filtered[df_filtered['tipo_servicio'].isin(serv_filtro)]

    st.divider()
    
    if df_filtered.empty:
        st.warning("No hay datos con estos filtros.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Paquetes", f"{df_filtered['paquetes'].sum():,}")
    k2.metric("Total Masters", len(df_filtered))
    
    try:
        top_p = df_filtered.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
    except:
        top_p = "-"
    k3.metric("Top Plataforma", top_p)
    
    prom = int(df_filtered['paquetes'].mean()) if not df_filtered.empty else 0
    k4.metric("Promedio", prom)
    
    st.divider()

    tab1, tab2 = st.tabs(["📈 Evolución", "🍰 Distribución"])
    with tab1:
        df_dia = df_filtered.groupby('fecha')['paquetes'].sum().reset_index()
        fig_line = px.line(df_dia, x='fecha', y='paquetes', markers=True, title="Volumen Diario")
        st.plotly_chart(fig_line, use_container_width=True)
    with tab2:
        c_p1, c_p2 = st.columns(2)
        with c_p1: st.plotly_chart(px.pie(df_filtered, values='paquetes', names='proveedor_logistico', title="Prov. Logístico"), use_container_width=True)
        with c_p2: st.plotly_chart(px.pie(df_filtered, values='paquetes', names='plataforma_cliente', title="Cliente"), use_container_width=True)

@st.dialog("🛡️ Panel Admin", width="large")
def modal_admin():
    st.subheader("Gestión de Usuarios")
    
    with st.expander("➕ Crear Nuevo Usuario"):
        with st.form("new_user"):
            nu_name = st.text_input("Usuario")
            nu_pass = st.text_input("Contraseña", type="password")
            nu_role = st.selectbox("Rol", ["user", "admin"])
            if st.form_submit_button("Crear Usuario"):
                if admin_crear_usuario(nu_name, nu_pass, nu_role):
                    st.success(f"Usuario {nu_name} creado.")
                    st.rerun()
                else:
                    st.error("Error al crear.")
    
    conn = get_connection()
    users = pd.read_sql("SELECT id, username, rol, activo, created_at FROM usuarios", conn)
    conn.close()
    st.dataframe(users, use_container_width=True, hide_index=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        if not users.empty:
            u_sel = st.selectbox("ID Usuario", users['id'].tolist())
    with col_b:
        if not users.empty:
            estado_actual = users[users['id']==u_sel]['activo'].values[0]
            btn_txt = "Desactivar" if estado_actual else "Activar"
            if st.button(btn_txt):
                admin_toggle_usuario(u_sel, estado_actual)
                st.rerun()

# --- 7. LÓGICA PRINCIPAL ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c_izq, c_centro, c_der = st.columns([1, 1, 1])
    with c_centro:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("INICIAR", type="primary", use_container_width=True):
            user_data = verificar_login(u, p)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user_data
                st.rerun()
            else:
                st.error("Datos incorrectos")

else:
    col_logo, col_actions, col_user = st.columns([2, 4, 1.5], gap="small")
    with col_logo:
        st.markdown("### 📦 Control Logístico")
    
    with col_actions:
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("➕ NUEVO REGISTRO", use_container_width=True):
                modal_registro(None)
        with c_btn2:
            if st.button("📊 VER DASHBOARDS", use_container_width=True):
                # Cargamos datos aquí para asegurar que estén frescos
                df_dash = cargar_datos_logistica()
                modal_dashboard(df_dash)

    with col_user:
        user_role = st.session_state['user_info']['rol']
        with st.expander(f"👤 {st.session_state['user_info']['username']}"):
            if user_role == 'admin':
                if st.button("🛠️ Admin Panel"):
                    modal_admin()
            if st.button("Cerrar Sesión"):
                st.session_state['logged_in'] = False
                st.rerun()

    st.markdown("---")

    df = cargar_datos_logistica()
    
    events = []
    if not df.empty and 'fecha_str' in df.columns:
        for _, row in df.iterrows():
            color = "#6c757d"
            if row['plataforma_cliente'] == "AliExpress": color = "#f97316"
            elif row['plataforma_cliente'] == "Shein": color = "#000000"
            elif row['plataforma_cliente'] == "Temu": color = "#ea580c"
            
            title_evt = f"{row['paquetes']} - {row['proveedor_logistico']} ({row['plataforma_cliente']})"
            
            events.append({
                "id": str(row['id']),
                "title": title_evt,
                "start": row['fecha_str'],
                "backgroundColor": color,
                "borderColor": color,
                "extendedProps": {
                    "id": row['id'],
                    "fecha_str": row['fecha_str'],
                    "proveedor_logistico": row['proveedor_logistico'],
                    "plataforma_cliente": row['plataforma_cliente'],
                    "tipo_servicio": row['tipo_servicio'],
                    "master_lote": row['master_lote'],
                    "paquetes": row['paquetes'],
                    "comentarios": row['comentarios']
                }
            })

    cal_ops = {
        "initialView": "dayGridMonth",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
        "height": "750px",
        "locale": "es",
        "navLinks": True
    }

    state = calendar(events=events, options=cal_ops, key="calendar_pro")

    if state.get("eventClick"):
        props = state["eventClick"]["event"]["extendedProps"]
        modal_registro(props)

    if state.get("dateClick"):
        fecha_clic = state["dateClick"]["dateStr"]
        dummy_data = {'id': None, 'fecha_str': fecha_clic, 'proveedor_logistico': PROVEEDORES_LOGISTICOS[0], 
                      'plataforma_cliente': PLATAFORMAS_CLIENTE[0], 'tipo_servicio': TIPOS_SERVICIO[0], 
                      'master_lote': '', 'paquetes': 0, 'comentarios': ''}
        modal_registro(dummy_data)
