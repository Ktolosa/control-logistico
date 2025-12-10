import streamlit as st
from utils import init_mail_db, send_internal_message, get_user_messages, get_all_usernames
import time

def show(user_info):
    init_mail_db()
    st.title("📨 Nexus Mail")
    
    t1, t2, t3 = st.tabs(["📥 Recibidos", "📤 Enviados", "✍️ Redactar"])

    with t1:
        df = get_user_messages(user_info['username'], "inbox")
        if df.empty: st.info("Sin mensajes nuevos.")
        else:
            for _, r in df.iterrows():
                with st.expander(f"📧 {r['subject']} | De: {r['sender']}"):
                    st.write(r['body']); st.caption(f"{r['timestamp']}")

    with t2:
        df = get_user_messages(user_info['username'], "sent")
        if df.empty: st.info("Bandeja de salida vacía.")
        else:
            for _, r in df.iterrows():
                with st.expander(f"✈️ Para: {r['receiver']} | {r['subject']}"):
                    st.write(r['body']); st.caption(f"{r['timestamp']}")

    with t3:
        with st.form("mail_form"):
            users = get_all_usernames()
            if user_info['username'] in users: users.remove(user_info['username'])
            dest = st.selectbox("Para:", users)
            subj = st.text_input("Asunto")
            msg = st.text_area("Mensaje")
            if st.form_submit_button("Enviar", type="primary"):
                if send_internal_message(user_info['username'], dest, subj, msg):
                    st.success("Enviado"); time.sleep(1); st.rerun()
                else: st.error("Error al enviar")
