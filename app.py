import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import re
import io
import uuid
import qrcode
import random
import string
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import numpy as np
import cv2 
from pyzbar.pyzbar import decode

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(
    page_title="Nexus Logística", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# ⚠️ URL BASE
APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app" 
# ---------------------------------------------------------

# --- INTERCEPTOR DE DESCARGA (QR) ---
query_params = st.query_params
if "pod_uuid" in query_params:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    uuid_target = query_params["pod_uuid"]
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga POD</h2>", unsafe_allow_html=True)
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
        )
        q = "SELECT tracking FROM pod_items WHERE pod_uuid = %s"
        df_items = pd.read_sql(q, conn, params=(uuid_target,))
        q_info = "SELECT cliente, fecha, pod_code FROM pods WHERE uuid = %s"
        df_info = pd.read_sql(q_info, conn, params=(uuid_target,))
        conn.close()
        
        if not df_items.empty:
            cliente_nom = df_info.iloc[0]['cliente']
            pod_code_nom = df_info.iloc[0]['pod_code']
            st.success(f"✅ POD {pod_code_nom} Encontrada ({len(df_items)} paq).")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_items.to_excel(writer, index=False, sheet_name='Paquetes')
            st.download_button("📥 DESCARGAR EXCEL", output.getvalue(), f"POD_{pod_code_nom}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
        else: st.error("❌ No encontrada.")
    except Exception as e: st.error(f"Error: {e}")
    st.markdown("---")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# --- ESTADO DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"
for key in ['last_pod_pdf', 'last_pod_name', 'last_pod_excel', 'last_pod_excel_name', 'scanned_trackings', 'scan_buffer_modal']:
    if key not in st.session_state: st.session_state[key] = [] if 'scan' in key else None

# --- 2. CSS (MÓVIL BOTÓN ABAJO IZQUIERDA + PC FIJA) ---
SIDEBAR_WIDTH = "70px"

base_css = """
<style>
    /* Ocultar elementos innecesarios */
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeader"], footer { visibility: hidden !important; }
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 400px; padding-top: 15vh; margin: 0 auto; }
    div[data-testid="stTextInput"] input { border: 1px solid #e2e8f0; padding: 12px; border-radius: 10px; }
    div.stButton > button { width: 100%; border-radius: 10px; padding: 12px; font-weight: 600; background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; color: white; }
</style>
"""

dashboard_css = f"""
<style>
    /* === VISTA PC (Pantalla Grande) === */
    @media (min-width: 768px) {{
        [data-testid="collapsedControl"] {{ display: none !important; }}
        
        section[data-testid="stSidebar"] {{
            display: block !important; width: {SIDEBAR_WIDTH} !important; min-width: {SIDEBAR_WIDTH} !important;
            transform: none !important; visibility: visible !important;
            position: fixed !important; top: 0; left: 0; bottom: 0; z-index: 99999;
            background: #ffffff !important; border-right: 1px solid #e2e8f0; box-shadow: 4px 0 15px rgba(0,0,0,0.02);
        }}
        section[data-testid="stSidebar"] > div {{
            height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-top: 0px !important;
        }}
        .main .block-container {{ margin-left: {SIDEBAR_WIDTH}; width: calc(100% - {SIDEBAR_WIDTH}); padding: 2rem; }}
        [data-testid="stSidebar"] div[role="radiogroup"] {{ flex-direction: column; gap: 15px; }}
    }}

    /* === VISTA MÓVIL (Celulares) === */
    @media (max-width: 767px) {{
        /* BOTÓN HAMBURGUESA FLOTANTE ABAJO A LA IZQUIERDA */
        [data-testid="collapsedControl"] {{
            display: flex !important;
            position: fixed !important;
            top: auto !important;       /* No arriba */
            bottom: 20px !important;    /* Abajo */
            left: 20px !important;      /* Izquierda */
            background-color: #2563eb !important;
            color: white !important;
            border-radius: 50% !important; /* Redondo */
            z-index: 999999 !important;
            width: 50px !important;
            height: 50px !important;
            align-items: center;
            justify-content: center;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.3) !important;
        }}
        
        /* Barra lateral comportamiento nativo */
        section[data-testid="stSidebar"] {{
            background-color: white !important;
            top: 0 !important;
            height: 100vh !important;
            z-index: 999990 !important;
        }}
        
        section[data-testid="stSidebar"] > div {{
            padding-top: 50px !important; 
            display: block !important; 
        }}
        
        .main .block-container {{ margin-left: 0 !important; width: 100% !important; padding: 1rem; padding-bottom: 80px; }}
        
        .avatar-float {{ position: relative !important; margin: 0 auto 20px auto !important; top: 0 !important; }}
        .logout-float {{ position: relative !important; margin-top: 30px !important; bottom: 0 !important; }}
        [data-testid="stSidebar"] div[role="radiogroup"] {{ flex-direction: row; flex-wrap: wrap; justify-content: center; }}
    }}

    /* === ESTILOS COMUNES === */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex; justify-content: center; align-items: center;
        width: 45px; height: 45px; border-radius: 12px; cursor: pointer;
        background: transparent; color: #64748b; font-size: 24px; border: none; transition: 0.2s; margin: 0 auto;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: #f1f5f9; color: #0f172a; transform: scale(1.1); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; color: #2563eb; box-shadow: 0 2px 8px rgba(37,99,235,0.2);
    }}
    
    .avatar-float {{ width: 35px; height: 35px; background: #f1f5f9; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; color: #334155; }}
    .logout-float {{ margin-top: auto; text-align: center; width: 100%; }}
    
    .kpi-card {{ background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; }}
    .kpi-lbl {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 700; }}
    .kpi-val {{ font-size: 1.5rem; color: #0f172a; font-weight: 800; }}
    .count-ok {{ color: #16a34a; font-weight: bold; background:#dcfce7; padding:2px 6px; border-radius:4px; }}
    .count-err {{ color: #dc2626; font-weight: bold; background:#fee2e2; padding:2px 6px; border-radius:4px; }}
</style>
"""

st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)

