import streamlit as st
import mysql.connector
import io
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- CONSTANTES GLOBALES ---
APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app"
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# --- TEMAS (COLORES Y ESTILOS) ---
THEMES = {
    "light": {"name": "Claro", "bg": "#f8fafc", "text": "#1e293b", "card": "#ffffff", "btn_pri": "#2563eb", "btn_txt": "#ffffff", "nav_bg": "#ffffff", "nav_text": "#1e293b", "ok_bg": "#dcfce7", "ok_txt": "#16a34a", "err_bg": "#fee2e2", "err_txt": "#dc2626", "shadow": "rgba(0,0,0,0.05)"},
    "dark": {"name": "Oscuro", "bg": "#0f172a", "text": "#f1f5f9", "card": "#1e293b", "btn_pri": "#3b82f6", "btn_txt": "#ffffff", "nav_bg": "#1e293b", "nav_text": "#f1f5f9", "ok_bg": "#064e3b", "ok_txt": "#6ee7b7", "err_bg": "#7f1d1d", "err_txt": "#fca5a5", "shadow": "rgba(0,0,0,0.3)"},
    "blue": {"name": "Azul Pro", "bg": "#eff6ff", "text": "#1e3a8a", "card": "#ffffff", "btn_pri": "#1d4ed8", "btn_txt": "#ffffff", "nav_bg": "#dbeafe", "nav_text": "#1e3a8a", "ok_bg": "#dbeafe", "ok_txt": "#1e40af", "err_bg": "#fee2e2", "err_txt": "#991b1b", "shadow": "rgba(37,99,235,0.1)"},
    "purple": {"name": "Futuro", "bg": "#faf5ff", "text": "#581c87", "card": "#ffffff", "btn_pri": "#7e22ce", "btn_txt": "#ffffff", "nav_bg": "#f3e8ff", "nav_text": "#581c87", "ok_bg": "#f3e8ff", "ok_txt": "#6b21a8", "err_bg": "#fee2e2", "err_txt": "#be123c", "shadow": "rgba(126,34,206,0.1)"},
    "green": {"name": "Naturaleza", "bg": "#f0fdf4", "text": "#14532d", "card": "#ffffff", "btn_pri": "#16a34a", "btn_txt": "#ffffff", "nav_bg": "#dcfce7", "nav_text": "#14532d", "ok_bg": "#dcfce7", "ok_txt": "#15803d", "err_bg": "#fee2e2", "err_txt": "#b91c1c", "shadow": "rgba(22,163,74,0.1)"},
    "orange": {"name": "Cálido", "bg": "#fff7ed", "text": "#7c2d12", "card": "#ffffff", "btn_pri": "#ea580c", "btn_txt": "#ffffff", "nav_bg": "#ffedd5", "nav_text": "#9a3412", "ok_bg": "#f0fdf4", "ok_txt": "#15803d", "err_bg": "#fef2f2", "err_txt": "#b91c1c", "shadow": "rgba(234,88,12,0.1)"},
}
THEME_NAMES = list(THEMES.keys()) 

# --- DB & AUTH ---
def get_connection():
    try:
        config = { "host": st.secrets["mysql"]["host"], "user": st.secrets["mysql"]["user"], "password": st.secrets["mysql"]["password"], "database": st.secrets["mysql"]["database"], "ssl_verify_identity": True, "ssl_ca": "/etc/ssl/certs/ca-certificates.crt", "connection_timeout": 10 }
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        try:
            if err.errno == 2026: config.pop("ssl_ca"); config["ssl_verify_identity"] = False; return mysql.connector.connect(**config)
        except: pass
        return None
    except: return None

def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try: cur = conn.cursor(dictionary=True); cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p)); res = cur.fetchone(); conn.close(); return res
    except: 
        if conn: conn.close()
        return None

# --- TOOLS ---
def decode_image(image_file):
    try: bytes_data = image_file.getvalue(); file_bytes = np.asarray(bytearray(bytes_data), dtype=np.uint8); img = cv2.imdecode(file_bytes, 1); decoded_objects = decode(img); return [obj.data.decode('utf-8') for obj in decoded_objects]
    except: return []

