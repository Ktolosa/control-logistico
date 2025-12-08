import streamlit as st
import pandas as pd
from utils import get_connection

def show(user_info):
    st.title("Admin Usuarios")
    
    t1, t2, t3 = st.tabs(["Crear Usuario", "Lista & Roles", "Restablecer Claves"])
    
    with t1:
        with st.form("new_user"):
            u = st.text_input("Usuario")
            r = st.selectbox("Rol", ["user", "analista", "admin"])
            if st.form_submit_button("Crear"):
                conn = get_connection()
                if conn:
                    try:
                        conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
                        conn.commit(); conn.close()
                        st.success("Creado")
                    except: st.error("Error/Duplicado")

    with t2:
        conn = get_connection()
        if conn:
            df = pd.read_sql("SELECT id, username, rol, activo FROM usuarios", conn)
            st.dataframe(df, use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            uid = c1.selectbox("Seleccionar Usuario", df['id'].tolist())
            
            if uid:
                curr = df[df['id']==uid].iloc[0]
                new_rol = c2.selectbox("Nuevo Rol", ["user","analista","admin"], index=["user","analista","admin"].index(curr['rol']))
                
                if c2.button("💾 Guardar Rol"):
                    conn.cursor().execute("UPDATE usuarios SET rol=%s WHERE id=%s", (new_rol, uid))
                    conn.commit()
                    st.success("Rol actualizado"); st.rerun()
                
                btn_txt = "🔴 Desactivar" if curr['activo'] else "🟢 Reactivar"
                if c3.button(btn_txt):
                    conn.cursor().execute("UPDATE usuarios SET activo=%s WHERE id=%s", (0 if curr['activo'] else 1, uid))
                    conn.commit()
                    st.rerun()
            conn.close()

    with t3:
        conn = get_connection()
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn)
        
        if reqs.empty: st.info("No hay solicitudes pendientes.")
        
        for _, r in reqs.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.warning(f"Solicitud: {r['username']}")
            if c2.button(f"Reset {r['username']}", key=r['id']):
                cur = conn.cursor()
                cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (r['username'],))
                cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (r['id'],))
                conn.commit()
                st.success("Restablecido a 123456"); st.rerun()
        conn.close()
