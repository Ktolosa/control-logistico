import streamlit as st
import mysql.connector
import io
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- CONSTANTES GLOBALES ---
APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app"
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- DEFINICIÓN DE 10 TEMAS ---
# Cada tema define colores para: fondo, texto, tarjetas, botones primarios, sidebar y alertas
THEMES = {
    "light": {
        "name": "Claro (Default)",
        "bg": "#f8fafc", "text": "#1e293b", "card": "#ffffff",
        "btn_pri": "#2563eb", "btn_txt": "#ffffff", 
        "nav_bg": "#ffffff", "nav_text": "#1e293b",
        "ok_bg": "#dcfce7", "ok_txt": "#16a34a", "err_bg": "#fee2e2", "err_txt": "#dc2626"
    },
    "dark": {
        "name": "Oscuro",
        "bg": "#121212", "text": "#e0e0e0", "card": "#1e1e1e",
        "btn_pri": "#3b82f6", "btn_txt": "#ffffff",
        "nav_bg": "#1e1e1e", "nav_text": "#e0e0e0",
        "ok_bg": "#064e3b", "ok_txt": "#6ee7b7", "err_bg": "#7f1d1d", "err_txt": "#fca5a5"
    },
    "blue": {
        "name": "Azul Corporativo",
        "bg": "#eff6ff", "text": "#1e3a8a", "card": "#ffffff",
        "btn_pri": "#1e40af", "btn_txt": "#ffffff",
        "nav_bg": "#dbeafe", "nav_text": "#1e3a8a",
        "ok_bg": "#dbeafe", "ok_txt": "#1e40af", "err_bg": "#fee2e2", "err_txt": "#991b1b"
    },
    "green": {
        "name": "Naturaleza",
        "bg": "#f0fdf4", "text": "#14532d", "card": "#ffffff",
        "btn_pri": "#16a34a", "btn_txt": "#ffffff",
        "nav_bg": "#dcfce7", "nav_text": "#14532d",
        "ok_bg": "#dcfce7", "ok_txt": "#15803d", "err_bg": "#fee2e2", "err_txt": "#b91c1c"
    },
    "purple": {
        "name": "Moderno Púrpura",
        "bg": "#faf5ff", "text": "#581c87", "card": "#ffffff",
        "btn_pri": "#7e22ce", "btn_txt": "#ffffff",
        "nav_bg": "#f3e8ff", "nav_text": "#581c87",
        "ok_bg": "#f3e8ff", "ok_txt": "#6b21a8", "err_bg": "#fee2e2", "err_txt": "#be123c"
    },
    "red": {
        "name": "Alerta Roja",
        "bg": "#fef2f2", "text": "#7f1d1d", "card": "#ffffff",
        "btn_pri": "#dc2626", "btn_txt": "#ffffff",
        "nav_bg": "#fee2e2", "nav_text": "#991b1b",
        "ok_bg": "#ecfdf5", "ok_txt": "#047857", "err_bg": "#fee2e2", "err_txt": "#b91c1c"
    },
    "orange": {
        "name": "Cálido Naranja",
        "bg": "#fff7ed", "text": "#7c2d12", "card": "#ffffff",
        "btn_pri": "#ea580c", "btn_txt": "#ffffff",
        "nav_bg": "#ffedd5", "nav_text": "#9a3412",
        "ok_bg": "#f0fdf4", "ok_txt": "#15803d", "err_bg": "#fef2f2", "err_txt": "#b91c1c"
    },
    "teal": {
        "name": "Océano",
        "bg": "#f0fdfa", "text": "#134e4a", "card": "#ffffff",
        "btn_pri": "#0d9488", "btn_txt": "#ffffff",
        "nav_bg": "#ccfbf1", "nav_text": "#115e59",
        "ok_bg": "#ccfbf1", "ok_txt": "#0f766e", "err_bg": "#fee2e2", "err_txt": "#b91c1c"
    },
    "grey": {
        "name": "Minimalista Gris",
        "bg": "#f3f4f6", "text": "#374151", "card": "#ffffff",
        "btn_pri": "#4b5563", "btn_txt": "#ffffff",
        "nav_bg": "#e5e7eb", "nav_text": "#1f2937",
        "ok_bg": "#e5e7eb", "ok_txt": "#374151", "err_bg": "#fee2e2", "err_txt": "#b91c1c"
    },
     "contrast": {
        "name": "Alto Contraste",
        "bg": "#000000", "text": "#ffffff", "card": "#000000",
        "btn_pri": "#ffff00", "btn_txt": "#000000",
        "nav_bg": "#000000", "nav_text": "#ffff00",
        "ok_bg": "#000000", "ok_txt": "#00ff00", "err_bg": "#000000", "err_txt": "#ff0000",
        "border": "#ffff00" # Borde extra para contraste
    }
}
# Lista de claves de temas para selectores
THEME_NAMES = list(THEMES.keys())


# --- CONEXIÓN BD (SSL para TiDB) ---
def get_connection():
    try:
        config = {
            "host": st.secrets["mysql"]["host"],
            "user": st.secrets["mysql"]["user"],
            "password": st.secrets["mysql"]["password"],
            "database": st.secrets["mysql"]["database"],
            "ssl_verify_identity": True,
            "ssl_ca": "/etc/ssl/certs/ca-certificates.crt",
            "connection_timeout": 10 
        }
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        # Fallback para desarrollo local si falla SSL path linux
        try:
            if err.errno == 2026:
                config.pop("ssl_ca")
                config["ssl_verify_identity"] = False
                return mysql.connector.connect(**config)
        except: pass
        return None
    except: return None

# --- AUTH ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
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