# --- 3. CONEXIÓN ---
AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
        )
    except: return None

# --- FUNCIONES LÓGICAS ---
def decode_image(image_file):
    try:
        bytes_data = image_file.getvalue()
        file_bytes = np.asarray(bytearray(bytes_data), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        decoded_objects = decode(img)
        return [obj.data.decode('utf-8') for obj in decoded_objects]
    except: return []

def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

def validar_admin_pass(password):
    conn = get_connection()
    if not conn: return False
    try:
        cur = conn.cursor(); cur.execute("SELECT id FROM usuarios WHERE rol='admin' AND activo=1 AND password=%s", (password,))
        res = cur.fetchone(); conn.close(); return True if res else False
    except: return False

def cargar_datos():
    conn = get_connection(); 
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            df['Año'] = df['fecha'].dt.year; df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week; df['DiaSemana'] = df['fecha'].dt.day_name()
            def contar(t): return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()]) if t else 0
            df['conteo_masters_real'] = df['master_lote'].apply(contar)
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast_str, paq, com):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            user = st.session_state['user_info']['username']
            lista_masters = [m.strip() for m in re.split(r'[\n, ]+', mast_str) if m.strip()]
            clean_masters_str = " ".join(lista_masters)
            registro_id = id_reg
            if id_reg is None:
                sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, user))
                registro_id = cur.lastrowid
                st.toast("✅ Guardado")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, id_reg))
                cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,))
                st.toast("✅ Actualizado")
            if lista_masters:
                vals = [(registro_id, m, fecha) for m in lista_masters]
                cur.executemany("INSERT INTO masters_detalle (registro_id, master_code, fecha_registro) VALUES (%s, %s, %s)", vals)
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error BD: {e}")

def eliminar_registro(id_reg, admin_pass):
    if not validar_admin_pass(admin_pass): st.error("🔒 Clave incorrecta"); return False
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor(); cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,)); cur.execute("DELETE FROM registro_logistica WHERE id=%s", (id_reg,)); conn.commit(); conn.close(); st.toast("🗑️ Eliminado"); return True
        except: return False
    return False

