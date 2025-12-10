import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import get_connection
import time
import re

# --- CONFIGURACIÓN AUTOMÁTICA DE MODELO ---
def configure_gemini():
    if "gemini" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["gemini"]["api_key"])
            # Lista de modelos prioritaria
            preferred = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            for p in preferred:
                if p in available: return p
            return available[0] if available else None
        except: return None
    return None

# --- CARGAR DATOS PARA LA IA (DATAFRAMES REALES) ---
def load_data_for_brain():
    conn = get_connection()
    data = {}
    if conn:
        try:
            # 1. Calendario
            data['df_cal'] = pd.read_sql("SELECT * FROM registro_logistica", conn)
            # 2. PODs
            data['df_pods'] = pd.read_sql("SELECT * FROM pods", conn)
            # 3. Tracking
            data['df_track'] = pd.read_sql("SELECT * FROM tracking_db", conn)
            conn.close()
        except: pass
    return data

def show(user_info):
    st.title("🤖 Nexus Brain Pro")
    st.caption("Analítica Avanzada con IA Generativa")

    # 1. Validación de API
    if "gemini" not in st.secrets:
        st.error("⚠️ Falta API Key en secrets.toml"); return

    model_name = configure_gemini()
    if not model_name: st.error("❌ No hay modelos disponibles."); return

    # 2. Cargar Datos en Memoria (Contexto para el Code Interpreter)
    datasets = load_data_for_brain()
    df_cal = datasets.get('df_cal', pd.DataFrame())
    df_pods = datasets.get('df_pods', pd.DataFrame())
    df_track = datasets.get('df_track', pd.DataFrame())

    # 3. Preparar Prompt del Sistema (Explicando las tablas)
    data_summary = f"""
    TIENES ACCESO A LAS SIGUIENTES TABLAS DE DATOS (PANDAS DATAFRAMES):
    
    1. df_cal (Calendario de Entradas):
       - Columnas: {list(df_cal.columns) if not df_cal.empty else 'Vacia'}
       - Contiene: Registros de llegada de paquetes, proveedores, fechas.
    
    2. df_pods (Manifiestos de Salida):
       - Columnas: {list(df_pods.columns) if not df_pods.empty else 'Vacia'}
       - Contiene: Entregas realizadas, clientes, rutas, responsables.
       
    3. df_track (Inventario Tracking Pro):
       - Columnas: {list(df_track.columns) if not df_track.empty else 'Vacia'}
       - Contiene: Guías individuales y su invoice asociado.

    INSTRUCCIONES PARA RESPONDER:
    - Si te piden DATOS o TABLAS: Responde en formato Markdown normal.
    - Si te piden GRÁFICOS: Debes generar CÓDIGO PYTHON ejecutable.
      - Usa la librería `plotly.express` como `px`.
      - Crea la figura y guárdala en una variable `fig`.
      - NO uses `fig.show()`.
      - El código debe estar delimitado estrictamente por tres comillas invertidas y la palabra python: ```python ... ```
      - Asume que los dataframes `df_cal`, `df_pods`, `df_track` ya existen y están cargados.
    """

    # 4. Chat UI
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "¡Hola! Soy Nexus Brain Pro. Puedo generar gráficos y tablas de tus datos. ¿Qué quieres visualizar?"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # Si el mensaje contiene código de gráfico (marcado internamente), lo ejecutamos
            if "```python" in msg["content"] and msg["role"] == "assistant":
                parts = msg["content"].split("```python")
                # Texto antes del gráfico
                st.markdown(parts[0])
                # Ejecutar gráfico
                if len(parts) > 1:
                    code_block = parts[1].split("```")[0]
                    try:
                        # Entorno local seguro para ejecución
                        local_env = {"pd": pd, "px": px, "go": go, "df_cal": df_cal, "df_pods": df_pods, "df_track": df_track}
                        exec(code_block, {}, local_env)
                        if 'fig' in local_env:
                            st.plotly_chart(local_env['fig'], use_container_width=True)
                    except Exception as e:
                        st.error(f"Error generando gráfico: {e}")
            else:
                st.markdown(msg["content"])

    # 5. Lógica de Respuesta
    if prompt := st.chat_input("Ej: Grafica los paquetes por proveedor..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizando datos y generando respuesta..."):
                try:
                    model = genai.GenerativeModel(model_name)
                    chat = model.start_chat(history=[]) # Historial simplificado para ahorro de tokens
                    
                    response = chat.send_message(f"{data_summary}\n\nUSUARIO: {prompt}")
                    text_resp = response.text
                    
                    # Detectar si hay código para ejecutar
                    if "```python" in text_resp:
                        parts = text_resp.split("```python")
                        st.markdown(parts[0]) # Texto explicativo
                        
                        code_block = parts[1].split("```")[0]
                        
                        # Ejecución en vivo
                        local_env = {"pd": pd, "px": px, "go": go, "df_cal": df_cal, "df_pods": df_pods, "df_track": df_track}
                        exec(code_block, {}, local_env)
                        
                        if 'fig' in local_env:
                            st.plotly_chart(local_env['fig'], use_container_width=True)
                        else:
                            st.warning("La IA generó código pero no creó la variable 'fig'.")
                    else:
                        st.markdown(text_resp)
                        
                    st.session_state.messages.append({"role": "assistant", "content": text_resp})
                    
                except Exception as e:
                    st.error(f"Error: {e}")
