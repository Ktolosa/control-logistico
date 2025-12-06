import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# Inicializar estado de sesión si no existe
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 2. GESTIÓN DE CSS DINÁMICO ---
# Definimos el CSS base
base_css = """
<style>
    /* Ocultar elementos innecesarios de Streamlit */
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    [data-testid="stSidebarNav"] { display: none !important; } /* Ocultar nav nativa */
    
    /* Fondo general */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    /* Estilos de botones */
    div.stButton > button { border-radius: 6px; font-weight: 600; border: none; width: 100%; }
</style>
"""

# CSS Específico para cuando el usuario YA ESTÁ DENTRO (Barra Fija Visible)
dashboard_css = """
<style>
    /* FORZAR BARRA LATERAL VISIBLE Y FIJA */
    [data-testid="stSidebar"] {
        display: block !important;
        width: 260px !important;
        min-width: 260px !important;
        transform: translateX(0) !important; /* Evita que se oculte */
        visibility: visible !important;
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        height: 100vh !important;
        z-index: 99999;
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    /* Ocultar la flecha de colapsar */
    [data-testid="collapsedControl"] { display: none !important; }

    /* EMPUJAR EL CONTENIDO A LA DERECHA */
    .main .block-container {
        margin-left: 260px !important;
        padding-top: 2rem !important;
        max-width: calc(100% - 260px) !important;
    }

    /* Estilos de tarjetas */
    .kpi-card {
        background: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #3b82f6;
    }
    .kpi-val { font-size: 1.8rem; font-weight: bold; color: #0f172a; }
    .kpi-lbl { color: #64748b; font-size: 0.9rem; }
    
    .profile-card {
        background-color: #f8fafc; padding: 15px; border-radius: 10px;
        text-align: center; border: 1px solid #e2e8f0; margin-bottom: 20px; margin-top: 20px;
    }
</style>
"""

# CSS Específico para el LOGIN (Ocultar Barra, Centrar contenido)
login_css = """
<style>
    /* OCULTAR COMPLETAMENTE LA BARRA LATERAL EN EL LOGIN */
    section[data-testid="stSidebar"] { display: none !important; }
    
    /* Centrar el contenido del login */
    .main .block-container {
        max-width: 800px;
        padding-top: 5rem;
    }
    
    /* Estilo limpio para los inputs */
    div[data-testid="stTextInput"] input {
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 5px;
    }
</style>
"""

# Aplicar CSS según estado
st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)


# --- 3. DATOS Y CONEXIÓN ---
AVATARS = {
    "avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👷‍♀️",
    "avatar_5": "🤵", "avatar_6": "🕵️‍♀️", "avatar_7": "🦸‍♂️", "avatar_8": "👩‍💻",
    "avatar_9": "🤖", "avatar_10": "🦁"
}
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    # Uso try/except para evitar crash si no hay config de secrets
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"]
        )
    except Exception as e:
        st.error(f"Error de conexión DB: {e}")
        return None

# --- 4. FUNCIONES LÓGICAS ---
def verificar_login(username, password):
    conn = get_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone()
        conn.close()
        return user
    except: return None

def solicitar_reset_pass(username):
    conn = get_connection()
    if not conn: return "error"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
        if cursor.fetchone():
            cursor.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
                conn.commit(); conn.close(); return "ok"
            conn.close(); return "pendiente"
        conn.close(); return "no_user"
    except: return "error"

def actualizar_avatar(user_id, nuevo_avatar):
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (nuevo_avatar, user_id))
            conn.commit(); conn.close()
            st.session_state['user_info']['avatar'] = nuevo_avatar
        except: pass

def cargar_datos_completos():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
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
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            user = st.session_state['user_info']['username']
            if id_reg is None:
                sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, user))
                st.toast("✨ Guardado con éxito")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
                st.toast("✏️ Actualizado con éxito")
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error: {e}")

# Funciones Admin
def admin_crear_usuario(user, role):
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (user, role))
            conn.commit(); conn.close(); return True
        except: 
            conn.close(); return False
    return False

def admin_get_users():
    conn = get_connection()
    if conn:
        df = pd.read_sql("SELECT id, username, rol, activo, created_at FROM usuarios", conn)
        conn.close(); return df
    return pd.DataFrame()

