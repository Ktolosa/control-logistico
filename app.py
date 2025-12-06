import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# --- 2. GESTIÓN DE ESTADO ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
# La navegación ahora se controla por una variable de estado simple
if 'current_page' not in st.session_state: st.session_state['current_page'] = "login" 

# --- 3. ESTILOS CSS AVANZADOS (MAC DOCK + TOP PROFILE) ---
st.markdown("""
    <style>
    /* 1. OCULTAR ELEMENTOS NATIVOS DE STREAMLIT */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stDecoration"] { display: none; }
    
    /* Fondo General */
    .stApp { background-color: #f0f2f5; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    
    /* 2. PANEL DE USUARIO (TOP LEFT) */
    .user-profile-container {
        position: fixed;
        top: 20px;
        left: 20px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        padding: 10px 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        gap: 15px;
        border: 1px solid rgba(255,255,255,0.5);
        transition: all 0.3s ease;
    }
    .user-profile-container:hover {
        background: rgba(255, 255, 255, 1);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .profile-avatar {
        font-size: 2rem;
        background: #e2e8f0;
        border-radius: 50%;
        width: 45px; height: 45px;
        display: flex; justify-content: center; align-items: center;
    }
    .profile-info { display: flex; flex-direction: column; }
    .profile-name { font-weight: bold; font-size: 0.95rem; color: #1e293b; }
    .profile-role { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Botones pequeños del perfil */
    .profile-actions button {
        border: none; background: transparent; cursor: pointer; font-size: 1.2rem;
        transition: transform 0.2s; padding: 0 5px;
    }
    .profile-actions button:hover { transform: scale(1.2); }

    /* 3. DOCK TIPO MAC OS (BOTTOM CENTER) */
    .dock-container {
        position: fixed;
        bottom: 30px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(255, 255, 255, 0.25);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 24px;
        padding: 10px 20px;
        display: flex;
        gap: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        z-index: 9999;
    }

    /* Estilo de los Botones del Dock (Hackeando st.button) */
    div.stButton > button.dock-btn {
        background-color: transparent;
        border: none;
        font-size: 2rem;
        padding: 10px;
        border-radius: 15px;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        opacity: 0.6; /* Transparente por defecto */
        color: #334155;
        box-shadow: none;
    }
    
    /* Hover Effect: Agrandar y Opacidad Full */
    div.stButton > button.dock-btn:hover {
        transform: scale(1.4) translateY(-10px);
        opacity: 1;
        background-color: rgba(255,255,255,0.5);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* Active State (Herramienta actual) */
    div.stButton > button.dock-btn-active {
        background-color: rgba(255,255,255,0.8) !important;
        opacity: 1 !important;
        transform: scale(1.1) !important;
        border-bottom: 3px solid #3b82f6 !important;
        color: #0f172a !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }

    /* Ajuste para que el contenido no quede tapado por el Dock */
    .block-container { padding-bottom: 120px; padding-top: 80px; }
    
    /* Login Limpio */
    .login-box { 
        background: white; padding: 40px; border-radius: 20px; 
        box-shadow: 0 20px 50px rgba(0,0,0,0.1); 
        max-width: 400px; margin: 10vh auto; text-align: center;
    }
    
    /* Tablas Admin */
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 4. CONEXIÓN Y DATOS ---
AVATARS = {
    "avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👷‍♀️",
    "avatar_5": "🤵", "avatar_6": "🕵️‍♀️", "avatar_7": "🦸‍♂️", "avatar_8": "👩‍💻",
    "avatar_9": "🤖", "avatar_10": "🦁"
}
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- FUNCIONES DE BASE DE DATOS (CRUD USUARIOS ACTUALIZADO) ---

def verificar_login(username, password):
    try:
        conn = get_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone(); conn.close()
        return user
    except: return None

def cambiar_mis_datos(user_id, new_user, new_pass):
    conn = get_connection(); cursor = conn.cursor()
    if new_pass:
        cursor.execute("UPDATE usuarios SET username=%s, password=%s WHERE id=%s", (new_user, new_pass, user_id))
    else:
        cursor.execute("UPDATE usuarios SET username=%s WHERE id=%s", (new_user, user_id))
    conn.commit(); conn.close()
    # Actualizar session state
    st.session_state['user_info']['username'] = new_user

# --- FUNCIONES DE ADMIN (NUEVAS) ---

def admin_get_all_users():
    conn = get_connection()
    df = pd.read_sql("SELECT id, username, rol, activo, created_at, avatar FROM usuarios", conn)
    conn.close()
    return df

def admin_toggle_status(user_id, current_status):
    new_status = 0 if current_status == 1 else 1
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new_status, user_id))
    conn.commit(); conn.close()

def admin_crear_usuario(user, role):
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (user, role))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def admin_get_requests():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn)
    conn.close()
    return df

def admin_resolve_request(req_id, username):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (username,))
    cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (req_id,))
    conn.commit(); conn.close()

# --- FUNCIONES OPERATIVAS (CALENDARIO/DASHBOARD) ---
def cargar_datos_seguros():
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            df = df.dropna(subset=['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection(); cursor = conn.cursor()
    user = st.session_state['user_info']['username']
    if id_reg is None:
        sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, user))
        st.toast("✨ Registro Guardado")
    else:
        sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
        st.toast("✏️ Registro Actualizado")
    conn.commit(); conn.close()

# --- COMPONENTE: MODAL DE REGISTRO ---
@st.dialog("📝 Gestión Operativa")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled = True if rol == 'analista' else False
    
    d_fecha, d_prov, d_plat, d_serv = date.today(), PROVEEDORES[0], PLATAFORMAS[0], SERVICIOS[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        d_id = datos.get('id')
        f_str = datos.get('fecha_str')
        if f_str: d_fecha = datetime.strptime(f_str, '%Y-%m-%d').date()
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        if datos.get('servicio') in SERVICIOS: d_serv = datos['servicio']
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")

    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fecha_in = st.date_input("Fecha", d_fecha, disabled=disabled)
            prov_in = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            plat_in = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            serv_in = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv), disabled=disabled)
            mast_in = st.text_input("Master", d_mast, disabled=disabled)
            paq_in = st.number_input("Paquetes", min_value=0, value=int(d_paq), disabled=disabled)
        com_in = st.text_area("Notas", d_com, disabled=disabled, height=60)
        
        if not disabled:
            if st.form_submit_button("GUARDAR", type="primary", use_container_width=True):
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()

# ==============================================================================
#  LÓGICA DE NAVEGACIÓN Y RENDERIZADO
# ==============================================================================

# 1. PANTALLA DE LOGIN
if not st.session_state['logged_in']:
    st.markdown("""
        <div class='login-box'>
            <div style='font-size:3rem; margin-bottom:10px;'>📦</div>
            <h2 style='color:#1e293b;'>Nexus Logística</h2>
            <p style='color:#94a3b8; margin-bottom:30px;'>Acceso al Sistema</p>
    """, unsafe_allow_html=True)
    
    u = st.text_input("Usuario", placeholder="Ingresa tu usuario", label_visibility="collapsed")
    p = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña", label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("INICIAR SESIÓN", type="primary", use_container_width=True):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.session_state['current_page'] = "calendar" # Home por defecto
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    
    st.markdown("</div>", unsafe_allow_html=True)

else:
    # 2. SISTEMA INTERNO (LAYOUT PERSONALIZADO)
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    curr = st.session_state['current_page']

    # --- A. PANEL DE PERFIL (TOP LEFT) ---
    av_icon = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
    
    # HTML del Perfil con Botones de Acción Invisibles (usamos columns de Streamlit encima para la lógica)
    st.markdown(f"""
    <div class="user-profile-container">
        <div class="profile-avatar">{av_icon}</div>
        <div class="profile-info">
            <span class="profile-name">{u_info['username']}</span>
            <span class="profile-role">{rol}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Colocamos botones invisibles sobre el área del perfil para acciones rápidas es difícil, 
    # así que pondremos los botones de configuración y logout justo al lado del header usando columnas de Streamlit
    # Truco: Usamos st.sidebar NO visible para inyectar lógica, o un container float. 
    # Mejor: Agregamos botones al container fijo en HTML no es facil sin JS.
    # Solución: Botones en la esquina superior izquierda usando st.columns que empujen el contenido.
    
    # --- RENDERIZADO DE PÁGINAS ---
    
    # >> PÁGINA: CONFIGURACIÓN CUENTA
    if curr == "settings":
        st.title("⚙️ Configuración de Cuenta")
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"<div style='font-size:5rem; text-align:center;'>{av_icon}</div>", unsafe_allow_html=True)
            with col2:
                with st.form("my_data"):
                    nu = st.text_input("Cambiar Nombre de Usuario", value=u_info['username'])
                    np = st.text_input("Cambiar Contraseña (Dejar vacío para mantener)", type="password")
                    if st.form_submit_button("Actualizar mis datos", type="primary"):
                        cambiar_mis_datos(u_info['id'], nu, np)
                        st.success("Datos actualizados. Por favor inicia sesión de nuevo.")
                        time.sleep(2)
                        st.session_state['logged_in'] = False
                        st.rerun()
        
        if st.button("⬅️ Volver al Calendario"):
            st.session_state['current_page'] = "calendar"
            st.rerun()

    # >> PÁGINA: ADMIN PANEL
    elif curr == "admin":
        if rol != 'admin':
            st.error("No tienes permisos.")
        else:
            st.title("🛠️ Panel de Administración")
            t1, t2, t3 = st.tabs(["👥 Gestión Usuarios", "➕ Crear Usuario", "🔐 Solicitudes Clave"])
            
            with t1:
                df_users = admin_get_all_users()
                # Mostramos tabla interactiva
                st.dataframe(
                    df_users,
                    column_config={
                        "activo": st.column_config.CheckboxColumn("Activo", help="Desmarcar para bloquear acceso"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Acciones sobre usuarios
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    u_sel = st.selectbox("Seleccionar Usuario para modificar estado", df_users['id'].tolist(), format_func=lambda x: f"ID {x}")
                with c_act2:
                    st.write("") # Spacer
                    st.write("")
                    curr_status = df_users[df_users['id']==u_sel]['activo'].values[0]
                    btn_label = "🔴 Desactivar" if curr_status == 1 else "🟢 Activar"
                    if st.button(btn_label):
                        admin_toggle_status(u_sel, curr_status)
                        st.rerun()

            with t2:
                with st.form("new_u_admin"):
                    nu = st.text_input("Usuario")
                    nr = st.selectbox("Rol", ["user", "analista", "admin"])
                    st.caption("La contraseña por defecto será: 123456")
                    if st.form_submit_button("Crear Usuario"):
                        if admin_crear_usuario(nu, nr): st.success(f"Usuario {nu} creado."); st.rerun()
                        else: st.error("Error al crear.")

            with t3:
                reqs = admin_get_requests()
                if reqs.empty: st.info("No hay solicitudes pendientes.")
                else:
                    for _, row in reqs.iterrows():
                        c_r1, c_r2 = st.columns([3, 1])
                        c_r1.warning(f"Usuario: **{row['username']}** solicitó restablecer contraseña.")
                        if c_r2.button("Restablecer", key=f"rst_{row['id']}"):
                            admin_resolve_request(row['id'], row['username'])
                            st.success("Restablecida a '123456'")
                            st.rerun()

    # >> PÁGINA: DASHBOARD
    elif curr == "dashboard":
        st.title("📊 Inteligencia de Negocios")
        df = cargar_datos_seguros()
        if not df.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Paquetes", f"{df['paquetes'].sum():,}")
            k2.metric("Lotes/Viajes", len(df))
            k3.metric("Top Cliente", df.groupby('plataforma_cliente')['paquetes'].sum().idxmax())
            k4.metric("Promedio Lote", int(df['paquetes'].mean()))
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.line(df.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes', title="Tendencia"), use_container_width=True)
            c2.plotly_chart(px.pie(df, values='paquetes', names='proveedor_logistico', title="Share Proveedores"), use_container_width=True)
        else:
            st.info("Sin datos.")

    # >> PÁGINA: CALENDARIO (HOME)
    elif curr == "calendar":
        c_title, c_action = st.columns([5, 1])
        with c_title: st.title("📅 Calendario Operativo")
        with c_action:
            if rol != 'analista':
                if st.button("➕ NUEVO", type="primary", use_container_width=True):
                    modal_registro(None)

        df = cargar_datos_seguros()
        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                c = "#64748b"
                if "AliExpress" in r['plataforma_cliente']: c="#f97316"
                elif "Temu" in r['plataforma_cliente']: c="#10b981"
                elif "Shein" in r['plataforma_cliente']: c="#0f172a"
                
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"{int(r['paquetes'])} - {r['proveedor_logistico']}", "start": r['fecha_str'], "backgroundColor": c, "borderColor": c, "extendedProps": props})

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "700px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # --- B. DOCK DE NAVEGACIÓN (BOTTOM CENTER) ---
    
    # Definimos clases CSS para saber cuál está activo
    cls_cal = "dock-btn-active" if curr == "calendar" else "dock-btn"
    cls_dash = "dock-btn-active" if curr == "dashboard" else "dock-btn"
    cls_admin = "dock-btn-active" if curr == "admin" else "dock-btn"
    cls_set = "dock-btn-active" if curr == "settings" else "dock-btn"
    cls_out = "dock-btn" # Logout nunca está activo, es acción

    # Renderizamos el Dock
    # IMPORTANTE: Para aplicar las clases CSS a st.button, usamos un truco de javascript o simplemente
    # aprovechamos que Streamlit permite CSS targeting por nth-child, pero como queremos iconos flotantes
    # usaremos columnas en un container fijo abajo.
    
    st.markdown("<div class='dock-container'>", unsafe_allow_html=True)
    
    # Usamos st.columns dentro del flujo normal, pero el CSS 'dock-container' lo posiciona fixed abajo.
    # El problema es que st.columns NO se renderiza dentro del div HTML puro. 
    # Solución: Creamos el layout de botones y usamos CSS para inyectarles el estilo 'dock-btn'.
    
    dock_cols = st.columns(5)
    
    # Función auxiliar para aplicar estilo al botón según índice
    def set_btn_style(idx, is_active):
        active_class = "dock-btn-active" if is_active else "dock-btn"
        # Inyectamos estilo específico para este botón usando nth-of-type selector en el CSS global
        # pero para simplificar, confiamos en el estilo general y el efecto hover.
        # Para marcar el activo visualmente con Python es difícil sin recargar CSS dinámico.
        # Usaremos iconos rellenos vs outline para diferenciar si es posible, o colores.
        pass

    with dock_cols[0]:
        if st.button("📅", key="btn_cal", help="Calendario"): 
            st.session_state['current_page'] = "calendar"
            st.rerun()
    
    with dock_cols[1]:
        if st.button("📊", key="btn_dash", help="Dashboard"): 
            st.session_state['current_page'] = "dashboard"
            st.rerun()

    with dock_cols[2]:
        if rol == 'admin':
            if st.button("🛠️", key="btn_admin", help="Admin Panel"): 
                st.session_state['current_page'] = "admin"
                st.rerun()
        else:
            st.markdown("<div style='width:50px;'></div>", unsafe_allow_html=True) # Espacio vacío

    with dock_cols[3]:
        if st.button("⚙️", key="btn_set", help="Configuración"): 
            st.session_state['current_page'] = "settings"
            st.rerun()
            
    with dock_cols[4]:
        if st.button("🚪", key="btn_out", help="Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)

    # Inyección CSS dinámica para resaltar el botón activo en el Dock
    # Esto busca el botón en la posición X dentro del dock y le da opacidad 1
    idx_map = {"calendar": 1, "dashboard": 2, "admin": 3, "settings": 4}
    active_idx = idx_map.get(curr, 0)
    
    if active_idx > 0:
        st.markdown(f"""
            <style>
            /* Selector avanzado para encontrar el botón dentro del dock container (que visualmente está abajo) */
            /* Streamlit renderiza los botones como div.stButton > button */
            /* Dependiendo de la estructura, esto puede variar, pero intentamos targetear por orden */
            
            div.stButton:nth-of-type({active_idx}) > button {{
                background-color: rgba(255,255,255,0.8) !important;
                opacity: 1 !important;
                transform: scale(1.15) !important;
                border-bottom: 3px solid #3b82f6 !important;
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.3) !important;
            }}
            </style>
        """, unsafe_allow_html=True)
