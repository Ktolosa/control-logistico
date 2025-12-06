import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# Inicializar estado
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 2. GESTIÓN DE CSS (DISEÑO SLIM / DOCK) ---

# Ancho de la barra lateral (Muy delgado, solo para iconos)
SIDEBAR_WIDTH = "90px"

base_css = """
<style>
    /* Ocultar elementos del sistema */
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    .stDeployButton, [data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
    
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container {
        max-width: 400px;
        padding-top: 10vh;
        margin: 0 auto;
    }
    div[data-testid="stTextInput"] input {
        border: 1px solid #ddd; padding: 12px; border-radius: 8px;
    }
    div.stButton > button { width: 100%; border-radius: 8px; font-weight: 600; padding: 10px; }
    
    /* Contenedor Login */
    .login-box {
        background: white; padding: 40px; border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center;
    }
</style>
"""

dashboard_css = f"""
<style>
    /* --- 1. BARRA LATERAL LIMPIA (SIN SLIDER NI FLECHA) --- */
    
    /* Ocultar flecha de colapso */
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    /* Configuración del contenedor de la barra */
    [data-testid="stSidebar"] {{
        display: block !important;
        width: {SIDEBAR_WIDTH} !important;
        min-width: {SIDEBAR_WIDTH} !important;
        max-width: {SIDEBAR_WIDTH} !important;
        transform: translateX(0) !important;
        visibility: visible !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        background-color: #1e293b; /* Fondo oscuro elegante para iconos */
        border-right: 1px solid #334155;
    }}
    
    /* Ocultar SLIDER (Barra de desplazamiento) */
    [data-testid="stSidebar"] > div {{
        overflow: hidden !important; /* Adiós scrollbar */
        padding-top: 20px;
        display: flex;
        flex-direction: column;
        align-items: center; /* Centrar todo horizontalmente */
    }}

    /* --- 2. CONTENIDO PRINCIPAL --- */
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH} !important; 
        width: calc(100% - {SIDEBAR_WIDTH}) !important;
        padding: 2rem 3rem !important;
        max-width: 100% !important;
    }}

    /* --- 3. BOTONES DE NAVEGACIÓN (SOLO ICONOS) --- */
    
    /* Ocultar círculos de radio */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
        display: none !important;
    }}
    
    /* Estilo del Botón Icono */
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 50px !important;
        height: 50px !important;
        border-radius: 12px !important;
        margin-bottom: 15px !important;
        transition: all 0.3s ease;
        cursor: pointer;
        background-color: transparent;
        color: #94a3b8; /* Gris claro */
        font-size: 24px !important; /* Emoji grande */
        border: 1px solid transparent;
        padding: 0 !important;
    }}
    
    /* Hover */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background-color: #334155;
        color: white;
        transform: scale(1.1);
    }}
    
    /* Activo */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background-color: #3b82f6; /* Azul brillante */
        color: white;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
    }}

    /* Perfil solo Avatar */
    .profile-mini {{
        font-size: 2.5rem;
        text-align: center;
        margin-bottom: 30px;
        cursor: help; /* Muestra tooltip nativo si se posa el mouse */
    }}
    
    /* KPI Cards */
    .kpi-card {{
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-left: 5px solid #3b82f6;
    }}
    .kpi-val {{ font-size: 1.8rem; font-weight: 800; color: #0f172a; }}
    .kpi-lbl {{ color: #64748b; font-size: 0.9rem; font-weight: 600; text-transform: uppercase; }}
</style>
"""

# Aplicar CSS
st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)


# --- 3. CONEXIÓN Y DATOS ---
# Mapeo de navegación: Emoji -> Vista
NAV_MAP = {
    "📅": "calendar",
    "📊": "dashboard",
    "👥": "admin_users",
    "🔑": "admin_reqs"
}

AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"]
        )
    except: return None

# --- 4. LÓGICA DE NEGOCIO ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

def solicitar_reset_pass(username):
    conn = get_connection()
    if not conn: return "error"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
        if cur.fetchone():
            cur.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
            if not cur.fetchone():
                cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
                conn.commit(); conn.close(); return "ok"
            conn.close(); return "pendiente"
        conn.close(); return "no_user"
    except: return "error"

def cargar_datos():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            user = st.session_state['user_info']['username']
            if id_reg is None:
                cur.execute("INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (fecha, prov, plat, serv, mast, paq, com, user))
                st.toast("Guardado correctamente")
            else:
                cur.execute("UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s", (fecha, prov, plat, serv, mast, paq, com, id_reg))
                st.toast("Actualizado correctamente")
            conn.commit(); conn.close()
        except Exception as e: st.error(str(e))

def admin_crear_usuario(u, r):
    conn = get_connection()
    if conn:
        try:
            conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
            conn.commit(); conn.close(); return True
        except: pass
    return False

def admin_get_users():
    conn = get_connection()
    return pd.read_sql("SELECT id, username, rol, activo FROM usuarios", conn) if conn else pd.DataFrame()

def admin_toggle(uid, curr):
    conn = get_connection()
    if conn:
        conn.cursor().execute("UPDATE usuarios SET activo=%s WHERE id=%s", (0 if curr==1 else 1, uid))
        conn.commit(); conn.close()

def admin_restablecer_password(rid, uname):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,))
        cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,))
        conn.commit(); conn.close()

