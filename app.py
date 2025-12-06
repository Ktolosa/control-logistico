import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# --- 2. ESTILOS CSS (BARRA FIJA, DELGADA Y UI MODERNA) ---
st.markdown("""
    <style>
    /* 1. FORZAR BARRA LATERAL FIJA Y DELGADA */
    [data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 240px !important;
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    /* OCULTAR EL BOTÓN DE CERRAR BARRA LATERAL (FIJA) */
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* 2. LIMPIEZA DE INTERFAZ */
    [data-testid="stToolbar"] { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stHeader"] { background: transparent; }
    
    /* 3. ESTILO DE NAVEGACIÓN */
    .nav-header {
        font-size: 0.75rem;
        font-weight: 800;
        color: #94a3b8;
        margin-top: 20px;
        margin-bottom: 10px;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    
    /* 4. TARJETAS DE PERFIL */
    .profile-mini {
        background: #f8fafc;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        text-align: center;
        margin-bottom: 10px;
    }
    .p-avatar { font-size: 2.5rem; margin-bottom: 5px; }
    .p-name { font-weight: bold; font-size: 0.95rem; color: #1e293b; }
    .p-role { font-size: 0.75rem; color: #3b82f6; font-weight: 700; text-transform: uppercase; }

    /* 5. LOGIN */
    .login-container {
        margin-top: 10vh;
        background: white; padding: 40px; border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        max-width: 380px; margin-left: auto; margin-right: auto;
    }
    
    /* 6. KPIS DASHBOARD */
    .kpi-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-left: 4px solid #2563eb;
    }
    .kpi-val { font-size: 1.6rem; font-weight: 800; color: #1e293b; }
    .kpi-lbl { color: #64748b; font-size: 0.85rem; font-weight: 600; }
    
    /* Ajuste de botones */
    div.stButton > button { border-radius: 6px; font-weight: 600; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN Y DATOS ---
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

# --- 4. FUNCIONES DE GESTIÓN (CRUD) ---

# Auth
def verificar_login(username, password):
    try:
        conn = get_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone(); conn.close()
        return user
    except: return None

def actualizar_mi_perfil(uid, new_user, new_pass):
    conn = get_connection(); cursor = conn.cursor()
    if new_pass:
        cursor.execute("UPDATE usuarios SET username=%s, password=%s WHERE id=%s", (new_user, new_pass, uid))
    else:
        cursor.execute("UPDATE usuarios SET username=%s WHERE id=%s", (new_user, uid))
    conn.commit(); conn.close()
    st.session_state['user_info']['username'] = new_user

def actualizar_avatar(user_id, nuevo_avatar):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (nuevo_avatar, user_id))
    conn.commit(); conn.close()
    st.session_state['user_info']['avatar'] = nuevo_avatar

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

# Admin
def admin_crear_usuario(user, role):
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (user, role))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def admin_get_users():
    conn = get_connection()
    df = pd.read_sql("SELECT id, username, rol, activo, created_at, avatar FROM usuarios", conn)
    conn.close()
    return df

def admin_toggle_status(uid, current):
    new = 0 if current == 1 else 1
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new, uid))
    conn.commit(); conn.close()

def admin_get_reqs():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn)
    conn.close()
    return df

def admin_resolve_req(req_id, username):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (username,))
    cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (req_id,))
    conn.commit(); conn.close()

# Datos Logísticos
def cargar_datos():
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
        st.toast("✨ Guardado")
    else:
        sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
        st.toast("✏️ Actualizado")
    conn.commit(); conn.close()

# --- 5. MODAL REGISTRO ---
@st.dialog("📝 Operación")
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
            mast_in = st.text_input("Master / Lote", d_mast, disabled=disabled)
            paq_in = st.number_input("Paquetes", min_value=0, value=int(d_paq), disabled=disabled)
        com_in = st.text_area("Notas", d_com, disabled=disabled, height=60)
        
        if not disabled:
            if st.form_submit_button("GUARDAR DATOS", type="primary", use_container_width=True):
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()

# ==============================================================================
#  LÓGICA PRINCIPAL
# ==============================================================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    # Ocultar Sidebar en Login
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    
    # Login Limpio
    st.markdown("""
        <div class="login-container">
            <h2 style="text-align:center; color:#1e293b;">Bienvenido</h2>
            <p style="text-align:center; color:#64748b;">Inicia sesión en Nexus Logística</p>
    """, unsafe_allow_html=True)
    
    u = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
    p = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("INGRESAR", type="primary", use_container_width=True):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Datos incorrectos")
        
    with st.expander("¿Olvidaste tu contraseña?"):
        ur = st.text_input("Tu Usuario")
        if st.button("Enviar Solicitud"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Solicitud enviada.")
            else: st.warning("No se pudo enviar.")
    
    st.markdown("</div>", unsafe_allow_html=True)

else:
    # --- APP COMPLETA ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- BARRA LATERAL FIJA Y DELGADA ---
    with st.sidebar:
        # Perfil Mini
        av_icon = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
        <div class="profile-mini">
            <div class="p-avatar">{av_icon}</div>
            <div class="p-name">{u_info['username']}</div>
            <div class="p-role">{rol}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # MENÚ DE NAVEGACIÓN UNIFICADO (Aquí agregamos lo que pediste)
        st.markdown("<div class='nav-header'>PRINCIPAL</div>", unsafe_allow_html=True)
        
        # Opciones base
        menu_options = ["📅 Operaciones", "📊 Análisis BI", "👤 Mi Perfil"]
        
        # Opciones extra si es Admin (Se agregan DIRECTAMENTE al menú)
        if rol == 'admin':
            menu_options.insert(2, "👥 Gestión Usuarios")
            menu_options.insert(3, "🔐 Solicitudes")

        # Widget de Navegación
        selection = st.radio("Navegación", menu_options, label_visibility="collapsed")
        
        st.divider()
        if st.button("Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- PÁGINAS ---
    df = cargar_datos()

    # 1. OPERACIONES (CALENDARIO)
    if selection == "📅 Operaciones":
        c1, c2 = st.columns([5, 1])
        with c1: st.title("Calendario Operativo")
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
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"{int(r['paquetes'])} - {r['proveedor_logistico']}", "start": r['fecha_str'], "backgroundColor": c, "borderColor": c, "extendedProps": props})

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # 2. ANÁLISIS BI (DASHBOARD MEJORADO)
    elif selection == "📊 Análisis BI":
        st.title("Inteligencia de Datos")
        
        with st.expander("🔎 FILTRAR DATOS", expanded=True):
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

        if df_f.empty: st.warning("Sin datos.")
        else:
            # KPIS
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df_f['paquetes'].sum():,}</div><div class='kpi-lbl'>Total Paquetes</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(df_f)}</div><div class='kpi-lbl'>Total Lotes</div></div>", unsafe_allow_html=True)
            try: top = df_f.groupby('proveedor_logistico')['paquetes'].sum().idxmax()
            except: top="-"
            k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{top}</div><div class='kpi-lbl'>Top Proveedor</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><div class='kpi-val'>{int(df_f['paquetes'].mean())}</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # PESTAÑAS DE ANÁLISIS AVANZADO
            t1, t2, t3, t4 = st.tabs(["📈 Evolución & Comparativa", "📦 Distribución (Boxplot)", "🔥 Heatmap", "📋 Datos Detallados"])
            
            with t1:
                c_a, c_b = st.columns(2)
                with c_a:
                    # Linea temporal
                    g_line = df_f.groupby('fecha')['paquetes'].sum().reset_index()
                    st.plotly_chart(px.line(g_line, x='fecha', y='paquetes', title="Tendencia de Volumen", markers=True), use_container_width=True)
                with c_b:
                    # Sunburst
                    st.plotly_chart(px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico'], values='paquetes', title="Jerarquía de Carga"), use_container_width=True)

            with t2:
                # Boxplot para ver variabilidad de carga
                st.markdown("#### Análisis de Variabilidad (Boxplot)")
                fig_box = px.box(df_f, x='proveedor_logistico', y='paquetes', color='proveedor_logistico', title="Distribución de Paquetes por Lote (Rango de Carga)")
                st.plotly_chart(fig_box, use_container_width=True)
                
                # Barras apiladas
                st.plotly_chart(px.bar(df_f, x='proveedor_logistico', y='paquetes', color='tipo_servicio', title="Volumen por Servicio"), use_container_width=True)

            with t3:
                # Heatmap Día/Semana
                st.plotly_chart(px.density_heatmap(df_f, x='Semana', y='DiaSemana', z='paquetes', color_continuous_scale="Viridis", title="Mapa de Calor de Operaciones"), use_container_width=True)

            with t4:
                # Tabla Pivote y Export
                st.subheader("Datos Tabulares")
                st.dataframe(df_f, use_container_width=True)
                csv = df_f.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar CSV", csv, "data_export.csv", "text/csv")

    # 3. GESTIÓN USUARIOS (SOLO ADMIN)
    elif selection == "👥 Gestión Usuarios":
        st.title("Gestión de Usuarios")
        
        t_create, t_list = st.tabs(["Crear Nuevo", "Lista de Usuarios"])
        
        with t_create:
            with st.form("new_user_f"):
                nu = st.text_input("Nombre de Usuario")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                st.caption("Contraseña por defecto: 123456")
                if st.form_submit_button("Crear Usuario"):
                    if admin_crear_usuario(nu, nr): st.success("Usuario creado.")
                    else: st.error("Error al crear.")
        
        with t_list:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            
            c_act1, c_act2 = st.columns([3, 1])
            uid_sel = c_act1.selectbox("Seleccionar Usuario ID", df_u['id'].tolist())
            curr_stat = df_u[df_u['id']==uid_sel]['activo'].values[0]
            lbl = "🔴 Desactivar" if curr_stat == 1 else "🟢 Activar"
            
            if c_act2.button(lbl):
                admin_toggle_status(uid_sel, curr_stat)
                st.rerun()

    # 4. SOLICITUDES (SOLO ADMIN)
    elif selection == "🔐 Solicitudes":
        st.title("Restablecimiento de Contraseñas")
        reqs = admin_get_reqs()
        
        if reqs.empty: st.info("No hay solicitudes pendientes.")
        else:
            for _, r in reqs.iterrows():
                with st.expander(f"Solicitud de: {r['username']}", expanded=True):
                    if st.button(f"Restablecer Clave a '123456'", key=f"req_{r['id']}"):
                        admin_resolve_req(r['id'], r['username'])
                        st.success("Contraseña restablecida.")
                        st.rerun()

    # 5. MI PERFIL
    elif selection == "👤 Mi Perfil":
        st.title("Mi Cuenta")
        
        c_prof1, c_prof2 = st.columns([1, 2])
        
        with c_prof1:
            st.markdown("#### Avatar")
            cols = st.columns(3)
            for i, (k, v) in enumerate(AVATARS.items()):
                with cols[i%3]:
                    if st.button(v, key=f"prof_av_{k}"): actualizar_avatar(u_info['id'], k); st.rerun()
        
        with c_prof2:
            st.markdown("#### Credenciales")
            with st.form("my_creds"):
                new_u = st.text_input("Usuario", value=u_info['username'])
                new_p = st.text_input("Nueva Contraseña (Opcional)", type="password")
                if st.form_submit_button("Actualizar Datos"):
                    actualizar_mi_perfil(u_info['id'], new_u, new_p)
                    st.success("Perfil actualizado. Por favor inicia sesión nuevamente.")
                    st.session_state['logged_in'] = False
                    st.rerun()
