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

# ==============================================================================
# 1. CONFIGURACIÓN Y CONSTANTES
# ==============================================================================
st.set_page_config(page_title="Nexus Logística", layout="wide", initial_sidebar_state="collapsed")

APP_BASE_URL = "https://control-logistico-ifjfvph3s8ybga46f5bdfb.streamlit.app"
AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

# ==============================================================================
# 2. UTILIDADES (BASE DE DATOS, CSS, IMAGENES)
# ==============================================================================

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
        )
    except: return None

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
    if fmt == 'xlsx':
        with pd.ExcelWriter(out, engine='xlsxwriter') as w: df.to_excel(w, index=False, sheet_name='Sheet1')
    else:
        with pd.ExcelWriter(out, engine='xlwt') as w: df.to_excel(w, index=False, sheet_name='Sheet1')
    return out.getvalue()

# --- CSS MEJORADO PARA MOVIL ---
st.markdown("""
<style>
    /* Ocultar elementos nativos */
    [data-testid="stSidebarNav"], [data-testid="stToolbar"], footer { display: none !important; }
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
    
    /* Botones Menú Principal (Tarjetas) */
    .menu-btn {
        width: 100%; height: 100px !important;
        border: 1px solid #e2e8f0; border-radius: 15px;
        background-color: white; color: #1e293b;
        font-size: 18px; font-weight: 600;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.2s;
        margin-bottom: 15px;
    }
    .menu-btn:hover { transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); border-color: #3b82f6; }
    
    /* Botón Volver */
    div.stButton > button:first-child { width: 100%; border-radius: 10px; font-weight: 600; }
    
    /* KPIs */
    .kpi-card { background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; }
    .kpi-val { font-size: 1.4rem; font-weight: 800; color: #0f172a; }
    
    /* Alertas */
    .count-ok { color: #16a34a; font-weight: bold; background:#dcfce7; padding:4px 8px; border-radius:6px; }
    .count-err { color: #dc2626; font-weight: bold; background:#fee2e2; padding:4px 8px; border-radius:6px; }
    
    /* Sidebar solo info usuario */
    section[data-testid="stSidebar"] { width: 250px !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. INTERCEPTOR QR
# ==============================================================================
qp = st.query_params
if "pod_uuid" in qp:
    st.set_page_config(layout="centered", page_title="Descarga POD")
    uuid_target = qp["pod_uuid"]
    st.markdown("<br><h2 style='text-align:center;'>📦 Descarga POD</h2>", unsafe_allow_html=True)
    try:
        conn = get_connection()
        q = "SELECT tracking FROM pod_items WHERE pod_uuid = %s"
        df_items = pd.read_sql(q, conn, params=(uuid_target,))
        q_info = "SELECT cliente, fecha, pod_code FROM pods WHERE uuid = %s"
        df_info = pd.read_sql(q_info, conn, params=(uuid_target,))
        conn.close()
        
        if not df_items.empty:
            c_nom = df_info.iloc[0]['cliente']
            p_code = df_info.iloc[0]['pod_code']
            st.success(f"✅ POD {p_code} Encontrada ({len(df_items)} paq).")
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_items.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), f"POD_{p_code}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
        else: st.error("❌ No encontrada.")
    except Exception as e: st.error(f"Error: {e}")
    st.markdown("---")
    if st.button("Ir al Inicio"): st.query_params.clear(); st.rerun()
    st.stop()

# ==============================================================================
# 4. LÓGICA DE NEGOCIO (FUNCIONES DE LAS HERRAMIENTAS)
# ==============================================================================

# --- AUTH ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

def cambiar_password(uid, np):
    conn = get_connection()
    if conn:
        try: conn.cursor().execute("UPDATE usuarios SET password=%s WHERE id=%s", (np, uid)); conn.commit(); conn.close(); return True
        except: pass
    return False

# --- CALENDARIO / DB ---
def cargar_datos_cal():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            df['Año'] = df['fecha'].dt.year; df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            def contar(t): return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()]) if t else 0
            df['conteo_masters_real'] = df['master_lote'].apply(contar)
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast_str, paq, com, user):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            lista_masters = [m.strip() for m in re.split(r'[\n, ]+', mast_str) if m.strip()]
            clean_masters_str = " ".join(lista_masters)
            if id_reg is None:
                sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, user))
                id_reg = cur.lastrowid
                st.toast("✅ Guardado")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, id_reg))
                cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,))
                st.toast("✅ Actualizado")
            if lista_masters:
                vals = [(id_reg, m, fecha) for m in lista_masters]
                cur.executemany("INSERT INTO masters_detalle (registro_id, master_code, fecha_registro) VALUES (%s, %s, %s)", vals)
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error BD: {e}")

# --- TEMU ---
def procesar_temu(f):
    try:
        df_raw = pd.read_excel(f, header=None).fillna("")
        data_rows = df_raw.iloc[1:]
        data_rows = data_rows[data_rows[3].astype(str).str.strip() != ""]
        if data_rows.empty: return None, None, "Sin datos"
        grouped = data_rows.groupby(3)
        res = {}; sum_list = []
        h_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        h_cost = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]
        for m, g in grouped:
            rm=[]; rc=[]
            for _, r in g.iterrows():
                row=[""]*21; row[0]=str(r[7]).strip(); row[4]=str(r[10]).strip(); row[6]=str(r[14]).strip(); row[13]=str(r[3]).strip(); row[19]=str(r[5]).strip(); row[1]="YC - Log. for Temu"; rm.append(row)
                cos=[""]*16; cos[0]=str(r[7]).strip(); cos[5]=str(r[5]).strip(); rc.append(cos)
            res[m] = {"main": pd.DataFrame(rm,columns=h_main), "costos": pd.DataFrame(rc,columns=h_cost), "info": {"p": len(g)}}
            sum_list.append({"Master": m, "Paquetes": len(g)})
        return res, pd.DataFrame(sum_list), None
    except Exception as e: return None, None, str(e)

# --- POD DIGITAL ---
def guardar_pod(cli, rut, res, dec, bul, trks, firm, user):
    conn = get_connection(); 
    if not conn: return None, "Error BD"
    try:
        cur = conn.cursor(); uid = str(uuid.uuid4()); code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=10)); now = datetime.now()
        blob = None
        if firm.image_data is not None:
            im = Image.fromarray(firm.image_data.astype('uint8'), 'RGBA'); buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        cur.execute("INSERT INTO pods (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (uid, code, now, cli, rut, res, dec, len(trks), bul, blob, user))
        if trks: cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", [(uid, t) for t in trks])
        conn.commit(); conn.close(); return uid, None
    except Exception as e: return None, str(e)

def generar_pdf(data, uid, hist=False):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(37,99,235); pdf.rect(0,0,210,40,'F')
    pdf.set_text_color(255); pdf.set_font("Arial",'B',24); pdf.text(10,18,"MANIFIESTO / POD")
    pdf.set_font("Arial",'',10); pdf.text(10,28,f"ID: {data.get('pod_code','N/A')}")
    qr = qrcode.make(f"{APP_BASE_URL}/?pod_uuid={uid}"); qr.save("qr.png")
    pdf.image("qr.png",172,7,26,26); pdf.set_text_color(0)
    pdf.set_y(50); pdf.set_font("Arial",'B',11); pdf.cell(40,10,f"Cliente: {data['cliente']}",0,1)
    pdf.cell(40,10,f"Ruta: {data['ruta']}",0,1)
    pdf.cell(40,10,f"Paquetes: {len(data['trackings'])}",0,1)
    # Firma
    y = pdf.get_y()+10; pdf.text(10,y,"FIRMA:"); pdf.rect(10,y+5,80,40)
    try:
        if hist and data['firma_bytes']:
            with open("s.png","wb") as f: f.write(data['firma_bytes'])
            pdf.image("s.png",10,y+5,80,40)
        elif data.get('firma_img') is not None:
            im=Image.fromarray(data['firma_img'].image_data.astype('uint8'),'RGBA'); im.save("s.png"); pdf.image("s.png",10,y+5,80,40)
    except: pass
    return pdf.output(dest='S').encode('latin-1')

def recuperar_pod(uid):
    conn = get_connection()
    if not conn: return None
    try:
        dfh = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if dfh.empty: return None
        dfi = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        r = dfh.iloc[0]
        return {"uuid": r['uuid'], "pod_code": r.get('pod_code','N/A'), "cliente": r['cliente'], "ruta": r['ruta'], "responsable": r['responsable'], "bultos": r['bultos'], "trackings": dfi['tracking'].tolist(), "firma_bytes": r['signature_blob']}
    except: return None

# --- ADMIN ---
def admin_user(u, r):
    conn = get_connection()
    try: conn.cursor().execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r)); conn.commit(); conn.close(); return True
    except: return False

@st.dialog("Carga")
def modal_reg(datos, user):
    rol = st.session_state['user_info']['rol']
    dis = (rol=='analista')
    df, dp, dc = date.today(), PROVEEDORES[0], PLATAFORMAS[0]
    ds, dm, dpq, dcm = SERVICIOS[0], "", 0, ""
    did = None
    if datos:
        did=datos['id']; df=datetime.strptime(datos['fecha_str'],'%Y-%m-%d').date()
        if datos['proveedor'] in PROVEEDORES: dp=datos['proveedor']
        if datos['plataforma'] in PLATAFORMAS: dc=datos['plataforma']
        ds=datos['servicio']; dm=datos['master']; dpq=datos['paquetes']; dcm=datos['comentarios']

    st.write("**Escaneo**")
    if st.toggle("Cámara"):
        img = st.camera_input("Scan")
        if img:
            c = decode_image(img)
            if c and c[0] not in st.session_state.get('scan_buf', []):
                st.session_state.setdefault('scan_buf', []).append(c[0])
                st.success(c[0])
    
    if st.session_state.get('scan_buf'):
        if st.button("Limpiar"): st.session_state['scan_buf'] = []; st.rerun()
        dm += "\n" + "\n".join(st.session_state['scan_buf'])

    with st.form("f"):
        c1, c2 = st.columns(2)
        fin = c1.date_input("Fecha", df, disabled=dis)
        pin = c1.selectbox("Prov", PROVEEDORES, index=PROVEEDORES.index(dp), disabled=dis)
        clin = c2.selectbox("Cli", PLATAFORMAS, index=PLATAFORMAS.index(dc), disabled=dis)
        pain = c2.number_input("Paq", 0, value=int(dpq), disabled=dis)
        min_ = st.text_area("Masters", dm, height=100, disabled=dis)
        com = st.text_area("Nota", dcm, disabled=dis)
        if not dis and st.form_submit_button("Guardar"):
            guardar_registro(did, fin, pin, clin, ds, min_, pain, com, user)
            st.session_state['scan_buf'] = []
            st.rerun()

# ==============================================================================
# 5. CONTROLADOR PRINCIPAL
# ==============================================================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'current_view' not in st.session_state: st.session_state['current_view'] = "menu"
for k in ['scan_buf', 'scan_pod', 'last_pdf']: 
    if k not in st.session_state: st.session_state[k] = [] if 'scan' in k else None

if not st.session_state['logged_in']:
    st.markdown("<br><h2 style='text-align:center'>Nexus Logística</h2>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.button("Entrar", use_container_width=True):
            usr = verificar_login(u, p)
            if usr: st.session_state['logged_in']=True; st.session_state['user_info']=usr; st.rerun()
            else: st.error("Error")
else:
    user = st.session_state['user_info']
    
    # --- SIDEBAR SIMPLE ---
    with st.sidebar:
        st.markdown(f"**{user['username']}** ({user['rol']})")
        if st.button("Salir"): st.session_state['logged_in']=False; st.rerun()

    # --- NAVEGACIÓN ---
    vista = st.session_state['current_view']
    
    # VISTA MENÚ PRINCIPAL (HOME)
    if vista == "menu":
        st.title("Panel Principal")
        c1, c2 = st.columns(2)
        
        # Botones Grandes
        with c1:
            if st.button("📅\nCalendario", use_container_width=True): st.session_state['current_view']="cal"; st.rerun()
            if st.button("📑\nGestor TEMU", use_container_width=True): st.session_state['current_view']="temu"; st.rerun()
            if st.button("⚙️\nConfig", use_container_width=True): st.session_state['current_view']="conf"; st.rerun()
        with c2:
            if st.button("📈\nAnalytics", use_container_width=True): st.session_state['current_view']="ana"; st.rerun()
            if st.button("📝\nPOD Digital", use_container_width=True): st.session_state['current_view']="pod"; st.rerun()
            if user['rol']=='admin' and st.button("👥\nAdmin", use_container_width=True): st.session_state['current_view']="adm"; st.rerun()

    # VISTAS DE HERRAMIENTAS
    else:
        if st.button("⬅️ VOLVER AL MENÚ"): st.session_state['current_view']="menu"; st.rerun()
        
        if vista == "cal":
            st.title("Calendario")
            if user['rol']!='analista' and st.button("➕ Nuevo"): modal_reg(None, user['username'])
            df = cargar_datos_cal()
            if not df.empty:
                evts = [{"title":f"📦{r['paquetes']}", "start":r['fecha_str'], "extendedProps": {"id":int(r['id']), "fecha_str":str(r['fecha_str']), "proveedor":r['proveedor_logistico'], "plataforma":r['plataforma_cliente'], "servicio":r['tipo_servicio'], "master":r['master_lote'], "paquetes":int(r['paquetes']), "comentarios":r['comentarios']}} for _,r in df.iterrows()]
                cal = calendar(events=evts, options={"initialView":"dayGridMonth","height":"500px"})
                if cal.get('eventClick'): modal_reg(cal['eventClick']['event']['extendedProps'], user['username'])

        elif vista == "ana":
            st.title("Analytics")
            df = cargar_datos_cal()
            if not df.empty:
                st.dataframe(df)
                st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "data.csv")

        elif vista == "temu":
            st.title("Gestor TEMU")
            f = st.file_uploader("Excel", type=["xlsx","xls"])
            if f:
                res, sum_df, err = procesar_temu(f)
                if res:
                    st.dataframe(sum_df)
                    for m, d in res.items():
                        with st.expander(f"📦 {m}"):
                            st.download_button("Manifiesto", to_excel_bytes(d['main']), f"{m}.xlsx")
                            st.download_button("Costos", to_excel_bytes(d['costos']), f"{m}_Costos.xlsx")

        elif vista == "pod":
            st.title("POD Digital")
            t1, t2 = st.tabs(["Nueva", "Historial"])
            with t1:
                # Cámara fuera de form
                if st.toggle("Cámara"):
                    img = st.camera_input("Scan")
                    if img:
                        c = decode_image(img)
                        if c and c[0] not in st.session_state['scan_pod']:
                            st.session_state['scan_pod'].append(c[0]); st.success(c[0])
                
                if st.button("Limpiar"): st.session_state['scan_pod']=[]; st.rerun()
                txt_scan = "\n".join(st.session_state['scan_pod'])

                with st.form("fpod"):
                    cli = st.selectbox("Cliente", PROVEEDORES)
                    rut = st.text_input("Ruta")
                    res = st.text_input("Responsable")
                    bul = st.number_input("Bultos", 0)
                    trks = st.text_area("Trackings", txt_scan)
                    firm = st_canvas(stroke_width=2, height=150)
                    if st.form_submit_button("Generar"):
                        tl = [t.strip() for t in trks.split('\n') if t.strip()]
                        if tl and rut:
                            uid, err = guardar_pod(cli, rut, res, len(tl), bul, tl, firm, user['username'])
                            if uid:
                                st.success("Guardado")
                                st.session_state['last_pdf'] = generar_pdf({"cliente":cli,"ruta":rut,"responsable":res,"bultos":bul,"trackings":tl,"firma_img":firm if firm.image_data is not None else None}, uid)
                                st.session_state['scan_pod'] = []
                                st.rerun()
                
                if st.session_state.get('last_pdf'):
                    st.download_button("📥 PDF", st.session_state['last_pdf'], "POD.pdf", "application/pdf")

            with t2:
                st.subheader("Historial")
                s = st.text_input("Buscar (ID/Tracking)")
                conn = get_connection()
                q = "SELECT uuid, pod_code, fecha, cliente FROM pods ORDER BY fecha DESC LIMIT 20"
                if s: q = f"SELECT DISTINCT p.uuid, p.pod_code, p.fecha, p.cliente FROM pods p JOIN pod_items i ON p.uuid=i.pod_uuid WHERE p.pod_code LIKE '%{s}%' OR i.tracking LIKE '%{s}%'"
                df = pd.read_sql(q, conn); conn.close()
                st.dataframe(df)
                if not df.empty:
                    sel = st.selectbox("Reimprimir", df['uuid'].tolist(), format_func=lambda x: str(x))
                    if st.button("Generar"):
                        d = recuperar_pod(sel)
                        if d: st.download_button("PDF", generar_pdf(d, sel, True), f"POD_{d['pod_code']}.pdf")

        elif vista == "adm":
            st.title("Admin")
            u = st.text_input("User"); r = st.selectbox("Rol", ["user","admin"])
            if st.button("Crear"): admin_user(u, r)
            conn=get_connection(); st.dataframe(pd.read_sql("SELECT * FROM usuarios", conn)); conn.close()

        elif vista == "conf":
            st.title("Config")
            p1=st.text_input("Pass",type="password"); p2=st.text_input("Confirm",type="password")
            if st.button("Cambiar") and p1==p2: cambiar_password(user['id'], p1)
