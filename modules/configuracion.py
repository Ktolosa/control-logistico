import streamlit as st
from utils import get_connection, THEMES, THEME_NAMES
from PIL import Image
import io

def show(user_info):
    st.title(f"⚙️ Preferencias")
    
    t1, t2, t3 = st.tabs(["🎨 Apariencia", "🔒 Seguridad", "🚪 Sesión"])
    
    with t1:
        c_a, c_b = st.columns([1, 2])
        
        with c_a:
            st.write("#### Avatar")
            if user_info.get('avatar') and isinstance(user_info['avatar'], bytes):
                try: st.image(Image.open(io.BytesIO(user_info['avatar'])), width=150)
                except: st.warning("Error carga img")
            else: st.info("Sin foto")

        with c_b:
            st.subheader("Personalización")
            
            curr = user_info.get('tema', 'light')
            try: idx = THEME_NAMES.index(curr)
            except: idx = 0

            new_theme = st.selectbox("Tema Visual", THEME_NAMES, format_func=lambda x: THEMES[x]['name'], index=idx)
            up_file = st.file_uploader("Subir foto nueva", type=['jpg','png','jpeg'])
            
            if st.button("💾 Guardar Preferencias", type="primary"):
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    updates = []
                    params = []
                    
                    if new_theme != curr:
                        updates.append("tema=%s"); params.append(new_theme)
                    
                    if up_file:
                        img = Image.open(up_file)
                        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                        img.thumbnail((300, 300))
                        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=90)
                        updates.append("avatar=%s"); params.append(buf.getvalue())

                    if updates:
                        params.append(user_info['id'])
                        sql = f"UPDATE usuarios SET {', '.join(updates)} WHERE id=%s"
                        cur.execute(sql, tuple(params)); conn.commit(); conn.close()
                        
                        st.session_state['user_theme'] = new_theme
                        if new_theme != curr: st.session_state['user_info']['tema'] = new_theme
                        if up_file: st.session_state['user_info']['avatar'] = params[-2]
                        st.toast("✅ Guardado"); st.rerun()
                    else: st.info("Sin cambios")

    with t2:
        st.subheader("Cambiar Contraseña")
        p1 = st.text_input("Nueva Contraseña", type="password")
        p2 = st.text_input("Confirmar Contraseña", type="password")
        
        if st.button("Actualizar Password"):
            if p1 and p1 == p2:
                conn = get_connection()
                if conn:
                    conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s", (p1, user_info['id'])); conn.commit(); conn.close()
                    st.success("Contraseña actualizada.")
            else: st.error("No coinciden")

    with t3:
        st.warning("Zona de peligro")
        if st.button("Cerrar Sesión"):
            st.session_state.clear(); st.rerun()
