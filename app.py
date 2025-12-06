import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import re # Para procesar texto de masters

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

# --- 2. CSS AVANZADO (BARRA CENTRADA Y DISEÑO LIMPIO) ---
SIDEBAR_WIDTH = "60px" # Un poco más ancho para que se vea bien centrado

base_css = """
<style>
    /* Limpieza General */
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    footer { display: none !important; }
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 400px; padding-top: 15vh; margin: 0 auto; }
    div[data-testid="stTextInput"] input { border: 1px solid #e2e8f0; padding: 12px; border-radius: 10px; }
    div.stButton > button { width: 100%; border-radius: 10px; padding: 12px; font-weight: 600; background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; color: white; }
</style>
"""

dashboard_css = f"""
<style>
    /* --- 1. BARRA LATERAL (Centrada Vertical y Horizontalmente) --- */
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    section[data-testid="stSidebar"] {{
        display: block !important;
        width: {SIDEBAR_WIDTH} !important;
        min-width: {SIDEBAR_WIDTH} !important;
        max-width: {SIDEBAR_WIDTH} !important;
        transform: none !important;
        visibility: visible !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important; bottom: 0 !important;
        z-index: 99999;
        background-color: #ffffff !important;
        border-right: 1px solid #f1f5f9;
        box-shadow: 4px 0 20px rgba(0,0,0,0.03);
    }}
    
    /* CENTRADO VERTICAL DEL CONTENIDO DE LA BARRA */
    section[data-testid="stSidebar"] > div {{
        height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center; /* Centrar verticalmente */
        align-items: center;     /* Centrar horizontalmente */
        padding-top: 0px !important; 
    }}

    /* --- 2. CONTENIDO PRINCIPAL --- */
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH} !important;
        width: calc(100% - {SIDEBAR_WIDTH}) !important;
        padding: 2rem !important;
        max-width: 100% !important;
    }}

    /* --- 3. ICONOS DEL MENÚ --- */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    
    /* Contenedor del grupo de radio buttons */
    [data-testid="stSidebar"] div[role="radiogroup"] {{
        display: flex; flex-direction: column; align-items: center; gap: 15px;
    }}

    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important; justify-content: center !important; align-items: center !important;
        width: 42px !important; height: 42px !important;
        border-radius: 12px !important; cursor: pointer;
        background: transparent; color: #64748b; font-size: 22px !important;
        border: 1px solid transparent; transition: all 0.2s; margin: 0 !important;
    }}
    
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background: #f1f5f9; color: #0f172a; transform: scale(1.1);
    }}
    
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; color: #2563eb; border: 1px solid #dbeafe;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.15);
    }}

    /* Avatar flotante arriba (Absolute) */
    .avatar-float {{
        position: absolute; top: 20px; left: 0; right: 0; margin: auto;
        width: 35px; height: 35px; background: #f8fafc; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        border: 2px solid #e2e8f0; font-size: 18px; color: #334155;
    }}
    
    /* Botón Salir flotante abajo (Absolute) */
    .logout-float {{
        position: absolute; bottom: 20px; left: 0; right: 0; margin: auto; text-align: center;
    }}

    /* Estilos KPI y Tablas */
    .kpi-card {{
        background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0;
    }}
    .kpi-lbl {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 700; }}
    .kpi-val {{ font-size: 1.5rem; color: #0f172a; font-weight: 800; }}
    
    /* Validación de conteo (Verde/Rojo) */
    .count-ok {{ color: #16a34a; font-weight: bold; font-size: 0.9rem; }}
    .count-err {{ color: #dc2626; font-weight: bold; font-size: 0.9rem; }}
</style>
"""

st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)

# --- 3. CONEXIÓN Y UTILIDADES ---
AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
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

