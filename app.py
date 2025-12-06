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
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar" # Vista por defecto

# --- 2. CSS AVANZADO (GLASSMORPHISM & ANIMACIONES) ---

# Variables de dimensiones
SIDEBAR_WIDTH_COLLAPSED = "70px"
SIDEBAR_WIDTH_HOVER = "85px"

base_css = """
<style>
    /* Ocultar elementos nativos de Streamlit */
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    .stDeployButton, [data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
    
    .stApp { 
        background-color: #f8fafc; /* Fondo gris muy claro para contraste */
        font-family: 'Segoe UI', sans-serif; 
    }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container {
        max-width: 400px; padding-top: 15vh; margin: 0 auto;
    }
    div[data-testid="stTextInput"] input {
        border: 1px solid #e2e8f0; padding: 12px; border-radius: 10px; background: white;
    }
    div.stButton > button { 
        width: 100%; border-radius: 10px; font-weight: 600; padding: 12px; 
        background: linear-gradient(135deg, #3b82f6, #2563eb); border: none;
    }
</style>
"""

dashboard_css = f"""
<style>
    /* --- 1. BARRA LATERAL DINÁMICA (GLASSMORPHISM) --- */
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    [data-testid="stSidebar"] {{
        display: block !important;
        width: {SIDEBAR_WIDTH_COLLAPSED} !important;
        min-width: {SIDEBAR_WIDTH_COLLAPSED} !important;
        max-width: {SIDEBAR_WIDTH_COLLAPSED} !important;
        
        /* Posición Fija */
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        
        /* ESTILO TRANSPARENTE (Defecto) */
        background-color: rgba(15, 23, 42, 0.75) !important; /* Azul oscuro semi-transparente */
        backdrop-filter: blur(12px); /* Efecto cristal */
        border-right: 1px solid rgba(255, 255, 255, 0.1);
        
        /* Animación suave */
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        padding-top: 20px;
    }}
    
    /* ESTILO HOVER (Cuando el mouse pasa por encima) */
    [data-testid="stSidebar"]:hover {{
        background-color: rgba(15, 23, 42, 0.98) !important; /* Casi sólido */
        width: {SIDEBAR_WIDTH_HOVER} !important;
        min-width: {SIDEBAR_WIDTH_HOVER} !important;
        max-width: {SIDEBAR_WIDTH_HOVER} !important;
        box-shadow: 5px 0 25px rgba(0,0,0,0.2);
    }}

    /* Eliminar scroll interno */
    [data-testid="stSidebar"] > div {{
        overflow: hidden !important;
        width: 100% !important;
        display: flex;
        flex-direction: column;
        align-items: center;
    }}

    /* --- 2. CONTENIDO PRINCIPAL (Seguridad de Espacio) --- */
    /* El margen izquierdo asegura que NADA quede oculto, basado en el ancho hover */
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH_COLLAPSED} !important;
        width: calc(100% - {SIDEBAR_WIDTH_COLLAPSED}) !important;
        padding-top: 2rem !important;
        padding-left: 3rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
        transition: margin-left 0.4s ease;
    }}

    /* --- 3. MENÚ DE HERRAMIENTAS (ICONOS) --- */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    
    /* Estilo Base del Icono */
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 42px !important;
        height: 42px !important;
        border-radius: 12px !important;
        margin-bottom: 25px !important;
        cursor: pointer;
        color: rgba(255, 255, 255, 0.6); /* Icono apagado */
        font-size: 20px !important;
        background: transparent;
        border: 1px solid transparent;
        transition: all 0.3s ease;
    }}
    
    /* Hover en Icono Individual */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        transform: scale(1.1);
    }}
    
    /* Herramienta Activa (Seleccionada) */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        color: white;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.5);
    }}

    /* Tooltip visual personalizado (opcional) */
    .nav-label {{
        font-size: 10px; color: #94a3b8; margin-top: -20px; margin-bottom: 20px;
        opacity: 0; transition: opacity 0.3s;
    }}
    [data-testid="stSidebar"]:hover .nav-label {{ opacity: 1; }}

    /* Cards Estilizadas */
    .kpi-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid #f1f5f9;
        transition: transform 0.2s;
    }}
    .kpi-card:hover {{ transform: translateY(-3px); }}
</style>
"""

# Aplicar CSS
st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)


# --- 3. CONEXIÓN Y DATOS ---
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

# --- Funciones DB ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

def solicitar_reset_pass(username):
    # (Misma lógica anterior)
    conn = get_connection(); 
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
    conn = get_connection(); 
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

# Funciones de escritura (Guardar, Admin) se mantienen igual que tu código funcional
def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            user = st.session_state['user_info']['username']
            if id_reg is None:
                cur.execute("INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (fecha, prov, plat, serv, mast, paq, com, user))
                st.toast("Guardado")
            else:
                cur.execute("UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s", (fecha, prov, plat, serv, mast, paq, com, id_reg))
                st.toast("Actualizado")
            conn.commit(); conn.close()
        except Exception as e: st.error(str(e))

def admin_crear_usuario(u, r):
    conn = get_connection()
    if conn:
        try:
            conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
            conn.commit(); conn.close(); return True
        except: pass; return False

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
        cur = conn.cursor(); 
        cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,))
        cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,))
        conn.commit(); conn.close()

