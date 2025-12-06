import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go
import io

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(
    page_title="Nexus Logística", 
    layout="wide", 
    initial_sidebar_state="expanded" 
)

# Inicializar estado
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"

# --- 2. CSS AVANZADO (DISEÑO LIGHT & ULTRA SLIM) ---

# Ancho reducido al 50% funcional (menos de 50px afecta la usabilidad)
SIDEBAR_WIDTH = "55px"

base_css = """
<style>
    /* Limpieza General */
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    footer { display: none !important; }
    
    /* Fondo de la App (Gris muy suave para contraste con barra blanca) */
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 400px; padding-top: 15vh; margin: 0 auto; }
    div[data-testid="stTextInput"] input {
        border: 1px solid #e2e8f0; padding: 12px; border-radius: 10px; background: white; color: #334155;
    }
    div.stButton > button { 
        width: 100%; border-radius: 10px; padding: 12px; font-weight: 600;
        background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; color: white;
    }
</style>
"""

dashboard_css = f"""
<style>
    /* --- 1. BARRA LATERAL BLANCA & SLIM --- */
    
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    section[data-testid="stSidebar"] {{
        display: block !important;
        width: {SIDEBAR_WIDTH} !important;
        min-width: {SIDEBAR_WIDTH} !important;
        max-width: {SIDEBAR_WIDTH} !important;
        transform: none !important; /* Bloqueo de ocultamiento */
        visibility: visible !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        
        /* DISEÑO LIGHT (Blanco con sombra suave) */
        background-color: #ffffff !important;
        border-right: 1px solid #f1f5f9;
        box-shadow: 4px 0 20px rgba(0,0,0,0.03);
        padding-top: 15px;
    }}
    
    section[data-testid="stSidebar"] > div {{
        overflow: hidden !important;
        width: 100% !important;
        display: flex; flex-direction: column; align-items: center;
    }}

    /* --- 2. CONTENIDO PRINCIPAL (Ajuste Perfecto) --- */
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH} !important;
        width: calc(100% - {SIDEBAR_WIDTH}) !important;
        padding: 2rem !important;
        max-width: 100% !important;
    }}

    /* --- 3. BOTONES DE MENÚ (Light Theme) --- */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important; justify-content: center !important; align-items: center !important;
        width: 40px !important; height: 40px !important; /* Más pequeño */
        border-radius: 10px !important; margin-bottom: 20px !important; cursor: pointer;
        
        /* Colores Inactivos (Gris oscuro sobre blanco) */
        background: transparent;
        color: #64748b; 
        font-size: 20px !important;
        border: 1px solid transparent;
        transition: all 0.2s;
    }}
    
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background: #f1f5f9; color: #0f172a;
    }}
    
    /* Activo (Azul corporativo) */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; /* Azul muy claro de fondo */
        color: #2563eb; /* Azul fuerte de icono */
        border: 1px solid #dbeafe;
        box-shadow: 0 2px 5px rgba(37, 99, 235, 0.1);
    }}

    /* Avatar Container */
    .avatar-box {{
        width: 38px; height: 38px; background: #f8fafc;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        margin-bottom: 25px; border: 2px solid #e2e8f0; font-size: 18px;
        color: #334155;
    }}
    
    /* KPI Cards Premium */
    .kpi-card {{
        background: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 2px 10px rgba(0,0,0,0.02);
    }}
    .kpi-lbl {{ color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-val {{ color: #0f172a; font-size: 1.6rem; font-weight: 800; margin-top: 5px; }}
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

# --- Funciones Lógicas ---
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
                st.toast("Guardado Exitosamente")
            else:
                cur.execute("UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s", (fecha, prov, plat, serv, mast, paq, com, id_reg))
                st.toast("Registro Actualizado")
            conn.commit(); conn.close()
        except Exception as e: st.error(str(e))

def admin_crear_usuario(u, r):
    conn = get_connection(); 
    if conn:
        try:
            conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
            conn.commit(); conn.close(); return True
        except: pass; return False

def admin_get_users():
    conn = get_connection(); 
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
            if st.form_submit_button("Guardar Registro", type="primary", use_container_width=True):
                guardar_registro(d_id, fin, pin, clin, sin, min_, pain, com)
                st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    # --- LOGIN ---
    st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #1e293b;'>Nexus Logística</h2>", unsafe_allow_html=True)
    u = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
    st.write("")
    p = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
    st.write("")
    if st.button("ACCEDER"):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Credenciales inválidas")
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Recuperar acceso"):
        ur = st.text_input("Usuario")
        if st.button("Enviar"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Solicitud enviada.")
            elif r=="pendiente": st.info("Ya está pendiente.")
            else: st.warning("Usuario no existe.")

else:
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- BARRA LATERAL LIGHT (55px) ---
    with st.sidebar:
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div style='display:flex; justify-content:center;'><div class='avatar-box' title='{u_info['username']}'>{av}</div></div>", unsafe_allow_html=True)
        
        # MENÚ: 📅 (Cal) | 📈 (Analytics Pro) | 👥 (User) | 🔑 (Key)
        opciones = ["📅", "📈"]
        if rol == 'admin':
            opciones.extend(["👥", "🔑"])
        
        seleccion = st.radio("Menu", opciones, label_visibility="collapsed")
        
        mapa = {"📅": "calendar", "📈": "analytics_pro", "👥": "admin_users", "🔑": "admin_reqs"}
        st.session_state['current_view'] = mapa.get(seleccion, "calendar")

        st.markdown("<div style='flex-grow:1; margin-top:50px;'></div>", unsafe_allow_html=True)
        if st.button("🚪", help="Salir"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CONTENIDO ---
    vista = st.session_state['current_view']
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
                evts.append({"title": f"{int(r['paquetes'])}", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # --- NUEVA HERRAMIENTA: ANALYTICS PRO ---
    elif vista == "analytics_pro":
        st.title("Analytics Pro 360°")
        st.markdown("---")
        
        if df.empty:
            st.warning("No hay datos disponibles para analizar.")
        else:
            # 1. BARRA DE CONTROLES (Filtros Inteligentes)
            with st.expander("🛠️ Panel de Control y Filtros", expanded=True):
                fc1, fc2, fc3, fc4 = st.columns(4)
                
                # Filtro Fechas
                min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
                rango = fc1.date_input("Rango de Fechas", [min_d, max_d])
                
                # Filtros Listas
                provs = fc2.multiselect("Proveedores", df['proveedor_logistico'].unique())
                clis = fc3.multiselect("Clientes", df['plataforma_cliente'].unique())
                servs = fc4.multiselect("Servicios", df['tipo_servicio'].unique())
                
                # Aplicar Filtros
                df_fil = df.copy()
                if len(rango) == 2:
                    df_fil = df_fil[(df_fil['fecha'].dt.date >= rango[0]) & (df_fil['fecha'].dt.date <= rango[1])]
                if provs: df_fil = df_fil[df_fil['proveedor_logistico'].isin(provs)]
                if clis: df_fil = df_fil[df_fil['plataforma_cliente'].isin(clis)]
                if servs: df_fil = df_fil[df_fil['tipo_servicio'].isin(servs)]

            st.divider()

            # 2. KPIs DINÁMICOS
            k1, k2, k3, k4 = st.columns(4)
            total_paq = df_fil['paquetes'].sum()
            total_viajes = len(df_fil)
            # Contar masters únicos (ignorando vacíos)
            masters_unicos = df_fil[df_fil['master_lote'] != '']['master_lote'].nunique()
            promedio = df_fil['paquetes'].mean() if not df_fil.empty else 0

            k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>📦 Total Paquetes</div><div class='kpi-val'>{total_paq:,.0f}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>🚛 Viajes Registrados</div><div class='kpi-val'>{total_viajes}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>🔑 Masters Únicos</div><div class='kpi-val'>{masters_unicos}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>📊 Promedio Carga</div><div class='kpi-val'>{promedio:,.0f}</div></div>", unsafe_allow_html=True)

            st.write("") # Espacio

            # 3. GRÁFICOS AVANZADOS
            t1, t2, t3 = st.tabs(["📈 Evolución Temporal", "🎯 Distribución & Masters", "📥 Datos Detallados"])
            
            with t1:
                col_g1, col_g2 = st.columns([3, 1])
                with col_g1:
                    # Gráfico de Línea con Relleno (Área) por Día
                    g_time = df_fil.groupby('fecha')['paquetes'].sum().reset_index()
                    fig_line = px.area(g_time, x='fecha', y='paquetes', title="Volumen de Paquetes (Timeline)", markers=True, color_discrete_sequence=['#3b82f6'])
                    fig_line.update_layout(xaxis_title="Fecha", yaxis_title="Paquetes", template="plotly_white")
                    st.plotly_chart(fig_line, use_container_width=True)
                
                with col_g2:
                    # Heatmap Semanal
                    st.markdown("**Intensidad por Día de la Semana**")
                    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    g_day = df_fil.groupby('DiaSemana')['paquetes'].mean().reindex(order).reset_index()
                    fig_heat = px.bar(g_day, x='DiaSemana', y='paquetes', color='paquetes', color_continuous_scale="Blues")
                    fig_heat.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, template="plotly_white")
                    st.plotly_chart(fig_heat, use_container_width=True)

            with t2:
                c_pie, c_bar = st.columns(2)
                with c_pie:
                    # Donut Chart Proveedores
                    fig_pie = px.pie(df_fil, names='proveedor_logistico', values='paquetes', title="Share por Proveedor", hole=0.5, color_discrete_sequence=px.colors.qualitative.Prism)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with c_bar:
                    # Barras Apiladas Clientes vs Servicio
                    fig_bar = px.bar(df_fil, x='plataforma_cliente', y='paquetes', color='tipo_servicio', title="Cliente vs Tipo Servicio", barmode='group')
                    st.plotly_chart(fig_bar, use_container_width=True)

            with t3:
                # 4. TABLA Y EXPORTACIÓN
                st.subheader("Matriz de Datos")
                
                # Selector de columnas para reporte
                all_cols = df_fil.columns.tolist()
                sel_cols = st.multiselect("Seleccionar Columnas para Reporte", all_cols, default=['fecha', 'proveedor_logistico', 'plataforma_cliente', 'master_lote', 'paquetes', 'comentarios'])
                
                df_export = df_fil[sel_cols]
                st.dataframe(df_export, use_container_width=True)
                
                # Generar CSV en memoria
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte (CSV)",
                    data=csv,
                    file_name=f"Reporte_Nexus_{date.today()}.csv",
                    mime="text/csv",
                    type="primary"
                )

    elif vista == "admin_users":
        st.title("Usuarios")
        t1, t2 = st.tabs(["Crear", "Lista"])
        with t1:
            with st.form("new_u"):
                nu = st.text_input("User"); nr = st.selectbox("Rol", ["user", "analista", "admin"])
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
