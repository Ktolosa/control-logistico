import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# --- 2. ESTILOS CSS (DISEÑO PROFESIONAL) ---
st.markdown("""
    <style>
    /* OCULTAR ELEMENTOS NATIVOS MOLESTOS */
    [data-testid="stToolbar"] { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stHeader"] { background: transparent; }
    
    /* FONDO GENERAL */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    /* LOGIN MINIMALISTA (Centrado perfecto sin adornos) */
    .login-container {
        margin-top: 15vh;
        padding: 40px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        max-width: 400px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* BARRA LATERAL PERSONALIZADA */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    /* Tarjeta de Perfil en Sidebar */
    .profile-card {
        background-color: #f8fafc;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #e2e8f0;
        margin-bottom: 20px;
    }
    .profile-avatar { font-size: 3rem; margin-bottom: 5px; }
    .profile-name { font-weight: bold; color: #1e293b; font-size: 1.1rem; }
    .profile-role { color: #64748b; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Botones y Métricas */
    div.stButton > button { border-radius: 6px; font-weight: 600; border: none; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    
    .kpi-card {
        background: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #3b82f6;
    }
    .kpi-val { font-size: 1.8rem; font-weight: bold; color: #0f172a; }
    .kpi-lbl { color: #64748b; font-size: 0.9rem; }
    </style>
""", unsafe_allow_html=True)

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
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- 4. FUNCIONES DE LOGICA ---
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
    df = pd.read_sql("SELECT id, username, rol, activo, created_at FROM usuarios", conn)
    conn.close()
    return df

def admin_toggle_status(uid, current):
    new = 0 if current == 1 else 1
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new, uid))
    conn.commit(); conn.close()

def admin_restablecer_password(request_id, username):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (username,))
    cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (request_id,))
    conn.commit(); conn.close()