def cambiar_password(user_id, nueva_pass):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET password=%s WHERE id=%s", (nueva_pass, user_id))
            conn.commit(); conn.close(); return True
        except: pass
    return False

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
            # Lógica de Fechas
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            # ISO Week corrección
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
            
            # --- NUEVO: Conteo real de masters en la cadena ---
            # Asumimos que master_lote guarda strings. Contamos palabras.
            def contar_masters(texto):
                if not texto: return 0
                # Reemplazar saltos de línea y comas por espacios, luego contar
                clean = re.sub(r'[\n,]', ' ', str(texto))
                parts = [p for p in clean.split(' ') if p.strip()]
                return len(parts)
            
            df['conteo_masters_real'] = df['master_lote'].apply(contar_masters)

        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast_str, paq, com):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            user = st.session_state['user_info']['username']
            # Limpieza del string de masters para guardar formato standard (espaciado)
            clean_masters = " ".join([m.strip() for m in re.split(r'[\n, ]+', mast_str) if m.strip()])
            
            if id_reg is None:
                cur.execute("INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (fecha, prov, plat, serv, clean_masters, paq, com, user))
                st.toast("✅ Guardado Exitosamente")
            else:
                cur.execute("UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s", (fecha, prov, plat, serv, clean_masters, paq, com, id_reg))
                st.toast("✅ Registro Actualizado")
            conn.commit(); conn.close()
        except Exception as e: st.error(str(e))

# Funciones Admin (Usuarios/Claves) - Se mantienen igual
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
    conn = get_connection(); conn.cursor().execute("UPDATE usuarios SET activo=%s WHERE id=%s", (0 if curr==1 else 1, uid)); conn.commit(); conn.close()
def admin_restablecer_password(rid, uname):
    conn = get_connection(); 
    if conn:
        cur=conn.cursor(); cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,)); cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,)); conn.commit(); conn.close()

