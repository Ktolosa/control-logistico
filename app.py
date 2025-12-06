import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px

# --- 1. CONFIGURACIÓN INICIAL (CRÍTICO) ---
st.set_page_config(
    page_title="Nexus Logística", 
    layout="wide", 
    initial_sidebar_state="expanded" # Intenta forzar apertura al inicio
)

# Inicializar estado
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"

# --- 2. CSS AVANZADO (DISEÑO & CORRECCIONES) ---

# Dimensiones de la barra (Estrecha normal, un poco más ancha al pasar el mouse)
SIDEBAR_NORMAL = "70px"
SIDEBAR_HOVER = "200px" # Al pasar el mouse se ensancha para ver nombres (opcional) o se mantiene icono

base_css = """
<style>
    /* OCULTAR MENÚ NATIVO DE STREAMLIT (El que dice 'App', 'Dashboard', etc.) */
    [data-testid="stSidebarNav"] { display: none !important; }
    
    /* Ocultar elementos del sistema */
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    footer { display: none !important; }
    
    .stApp { background-color: #f1f5f9; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; } /* Sin barra en login */
    .main .block-container {
        max-width: 400px; padding-top: 15vh; margin: 0 auto;
    }
    div[data-testid="stTextInput"] input {
        border: 1px solid #cbd5e1; padding: 12px; border-radius: 8px;
    }
    div.stButton > button { 
        width: 100%; border-radius: 8px; font-weight: bold; padding: 12px;
        background: #2563eb; color: white; border: none;
    }
</style>
"""

