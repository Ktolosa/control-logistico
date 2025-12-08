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
# ⚠️ URL BASE (Para el QR)
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
            fecha_nom = df_info.iloc[0]['fecha'].strftime('%Y-%m-%d')
            st.success(f"✅ POD {pod_code_nom} Encontrada ({len(df_items)} paq).")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_items.to_excel(writer, index=False, sheet_name='Paquetes')
            
            st.download_button(
                "📥 DESCARGAR EXCEL", output.getvalue(),
                f"POD_{pod_code_nom}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", use_container_width=True
            )
        else: st.error("❌ No encontrada.")
    except Exception as e: st.error(f"Error: {e}")
    
    st.markdown("---")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# --- ESTADO DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"
# Variables para persistencia de cámara/archivos
for key in ['last_pod_pdf', 'last_pod_name', 'last_pod_excel', 'last_pod_excel_name']:
    if key not in st.session_state: st.session_state[key] = None
# Buffer de escaneo para el modal de carga
if 'scan_buffer_modal' not in st.session_state: st.session_state['scan_buffer_modal'] = []

# --- 2. CSS RESPONSIVE (MÓVIL vs PC) ---
SIDEBAR_DESKTOP_WIDTH = "70px"

base_css = """
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeader"], footer { display: none !important; }
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
    [data-testid="collapsedControl"] {{ display: none !important; }}
    
    /* --- VISTA DE ESCRITORIO (PC) --- */
    @media (min-width: 768px) {{
        section[data-testid="stSidebar"] {{
            width: {SIDEBAR_DESKTOP_WIDTH} !important; min-width: {SIDEBAR_DESKTOP_WIDTH} !important;
            transform: none !important; visibility: visible !important;
            position: fixed !important; top: 0; left: 0; bottom: 0; z-index: 99999;
            background: #ffffff !important; border-right: 1px solid #e2e8f0; box-shadow: 4px 0 15px rgba(0,0,0,0.02);
        }}
        section[data-testid="stSidebar"] > div {{
            height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center;
        }}
        .main .block-container {{ margin-left: {SIDEBAR_DESKTOP_WIDTH}; width: calc(100% - {SIDEBAR_DESKTOP_WIDTH}); padding: 2rem; }}
        
        [data-testid="stSidebar"] div[role="radiogroup"] {{ flex-direction: column; gap: 15px; }}
        .nav-label {{ display: none; }} /* Ocultar texto en PC */
    }}

    /* --- VISTA MÓVIL (CELULAR) --- */
    @media (max-width: 767px) {{
        section[data-testid="stSidebar"] {{
            width: 100% !important; height: 65px !important; min-width: 100% !important;
            top: auto !important; bottom: 0 !important; left: 0 !important; right: 0 !important;
            display: flex !important; flex-direction: row !important;
            background: #ffffff !important; border-top: 1px solid #e2e8f0; z-index: 999999 !important;
            transform: none !important; transition: none !important;
            box-shadow: 0 -4px 10px rgba(0,0,0,0.05);
        }}
        section[data-testid="stSidebar"] > div {{
            flex-direction: row !important; justify-content: space-evenly !important; align-items: center !important;
            width: 100% !important; padding: 0 !important; height: 100% !important;
        }}
        
        /* Contenido principal con margen inferior para no tapar el menú */
        .main .block-container {{
            margin-left: 0 !important; width: 100% !important; max-width: 100% !important;
            padding: 1rem !important; padding-bottom: 100px !important; 
        }}
        
        /* Ajuste de iconos para móvil */
        [data-testid="stSidebar"] div[role="radiogroup"] {{ 
            flex-direction: row !important; width: 100%; justify-content: space-around; 
        }}
        
        .avatar-float, .logout-float {{ display: none !important; }}
    }}

    /* --- ESTILOS COMUNES --- */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex; justify-content: center; align-items: center;
        width: 45px; height: 45px; border-radius: 12px; cursor: pointer;
        background: transparent; color: #64748b; font-size: 24px; border: none; transition: 0.2s;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; color: #2563eb; box-shadow: 0 2px 8px rgba(37,99,235,0.2);
    }}
    
    .avatar-float {{ position: absolute; top: 20px; width: 40px; height: 40px; background: #f1f5f9; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; }}
    .logout-float {{ position: absolute; bottom: 20px; }}
    
    .kpi-card {{ background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; }}
    .kpi-val {{ font-size: 1.4rem; font-weight: 800; color: #0f172a; }}
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
        codes = [obj.data.decode('utf-8') for obj in decoded_objects]
        return codes
    except Exception: return []

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
            cur = conn.cursor()
            cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,)) 
            cur.execute("DELETE FROM registro_logistica WHERE id=%s", (id_reg,))
            conn.commit(); conn.close(); st.toast("🗑️ Eliminado"); return True
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
    if fmt == 'xlsx': 
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df.to_excel(w, index=False)
    else: 
        with pd.ExcelWriter(out, engine='xlwt') as w: df.to_excel(w, index=False)
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
    pdf.set_font("Arial",'',10); pdf.text(10,28,f"ID: {data.get('pod_code','N/A')}"); 
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

# --- MODAL GESTIÓN DE CARGA (AHORA CON ESCÁNER Y VALIDACIÓN) ---
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

    # --- FORMULARIO DE CARGA ---
    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha Llegada", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            # Campo de validación (Cantidad Esperada)
            esperados = st.number_input("Cantidad Esperada (Validación)", min_value=1, value=d_esp, disabled=disabled)
            pain = st.number_input("Total Paquetes (Manual)", 0, value=int(d_paq), disabled=disabled, help="Se actualizará si escaneas")

        st.markdown("---")
        st.write("📋 **Escaneo / Ingreso de Masters**")
        
        # --- SECCIÓN DE CÁMARA (NUEVO) ---
        col_cam, col_txt = st.columns([1,2])
        activar_cam = col_cam.toggle("📷 Escanear con Cámara")
        
        if activar_cam:
            img = st.camera_input("Apunta al código")
            if img:
                codes = decode_image(img)
                if codes:
                    st.success(f"Leído: {codes[0]}")
                    if codes[0] not in st.session_state['scan_buffer_modal']:
                        st.session_state['scan_buffer_modal'].append(codes[0])
                    else: st.warning("Ya escaneado")

        # Mostrar acumulado de escaneos
        if st.session_state['scan_buffer_modal']:
            st.info(f"En memoria: {len(st.session_state['scan_buffer_modal'])} códigos. (Se añadirán al texto)")
            if st.button("Limpiar Escaneos"): st.session_state['scan_buffer_modal'] = []; st.rerun()

        # Concatenar buffer de cámara con texto existente
        valor_actual = d_mast
        if st.session_state['scan_buffer_modal']:
            valor_actual += "\n" + "\n".join(st.session_state['scan_buffer_modal'])
            # Limpiar buffer para no duplicar en siguientes reruns
            # (Nota: en Streamlit form esto es truco, mejor dejar que el usuario edite el text area final)
        
        # AREA DE TEXTO FINAL (Editable)
        # Aquí el usuario ve lo escaneado y puede pegar masivamente
        masters_input = st.text_area("Masters (Uno por línea o espacios)", value=valor_actual, height=150, disabled=disabled)
        
        # --- VALIDACIÓN EN TIEMPO REAL ---
        # Limpieza
        lista_final = [m.strip() for m in re.split(r'[\n, ]+', masters_input) if m.strip()]
        conteo_real = len(lista_final)
        unicos = len(set(lista_final))
        
        c_v1, c_v2 = st.columns(2)
        c_v1.caption(f"Leídos: {conteo_real} | Únicos: {unicos}")
        
        # Alertas Visuales
        if conteo_real != unicos:
            st.markdown(f"<div class='count-err'>⚠️ ALERTA: Hay {conteo_real - unicos} códigos duplicados!</div>", unsafe_allow_html=True)
        
        if esperados > 0:
            if conteo_real == esperados:
                c_v2.markdown(f"<div class='count-ok'>✅ Cuadra Perfecto ({conteo_real}/{esperados})</div>", unsafe_allow_html=True)
            else:
                diff = conteo_real - esperados
                msg = f"Sobran {diff}" if diff > 0 else f"Faltan {abs(diff)}"
                c_v2.markdown(f"<div class='count-err'>❌ No cuadra ({msg})</div>", unsafe_allow_html=True)

        com = st.text_area("Notas", d_com, disabled=disabled)
        
        if not disabled:
            if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
                # Usar el conteo real escaneado como cantidad de paquetes si se desea auto-actualizar
                # Ojo: guardamos 'pain' (input manual) o 'conteo_real' (escaneado)? 
                # Generalmente en logistica el escaneo MANDA.
                paquetes_final = conteo_real if conteo_real > 0 else pain
                
                guardar_registro(d_id, fin, pin, clin, sin, masters_input, paquetes_final, com)
                st.session_state['scan_buffer_modal'] = [] # Limpiar memoria
                st.rerun()

    if d_id is not None and not disabled:
        st.markdown("---")
        with st.expander("🗑️ Eliminar Registro"):
            p_del = st.text_input("Clave Admin:", type="password")
            if st.button("Confirmar Borrado", type="secondary"):
                if eliminar_registro(d_id, p_del): st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    st.markdown("<br><h2 style='text-align: center;'>Nexus Logística</h2>", unsafe_allow_html=True)
    u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
    if st.button("ACCEDER"):
        user = verificar_login(u, p)
        if user: st.session_state['logged_in'] = True; st.session_state['user_info'] = user; st.rerun()
        else: st.error("Error credenciales")
else:
    u_info = st.session_state['user_info']; rol = u_info['rol']
    
    with st.sidebar:
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div class='avatar-float' title='{u_info['username']}'>{av}</div>", unsafe_allow_html=True)
        opts = ["📅", "📈", "📑", "📝", "⚙️"]
        if rol == 'admin': opts.extend(["👥", "🔑"])
        sel = st.radio("Menu", opts, label_visibility="collapsed")
        mapa = {"📅":"calendar","📈":"analytics","📑":"temu","📝":"pod","⚙️":"settings","👥":"users","🔑":"keys"}
        st.session_state['current_view'] = mapa.get(sel, "calendar")
        st.markdown("<div class='logout-float'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🚪"): st.session_state['logged_in'] = False; st.rerun()

    vista = st.session_state['current_view']
    df = cargar_datos()

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

    elif vista == "analytics":
        st.title("Analytics")
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
                st.dataframe(df_fil, use_container_width=True)

    elif vista == "temu":
        st.title("Gestor TEMU"); f = st.file_uploader("Excel", type=["xlsx","xls"])
        if f:
            res, df_sum, err = procesar_archivo_temu(f)
            if res:
                st.dataframe(df_sum)
                fmt = st.radio("Fmt", ["xlsx", "xls"], horizontal=True)
                ext = "xlsx" if fmt=="xlsx" else "xls"
                for m, d in res.items():
                    with st.expander(f"{m} ({d['info']['paquetes']})"):
                        st.download_button("Manifiesto", to_excel_bytes(d['main'],ext), f"{m}.{ext}")
                        st.download_button("Costos", to_excel_bytes(d['costos'],ext), f"{m}_Costos.{ext}")

    elif vista == "pod_digital":
        st.title("POD Digital")
        t1, t2 = st.tabs(["Nueva", "Historial"])
        with t1:
            with st.form("pod_form"):
                c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", ["Mail Americas","APG","IMILE"]); rut = c2.text_input("Ruta")
                c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",0)
                st.write("**Carga**")
                
                # --- CÁMARA POD ---
                act_cam_pod = st.toggle("Usar Cámara")
                if act_cam_pod:
                    img_pod = st.camera_input("Scan POD")
                    if img_pod:
                        res_pod = decode_image(img_pod)
                        if res_pod: st.success(f"Leído: {res_pod[0]}")
                        # Nota: En form la logica compleja de acumulacion es dificil, mejor textarea directo
                
                track_raw = st.text_area("Trackings")
                firma = st_canvas(fill_color="rgba(255, 165, 0, 0.3)", stroke_width=2, height=150)
                sub_pod = st.form_submit_button("Generar")
            
            if sub_pod:
                ts = [t.strip() for t in track_raw.split('\n') if t.strip()]
                if not rut or not ts: st.error("Datos faltantes")
                else:
                    d_pod = {"cliente":cli,"ruta":rut,"responsable":resp,"bultos":bult,"trackings":ts,"firma_img":firma if firma.image_data is not None else None}
                    uid, err = guardar_pod_digital(cli, rut, resp, len(ts), bult, ts, firma)
                    if uid:
                        st.success("Guardado")
                        st.session_state['last_pod_pdf'] = generar_pdf_pod(d_pod, uid)
                        st.session_state['last_pod_name'] = f"POD_{uid[:4]}.pdf"
                        st.rerun()
            
            if st.session_state['last_pod_pdf']:
                st.download_button("Descargar PDF", st.session_state['last_pod_pdf'], st.session_state['last_pod_name'])

        with t2:
            conn=get_connection(); df_p = pd.read_sql("SELECT * FROM pods ORDER BY fecha DESC LIMIT 20", conn); conn.close()
            st.dataframe(df_p)

    # ... (Resto de vistas Admin/Config igual)