# --- LOGICA TEMU / EXCEL ---
def procesar_archivo_temu(uploaded_file):
    try:
        df_raw = pd.read_excel(uploaded_file, header=None).fillna("")
        data_rows = df_raw.iloc[1:]
        data_rows = data_rows[data_rows[3].astype(str).str.strip() != ""]
        if data_rows.empty: return None, None, "Sin datos en columna D."
        grouped = data_rows.groupby(3)
        resultados = {}; resumen_list = []
        h_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        h_cost = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]
        for master, group in grouped:
            r_m = []; r_c = []
            for _, row in group.iterrows():
                r = [""]*21; r[0]=str(row[7]).strip(); r[4]=str(row[10]).strip(); r[6]=str(row[14]).strip(); r[7]=str(row[11]).strip(); r[8]=str(row[12]).strip(); r[9]=str(row[13]).strip(); r[10]=str(row[16]).strip(); r[11]=str(row[17]).strip(); r[12]=str(row[15]).strip(); r[13]=str(row[3]).strip(); r[19]=str(row[5]).strip(); r[1]="YC - Log. for Temu"; r[2]="Zhaoqing"; r[3]="CN"; r[5]="SLV"; r[18]="USD"; r[14]="1"; r[15]="0.45"; r[16]="0.01"; r[17]="N/A"; r[20]="N/A"; r_m.append(r)
                c = [""]*16; c[0]=str(row[7]).strip(); c[2]=str(row[10]).strip(); c[3]=str(row[15]).strip(); c[5]=str(row[5]).strip(); c[7]="0.00"; c[8]="0.01"; c[9]="0.01"; c[10]="0.00"; c[11]="0.00"; c[12]="0.00"; c[13]="0.00"; c[14]="0.00"; c[15]="0.01"; r_c.append(c)
            resultados[master] = {"main": pd.DataFrame(r_m, columns=h_main), "costos": pd.DataFrame(r_c, columns=h_cost), "info": {"paquetes": len(group), "cajas": group[5].nunique()}}
            resumen_list.append({"Master": master, "Cajas": group[5].nunique(), "Paquetes": len(group)})
        return resultados, pd.DataFrame(resumen_list), None
    except Exception as e: return None, None, str(e)

def to_excel_bytes(df, fmt='xlsx'):
    out = io.BytesIO()
    if fmt == 'xlsx': with pd.ExcelWriter(out, engine='xlsxwriter') as w: df.to_excel(w, index=False)
    else: with pd.ExcelWriter(out, engine='xlwt') as w: df.to_excel(w, index=False)
    return out.getvalue()

