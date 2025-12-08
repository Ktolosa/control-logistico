import streamlit as st
import mysql.connector
import io
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- CONSTANTES ---
APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app"
AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- CONEXIÓN BD CORREGIDA ---
# NOTA: No usamos @st.cache_resource aquí para evitar desconexiones por timeout de TiDB
def get_connection():
    try:
        # Configuración para TiDB con SSL obligatorio
        config = {
            "host": st.secrets["mysql"]["host"],
            "user": st.secrets["mysql"]["user"],
            "password": st.secrets["mysql"]["password"],
            "database": st.secrets["mysql"]["database"],
            "ssl_verify_identity": True,
            "ssl_ca": "/etc/ssl/certs/ca-certificates.crt"
        }
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        # Fallback para entorno local (Windows/Mac) donde la ruta SSL puede variar
        try:
            if err.errno == 2026: 
                config.pop("ssl_ca")
                config["ssl_verify_identity"] = False
                return mysql.connector.connect(**config)
        except: 
            pass
        return None
    except Exception as e:
        return None

# --- AUTH ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        # Se verifica que el usuario exista, la contraseña coincida y esté activo
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone()
        conn.close() # Cerramos conexión inmediatamente tras la consulta
        return res
    except: 
        if conn: conn.close()
        return None

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

# --- CSS GLOBAL ---
def load_css(tema="light"):
    # Se añade soporte básico para tema oscuro si se requiere en el futuro
    bg_color = "#f8fafc"
    if tema == "dark": bg_color = "#1e1e1e"
    
    st.markdown(f"""
    <style>
        [data-testid="stSidebarNav"], [data-testid="stToolbar"], footer {{ display: none !important; }}
        .stApp {{ background-color: {bg_color}; font-family: 'Segoe UI', sans-serif; }}
        
        /* BOTONES MENU HOME */
        .menu-btn {{
            width: 100%; height: 100px !important;
            border: 1px solid #e2e8f0; border-radius: 15px;
            background-color: white; color: #1e293b;
            font-size: 18px; font-weight: 600;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.2s; margin-bottom: 15px;
        }}
        .menu-btn:hover {{ transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); border-color: #3b82f6; }}
        
        /* BOTÓN VOLVER */
        div.stButton > button:first-child {{ width: 100%; border-radius: 10px; font-weight: 600; }}
        
        /* KPIs */
        .kpi-card {{ background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; }}
        .kpi-val {{ font-size: 1.4rem; font-weight: 800; color: #0f172a; }}
        .kpi-lbl {{ font-size: 0.75rem; color: #64748b; font-weight: 700; text-transform: uppercase; }}
        
        /* ALERTAS */
        .count-ok {{ color: #16a34a; font-weight: bold; background:#dcfce7; padding:4px 8px; border-radius:6px; }}
        .count-err {{ color: #dc2626; font-weight: bold; background:#fee2e2; padding:4px 8px; border-radius:6px; }}
        
        /* Sidebar (Info Usuario) */
        section[data-testid="stSidebar"] {{ width: 250px !important; }}
    </style>
    """, unsafe_allow_html=True)