dashboard_css = f"""
<style>
    /* --- 1. BARRA LATERAL INDESTRUCTIBLE --- */
    
    /* Ocultar la flecha 'X' o '>' para que no se pueda cerrar manualmente */
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    /* Forzar que la barra sea visible siempre */
    [data-testid="stSidebar"] {{
        display: block !important;
        width: {SIDEBAR_NORMAL} !important;
        min-width: {SIDEBAR_NORMAL} !important;
        max-width: {SIDEBAR_NORMAL} !important;
        
        /* Posición Fija */
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        
        /* ESTILO VISUAL MEJORADO (Glass Dark) */
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
        border-right: 1px solid #334155;
        box-shadow: 4px 0 15px rgba(0,0,0,0.3);
        
        /* Animación */
        transition: width 0.3s ease, background 0.3s ease;
        padding-top: 1rem;
    }}
    
    /* Efecto al pasar el mouse por la barra (Opcional: aumenta opacidad) */
    [data-testid="stSidebar"]:hover {{
        background: #0f172a !important; /* Más sólido al usarlo */
        width: 80px !important; /* Crece un poquito */
    }}

    /* Eliminar scrollbars feas */
    [data-testid="stSidebar"] > div {{
        overflow: hidden !important;
        width: 100% !important;
        display: flex;
        flex-direction: column;
        align-items: center;
    }}

    /* --- 2. CONTENIDO PRINCIPAL (Sin cortes) --- */
    .main .block-container {{
        margin-left: {SIDEBAR_NORMAL} !important;
        width: calc(100% - {SIDEBAR_NORMAL}) !important;
        padding-top: 2rem !important;
        padding-left: 3rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }}

    /* --- 3. ICONOS DEL MENÚ (DISEÑO) --- */
    
    /* Ocultar el círculo del radio button */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    
    /* Estilo del Botón */
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 48px !important;
        height: 48px !important;
        border-radius: 12px !important;
        margin-bottom: 20px !important;
        cursor: pointer;
        
        /* Colores por defecto (Inactivo) */
        background: rgba(255, 255, 255, 0.05);
        color: #94a3b8; /* Gris claro */
        font-size: 22px !important;
        border: 1px solid transparent;
        transition: all 0.2s ease;
    }}
    
    /* Hover (Al pasar el mouse por el icono) */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background: rgba(255, 255, 255, 0.15);
        color: white;
        transform: scale(1.05);
    }}
    
    /* Activo (Seleccionado) */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #3b82f6; /* Azul Vibrante */
        color: white;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.6); /* Resplandor */
        border: 1px solid #60a5fa;
    }}

    /* Estilos extra para Avatar y KPIs */
    .avatar-container {{
        width: 50px; height: 50px; background: rgba(255,255,255,0.1);
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        margin-bottom: 30px; border: 2px solid #3b82f6; font-size: 24px;
    }}
    
    .kpi-card {{
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-bottom: 3px solid #3b82f6;
    }}
    .kpi-lbl {{ color: #64748b; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }}
    .kpi-val {{ color: #0f172a; font-size: 1.8rem; font-weight: 800; }}
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
    # --- APP COMPLETA ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- 1. BARRA LATERAL (INTEGRADA Y LIMPIA) ---
    with st.sidebar:
        # Avatar Arriba
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"""
            <div style="display:flex; justify-content:center;">
                <div class="avatar-container" title="{u_info['username']}">{av}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # MENÚ DE HERRAMIENTAS (Dashboard incluido como icono)
        # 📅 = Calendario
        # 📊 = Dashboard
        # 👥 = Admin Users
        # 🔑 = Admin Keys
        
        opciones_disponibles = ["📅", "📊"]
        if rol == 'admin':
            opciones_disponibles.extend(["👥", "🔑"])
            
        seleccion = st.radio("Menú", opciones_disponibles, label_visibility="collapsed")
        
        # Mapeo a Vistas
        mapa_vistas = {
            "📅": "calendar",
            "📊": "dashboard_inteligencia", # <- Ahora se accede desde aquí
            "👥": "admin_users",
            "🔑": "admin_reqs"
        }
        st.session_state['current_view'] = mapa_vistas.get(seleccion, "calendar")

        # Botón Salir al fondo
        st.markdown("<div style='flex-grow:1; margin-top:50px;'></div>", unsafe_allow_html=True)
        if st.button("🚪", help="Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 2. VISTAS (SIN ENLACES EXTERNOS) ---
    vista = st.session_state['current_view']
    df = cargar_datos()

    # --- VISTA: CALENDARIO ---
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

    # --- VISTA: DASHBOARD INTELIGENCIA (INTEGRADA) ---
    elif vista == "dashboard_inteligencia":
        st.title("Dashboard de Inteligencia")
        st.markdown("---")
        
        if df.empty: st.info("Sin datos para analizar.")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Total Paquetes</div><div class='kpi-val'>{df['paquetes'].sum():,}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Total Viajes</div><div class='kpi-val'>{len(df)}</div></div>", unsafe_allow_html=True)
            prom = df['paquetes'].mean()
            k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio Carga</div><div class='kpi-val'>{prom:.0f}</div></div>", unsafe_allow_html=True)
            top_c = df['plataforma_cliente'].mode()[0] if not df.empty else "-"
            k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Cliente Top</div><div class='kpi-val'>{top_c}</div></div>", unsafe_allow_html=True)
            
            st.divider()
            
            c_g1, c_g2 = st.columns([2, 1])
            with c_g1:
                st.subheader("Volumen Diario")
                gf = df.groupby('fecha')['paquetes'].sum().reset_index()
                fig = px.area(gf, x='fecha', y='paquetes', color_discrete_sequence=['#3b82f6'])
                st.plotly_chart(fig, use_container_width=True)
            
            with c_g2:
                st.subheader("Share Proveedores")
                fig2 = px.pie(df, names='proveedor_logistico', values='paquetes', hole=0.5)
                st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(df, use_container_width=True)

    # --- VISTA: ADMIN ---
    elif vista == "admin_users":
        st.title("Usuarios")
        t1, t2 = st.tabs(["Crear", "Lista"])
        with t1:
            with st.form("new_u"):
                nu = st.text_input("User")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"):
                    if admin_crear_usuario(nu, nr): st.success("Creado")
        with t2:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            c1, c2 = st.columns(2)
            uid = c1.selectbox("ID", df_u['id'].tolist() if not df_u.empty else [])
            if uid and c2.button("Toggle"):
                curr = df_u[df_u['id']==uid]['activo'].values[0]
                admin_toggle(uid, curr); st.rerun()

    elif vista == "admin_reqs":
        st.title("Claves")
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
        if reqs.empty: st.success("Sin pendientes.")
        else:
            for _, r in reqs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"User: {r['username']}")
                if c2.button("Reset", key=r['id']):
                    admin_restablecer_password(r['id'], r['username']); st.rerun()