# --- 4. MODAL DE REGISTRO (CON LÓGICA DE CONTEO) ---
@st.dialog("Gestión de Carga")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled = (rol == 'analista')
    
    # Valores por defecto
    d_fecha, d_prov, d_plat = date.today(), PROVEEDORES[0], PLATAFORMAS[0]
    d_serv, d_mast, d_paq, d_com, d_id = SERVICIOS[0], "", 0, "", None
    d_esp = 1 # Esperados por defecto

    if datos:
        d_id = datos.get('id')
        if datos.get('fecha_str'): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        d_serv = datos.get('servicio', SERVICIOS[0])
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")
        # Intentar adivinar cuantos esperaban basándonos en lo que hay
        d_esp = len([x for x in re.split(r'[\n, ]+', d_mast) if x.strip()]) 
        if d_esp == 0: d_esp = 1

    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha Llegada", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            pain = st.number_input("Total Paquetes", 0, value=int(d_paq), disabled=disabled)
            esperados = st.number_input("Masters Esperadas (Validación)", min_value=1, value=d_esp, disabled=disabled)

        st.markdown("---")
        st.write("📋 **Pegar Masters (Bloque de texto)**")
        # AREA DE TEXTO PARA PEGAR MULTIPLES
        min_ = st.text_area("Masters (Separadas por espacio, coma o enter)", d_mast, height=100, disabled=disabled, placeholder="Pegue aquí sus códigos...")
        
        # --- LÓGICA DE VALIDACIÓN DE CONTEO EN TIEMPO REAL (AL RENDERIZAR) ---
        lista_masters = [m for m in re.split(r'[\n, ]+', min_) if m.strip()]
        conteo_actual = len(lista_masters)
        
        col_val1, col_val2 = st.columns(2)
        col_val1.caption(f"Leídas: {conteo_actual}")
        
        if conteo_actual == esperados:
            col_val2.markdown(f"<span class='count-ok'>✅ Correcto ({conteo_actual}/{esperados})</span>", unsafe_allow_html=True)
        else:
            col_val2.markdown(f"<span class='count-err'>⚠️ Diferencia: {conteo_actual - esperados}</span>", unsafe_allow_html=True)

        com = st.text_area("Comentarios / Notas", d_com, disabled=disabled)
        
        if not disabled:
            if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
                guardar_registro(d_id, fin, pin, clin, sin, min_, pain, com)
                st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
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
    with st.expander("Recuperar contraseña"):
        ur = st.text_input("Usuario")
        if st.button("Solicitar Reset"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Solicitud enviada.")
            elif r=="pendiente": st.info("Pendiente.")
            else: st.warning("No existe.")

else:
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    # --- BARRA LATERAL (CENTRADA) ---
    with st.sidebar:
        # Avatar (Position Absolute CSS lo pone arriba)
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div class='avatar-float' title='{u_info['username']}'>{av}</div>", unsafe_allow_html=True)
        
        # MENÚ ICONOS (CENTRADO POR FLEXBOX EN CSS)
        # 📅 Cal | 📈 Analytics | ⚙️ Config | 👥 Admin | 🔑 Keys
        opciones = ["📅", "📈", "⚙️"]
        if rol == 'admin':
            opciones.extend(["👥", "🔑"])
        
        seleccion = st.radio("Menu", opciones, label_visibility="collapsed")
        
        mapa = {
            "📅": "calendar", 
            "📈": "analytics_pro", 
            "⚙️": "user_settings",
            "👥": "admin_users", 
            "🔑": "admin_reqs"
        }
        st.session_state['current_view'] = mapa.get(seleccion, "calendar")

        # Botón Salir (Position Absolute CSS lo pone abajo)
        st.markdown("<div class='logout-float'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🚪", help="Salir"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CONTENIDO ---
    vista = st.session_state['current_view']
    df = cargar_datos()

    # 1. CALENDARIO
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
                # En el título mostramos Paquetes y conteo de Masters
                conteo = r['conteo_masters_real']
                evts.append({"title": f"📦{int(r['paquetes'])} | 🔑{conteo}", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # 2. ANALYTICS PRO (ACTUALIZADO CON TUS REQUISITOS)
    elif vista == "analytics_pro":
        st.title("Analytics & Reportes")
        
        if df.empty:
            st.warning("Sin datos.")
        else:
            # --- SECCION SUPERIOR: FILTROS Y BÚSQUEDA MASTER ---
            with st.container(border=True):
                c_search, c_date = st.columns([1, 2])
                # Buscador de Master Específica
                search_master = c_search.text_input("🔍 Buscar Master Lote", placeholder="Escribe el código...")
                
                # Filtro Fechas
                min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
                rango = c_date.date_input("Rango de Análisis", [min_d, max_d])

            # Aplicar Filtros
            df_fil = df.copy()
            if search_master:
                # Filtrar donde el string master_lote contenga el texto (case insensitive)
                df_fil = df_fil[df_fil['master_lote'].str.contains(search_master, case=False, na=False)]
                if not df_fil.empty:
                    st.success(f"Se encontraron {len(df_fil)} viajes con la master '{search_master}'")
                else:
                    st.error(f"No se encontró la master '{search_master}'")
            
            if len(rango) == 2:
                df_fil = df_fil[(df_fil['fecha'].dt.date >= rango[0]) & (df_fil['fecha'].dt.date <= rango[1])]

            st.divider()

            # --- SECCION KPI ---
            k1, k2, k3, k4 = st.columns(4)
            # Suma de paquetes
            t_paq = df_fil['paquetes'].sum()
            # Suma de masters reales (calculado en cargar_datos)
            t_mast = df_fil['conteo_masters_real'].sum()
            
            k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Paquetes Total</div><div class='kpi-val'>{t_paq:,.0f}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Masters (Real)</div><div class='kpi-val'>{t_mast:,.0f}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Viajes</div><div class='kpi-val'>{len(df_fil)}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio Paq/Viaje</div><div class='kpi-val'>{df_fil['paquetes'].mean():,.0f}</div></div>", unsafe_allow_html=True)

            st.write("")

            # --- TABS DE ANALISIS ---
            tab1, tab2, tab3 = st.tabs(["📅 Resumen Semanal", "📊 Gráficos", "📥 Matriz de Datos"])
            
            with tab1:
                st.subheader("Resumen Semanal de Operaciones")
                # Agrupación por Año y Semana
                if not df_fil.empty:
                    # Crear tabla resumen
                    # Agrupar
                    resumen = df_fil.groupby(['Año', 'Semana', 'Mes']).agg(
                        Paquetes=('paquetes', 'sum'),
                        Masters=('conteo_masters_real', 'sum'),
                        Viajes=('id', 'count')
                    ).reset_index()
                    
                    # Calcular Fechas Inicio/Fin de la semana para mostrar
                    def get_week_dates(year, week):
                        d = date.fromisocalendar(year, week, 1)
                        d2 = d + timedelta(days=6)
                        return f"{d.strftime('%d-%b')} al {d2.strftime('%d-%b')}"

                    resumen['Rango Fechas'] = resumen.apply(lambda x: get_week_dates(x['Año'], x['Semana']), axis=1)
                    
                    # Reordenar columnas
                    resumen = resumen[['Año', 'Semana', 'Mes', 'Rango Fechas', 'Viajes', 'Masters', 'Paquetes']]
                    st.dataframe(resumen, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay datos para el resumen.")

            with tab2:
                g1, g2 = st.columns(2)
                with g1:
                    st.caption("Volumen por Día")
                    g_time = df_fil.groupby('fecha')['paquetes'].sum().reset_index()
                    fig = px.bar(g_time, x='fecha', y='paquetes', color_discrete_sequence=['#3b82f6'])
                    st.plotly_chart(fig, use_container_width=True)
                with g2:
                    st.caption("Distribución por Proveedor")
                    fig2 = px.pie(df_fil, names='proveedor_logistico', values='paquetes', hole=0.5)
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Desglose por cliente
                st.caption("Paquetes por Cliente y Plataforma")
                fig3 = px.bar(df_fil, x='plataforma_cliente', y='paquetes', color='tipo_servicio', barmode='group')
                st.plotly_chart(fig3, use_container_width=True)

            with tab3:
                st.dataframe(df_fil, use_container_width=True)
                # Exportar
                csv = df_fil.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar CSV", csv, "reporte.csv", "text/csv")

    # 3. CONFIGURACIÓN DE USUARIO (NUEVA HERRAMIENTA)
    elif vista == "user_settings":
        st.title("Configuración de Cuenta")
        
        with st.container(border=True):
            st.subheader("Cambiar Contraseña")
            p1 = st.text_input("Nueva Contraseña", type="password")
            p2 = st.text_input("Confirmar Contraseña", type="password")
            
            if st.button("Actualizar Contraseña", type="primary"):
                if p1 and p2 and p1 == p2:
                    if cambiar_password(u_info['id'], p1):
                        st.success("Contraseña actualizada correctamente.")
                    else:
                        st.error("Error al actualizar.")
                else:
                    st.warning("Las contraseñas no coinciden o están vacías.")

    # 4. ADMIN
    elif vista == "admin_users":
        st.title("Usuarios")
        t1, t2 = st.tabs(["Crear", "Lista"])
        with t1:
            with st.form("new_u"):
                nu = st.text_input("User"); nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"):
                    if admin_crear_usuario(nu, nr): st.success("Creado")
        with t2:
            df_u = admin_get_users(); st.dataframe(df_u, use_container_width=True)
            c1, c2 = st.columns(2)
            uid = c1.selectbox("ID", df_u['id'].tolist() if not df_u.empty else [])
            if uid and c2.button("Toggle"):
                curr = df_u[df_u['id']==uid]['activo'].values[0]
                admin_toggle(uid, curr); st.rerun()

    elif vista == "admin_reqs":
        st.title("Claves")
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
        if reqs.empty: st.success("Limpio.")
        else:
            for _, r in reqs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"User: {r['username']}")
                if c2.button("Reset", key=r['id']):
                    admin_restablecer_password(r['id'], r['username']); st.rerun()
