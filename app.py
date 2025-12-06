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

# --- 2. GESTIÓN DE ESTADO ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'nav_selection' not in st.session_state: st.session_state['nav_selection'] = "📅 Calendario"

# --- 3. ESTILOS CSS CORREGIDOS ---
st.markdown("""
    <style>
    /* 1. OCULTAR ELEMENTOS INNECESARIOS PERO MANTENER EL BOTÓN DE EXPANDIR */
    
    /* Ocultar el menú de hamburguesa y deploy a la derecha */
    [data-testid="stToolbar"] {
        visibility: hidden;
        height: 0px;
    }
    
    /* Ocultar la decoración de colores superior */
    [data-testid="stDecoration"] {
        visibility: hidden;
        display: none;
    }
    
    /* IMPORTANTE: Hacemos el header transparente para que no estorbe, 
       pero NO usamos 'display:none' para que el botón de expandir (>) siga existiendo */
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
        z-index: 1; 
    }
    
    /* Ajuste para que el contenido suba un poco ya que quitamos la barra visualmente */
    .block-container {
        padding-top: 2rem;
    }

    /* 2. ESTILO GENERAL */
    .stApp { background-color: #f4f7f6; font-family: 'Segoe UI', sans-serif; }
    
    /* 3. LOGIN BOX */
    .login-container {
        background: white; padding: 40px; border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center;
        max-width: 420px; margin: 50px auto; border-top: 5px solid #3b82f6;
    }
    
    /* 4. SIDEBAR REDISEÑADA Y LIMPIA */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eaecf0;
    }
    /* Quitar padding extra del sidebar nativo */
    [data-testid="stSidebarUserContent"] {
        padding-top: 2rem;
    }
    
    .sidebar-profile {
        text-align: center; padding: 20px 10px;
        background: #f8fafc; border-radius: 12px; margin-bottom: 20px;
        border: 1px solid #e2e8f0;
    }
    .sidebar-avatar { font-size: 3.5rem; display: block; margin-bottom: 5px; }
    .sidebar-name { font-weight: 700; color: #1e293b; font-size: 1.1rem; }
    .sidebar-role { 
        background-color: #e0f2fe; color: #0284c7; 
        padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;
    }
    
    /* Menú de navegación personalizado */
    .nav-header {
        font-size: 0.8rem; color: #94a3b8; font-weight: 700; 
        margin-top: 10px; margin-bottom: 5px; letter-spacing: 0.05em;
    }
    
    /* 5. TARJETAS MÉTRICAS */
    .metric-box {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03); 
        border-left: 5px solid #3b82f6; transition: transform 0.2s;
    }
    .metric-box:hover { transform: translateY(-3px); }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #1e293b; }
    .metric-label { color: #64748b; font-size: 0.9rem; font-weight: 500; }
    
    /* Botones */
    div.stButton > button { border-radius: 8px; border: none; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- 4. DATOS Y CONEXIÓN ---
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
        st.toast("✨ Registro creado correctamente")
    else:
        sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
        st.toast("✏️ Registro actualizado")
    conn.commit(); conn.close()

# --- 6. MODALES ---
@st.dialog("📝 Gestión Operativa")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled = True if rol == 'analista' else False
    
    # Defaults
    d_fecha, d_prov, d_plat, d_serv = date.today(), PROVEEDORES[0], PLATAFORMAS[0], SERVICIOS[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        # Aseguramos que 'datos' sea un dict limpio
        d_id = datos.get('id')
        f_str = datos.get('fecha_str')
        if f_str: d_fecha = datetime.strptime(f_str, '%Y-%m-%d').date()
        
        # Validar listas
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        if datos.get('servicio') in SERVICIOS: d_serv = datos['servicio']
        
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")

    with st.form("frm_log"):
        st.markdown("#### Detalles del Envío")
        c1, c2 = st.columns(2)
        with c1:
            fecha_in = st.date_input("Fecha de Arribo", d_fecha, disabled=disabled)
            prov_in = st.selectbox("Proveedor Logístico", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            plat_in = st.selectbox("Plataforma Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            serv_in = st.selectbox("Tipo de Servicio", SERVICIOS, index=SERVICIOS.index(d_serv), disabled=disabled)
            mast_in = st.text_input("ID Master / Lote", d_mast, disabled=disabled)
            paq_in = st.number_input("Cantidad Paquetes", min_value=0, value=int(d_paq), disabled=disabled)
        
        com_in = st.text_area("Notas / Observaciones", d_com, disabled=disabled)
        
        if not disabled:
            col_b1, col_b2 = st.columns([1, 1])
            with col_b2:
                if st.form_submit_button("💾 GUARDAR REGISTRO", type="primary", use_container_width=True):
                    guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                    st.rerun()
        else:
            st.warning("🔒 Modo Lectura (Analista)")
            st.form_submit_button("Cerrar")

# ==============================================================================
#  LÓGICA PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    # Ocultar sidebar en login
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    
    col_c = st.columns([1, 1, 1])
    with col_c[1]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="login-container">
            <div style="font-size:3rem;">📦</div>
            <h2 style="color:#1e293b; margin-bottom:5px;">Nexus Logística</h2>
            <p style="color:#64748b; font-size:0.9rem; margin-bottom:25px;">Sistema de Control de Operaciones</p>
        </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["Iniciar Sesión", "Ayuda / Reset"])
        with t1:
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.button("INGRESAR", type="primary", use_container_width=True):
                user = verificar_login(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user
                    st.rerun()
                else: st.error("Acceso incorrecto")
        with t2:
            u_r = st.text_input("Ingresa tu usuario", key="ur")
            if st.button("Solicitar nueva clave"):
                r = solicitar_reset_pass(u_r)
                if r == "ok": st.success("Solicitud enviada al Admin.")
                elif r == "pendiente": st.warning("Ya pendiente.")
                else: st.error("Usuario no existe.")

else:
    # --- APP LOGUEADA ---
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # ---------------- BARRA LATERAL REDISEÑADA ----------------
    with st.sidebar:
        # 1. PERFIL CARD (Diseño Mejorado)
        icon_av = AVATARS.get(u_info.get('avatar', 'avatar_1'), '👨‍💼')
        st.markdown(f"""
        <div class="sidebar-profile">
            <span class="sidebar-avatar">{icon_av}</span>
            <div class="sidebar-name">{u_info['username']}</div>
            <span class="sidebar-role">{rol.upper()}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Expander discreto para edición
        with st.expander("✏️ Editar Avatar"):
            cols = st.columns(5)
            for i, (k, v) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(v, key=f"s_{k}"): actualizar_avatar(u_info['id'], k); st.rerun()
        
        # 2. NAVEGACIÓN LIMPIA
        st.markdown("<div class='nav-header'>MENÚ PRINCIPAL</div>", unsafe_allow_html=True)
        
        opts = ["📅 Calendario", "📊 Dashboards"]
        idx = 0 if st.session_state['nav_selection'] == "📅 Calendario" else 1
        sel = st.radio("Ir a:", opts, index=idx, label_visibility="collapsed")
        st.session_state['nav_selection'] = sel
        
        # 3. ADMIN PANEL (Solo visible si es Admin)
        if rol == 'admin':
            st.divider()
            st.markdown("<div class='nav-header'>ADMINISTRACIÓN</div>", unsafe_allow_html=True)
            
            with st.expander("👥 Usuarios y Claves"):
                with st.form("add_u"):
                    nu = st.text_input("Usuario nuevo")
                    nr = st.selectbox("Rol", ["user", "analista", "admin"])
                    if st.form_submit_button("Crear (Clave: 123456)"):
                        if admin_crear_usuario(nu, nr): st.success("Creado")
                        else: st.error("Error")
                
                # Check resets
                conn = get_connection(); reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn); conn.close()
                if not reqs.empty:
                    st.divider()
                    st.warning(f"{len(reqs)} Solicitudes")
                    for _, r in reqs.iterrows():
                        if st.button(f"Reset {r['username']}", key=f"rr_{r['id']}"):
                            admin_restablecer_password(r['id'], r['username'])
                            st.rerun()
        
        st.markdown("---")
        # 4. BOTÓN CERRAR SESIÓN (Más visible)
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False; st.rerun()

    # ---------------- CONTENIDO ----------------
    df = cargar_datos_seguros()

    if st.session_state['nav_selection'] == "📅 Calendario":
        c_tit, c_btn = st.columns([4, 1])
        with c_tit: st.title("Calendario Operativo")
        with c_btn:
            if rol != 'analista':
                if st.button("➕ NUEVO REGISTRO", type="primary", use_container_width=True): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                # Colores
                color = "#64748b"
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316"
                elif "Temu" in r['plataforma_cliente']: color = "#10b981"
                elif "Shein" in r['plataforma_cliente']: color = "#0f172a"
                
                # Conversión estricta a tipos nativos para evitar MarshallError
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
                
                evts.append({
                    "title": f"{int(r['paquetes'])} - {str(r['proveedor_logistico'])}",
                    "start": r['fecha_str'],
                    "backgroundColor": color,
                    "borderColor": color,
                    "extendedProps": props
                })

        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        
        if cal.get("eventClick"):
            modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif st.session_state['nav_selection'] == "📊 Dashboards":
        st.title("Inteligencia de Negocios")
        
        with st.expander("🔎 Configurar Filtros", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
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
        
        if df_f.empty: st.info("No hay datos para mostrar.")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='metric-box'><div class='metric-value'>{df_f['paquetes'].sum():,}</div><div class='metric-label'>Total Paquetes</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='metric-box'><div class='metric-value'>{len(df_f)}</div><div class='metric-label'>Total Lotes</div></div>", unsafe_allow_html=True)
            try: top = df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top="-"
            k3.markdown(f"<div class='metric-box'><div class='metric-value'>{top}</div><div class='metric-label'>Cliente Principal</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='metric-box'><div class='metric-value'>{int(df_f['paquetes'].mean())}</div><div class='metric-label'>Promedio Lote</div></div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            t1, t2, t3, t4 = st.tabs(["Tendencias", "Distribución", "Mapa Calor", "Exportar"])
            
            with t1:
                g_df = df_f.groupby('fecha').agg({'paquetes':'sum', 'master_lote':'count'}).reset_index()
                fig = go.Figure()
                fig.add_trace(go.Bar(x=g_df['fecha'], y=g_df['master_lote'], name="Lotes", marker_color="#cbd5e1", yaxis="y2"))
                fig.add_trace(go.Scatter(x=g_df['fecha'], y=g_df['paquetes'], name="Paquetes", line=dict(color="#3b82f6", width=3)))
                fig.update_layout(yaxis2=dict(overlaying="y", side="right"), template="plotly_white", title="Evolución Diaria")
                st.plotly_chart(fig, use_container_width=True)
            
            with t2:
                c_a, c_b = st.columns(2)
                with c_a: st.plotly_chart(px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico'], values='paquetes', title="Jerarquía de Volumen"), use_container_width=True)
                with c_b: st.plotly_chart(px.bar(df_f, x='proveedor_logistico', y='paquetes', color='tipo_servicio', title="Operación por Proveedor"), use_container_width=True)
            
            with t3:
                st.plotly_chart(px.density_heatmap(df_f, x='Semana', y='DiaSemana', z='paquetes', color_continuous_scale="Blues", title="Intensidad Semanal"), use_container_width=True)
            
            with t4:
                sel_c = st.multiselect("Columnas", df_f.columns.tolist(), default=['fecha', 'proveedor_logistico', 'plataforma_cliente', 'paquetes'])
                if sel_c:
                    csv = df_f[sel_c].to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Descargar CSV", csv, "reporte.csv", "text/csv")
