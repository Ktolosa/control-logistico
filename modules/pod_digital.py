import streamlit as st
import pandas as pd
import uuid, qrcode, random, string, io, cv2
import numpy as np
from datetime import datetime, date
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from utils import get_connection, decode_image, to_excel_bytes, APP_BASE_URL, PROVEEDORES

# --- 1. FUNCIÓN DE BASE DE DATOS ---
def guardar_pod(cli, rut, res, dec, bul, trks, firm, user):
    conn = get_connection(); 
    if not conn: return None, None, None, "Error BD"
    try:
        cur = conn.cursor(); uid = str(uuid.uuid4()); code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=10)); now = datetime.now()
        blob = None
        if firm.image_data is not None:
            im = Image.fromarray(firm.image_data.astype('uint8'), 'RGBA'); buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        
        cur.execute("INSERT INTO pods (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (uid, code, now, cli, rut, res, dec, len(trks), bul, blob, user))
        
        if trks: cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", [(uid, t) for t in trks])
        
        conn.commit(); conn.close(); 
        return uid, code, now.strftime("%Y-%m-%d %H:%M"), None 
    except Exception as e: return None, None, None, str(e)

# --- 2. GENERADOR DE PDF (CORREGIDO) ---
def generar_pdf(data, uid, hist=False):
    pdf = FPDF(); pdf.add_page()
    
    # --- ENCABEZADO ---
    pdf.set_fill_color(37,99,235); pdf.rect(0,0,210,40,'F') # Fondo Azul
    pdf.set_text_color(255); pdf.set_font("Arial",'B',24); pdf.text(10,18,"MANIFIESTO / POD")
    
    # Datos Encabezado (ID y Fecha ubicados para no tapar QR)
    pdf.set_font("Arial",'B',10)
    pdf.text(120, 18, f"ID: {data.get('pod_code','N/A')}")
    pdf.set_font("Arial",'',10)
    pdf.text(120, 25, f"Fecha: {data.get('fecha_str','N/A')}")

    # QR (A la derecha)
    qr = qrcode.make(f"{APP_BASE_URL}/?pod_uuid={uid}"); qr.save("qr.png")
    pdf.image("qr.png",172,7,26,26) 
    
    # --- INFORMACIÓN PRINCIPAL ---
    pdf.set_text_color(0)
    pdf.set_y(50)
    
    # Bloque de datos (Cliente, Ruta, Responsable)
    info = [
        ("Cliente / Proveedor:", str(data['cliente'])),
        ("Ruta / Destino:", str(data['ruta'])),
        ("Responsable:", str(data['responsable'])) # <-- AGREGADO RESPONSABLE
    ]
    
    for lbl, val in info:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(50, 8, lbl, 0, 0)
        pdf.set_font("Arial", '', 11)
        pdf.cell(100, 8, val, 0, 1) # Salto de línea

    pdf.ln(5)

    # --- TABLA DE TOTALES (RESTAURADA) ---
    # Encabezados
    pdf.set_fill_color(230, 230, 230) # Gris claro
    pdf.set_font("Arial", 'B', 12)
    # Ancho total 190 (95+95) centrado aprox
    pdf.cell(95, 12, "Cantidad de Paquetes", 1, 0, 'C', True)
    pdf.cell(95, 12, "Cantidad de Bultos", 1, 1, 'C', True)
    
    # Valores
    total_paquetes = len(data['trackings'])
    total_bultos = data['bultos']
    
    pdf.set_font("Arial", '', 14)
    pdf.cell(95, 15, str(total_paquetes), 1, 0, 'C')
    pdf.cell(95, 15, str(total_bultos), 1, 1, 'C')
    
    pdf.ln(25) # Espacio antes de firmas
    
    # --- FIRMAS ---
    y = pdf.get_y()
    
    # Cuadro Izquierdo (Responsable)
    pdf.set_font("Arial", 'B', 10)
    pdf.text(10, y, "FIRMA RESPONSABLE:")
    pdf.rect(10, y+5, 85, 40)
    
    # Insertar firma imagen
    try:
        if hist and data.get('firma_bytes'):
            with open("s.png","wb") as f: f.write(data['firma_bytes'])
            pdf.image("s.png", 15, y+10, 75, 30)
        elif data.get('firma_img') is not None:
            im = Image.fromarray(data['firma_img'].image_data.astype('uint8'), 'RGBA')
            im.save("s.png")
            pdf.image("s.png", 15, y+10, 75, 30)
    except: pass

    # Cuadro Derecho (Recibido)
    pdf.text(110, y, "RECIBIDO POR:")
    pdf.rect(110, y+5, 85, 40)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. RECUPERAR DATOS ---
def recuperar_pod(uid):
    conn = get_connection()
    if not conn: return None
    try:
        dfh = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if dfh.empty: return None
        dfi = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        r = dfh.iloc[0]
        f_str = r['fecha'].strftime("%Y-%m-%d %H:%M") if r['fecha'] else "N/A"
        return {
            "uuid": r['uuid'], 
            "pod_code": r.get('pod_code','N/A'), 
            "fecha_str": f_str, 
            "cliente": r['cliente'], 
            "ruta": r['ruta'], 
            "responsable": r['responsable'], 
            "bultos": r['bultos'], 
            "trackings": dfi['tracking'].tolist(), 
            "firma_bytes": r['signature_blob']
        }
    except: return None

# --- 4. INTERFAZ GRÁFICA ---
def show(user_info):
    st.title("📝 POD Digital")
    if 'scanned_trackings' not in st.session_state: st.session_state['scanned_trackings'] = []
    
    t1, t2 = st.tabs(["Nueva", "Historial"])
    
    with t1:
        c_cam, c_txt = st.columns([1,2])
        
        # TOGGLE CÁMARA
        use_cam = c_cam.toggle("📷 Usar Cámara", value=False)
        if use_cam:
            img = st.camera_input("Scan")
            if img:
                codes = decode_image(img)
                if codes:
                    if codes[0] not in st.session_state['scanned_trackings']:
                        st.session_state['scanned_trackings'].append(codes[0]); st.success(f"Leído: {codes[0]}")
                    else: st.warning("Repetido")
        
        if st.button("Limpiar Lista"): st.session_state['scanned_trackings'] = []; st.rerun()
        
        curr_scan = "\n".join(st.session_state['scanned_trackings'])

        with st.form("pod_form"):
            st.subheader("Datos del Manifiesto")
            c1,c2 = st.columns(2); cli = c1.selectbox("Cliente", PROVEEDORES); rut = c2.text_input("Ruta")
            c3,c4 = st.columns(2); resp = c3.text_input("Responsable"); bult = c4.number_input("Bultos",1)
            paq_dec = st.number_input("Paquetes Declarados", 1)
            
            st.write("Trackings (Uno por línea)")
            trks_area = st.text_area("Lista", curr_scan, height=150, label_visibility="collapsed")
            
            # Validación Visual
            lista_t = [x.strip() for x in trks_area.split('\n') if x.strip()]
            unicos_t = list(set(lista_t))
            
            c_val1, c_val2 = st.columns(2)
            with c_val1:
                if len(lista_t) != len(unicos_t): st.markdown(f"<div class='count-err'>⚠️ {len(lista_t)-len(unicos_t)} Duplicados</div>", unsafe_allow_html=True)
                else: st.caption("Sin duplicados")
            with c_val2:
                if len(lista_t) == paq_dec and len(lista_t) > 0: st.markdown(f"<div class='count-ok'>✅ Cuadra ({len(lista_t)})</div>", unsafe_allow_html=True)
                else: st.markdown(f"<div class='count-err'>❌ Dif: {len(lista_t) - paq_dec}</div>", unsafe_allow_html=True)

            st.write("Firma Responsable")
            firm = st_canvas(stroke_width=2, height=150, key="firma_new")
            
            if st.form_submit_button("Generar POD", type="primary"):
                if not rut or not unicos_t: st.error("Faltan datos (Ruta o Trackings)")
                elif len(lista_t) != len(unicos_t): st.error("Elimina duplicados primero")
                else:
                    uid, code, f_str, err = guardar_pod(cli, rut, resp, paq_dec, bult, unicos_t, firm, user_info['username'])
                    
                    if uid:
                        st.success(f"POD {code} Generado")
                        d_pod = {
                            "pod_code": code,
                            "fecha_str": f_str, 
                            "cliente":cli, "ruta":rut, "responsable":resp, "bultos":bult, "trackings":unicos_t,
                            "firma_img":firm if firm.image_data is not None else None
                        }
                        st.session_state['last_pod_pdf'] = generar_pdf(d_pod, uid)
                        st.session_state['last_pod_name'] = f"POD_{code}.pdf"
                        df_ex = pd.DataFrame(unicos_t, columns=['Tracking'])
                        st.session_state['last_pod_excel'] = to_excel_bytes(df_ex,'xlsx')
                        st.session_state['scanned_trackings'] = []
                        st.rerun()
                    else:
                        st.error(f"Error: {err}")

        if st.session_state.get('last_pod_pdf'):
            st.success("Archivos listos para descargar:")
            c1,c2 = st.columns(2)
            c1.download_button("📄 Descargar PDF", st.session_state['last_pod_pdf'], st.session_state['last_pod_name'], type="primary", use_container_width=True)
            c2.download_button("📊 Descargar Excel", st.session_state['last_pod_excel'], "Lista.xlsx", use_container_width=True)

    with t2:
        st.subheader("Historial y Reimpresión")
        s_pod = st.text_input("🔍 Buscar (ID, Tracking, Cliente, Ruta)")
        conn = get_connection()
        if conn:
            q_base = "SELECT DISTINCT p.uuid, p.pod_code, p.fecha, p.cliente, p.ruta FROM pods p "
            if s_pod:
                q = q_base + f"LEFT JOIN pod_items i ON p.uuid=i.pod_uuid WHERE p.pod_code LIKE '%{s_pod}%' OR p.cliente LIKE '%{s_pod}%' OR p.ruta LIKE '%{s_pod}%' OR i.tracking LIKE '%{s_pod}%' ORDER BY p.fecha DESC LIMIT 20"
            else:
                q = q_base + "ORDER BY p.fecha DESC LIMIT 20"
            
            dfp = pd.read_sql(q, conn); conn.close()
            
            if not dfp.empty:
                st.dataframe(dfp[['pod_code','fecha','cliente','ruta']], use_container_width=True)
                
                opciones = dfp.apply(lambda x: f"{x['pod_code']} | {x['cliente']}", axis=1).tolist()
                dic_map = dict(zip(opciones, dfp['uuid'].tolist()))
                sel = st.selectbox("Seleccionar para reimprimir:", opciones)
                
                if st.button("🔄 Regenerar Documentos"):
                    uuid_sel = dic_map[sel]
                    d = recuperar_pod(uuid_sel)
                    if d: 
                        c1, c2 = st.columns(2)
                        c1.download_button("📄 PDF", generar_pdf(d, uuid_sel, True), f"POD_{d['pod_code']}.pdf", type="primary", use_container_width=True)
                        c2.download_button("📊 Excel", to_excel_bytes(pd.DataFrame(d['trackings'],columns=['Tracking'])), f"List_{d['pod_code']}.xlsx", use_container_width=True)
            else:
                st.info("Sin resultados")