def to_excel_bytes(df, fmt='xlsx'):
    out = io.BytesIO()
    import pandas as pd
    if fmt == 'xlsx':
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df.to_excel(w, index=False, sheet_name='Sheet1')
    else:
        with pd.ExcelWriter(out, engine='xlwt') as w: df.to_excel(w, index=False, sheet_name='Sheet1')
    return out.getvalue()

def enviar_email_con_adjuntos(destinatario, asunto, cuerpo, archivos_adjuntos):
    if not destinatario: return False, "Sin destinatario"
    try:
        sender_email = st.secrets["email"]["sender_email"]; sender_password = st.secrets["email"]["sender_password"]; smtp_server = st.secrets["email"]["smtp_server"]; smtp_port = st.secrets["email"]["smtp_port"]
        msg = MIMEMultipart(); msg['From'] = sender_email; msg['To'] = destinatario; msg['Subject'] = asunto; msg.attach(MIMEText(cuerpo, 'plain'))
        for nombre, datos in archivos_adjuntos: part = MIMEApplication(datos, Name=nombre); part['Content-Disposition'] = f'attachment; filename="{nombre}"'; msg.attach(part)
        server = smtplib.SMTP(smtp_server, smtp_port); server.starttls(); server.login(sender_email, sender_password); server.sendmail(sender_email, destinatario, msg.as_string()); server.quit(); return True, "Enviado"
    except Exception as e: return False, str(e)

# --- TRACKING PRO DB ---
def init_tracking_db():
    conn = get_connection()
    if conn:
        try: cur = conn.cursor(); cur.execute("""CREATE TABLE IF NOT EXISTS tracking_db (id INT AUTO_INCREMENT PRIMARY KEY, invoice VARCHAR(100) NOT NULL, tracking VARCHAR(100) NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, INDEX idx_tracking (tracking), INDEX idx_invoice (invoice));"""); conn.commit(); conn.close()
        except: pass

def guardar_base_tracking(invoice, lista_trackings):
    conn = get_connection(); 
    if not conn: return False, "Error Conexión"
    try: cur = conn.cursor(); vals = [(invoice, t) for t in lista_trackings]; cur.executemany("INSERT INTO tracking_db (invoice, tracking) VALUES (%s, %s)", vals); conn.commit(); conn.close(); return True, f"{len(vals)} guardados"
    except Exception as e: return False, str(e)

# MEJORA: Procesamiento por lotes para evitar desconexiones (Error 2013)
def buscar_trackings_masivo(lista_trackings):
    conn = get_connection()
    if not conn: return pd.DataFrame()
    
    todos_los_datos = []
    BATCH_SIZE = 1000 # Procesar de 1000 en 1000
    
    try:
        import pandas as pd
        cur = conn.cursor(dictionary=True)
        
        # Iteramos sobre la lista en trozos (chunks)
        for i in range(0, len(lista_trackings), BATCH_SIZE):
            lote = lista_trackings[i : i + BATCH_SIZE]
            if not lote: continue
            
            format_strings = ','.join(['%s'] * len(lote))
            query = f"SELECT tracking, invoice FROM tracking_db WHERE tracking IN ({format_strings})"
            
            cur.execute(query, tuple(lote))
            todos_los_datos.extend(cur.fetchall())
            
        conn.close()
        return pd.DataFrame(todos_los_datos)
    except: 
        if conn: conn.close()
        return pd.DataFrame(todos_los_datos) if todos_los_datos else pd.DataFrame()

def obtener_resumen_bases():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        import pandas as pd
        # SQL Optimizado para TiDB
        query = """
            SELECT 
                invoice, 
                COUNT(*) as cantidad, 
                MAX(created_at) as fecha_creacion 
            FROM tracking_db 
            GROUP BY invoice 
            ORDER BY fecha_creacion DESC
        """
        cur = conn.cursor(dictionary=True)
        cur.execute(query)
        data = cur.fetchall()
        conn.close()
        return pd.DataFrame(data)
    except Exception as e:
        print(f"Error SQL: {e}") 
        return pd.DataFrame()

