import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
from streamlit_calendar import calendar
import plotly.express as px

# --- 1. CONFIGURACIÓN INICIAL ---
# Importante: initial_sidebar_state="expanded" para asegurar que cargue abierta antes de bloquearla con CSS
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# Inicializar estado
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None

# --- 2. GESTIÓN DE CSS (DISEÑO AJUSTADO Y CORREGIDO) ---

base_css = """
<style>
    /* Limpieza general de elementos de Streamlit */
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
</style>
"""

# CSS Login (Sin barra lateral, contenido centrado)
login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container {
        max-width: 800px;
        padding-top: 5rem;
        margin: 0 auto; /* Centrado automático */
    }
    div[data-testid="stTextInput"] input {
        border: 1px solid #ddd; padding: 10px; border-radius: 5px;
    }
    div.stButton > button { width: 100%; border-radius: 5px; font-weight: 600; }
</style>
"""

# CSS Dashboard (Barra Fija, Estrecha y Contenido Ajustado)
dashboard_css = """
<style>
    /* --- 1. BARRA LATERAL (SIDEBAR) --- */
    
    /* Eliminar la flecha y el botón de colapsar (keyboard_double_arrow_left) */
    [data-testid="collapsedControl"] { 
        display: none !important; 
    }
    
    /* Configuración de la barra fija */
    [data-testid="stSidebar"] {
        display: block !important;
        width: 220px !important;       /* ANCHO REDUCIDO */
        min-width: 220px !important;
        max-width: 220px !important;
        transform: translateX(0) !important; /* Bloquear posición */
        visibility: visible !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
        padding-top: 1rem; /* Espacio arriba */
    }

    /* --- 2. CONTENIDO PRINCIPAL (ELIMINAR SUPERPOSICIÓN) --- */
    
    /* Empujar el contenido a la derecha para respetar el ancho de la barra */
    .main .block-container {
        margin-left: 220px !important;  /* IDÉNTICO AL ANCHO DE LA BARRA */
        width: calc(100% - 220px) !important; /* El ancho restante */
        padding-top: 2rem !important;
        padding-left: 2rem !important;  /* Aire entre la barra y el contenido */
        padding-right: 2rem !important;
        max-width: 100% !important;
    }

    /* --- 3. ESTILOS DEL MENÚ Y PERFIL (MEJOR DISTRIBUCIÓN) --- */
    
    /* Ocultar círculos de los radio buttons */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    
    /* Botones del menú más grandes y espaciados */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        padding: 12px 20px !important; /* Más relleno interno */
        margin-bottom: 8px !important; /* Separación entre botones */
        border-radius: 6px !important;
        border: 1px solid transparent;
        transition: all 0.2s ease;
        cursor: pointer;
        color: #64748b;
        font-size: 15px !important;
    }
    
    /* Hover */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: #f8fafc;
        color: #1e293b;
    }
    
    /* Botón Activo */
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {
        background-color: #eff6ff;
        color: #2563eb;
        font-weight: 600;
        border-left: 4px solid #2563eb;
    }

    /* Tarjeta de Perfil Compacta */
    .profile-card {
        background-color: #f1f5f9; 
        padding: 15px; 
        border-radius: 8px;
        text-align: center; 
        margin-bottom: 30px; /* Separación con el menú */
    }
    .profile-avatar { font-size: 2.2rem; margin-bottom: 5px; }
    .profile-name { font-weight: 700; color: #334155; font-size: 0.9rem; }
    .profile-role { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; }

    /* Tarjetas KPI */
    .kpi-card {
        background: white; padding: 15px; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-left: 4px solid #3b82f6;
    }
    .kpi-val { font-size: 1.5rem; font-weight: bold; color: #0f172a; }
    .kpi-lbl { color: #64748b; font-size: 0.85rem; }
</style>
"""

# Aplicar CSS según estado
st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)


# --- 3. CONEXIÓN Y DATOS ---
# (Mismos datos de ejemplo para que funcione standalone)
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

# --- 4. FUNCIONES LÓGICAS ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

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
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    # --- LOGIN ---
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align:center; color:#333; margin-bottom: 20px;'>Nexus Logística</h2>", unsafe_allow_html=True)
        u = st.text_input("Usuario", placeholder="Usuario")
        p = st.text_input("Contraseña", type="password", placeholder="Contraseña")
        st.write("")
        if st.button("INICIAR SESIÓN", type="primary"):
            user = verificar_login(u, p)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user
                st.rerun()
            else: st.error("Acceso denegado")

else:
    # --- DASHBOARD ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # 1. BARRA LATERAL (FIXED & ESTRECHA)
    with st.sidebar:
        # Perfil Visualmente Atractivo
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"""
            <div class='profile-card'>
                <div class='profile-avatar'>{av}</div>
                <div class='profile-name'>{u_info['username']}</div>
                <div class='profile-role'>{rol}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # MENÚ UNIFICADO
        opciones_menu = ["📅 Calendario", "📊 Reportes"]
        if rol == 'admin':
            opciones_menu.extend(["👥 Admin Usuarios", "🔑 Admin Claves"])
        
        # Radio buttons estilizados como botones
        seleccion = st.radio("Menú", opciones_menu, label_visibility="collapsed")
        
        # Espacio flexible y botón de salir
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # 2. CONTENIDO PRINCIPAL (LADO DERECHO)
    df = cargar_datos()
    
    if seleccion == "📅 Calendario":
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
                    "title": f"{int(r['paquetes'])} - {r['proveedor_logistico']}", 
                    "start": r['fecha_str'], 
                    "backgroundColor": color, 
                    "borderColor": color, 
                    "extendedProps": props
                })
        
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "700px"}, key="calendar_view")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif seleccion == "📊 Reportes":
        st.title("Reportes y Estadísticas")
        if df.empty: st.info("No hay datos.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df['paquetes'].sum():,}</div><div class='kpi-lbl'>Paquetes Totales</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{len(df)}</div><div class='kpi-lbl'>Entradas Registradas</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{df['paquetes'].mean():.0f}</div><div class='kpi-lbl'>Promedio por Carga</div></div>", unsafe_allow_html=True)
            
            st.divider()
            t1, t2 = st.tabs(["Gráficos", "Tabla de Datos"])
            with t1:
                g = df.groupby('fecha')['paquetes'].sum().reset_index()
                st.plotly_chart(px.line(g, x='fecha', y='paquetes', title="Tendencia de Volumen"), use_container_width=True)
            with t2:
                st.dataframe(df, use_container_width=True)

    elif seleccion == "👥 Admin Usuarios":
        st.title("Gestión de Usuarios")
        t_new, t_list = st.tabs(["Crear Usuario", "Lista Existente"])
        with t_new:
            with st.form("f_new_u"):
                nu = st.text_input("Usuario")
                nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"):
                    if admin_crear_usuario(nu, nr): st.success("Creado correctamente")
                    else: st.error("Error al crear")
        with t_list:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            c1, c2 = st.columns(2)
            uid = c1.selectbox("ID Usuario", df_u['id'].tolist() if not df_u.empty else [])
            if uid:
                curr = df_u[df_u['id']==uid]['activo'].values[0]
                btn_txt = "Desactivar" if curr == 1 else "Activar"
                if c2.button(btn_txt): admin_toggle(uid, curr); st.rerun()

    elif seleccion == "🔑 Admin Claves":
        st.title("Solicitudes de Contraseña")
        st.info("Módulo de claves activo.")
