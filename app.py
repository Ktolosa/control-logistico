import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN Y ESTILOS MODERNOS ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# CSS AVANZADO (Animaciones, Sombras, Botones Redondos)
st.markdown("""
    <style>
    /* Fondo y Fuente Global */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    /* Botón Flotante "+" (Estilo Material Design) */
    div.stButton > button:first-child {
        border-radius: 12px;
        transition: all 0.3s ease;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }

    /* Estilo para el botón "+" específico */
    .plus-btn { 
        background-color: #2563eb !important; 
        color: white !important; 
        font-size: 24px !important;
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        padding: 0 !important;
    }

    /* Tarjetas de Métricas */
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #3b82f6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: scale(1.02); }

    /* Login Box */
    .login-box {
        max-width: 400px;
        margin: auto;
        padding: 40px;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    }
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
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

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
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except:
        return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection()
    cursor = conn.cursor()
    usuario_actual = st.session_state['user_info']['username']
    
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
    
    # Valores por defecto
    d_fecha = date.today()
    d_prov = PROVEEDORES_LOGISTICOS[0]
    d_plat = PLATAFORMAS_CLIENTE[0]
    d_serv = TIPOS_SERVICIO[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        d_id = datos['id']
        try: d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
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

@st.dialog("📊 Centro de Análisis y Reportes", width="large")
def modal_dashboard(df):
    st.markdown("### 🔎 Filtros de Análisis")
    
    # --- FILTROS ---
    cf1, cf2, cf3, cf4 = st.columns(4)
    with cf1:
        filtro_prov = st.multiselect("Proveedor", df['proveedor_logistico'].unique())
    with cf2:
        filtro_plat = st.multiselect("Plataforma", df['plataforma_cliente'].unique())
    with cf3:
        # Filtro de Mes
        meses = df['fecha'].dt.month_name().unique()
        filtro_mes = st.multiselect("Mes", meses)
    with cf4:
        serv_filtro = st.multiselect("Servicio", df['tipo_servicio'].unique())
        
    # Aplicar filtros
    df_filtered = df.copy()
    if filtro_prov: df_filtered = df_filtered[df_filtered['proveedor_logistico'].isin(filtro_prov)]
    if filtro_plat: df_filtered = df_filtered[df_filtered['plataforma_cliente'].isin(filtro_plat)]
    if filtro_mes: df_filtered = df_filtered[df_filtered['fecha'].dt.month_name().isin(filtro_mes)]
    if serv_filtro: df_filtered = df_filtered[df_filtered['tipo_servicio'].isin(serv_filtro)]

    st.divider()
    
    if df_filtered.empty:
        st.warning("No hay datos con estos filtros.")
        return

    # --- KPI CARDS ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Paquetes", f"{df_filtered['paquetes'].sum():,}")
    k2.metric("Total Masters", len(df_filtered))
    top_p = df_filtered.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
    k3.metric("Top Plataforma", top_p)
    prom = int(df_filtered['paquetes'].mean())
    k4.metric("Promedio x Lote", prom)
    
    st.divider()

    # --- GRÁFICOS ---
    tab1, tab2, tab3 = st.tabs(["📈 Evolución", "🍰 Distribución", "📅 Semanal"])
    
    with tab1:
        # Linea temporal
        df_dia = df_filtered.groupby('fecha')['paquetes'].sum().reset_index()
        fig_line = px.line(df_dia, x='fecha', y='paquetes', markers=True, title="Volumen Diario")
        fig_line.update_layout(height=350)
        st.plotly_chart(fig_line, use_container_width=True)
        
    with tab2:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_pie1 = px.pie(df_filtered, values='paquetes', names='proveedor_logistico', title="Share x Proveedor", hole=0.4)
            st.plotly_chart(fig_pie1, use_container_width=True)
        with col_g2:
            fig_pie2 = px.bar(df_filtered, x='plataforma_cliente', y='paquetes', color='tipo_servicio', title="Paquetes x Plataforma")
            st.plotly_chart(fig_pie2, use_container_width=True)
            
    with tab3:
        df_filtered['semana'] = df_filtered['fecha'].dt.isocalendar().week
        df_sem = df_filtered.groupby('semana')['paquetes'].sum().reset_index()
        st.bar_chart(df_sem, x='semana', y='paquetes')

@st.dialog("🛡️ Panel de Administrador", width="large")
def modal_admin():
    st.subheader("Gestión de Usuarios")
    
    # Crear Usuario
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
                    st.error("Error al crear (quizás el usuario ya existe).")
    
    # Listar Usuarios
    conn = get_connection()
    users = pd.read_sql("SELECT id, username, rol, activo, created_at FROM usuarios", conn)
    conn.close()
    
    st.dataframe(users, use_container_width=True, hide_index=True)
    
    # Acciones
    col_a, col_b = st.columns(2)
    with col_a:
        u_sel = st.selectbox("Seleccionar ID Usuario para acción", users['id'].tolist())
    with col_b:
        estado_actual = users[users['id']==u_sel]['activo'].values[0] if not users.empty else 0
        btn_txt = "🔴 Desactivar" if estado_actual else "🟢 Activar"
        if st.button(btn_txt):
            admin_toggle_usuario(u_sel, estado_actual)
            st.rerun()

# --- 7. LÓGICA PRINCIPAL (LOGIN + APP) ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    # --- PANTALLA DE LOGIN ---
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div class='login-box'><h2 style='text-align:center;'>🔐 Nexus Logística</h2><p style='text-align:center;color:gray;'>Inicia sesión para continuar</p>", unsafe_allow_html=True)
        
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        
        if st.button("INGRESAR", type="primary", use_container_width=True):
            user_data = verificar_login(u, p)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user_data
                st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario inactivo.")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    # --- APLICACIÓN PRINCIPAL ---
    
    # ENCABEZADO SUPERIOR
    col_logo, col_actions, col_user = st.columns([2, 4, 1.5], gap="small")
    
    with col_logo:
        st.markdown("### 📦 Control Logístico")
    
    with col_actions:
        # Botones de Acción en el Header
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("➕ NUEVO REGISTRO", use_container_width=True):
                modal_registro(None)
        with c_btn2:
            if st.button("📊 VER DASHBOARDS", use_container_width=True):
                df_dash = cargar_datos_logistica()
                modal_dashboard(df_dash)

    with col_user:
        # Menú de Usuario / Admin
        user_role = st.session_state['user_info']['rol']
        with st.expander(f"👤 {st.session_state['user_info']['username']}"):
            if user_role == 'admin':
                if st.button("🛠️ Admin Panel"):
                    modal_admin()
            if st.button("Cerrar Sesión"):
                st.session_state['logged_in'] = False
                st.rerun()

    st.markdown("---")

    # CALENDARIO PRINCIPAL
    df = cargar_datos_logistica()
    
    events = []
    if not df.empty:
        for _, row in df.iterrows():
            # Color Coding basado en Plataforma
            color = "#6c757d" # Default gris
            if row['plataforma_cliente'] == "AliExpress": color = "#f97316" # Naranja
            elif row['plataforma_cliente'] == "Shein": color = "#000000" # Negro
            elif row['plataforma_cliente'] == "Temu": color = "#ea580c" # Naranja fuerte
            
            # Título del evento combina Proveedor y Paquetes
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

    # CLICK PARA EDITAR
    if state.get("eventClick"):
        props = state["eventClick"]["event"]["extendedProps"]
        modal_registro(props)

    # CLICK EN DÍA VACÍO (Opcional, si quieres que al dar clic en dia tambien abra)
    if state.get("dateClick"):
        fecha_clic = state["dateClick"]["dateStr"]
        # Preparamos un objeto dummy solo con la fecha
        dummy_data = {'id': None, 'fecha_str': fecha_clic, 'proveedor_logistico': PROVEEDORES_LOGISTICOS[0], 
                      'plataforma_cliente': PLATAFORMAS_CLIENTE[0], 'tipo_servicio': TIPOS_SERVICIO[0], 
                      'master_lote': '', 'paquetes': 0, 'comentarios': ''}
        modal_registro(dummy_data)