def eliminar_base_invoice(invoice):
    conn = get_connection(); 
    if not conn: return False
    try: cur = conn.cursor(); cur.execute("DELETE FROM tracking_db WHERE invoice = %s", (invoice,)); conn.commit(); conn.close(); return True
    except: return False

# --- CSS SUPER ESTÉTICO ---
def load_css(theme_code="light"):
    t = THEMES.get(theme_code, THEMES["light"])
    
    css = f"""
    <style>
        /* UI Limpia */
        [data-testid="stSidebarNav"], [data-testid="stToolbar"], footer, header {{ display: none !important; }}
        #MainMenu, [data-testid="stStatusWidget"], .stDeployButton, [data-testid="stDecoration"] {{ display: none !important; visibility: hidden !important; }}
        
        :root {{ 
            --pri: {t['btn_pri']}; --bg: {t['bg']}; --card: {t['card']}; --txt: {t['text']}; 
            --shadow: {t.get('shadow', 'rgba(0,0,0,0.1)')};
        }}
        
        @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        
        .stApp {{ 
            background-color: var(--bg); 
            font-family: 'Segoe UI', sans-serif; 
            color: var(--txt);
            animation: fadeInUp 0.6s ease-out; 
            margin-top: -60px;
        }}

        h1, h2, h3, p, label, .stDataFrame {{ color: var(--txt) !important; }}
        
        section[data-testid="stSidebar"] {{ 
            background-color: {t['nav_bg']} !important; 
            border-right: 1px solid rgba(0,0,0,0.05);
            box-shadow: 5px 0 15px var(--shadow);
        }}
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] div {{ color: {t['nav_text']} !important; }}
        
        /* Botones del Menú */
        .menu-btn {{ 
            width: 100%; height: 110px !important;
            border: 1px solid rgba(0,0,0,0.05); border-radius: 16px;
            background-color: var(--card); color: var(--txt);
            font-size: 18px; font-weight: 600;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            box-shadow: 0 4px 6px var(--shadow); 
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            margin-bottom: 15px; cursor: pointer; position: relative; overflow: hidden;
        }}
        .menu-btn:hover {{ 
            transform: translateY(-5px) scale(1.02); 
            box-shadow: 0 15px 30px var(--shadow); 
            border-color: var(--pri); color: var(--pri);
        }}

        /* Botones Estándar */
        div.stButton > button {{ 
            width: 100%; border-radius: 12px; font-weight: 600; border: none;
            box-shadow: 0 2px 4px var(--shadow); transition: all 0.2s;
        }}
        div.stButton > button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px var(--shadow); }}
        div.stButton > button[kind="primary"] {{ 
            background: {t['btn_pri']} !important; color: {t['btn_txt']} !important; 
        }}

        /* Inputs & Cards */
        .stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea {{ 
            background-color: var(--card) !important; color: var(--txt) !important; 
            border: 1px solid rgba(0,0,0,0.1) !important; border-radius: 10px;
        }}
        .stTextInput>div>div>input:focus {{ border-color: var(--pri) !important; box-shadow: 0 0 0 2px {t['btn_pri']}33; }}
        
        .kpi-card, [data-testid="stExpander"], div.stForm, [data-testid="stContainer"] {{ 
            background: var(--card); 
            border: 1px solid rgba(0,0,0,0.05); border-radius: 16px; 
            padding: 20px; 
            box-shadow: 0 4px 20px var(--shadow);
        }}
        
        .kpi-val {{ font-size: 1.8rem; font-weight: 800; color: var(--txt); }}
        .kpi-lbl {{ font-size: 0.8rem; opacity: 0.7; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }}

        .stTabs [data-baseweb="tab-list"] {{ border-bottom: 2px solid rgba(0,0,0,0.05); gap: 10px; }}
        .stTabs [data-baseweb="tab"] {{ border-radius: 8px; padding: 8px 16px; transition: background 0.3s; }}
        .stTabs [data-baseweb="tab"]:hover {{ background-color: rgba(0,0,0,0.02); }}
        .stTabs [aria-selected="true"] {{ background-color: {t['btn_pri']}11 !important; color: var(--pri) !important; border: none !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
