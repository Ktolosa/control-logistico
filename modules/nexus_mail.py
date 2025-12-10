import streamlit as st
import pandas as pd
from utils import init_mail_db, send_internal_message, get_user_messages, get_all_usernames
import time

def show(user_info):
    init_mail_db()
    st.title("📨 Nexus Mail")
    
    # Menú lateral para carpetas
    carpeta = st.radio("Carpetas", ["📥 Bandeja de Entrada", "📤 Enviados", "✍️ Redactar"], horizontal=True, label_visibility="collapsed")
    st.divider()

    # --- BANDEJA DE ENTRADA ---
    if "Bandeja de Entrada" in carpeta:
        st.subheader("Bandeja de Entrada")
        df = get_user_messages(user_info['username'], "inbox")
        
        if df.empty:
            st.info("No tienes mensajes nuevos.")
        else:
            for index, row in df.iterrows():
                # Diseño de tarjeta de correo
                with st.expander(f"📧 {row['subject']} - De: {row['sender']} ({row['timestamp']})"):
                    st.markdown(f"**Mensaje:**")
                    st.write(row['body'])
                    st.caption(f"Recibido el: {row['timestamp']}")

    # --- ENVIADOS ---
    elif "Enviados" in carpeta:
        st.subheader("Mensajes Enviados")
        df = get_user_messages(user_info['username'], "sent")
        
        if df.empty:
            st.info("No has enviado mensajes aún.")
        else:
            for index, row in df.iterrows():
                with st.expander(f"✈️ Para: {row['receiver']} - {row['subject']}"):
                    st.write(row['body'])
                    st.caption(f"Enviado el: {row['timestamp']}")

    # --- REDACTAR ---
    elif "Redactar" in carpeta:
        st.subheader("Nuevo Mensaje")
        
        with st.form("new_mail_form"):
            usuarios = get_all_usernames()
            # Quitamos al usuario actual de la lista
            if user_info['username'] in usuarios: usuarios.remove(user_info['username'])
            
            destinatario = st.selectbox("Para:", usuarios)
            asunto = st.text_input("Asunto:")
            cuerpo = st.text_area("Mensaje:", height=200)
            
            enviar = st.form_submit_button("Enviar Mensaje", type="primary")
            
            if enviar:
                if not asunto or not cuerpo:
                    st.error("Falta asunto o mensaje.")
                else:
                    if send_internal_message(user_info['username'], destinatario, asunto, cuerpo):
                        st.success("Mensaje enviado correctamente.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Error al enviar.")
