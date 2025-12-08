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
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas

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

# --- LÓGICA DE DESCARGA VÍA QR (INTERCEPTOR) ---
query_params = st.query_params
if "pod_uuid" in query_params:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    uuid_target = query_params["pod_uuid"]
    
    st.markdown("<br><br><h1 style='text-align:center;'>📦 Descarga de Paquetes POD</h1>", unsafe_allow_html=True)
    
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
        )
        q = "SELECT tracking FROM pod_items WHERE pod_uuid = %s"
        df_items = pd.read_sql(q, conn, params=(uuid_target,))
        
        q_info = "SELECT cliente, fecha FROM pods WHERE uuid = %s"
        df_info = pd.read_sql(q_info, conn, params=(uuid_target,))
        conn.close()
        
        if not df_items.empty:
            cliente_nom = df_info.iloc[0]['cliente']
            fecha_nom = df_info.iloc[0]['fecha'].strftime('%Y-%m-%d')
            
            st.success(f"✅ POD Encontrada: {len(df_items)} paquetes.")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_items.to_excel(writer, index=False, sheet_name='Paquetes')
                worksheet = writer.sheets['Paquetes']
                worksheet.set_column('A:A', 30)
            
            st.download_button(
                label="📥 DESCARGAR EXCEL DE TRACKINGS",
                data=output.getvalue(),
                file_name=f"Listado_POD_{cliente_nom}_{fecha_nom}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        else:
            st.error("❌ POD no encontrada.")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.markdown("---")
    if st.button("Ir al Inicio"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# --- ESTADO NORMAL DE LA APP ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"

# --- CORRECCIÓN VARIABLES ---
if 'last_pod_pdf' not in st.session_state: st.session_state['last_pod_pdf'] = None
if 'last_pod_name' not in st.session_state: st.session_state['last_pod_name'] = None
if 'last_pod_excel' not in st.session_state: st.session_state['last_pod_excel'] = None
if 'last_pod_excel_name' not in st.session_state: st.session_state['last_pod_excel_name'] = None

# --- 2. CSS ---
SIDEBAR_WIDTH = "60px"

base_css = """
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    footer { display: none !important; }
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
    section[data-testid="stSidebar"] {{
        display: block !important; width: {SIDEBAR_WIDTH} !important; min-width: {SIDEBAR_WIDTH} !important;
        max-width: {SIDEBAR_WIDTH} !important; transform: none !important; visibility: visible !important;
        position: fixed !important; top: 0 !important; left: 0 !important; bottom: 0 !important; z-index: 99999;
        background-color: #ffffff !important; border-right: 1px solid #f1f5f9; box-shadow: 4px 0 20px rgba(0,0,0,0.03);
    }}
    section[data-testid="stSidebar"] > div {{
        height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-top: 0px !important; 
    }}
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH} !important; width: calc(100% - {SIDEBAR_WIDTH}) !important;
        padding: 2rem !important; max-width: 100% !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important; justify-content: center !important; align-items: center !important;
        width: 42px !important; height: 42px !important; border-radius: 12px !important; cursor: pointer;
        background: transparent; color: #64748b; font-size: 22px !important; border: 1px solid transparent; transition: all 0.2s; margin: 0 !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: #f1f5f9; color: #0f172a; transform: scale(1.1); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; color: #2563eb; border: 1px solid #dbeafe; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.15);
    }}
    .avatar-float {{ position: absolute; top: 20px; left: 0; right: 0; margin: auto; width: 35px; height: 35px; background: #f8fafc; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid #e2e8f0; font-size: 18px; color: #334155; }}
    .logout-float {{ position: absolute; bottom: 20px; left: 0; right: 0; margin: auto; text-align: center; }}
    .kpi-card {{ background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; }}
    .kpi-lbl {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 700; }}
    .kpi-val {{ font-size: 1.5rem; color: #0f172a; font-weight: 800; }}
    .count-ok {{ color: #16a34a; font-weight: bold; font-size: 0.9rem; }}
    .count-err {{ color: #dc2626; font-weight: bold; font-size: 0.9rem; }}
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

# --- CREACIÓN TABLAS POD ---
try:
    conn_tmp = get_connection()
    if conn_tmp:
        cur = conn_tmp.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS pods (id INT AUTO_INCREMENT PRIMARY KEY, uuid VARCHAR(50), fecha DATETIME, cliente VARCHAR(50), ruta VARCHAR(100), responsable VARCHAR(100), paquetes_declarados INT, paquetes_reales INT, bultos INT, signature_blob LONGBLOB, created_by VARCHAR(50))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS pod_items (id INT AUTO_INCREMENT PRIMARY KEY, pod_uuid VARCHAR(50), tracking VARCHAR(100), INDEX (pod_uuid))""")
        conn_tmp.commit()
        conn_tmp.close()
except: pass

# --- FUNCIONES LÓGICAS ---
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
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE rol='admin' AND activo=1 AND password=%s", (password,))
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
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
            def contar(t):
                if not t: return 0
                return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()])
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
                st.toast("✅ Guardado Exitosamente")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, id_reg))
                cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,))
                st.toast("✅ Registro Actualizado")
            if lista_masters:
                vals = [(registro_id, m, fecha) for m in lista_masters]
                cur.executemany("INSERT INTO masters_detalle (registro_id, master_code, fecha_registro) VALUES (%s, %s, %s)", vals)
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error BD: {e}")

