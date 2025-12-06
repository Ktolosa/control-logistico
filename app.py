import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTIÓN DE ESTADO Y PERSISTENCIA (FIX RECARGA) ---
# Funciones DB primero para usarlas en la validación de sesión
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def verificar_usuario_por_id(user_id):
    try:
        conn = get_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE id=%s AND activo=1", (user_id,))
        user = cursor.fetchone(); conn.close()
        return user
    except: return None

# Lógica de Auto-Login al recargar
if 'logged_in' not in st.session_state:
    # Intentar recuperar sesión de la URL
    params = st.query_params
    session_uid = params.get("uid", None)
    
    if session_uid:
        user_recovered = verificar_usuario_por_id(session_uid)
        if user_recovered:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user_recovered
            st.session_state['nav_selection'] = "📅 Calendario"
        else:
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
    else:
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None

if 'nav_selection' not in st.session_state: st.session_state['nav_selection'] = "📅 Calendario"

# --- 3. ESTILOS CSS (FIX SIDEBAR Y LOGIN LIMPIO) ---
st.markdown("""
    <style>
    /* 1. OCULTAR MENÚS DE STREAMLIT PERO DEJAR EL BOTÓN DE SIDEBAR VISIBLE */
    
    /* Ocultar barra superior de colores */
    [data-testid="stDecoration"] { display: none; }
    
    /* Ocultar menú hamburguesa y deploy (derecha) */
    [data-testid="stToolbar"] { visibility: hidden; }
    
    /* El Header contiene el botón de sidebar. Lo hacemos transparente. */
    [data-testid="stHeader"] {
        background-color: transparent;
        z-index: 99;
    }
    
    /* Aseguramos que el botón de colapsar sidebar sea visible y tenga color */
    [data-testid="collapsedControl"] {
        display: block !important;
        visibility: visible !important;
        color: #1e293b !important; /* Color oscuro para que se vea */
    }
    
    /* 2. ESTILO GENERAL */
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
    
    /* 3. SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Perfil en Sidebar */
    .sidebar-profile {
        text-align: center; padding: 20px 10px;
        background: #f1f5f9; border-radius: 12px; margin-bottom: 20px;
        border: 1px solid #e2e8f0;
    }
    .sidebar-avatar { font-size: 3rem; display: block; margin-bottom: 5px; }
    .sidebar-name { font-weight: 700; color: #0f172a; font-size: 1rem; }
    
    /* Menú */
    .nav-label { font-size: 0.75rem; font-weight: 700; color: #94a3b8; margin-top: 15px; margin-bottom: 5px; letter-spacing: 0.5px; }
    
    /* 4. LOGIN MINIMALISTA (Centrado y Limpio) */
    /* Quitamos bordes y fondos extras, solo inputs */
    .login-wrapper { margin-top: 10vh; }
    
    /* Botones */
    div.stButton > button { border-radius: 8px; font-weight: 600; border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# --- 4. CONFIGURACIÓN ---
AVATARS = {
    "avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👷‍♀️",
    "avatar_5": "🤵", "avatar_6": "🕵️‍♀️", "avatar_7": "🦸‍♂️", "avatar_8": "👩‍💻",
    "avatar_9": "🤖", "avatar_10": "🦁"
}
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- 5. FUNCIONES ---
def verificar_login(username, password):
    try:
        conn = get_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone(); conn.close()
        return user
    except: return None

def solicitar_reset_pass(username):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
    if cursor.fetchone():
        cursor.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
            conn.commit(); conn.close(); return "ok"
        conn.close(); return "pendiente"
    conn.close(); return "no_user"

def actualizar_avatar(user_id, nuevo_avatar):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (nuevo_avatar, user_id))
    conn.commit(); conn.close()
    st.session_state['user_info']['avatar'] = nuevo_avatar

# Admin Functions
def admin_crear_usuario(user, role):
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (user, role))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def admin_restablecer_password(request_id, username):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (username,))
    cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (request_id,))
    conn.commit(); conn.close()

# Data Functions
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

# --- 6. MODAL ---
@st.dialog("📝 Gestión")
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
#  MAIN
# ==============================================================================

if not st.session_state['logged_in']:
    # Ocultar sidebar
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    
    # LOGIN MINIMALISTA Y LIMPIO
    # Usamos columnas para centrar y reducir el ancho
    c_left, c_main, c_right = st.columns([1, 1, 1])
    
    with c_main:
        st.markdown("<div class='login-wrapper'></div>", unsafe_allow_html=True)
        # Solo inputs y boton
        u = st.text_input("Usuario", placeholder="Escribe tu usuario")
        p = st.text_input("Contraseña", type="password", placeholder="Escribe tu contraseña")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("INICIAR SESIÓN", type="primary", use_container_width=True):
            user = verificar_login(u, p)
            if user:
                # Login Exitoso
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user
                # ESTABLECER PERSISTENCIA (Truco URL)
                st.query_params["uid"] = str(user['id'])
                st.rerun()
            else:
                st.error("Datos incorrectos")

        with st.expander("¿Problemas para entrar?"):
            u_r = st.text_input("Ingresa tu usuario para restablecer")
            if st.button("Solicitar Ayuda"):
                r = solicitar_reset_pass(u_r)
                if r=="ok": st.success("Solicitud enviada.")
                elif r=="pendiente": st.warning("Ya pendiente.")
                else: st.error("No existe.")

else:
    # --- APP INTERNA ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # BARRA LATERAL
    with st.sidebar:
        # Perfil
        av_icon = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
        <div class="sidebar-profile">
            <span class="sidebar-avatar">{av_icon}</span>
            <div class="sidebar-name">{u_info['username']}</div>
            <div style='color:#64748b; font-size:0.8rem;'>{rol.upper()}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Avatar"):
            cols = st.columns(5)
            for i, (k, v) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(v, key=f"s_{k}"): actualizar_avatar(u_info['id'], k); st.rerun()
        
        st.markdown("<div class='nav-label'>MENÚ</div>", unsafe_allow_html=True)
        opts = ["📅 Calendario", "📊 Dashboards"]
        idx = 0 if st.session_state['nav_selection'] == "📅 Calendario" else 1
        sel = st.radio("Ir a:", opts, index=idx, label_visibility="collapsed")
        st.session_state['nav_selection'] = sel
        
        if rol == 'admin':
            st.markdown("<div class='nav-label'>ADMIN</div>", unsafe_allow_html=True)
            with st.expander("Usuarios"):
                with st.form("add"):
                    nu = st.text_input("Usuario")
                    nr = st.selectbox("Rol", ["user", "analista", "admin"])
                    if st.form_submit_button("Crear"):
                        if admin_crear_usuario(nu, nr): st.success("Creado")
                        else: st.error("Error")
                conn = get_connection(); reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn); conn.close()
                if not reqs.empty:
                    st.warning(f"{len(reqs)} Solicitudes")
                    for _, r in reqs.iterrows():
                        if st.button(f"Reset {r['username']}", key=f"rs_{r['id']}"):
                            admin_restablecer_password(r['id'], r['username']); st.rerun()

        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
            st.query_params.clear() # Limpiar persistencia
            st.rerun()

    # CONTENIDO
    df = cargar_datos_seguros()

    if st.session_state['nav_selection'] == "📅 Calendario":
        c1, c2 = st.columns([5, 1])
        with c1: st.title("Calendario")
        with c2: 
            if rol != 'analista':
                if st.button("➕ NUEVO", type="primary", use_container_width=True): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                c = "#64748b"
                if "AliExpress" in r['plataforma_cliente']: c="#f97316"
                elif "Temu" in r['plataforma_cliente']: c="#10b981"
                elif "Shein" in r['plataforma_cliente']: c="#0f172a"
                
                props = {
                    "id": int(r['id']),
                    "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']),
                    "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']),
                    "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']),
                    "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"{int(r['paquetes'])} - {str(r['proveedor_logistico'])}", "start": r['fecha_str'], "backgroundColor": c, "borderColor": c, "extendedProps": props})

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif st.session_state['nav_selection'] == "📊 Dashboards":
        st.title("Dashboards")
        with st.expander("Filtros", expanded=True):
            f1, f2, f3 = st.columns(3)
            df_f = df.copy()
            if not df.empty:
                sy = f1.multiselect("Año", sorted(df['Año'].unique()))
                sp = f2.multiselect("Proveedor", df['proveedor_logistico'].unique())
                sc = f3.multiselect("Cliente", df['plataforma_cliente'].unique())
                if sy: df_f = df_f[df_f['Año'].isin(sy)]
                if sp: df_f = df_f[df_f['proveedor_logistico'].isin(sp)]
                if sc: df_f = df_f[df_f['plataforma_cliente'].isin(sc)]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Paquetes", f"{df_f['paquetes'].sum():,}")
            k2.metric("Lotes", len(df_f))
            try: top=df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top="-"
            k3.metric("Top Cliente", top)
            
            t1, t2, t3 = st.tabs(["Volumen", "Distribución", "Exportar"])
            with t1:
                g = df_f.groupby('fecha')['paquetes'].sum().reset_index()
                st.plotly_chart(px.line(g, x='fecha', y='paquetes', markers=True), use_container_width=True)
            with t2:
                c_a, c_b = st.columns(2)
                with c_a: st.plotly_chart(px.pie(df_f, values='paquetes', names='proveedor_logistico', title="Proveedor"), use_container_width=True)
                with c_b: st.plotly_chart(px.pie(df_f, values='paquetes', names='plataforma_cliente', title="Cliente"), use_container_width=True)
            with t3:
                st.download_button("Descargar CSV", df_f.to_csv(index=False).encode('utf-8'), "data.csv")
        else: st.info("Sin datos")
