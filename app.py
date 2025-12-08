import streamlit as st
import utils
# Importamos el nuevo módulo tracking_pro junto a los demás
from modules import calendario, analytics, gestor_temu, pod_digital, admin, configuracion, tracking_pro
import pandas as pd
import io
from PIL import Image

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# 2. CARGAR TEMA VISUAL
if 'user_theme' not in st.session_state:
    st.session_state['user_theme'] = 'light'

utils.load_css(st.session_state['user_theme'])

# 3. INTERCEPTOR QR (PARA DESCARGA PÚBLICA DE PODS)
qp = st.query_params
if "pod_uuid" in qp:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    uuid_target = qp["pod_uuid"]
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga POD</h2>", unsafe_allow_html=True)
    try:
        conn = utils.get_connection()
        q = "SELECT tracking FROM pod_items WHERE pod_uuid = %s"
        df_items = pd.read_sql(q, conn, params=(uuid_target,))
        q_info = "SELECT cliente, fecha, pod_code FROM pods WHERE uuid = %s"
        df_info = pd.read_sql(q_info, conn, params=(uuid_target,))
        conn.close()
        
        if not df_items.empty:
            p_code = df_info.iloc[0]['pod_code']
            st.success(f"✅ POD {p_code} Encontrado ({len(df_items)} paquetes).")
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_items.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), f"POD_{p_code}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
        else: 
            st.error("Documento no encontrado.")
    except Exception as e: 
        st.error(f"Error: {e}")
    
    if st.button("Ir al Inicio"): 
        st.query_params.clear()
        st.rerun()
    st.stop()

# 4. SISTEMA DE LOGIN
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.markdown("<div style='height: 50px'></div><h2 style='text-align:center;'>Nexus Logística</h2>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True, type="primary"):
            usr = utils.verificar_login(u, p)
            if usr: 
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = usr
                st.session_state['user_theme'] = usr.get('tema', 'light')
                st.rerun()
            else: 
                st.error("Credenciales inválidas")
        
        with st.expander("¿Olvidaste tu contraseña?"):
            ur = st.text_input("Usuario a recuperar")
            if st.button("Solicitar Restablecimiento"):
                conn = utils.get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM usuarios WHERE username=%s", (ur,))
                    if cur.fetchone():
                        try:
                            cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (ur,))
                            conn.commit()
                            st.success("Solicitud enviada.")
                        except: 
                            st.warning("Solicitud ya existente.")
                    else: 
                        st.warning("Usuario no existe.")
                    conn.close()
    st.stop()

# 5. MENÚ PRINCIPAL
u_info = st.session_state['user_info']
rol = u_info['rol']

# Definición del Menú (Incluye Tracking Pro)
MENU = {
    "calendar": {"title": "Calendario", "icon": "📅", "mod": calendario, "roles": ["all"]},
    "analytics": {"title": "Analytics", "icon": "📈", "mod": analytics, "roles": ["all"]},
    "tracking_pro": {"title": "Tracking Pro", "icon": "🔍", "mod": tracking_pro, "roles": ["all"]}, # <-- NUEVO
    "temu": {"title": "Gestor TEMU", "icon": "📑", "mod": gestor_temu, "roles": ["all"]},
    "pod": {"title": "POD Digital", "icon": "📝", "mod": pod_digital, "roles": ["all"]},
    "admin": {"title": "Admin", "icon": "👥", "mod": admin, "roles": ["admin"]},
    "config": {"title": "Configuración", "icon": "⚙️", "mod": configuracion, "roles": ["all"]},
}

def count_pending():
    conn = utils.get_connection()
    if conn:
        try: 
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM password_requests WHERE status='pendiente'")
            c = cur.fetchone()[0]
            conn.close()
            return c
        except: return 0
    return 0

# GESTOR DE VISTAS
if 'current_view' not in st.session_state: 
    st.session_state['current_view'] = "menu"

if st.session_state['current_view'] == "menu":
    
    # --- ENCABEZADO PERFIL INICIO (RESTAURADO) ---
    with st.container():
        c_perfil, c_info, c_logout = st.columns([1, 4, 1])
        
        # Columna Foto
        with c_perfil:
            if u_info.get('avatar') and isinstance(u_info['avatar'], bytes):
                try:
                    image = Image.open(io.BytesIO(u_info['avatar']))
                    st.image(image, width=90) 
                except: st.header("👤")
            else:
                st.header("👤")
        
        # Columna Saludo
        with c_info:
            st.subheader(f"Hola, {u_info['username']}")
            # Convertimos el código del tema a nombre bonito para mostrarlo
            tema_actual = st.session_state.get('user_theme','light')
            nombre_tema = utils.THEMES.get(tema_actual, {}).get('name', 'Claro')
            st.caption(f"Rol: {rol.capitalize()} | Tema: {nombre_tema}")
            
        # Columna Salir
        with c_logout:
            st.write("") # Espacio vertical
            if st.button("🚪 Salir", key="top_logout"):
                st.session_state.clear()
                st.rerun()
    
    st.divider()
    # --- FIN ENCABEZADO ---
    
    # Notificaciones Admin
    pending = 0
    if rol == 'admin': pending = count_pending()
    
    # Grid de Botones
    cols = st.columns(2)
    valid_keys = [k for k,v in MENU.items() if "all" in v['roles'] or rol in v['roles']]
    
    for i, k in enumerate(valid_keys):
        with cols[i % 2]:
            label = f"{MENU[k]['icon']}\n{MENU[k]['title']}"
            if k == "admin" and pending > 0:
                label = f"🔴 {pending} Pendientes\n{MENU[k]['title']}"
            
            if st.button(label, key=f"btn_{k}", use_container_width=True):
                st.session_state['current_view'] = k
                st.rerun()

else:
    # VISTA DE MÓDULO INTERNO
    c_back, c_title = st.columns([1, 5])
    if c_back.button("⬅️ MENÚ"): 
        st.session_state['current_view'] = "menu"
        st.rerun()
    
    # Cargar módulo
    k = st.session_state['current_view']
    if k in MENU:
        try:
            MENU[k]['mod'].show(u_info)
        except Exception as e:
            st.error(f"Error cargando módulo: {e}")
    else:
        st.error("Módulo no encontrado")
