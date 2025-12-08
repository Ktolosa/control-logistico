import streamlit as st
import pandas as pd
import uuid, qrcode, random, string, io, cv2
import numpy as np
from datetime import datetime, date
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from utils import get_connection, decode_image, to_excel_bytes, APP_BASE_URL, PROVEEDORES

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
    pdf.cell(40,10,f"Ruta: {data['ruta']}",0,1); pdf.cell(40,10,f"Paquetes: {len(data['trackings'])}",0,1)
    y = pdf.get_y()+10; pdf.text(10,y,"FIRMA:"); pdf.rect(10,y+5,80,40)
    try:
        if hist and data['firma_bytes']:
            with open("s.png","wb") as f: f.write(data['firma_bytes'])
            pdf.image("s.png",10,y+5,80,40)
        elif data.get('firma_img') is not None:
            im=Image.fromarray(data['firma_img'].image_data.astype('uint8'),'RGBA'); im.save("s.png"); pdf.image("s.png",10,y+5,80,40)
    except: pass
    pdf.rect(10,y+5,80,40); pdf.text(110,y,"RECIBIDO POR:"); pdf.rect(110,y+5,80,40)
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
                if codes:
                    if codes[0] not in st.session_state['scanned_trackings']:
                        st.session_state['scanned_trackings'].append(codes[0]); st.success(f"Leído: {codes[0]}")
                    else: st.warning("Repetido")
        if st.button("Limpiar"): st.session_state['scanned_trackings'] = []; st.rerun()
        
        curr_scan = "\n".join(st.session_state['scanned_trackings'])

        with st.form("pod_form"):
            c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", PROVEEDORES); rut = c2.text_input("Ruta")
            c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",0)
            paq_dec = st.number_input("Paquetes Declarados", 1)
            
            trks_area = st.text_area("Trackings (Uno por línea)", curr_scan, height=150)
            
            # Validación Visual
            lista_t = [x.strip() for x in trks_area.split('\n') if x.strip()]
            unicos_t = list(set(lista_t))
            
            if len(lista_t) != len(unicos_t): st.markdown(f"<div class='count-err'>⚠️ {len(lista_t)-len(unicos_t)} Duplicados</div>", unsafe_allow_html=True)
            if len(lista_t) == paq_dec: st.markdown(f"<div class='count-ok'>✅ Cuadra Correcto ({len(lista_t)})</div>", unsafe_allow_html=True)
            else: st.markdown(f"<div class='count-err'>❌ No cuadra: {len(lista_t)} vs {paq_dec}</div>", unsafe_allow_html=True)

            firm = st_canvas(stroke_width=2, height=150)
            if st.form_submit_button("Generar"):
                if not rut or not unicos_t: st.error("Datos faltantes")
                elif len(lista_t) != len(unicos_t): st.error("Elimina duplicados primero")
                else:
                    d_pod = {"pod_code":"...","cliente":cli,"ruta":rut,"responsable":resp,"bultos":bult,"trackings":unicos_t,"firma_img":firm if firm.image_data is not None else None}
                    uid, err = guardar_pod(cli, rut, resp, paq_dec, bult, unicos_t, firm, user_info['username'])
                    if uid:
                        st.success("Guardado")
                        st.session_state['last_pod_pdf'] = generar_pdf(d_pod, uid)
                        st.session_state['last_pod_name'] = f"POD_{uid[:4]}.pdf"
                        df_ex = pd.DataFrame(unicos_t, columns=['Tracking'])
                        st.session_state['last_pod_excel'] = to_excel_bytes(df_ex,'xlsx')
                        st.session_state['scanned_trackings'] = []
                        st.rerun()

        if st.session_state.get('last_pod_pdf'):
            c1,c2 = st.columns(2)
            c1.download_button("Descargar PDF", st.session_state['last_pod_pdf'], st.session_state['last_pod_name'])
            c2.download_button("Descargar Excel", st.session_state['last_pod_excel'], "Lista.xlsx")

    with t2:
        st.subheader("Buscador")
        s_pod = st.text_input("Buscar (ID, Tracking, Cliente)")
        conn = get_connection()
        if conn:
            q = "SELECT uuid, pod_code, fecha, cliente FROM pods ORDER BY fecha DESC LIMIT 50"
            if s_pod:
                q = f"SELECT DISTINCT p.uuid, p.pod_code, p.fecha, p.cliente FROM pods p LEFT JOIN pod_items i ON p.uuid=i.pod_uuid WHERE p.pod_code LIKE '%{s_pod}%' OR p.cliente LIKE '%{s_pod}%' OR i.tracking LIKE '%{s_pod}%' LIMIT 20"
            dfp = pd.read_sql(q, conn); conn.close()
            st.dataframe(dfp)
            if not dfp.empty:
                sel = st.selectbox("Reimprimir", dfp['uuid'].tolist(), format_func=lambda x: str(x))
                if st.button("Regenerar"):
                    d = recuperar_pod(sel)
                    if d: 
                        st.download_button("PDF", generar_pdf(d, sel, True), f"POD_{d['pod_code']}.pdf")
                        st.download_button("Excel", to_excel_bytes(pd.DataFrame(d['trackings'],columns=['Tracking'])), f"List_{d['pod_code']}.xlsx")
