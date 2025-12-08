import streamlit as st
import utils
from modules import calendario, analytics, gestor_temu, pod_digital, admin, configuracion
import pandas as pd
import mysql.connector
import io

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

# 2. CARGAR CSS
utils.load_css()

# 3. INTERCEPTOR QR (POD)
qp = st.query_params
if "pod_uuid" in qp:
    # Lógica mínima para descarga sin login
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga POD</h2>", unsafe_allow_html=True)
    try:
        conn = utils.get_connection()
        uid = qp["pod_uuid"]
        items = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        info = pd.read_sql("SELECT pod_code, cliente FROM pods WHERE uuid=%s", conn, params=(uid,))
        conn.close()
        
        if not items.empty:
            code = info.iloc[0]['pod_code']
            st.success(f"POD {code} encontrada ({len(items)} paq).")
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: items.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), f"POD_{code}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else: st.error("No encontrada")
    except Exception as e: st.error(f"Error: {e}")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# 4. LOGIN
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    st.markdown("<div style='height: 50px'></div><h2 style='text-align:center;'>Nexus Logística</h2>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True, type="primary"):
            usr = utils.verificar_login(u, p)
            if usr: st.session_state['logged_in']=True; st.session_state['user_info']=usr; st.rerun()
            else: st.error("Credenciales inválidas")
        
        # Recuperar Password
        with st.expander("¿Olvidaste tu contraseña?"):
            ur = st.text_input("Usuario a recuperar")
            if st.button("Solicitar Reset"):
                conn = utils.get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM usuarios WHERE username=%s", (ur,))
                    if cur.fetchone():
                        try:
                            cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (ur,))
                            conn.commit(); st.success("Solicitud enviada")
                        except: st.warning("Ya existe una solicitud pendiente")
                    else: st.warning("Usuario no existe")
                    conn.close()
    st.stop()

# 5. MENÚ Y NAVEGACIÓN
u_info = st.session_state['user_info']
rol = u_info['rol']

# Sidebar simple
with st.sidebar:
    st.markdown(f"<h1 style='text-align:center'>👤</h1>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center'>{u_info['username']}</div><hr>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['logged_in'] = False; st.rerun()

# Definir Menú
MENU = {
    "calendar": {"title": "Calendario", "icon": "📅", "mod": calendario, "roles": ["all"]},
    "analytics": {"title": "Analytics", "icon": "📈", "mod": analytics, "roles": ["all"]},
    "temu": {"title": "Gestor TEMU", "icon": "📑", "mod": gestor_temu, "roles": ["all"]},
    "pod": {"title": "POD Digital", "icon": "📝", "mod": pod_digital, "roles": ["all"]},
    "admin": {"title": "Admin", "icon": "👥", "mod": admin, "roles": ["admin"]},
    "config": {"title": "Configuración", "icon": "⚙️", "mod": configuracion, "roles": ["all"]},
}

if 'current_view' not in st.session_state: st.session_state['current_view'] = "menu"

if st.session_state['current_view'] == "menu":
    st.title("Panel Principal")
    cols = st.columns(2)
    valid_keys = [k for k,v in MENU.items() if "all" in v['roles'] or rol in v['roles']]
    
    for i, k in enumerate(valid_keys):
        with cols[i % 2]:
            if st.button(f"{MENU[k]['icon']}\n{MENU[k]['title']}", key=k, use_container_width=True):
                st.session_state['current_view'] = k
                st.rerun()

else:
    # Botón Volver
    if st.button("⬅️ VOLVER AL MENÚ"): 
        st.session_state['current_view'] = "menu"
        st.rerun()
    
    # Cargar Módulo
    k = st.session_state['current_view']
    MENU[k]['mod'].show(u_info)