# Data
def cargar_datos_completos():
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            df = df.dropna(subset=['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            # Columnas de análisis extra
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
        st.toast("✨ Guardado con éxito")
    else:
        sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
        st.toast("✏️ Actualizado con éxito")
    conn.commit(); conn.close()

# --- 5. MODAL DE REGISTRO ---
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
#  LÓGICA PRINCIPAL
# ==============================================================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

if not st.session_state['logged_in']:
    # --- LOGIN MINIMALISTA (SIN HEADER) ---
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    
    # Contenedor centrado y limpio
    col_l, col_m, col_r = st.columns([1, 1, 1])
    with col_m:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        # Tabs sutiles
        t1, t2 = st.tabs(["Ingresar", "Ayuda"])
        
        with t1:
            u = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
            p = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INICIAR SESIÓN", type="primary", use_container_width=True):
                user = verificar_login(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user
                    st.session_state['view'] = "calendar" # Default
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        
        with t2:
            ur = st.text_input("Ingresa tu usuario", key="reset")
            if st.button("Solicitar restablecimiento"):
                r = solicitar_reset_pass(ur)
                if r == "ok": st.success("Solicitud enviada al Admin.")
                else: st.warning("No se pudo procesar (Usuario no existe o ya pendiente).")

else:
    # --- APLICACIÓN COMPLETA ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- BARRA LATERAL FIJA Y REDISEÑADA ---
    with st.sidebar:
        # 1. TARJETA DE PERFIL
        av_icon = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
        <div class="profile-card">
            <div class="profile-avatar">{av_icon}</div>
            <div class="profile-name">{u_info['username']}</div>
            <div class="profile-role">{rol}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("⚙️ Configuración"):
            st.caption("Cambiar Avatar")
            cols = st.columns(5)
            for i, (k, v) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(v, key=f"av_{k}"): actualizar_avatar(u_info['id'], k); st.rerun()
        
        st.divider()
        
        # 2. MENÚ DE NAVEGACIÓN
        st.caption("NAVEGACIÓN")
        menu = st.radio("Ir a:", ["📅 Calendario", "📊 Análisis & Reportes"], label_visibility="collapsed")
        
        # 3. SECCIÓN ADMIN (SOLO VISIBLE PARA ADMIN)
        if rol == 'admin':
            st.divider()
            st.caption("ADMINISTRACIÓN")
            admin_opts = st.selectbox("Herramientas", ["Gestión Usuarios", "Solicitudes Clave"])
            if admin_opts == "Gestión Usuarios":
                st.session_state['view'] = "admin_users"
            elif admin_opts == "Solicitudes Clave":
                st.session_state['view'] = "admin_reqs"
            
            # Forzar vista si selecciona menú principal
            if menu == "📅 Calendario": st.session_state['view'] = "calendar"
            elif menu == "📊 Análisis & Reportes": st.session_state['view'] = "dashboard"
        else:
             if menu == "📅 Calendario": st.session_state['view'] = "calendar"
             elif menu == "📊 Análisis & Reportes": st.session_state['view'] = "dashboard"

        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CONTENIDO PRINCIPAL ---
    df = cargar_datos_completos()
    vista = st.session_state['view']

    # >> VISTA 1: CALENDARIO
    if vista == "calendar":
        c1, c2 = st.columns([5, 1])
        with c1: st.title("Calendario Operativo")
        with c2: 
            if rol != 'analista':
                if st.button("➕ NUEVO", type="primary", use_container_width=True): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                color = "#64748b"
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316"
                elif "Temu" in r['plataforma_cliente']: color = "#10b981"
                elif "Shein" in r['plataforma_cliente']: color = "#0f172a"
                
                # Props seguros
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"{int(r['paquetes'])} - {r['proveedor_logistico']}", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # >> VISTA 2: DASHBOARDS COMPLETOS
    elif vista == "dashboard":
        st.title("Centro de Análisis de Datos")
        
        # FILTROS PROFUNDOS
        with st.expander("🔎 FILTROS AVANZADOS", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            df_f = df.copy()
            if not df.empty:
                yrs = sorted(df['Año'].unique())
                provs = df['proveedor_logistico'].unique()
                clis = df['plataforma_cliente'].unique()
                servs = df['tipo_servicio'].unique()
                weeks = sorted(df['Semana'].unique())
                
                sy = f1.multiselect("Año", yrs)
                sm = f2.multiselect("Mes", df['Mes'].unique())
                sw = f3.multiselect("Semana", weeks)
                sp = f4.multiselect("Proveedor", provs)
                sc = f5.multiselect("Cliente", clis)
                
                if sy: df_f = df_f[df_f['Año'].isin(sy)]
                if sm: df_f = df_f[df_f['Mes'].isin(sm)]
                if sw: df_f = df_f[df_f['Semana'].isin(sw)]
                if sp: df_f = df_f[df_f['proveedor_logistico'].isin(sp)]
                if sc: df_f = df_f[df_f['plataforma_cliente'].isin(sc)]
        
        if df_f.empty: st.warning("No hay datos coincidentes.")
        else:
            # KPIS
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df_f['paquetes'].sum():,}</div><div class='kpi-lbl'>Total Paquetes</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(df_f)}</div><div class='kpi-lbl'>Total Viajes</div></div>", unsafe_allow_html=True)
            try: top = df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top = "-"
            k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{top}</div><div class='kpi-lbl'>Cliente Top</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><div class='kpi-val'>{int(df_f['paquetes'].mean())}</div><div class='kpi-lbl'>Promedio</div></div>", unsafe_allow_html=True)
            
            st.divider()
            
            # PESTAÑAS DE ANÁLISIS
            t1, t2, t3, t4 = st.tabs(["📈 Evolución", "🍰 Distribución", "🔥 Intensidad", "📥 Datos & Exportar"])
            
            with t1:
                # Grafico Linea Tiempo
                g_df = df_f.groupby('fecha')['paquetes'].sum().reset_index()
                fig = px.line(g_df, x='fecha', y='paquetes', markers=True, title="Tendencia de Volumen Diario")
                fig.update_traces(line_color='#2563eb', line_width=3)
                st.plotly_chart(fig, use_container_width=True)
            
            with t2:
                c_a, c_b = st.columns(2)
                with c_a: 
                    # Sunburst
                    fig = px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico'], values='paquetes', title="Distribución Jerárquica")
                    st.plotly_chart(fig, use_container_width=True)
                with c_b:
                    # Barras
                    fig = px.bar(df_f, x='proveedor_logistico', y='paquetes', color='tipo_servicio', title="Volumen por Proveedor y Servicio")
                    st.plotly_chart(fig, use_container_width=True)
            
            with t3:
                # Heatmap
                fig = px.density_heatmap(df_f, x='Semana', y='DiaSemana', z='paquetes', color_continuous_scale="Viridis", title="Mapa de Calor (Semana vs Día)")
                st.plotly_chart(fig, use_container_width=True)
                
            with t4:
                st.subheader("Exportación de Datos")
                cols = st.multiselect("Columnas a exportar", df_f.columns.tolist(), default=['fecha', 'proveedor_logistico', 'plataforma_cliente', 'paquetes', 'master_lote'])
                if cols:
                    df_exp = df_f[cols]
                    csv = df_exp.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 DESCARGAR EXCEL/CSV", csv, "reporte_logistica.csv", "text/csv", type="primary")
                st.dataframe(df_f, use_container_width=True)

    # >> VISTAS ADMIN
    elif vista == "admin_users":
        st.title("Gestión de Usuarios")
        t_crear, t_ver = st.tabs(["Crear Usuario", "Ver Todos"])
        
        with t_crear:
            with st.form("new_u"):
                nu = st.text_input("Usuario")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear Usuario (Clave: 123456)"):
                    if admin_crear_usuario(nu, nr): st.success("Creado")
                    else: st.error("Error")
        
        with t_ver:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            
            c_u1, c_u2 = st.columns(2)
            uid = c_u1.selectbox("Seleccionar Usuario", df_u['id'].tolist())
            current = df_u[df_u['id']==uid]['activo'].values[0]
            lbl = "Desactivar" if current==1 else "Activar"
            if c_u2.button(f"{lbl} Usuario"):
                admin_toggle_status(uid, current); st.rerun()

    elif vista == "admin_reqs":
        st.title("Solicitudes de Contraseña")
        conn = get_connection(); reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn); conn.close()
        
        if reqs.empty: st.info("No hay solicitudes pendientes.")
        else:
            for _, r in reqs.iterrows():
                c_r1, c_r2 = st.columns([3, 1])
                c_r1.warning(f"Usuario **{r['username']}** solicitó resetear su clave.")
                if c_r2.button(f"Resetear a '123456'", key=f"rs_{r['id']}"):
                    admin_restablecer_password(r['id'], r['username'])
                    st.success("Hecho"); st.rerun()