def eliminar_registro(id_reg, admin_pass):
    if not validar_admin_pass(admin_pass):
        st.error("🔒 Clave incorrecta.")
        return False
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,)) 
            cur.execute("DELETE FROM registro_logistica WHERE id=%s", (id_reg,))
            conn.commit(); conn.close()
            st.toast("🗑️ Eliminado"); return True
        except Exception as e: st.error(str(e)); return False
    return False

# --- LOGICA TEMU MANAGER ---
def procesar_archivo_temu(uploaded_file):
    try:
        df_raw = pd.read_excel(uploaded_file, header=None).fillna("")
        data_rows = df_raw.iloc[1:]
        data_rows = data_rows[data_rows[3].astype(str).str.strip() != ""]
        if data_rows.empty: return None, None, "No se encontraron datos en columna Master (D)."

        grouped = data_rows.groupby(3)
        resultados = {}
        resumen_list = []

        headers_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        headers_costos = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]

        for master, group in grouped:
            rows_main = []
            for _, row in group.iterrows():
                r = [""] * 21
                r[0]=str(row[7]).strip(); r[4]=str(row[10]).strip(); r[6]=str(row[14]).strip(); r[7]=str(row[11]).strip();
                r[8]=str(row[12]).strip(); r[9]=str(row[13]).strip(); r[10]=str(row[16]).strip(); r[11]=str(row[17]).strip();
                r[12]=str(row[15]).strip(); r[13]=str(row[3]).strip(); r[19]=str(row[5]).strip();
                r[1]="YC - Log. for Temu"; r[2]="Zhaoqing"; r[3]="CN"; r[5]="SLV"; r[18]="USD";
                r[14]="1"; r[15]="0.45"; r[16]="0.01"; r[17]="N/A"; r[20]="N/A";
                rows_main.append(r)
            rows_costos = []
            for _, row in group.iterrows():
                c = [""] * 16
                c[0]=str(row[7]).strip(); c[2]=str(row[10]).strip(); c[3]=str(row[15]).strip(); c[5]=str(row[5]).strip();
                c[7]="0.00"; c[8]="0.01"; c[9]="0.01"; c[10]="0.00"; c[11]="0.00"; c[12]="0.00"; c[13]="0.00"; c[14]="0.00"; c[15]="0.01";
                rows_costos.append(c)
            paquetes = len(group); cajas = group[5].nunique()
            resultados[master] = {"main": pd.DataFrame(rows_main, columns=headers_main), "costos": pd.DataFrame(rows_costos, columns=headers_costos), "info": {"paquetes": paquetes, "cajas": cajas}}
            resumen_list.append({"Master": master, "Cajas": cajas, "Paquetes": paquetes})
        df_resumen = pd.DataFrame(resumen_list)
        return resultados, df_resumen, None
    except Exception as e: return None, None, str(e)

