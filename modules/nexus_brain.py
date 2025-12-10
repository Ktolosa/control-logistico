import streamlit as st
import google.generativeai as genai
from utils import get_system_context
import time

# --- CONFIGURACIÓN SEGURA ---
def configure_gemini():
    """Configura la API y busca un modelo disponible automáticamente"""
    if "gemini" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["gemini"]["api_key"])
            
            # INTENTO DE AUTO-DESCUBRIMIENTO DE MODELO
            # Buscamos modelos que soporten 'generateContent'
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            # Preferencia: Flash > Pro > 1.0 > Cualquiera
            preferred_order = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro', 'models/gemini-1.5-pro']
            
            selected_model = None
            
            # 1. Buscar preferidos
            for pref in preferred_order:
                if pref in available_models:
                    selected_model = pref
                    break
            
            # 2. Si no hay preferidos, usar el primero disponible
            if not selected_model and available_models:
                selected_model = available_models[0]
                
            return selected_model
            
        except Exception as e:
            return None
    return None

def show(user_info):
    st.title("🤖 Nexus Brain")
    st.caption("Inteligencia Artificial conectada a tu Logística")

    # Verificar API Key
    if "gemini" not in st.secrets:
        st.warning("⚠️ No se ha configurado la API Key de Gemini en secrets.toml")
        return

    # Obtener modelo dinámicamente
    model_name = configure_gemini()
    
    if not model_name:
        st.error("❌ No se pudo conectar con Google AI o no hay modelos disponibles para tu API Key.")
        return

    # Historial
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": f"¡Hola {user_info['username']}! Soy la IA de Nexus (Motor: {model_name}). ¿Qué necesitas saber hoy?"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input Usuario
    if prompt := st.chat_input("Escribe tu consulta aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # 1. Contexto
                contexto = get_system_context()
                
                # 2. Configurar Modelo Detectado
                model = genai.GenerativeModel(model_name)
                
                system_instruction = f"""
                Eres Nexus Brain, el asistente experto de logística.
                DATOS EN TIEMPO REAL: {contexto}
                Instrucciones: Responde de forma breve, útil y profesional. Si te preguntan datos, usa los que te acabo de dar.
                """
                
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
                full_response = f"Error IA ({model_name}): {str(e)}"
                message_placeholder.error(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
