import streamlit as st
import pandas as pd
import uuid, qrcode, random, string, io
from datetime import datetime, date
from fpdf import FPDF
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from utils import get_connection, decode_image, to_excel_bytes, APP_BASE_URL, PROVEEDORES

# --- 1. CLASE PDF ACTUALIZADA (DISEÑO RESUMIDO) ---
class PDF(FPDF):
    def header(self):
        # Encabezado azul corporativo
        self.set_fill_color(37, 99, 235)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255)
        self.set_font("Arial", 'B', 24)
        self.text(10, 18, "MANIFIESTO / POD")
        self.set_font("Arial", '', 10)
        self.text(10, 28, "Resumen de Carga")

def generar_pdf_resumen(data, uid, hist=False):
    pdf = PDF()
    pdf.add_page()
    
    # --- DATOS DEL ENCABEZADO ---
    pdf.set_text_color(255)
    pdf.set_font("Arial", 'B', 14)
    pdf.text(140, 18, f"ID: {data.get('pod_code','N/A')}")
    
    pdf.set_font("Arial", '', 10)
    fecha = data.get('fecha', datetime.now())
    str_fecha = fecha.strftime("%Y-%m-%d %H:%M") if isinstance(fecha, datetime) else str(fecha)[:16]
    pdf.text(140, 25, f"Fecha: {str_fecha}")
    
    # Generar QR
    qr = qrcode.make(f"{APP_BASE_URL}/?pod_uuid={uid}")
    qr.save("qr.png")
    pdf.image("qr.png", 170, 5, 30, 30)
    
    # --- INFORMACIÓN DEL VIAJE ---
    pdf.set_text_color(0)
    pdf.set_y(50)
    
    # Estilo de datos clave
    info_rows = [
        ("Cliente / Proveedor:", str(data['cliente'])),
        ("Ruta / Destino:", str(data['ruta'])),
        ("Responsable:", str(data['responsable']))
    ]
    
    for label, value in info_rows:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(50, 8, label, 0, 0)
        pdf.set_font("Arial", '', 11)
        pdf.cell(100, 8, value, 0, 1) # Salto de línea
    
    pdf.ln(10)

    # --- NUEVA TABLA (SOLO TOTALES) ---
    # Según tu requerimiento: Col A (Total Paquetes), Col B (Bultos)
    
    # Encabezados de tabla
    pdf.set_fill_color(230, 230, 230) # Gris claro
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 12, "Cantidad de Paquetes", 1, 0, 'C', True)
    pdf.cell(95, 12, "Cantidad de Bultos", 1, 1, 'C', True)
    
    # Datos de tabla
    total_paquetes = len(data['trackings'])
    total_bultos = data['bultos']
    
    pdf.set_font("Arial", '', 14)
    pdf.cell(95, 15, str(total_paquetes), 1, 0, 'C')
    pdf.cell(95, 15, str(total_bultos), 1, 1, 'C')
    
    pdf.ln(20)
    
    # --- SECCIÓN DE FIRMAS ---
    if pdf.get_y() > 220: pdf.add_page()
    y_pos = pdf.get_y()
    
    pdf.set_font("Arial", 'B', 10)
    
    # Cuadro Firma Responsable
    pdf.text(10, y_pos, "ENTREGADO POR (Responsable):")
    pdf.rect(10, y_pos+5, 85, 40)
    
    # Insertar imagen de firma si existe
    try:
        if hist and data.get('firma_bytes'):
            with open("temp_sig.png", "wb") as f: f.write(data['firma_bytes'])
            pdf.image("temp_sig.png", 15, y_pos+10, 75, 30)
        elif data.get('firma_img') is not None:
            im = Image.fromarray(data['firma_img'].image_data.astype('uint8'), 'RGBA')
            im.save("temp_sig.png")
            pdf.image("temp_sig.png", 15, y_pos+10, 75, 30)
    except: pass

    # Cuadro Firma Recibido
    pdf.text(110, y_pos, "RECIBIDO POR (Cliente/Almacén):")
    pdf.rect(110, y_pos+5, 85, 40)
    
    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIONES DE BASE DE DATOS ---
