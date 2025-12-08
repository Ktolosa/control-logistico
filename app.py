import streamlit as st
import utils
import time # Necesario para las transiciones
from modules import calendario, analytics, gestor_temu, pod_digital, admin, configuracion, tracking_pro
import pandas as pd
import io
from PIL import Image

# 1. CONFIGURACIÓN (Debe ser lo primero)
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# 2. GESTIÓN DE ESTADO Y TEMA
if 'user_theme' not in st.session_state: st.session_state['user_theme'] = 'light'
if 'login_transition' not in st.session_state: st.session_state['login_transition'] = False

# Cargamos el CSS "Super Estético"
utils.load_css(st.session_state['user_theme'])

# 3. INTERCEPTOR QR (Descargas públicas)
qp = st.query_params
if "pod_uuid" in qp:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga Segura</h2>", unsafe_allow_html=True)
    with st.spinner("Buscando documento..."):
        time.sleep(0.5) # Pequeña pausa para efecto visual
        try:
            conn = utils.get_connection()
            uuid_target = qp["pod_uuid"]
            df_items = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid = %s", conn, params=(uuid_target,))
            df_info = pd.read_sql("SELECT cliente, fecha, pod_code FROM pods WHERE uuid = %s", conn, params=(uuid_target,))
            conn.close()
            
            if not df_items.empty:
                p_code = df_info.iloc[0]['pod_code']
                st.success(f"✅ Documento {p_code} Localizado.")
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_items.to_excel(w, index=False)
                st.download_button("📥 Descargar Manifiesto (Excel)", out.getvalue(), f"POD_{p_code}.xlsx", "primary", use_container_width=True)
            else: 
                st.error("El enlace ha expirado o no existe.")
        except: st.error("Error de conexión.")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# 4. LOGIN CON TRANSICIÓN ANIMADA
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.markdown("<div style='height: 8vh'></div>", unsafe_allow_html=True)
    c_spacer, c_login, c_spacer2 = st.columns([1, 1.2, 1]) # Centrado más preciso
    
    with c_login:
        # Tarjeta de Login flotante
        with st.container(border=True):
            st.markdown("<h1 style='text-align:center; font-size: 2.5rem;'>Nexus</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:grey; margin-top:-15px;'>Logística Inteligente</p>", unsafe_allow_html=True)
            
            u = st.text_input("Usuario", placeholder="Ingresa tu ID")
            p = st.text_input("Contraseña", type="password", placeholder="••••••••")
            
            if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
                usr = utils.verificar_login(u, p)
                if usr:
                    # --- SECUENCIA DE TRANSICIÓN PREMIUM ---
                    placeholder = st.empty()
                    with placeholder.container():
                        st.success(f"¡Bienvenido de nuevo, {usr['username']}!")
                        progress_text = "Cargando módulos..."
                        my_bar = st.progress(0, text=progress_text)
                        
                        for percent_complete in range(100):
                            time.sleep(0.005) # Velocidad de la barra
                            my_bar.progress(percent_complete + 1, text=progress_text)
                        time.sleep(0.2) # Pausa final al 100%
                    
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = usr
                    st.session_state['user_theme'] = usr.get('tema', 'light')
                    st.rerun() # Recarga con la nueva UI
                else:
                    st.error("Credenciales incorrectas")
                    st.toast("⚠️ Verifica tu usuario o contraseña") # Feedback tipo notificación

            # Recuperar contraseña (Minimalista)
            with st.expander("¿Problemas para entrar?"):
                ur = st.text_input("Tu Usuario")
                if st.button("Solicitar Ayuda"):
                    conn = utils.get_connection()
                    if conn:
                        try:
                            conn.cursor().execute("INSERT INTO password_requests (username) VALUES (%s)", (ur,)); conn.commit()
                            st.info("Solicitud enviada a soporte.")
                        except: st.warning("Ya existe una solicitud pendiente.")
                        conn.close()
    st.stop()

