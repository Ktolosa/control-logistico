import streamlit as st
import mysql.connector
import io
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- CONSTANTES ---
APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app"
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- CONEXIÓN BD (Con Caché para mayor velocidad) ---
@st.cache_resource
def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"]
        )
    except: return None

# --- AUTH ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        # Nota: Asegúrate de que tu tabla tenga 'activo' o quita 'AND activo=1' si da error
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s", (u, p))
        res = cur.fetchone()
        return res
    except: return None

# --- HERRAMIENTAS ---
def decode_image(image_file):
    try:
        bytes_data = image_file.getvalue()
        file_bytes = np.asarray(bytearray(bytes_data), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        decoded_objects = decode(img)
        return [obj.data.decode('utf-8') for obj in decoded_objects]
    except: return []

def to_excel_bytes(df, fmt='xlsx'):
    out = io.BytesIO()
    import pandas as pd
    if fmt == 'xlsx':
        with pd.ExcelWriter(out, engine='xlsxwriter') as w:
            df.to_excel(w, index=False, sheet_name='Sheet1')
    else:
        with pd.ExcelWriter(out, engine='xlwt') as w:
            df.to_excel(w, index=False, sheet_name='Sheet1')
    return out.getvalue()

# --- CSS GLOBAL DINÁMICO ---
def load_css(tema="light"):
    # Definición de paletas de colores
    if tema == "dark":
        bg_color = "#1e1e1e"
        text_color = "#e0e0e0"
        card_bg = "#333333"
        btn_bg = "#444444"
        btn_text = "#ffffff"
    elif tema == "blue":
        bg_color = "#e3f2fd"
        text_color = "#0d47a1"
        card_bg = "#ffffff"
        btn_bg = "#bbdefb"
        btn_text = "#0d47a1"
    else: # Light (Default)
        bg_color = "#f8fafc"
        text_color = "#1e293b"
        card_bg = "#ffffff"
        btn_bg = "#ffffff"
        btn_text = "#1e293b"

    st.markdown(f"""
    <style>
        /* Ocultar elementos por defecto de Streamlit */
        [data-testid="stSidebarNav"], [data-testid="stToolbar"], footer {{ display: none !important; }}
        
        /* Tema Global */
        .stApp {{ background-color: {bg_color}; font-family: 'Segoe UI', sans-serif; color: {text_color}; }}
        h1, h2, h3, p, div, span, label, li {{ color: {text_color}; }}
        
        /* Botones del Menú Principal */
        .menu-btn {{
            width: 100%; height: 100px !important;
            border: 1px solid #e2e8f0; border-radius: 15px;
            background-color: {btn_bg}; color: {btn_text};
            font-size: 18px; font-weight: 600;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.2s; margin-bottom: 15px;
        }}
        .menu-btn:hover {{ transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); border-color: #3b82f6; }}
        
        /* Botones estándar */
        div.stButton > button:first-child {{ width: 100%; border-radius: 10px; font-weight: 600; }}
        
        /* Tarjetas KPI */
        .kpi-card {{ background: {card_bg}; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; }}
        .kpi-val {{ font-size: 1.4rem; font-weight: 800; color: {text_color}; }}
        .kpi-lbl {{ font-size: 0.75rem; color: #64748b; font-weight: 700; text-transform: uppercase; }}
        
        /* Estilos de inputs en modo oscuro */
        input, select, textarea {{ background-color: {card_bg} !important; color: {text_color} !important; }}
        
        /* Estilo para foto redonda */
        .profile-img {{ border-radius: 50%; border: 3px solid #ccc; }}
    </style>
    """, unsafe_allow_html=True)
