import streamlit as st
from utils import get_connection

def show(user_info):
    st.title("Configuración")
    with st.container(border=True):
        st.subheader("Cambiar Contraseña")
        p1 = st.text_input("Nueva Contraseña", type="password")
        p2 = st.text_input("Confirmar Contraseña", type="password")
        
        if st.button("Actualizar"):
            if p1 and p1 == p2:
                conn = get_connection()
                if conn:
                    conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s", (p1, user_info['id']))
                    conn.commit(); conn.close()
                    st.success("Contraseña actualizada")
            else:
                st.error("Las contraseñas no coinciden o están vacías")
