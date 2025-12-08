import streamlit as st
from utils import get_connection, THEMES, THEME_NAMES # Importamos las nuevas constantes de temas
from PIL import Image
import io

def show(user_info):
    st.title(f"⚙️ Preferencias de {user_info['username']}")
    
    t1, t2, t3 = st.tabs(["🎨 Apariencia y Avatar", "🔒 Seguridad", "🚪 Sesión"])
    
    # --- T1: APARIENCIA ---
    with t1:
        c_a, c_b = st.columns([1, 2])
        
        with c_a:
            st.write("#### Avatar Actual")
            if user_info.get('avatar') and isinstance(user_info['avatar'], bytes):
                try:
                    image = Image.open(io.BytesIO(user_info['avatar']))
                    st.image(image, width=150)
                except: st.warning("Error al cargar imagen")
            else:
                st.info("Sin foto de perfil personalizada")

        with c_b:
            st.subheader("Personalización Visual")
            
            # Selector de Tema (Usa los 10 temas nuevos)
            curr_theme_code = user_info.get('tema', 'light')
            
            # Buscar el índice actual en la lista de nombres clave
            try:
                idx = THEME_NAMES.index(curr_theme_code)
            except ValueError:
                idx = 0 # Default a light si no encuentra el tema

            new_theme_code = st.selectbox(
                "Selecciona un Tema", 
                THEME_NAMES, 
                format_func=lambda x: THEMES[x]['name'], # Muestra el nombre bonito
                index=idx
            )
            
            st.divider()
            st.write("#### Actualizar Foto")
            up_file = st.file_uploader("Subir nueva imagen (JPG/PNG)", type=['jpg','png','jpeg'])
            
            if st.button("💾 Guardar Apariencia", type="primary"):
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    updates = []
                    params = []
                    
                    # Si cambió el tema
                    if new_theme_code != curr_theme_code:
                        updates.append("tema=%s")
                        params.append(new_theme_code)
                    
                    # Si subió foto
                    if up_file:
                        try:
                            img = Image.open(up_file)
                            # Convertir a RGB si es necesario antes de guardar como JPEG/PNG
                            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                            img.thumbnail((300, 300)) # Redimensionar
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=90) # Guardar comprimido
                            updates.append("avatar=%s")
                            params.append(buf.getvalue())
                        except Exception as e:
                            st.error(f"Error procesando imagen: {e}")

                    if updates:
                        params.append(user_info['id'])
                        sql = f"UPDATE usuarios SET {', '.join(updates)} WHERE id=%s"
                        cur.execute(sql, tuple(params))
                        conn.commit(); conn.close()
                        
                        # Actualizar sesión
                        st.session_state['user_theme'] = new_theme_code
                        # Actualizar info de usuario en sesión para reflejar cambios inmediatos
                        if new_theme_code != curr_theme_code: st.session_state['user_info']['tema'] = new_theme_code
                        if up_file: st.session_state['user_info']['avatar'] = params[-2] # El penúltimo param es el blob

                        st.toast("✅ Preferencias guardadas. Aplicando...", icon="🎉")
                        st.rerun()
                    else:
                        st.info("No hay cambios para guardar.")

    # --- T2: PASSWORD ---
    with t2:
        with st.container(border=True):
            st.subheader("Cambiar Contraseña")
            c1, c2 = st.columns(2)
            p1 = c1.text_input("Nueva Contraseña", type="password")
            p2 = c2.text_input("Confirmar Contraseña", type="password")
            
            if st.button("Actualizar Password"):
                if p1 and p1 == p2 and len(p1) >= 4:
                    conn = get_connection()
                    if conn:
                        try:
                            conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s", (p1, user_info['id']))
                            conn.commit(); conn.close()
                            st.success("Contraseña actualizada correctamente.")
                        except Exception as e:
                            st.error(f"Error de BD: {e}")
                else:
                    st.error("Las contraseñas no coinciden o son muy cortas.")

    # --- T3: SALIR ---
    with t3:
        st.warning("¿Deseas cerrar tu sesión actual?")
        if st.button("🔴 Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()
