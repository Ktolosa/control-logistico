import streamlit as st
import time
from utils import brain_get_stats

def show(user_info):
    st.title("🤖 Nexus Brain")
    st.caption("Asistente Virtual de Logística")

    # Historial del chat
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": f"¡Hola {user_info['username']}! Soy la IA de Nexus. Pregúntame sobre el estado del sistema o estadísticas."}
        ]

    # Mostrar mensajes previos
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input del usuario
    if prompt := st.chat_input("Escribe tu consulta aquí..."):
        # 1. Mostrar mensaje usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Lógica de "IA" (Simulada/Reglas)
        # Aquí es donde conectarías una API real (OpenAI/Gemini) en el futuro.
        # Por ahora, usamos reglas lógicas para responder datos reales.
        
        response = ""
        prompt_lower = prompt.lower()
        
        with st.spinner("Analizando base de datos..."):
            time.sleep(0.8) # Simular pensamiento
            
            if "hola" in prompt_lower or "saludos" in prompt_lower:
                response = "¡Hola! ¿En qué puedo ayudarte hoy con la logística?"
            elif "resumen" in prompt_lower or "estadisticas" in prompt_lower or "datos" in prompt_lower:
                # Conectar a datos reales
                stats = brain_get_stats()
                response = f"Aquí tienes un resumen en tiempo real:\n\n{stats}"
            elif "ayuda" in prompt_lower:
                response = "Puedo ayudarte con:\n- Resumen de datos (Escribe 'dame un resumen')\n- Información de contacto\n- Dudas sobre el sistema."
            else:
                response = "Entendido. Esa función específica aún está en entrenamiento, pero puedo darte un resumen general si escribes 'resumen'."

        # 3. Mostrar respuesta asistente
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