# --- CSS DINÁMICO (10 TEMAS) ---
def load_css(theme_code="light"):
    # Recuperar colores del tema seleccionado, fallback a 'light' si falla
    t = THEMES.get(theme_code, THEMES["light"])
    
    # Borde especial para alto contraste
    border_color = t.get("border", "#e2e8f0")
    
    css = f"""
    <style>
        /* Ocultar elementos estándar */
        [data-testid="stSidebarNav"], [data-testid="stToolbar"], footer {{ display: none !important; }}
        
        /* --- VARIABLES GLOBALES DEL TEMA --- */
        :root {{
            --primary-color: {t['btn_pri']};
            --background-color: {t['bg']};
            --secondary-background-color: {t['card']};
            --text-color: {t['text']};
        }}
        
        /* Aplicación Principal */
        .stApp {{ background-color: {t['bg']}; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: {t['text']}; }}
        h1, h2, h3, h4, h5, h6, p, div, span, label, li, .stDataFrame {{ color: {t['text']} !important; }}
        
        /* Sidebar / Navegación */
        section[data-testid="stSidebar"] {{ background-color: {t['nav_bg']} !important; border-right: 1px solid {border_color}; }}
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] div {{ color: {t['nav_text']} !important; }}
        
        /* BOTONES MENU HOME */
        .menu-btn {{
            width: 100%; height: 100px !important;
            border: 1px solid {border_color}; border-radius: 15px;
            background-color: {t['card']}; color: {t['text']};
            font-size: 18px; font-weight: 600;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.2s; margin-bottom: 15px;
        }}
        .menu-btn:hover {{ transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); border-color: {t['btn_pri']}; color: {t['btn_pri']}; }}
        
        /* Botones Estándar de Streamlit */
        div.stButton > button:first-child {{ width: 100%; border-radius: 10px; font-weight: 600; border: 1px solid {border_color}; color: {t['text']}; background-color: {t['card']}; }}
        div.stButton > button:first-child:hover {{ border-color: {t['btn_pri']}; color: {t['btn_pri']}; }}
        
        /* Botones Primarios (Type="primary") */
        div.stButton > button[kind="primary"] {{
            background-color: {t['btn_pri']} !important; color: {t['btn_txt']} !important; border: none !important;
        }}
        div.stButton > button[kind="primary"]:hover {{ opacity: 0.9; }}

        /* Inputs y Selects */
        .stTextInput > div > div > input, .stSelectbox > div > div > div, .stTextArea > div > div > textarea, .stNumberInput > div > div > input {{
            background-color: {t['card']} !important; color: {t['text']} !important; border-color: {border_color} !important;
        }}
        
        /* Tarjetas y Contenedores */
        .kpi-card, [data-testid="stExpander"], div.stForm {{ background: {t['card']}; border: 1px solid {border_color}; border-radius: 12px; padding: 15px; }}
        .kpi-val {{ font-size: 1.4rem; font-weight: 800; color: {t['text']}; }}
        .kpi-lbl {{ font-size: 0.75rem; opacity: 0.8; font-weight: 700; text-transform: uppercase; }}
        
        /* ALERTAS PERSONALIZADAS */
        .count-ok {{ color: {t['ok_txt']}; font-weight: bold; background:{t['ok_bg']}; padding:4px 8px; border-radius:6px; border: 1px solid {t['ok_txt']}; }}
        .count-err {{ color: {t['err_txt']}; font-weight: bold; background:{t['err_bg']}; padding:4px 8px; border-radius:6px; border: 1px solid {t['err_txt']};}}

        /* Pestañas (Tabs) */
        .stTabs [data-baseweb="tab-list"] {{ border-bottom-color: {border_color}; }}
        .stTabs [data-baseweb="tab"] {{ color: {t['text']}; }}
        .stTabs [aria-selected="true"] {{ color: {t['btn_pri']} !important; border-top-color: {t['btn_pri']} !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
# --- FUNCIONES PARA TRACKING PRO ---
def init_tracking_db():
    """Crea la tabla si no existe"""
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tracking_db (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    invoice VARCHAR(100) NOT NULL,
                    tracking VARCHAR(100) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_tracking (tracking),
                    INDEX idx_invoice (invoice)
                );
            """)
            conn.commit(); conn.close()
        except: pass

def guardar_base_tracking(invoice, lista_trackings):
    conn = get_connection()
    if not conn: return False, "Error de conexión"
    try:
        cur = conn.cursor()
        # Verificar si ya existe el invoice para advertir o limpiar (opcional, aquí solo agregamos)
        # Inserción masiva
        vals = [(invoice, t) for t in lista_trackings]
        cur.executemany("INSERT INTO tracking_db (invoice, tracking) VALUES (%s, %s)", vals)
        conn.commit(); conn.close()
        return True, f"{len(vals)} trackings guardados en {invoice}"
    except Exception as e: return False, str(e)

def buscar_trackings_masivo(lista_trackings):
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        # Convertimos la lista a formato SQL seguro para IN (...)
        format_strings = ','.join(['%s'] * len(lista_trackings))
        query = f"SELECT tracking, invoice FROM tracking_db WHERE tracking IN ({format_strings})"
        
        import pandas as pd
        df = pd.read_sql(query, conn, params=tuple(lista_trackings))
        conn.close()
        return df
    except: return pd.DataFrame()

def obtener_resumen_bases():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT invoice, COUNT(*) as cantidad, MAX(created_at) as fecha_creacion FROM tracking_db GROUP BY invoice ORDER BY created_at DESC"
        import pandas as pd
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except: return pd.DataFrame()

def eliminar_base_invoice(invoice):
    conn = get_connection()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tracking_db WHERE invoice = %s", (invoice,))
        conn.commit(); conn.close()
        return True
    except: return False