# --- FUNCIONES POD / PDF ---
def generate_pod_code(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def guardar_pod_digital(cliente, ruta, responsable, paq_dec, bultos, trackings, firma_canvas):
    conn = get_connection(); 
    if not conn: return None, "Error BD"
    try:
        cur = conn.cursor(); uid = str(uuid.uuid4()); code = generate_pod_code(); now = datetime.now()
        blob = None
        if firma_canvas.image_data is not None:
            im = Image.fromarray(firma_canvas.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        sql = "INSERT INTO pods (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        cur.execute(sql, (uid, code, now, cliente, ruta, responsable, paq_dec, len(trackings), bultos, blob, st.session_state['user_info']['username']))
        if trackings: cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", [(uid, t) for t in trackings])
        conn.commit(); conn.close(); return uid, None
    except Exception as e: return None, str(e)

def recuperar_datos_pod(uid):
    conn = get_connection()
    if not conn: return None
    try:
        df_h = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if df_h.empty: return None
        df_i = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        r = df_h.iloc[0]
        return {"uuid": r['uuid'], "pod_code": r.get('pod_code','N/A'), "fecha": r['fecha'], "cliente": r['cliente'], "ruta": r['ruta'], "responsable": r['responsable'], "bultos": r['bultos'], "trackings": df_i['tracking'].tolist(), "firma_bytes": r['signature_blob']}
    except: return None

def generar_pdf_pod(data, pod_uuid, from_history=False):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(37,99,235); pdf.rect(0,0,210,40,'F')
    pdf.set_text_color(255,255,255); pdf.set_font("Arial",'B',24); pdf.text(10,18,"MANIFIESTO / POD")
    pdf.set_font("Arial",'',10); pdf.text(10,28,f"ID: {data.get('pod_code','N/A')} (Ref:{pod_uuid[:6]})"); 
    fd = data.get('fecha', datetime.now()); pdf.text(10,34,f"Fecha: {fd if isinstance(fd,str) else fd.strftime('%Y-%m-%d %H:%M')}")
    
    qr = qrcode.make(f"{APP_BASE_URL}/?pod_uuid={pod_uuid}"); qr.save("qr.png")
    pdf.set_fill_color(255,255,255); pdf.rect(170,5,30,30,'F'); pdf.image("qr.png",172,7,26,26)
    
    pdf.set_y(50); pdf.set_text_color(0,0,0); pdf.set_font("Arial",'B',11)
    pdf.cell(30,8,"CLIENTE:",0,0); pdf.set_font("Arial",'',11); pdf.cell(70,8,data['cliente'],0,0)
    pdf.set_font("Arial",'B',11); pdf.cell(35,8,"RESPONSABLE:",0,0); pdf.set_font("Arial",'',11); pdf.cell(60,8,data['responsable'],0,1)
    pdf.set_font("Arial",'B',11); pdf.cell(30,8,"DETALLE:",0,0); pdf.set_font("Arial",'',11); pdf.cell(165,8,data['ruta'],0,1); pdf.ln(5)
    
    pdf.set_fill_color(240,240,240); pdf.set_font("Arial",'B',10)
    pdf.cell(95,10,"PAQUETES REALES",1,0,'C',1); pdf.cell(95,10,"BULTOS / SACOS",1,1,'C',1)
    pdf.set_font("Arial",'',14); pdf.cell(95,15,str(len(data['trackings'])),1,0,'C'); pdf.cell(95,15,str(data['bultos']),1,1,'C'); pdf.ln(10)
    
    y = pdf.get_y(); pdf.set_font("Arial",'B',10); pdf.text(10,y,"ENTREGADO POR:"); 
    try:
        if from_history and data['firma_bytes']:
            with open("sig.png","wb") as f: f.write(data['firma_bytes'])
            pdf.image("sig.png",10,y+5,80,40)
        elif data.get('firma_img') is not None:
            im = Image.fromarray(data['firma_img'].image_data.astype('uint8'),'RGBA'); im_bg = Image.new("RGB", im.size, (255,255,255)); im_bg.paste(im, mask=im.split()[3]); im_bg.save("sig.png")
            pdf.image("sig.png",10,y+5,80,40)
    except: pass
    pdf.rect(10,y+5,80,40); pdf.text(110,y,"RECIBIDO POR:"); pdf.rect(110,y+5,80,40)
    return pdf.output(dest='S').encode('latin-1')

# --- ADMIN FUNCTIONS ---
def admin_crear_usuario(u, r):
    conn = get_connection()
    if not conn: return False
    try: conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r)); conn.commit(); conn.close(); return True
    except: pass; return False
def admin_get_users():
    conn = get_connection(); 
    if not conn: return pd.DataFrame()
    df=pd.read_sql("SELECT id, username, rol, activo FROM usuarios", conn); conn.close(); return df
def admin_toggle(uid, curr):
    conn = get_connection(); conn.cursor().execute("UPDATE usuarios SET activo=%s WHERE id=%s", (0 if curr==1 else 1, uid)); conn.commit(); conn.close()
def admin_update_role(uid, new_role):
    conn = get_connection(); 
    if conn: conn.cursor().execute("UPDATE usuarios SET rol=%s WHERE id=%s", (new_role, uid)); conn.commit(); conn.close(); return True; return False
def admin_restablecer_password(rid, uname):
    conn = get_connection(); 
    if conn: cur=conn.cursor(); cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,)); cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,)); conn.commit(); conn.close()
def solicitar_reset_pass(username):
    conn = get_connection(); 
    if not conn: return "error"
    try:
        cur = conn.cursor(); cur.execute("SELECT id FROM usuarios WHERE username=%s", (username,)); 
        if cur.fetchone():
            cur.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,)); 
            if not cur.fetchone(): cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,)); conn.commit(); conn.close(); return "ok"
            conn.close(); return "pendiente"
        conn.close(); return "no_user"
    except: return "error"
