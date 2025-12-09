import streamlit as st
import utils
import time
from modules import calendario, analytics, gestor_temu, pod_digital, admin, configuracion, tracking_pro
import pandas as pd
import io
from PIL import Image

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# 2. ESTADO
if 'user_theme' not in st.session_state: st.session_state['user_theme'] = 'light'
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# Cargar CSS
utils.load_css(st.session_state['user_theme'])

# 3. INTERCEPTOR QR
qp = st.query_params
if "pod_uuid" in qp:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga Segura</h2>", unsafe_allow_html=True)
    with st.spinner("Buscando documento..."):
        time.sleep(0.5)
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
            else: st.error("Enlace expirado.")
        except: st.error("Error de conexión.")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# 4. LOGIN (DISEÑO MEJORADO & TRANSICIÓN FULL SCREEN)
if not st.session_state['logged_in']:
    # Placeholder que contiene TODO el login para poder borrarlo después
    login_holder = st.empty()
    
    with login_holder.container():
        st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
        # Diseño clásico [1, 2, 1] que te gustaba, más ancho
        c1, c2, c3 = st.columns([1, 2, 1])
        
        with c2:
            # Contenedor "Glass" para el formulario
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center; margin-bottom: 20px;'>Nexus Logística</h2>", unsafe_allow_html=True)
                
                u = st.text_input("Usuario", placeholder="Escribe tu usuario")
                p = st.text_input("Contraseña", type="password", placeholder="••••••••")
                
                st.write("") # Espacio
                
                if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                    usr = utils.verificar_login(u, p)
                    if usr:
                        # --- TRANSICIÓN A PANTALLA COMPLETA ---
                        # 1. Borramos el formulario de login inmediatamente
                        login_holder.empty()
                        
                        # 2. Mostramos la animación en la pantalla limpia
                        with st.container():
                            st.markdown("<br><br><br><br>", unsafe_allow_html=True)
                            # Mensaje grande centrado
                            st.markdown(f"""
                            <div style='text-align:center; animation: fadeInUp 0.8s;'>
                                <h1>🚀 Bienvenido, {usr['username']}</h1>
                                <p style='color:grey;'>Iniciando módulos de logística...</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Barra de progreso centrada (usando columnas para que no sea tan ancha)
                            cb1, cb2, cb3 = st.columns([1, 2, 1])
                            with cb2:
                                my_bar = st.progress(0)
                                for percent in range(100):
                                    time.sleep(0.01) # Velocidad de carga
                                    my_bar.progress(percent + 1)
                            
                            time.sleep(0.3) # Pequeña pausa al final
                            
                            # 3. Guardamos sesión y recargamos
                            st.session_state['logged_in'] = True
                            st.session_state['user_info'] = usr
                            st.session_state['user_theme'] = usr.get('tema', 'light')
                            st.rerun()
                    else:
                        st.error("Credenciales incorrectas")

            # Link de recuperación fuera de la tarjeta principal
            with st.expander("¿Olvidaste tu contraseña?", expanded=False):
                ur = st.text_input("Usuario a recuperar")
                if st.button("Solicitar Reset"):
                    conn = utils.get_connection()
                    if conn:
                        try:
                            conn.cursor().execute("INSERT INTO password_requests (username) VALUES (%s)", (ur,)); conn.commit()
                            st.success("Solicitud enviada.")
                        except: st.warning("Ya pendiente.")
                        conn.close()
    st.stop()

# 5. DASHBOARD PRINCIPAL
u_info = st.session_state['user_info']
rol = u_info['rol']

# Sidebar solo para cerrar sesión (Minimalista)
with st.sidebar:
    st.write("")
    if st.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Definición Menú
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
        try: cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM password_requests WHERE status='pendiente'"); c = cur.fetchone()[0]; conn.close(); return c
        except: return 0
    return 0

# GESTIÓN DE VISTAS
if 'current_view' not in st.session_state: st.session_state['current_view'] = "menu"

if st.session_state['current_view'] == "menu":
    
    # --- ENCABEZADO RESTAURADO (PERFIL EN PAGINA DE INICIO) ---
    with st.container():
        # Columnas: Foto | Info | Espacio
        c_pic, c_txt, c_ext = st.columns([0.8, 4, 1])
        
        with c_pic:
            if u_info.get('avatar') and isinstance(u_info['avatar'], bytes):
                try: 
                    # Mostramos la imagen redonda
                    st.image(Image.open(io.BytesIO(u_info['avatar'])), width=85)
                except: st.header("👤")
            else:
                st.header("👤")
        
        with c_txt:
            # Texto alineado verticalmente
            st.markdown(f"""
            <div style='padding-top: 10px;'>
                <h2 style='margin:0; padding:0;'>Hola, {u_info['username']}</h2>
                <p style='margin:0; padding:0; opacity: 0.7;'>Rol: {rol.capitalize()} | Panel de Control</p>
            </div>
            """, unsafe_allow_html=True)
            
    st.divider()
    # -----------------------------------------------------------

    # Grid de Herramientas
    pending = count_pending() if rol == 'admin' else 0
    valid_keys = [k for k,v in MENU.items() if "all" in v['roles'] or rol in v['roles']]
    
    cols = st.columns(2) # 2 Columnas como te gustaba antes
    for i, k in enumerate(valid_keys):
        with cols[i % 2]:
            label = f"{MENU[k]['icon']}\n{MENU[k]['title']}"
            if k == "admin" and pending > 0: label = f"🔴 {pending} Pendientes\n{MENU[k]['title']}"
            
            if st.button(label, key=f"dash_{k}", use_container_width=True):
                st.session_state['current_view'] = k
                st.rerun()

else:
    # VISTA HERRAMIENTA
    c_back, c_tit = st.columns([1, 6])
    if c_back.button("⬅️ Volver", use_container_width=True):
        st.session_state['current_view'] = "menu"
        st.rerun()
    
    k = st.session_state['current_view']
    if k in MENU:
        with st.container():
            # Pequeña animación de entrada para el módulo
            st.markdown("<div style='animation: fadeInUp 0.4s ease-out;'>", unsafe_allow_html=True)
            try: MENU[k]['mod'].show(u_info)
            except Exception as e: st.error(f"Error módulo: {e}")
            st.markdown("</div>", unsafe_allow_html=True)