# 5. UI PRINCIPAL (DASHBOARD)
u_info = st.session_state['user_info']
rol = u_info['rol']

# Sidebar minimalista con Avatar
with st.sidebar:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    col_av, col_det = st.columns([1, 2])
    with col_av:
        if u_info.get('avatar') and isinstance(u_info['avatar'], bytes):
            try: st.image(Image.open(io.BytesIO(u_info['avatar'])), width=70)
            except: st.header("👤")
        else: st.header("👤")
    with col_det:
        st.write(f"**{u_info['username']}**")
        st.caption(f"{rol.upper()}")
    
    st.divider()
    if st.button("Cerrar Sesión", use_container_width=True):
        with st.spinner("Cerrando sesión..."):
            time.sleep(0.5)
            st.session_state.clear()
            st.rerun()

# Definición del Menú
MENU = {
    "calendar": {"title": "Calendario", "icon": "📅", "mod": calendario, "roles": ["all"]},
    "analytics": {"title": "Analytics", "icon": "📈", "mod": analytics, "roles": ["all"]},
    "tracking_pro": {"title": "Tracking Pro", "icon": "🔍", "mod": tracking_pro, "roles": ["all"]},
    "temu": {"title": "Gestor TEMU", "icon": "📑", "mod": gestor_temu, "roles": ["all"]},
    "pod": {"title": "POD Digital", "icon": "📝", "mod": pod_digital, "roles": ["all"]},
    "admin": {"title": "Admin", "icon": "👥", "mod": admin, "roles": ["admin"]},
    "config": {"title": "Ajustes", "icon": "⚙️", "mod": configuracion, "roles": ["all"]},
}

def count_pending():
    conn = utils.get_connection()
    if conn:
        try: 
            cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM password_requests WHERE status='pendiente'"); c = cur.fetchone()[0]; conn.close(); return c
        except: return 0
    return 0

# CONTROL DE NAVEGACIÓN
if 'current_view' not in st.session_state: st.session_state['current_view'] = "menu"

if st.session_state['current_view'] == "menu":
    # --- HEADER DASHBOARD ---
    c_h1, c_h2 = st.columns([4, 1])
    with c_h1:
        st.title(f"Hola, {u_info['username']} 👋")
        st.caption("Selecciona una herramienta para comenzar.")
    with c_h2:
        # Mini widget de fecha o estado
        st.markdown(f"<div style='text-align:right; padding-top:10px; opacity:0.6'>{pd.Timestamp.now().strftime('%d %b')}</div>", unsafe_allow_html=True)

    # --- GRID DE BOTONES ---
    pending = count_pending() if rol == 'admin' else 0
    
    valid_keys = [k for k,v in MENU.items() if "all" in v['roles'] or rol in v['roles']]
    
    # Creamos filas de 2 o 3 columnas dinámicamente
    cols = st.columns(3) # Diseño más amplio
    for i, k in enumerate(valid_keys):
        with cols[i % 3]: # Distribuir en 3 columnas
            label = f"{MENU[k]['icon']}\n{MENU[k]['title']}"
            if k == "admin" and pending > 0: label = f"🔴 {pending}\n{MENU[k]['title']}"
            
            # Botón con key única
            if st.button(label, key=f"dash_{k}", use_container_width=True):
                st.session_state['current_view'] = k
                st.rerun()

else:
    # --- VISTA INTERNA (CON ANIMACIÓN DE RETORNO) ---
    c_nav, c_tit = st.columns([1, 6])
    with c_nav:
        if st.button("⬅️ Inicio", use_container_width=True):
            st.session_state['current_view'] = "menu"
            st.rerun()
    
    k = st.session_state['current_view']
    if k in MENU:
        # Contenedor para la herramienta con margen
        with st.container():
            try: MENU[k]['mod'].show(u_info)
            except Exception as e: st.error(f"Error módulo: {e}")