def cambiar_password(uid, np):
    conn=get_connection();
    if conn:
        try: conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s",(np, uid)); conn.commit(); conn.close(); return True
        except: pass
    return False

# --- MODAL GESTIÓN CARGA ---
@st.dialog("Gestión de Carga")
def modal_registro(datos=None):
    rol = st.session_state['user_info']['rol']
    disabled = (rol == 'analista')
    d_fecha, d_prov, d_plat = date.today(), PROVEEDORES[0], PLATAFORMAS[0]
    d_serv, d_mast, d_paq, d_com, d_id = SERVICIOS[0], "", 0, "", None
    d_esp = 1
    
    if datos:
        d_id = datos.get('id')
        if datos.get('fecha_str'): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        d_serv = datos.get('servicio', SERVICIOS[0]); d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0); d_com = datos.get('comentarios', "")
        d_esp = len([x for x in re.split(r'[\n, ]+', d_mast) if x.strip()]) or 1

    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha Llegada", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            esperados = st.number_input("Masters Esperadas", min_value=1, value=d_esp, disabled=disabled)
            pain = st.number_input("Total Paquetes", 0, value=int(d_paq), disabled=disabled)

        st.markdown("---")
        st.write("📋 **Escaneo / Ingreso de Masters**")
        
        col_cam, col_txt = st.columns([1,2])
        activar_cam = col_cam.toggle("📷 Usar Cámara")
        if activar_cam:
            img = st.camera_input("Escanear código")
            if img:
                codes = decode_image(img)
                if codes:
                    st.success(f"Leído: {codes[0]}")
                    if codes[0] not in st.session_state['scan_buffer_modal']:
                        st.session_state['scan_buffer_modal'].append(codes[0])
        
        if st.session_state.get('scan_buffer_modal'):
            st.info(f"Escaneados: {len(st.session_state['scan_buffer_modal'])}")
            if st.button("Borrar Escaneos"): st.session_state['scan_buffer_modal'] = []; st.rerun()
        
        val_txt = d_mast
        if st.session_state.get('scan_buffer_modal'): val_txt += "\n" + "\n".join(st.session_state['scan_buffer_modal'])

        masters_input = st.text_area("Masters (Uno por línea)", value=val_txt, height=150, disabled=disabled)
        
        lista_final = [m.strip() for m in re.split(r'[\n, ]+', masters_input) if m.strip()]
        conteo_real = len(lista_final); unicos = len(set(lista_final))
        
        c_v1, c_v2 = st.columns(2); c_v1.caption(f"Leídos: {conteo_real}")
        if conteo_real != unicos: st.markdown(f"<div class='count-err'>⚠️ {conteo_real-unicos} Duplicados</div>", unsafe_allow_html=True)
        if esperados > 0:
            if conteo_real == esperados: c_v2.markdown(f"<div class='count-ok'>✅ Cuadra</div>", unsafe_allow_html=True)
            else: c_v2.markdown(f"<div class='count-err'>❌ Dif: {conteo_real-esperados}</div>", unsafe_allow_html=True)

        com = st.text_area("Notas", d_com, disabled=disabled)
        
        if not disabled:
            if st.form_submit_button("💾 Guardar", type="primary"):
                guardar_registro(d_id, fin, pin, clin, sin, masters_input, pain, com)
                st.session_state['scan_buffer_modal'] = []
                st.rerun()

    if d_id is not None and not disabled:
        with st.expander("🗑️ Eliminar"):
            p_del = st.text_input("Clave Admin:", type="password")
            if st.button("Confirmar Borrado", type="secondary"):
                if eliminar_registro(d_id, p_del): st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='login-container'><h2 style='color:#1e293b;'>Nexus Logística</h2></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        u = st.text_input("Usuario", placeholder="Usuario")
        p = st.text_input("Contraseña", type="password", placeholder="Contraseña")
        if st.button("ACCEDER"):
            user = verificar_login(u, p)
            if user: st.session_state['logged_in'] = True; st.session_state['user_info'] = user; st.rerun()
            else: st.error("Error credenciales")
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Recuperar contraseña"):
            ur = st.text_input("Usuario recuperación")
            if st.button("Solicitar Reset"):
                r = solicitar_reset_pass(ur)
                if r=="ok": st.success("Enviado")
                elif r=="pendiente": st.warning("Ya pendiente")
                else: st.warning("Error")