def to_excel_bytes(df, fmt='xlsx'):
    output = io.BytesIO()
    if fmt == 'xlsx':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name='Sheet1')
    else:
        with pd.ExcelWriter(output, engine='xlwt') as writer: df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- FUNCIONES POD DIGITAL ---
def guardar_pod_digital(cliente, ruta, responsable, paq_dec, bultos, trackings, firma_img_data):
    conn = get_connection()
    if not conn: return None, "Error BD"
    try:
        cur = conn.cursor()
        pod_uuid = str(uuid.uuid4())
        fecha_now = datetime.now()
        sql_pod = "INSERT INTO pods (uuid, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        cur.execute(sql_pod, (pod_uuid, fecha_now, cliente, ruta, responsable, paq_dec, len(trackings), bultos, None, st.session_state['user_info']['username']))
        if trackings:
            items_data = [(pod_uuid, t) for t in trackings]
            cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", items_data)
        conn.commit(); conn.close()
        return pod_uuid, None
    except Exception as e: return None, str(e)

def generar_pdf_pod(data, pod_uuid):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. ENCABEZADO
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 24)
    pdf.text(10, 18, "MANIFIESTO / POD")
    pdf.set_font("Arial", '', 10)
    pdf.text(10, 28, f"ID: {pod_uuid}")
    pdf.text(10, 34, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # QR (CORREGIDO: RECTÁNGULO NORMAL PARA EVITAR ERROR)
    qr_data = f"{APP_BASE_URL}/?pod_uuid={pod_uuid}"
    qr = qrcode.make(qr_data)
    qr.save(f"qr_{pod_uuid}.png")
    pdf.set_fill_color(255, 255, 255)
    
    # CAMBIO AQUÍ: Usar rect() normal en lugar de rounded_rect()
    pdf.rect(170, 5, 30, 30, 'F') 
    
    pdf.image(f"qr_{pod_uuid}.png", 172, 7, 26, 26)
    
    # 2. INFORMACIÓN
    pdf.set_y(50)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 8, "CLIENTE:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(70, 8, data['cliente'], 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(35, 8, "RESPONSABLE:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(60, 8, data['responsable'], 0, 1)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 8, "RUTA:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(165, 8, data['ruta'], 0, 1)
    
    pdf.ln(5)
    
    # 3. TABLA
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(65, 10, "PAQUETES REALES", 1, 0, 'C', 1)
    pdf.cell(65, 10, "BULTOS / SACOS", 1, 0, 'C', 1)
    pdf.cell(60, 10, "ESTADO", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", '', 14)
    pdf.cell(65, 15, str(len(data['trackings'])), 1, 0, 'C')
    pdf.cell(65, 15, str(data['bultos']), 1, 0, 'C')
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(22, 163, 74)
    pdf.cell(60, 15, "ENTREGADO", 1, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(10)
    
    # 4. FIRMAS
    y_firmas = pdf.get_y()
    pdf.set_font("Arial", 'B', 10)
    pdf.text(10, y_firmas, "ENTREGADO POR (FIRMA DIGITAL):")
    
    if data['firma_img'] is not None:
        from PIL import Image
        img_data = data['firma_img'].image_data
        im = Image.fromarray(img_data.astype('uint8'), mode='RGBA')
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        bg.save("temp_sig.png")
        pdf.image("temp_sig.png", 10, y_firmas + 5, 80, 40)
        pdf.rect(10, y_firmas + 5, 80, 40)
    else:
        pdf.rect(10, y_firmas + 5, 80, 40)
        pdf.text(20, y_firmas + 25, "(Sin Firma Digital)")

    pdf.text(110, y_firmas, "RECIBIDO POR:")
    pdf.rect(110, y_firmas + 5, 80, 40)
    
    pdf.ln(50)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, "Documento generado digitalmente por Nexus Logistica.", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIONES ADMIN ---
def admin_crear_usuario(u, r):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
            conn.commit()
            conn.close()
            return True
        except:
            pass
    return False

def admin_get_users():
    conn = get_connection()
    if conn:
        df = pd.read_sql("SELECT id, username, rol, activo FROM usuarios", conn)
        conn.close()
        return df
    return pd.DataFrame()

def admin_toggle(uid, curr):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        new_status = 0 if curr == 1 else 1
        cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new_status, uid))
        conn.commit()
        conn.close()

def admin_update_role(uid, new_role):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET rol=%s WHERE id=%s", (new_role, uid))
            conn.commit()
            conn.close()
            return True
        except:
            pass
    return False

def admin_restablecer_password(rid, uname):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,))
        cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,))
        conn.commit()
        conn.close()