def admin_toggle_status(uid, current):
    conn = get_connection()
    if conn:
        new = 0 if current == 1 else 1
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new, uid))
        conn.commit(); conn.close()

def admin_restablecer_password(request_id, username):
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (username,))
        cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (request_id,))
        conn.commit(); conn.close()

# --- 5. MODAL REGISTRO ---
@st.dialog("📝 Gestión de Carga")
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
            fecha_in = st.date_input("Fecha llegada", d_fecha, disabled=disabled)
            prov_in = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            plat_in = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            serv_in = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv), disabled=disabled)
            mast_in = st.text_input("Master ID", d_mast, disabled=disabled)
            paq_in = st.number_input("Cantidad Paquetes", min_value=0, value=int(d_paq), disabled=disabled)
        com_in = st.text_area("Notas", d_com, disabled=disabled, height=60)
        
        if not disabled:
            if st.form_submit_button("GUARDAR DATOS", type="primary", use_container_width=True):
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()

# ==============================================================================
#  LÓGICA PRINCIPAL (INTERFAZ)
# ==============================================================================

if not st.session_state['logged_in']:
    # --- PANTALLA DE LOGIN ---
    
    # Columnas para centrar y reducir el ancho del formulario
    col_izq, col_centro, col_der = st.columns([1, 1.5, 1])
    
    with col_centro:
        st.markdown("<h2 style='text-align: center; color: #333;'>Nexus Logística</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 30px;'>Inicia sesión para continuar</p>", unsafe_allow_html=True)
        
        # Inputs directos (Sin divs fantasmas alrededor)
        u = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        p = st.text_input("Contraseña", type="password", placeholder="••••••••")
        
        st.write("") # Espaciador
        
        if st.button("INGRESAR", type="primary", use_container_width=True):
            user = verificar_login(u, p)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        
        st.markdown("---")
        with st.expander("Recuperar acceso"):
            ur = st.text_input("Usuario a recuperar")
            if st.button("Enviar solicitud"):
                r = solicitar_reset_pass(ur)
                if r=="ok": st.success("Solicitud enviada al administrador.")
                elif r=="pendiente": st.info("Ya tienes una solicitud pendiente.")
                else: st.warning("Usuario no existe.")

