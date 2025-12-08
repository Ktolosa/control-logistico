import streamlit as st
import pandas as pd
import uuid, qrcode, random, string, io
from datetime import datetime
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from utils import get_connection, decode_image, to_excel_bytes, APP_BASE_URL, PROVEEDORES

# CLASE PDF MEJORADA
class PDF(FPDF):
    def header(self):
        self.set_fill_color(37, 99, 235)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255)
        self.set_font("Arial", 'B', 24)
        self.text(10, 18, "MANIFIESTO / POD")

def guardar_pod(cli, rut, res, dec, bul, trks, firm, user):
    conn = get_connection(); 
    if not conn: return None, None, "Error BD"
    try:
        cur = conn.cursor()
        uid = str(uuid.uuid4())
        code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=10))
        now = datetime.now()
        blob = None
        if firm.image_data is not None:
            im = Image.fromarray(firm.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        
        cur.execute("INSERT INTO pods (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (uid, code, now, cli, rut, res, dec, len(trks), bul, blob, user))
        if trks: cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", [(uid, t) for t in trks])
        conn.commit(); conn.close()
        return uid, code, None
    except Exception as e: return None, None, str(e)

def generar_pdf(data, uid, hist=False):
    pdf = PDF(); pdf.add_page()
    
    # HEADER DATA
    pdf.set_text_color(255); pdf.set_font("Arial", 'B', 12)
    pdf.text(10, 28, f"ID: {data.get('pod_code','PENDIENTE')}")
    pdf.set_font("Arial", '', 10)
    fecha = data.get('fecha', datetime.now())
    f_str = fecha.strftime("%Y-%m-%d %H:%M:%S") if isinstance(fecha, datetime) else str(fecha)[:19]
    pdf.text(10, 35, f"Emisión: {f_str}")
    
    qr = qrcode.make(f"{APP_BASE_URL}/?pod_uuid={uid}"); qr.save("qr.png")
    pdf.image("qr.png", 170, 5, 30, 30)
    
    # VIAJE INFO
    pdf.set_text_color(0); pdf.set_y(50)
    infos = [("Cliente:", str(data['cliente'])), ("Ruta:", str(data['ruta'])), ("Responsable:", str(data['responsable'])), ("Total Paquetes:", str(len(data['trackings'])))]
    
    for k, v in infos:
        pdf.set_font("Arial", 'B', 10); pdf.cell(30, 8, k, 0, 0)
        pdf.set_font("Arial", '', 10); pdf.cell(70, 8, v, 0, 1)
    
    pdf.ln(5)
    
    # TABLA
    pdf.set_fill_color(220, 220, 220); pdf.set_font("Arial", 'B', 9)
    pdf.cell(10, 8, "#", 1, 0, 'C', True)
    pdf.cell(140, 8, "Tracking / Código", 1, 0, 'L', True)
    pdf.cell(40, 8, "Estado", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    for i, trk in enumerate(data['trackings']):
        pdf.cell(10, 7, str(i+1), 1, 0, 'C')
        pdf.cell(140, 7, str(trk), 1, 0, 'L')
        pdf.cell(40, 7, "Recibido", 1, 1, 'C')
    
    # FIRMAS
    if pdf.get_y() > 240: pdf.add_page()
    y = pdf.get_y() + 15
    pdf.set_font("Arial", 'B', 8)
    
    pdf.text(10, y, "FIRMA RESPONSABLE:"); pdf.rect(10, y+2, 80, 30)
    try:
        if hist and data.get('firma_bytes'):
            with open("s.png","wb") as f: f.write(data['firma_bytes'])
            pdf.image("s.png", 12, y+4, 76, 26)
        elif data.get('firma_img') is not None:
            im = Image.fromarray(data['firma_img'].image_data.astype('uint8'), 'RGBA'); im.save("s.png")
            pdf.image("s.png", 12, y+4, 76, 26)
    except: pass
    
    pdf.text(110, y, "RECIBIDO POR:"); pdf.rect(110, y+2, 80, 30)
    return pdf.output(dest='S').encode('latin-1')

def recuperar_pod(uid):
    conn = get_connection()
    if not conn: return None
    try:
        dfh = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if dfh.empty: return None
        dfi = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        r = dfh.iloc[0]
        return {"uuid":r['uuid'], "pod_code":r.get('pod_code','N/A'), "fecha":r['fecha'], "cliente":r['cliente'], "ruta":r['ruta'], "responsable":r['responsable'], "bultos":r['bultos'], "trackings":dfi['tracking'].tolist(), "firma_bytes":r['signature_blob']}
    except: return None

def show(user_info):
    st.title("📝 POD Digital")
    if 'scanned_trackings' not in st.session_state: st.session_state['scanned_trackings'] = []
    
    t1, t2 = st.tabs(["Nueva", "Historial"])
    with t1:
        c_cam, c_txt = st.columns([1,2])
        if c_cam.toggle("📷 Usar Cámara"):
            img = st.camera_input("Scan")
            if img:
                codes = decode_image(img)
                if codes and codes[0] not in st.session_state['scanned_trackings']:
                    st.session_state['scanned_trackings'].append(codes[0]); st.success(f"Leído: {codes[0]}")
        
        if st.button("Limpiar"): st.session_state['scanned_trackings'] = []; st.rerun()
        curr_scan = "\n".join(st.session_state['scanned_trackings'])

        with st.form("pod_form"):
            c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", PROVEEDORES); rut = c2.text_input("Ruta")
            c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",0)
            paq_dec = st.number_input("Paquetes Declarados", 1)
            trks_area = st.text_area("Trackings", curr_scan, height=150)
            
            lista_t = [x.strip() for x in trks_area.split('\n') if x.strip()]
            unicos_t = list(set(lista_t))
            
            if len(lista_t) != len(unicos_t): st.warning(f"Duplicados eliminados: {len(lista_t)-len(unicos_t)}")
            
            firm = st_canvas(stroke_width=2, height=150)
            if st.form_submit_button("Generar"):
                if not rut or not unicos_t: st.error("Faltan datos")
                else:
                    uid, cod, err = guardar_pod(cli, rut, resp, paq_dec, bult, unicos_t, firm, user_info['username'])
                    if uid:
                        st.success(f"Generado {cod}")
                        d = {"pod_code":cod, "fecha":datetime.now(), "cliente":cli, "ruta":rut, "responsable":resp, "trackings":unicos_t, "firma_img":firm if firm.image_data is not None else None}
                        st.session_state['last_pdf'] = generar_pdf(d, uid)
                        st.session_state['last_name'] = f"POD_{cod}.pdf"
                        st.session_state['scanned_trackings'] = []; st.rerun()

        if st.session_state.get('last_pdf'):
            st.download_button("Descargar PDF Generado", st.session_state['last_pdf'], st.session_state['last_name'], type="primary")

    with t2:
        st.subheader("Historial")
        s_pod = st.text_input("Buscar ID/Tracking")
        conn = get_connection()
        if conn:
            q = f"SELECT uuid, pod_code, fecha, cliente FROM pods WHERE pod_code LIKE '%{s_pod}%' OR cliente LIKE '%{s_pod}%' ORDER BY fecha DESC LIMIT 20"
            dfp = pd.read_sql(q, conn); conn.close(); st.dataframe(dfp)
            if not dfp.empty:
                sel = st.selectbox("Reimprimir", dfp['uuid'].tolist(), format_func=lambda x: str(x))
                if st.button("Descargar Copia"):
                    d = recuperar_pod(sel)
                    if d: st.download_button("📄 PDF", generar_pdf(d, sel, True), f"Copia_{d['pod_code']}.pdf")