# --- 4. MODAL ---
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
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    # --- LOGIN ---
    st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #1e293b; margin-bottom: 10px;'>Nexus Logística</h2>", unsafe_allow_html=True)
    
    u = st.text_input("Usuario", placeholder="Tu usuario", label_visibility="collapsed")
    st.write("")
    p = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", label_visibility="collapsed")
    st.write("")
    
    if st.button("INICIAR SESIÓN"):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Datos incorrectos")
        
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("¿Olvidaste tu contraseña?"):
        ur = st.text_input("Usuario para restablecer")
        if st.button("Solicitar"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Enviado.")
            elif r=="pendiente": st.info("Pendiente.")
            else: st.warning("No existe.")

else:
    # --- DASHBOARD & BARRA LATERAL ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- 1. BARRA LATERAL GLOBAL (Siempre visible, no cambia) ---
    with st.sidebar:
        # Avatar minimalista
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div style='font-size:2rem; text-align:center; margin-bottom:20px; color:white; opacity:0.9;'>{av}</div>", unsafe_allow_html=True)
        
        # --- MENÚ DE HERRAMIENTAS ---
        # Aquí definimos las herramientas disponibles y sus Iconos
        # 📅 = Calendario
        # 📊 = Dashboard de Análisis e Inteligencia
        # 👥 = Admin Usuarios (Solo Admin)
        # 🔑 = Admin Claves (Solo Admin)
        
        opciones_disponibles = ["📅", "📊"]
        if rol == 'admin':
            opciones_disponibles.extend(["👥", "🔑"])
            
        # Widget de selección
        # IMPORTANTE: Usamos un key único para que no resetee
        seleccion = st.radio("Menú", opciones_disponibles, label_visibility="collapsed")
        
        # Actualizamos la vista global basada en la selección
        mapa_vistas = {
            "📅": "calendar",
            "📊": "dashboard_inteligencia",
            "👥": "admin_users",
            "🔑": "admin_reqs"
        }
        st.session_state['current_view'] = mapa_vistas.get(seleccion, "calendar")

        # Espaciador y Botón Salir
        st.markdown("<div style='flex-grow:1; margin-top:40px;'></div>", unsafe_allow_html=True)
        if st.button("🚪", help="Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 2. RENDERIZADO DE LA HERRAMIENTA ACTIVA ---
    # Esto ocurre en el contenedor principal, respetando los márgenes
    vista = st.session_state['current_view']
    df = cargar_datos()

    # --- HERRAMIENTA 1: CALENDARIO ---
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
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # --- HERRAMIENTA 2: DASHBOARD DE ANÁLISIS E INTELIGENCIA ---
    elif vista == "dashboard_inteligencia":
        st.title("📊 Dashboard de Inteligencia")
        st.markdown("<p style='color:#64748b; margin-top:-10px;'>Análisis profundo de operaciones logísticas</p>", unsafe_allow_html=True)
        
        if df.empty: st.info("No hay datos suficientes para generar inteligencia.")
        else:
            # KPIs Premium
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>📦 Volumen Total</div><div class='kpi-val'>{df['paquetes'].sum():,}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>🚚 Viajes</div><div class='kpi-val'>{len(df)}</div></div>", unsafe_allow_html=True)
            prom = df['paquetes'].mean()
            k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>📈 Promedio/Carga</div><div class='kpi-val'>{prom:.0f}</div></div>", unsafe_allow_html=True)
            top_c = df['plataforma_cliente'].mode()[0] if not df.empty else "-"
            k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>🏆 Top Cliente</div><div class='kpi-val'>{top_c}</div></div>", unsafe_allow_html=True)
            
            st.divider()
            
            # Gráficos Avanzados
            c_g1, c_g2 = st.columns([2, 1])
            with c_g1:
                st.subheader("Tendencia Temporal")
                gf = df.groupby('fecha')['paquetes'].sum().reset_index()
                fig = px.area(gf, x='fecha', y='paquetes', color_discrete_sequence=['#3b82f6'])
                fig.update_layout(xaxis_title=None, yaxis_title=None, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            
            with c_g2:
                st.subheader("Distribución")
                fig2 = px.pie(df, names='proveedor_logistico', values='paquetes', hole=0.6, color_discrete_sequence=px.colors.sequential.Bluyl)
                fig2.update_layout(showlegend=False, annotations=[dict(text='Proveedores', x=0.5, y=0.5, font_size=12, showarrow=False)])
                st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Matriz de Datos Detallada")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # --- HERRAMIENTA 3: ADMIN USUARIOS ---
    elif vista == "admin_users":
        st.title("Gestión de Usuarios")
        t_crear, t_lista = st.tabs(["Nuevo Usuario", "Directorio"])
        with t_crear:
            with st.form("new_u"):
                nu = st.text_input("Username")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear Usuario"):
                    if admin_crear_usuario(nu, nr): st.success("Creado con éxito.")
        with t_lista:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            c_a, c_b = st.columns(2)
            uid = c_a.selectbox("ID Usuario", df_u['id'].tolist() if not df_u.empty else [])
            if uid and c_b.button("Alternar Acceso (Activo/Inactivo)"):
                curr = df_u[df_u['id']==uid]['activo'].values[0]
                admin_toggle(uid, curr); st.rerun()

    # --- HERRAMIENTA 4: ADMIN CLAVES ---
    elif vista == "admin_reqs":
        st.title("Restablecimiento de Claves")
        try:
            reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
            if reqs.empty: st.success("Todo al día. No hay solicitudes.")
            else:
                for _, r in reqs.iterrows():
                    with st.container(border=True):
                        col_req1, col_req2 = st.columns([3, 1])
                        col_req1.markdown(f"**{r['username']}** solicita cambio de clave.")
                        if col_req2.button("Resetear a '123456'", key=r['id']):
                            admin_restablecer_password(r['id'], r['username']); st.rerun()
        except: st.error("Error de conexión.")