else:
    # --- PANTALLA DASHBOARD (SIDEBAR SIEMPRE VISIBLE) ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # 1. Contenido de la Barra Lateral
    with st.sidebar:
        # Perfil
        av_icon = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
        <div class="profile-card">
            <div class="profile-avatar">{av_icon}</div>
            <div class="profile-name">{u_info['username']}</div>
            <div class="profile-role">{rol}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Avatar"):
            cols = st.columns(5)
            for i, (k, v) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(v, key=f"av_{k}"): actualizar_avatar(u_info['id'], k); st.rerun()
        
        st.markdown("---")
        
        # Navegación (Botones estáticos)
        menu = st.radio("Navegación", ["📅 Calendario", "📊 Reportes"], label_visibility="collapsed")
        
        if rol == 'admin':
            st.divider()
            st.caption("ADMINISTRACIÓN")
            admin_opts = st.radio("Admin", ["👥 Usuarios", "🔑 Claves"], label_visibility="collapsed")
            
            # Lógica de vistas admin
            if admin_opts == "👥 Usuarios": st.session_state['view'] = "admin_users"
            elif admin_opts == "🔑 Claves": st.session_state['view'] = "admin_reqs"
            
            # Si el usuario cambia el menú principal, salimos del modo admin
            if 'last_menu' not in st.session_state: st.session_state['last_menu'] = menu
            if st.session_state['last_menu'] != menu:
                 st.session_state['view'] = "calendar" if menu == "📅 Calendario" else "dashboard"
            st.session_state['last_menu'] = menu
        else:
             if menu == "📅 Calendario": st.session_state['view'] = "calendar"
             elif menu == "📊 Reportes": st.session_state['view'] = "dashboard"

        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # 2. Contenido Principal
    df = cargar_datos_completos()
    vista = st.session_state.get('view', 'calendar')

    if vista == "calendar":
        c1, c2 = st.columns([5, 1])
        with c1: st.title("Calendario Operativo")
        with c2: 
            if rol != 'analista':
                if st.button("➕ NUEVO", type="primary", use_container_width=True): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                color = "#64748b" # Gris default
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316" # Naranja
                elif "Temu" in r['plataforma_cliente']: color = "#10b981" # Verde
                elif "Shein" in r['plataforma_cliente']: color = "#0f172a" # Negro
                
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"{int(r['paquetes'])} Pkgs", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif vista == "dashboard":
        st.title("Centro de Análisis")
        
        with st.expander("🔎 FILTROS", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            df_f = df.copy()
            if not df.empty:
                sy = f1.multiselect("Año", sorted(df['Año'].unique()))
                sm = f2.multiselect("Mes", df['Mes'].unique())
                sp = f3.multiselect("Proveedor", df['proveedor_logistico'].unique())
                sc = f4.multiselect("Cliente", df['plataforma_cliente'].unique())
                ss = f5.multiselect("Servicio", df['tipo_servicio'].unique())
                
                if sy: df_f = df_f[df_f['Año'].isin(sy)]
                if sm: df_f = df_f[df_f['Mes'].isin(sm)]
                if sp: df_f = df_f[df_f['proveedor_logistico'].isin(sp)]
                if sc: df_f = df_f[df_f['plataforma_cliente'].isin(sc)]
                if ss: df_f = df_f[df_f['tipo_servicio'].isin(ss)]
        
        if df_f.empty: st.info("No hay datos para mostrar.")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df_f['paquetes'].sum():,}</div><div class='kpi-lbl'>Total Paquetes</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(df_f)}</div><div class='kpi-lbl'>Viajes</div></div>", unsafe_allow_html=True)
            try: top = df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top = "-"
            k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{top}</div><div class='kpi-lbl'>Top Cliente</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><div class='kpi-val'>{int(df_f['paquetes'].mean())}</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
            
            st.divider()
            t1, t2, t3, t4 = st.tabs(["Evolución", "Distribución", "Heatmap", "Tabla"])
            with t1:
                g = df_f.groupby('fecha')['paquetes'].sum().reset_index()
                st.plotly_chart(px.line(g, x='fecha', y='paquetes', title="Tendencia", markers=True), use_container_width=True)
            with t2:
                c_a, c_b = st.columns(2)
                with c_a: st.plotly_chart(px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico'], values='paquetes'), use_container_width=True)
                with c_b: st.plotly_chart(px.bar(df_f, x='proveedor_logistico', y='paquetes', color='tipo_servicio'), use_container_width=True)
            with t3:
                st.plotly_chart(px.density_heatmap(df_f, x='Semana', y='DiaSemana', z='paquetes', color_continuous_scale="Viridis"), use_container_width=True)
            with t4:
                st.dataframe(df_f, use_container_width=True)

    # VISTAS ADMIN
    elif vista == "admin_users":
        st.title("Gestión de Usuarios")
        t_crear, t_ver = st.tabs(["Crear Nuevo", "Lista Usuarios"])
        with t_crear:
            with st.form("new_u"):
                nu = st.text_input("Nombre Usuario")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear Usuario (Clave por defecto: 123456)"):
                    if admin_crear_usuario(nu, nr): st.success("Usuario creado.")
                    else: st.error("Error al crear.")
        with t_ver:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            if not df_u.empty:
                c1, c2 = st.columns(2)
                uid = c1.selectbox("Seleccionar Usuario ID", df_u['id'].tolist())
                if uid:
                    curr = df_u[df_u['id']==uid]['activo'].values[0]
                    lbl = "Desactivar Acceso" if curr==1 else "Activar Acceso"
                    if c2.button(lbl): admin_toggle_status(uid, curr); st.rerun()

    elif vista == "admin_reqs":
        st.title("Solicitudes de Contraseña")
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
        if reqs.empty: st.info("No hay solicitudes pendientes.")
        else:
            for _, r in reqs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"Usuario: **{r['username']}** - Fecha: {r['created_at']}")
                if c2.button("Restablecer a '123456'", key=r['id']):
                    admin_restablecer_password(r['id'], r['username']); st.rerun()