def solicitar_reset_pass(username):
    conn = get_connection()
    if not conn: return "error"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
        if cur.fetchone():
            cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
            conn.commit(); conn.close(); return "ok"
        conn.close(); return "no_user"
    except: return "error"

def cambiar_password(uid, np):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET password=%s WHERE id=%s", (np, uid))
            conn.commit()
            conn.close()
            return True
        except: pass
    return False

# --- 4. MODAL ---
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
        d_serv = datos.get('servicio', SERVICIOS[0])
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")
        d_esp = len([x for x in re.split(r'[\n, ]+', d_mast) if x.strip()]) or 1
    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha Llegada", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            pain = st.number_input("Total Paquetes", 0, value=int(d_paq), disabled=disabled)
            esperados = st.number_input("Masters Esperadas", min_value=1, value=d_esp, disabled=disabled)
        st.markdown("---")
        st.write("📋 **Masters (Pegar Bloque)**")
        min_ = st.text_area("Códigos separados por espacio/enter", d_mast, height=100, disabled=disabled)
        lista_masters = [m for m in re.split(r'[\n, ]+', min_) if m.strip()]
        conteo_actual = len(lista_masters)
        col_val1, col_val2 = st.columns(2)
        col_val1.caption(f"Detectadas: {conteo_actual}")
        if conteo_actual == esperados: col_val2.markdown(f"<span class='count-ok'>✅ Cuadra</span>", unsafe_allow_html=True)
        else: col_val2.markdown(f"<span class='count-err'>⚠️ Diferencia: {conteo_actual - esperados}</span>", unsafe_allow_html=True)
        com = st.text_area("Notas", d_com, disabled=disabled)
        if not disabled:
            if st.form_submit_button("💾 Guardar / Actualizar", type="primary", use_container_width=True):
                guardar_registro(d_id, fin, pin, clin, sin, min_, pain, com)
                st.rerun()
    if d_id is not None and not disabled:
        st.markdown("---")
        with st.expander("🗑️ Eliminar este Registro"):
            st.warning("Esta acción es irreversible.")
            del_pass = st.text_input("Ingresa contraseña de Administrador:", type="password")
            if st.button("Confirmar Eliminación", type="secondary"):
                if eliminar_registro(d_id, del_pass): st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #1e293b;'>Nexus Logística</h2>", unsafe_allow_html=True)
    u = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
    st.write("")
    p = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
    st.write("")
    if st.button("ACCEDER"):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Credenciales inválidas")
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Recuperar contraseña"):
        ur = st.text_input("Usuario")
        if st.button("Solicitar Reset"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Enviado.")
            else: st.warning("Error.")

else:
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    with st.sidebar:
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div class='avatar-float' title='{u_info['username']}'>{av}</div>", unsafe_allow_html=True)
        
        opciones = ["📅", "📈", "📑", "📝", "⚙️"] 
        if rol == 'admin': opciones.extend(["👥", "🔑"])
        
        seleccion = st.radio("Menu", opciones, label_visibility="collapsed")
        
        mapa = {
            "📅": "calendar", 
            "📈": "analytics_pro", 
            "📑": "temu_manager", 
            "📝": "pod_digital",
            "⚙️": "user_settings", 
            "👥": "admin_users", 
            "🔑": "admin_reqs"
        }
        st.session_state['current_view'] = mapa.get(seleccion, "calendar")

        st.markdown("<div class='logout-float'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🚪", help="Salir"):
            st.session_state['logged_in'] = False
            st.rerun()

    vista = st.session_state['current_view']
    df = cargar_datos()

    if vista == "calendar":
        c1, c2 = st.columns([6, 1])
        c1.title("Calendario Operativo")
        if rol != 'analista':
            if c2.button("➕ Nuevo", type="primary"): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                color = "#3b82f6" 
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316"
                elif "Temu" in r['plataforma_cliente']: color = "#10b981"
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"📦{int(r['paquetes'])} | 🔑{r['conteo_masters_real']}", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif vista == "analytics_pro":
        st.title("Analytics & Reportes")
        if df.empty:
            st.warning("Sin datos.")
        else:
            with st.container(border=True):
                c_search, c_date = st.columns([1, 2])
                search_master = c_search.text_input("🔍 Buscar Master Exacta", placeholder="Escribe el código...")
                min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
                rango = c_date.date_input("Rango", [min_d, max_d])
            df_fil = df.copy()
            if search_master:
                conn = get_connection()
                try:
                    q = f"SELECT registro_id, fecha_registro FROM masters_detalle WHERE master_code LIKE '%{search_master}%'"
                    df_masters_found = pd.read_sql(q, conn)
                    conn.close()
                    if not df_masters_found.empty:
                        df_fil = df_fil[df_fil['id'].isin(df_masters_found['registro_id'].unique())]
                        st.success(f"✅ Encontrada en {len(df_fil)} viaje(s).")
                        st.dataframe(df_masters_found[['master_code', 'fecha_registro']], hide_index=True)
                    else:
                        st.error("❌ No encontrada.")
                        df_fil = pd.DataFrame()
                except: pass
            elif len(rango) == 2:
                df_fil = df_fil[(df_fil['fecha'].dt.date >= rango[0]) & (df_fil['fecha'].dt.date <= rango[1])]
            st.divider()
            if not df_fil.empty:
                k1, k2, k3, k4 = st.columns(4)
                k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Paquetes</div><div class='kpi-val'>{df_fil['paquetes'].sum():,.0f}</div></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Masters Reales</div><div class='kpi-val'>{df_fil['conteo_masters_real'].sum():,.0f}</div></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Viajes</div><div class='kpi-val'>{len(df_fil)}</div></div>", unsafe_allow_html=True)
                k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio</div><div class='kpi-val'>{df_fil['paquetes'].mean():,.0f}</div></div>", unsafe_allow_html=True)
                st.write("")
                tab1, tab2, tab3 = st.tabs(["📅 Resumen Semanal", "📊 Gráficos", "📥 Matriz"])
                with tab1:
                    st.subheader("Resumen Semanal de Operaciones")
                    resumen = df_fil.groupby(['Año', 'Semana', 'Mes']).agg(
                        Paquetes=('paquetes', 'sum'), Masters=('conteo_masters_real', 'sum'), Viajes=('id', 'count')
                    ).reset_index()
                    def get_week_dates(year, week):
                        d = date.fromisocalendar(year, week, 1); return f"{d.strftime('%d-%b')} al {(d + timedelta(days=6)).strftime('%d-%b')}"
                    resumen['Rango'] = resumen.apply(lambda x: get_week_dates(x['Año'], x['Semana']), axis=1)
                    resumen = resumen[['Año', 'Semana', 'Mes', 'Rango', 'Viajes', 'Masters', 'Paquetes']]
                    st.dataframe(resumen, use_container_width=True, hide_index=True)
                with tab2:
                    g1, g2 = st.columns(2)
                    with g1: st.plotly_chart(px.bar(df_fil.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes'), use_container_width=True)
                    with g2: st.plotly_chart(px.pie(df_fil, names='proveedor_logistico', values='paquetes', hole=0.5), use_container_width=True)
                with tab3:
                    st.dataframe(df_fil, use_container_width=True)
                    csv = df_fil.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "reporte.csv", "text/csv")

    elif vista == "temu_manager":
        st.title("Gestor TEMU | Multi-Formato")
        with st.container(border=True):
            f_temu = st.file_uploader("Cargar Archivo de DATOS (.xlsx, .xls)", type=["xlsx", "xls"])
            if f_temu:
                resultados, df_resumen, error = procesar_archivo_temu(f_temu)
                if error: st.error(f"Error: {error}")
                elif resultados:
                    st.subheader("📋 Resumen"); st.dataframe(df_resumen, hide_index=True, use_container_width=False)
                    st.divider(); st.subheader("📁 Descargas")
                    fmt = st.radio("Formato:", ["Excel Moderno (.xlsx)", "Excel 97-2003 (.xls)"], horizontal=True)
                    ext = "xlsx" if "Moderno" in fmt else "xls"
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if ext == "xlsx" else "application/vnd.ms-excel"
                    for master, data in resultados.items():
                        with st.expander(f"📦 Master: {master} ({data['info']['paquetes']} paq)", expanded=False):
                            search_q = st.text_input(f"🔍 Buscar en {master}", key=f"s_{master}")
                            c1, c2 = st.columns(2)
                            c1.download_button(f"📥 Manifiesto", to_excel_bytes(data["main"], ext), f"{master}.{ext}", mime, key=f"bm_{master}")
                            c2.download_button(f"💲 Costos", to_excel_bytes(data["costos"], ext), f"{master}_Costos.{ext}", mime, key=f"bc_{master}")
                            df_disp = data["main"]
                            if search_q: df_disp = df_disp[df_disp.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)]
                            st.dataframe(df_disp, hide_index=True)

    # --- NUEVA VISTA: POD DIGITAL ---
    elif vista == "pod_digital":
        st.title("📝 POD Digital")
        
        tab_new, tab_hist = st.tabs(["Nueva POD", "Historial"])
        
        with tab_new:
            with st.form("form_pod"):
                st.subheader("1. Cliente y Ruta")
                c1, c2 = st.columns(2)
                cliente = c1.selectbox("Cliente", ["Mail Americas", "APG", "IMILE"])
                ruta = c2.text_input("Nombre Ruta / Referencia", placeholder="Ej: Ruta Norte")
                c3, c4, c5 = st.columns(3)
                responsable = c3.text_input("Responsable Entrega")
                paq_dec = c4.number_input("Paquetes Declarados", min_value=1, step=1)
                bultos = c5.number_input("Bultos (Sacos)", min_value=0, step=1)
                st.subheader("2. Carga (Escaneo)")
                trackings_raw = st.text_area("Escanea los códigos aquí (uno por línea)", height=150)
                st.subheader("3. Firma Digital")
                firma_canvas = st_canvas(fill_color="rgba(255, 165, 0, 0.3)", stroke_width=2, stroke_color="#000000", background_color="#ffffff", height=150, width=600, drawing_mode="freedraw", key="canvas_firma")
                submitted = st.form_submit_button("💾 GUARDAR Y GENERAR POD", type="primary")

            if submitted:
                trackings_list = [t.strip() for t in trackings_raw.split('\n') if t.strip()]
                if not responsable or not ruta: st.error("Faltan datos obligatorios.")
                elif len(trackings_list) == 0: st.error("No hay trackings escaneados.")
                else:
                    data_pod = {"cliente": cliente, "ruta": ruta, "responsable": responsable, "bultos": bultos, "trackings": trackings_list, "firma_img": firma_canvas if firma_canvas.image_data is not None else None}
                    uuid_pod, error = guardar_pod_digital(cliente, ruta, responsable, paq_dec, bultos, trackings_list, firma_canvas)
                    if uuid_pod:
                        st.success("✅ POD Guardada con éxito.")
                        pdf_bytes = generar_pdf_pod(data_pod, uuid_pod)
                        st.session_state['last_pod_pdf'] = pdf_bytes
                        st.session_state['last_pod_name'] = f"POD_{cliente}_{date.today()}.pdf"
                        df_excel = pd.DataFrame(trackings_list, columns=["Tracking"])
                        st.session_state['last_pod_excel'] = to_excel_bytes(df_excel, 'xlsx')
                        st.session_state['last_pod_excel_name'] = f"Listado_{cliente}_{date.today()}.xlsx"
                    else: st.error(f"Error al guardar: {error}")

            if 'last_pod_pdf' in st.session_state and st.session_state['last_pod_pdf'] is not None:
                c_pdf, c_xls = st.columns(2)
                c_pdf.download_button(label="📥 DESCARGAR PDF CON QR", data=st.session_state['last_pod_pdf'], file_name=st.session_state['last_pod_name'], mime="application/pdf", type="primary")
                if 'last_pod_excel' in st.session_state and st.session_state['last_pod_excel'] is not None:
                    c_xls.download_button(label="📊 DESCARGAR EXCEL", data=st.session_state['last_pod_excel'], file_name=st.session_state['last_pod_excel_name'], mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with tab_hist:
            st.subheader("Historial de PODs Generadas")
            conn = get_connection()
            if conn:
                df_pods = pd.read_sql("SELECT uuid, fecha, cliente, ruta, responsable, paquetes_reales FROM pods ORDER BY fecha DESC LIMIT 50", conn)
                conn.close()
                st.dataframe(df_pods, use_container_width=True)
            else: st.error("Error de conexión.")

    elif vista == "user_settings":
        st.title("Configuración")
        with st.container(border=True):
            st.subheader("Cambiar Contraseña")
            p1 = st.text_input("Nueva", type="password")
            p2 = st.text_input("Confirmar", type="password")
            if st.button("Actualizar", type="primary"):
                if p1 and p1==p2:
                    if cambiar_password(u_info['id'], p1): st.success("OK")
                    else: st.error("Error")
                else: st.warning("No coinciden")

    elif vista == "admin_users":
        st.title("Usuarios")
        t1, t2 = st.tabs(["Crear", "Lista"])
        with t1:
            with st.form("new_u"):
                nu = st.text_input("User"); nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"): 
                    if admin_crear_usuario(nu, nr): st.success("Creado")
        with t2:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            if not df_u.empty:
                c1, c2, c3 = st.columns(3)
                uid = c1.selectbox("Seleccionar Usuario", df_u['id'].tolist())
                if uid:
                    current_user_data = df_u[df_u['id'] == uid].iloc[0]
                    current_role = current_user_data['rol']
                    current_active = current_user_data['activo']
                    new_role = c2.selectbox("Cambiar Rol", ["user", "analista", "admin"], index=["user", "analista", "admin"].index(current_role))
                    if c2.button("💾 Actualizar Rol"):
                        if admin_update_role(uid, new_role): st.success("Rol actualizado"); st.rerun()
                        else: st.error("Error")
                    btn_lbl = "🔴 Desactivar" if current_active == 1 else "🟢 Reactivar"
                    if c3.button(btn_lbl):
                        admin_toggle(uid, current_active); st.rerun()

    elif vista == "admin_reqs":
        st.title("Claves")
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
        if reqs.empty: st.success("Limpio")
        else:
            for _, r in reqs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"{r['username']}")
                if c2.button("Reset", key=r['id']): admin_restablecer_password(r['id'], r['username']); st.rerun()
