import streamlit as st
import google.generativeai as genai
from utils import get_system_context
import time

# Configurar Gemini (Manejo de errores si no hay key)
try:
    if "gemini" in st.secrets:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
    else:
        # Fallback silencioso para no romper la app si no hay key
        pass 
except: pass

def show(user_info):
    st.title("🤖 Nexus Brain")
    st.caption("Inteligencia Artificial conectada a tu Logística")

    # Verificar si hay Key configurada
    if "gemini" not in st.secrets:
        st.warning("⚠️ No se ha configurado la API Key de Gemini en secrets.toml")
        st.info("Agrega: [gemini] api_key = 'TU_KEY'")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": f"¡Hola {user_info['username']}! Soy la IA de Nexus. ¿Qué necesitas saber hoy?"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Escribe tu consulta aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            try:
                # 1. Obtener contexto fresco
                contexto = get_system_context()
                
                # 2. Configurar Modelo 
                # CAMBIO AQUÍ: Usamos 'gemini-pro' que es el más estable
                model = genai.GenerativeModel('gemini-pro') 
                
                system_instruction = f"Eres el asistente de Nexus Logística. Datos actuales: {contexto}. Responde breve y profesionalmente."
                
                # 3. Llamar API
                chat = model.start_chat(history=[])
                response = chat.send_message(f"{system_instruction}\nUsuario: {prompt}")
                full_response = response.text
                
                # 4. Efecto escritura
                display_text = ""
                for chunk in full_response.split():
                    display_text += chunk + " "
                    time.sleep(0.05)
                    message_placeholder.markdown(display_text + "▌")
                message_placeholder.markdown(full_response)

            except Exception as e:
                full_response = f"Error IA: {str(e)}"
                message_placeholder.error(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
