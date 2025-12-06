import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import plotly.graph_objects as go
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Nexus Logística Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Estilos Generales */
    .stApp { background-color: #f0f2f6; font-family: 'Segoe UI', sans-serif; }
    
    /* Sidebar Personalizado */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    /* Tarjetas de Métricas */
    .metric-container {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #3b82f6;
    }
    
    /* Botones */
    div.stButton > button {
        border-radius: 6px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURACIÓN DE AVATARES ---
AVATARS = {
    "avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👷‍♀️",
    "avatar_5": "🤵", "avatar_6": "🕵️‍♀️", "avatar_7": "🦸‍♂️", "avatar_8": "👩‍💻",
    "avatar_9": "🤖", "avatar_10": "🦁"
}

# --- 3. CONEXIÓN DB ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- 4. FUNCIONES DE USUARIO Y AUTH ---
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
    """Crea una solicitud para que el admin restablezca la contraseña"""
    conn = get_connection()
    cursor = conn.cursor()
    # Verificar si usuario existe
    cursor.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
    if cursor.fetchone():
        # Verificar si ya hay solicitud pendiente
        cursor.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
            conn.commit()
            conn.close()
            return "ok"
        else:
            conn.close()
            return "pendiente"
    conn.close()
    return "no_user"

def actualizar_avatar(user_id, nuevo_avatar):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (nuevo_avatar, user_id))
    conn.commit()
    conn.close()
    st.session_state['user_info']['avatar'] = nuevo_avatar

# --- 5. FUNCIONES ADMIN ---
def admin_crear_usuario(user, role):
    """Crea usuario con contraseña por defecto 123456"""
    conn = get_connection()
    cursor = conn.cursor()
    default_pass = "123456"
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, %s, %s, 'avatar_1')", (user, default_pass, role))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def admin_restablecer_password(request_id, username):
    """Restablece la contraseña a 123456 y cierra la solicitud"""
    conn = get_connection()
    cursor = conn.cursor()
    default_pass = "123456"
    
    # 1. Resetear password
    cursor.execute("UPDATE usuarios SET password=%s WHERE username=%s", (default_pass, username))
    # 2. Marcar solicitud como resuelta
    cursor.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (request_id,))
    
    conn.commit()
    conn.close()

# --- 6. GESTIÓN DE DATOS LOGÍSTICOS ---
def cargar_datos_seguros():
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            df = df.dropna(subset=['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            
            # Columnas derivadas para filtros avanzados
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast, paq, com):
    conn = get_connection()
    cursor = conn.cursor()
    user = st.session_state['user_info']['username']
    
    if id_reg is None:
        sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, user))
        st.toast("✨ Registro Guardado")
    else:
        sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
        cursor.execute(sql, (fecha, prov, plat, serv, mast, paq, com, id_reg))
        st.toast("✏️ Registro Actualizado")
    conn.commit()
    conn.close()

# --- CONSTANTES ---
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# ==============================================================================
#  VENTANA EMERGENTE (MODAL DE REGISTRO)
# ==============================================================================
@st.dialog("📝 Gestión de Operaciones")
def modal_registro(datos=None):
    # BLOQUEO DE SEGURIDAD PARA ANALISTAS
    rol = st.session_state['user_info']['rol']
    
    st.markdown("### Detalles del Envío")
    
    # Valores por defecto
    d_fecha, d_prov, d_plat, d_serv = date.today(), PROVEEDORES[0], PLATAFORMAS[0], SERVICIOS[0]
    d_mast, d_paq, d_com, d_id = "", 0, "", None

    if datos:
        d_id = datos['id']
        if isinstance(datos['fecha_str'], str): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos['proveedor_logistico'] in PROVEEDORES: d_prov = datos['proveedor_logistico']
        if datos['plataforma_cliente'] in PLATAFORMAS: d_plat = datos['plataforma_cliente']
        if datos['tipo_servicio'] in SERVICIOS: d_serv = datos['tipo_servicio']
        d_mast, d_paq, d_com = datos['master_lote'], datos['paquetes'], datos['comentarios']

    # Si es analista, mostramos solo lectura
    disabled_mode = True if rol == 'analista' else False

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
            if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
                guardar_registro(d_id, fecha_in, prov_in, plat_in, serv_in, mast_in, paq_in, com_in)
                st.rerun()
        else:
            st.warning("🔒 Modo Lectura: Tu rol de Analista no permite editar.")
            if st.form_submit_button("Cerrar"):
                st.rerun()

