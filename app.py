import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go
import time

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTIÓN DE ESTADO (PERSISTENCIA) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'nav_selection' not in st.session_state:
    st.session_state['nav_selection'] = "📅 Calendario Operativo" # Página por defecto

# --- 3. ESTILOS CSS (Login Limpio + Sidebar Control) ---
st.markdown("""
    <style>
    /* Estilo General */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    /* Login Box Minimalista */
    .login-container {
        background-color: white;
        padding: 40px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        text-align: center;
        max-width: 400px;
        margin: auto;
    }
    .login-title {
        font-size: 24px;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 20px;
    }
    
    /* Sidebar Personalizado */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Avatar Circular */
    .avatar-frame {
        display: flex; justify-content: center; align-items: center;
        margin-bottom: 10px;
    }
    .avatar-icon {
        font-size: 3.5rem;
        background: #f1f5f9;
        border-radius: 50%;
        width: 80px; height: 80px;
        display: flex; justify-content: center; align-items: center;
        border: 2px solid #3b82f6;
    }
    
    /* Botones y Métricas */
    div.stButton > button { border-radius: 6px; font-weight: 600; }
    .metric-box {
        background: white; padding: 15px; border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #3b82f6;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. AVATARES Y DATOS ---
AVATARS = {
    "avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👷‍♀️",
    "avatar_5": "🤵", "avatar_6": "🕵️‍♀️", "avatar_7": "🦸‍♂️", "avatar_8": "👩‍💻",
    "avatar_9": "🤖", "avatar_10": "🦁"
}
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- 5. FUNCIONES DE BASE DE DATOS ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def verificar_login(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (username, password))
        user = cursor.fetchone()
        conn.close()
        return user
    except: return None

def solicitar_reset_pass(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
    if cursor.fetchone():
        cursor.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
            conn.commit(); conn.close(); return "ok"
        conn.close(); return "pendiente"
    conn.close(); return "no_user"

def actualizar_avatar(user_id, nuevo_avatar):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (nuevo_avatar, user_id))
    conn.commit(); conn.close()
    st.session_state['user_info']['avatar'] = nuevo_avatar

# --- Funciones Admin ---
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

# --- Funciones Datos ---
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

# --- 6. MODALES ---
@st.dialog("📝 Gestión de Operaciones")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled_mode = True if rol == 'analista' else False
    
    d_fecha, d_prov, d_plat, d_serv = date.today(), PROVEEDORES[0], PLATAFORMAS[0], SERVICIOS[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        d_id = datos['id']
        if isinstance(datos['fecha_str'], str): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos['proveedor_logistico'] in PROVEEDORES: d_prov = datos['proveedor_logistico']
        if datos['plataforma_cliente'] in PLATAFORMAS: d_plat = datos['plataforma_cliente']
        if datos['tipo_servicio'] in SERVICIOS: d_serv = datos['tipo_servicio']
        d_mast, d_paq, d_com = datos['master_lote'], datos['paquetes'], datos['comentarios']

    with st.form("frm_log"):
        c1, c2 = st.columns(2)
        with c1:
            fecha_in = st.date_input("Fecha", d_fecha, disabled=disabled_mode)
            prov_in = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled_mode)
            plat_in = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled_mode)
        with c2:
            serv_in = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv), disabled=disabled_mode)
            mast_in = st.text_input("Master / Lote", d_mast, disabled=disabled_mode)
            paq_in = st.number_input("Paquetes", min_value=0, value=d_paq, disabled=disabled_mode)
        
        com_in = st.text_area("Notas", d_com, disabled=disabled_mode)
        
        if not disabled_mode:
            if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()
        else:
            st.warning("Solo lectura")
            st.form_submit_button("Cerrar")

# ==============================================================================
#  LÓGICA PRINCIPAL DE NAVEGACIÓN
# ==============================================================================

if not st.session_state['logged_in']:
    # --- PANTALLA DE LOGIN (BARRA LATERAL OCULTA) ---
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    
    col_spacer_l, col_login, col_spacer_r = st.columns([1, 1, 1])
    with col_login:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='login-container'>
                <div class='login-title'>Iniciar Sesión</div>
                <p style='color:gray; font-size:0.9rem;'>Ingresa tus credenciales para acceder</p>
            </div>
        """, unsafe_allow_html=True)
        
        tab_log, tab_rec = st.tabs(["Ingresar", "Ayuda"])
        
        with tab_log:
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("ACCEDER AL SISTEMA", type="primary", use_container_width=True):
                user = verificar_login(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        
        with tab_rec:
            st.info("Si olvidaste tu contraseña, solicita un reseteo.")
            u_rec = st.text_input("Usuario", key="u_rec")
            if st.button("Solicitar Restablecimiento"):
                res = solicitar_reset_pass(u_rec)
                if res == "ok": st.success("Solicitud enviada al Admin.")
                elif res == "pendiente": st.warning("Ya hay una solicitud pendiente.")
                else: st.error("Usuario no encontrado.")

else:
    # --- APLICACIÓN (BARRA LATERAL VISIBLE) ---
    user_info = st.session_state['user_info']
    rol = user_info['rol']
    
    # --- BARRA LATERAL ---
    with st.sidebar:
        # 1. Avatar y Usuario
        av_icon = AVATARS.get(user_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
            <div class='avatar-frame'><div class='avatar-icon'>{av_icon}</div></div>
            <div style='text-align:center; font-weight:bold; font-size:1.2rem;'>{user_info['username']}</div>
            <div style='text-align:center; color:gray; font-size:0.9rem; margin-bottom:20px;'>{rol.upper()}</div>
        """, unsafe_allow_html=True)
        
        with st.expander("⚙️ Mi Perfil"):
            st.caption("Cambiar Avatar")
            cols = st.columns(5)
            for i, (key, icon) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(icon, key=f"av_{key}"):
                        actualizar_avatar(user_info['id'], key)
                        st.rerun()

        st.markdown("---")
        
        # 2. Navegación (Radio Buttons)
        # Usamos session_state para mantener la selección al recargar
        menu_sel = st.radio("Navegación", 
                            ["📅 Calendario Operativo", "📊 Dashboard Intelligence"], 
                            index=0 if st.session_state['nav_selection'] == "📅 Calendario Operativo" else 1)
        st.session_state['nav_selection'] = menu_sel
        
        # 3. Admin Panel
        if rol == 'admin':
            st.markdown("---")
            st.markdown("###### 🛡️ Administración")
            with st.expander("Usuarios y Claves"):
                with st.form("crear_u"):
                    st.caption("Crear nuevo usuario (Clave: 123456)")
                    nu = st.text_input("Usuario")
                    nr = st.selectbox("Rol", ["user", "analista", "admin"])
                    if st.form_submit_button("Crear"):
                        if admin_crear_usuario(nu, nr): st.success("OK")
                        else: st.error("Error")
                
                # Check Solicitudes
                conn = get_connection(); reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn); conn.close()
                if not reqs.empty:
                    st.divider()
                    st.warning(f"{len(reqs)} Solicitudes de clave")
                    for _, row in reqs.iterrows():
                        if st.button(f"Reset {row['username']} -> 123456", key=f"r_{row['id']}"):
                            admin_restablecer_password(row['id'], row['username'])
                            st.rerun()

        st.markdown("---")
        # 4. Botón Cerrar Sesión
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
            st.rerun()

    # --- CONTENIDO PRINCIPAL ---
    df = cargar_datos_seguros()
    
    if st.session_state['nav_selection'] == "📅 Calendario Operativo":
        c1, c2 = st.columns([5, 1])
        with c1: st.title("Operaciones Logísticas")
        with c2: 
            if rol != 'analista':
                if st.button("➕ NUEVO", type="primary", use_container_width=True): modal_registro(None)
        
        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                c = "#6c757d"
                if "AliExpress" in r['plataforma_cliente']: c="#f97316"
                elif "Temu" in r['plataforma_cliente']: c="#22c55e"
                elif "Shein" in r['plataforma_cliente']: c="#000000"
                evts.append({"title": f"{r['paquetes']} - {r['proveedor_logistico']}", "start": r['fecha_str'], "backgroundColor": c, "borderColor": c, "extendedProps": r.to_dict()})
        
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif st.session_state['nav_selection'] == "📊 Dashboard Intelligence":
        st.title("Business Intelligence")
        with st.expander("🔎 Filtros Avanzados", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            # Filtros dinámicos
            df_f = df.copy()
            if not df.empty:
                sy = f1.multiselect("Año", sorted(df['Año'].unique()))
                sm = f2.multiselect("Mes", df['Mes'].unique())
                sw = f3.multiselect("Semana", sorted(df['Semana'].unique()))
                sp = f4.multiselect("Proveedor", df['proveedor_logistico'].unique())
                sc = f5.multiselect("Cliente", df['plataforma_cliente'].unique())
                
                if sy: df_f = df_f[df_f['Año'].isin(sy)]
                if sm: df_f = df_f[df_f['Mes'].isin(sm)]
                if sw: df_f = df_f[df_f['Semana'].isin(sw)]
                if sp: df_f = df_f[df_f['proveedor_logistico'].isin(sp)]
                if sc: df_f = df_f[df_f['plataforma_cliente'].isin(sc)]

        if df_f.empty: st.warning("No hay datos.")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='metric-box'><h3>📦 {df_f['paquetes'].sum():,}</h3><p>Paquetes</p></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='metric-box'><h3>🚛 {len(df_f)}</h3><p>Viajes</p></div>", unsafe_allow_html=True)
            try: top = df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top="-"
            k3.markdown(f"<div class='metric-box'><h3>🏆 {top}</h3><p>Cliente Top</p></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='metric-box'><h3>📊 {int(df_f['paquetes'].mean())}</h3><p>Promedio</p></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            t1, t2, t3, t4 = st.tabs(["Evolución", "Distribución", "Heatmap", "Exportar"])
            with t1:
                df_grp = df_f.groupby('fecha').agg({'paquetes':'sum', 'master_lote':'count'}).reset_index()
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_grp['fecha'], y=df_grp['master_lote'], name="Masters", marker_color="#cbd5e1", yaxis="y2"))
                fig.add_trace(go.Scatter(x=df_grp['fecha'], y=df_grp['paquetes'], name="Paquetes", line=dict(color="#3b82f6", width=3)))
                fig.update_layout(yaxis2=dict(overlaying="y", side="right"))
                st.plotly_chart(fig, use_container_width=True)
            with t2:
                c_a, c_b = st.columns(2)
                with c_a: st.plotly_chart(px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico'], values='paquetes'), use_container_width=True)
                with c_b: st.plotly_chart(px.bar(df_f, x='proveedor_logistico', y='paquetes', color='tipo_servicio'), use_container_width=True)
            with t3:
                st.plotly_chart(px.density_heatmap(df_f, x='Semana', y='DiaSemana', z='paquetes', color_continuous_scale="Viridis"), use_container_width=True)
            with t4:
                sel_cols = st.multiselect("Columnas", df_f.columns.tolist(), default=['fecha', 'proveedor_logistico', 'plataforma_cliente', 'paquetes', 'master_lote'])
                if sel_cols:
                    st.download_button("Descargar CSV", df_f[sel_cols].to_csv(index=False).encode('utf-8'), "reporte.csv", "text/csv")
