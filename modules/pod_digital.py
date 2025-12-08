import streamlit as st
import pandas as pd
import uuid
import qrcode
import random
import string
import io
import cv2
import numpy as np
from datetime import datetime, date
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from utils import get_connection, decode_image, to_excel_bytes, APP_BASE_URL

# --- FUNCIONES AUXILIARES ---
def generate_pod_code(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def guardar_pod(cliente, ruta, responsable, paq_dec, bultos, trackings, firma_canvas, user):
    conn = get_connection(); 
    if not conn: return None, "Error BD"
    try:
        cur = conn.cursor(); uid = str(uuid.uuid4()); code = generate_pod_code(); now = datetime.now()
        blob = None
        if firma_canvas.image_data is not None:
            im = Image.fromarray(firma_canvas.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        
        sql = "INSERT INTO pods (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        cur.execute(sql, (uid, code, now, cliente, ruta, responsable, paq_dec, len(trackings), bultos, blob, user))
        
        if trackings: 
            cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", [(uid, t) for t in trackings])
        
        conn.commit(); conn.close(); return uid, None
    except Exception as e: return None, str(e)

def recuperar_pod(uid):
    conn = get_connection()
    if not conn: return None
    try:
        df_h = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if df_h.empty: return None
        df_i = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        r = df_h.iloc[0]
        return {"uuid": r['uuid'], "pod_code": r.get('pod_code','N/A'), "fecha": r['fecha'], "cliente": r['cliente'], "ruta": r['ruta'], "responsable": r['responsable'], "bultos": r['bultos'], "trackings": df_i['tracking'].tolist(), "firma_bytes": r['signature_blob']}
    except: return None

def generar_pdf(data, pod_uuid, from_history=False):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(37,99,235); pdf.rect(0,0,210,40,'F')
    pdf.set_text_color(255,255,255); pdf.set_font("Arial",'B',24); pdf.text(10,18,"MANIFIESTO / POD")
    pdf.set_font("Arial",'',10); pdf.text(10,28,f"ID: {data.get('pod_code','N/A')} (Ref:{pod_uuid[:6]})")
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

def show(user_info):
    st.title("📝 POD Digital")
    
    # Inicializar memoria escaneo local si no existe
    if 'scanned_trackings' not in st.session_state: st.session_state['scanned_trackings'] = []
    
    t1, t2 = st.tabs(["Nueva", "Historial"])
    
    with t1:
        # CÁMARA (FUERA DEL FORM)
        col_cam, col_txt = st.columns([1,2])
        if col_cam.toggle("📷 Usar Cámara"):
            img = st.camera_input("Scan")
            if img:
                codes = decode_image(img)
                if codes: 
                    if codes[0] not in st.session_state['scanned_trackings']:
                        st.session_state['scanned_trackings'].append(codes[0])
                        st.success(f"Leído: {codes[0]}")
                    else: st.warning("Repetido")
        
        if st.button("Limpiar Escaneos"): st.session_state['scanned_trackings'] = []; st.rerun()
        curr_scan = "\n".join(st.session_state['scanned_trackings'])

        with st.form("pod_form"):
            c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", ["Mail Americas","APG","IMILE"]); rut = c2.text_input("Ruta")
            c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",0)
            paq_obj = st.number_input("Paquetes Declarados",1)
            
            track_raw = st.text_area("Trackings", value=curr_scan, height=150)
            firma = st_canvas(fill_color="rgba(255, 165, 0, 0.3)", stroke_width=2, height=150)
            
            if st.form_submit_button("Generar"):
                ts = [t.strip() for t in track_raw.split('\n') if t.strip()]
                unique_ts = list(set(ts))
                if len(ts) != len(unique_ts): st.error(f"Duplicados: {len(ts)-len(unique_ts)}")
                elif len(ts) != paq_obj: st.error(f"No cuadra: {len(ts)} vs {paq_obj}")
                elif not rut or not ts: st.error("Datos faltantes")
                else:
                    d_pod = {"cliente":cli,"ruta":rut,"responsable":resp,"bultos":bult,"trackings":ts,"firma_img":firma if firma.image_data is not None else None}
                    uid, err = guardar_pod(cli, rut, resp, paq_obj, bult, ts, firma, user_info['username'])
                    if uid:
                        st.success("Guardado")
                        st.session_state['last_pod_pdf'] = generar_pdf(d_pod, uid)
                        st.session_state['last_pod_name'] = f"POD_{uid[:4]}.pdf"
                        df_ex = pd.DataFrame(ts, columns=['Tracking'])
                        st.session_state['last_pod_excel'] = to_excel_bytes(df_ex,'xlsx')
                        st.session_state['scanned_trackings'] = [] # Limpiar
                        st.rerun()

        if st.session_state.get('last_pod_pdf'):
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
                pod_options = {row['uuid']: f"{row['pod_code']} - {row['cliente']} ({row['fecha']})" for i, row in df_p.iterrows()}
                sel_uuid = st.selectbox("Reimprimir", list(pod_options.keys()), format_func=lambda x: pod_options[x])
                
                if st.button("Regenerar Archivos"):
                    d_hist = recuperar_pod(sel_uuid)
                    if d_hist:
                        pdf_h = generar_pdf(d_hist, sel_uuid, True)
                        df_ex = pd.DataFrame(d_hist['trackings'], columns=["Tracking"])
                        xls_h = to_excel_bytes(df_ex,'xlsx')
                        c1,c2 = st.columns(2)
                        c1.download_button("📥 PDF", pdf_h, f"POD_{d_hist['pod_code']}.pdf")
                        c2.download_button("📊 Excel", xls_h, f"List_{d_hist['pod_code']}.xlsx")