def guardar_pod(cli, rut, res, dec, bul, trks, firm, user):
    conn = get_connection()
    if not conn: return None, None, "Error de Conexión"
    try:
        cur = conn.cursor()
        uid = str(uuid.uuid4())
        code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=10))
        now = datetime.now()
        
        # Procesar firma
        blob = None
        if firm.image_data is not None:
            im = Image.fromarray(firm.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO(); im.save(buf, 'PNG'); blob = buf.getvalue()
        
        # Insertar Cabecera
        cur.execute("""
            INSERT INTO pods 
            (uuid, pod_code, fecha, cliente, ruta, responsable, paquetes_declarados, paquetes_reales, bultos, signature_blob, created_by) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (uid, code, now, cli, rut, res, dec, len(trks), bul, blob, user))
        
        # Insertar Items (Trackings)
        if trks: 
            val_list = [(uid, t) for t in trks]
            cur.executemany("INSERT INTO pod_items (pod_uuid, tracking) VALUES (%s, %s)", val_list)
        
        conn.commit()
        conn.close()
        return uid, code, None
    except Exception as e: return None, None, str(e)

def recuperar_pod_completo(uid):
    conn = get_connection()
    if not conn: return None
    try:
        # Recuperar cabecera
        dfh = pd.read_sql("SELECT * FROM pods WHERE uuid=%s", conn, params=(uid,))
        if dfh.empty: return None
        
        # Recuperar trackings
        dfi = pd.read_sql("SELECT tracking FROM pod_items WHERE pod_uuid=%s", conn, params=(uid,))
        
        r = dfh.iloc[0]
        return {
            "uuid": r['uuid'],
            "pod_code": r.get('pod_code', 'N/A'),
            "fecha": r['fecha'],
            "cliente": r['cliente'],
            "ruta": r['ruta'],
            "responsable": r['responsable'],
            "bultos": r['bultos'],
            "trackings": dfi['tracking'].tolist(), # Lista para contar paquetes
            "firma_bytes": r['signature_blob']
        }
    except: return None

# --- VISTA PRINCIPAL ---
def show(user_info):
    st.title("📝 POD Digital (Manifiestos)")
    
    if 'scanned_trackings' not in st.session_state: st.session_state['scanned_trackings'] = []
    
    tab_new, tab_hist = st.tabs(["➕ Nuevo Manifiesto", "🔍 Historial y Descargas"])
    
    # ---------------------------------------------------------
    # PESTAÑA 1: NUEVO MANIFIESTO
    # ---------------------------------------------------------
    with tab_new:
        col_scan, col_manual = st.columns([1, 2])
        
        # Escáner
        with col_scan:
            st.info("Escáner QR/Barras")
            img = st.camera_input("Escanear etiqueta")
            if img:
                codes = decode_image(img)
                if codes:
                    for c in codes:
                        if c not in st.session_state['scanned_trackings']:
                            st.session_state['scanned_trackings'].append(c)
                            st.toast(f"✅ Agregado: {c}")
                        else:
                            st.toast(f"⚠️ Ya existe: {c}")

        # Lista y Botones
        with col_manual:
            if st.button("🗑️ Limpiar Lista", type="secondary"):
                st.session_state['scanned_trackings'] = []
                st.rerun()
                
            curr_scan = "\n".join(st.session_state['scanned_trackings'])
            st.caption(f"Paquetes escaneados: {len(st.session_state['scanned_trackings'])}")

        st.divider()

        # Formulario de Datos
        with st.form("pod_form_new"):
            st.subheader("Datos del Manifiesto")
            
            c1, c2 = st.columns(2)
            cli = c1.selectbox("Cliente / Proveedor", PROVEEDORES)
            rut = c2.text_input("Ruta / Destino")
            
            c3, c4, c5 = st.columns(3)
            resp = c3.text_input("Responsable (Chofer/Mensajero)")
            bult = c4.number_input("Cantidad de Bultos (Sacos)", min_value=1, value=1)
            paq_dec = c5.number_input("Paquetes Declarados", min_value=1, value=1)
            
            st.markdown("---")
            st.write("📋 **Lista de Trackings (Excel)**")
            trks_area = st.text_area("Pegar o escanear aquí (uno por línea)", curr_scan, height=150)
            
            # Limpieza de lista
            raw_list = [x.strip() for x in trks_area.split('\n') if x.strip()]
            final_trackings = list(set(raw_list)) # Eliminar duplicados
            
            # Validaciones visuales
            if len(final_trackings) != len(raw_list):
                st.warning(f"⚠️ Se eliminaron {len(raw_list)-len(final_trackings)} duplicados.")
            
            st.write("✍️ **Firma del Responsable**")
            firm = st_canvas(stroke_width=2, height=150, key="new_sig")
            
            submitted = st.form_submit_button("💾 Guardar y Generar Archivos", type="primary")
            
            if submitted:
                if not rut or not final_trackings:
                    st.error("❌ Faltan datos obligatorios (Ruta o Lista de Trackings).")
                else:
                    uid, code, err = guardar_pod(cli, rut, resp, paq_dec, bult, final_trackings, firm, user_info['username'])
                    
                    if uid:
                        st.success(f"✅ Manifiesto {code} Creado Exitosamente")
                        
                        # Preparar datos para generación inmediata
                        datos_pod = {
                            "pod_code": code,
                            "fecha": datetime.now(),
                            "cliente": cli,
                            "ruta": rut,
                            "responsable": resp,
                            "bultos": bult,
                            "trackings": final_trackings,
                            "firma_img": firm if firm.image_data is not None else None
                        }
                        
                        # Generar PDF (Resumen)
                        pdf_bytes = generar_pdf_resumen(datos_pod, uid)
                        
                        # Generar Excel (Detalle)
                        df_ex = pd.DataFrame(final_trackings, columns=['Tracking Code'])
                        excel_bytes = to_excel_bytes(df_ex, 'xlsx')
                        
                        # Guardar en sesión para descargar fuera del form
                        st.session_state['new_pdf'] = pdf_bytes
                        st.session_state['new_excel'] = excel_bytes
                        st.session_state['new_code'] = code
                        st.session_state['scanned_trackings'] = [] # Reset
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {err}")

        # Zona de Descarga (Aparece tras guardar)
        if 'new_pdf' in st.session_state:
            st.success("📂 Archivos listos para descargar:")
            kc1, kc2 = st.columns(2)
            kc1.download_button(
                label="📄 Descargar PDF (Resumen)",
                data=st.session_state['new_pdf'],
                file_name=f"POD_{st.session_state['new_code']}_Resumen.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            kc2.download_button(
                label="📊 Descargar Excel (Trackings)",
                data=st.session_state['new_excel'],
                file_name=f"POD_{st.session_state['new_code']}_Detalle.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            if st.button("Cerrar y Nuevo"):
                del st.session_state['new_pdf']
                del st.session_state['new_excel']
                st.rerun()

    # ---------------------------------------------------------
    # PESTAÑA 2: HISTORIAL Y FILTROS AVANZADOS
    # ---------------------------------------------------------
    with tab_hist:
        st.subheader("🔍 Buscador Avanzado")
        
        # --- FILTROS ---
        with st.expander("Filtros de Búsqueda", expanded=True):
            f1, f2, f3 = st.columns(3)
            s_id = f1.text_input("ID Manifiesto")
            s_cli = f2.selectbox("Cliente", ["Todos"] + PROVEEDORES)
            s_trk = f3.text_input("Buscar Tracking específico")
            
            f4, f5, f6 = st.columns(3)
            s_rut = f4.text_input("Ruta")
            s_res = f5.text_input("Responsable")
            # Filtro de fecha (Opcional)
            use_date = f6.checkbox("Filtrar por Fecha")
            s_date = f6.date_input("Fecha", []) if use_date else None

        # --- QUERY DINÁMICA ---
        conn = get_connection()
        if conn:
            # Base query
            query = """
                SELECT DISTINCT p.uuid, p.pod_code, p.fecha, p.cliente, p.ruta, p.responsable, p.bultos, p.paquetes_reales 
                FROM pods p 
            """
            params = []
            conditions = ["1=1"] # Siempre verdadero para concatenar ANDs
            
            # Si busca tracking, hacemos JOIN
            if s_trk:
                query += " JOIN pod_items i ON p.uuid = i.pod_uuid "
                conditions.append("i.tracking LIKE %s")
                params.append(f"%{s_trk}%")
            
            if s_id:
                conditions.append("p.pod_code LIKE %s")
                params.append(f"%{s_id}%")
            
            if s_cli != "Todos":
                conditions.append("p.cliente = %s")
                params.append(s_cli)
                
            if s_rut:
                conditions.append("p.ruta LIKE %s")
                params.append(f"%{s_rut}%")
                
            if s_res:
                conditions.append("p.responsable LIKE %s")
                params.append(f"%{s_res}%")

            if use_date and isinstance(s_date, tuple) and len(s_date) == 2:
                conditions.append("DATE(p.fecha) BETWEEN %s AND %s")
                params.extend([s_date[0], s_date[1]])
            elif use_date and not isinstance(s_date, tuple):
                 # Si seleccionó solo un día
                conditions.append("DATE(p.fecha) = %s")
                params.append(s_date)

            # Armar query final
            final_sql = query + " WHERE " + " AND ".join(conditions) + " ORDER BY p.fecha DESC LIMIT 50"
            
            df_res = pd.read_sql(final_sql, conn, params=params)
            conn.close()
            
            # --- RESULTADOS ---
            if not df_res.empty:
                st.dataframe(df_res[['pod_code', 'fecha', 'cliente', 'ruta', 'responsable', 'paquetes_reales', 'bultos']], use_container_width=True)
                
                st.write("📥 **Descargar Documentos**")
                
                # Selector para descargar
                opciones = df_res.apply(lambda x: f"{x['pod_code']} | {x['cliente']} ({x['fecha']})", axis=1).tolist()
                ids = df_res['uuid'].tolist()
                dic_map = dict(zip(opciones, ids))
                
                seleccion = st.selectbox("Seleccione un manifiesto de la lista:", opciones)
                uuid_sel = dic_map[seleccion]
                
                if uuid_sel:
                    col_d1, col_d2 = st.columns(2)
                    
                    # Recuperar datos completos para generar archivos
                    data_full = recuperar_pod_completo(uuid_sel)
                    
                    if data_full:
                        # Botón PDF
                        pdf_hist = generar_pdf_resumen(data_full, uuid_sel, hist=True)
                        col_d1.download_button(
                            label="📄 Descargar PDF (Resumen)",
                            data=pdf_hist,
                            file_name=f"POD_{data_full['pod_code']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        # Botón Excel
                        df_items_hist = pd.DataFrame(data_full['trackings'], columns=['Tracking Code'])
                        xls_hist = to_excel_bytes(df_items_hist, 'xlsx')
                        col_d2.download_button(
                            label="📊 Descargar Excel (Detalle)",
                            data=xls_hist,
                            file_name=f"Lista_{data_full['pod_code']}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
            else:
                st.info("No se encontraron manifiestos con esos filtros.")