else:
    u_info = st.session_state['user_info']; rol = u_info['rol']
    
    with st.sidebar:
        # En móvil, esto se ve dentro del menú hamburguesa. En PC, fijo a la izquierda.
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div class='avatar-float' style='position:relative; margin:0 auto; text-align:center;'>{av}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; font-size:12px; color:gray; margin-bottom:20px;'>{u_info['username']}</div>", unsafe_allow_html=True)
        
        opts = ["📅", "📈", "📑", "📝", "⚙️"]
        if rol == 'admin': opts.extend(["👥", "🔑"])
        sel = st.radio("Menu", opts, label_visibility="collapsed")
        mapa = {"📅":"calendar","📈":"analytics","📑":"temu","📝":"pod","⚙️":"settings","👥":"users","🔑":"keys"}
        st.session_state['current_view'] = mapa.get(sel, "calendar")
        
        st.markdown("<div class='logout-float'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🚪"): st.session_state['logged_in'] = False; st.rerun()

    vista = st.session_state['current_view']
    df = cargar_datos()

    # --- CALENDARIO ---
    if vista == "calendar":
        c1, c2 = st.columns([6, 1])
        c1.title("Operaciones")
        if rol != 'analista' and c2.button("➕ Nuevo", type="primary"): modal_registro(None)
        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                col = "#3b82f6"
                if "AliExpress" in r['plataforma_cliente']: col = "#f97316"
                elif "Temu" in r['plataforma_cliente']: col = "#10b981"
                props = {"id": int(r['id']), "fecha_str": str(r['fecha_str']), "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']), "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']), "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])}
                evts.append({"title": f"📦{int(r['paquetes'])} | 🔑{r['conteo_masters_real']}", "start": r['fecha_str'], "backgroundColor": col, "borderColor": col, "extendedProps": props})
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    # --- ANALYTICS PRO (RECUPERADO) ---
    elif vista == "analytics":
        st.title("Analytics Pro")
        if df.empty: st.warning("Sin datos")
        else:
            with st.container(border=True):
                c_s, c_d = st.columns([1,2])
                s_mast = c_s.text_input("🔍 Buscar Master")
                rango = c_d.date_input("Rango", [df['fecha'].min(), df['fecha'].max()])
            
            df_fil = df.copy()
            if s_mast:
                conn = get_connection()
                try: 
                    q = f"SELECT registro_id FROM masters_detalle WHERE master_code LIKE '%{s_mast}%'"
                    found = pd.read_sql(q, conn)
                    conn.close()
                    if not found.empty: df_fil = df_fil[df_fil['id'].isin(found['registro_id'])]
                    else: st.error("No encontrado"); df_fil = pd.DataFrame()
                except: pass
            elif len(rango)==2: df_fil = df_fil[(df_fil['fecha'].dt.date>=rango[0])&(df_fil['fecha'].dt.date<=rango[1])]
            
            if not df_fil.empty:
                k1,k2,k3,k4 = st.columns(4)
                k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Paq</div><div class='kpi-val'>{df_fil['paquetes'].sum():,.0f}</div></div>",unsafe_allow_html=True)
                k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Masters</div><div class='kpi-val'>{df_fil['conteo_masters_real'].sum():,.0f}</div></div>",unsafe_allow_html=True)
                k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Viajes</div><div class='kpi-val'>{len(df_fil)}</div></div>",unsafe_allow_html=True)
                k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio</div><div class='kpi-val'>{df_fil['paquetes'].mean():,.0f}</div></div>",unsafe_allow_html=True)
                
                t1,t2,t3 = st.tabs(["📅 Resumen", "📊 Gráficos", "📥 Data"])
                with t1:
                    st.subheader("Resumen Semanal")
                    res = df_fil.groupby(['Año','Semana','Mes']).agg(Paquetes=('paquetes','sum'), Masters=('conteo_masters_real','sum'), Viajes=('id','count')).reset_index()
                    st.dataframe(res, use_container_width=True)
                with t2:
                    g1,g2 = st.columns(2)
                    with g1: st.plotly_chart(px.bar(df_fil.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes'), use_container_width=True)
                    with g2: st.plotly_chart(px.pie(df_fil, names='proveedor_logistico', values='paquetes'), use_container_width=True)
                with t3:
                    st.dataframe(df_fil)
                    st.download_button("Descargar CSV", df_fil.to_csv(index=False).encode('utf-8'), "reporte.csv", "text/csv")

    # --- TEMU MANAGER (RECUPERADO) ---
    elif vista == "temu":
        st.title("Gestor TEMU"); f = st.file_uploader("Excel", type=["xlsx","xls"])
        if f:
            res, df_sum, err = procesar_archivo_temu(f)
            if res:
                st.subheader("Resumen")
                st.dataframe(df_sum, use_container_width=True)
                fmt = st.radio("Fmt", ["xlsx", "xls"], horizontal=True)
                ext = "xlsx" if fmt=="xlsx" else "xls"
                for m, d in res.items():
                    with st.expander(f"📦 {m} ({d['info']['paquetes']} paq)"):
                        search_q = st.text_input(f"🔍 Buscar", key=f"s_{m}")
                        c1,c2 = st.columns(2)
                        c1.download_button("Manifiesto", to_excel_bytes(d['main'],ext), f"{m}.{ext}")
                        c2.download_button("Costos", to_excel_bytes(d['costos'],ext), f"{m}_Costos.{ext}")
                        df_disp = d['main']
                        if search_q: df_disp = df_disp[df_disp.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)]
                        st.dataframe(df_disp, hide_index=True)

    # --- POD DIGITAL (RECUPERADO HISTORIAL) ---
    elif vista == "pod":
        st.title("POD Digital")
        t1, t2 = st.tabs(["Nueva", "Historial"])
        with t1:
            with st.form("pod_form"):
                c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", ["Mail Americas","APG","IMILE"]); rut = c2.text_input("Ruta")
                c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",0)
                paq_obj = st.number_input("Paquetes Declarados",1)
                
                # CÁMARA POD
                act_cam_pod = st.toggle("Usar Cámara")
                if act_cam_pod:
                    img_pod = st.camera_input("Scan")
                    if img_pod:
                        res_pod = decode_image(img_pod)
                        if res_pod: 
                            if res_pod[0] not in st.session_state.get('scanned_trackings',[]):
                                st.session_state['scanned_trackings'].append(res_pod[0])
                                st.success(f"Leído: {res_pod[0]}")
                            else: st.warning("Repetido")
                
                # Mostrar acumulado
                curr_scan = "\n".join(st.session_state.get('scanned_trackings',[]))
                track_raw = st.text_area("Trackings", value=curr_scan, height=150)
                
                firma = st_canvas(fill_color="rgba(255, 165, 0, 0.3)", stroke_width=2, height=150)
                sub_pod = st.form_submit_button("Generar")
            
            if st.button("Limpiar Escaneos"): st.session_state['scanned_trackings'] = []; st.rerun()

            if sub_pod:
                ts = [t.strip() for t in track_raw.split('\n') if t.strip()]
                unique_ts = list(set(ts))
                
                if len(ts) != len(unique_ts): st.error(f"Duplicados: {len(ts)-len(unique_ts)}")
                elif len(ts) != paq_obj: st.error(f"No cuadra: Leídos {len(ts)} vs Declarados {paq_obj}")
                elif not rut or not ts: st.error("Datos faltantes")
                else:
                    d_pod = {"cliente":cli,"ruta":rut,"responsable":resp,"bultos":bult,"trackings":ts,"firma_img":firma if firma.image_data is not None else None}
                    uid, err = guardar_pod_digital(cli, rut, resp, paq_obj, bult, ts, firma)
                    if uid:
                        st.success("Guardado")
                        st.session_state['last_pod_pdf'] = generar_pdf_pod(d_pod, uid)
                        st.session_state['last_pod_name'] = f"POD_{uid[:4]}.pdf"
                        df_ex = pd.DataFrame(ts, columns=['Tracking'])
                        st.session_state['last_pod_excel'] = to_excel_bytes(df_ex,'xlsx')
                        st.session_state['scanned_trackings'] = []
                        st.rerun()
            
            if st.session_state['last_pod_pdf']:
                c1,c2 = st.columns(2)
                c1.download_button("Descargar PDF", st.session_state['last_pod_pdf'], st.session_state['last_pod_name'])
                c2.download_button("Descargar Excel", st.session_state['last_pod_excel'], "Lista.xlsx")

        with t2:
            st.subheader("Buscador Historial")
            search_pod = st.text_input("🔍 Buscar (ID, Cliente, Tracking)")
            conn = get_connection()
            if conn:
                q = "SELECT uuid, pod_code, fecha, cliente, responsable FROM pods ORDER BY fecha DESC LIMIT 50"
                if search_pod:
                    q = f"SELECT DISTINCT p.uuid, p.pod_code, p.fecha, p.cliente, p.responsable FROM pods p LEFT JOIN pod_items pi ON p.uuid = pi.pod_uuid WHERE p.pod_code LIKE '%{search_pod}%' OR p.cliente LIKE '%{search_pod}%' OR pi.tracking LIKE '%{search_pod}%' LIMIT 20"
                df_p = pd.read_sql(q, conn)
                conn.close()
                st.dataframe(df_p)
                
                if not df_p.empty:
                    # SELECTOR MEJORADO: Muestra ID corto y Cliente en lugar de UUID
                    pod_options = {row['uuid']: f"{row['pod_code']} - {row['cliente']} ({row['fecha']})" for i, row in df_p.iterrows()}
                    selected_uuid = st.selectbox("Seleccionar para Reimprimir", list(pod_options.keys()), format_func=lambda x: pod_options[x])
                    
                    if st.button("Regenerar Archivos"):
                        d_hist = recuperar_datos_pod(selected_uuid)
                        if d_hist:
                            pdf_hist = generar_pdf_pod(d_hist, selected_uuid, from_history=True)
                            df_excel_hist = pd.DataFrame(d_hist['trackings'], columns=["Tracking"])
                            excel_hist = to_excel_bytes(df_excel_hist, 'xlsx')
                            c1,c2 = st.columns(2)
                            c1.download_button("📥 PDF", pdf_hist, f"POD_{d_hist['pod_code']}.pdf")
                            c2.download_button("📊 Excel", excel_hist, f"List_{d_hist['pod_code']}.xlsx")
            else: st.error("Error de conexión.")

    elif vista == "settings":
        st.title("Configuración")
        with st.container(border=True):
            st.subheader("Contraseña")
            p1 = st.text_input("Nueva", type="password"); p2 = st.text_input("Confirmar", type="password")
            if st.button("Actualizar"):
                if p1==p2 and p1: 
                    if cambiar_password(u_info['id'], p1): st.success("OK")
                else: st.warning("Error")

    elif vista == "users":
        st.title("Admin Usuarios"); t1,t2=st.tabs(["Crear","Lista"])
        with t1: 
            with st.form("nu"): 
                u=st.text_input("User"); r=st.selectbox("Rol",["user","analista","admin"])
                if st.form_submit_button("Crear"): admin_crear_usuario(u,r)
        with t2:
            df_u = admin_get_users(); st.dataframe(df_u)
            if not df_u.empty:
                uid = st.selectbox("Usuario", df_u['id'].tolist())
                if uid:
                    c1,c2 = st.columns(2)
                    rol_new = c1.selectbox("Nuevo Rol", ["user","analista","admin"])
                    if c1.button("Cambiar Rol"): admin_update_role(uid, rol_new); st.rerun()
                    if c2.button("Activar/Desactivar"): admin_toggle(uid, df_u[df_u['id']==uid]['activo'].values[0]); st.rerun()

    elif vista == "keys":
        st.title("Claves Pendientes")
        conn=get_connection(); req=pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", conn); conn.close()
        for _,r in req.iterrows():
            st.write(f"User: {r['username']}")
            if st.button(f"Reset {r['username']}", key=r['id']): admin_restablecer_password(r['id'], r['username']); st.rerun()
