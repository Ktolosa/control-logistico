import streamlit as st
from utils import get_connection
from PIL import Image
import io

THEMES = {"light": "Claro", "dark": "Oscuro", "blue": "Azul Corporativo"}

def show(user_info):
    st.title(f"⚙️ Configuración de {user_info['username']}")
    
    # Tabs para organizar
    t1, t2, t3 = st.tabs(["🔒 Seguridad", "👤 Perfil y Tema", "🚪 Sesión"])
    
    # --- T1: PASSWORD ---
    with t1:
        with st.container(border=True):
            st.subheader("Cambiar Contraseña")
            p1 = st.text_input("Nueva Contraseña", type="password")
            p2 = st.text_input("Confirmar Contraseña", type="password")
            
            if st.button("Actualizar Password", type="primary"):
                if p1 and p1 == p2:
                    conn = get_connection()
                    if conn:
                        try:
                            conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s", (p1, user_info['id']))
                            conn.commit(); conn.close()
                            st.success("Contraseña actualizada correctamente.")
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    st.error("Las contraseñas no coinciden o están vacías")

    # --- T2: PERFIL ---
    with t2:
        c_a, c_b = st.columns([1, 2])
        
        with c_a:
            st.write("#### Avatar")
            if user_info.get('avatar'):
                try:
                    image = Image.open(io.BytesIO(user_info['avatar']))
                    st.image(image, width=150)
                except: st.warning("Error carga img")
            else:
                st.info("Sin foto de perfil")

        with c_b:
            st.subheader("Personalización")
            
            # Selector Tema
            curr = user_info.get('tema', 'light')
            idx = list(THEMES.keys()).index(curr) if curr in THEMES else 0
            new_theme = st.selectbox("Tema Visual", list(THEMES.keys()), format_func=lambda x: THEMES[x], index=idx)
            
            # Subir Foto
            up_file = st.file_uploader("Subir foto nueva", type=['jpg','png','jpeg'])
            
            if st.button("💾 Guardar Preferencias"):
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    # Update Tema
                    cur.execute("UPDATE usuarios SET tema=%s WHERE id=%s", (new_theme, user_info['id']))
                    # Update Avatar
                    if up_file:
                        img = Image.open(up_file)
                        img.thumbnail((300, 300))
                        buf = io.BytesIO(); img.save(buf, format="PNG")
                        cur.execute("UPDATE usuarios SET avatar=%s WHERE id=%s", (buf.getvalue(), user_info['id']))
                    
                    conn.commit(); conn.close()
                    
                    # Actualizar Sesión
                    st.session_state['user_theme'] = new_theme
                    st.success("Guardado. Recargando...")
                    st.rerun()

    # --- T3: SALIR ---
    with t3:
        st.warning("¿Deseas cerrar tu sesión?")
        if st.button("Cerrar Sesión", type="primary"):
            st.session_state.clear()
            st.rerun()