# --- 5. MODAL ---
@st.dialog("Gestión de Carga")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled = (rol == 'analista')
    d_fecha, d_prov, d_plat = date.today(), PROVEEDORES[0], PLATAFORMAS[0]
    d_serv, d_mast, d_paq, d_com, d_id = SERVICIOS[0], "", 0, "", None
    if datos:
        d_id = datos.get('id')
        if datos.get('fecha_str'): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        d_serv = datos.get('servicio', SERVICIOS[0])
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")
    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            min_ = st.text_input("Master", d_mast, disabled=disabled)
            pain = st.number_input("Paquetes", 0, value=int(d_paq), disabled=disabled)
        com = st.text_area("Notas", d_com, disabled=disabled)
        if not disabled:
            if st.form_submit_button("Guardar", type="primary", use_container_width=True):
                guardar_registro(d_id, fin, pin, clin, sin, min_, pain, com)
                st.rerun()

# ==============================================================================
#  INTERFAZ
# ==============================================================================

if not st.session_state['logged_in']:
    # --- LOGIN RESTAURADO ---
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Contenedor visual blanco
    st.markdown("""
        <div class="login-box">
            <h2 style="color:#333; margin-bottom:10px;">Nexus Logística</h2>
            <p style="color:#888; margin-bottom:30px;">Panel de Control</p>
        </div>
    """, unsafe_allow_html=True)

    u = st.text_input("Usuario", placeholder="Ingresa tu usuario", label_visibility="collapsed")
    p = st.text_input("Contraseña", type="password", placeholder="••••••••", label_visibility="collapsed")
    
    st.write("")
    if st.button("INICIAR SESIÓN", type="primary"):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Acceso denegado")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # SECCIÓN RESTAURADA DE RECUPERACIÓN
    with st.expander("¿Olvidaste tu contraseña?"):
        st.caption("Solicita un restablecimiento al administrador.")
        ur = st.text_input("Usuario a recuperar")
        if st.button("Enviar Solicitud"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Solicitud enviada.")
            elif r=="pendiente": st.info("Ya está pendiente.")
            else: st.warning("Usuario no existe.")

else:
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- BARRA LATERAL SOLO ICONOS (90px) ---
    with st.sidebar:
        # Avatar (Solo icono)
        av = AVATARS.get(u_info.get('avatar'), '👤')
        # Usamos title HTML native para tooltip al pasar el mouse
        st.markdown(f"<div class='profile-mini' title='{u_info['username']} ({rol})'>{av}</div>", unsafe_allow_html=True)
        
        # MENÚ DE SOLO ICONOS
        # Definimos las opciones visuales (Solo emojis)
        opts = ["📅", "📊"]
        if rol == 'admin':
            opts.extend(["👥", "🔑"])
            
        seleccion_emoji = st.radio("Nav", opts, label_visibility="collapsed")
        
        # Logout al fondo (Icono de puerta)
        st.markdown("<div style='flex-grow:1'></div>", unsafe_allow_html=True) # Espaciador
        if st.button("🚪", help="Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CONTENIDO PRINCIPAL ---
    # Traducimos el emoji seleccionado a la vista lógica
    vista = NAV_MAP.get(seleccion_emoji, "calendar")
    df = cargar_datos()
    
    if vista == "calendar":
        c1, c2 = st.columns([6, 1])
        c1.title("Calendario Operativo")
        if rol != 'analista':
            if c2.button("➕ Nuevo", type="primary"): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                color = "#3b82f6" 
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316"
                elif "Temu" in r['plataforma_cliente']: color = "#10b981"
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({
                    "title": f"{int(r['paquetes'])}", 
                    "start": r['fecha_str'], 
                    "backgroundColor": color, "borderColor": color, "extendedProps": props
                })
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="calendar_view")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif vista == "dashboard":
        st.title("Reportes")
        if df.empty: st.info("Sin datos.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df['paquetes'].sum():,}</div><div class='kpi-lbl'>Total</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(df)}</div><div class='kpi-lbl'>Viajes</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df['paquetes'].mean():.0f}</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
            st.divider()
            t1, t2 = st.tabs(["Gráficos", "Tabla"])
            with t1:
                st.plotly_chart(px.line(df.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes'), use_container_width=True)
            with t2: st.dataframe(df, use_container_width=True)

    elif vista == "admin_users":
        st.title("Usuarios")
        t_new, t_list = st.tabs(["Crear", "Lista"])
        with t_new:
            with st.form("f_new_u"):
                nu = st.text_input("Usuario")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"):
                    if admin_crear_usuario(nu, nr): st.success("Ok")
        with t_list:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            c1, c2 = st.columns(2)
            uid = c1.selectbox("ID", df_u['id'].tolist() if not df_u.empty else [])
            if uid:
                curr = df_u[df_u['id']==uid]['activo'].values[0]
                if c2.button("Toggle Estado"): admin_toggle(uid, curr); st.rerun()

    elif vista == "admin_reqs":
        st.title("Claves Pendientes")
        try:
            reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
            if reqs.empty: st.info("Nada pendiente.")
            else:
                for _, r in reqs.iterrows():
                    c1, c2 = st.columns([3,1])
                    c1.write(f"User: {r['username']}")
                    if c2.button("Reset (123456)", key=r['id']):
                        admin_restablecer_password(r['id'], r['username']); st.rerun()
        except: st.error("Error BD")