# ==============================================================================
#  LÓGICA PRINCIPAL DE LA APP
# ==============================================================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- PANTALLA DE INICIO (LOGIN / RECUPERAR) ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>🔐 Nexus Logística</h1>", unsafe_allow_html=True)
        
        tab_log, tab_rec = st.tabs(["Ingresar", "Olvidé Contraseña"])
        
        with tab_log:
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.button("INICIAR SESIÓN", type="primary", use_container_width=True):
                user = verificar_login(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user
                    st.rerun()
                else:
                    st.error("Credenciales inválidas o usuario inactivo.")
        
        with tab_rec:
            st.markdown("Solicita al Administrador el restablecimiento de tu contraseña.")
            u_rec = st.text_input("Ingresa tu Usuario")
            if st.button("Enviar Solicitud de Ayuda"):
                res = solicitar_reset_pass(u_rec)
                if res == "ok": st.success("✅ Solicitud enviada. El Admin restablecerá tu clave.")
                elif res == "pendiente": st.info("⏳ Ya tienes una solicitud pendiente.")
                else: st.error("❌ Usuario no encontrado.")

else:
    # --- APLICACIÓN INTERNA ---
    user_info = st.session_state['user_info']
    rol = user_info['rol']
    
    # ------------------------------------------------------------------
    #  BARRA LATERAL (SIDEBAR) PROFESIONAL
    # ------------------------------------------------------------------
    with st.sidebar:
        # 1. PERFIL DE USUARIO
        st.markdown(f"<div style='text-align:center; font-size: 4rem; margin-bottom:10px;'>{AVATARS.get(user_info.get('avatar', 'avatar_1'), '👨‍💼')}</div>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align:center; margin:0;'>{user_info['username']}</h3>", unsafe_allow_html=True)
        
        # Etiqueta de Rol con color
        color_rol = "#2ecc71" if rol == "admin" else "#3498db" if rol == "user" else "#9b59b6"
        st.markdown(f"<div style='text-align:center;'><span style='background-color:{color_rol}; color:white; padding:2px 8px; border-radius:10px; font-size:0.8rem;'>{rol.upper()}</span></div>", unsafe_allow_html=True)
        
        # Selector de Avatar (Expander)
        with st.expander("📷 Cambiar mi Avatar"):
            cols = st.columns(5)
            for i, (key, icon) in enumerate(AVATARS.items()):
                with cols[i%5]:
                    if st.button(icon, key=f"av_{key}"):
                        actualizar_avatar(user_info['id'], key)
                        st.rerun()
        
        st.markdown("---")
        
        # 2. MENÚ DE NAVEGACIÓN
        st.markdown("##### 🧭 Navegación")
        menu = st.radio("Ir a:", ["📅 Calendario Operativo", "📊 Dashboard Intelligence"], label_visibility="collapsed")
        
        # 3. PANEL DE ADMINISTRADOR (SOLO ADMIN)
        if rol == 'admin':
            st.markdown("---")
            st.markdown("##### 🛡️ Panel Admin")
            
            # A. Gestión de Usuarios
            with st.expander("➕ Crear Usuario"):
                with st.form("new_u"):
                    nu = st.text_input("Usuario")
                    nr = st.selectbox("Rol", ["user", "analista", "admin"])
                    st.caption("Contraseña por defecto: 123456")
                    if st.form_submit_button("Crear"):
                        if admin_crear_usuario(nu, nr): st.success("Creado")
                        else: st.error("Error")
            
            # B. Solicitudes de Contraseña
            conn = get_connection()
            reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn)
            conn.close()
            
            if not reqs.empty:
                st.error(f"🔔 {len(reqs)} Solicitud(es) de clave")
                with st.expander("Ver Solicitudes", expanded=True):
                    for _, row in reqs.iterrows():
                        st.write(f"🔐 **{row['username']}** olvidó su clave.")
                        if st.button("Restablecer a '123456'", key=f"rst_{row['id']}"):
                            admin_restablecer_password(row['id'], row['username'])
                            st.success(f"Clave de {row['username']} reseteada.")
                            st.rerun()
            else:
                st.caption("✅ Sin solicitudes de contraseña.")

        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # ------------------------------------------------------------------
    #  ÁREA PRINCIPAL DE CONTENIDO
    # ------------------------------------------------------------------
    
    df = cargar_datos_seguros()
    
    # --- VISTA 1: CALENDARIO ---
    if menu == "📅 Calendario Operativo":
        col_title, col_add = st.columns([5, 1])
        with col_title: st.title("Operaciones Logísticas")
        with col_add:
            # Solo Admin y User pueden ver el botón de agregar
            if rol != 'analista':
                if st.button("➕ REGISTRAR", type="primary", use_container_width=True):
                    modal_registro(None)
        
        # Lógica del Calendario
        events = []
        if not df.empty:
            for _, row in df.iterrows():
                # Colores por Cliente
                c = "#6c757d"
                if "AliExpress" in row['plataforma_cliente']: c = "#f97316" # Naranja
                elif "Temu" in row['plataforma_cliente']: c = "#22c55e" # Verde
                elif "Shein" in row['plataforma_cliente']: c = "#000000" # Negro
                
                events.append({
                    "title": f"{row['paquetes']} - {row['proveedor_logistico']}",
                    "start": row['fecha_str'],
                    "backgroundColor": c,
                    "borderColor": c,
                    "extendedProps": row.to_dict()
                })
        
        cal = calendar(events=events, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        
        if cal.get("eventClick"):
            modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # --- VISTA 2: DASHBOARD INTELLIGENCE ---
    elif menu == "📊 Dashboard Intelligence":
        st.title("Centro de Análisis Avanzado")
        
        # 1. FILTROS AVANZADOS (EXPANDER)
        with st.expander("🔎 FILTROS PROFUNDOS", expanded=True):
            f1, f2, f3, f4, f5, f6 = st.columns(6)
            
            # Listas para filtros
            years = sorted(df['Año'].unique().tolist()) if not df.empty else []
            months = df['Mes'].unique().tolist() if not df.empty else []
            weeks = sorted(df['Semana'].unique().tolist()) if not df.empty else []
            provs = df['proveedor_logistico'].unique().tolist() if not df.empty else []
            plats = df['plataforma_cliente'].unique().tolist() if not df.empty else []
            
            with f1: sel_year = st.multiselect("Año", years)
            with f2: sel_month = st.multiselect("Mes", months)
            with f3: sel_week = st.multiselect("Semana", weeks)
            with f4: sel_prov = st.multiselect("Proveedor", provs)
            with f5: sel_plat = st.multiselect("Cliente", plats)
            with f6: sel_serv = st.multiselect("Servicio", SERVICIOS)
        
        # Aplicar Filtros
        df_f = df.copy()
        if sel_year: df_f = df_f[df_f['Año'].isin(sel_year)]
        if sel_month: df_f = df_f[df_f['Mes'].isin(sel_month)]
        if sel_week: df_f = df_f[df_f['Semana'].isin(sel_week)]
        if sel_prov: df_f = df_f[df_f['proveedor_logistico'].isin(sel_prov)]
        if sel_plat: df_f = df_f[df_f['plataforma_cliente'].isin(sel_plat)]
        if sel_serv: df_f = df_f[df_f['tipo_servicio'].isin(sel_serv)]
        
        if df_f.empty:
            st.warning("⚠️ No hay datos que coincidan con los filtros.")
        else:
            # 2. TARJETAS KPI
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='metric-container'><h3>📦 {df_f['paquetes'].sum():,}</h3><p>Total Paquetes</p></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='metric-container'><h3>🚛 {len(df_f)}</h3><p>Total Viajes/Masters</p></div>", unsafe_allow_html=True)
            try: top_c = df_f.groupby('plataforma_cliente')['paquetes'].sum().idxmax()
            except: top_c = "-"
            k3.markdown(f"<div class='metric-container'><h3>🏆 {top_c}</h3><p>Cliente Top</p></div>", unsafe_allow_html=True)
            avg = int(df_f['paquetes'].mean())
            k4.markdown(f"<div class='metric-container'><h3>📊 {avg}</h3><p>Promedio x Lote</p></div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)

            # 3. PESTAÑAS DE ANÁLISIS
            t1, t2, t3, t4 = st.tabs(["📈 Tendencias", "🍰 Distribución", "🔥 Mapa de Calor", "📥 Exportar Datos"])
            
            with t1:
                # Gráfico combinado Línea (Paquetes) y Barras (Masters)
                df_time = df_f.groupby('fecha').agg({'paquetes':'sum', 'master_lote':'count'}).reset_index()
                fig_combo = go.Figure()
                fig_combo.add_trace(go.Bar(x=df_time['fecha'], y=df_time['master_lote'], name='Cant. Masters', marker_color='#cbd5e1', yaxis='y2'))
                fig_combo.add_trace(go.Scatter(x=df_time['fecha'], y=df_time['paquetes'], name='Paquetes', line=dict(color='#2563eb', width=3)))
                
                fig_combo.update_layout(title="Volumen Diario (Paquetes vs Masters)", yaxis=dict(title="Paquetes"), yaxis2=dict(title="Masters", overlaying='y', side='right'))
                st.plotly_chart(fig_combo, use_container_width=True)
                
            with t2:
                cg1, cg2 = st.columns(2)
                with cg1:
                    # Sunburst: Cliente -> Proveedor -> Servicio
                    fig_sun = px.sunburst(df_f, path=['plataforma_cliente', 'proveedor_logistico', 'tipo_servicio'], values='paquetes', title="Distribución Jerárquica")
                    st.plotly_chart(fig_sun, use_container_width=True)
                with cg2:
                    # Comparativa Barras
                    fig_bar = px.bar(df_f, x='proveedor_logistico', y='paquetes', color='plataforma_cliente', title="Paquetes por Proveedor y Cliente")
                    st.plotly_chart(fig_bar, use_container_width=True)

            with t3:
                # Mapa de Calor: Día de semana vs Hora (o Semana)
                df_heat = df_f.groupby(['DiaSemana', 'Semana'])['paquetes'].sum().reset_index()
                # Ordenar días
                dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                fig_heat = px.density_heatmap(df_heat, x='Semana', y='DiaSemana', z='paquetes', 
                                              category_orders={'DiaSemana': dias_orden},
                                              title="Mapa de Intensidad (Semana vs Día)", color_continuous_scale="Viridis")
                st.plotly_chart(fig_heat, use_container_width=True)

            with t4:
                st.subheader("Generador de Reportes")
                st.info("Selecciona las columnas que deseas descargar en tu reporte.")
                
                all_cols = ['fecha', 'proveedor_logistico', 'plataforma_cliente', 'tipo_servicio', 'master_lote', 'paquetes', 'comentarios', 'Año', 'Mes', 'Semana']
                cols_sel = st.multiselect("Columnas a exportar", all_cols, default=all_cols)
                
                if cols_sel:
                    df_export = df_f[cols_sel]
                    csv = df_export.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 DESCARGAR REPORTE (CSV)",
                        data=csv,
                        file_name=f"reporte_logistica_{date.today()}.csv",
                        mime="text/csv",
                        type="primary"
                    )
