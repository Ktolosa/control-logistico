import streamlit as st
import utils
# IMPORTAR TUS MÓDULOS
from modules import calendario, analytics, gestor_temu, pod_digital, admin

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="expanded")

# 2. CARGAR CSS (Desde utils)
utils.load_css()

# 3. INTERCEPTOR QR (Si existe lógica global)
# ... (Tu código de descarga por QR va aquí) ...

# 4. LOGIN
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    # ... (Tu lógica de Login, usando utils.verificar_login) ...
    st.stop() # Detiene la app si no está logueado

# 5. SISTEMA DE NAVEGACIÓN
u_info = st.session_state['user_info']
rol = u_info['rol']

# --- CONFIGURACIÓN DEL MENÚ (AQUÍ AGREGAS NUEVAS HERRAMIENTAS) ---
# Estructura: "Clave": {Titulo, Icono, Modulo, Roles_Permitidos}
MENU = {
    "calendar": {"title": "Calendario", "icon": "📅", "module": calendario, "roles": ["all"]},
    "analytics": {"title": "Analytics", "icon": "📈", "module": analytics, "roles": ["all"]},
    "temu":      {"title": "Gestor TEMU", "icon": "📑", "module": gestor_temu, "roles": ["all"]},
    "pod":       {"title": "POD Digital", "icon": "📝", "module": pod_digital, "roles": ["all"]},
    "admin":     {"title": "Admin", "icon": "👥", "module": admin, "roles": ["admin"]},
}

# --- BARRA LATERAL (Renderizado Dinámico) ---
with st.sidebar:
    st.markdown(f"<div class='avatar-float'>{utils.AVATARS.get(u_info.get('avatar'), '👤')}</div>", unsafe_allow_html=True)
    
    # Generar opciones según rol
    opciones_validas = [k for k, v in MENU.items() if "all" in v["roles"] or rol in v["roles"]]
    
    # Usamos iconos para el radio button
    iconos = [MENU[k]["icon"] for k in opciones_validas]
    seleccion_icono = st.radio("Menú", iconos, label_visibility="collapsed")
    
    # Traducir Icono -> Clave
    clave_seleccionada = next(k for k in opciones_validas if MENU[k]["icon"] == seleccion_icono)
    
    if st.button("🚪 Salir"): 
        st.session_state['logged_in'] = False
        st.rerun()

# --- RENDERIZADO DEL MÓDULO ---
# Aquí ocurre la magia. No hay if/elif gigantes.
modulo_actual = MENU[clave_seleccionada]["module"]

# Si estamos en móvil y queremos botón volver (opcional, si el módulo lo requiere)
if st.session_state.get('is_mobile', False): # Podrías detectar móvil con JS o CSS hacks, o simplemente ponerlo siempre
    pass 

# EJECUTAR LA VISTA DEL MÓDULO
modulo_actual.show(u_info)
