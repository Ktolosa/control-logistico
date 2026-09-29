import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io
import json
import zipfile
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS COMPARTIDA ---
def init_proformas_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            try: cur.execute("ALTER TABLE facturas ADD COLUMN modulo VARCHAR(50) DEFAULT 'Finanzas';")
            except: pass
            try: cur.execute("ALTER TABLE facturas ADD COLUMN items_json TEXT DEFAULT NULL;")
            except: pass
            conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()

# --- 2. OBTENER LISTA DE CORRELATIVOS USADOS (PARA HUECOS Y LOTES) ---
def get_all_used_invoice_numbers():
    conn = get_connection()
    if not conn: return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT invoice_num FROM facturas")
        nums = [int(r[0]) for r in cur.fetchall() if r[0].isdigit()]
        conn.close()
        return nums
    except:
        if conn: conn.close()
        return []

# --- 3. GENERAR PDF (SOPORTA HASTA 10 FILAS) ---
def generar_proforma_pdf(tipo_factura, inv_num, fecha, cliente, direccion, items_df, subtotal, tax, otros, total):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_fill_color(22, 60, 115) 
    pdf.rect(0, 0, 210, 45, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 22)
    pdf.text(10, 15, "Global Cargo de El Salvador S.A. de C.V")
    
    pdf.set_font("Arial", '', 9)
    pdf.text(10, 25, "Zona industrial Plan de la Laguna")
    pdf.text(10, 30, "Calle Circunvalacion, Poligono D, Lote No. 7")
    pdf.text(10, 35, "Antiguo Cuscatlan, La Libertad El Salvador El Salvador")
    
    pdf.set_text_color(22, 60, 115)
    pdf.set_font("Arial", 'B', 16)
    pdf.text(10, 60, f"INVOICE # {inv_num}")
    
    pdf.text(150, 60, "Date:")
    pdf.set_text_color(0, 0, 0)
    fecha_str = fecha.strftime("%d-%b-%Y") if isinstance(fecha, datetime) else str(fecha)
    pdf.set_font("Arial", '', 12)
    pdf.text(150, 68, fecha_str)
    
    pdf.set_text_color(22, 60, 115)
    pdf.set_font("Arial", 'B', 16)
    pdf.text(10, 85, "Bill To")
    pdf.text(150, 85, "For")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.text(10, 93, str(cliente))
    pdf.set_font("Arial", '', 10)
    pdf.set_xy(9, 95)
    pdf.multi_cell(100, 5, str(direccion))
    
    pdf.set_xy(149, 90)
    pdf.cell(40, 5, "Per Package")
    
    # --- Tabla de Múltiples Filas (Hasta 10) ---
    pdf.set_y(120)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 11)
    
    pdf.cell(80, 8, "MAWB", 1, 0, 'C', True)
    pdf.cell(30, 8, "Parcel", 1, 0, 'C', True)
    pdf.cell(30, 8, "Price", 1, 0, 'C', True)
    pdf.cell(50, 8, "Amount", 1, 1, 'C', True)
    
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    
    filas_impresas = 0
    for index, row in items_df.iterrows():
        mawb = str(row.get("MAWB", ""))
        parcel = str(row.get("Parcel", "0"))
        price = float(row.get("Price", 0.0))
        amount = float(row.get("Amount", 0.0))
        
        if mawb.strip(): 
            pdf.cell(80, 8, mawb, 1, 0, 'C', True)
            pdf.cell(30, 8, parcel, 1, 0, 'C', True)
            pdf.cell(30, 8, f"${price:.2f}", 1, 0, 'C', True)
            pdf.cell(50, 8, f"${amount:,.2f}", 1, 1, 'C', True)
            filas_impresas += 1
    
    # Relleno estético para alcanzar 10 filas máximo
    for _ in range(max(0, 10 - filas_impresas)):
        pdf.cell(80, 8, "", 1, 0, 'L', False)
        pdf.cell(30, 8, "", 1, 0, 'L', False)
        pdf.cell(30, 8, "", 1, 0, 'L', False)
        pdf.cell(50, 8, "", 1, 1, 'C', False)
        
    pdf.ln(5)
    y_totales = pdf.get_y()
    
    pdf.set_y(y_totales)
    pdf.set_font("Arial", '', 9)
    pdf.cell(100, 5, "Make all checks payable to Company Name", ln=True)
    pdf.cell(100, 5, "If you have any questions concerning this invoice, use the following contact information:", ln=True)
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(100, 5, "Thank you for your business!", ln=True)
    
    pdf.set_y(y_totales)
    pdf.set_x(100)
    pdf.set_font("Arial", '', 11)
    
    pdf.cell(50, 8, "Subtotal", 0, 0, 'R')
    pdf.cell(50, 8, f"${subtotal:,.2f}", 1, 1, 'C')
    pdf.set_x(100)
    pdf.cell(50, 8, "Tax Rate", 0, 0, 'R')
    pdf.cell(50, 8, f"${tax:,.2f}", 1, 1, 'C')
    pdf.set_x(100)
    pdf.cell(50, 8, "Other Costs", 0, 0, 'R')
    pdf.cell(50, 8, f"${otros:,.2f}", 1, 1, 'C')
    
    pdf.set_x(100)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(50, 10, "Total Cost", 0, 0, 'R')
    pdf.cell(50, 10, f"${total:,.2f}", 1, 1, 'C', True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. CONFIGURACIÓN ---
CONFIG_PROFORMAS = {
    "CC service": {
        "cliente": "RADIANCE SEA HONG KONG LIMITED",
        "direccion": "United 417,4/f Lippo Ctr Tower Two, No. 89 Queensway Admiralty, Hong Kong.",
        "tax_rate": 0.00,
        "other_costs": 0.00,
        "default_price": 0.70
    },
    "Adimex": {
        "cliente": "ADIMEX LOGISTICS INC.",
        "direccion": "123 Supply Chain Blvd, Miami, FL 33166, USA.",
        "tax_rate": 0.00,
        "other_costs": 15.00,
        "default_price": 0.85
    }
}

# --- 5. INTERFAZ GRÁFICA ---
def show(user_info):
    init_proformas_db()
    st.title("📑 Proformas de Servicios")
    st.caption("Generación masiva con autocalculadora y separación en lotes de 10 filas.")
    
    t1, t2 = st.tabs(["Generación Masiva (Excel)", "Historial y Edición"])
    
    # ==========================================
    # PESTAÑA 1: INGRESO MASIVO (ÁREA DE PEGADO)
    # ==========================================
    with t1:
        c_tipo, c_blank = st.columns([1, 1])
        tipo_sel = c_tipo.selectbox("Tipo de Proforma:", list(CONFIG_PROFORMAS.keys()))
        cfg = CONFIG_PROFORMAS[tipo_sel]
        
        st.write("### 📥 Pegar datos desde Excel")
        st.info("Copia las 3 columnas de tu Excel y pégalas abajo. El orden debe ser: **MAWB 1 | MAWB 2 | Paquetes**")
        
        raw_text = st.text_area("Pegar aquí:", height=150, placeholder="172-05962036    810-51486680    1504\n369-10025153    729-95349380    1001")
        
        parsed_items = []
        if raw_text:
            lines = raw_text.strip().split('\n')
            for line in lines:
                cols = line.split('\t') # Al copiar de Excel, las celdas se separan por tabulaciones (\t)
                if len(cols) >= 3:
                    mawb = f"{cols[0].strip()}/{cols[1].strip()}"
                    try: parcel = int(cols[2].strip().replace(',', ''))
                    except: parcel = 0
                    
                    amount = parcel * cfg['default_price']
                    parsed_items.append({"MAWB": mawb, "Parcel": parcel, "Price": cfg['default_price'], "Amount": amount})
                elif len(cols) == 2:
                    # Por si solo copian los dos MAWBs y olvidan los paquetes
                    mawb = f"{cols[0].strip()}/{cols[1].strip()}"
                    parsed_items.append({"MAWB": mawb, "Parcel": 0, "Price": cfg['default_price'], "Amount": 0.0})

        if parsed_items:
            df_preview = pd.DataFrame(parsed_items)
            
            st.write("### 🔍 Vista Previa y Cálculo Automático")
            st.dataframe(df_preview, use_container_width=True)
            
            # Dividir en lotes de 10
            lotes = [parsed_items[i:i + 10] for i in range(0, len(parsed_items), 10)]
            
            st.success(f"✅ Se detectaron {len(parsed_items)} filas. Se generarán **{len(lotes)} Proformas** (máx 10 por PDF).")
            
            if st.button("🚀 Procesar Lote y Generar ZIP", type="primary"):
                with st.spinner("Calculando, dividiendo y empaquetando proformas..."):
                    ahora = datetime.now()
                    used_nums = get_all_used_invoice_numbers()
                    next_num = 46 # Lógica de inicio requerida
                    
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        conn = get_connection()
                        cur = conn.cursor()
                        
                        for lote in lotes:
                            # 1. Encontrar el siguiente número disponible
                            while next_num in used_nums:
                                next_num += 1
                            inv_num_str = f"{next_num:04d}"
                            used_nums.append(next_num) # Marcarlo como usado para el siguiente ciclo
                            
                            # 2. Cálculos del lote
                            df_lote = pd.DataFrame(lote)
                            subtotal = df_lote['Amount'].sum()
                            tax = cfg['tax_rate']
                            otros = cfg['other_costs']
                            total_lote = subtotal + tax + otros
                            cant_paq_lote = int(df_lote['Parcel'].sum())
                            items_json = df_lote.to_json(orient='records')
                            
                            # 3. Generar PDF
                            pdf_bytes = generar_proforma_pdf(
                                tipo_sel, inv_num_str, ahora, cfg['cliente'], cfg['direccion'], 
                                df_lote, subtotal, tax, otros, total_lote
                            )
                            
                            # 4. Guardar en BD
                            sql = """INSERT INTO facturas (modulo, tipo_factura, invoice_num, fecha, cliente, direccion, concepto, cantidad_paquetes, subtotal, tax_rate, other_costs, total, pdf_file, created_by, items_json) 
                                     VALUES ('Proformas', %s, %s, %s, %s, %s, 'Customs Clearance per Package', %s, %s, %s, %s, %s, %s, %s, %s)"""
                            cur.execute(sql, (tipo_sel, inv_num_str, ahora, cfg['cliente'], cfg['direccion'], cant_paq_lote, subtotal, tax, otros, total_lote, pdf_bytes, user_info['username'], items_json))
                            
                            # 5. Añadir al ZIP
                            zip_file.writestr(f"Proforma_{tipo_sel}_{inv_num_str}.pdf", pdf_bytes)
                            
                        conn.commit()
                        conn.close()
                    
                    st.success("¡Lote procesado y guardado en la Base de Datos con éxito!")
                    st.download_button(
                        label="⬇️ Descargar ZIP con todas las Proformas", 
                        data=zip_buffer.getvalue(), 
                        file_name=f"Lote_Proformas_{ahora.strftime('%Y%m%d_%H%M')}.zip", 
                        mime="application/zip",
                        type="primary"
                    )

    # ==========================================
    # PESTAÑA 2: HISTORIAL, EDICIÓN Y ELIMINACIÓN
    # ==========================================
    with t2:
        st.subheader("Gestión de Proformas")
        conn = get_connection()
        if conn:
            try:
                query = """
                    SELECT id, tipo_factura as 'Tipo', invoice_num as 'Invoice #', fecha as 'Fecha', 
                    cliente as 'Cliente', total as 'Total ($)', created_by as 'Creado Por', 
                    is_modified as 'Modificada', modified_by as 'Modif. Por', items_json 
                    FROM facturas WHERE modulo = 'Proformas' ORDER BY invoice_num DESC
                """
                df_fac = pd.read_sql(query, conn)
                
                if df_fac.empty:
                    st.info("No hay proformas generadas aún.")
                else:
                    df_display = df_fac.drop(columns=['items_json'])
                    df_display['Modificada'] = df_display['Modificada'].apply(lambda x: "⚠️ Sí" if x else "No")
                    st.dataframe(df_display, use_container_width=True)
                    
                    st.divider()
                    st.write("### 🛠️ Acciones")
                    
                    df_fac['Label'] = df_fac['Tipo'] + " - " + df_fac['Invoice #'] + " | " + df_fac['Cliente']
                    dic_map = dict(zip(df_fac['Label'], df_fac['id']))
                    
                    inv_sel_display = st.selectbox("Seleccione la proforma:", df_fac['Label'].tolist())
                    fac_id = dic_map[inv_sel_display]
                    
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT * FROM facturas WHERE id = %s", (fac_id,))
                    fac_data = cur.fetchone()
                    
                    if fac_data:
                        accion = st.radio("Acción:", ["⬇️ Descargar PDF", "✏️️ Editar Valores", "🗑️ Eliminar Proforma"], horizontal=True)
                        
                        if accion == "⬇️ Descargar PDF":
                            if fac_data['pdf_file']:
                                st.download_button("Descargar PDF", data=fac_data['pdf_file'], file_name=f"Proforma_{fac_data['invoice_num']}.pdf", mime="application/pdf", type="primary")
                        
                        elif accion == "🗑️ Eliminar Proforma":
                            st.warning(f"Eliminar proforma {fac_data['invoice_num']}. El correlativo será liberado globalmente y se rellenará en la próxima generación.")
                            if st.button("🚨 Confirmar Eliminación", type="primary"):
                                cur.execute("DELETE FROM facturas WHERE id = %s", (fac_id,))
                                conn.commit()
                                st.success("Eliminada.")
                                st.rerun()
                                
                        elif accion == "✏️ Editar Valores":
                            st.info("ℹ️ Edita los Paquetes o el Precio. Los totales se recalcularán automáticamente al guardar.")
                            
                            if fac_data['items_json']:
                                items_cargados = pd.DataFrame(json.loads(fac_data['items_json']))
                            else:
                                items_cargados = pd.DataFrame([{"MAWB": "", "Parcel": 0, "Price": 0.0, "Amount": 0.0}])
                                
                            edited_df_hist = st.data_editor(
                                items_cargados, 
                                num_rows="dynamic",
                                column_config={
                                    "MAWB": st.column_config.TextColumn("MAWB", width="large"),
                                    "Parcel": st.column_config.NumberColumn("Parcel", min_value=0, step=1),
                                    "Price": st.column_config.NumberColumn("Price ($)", min_value=0.0, format="$%.2f"),
                                    "Amount": st.column_config.NumberColumn("Amount ($) [Ignorar, se autocalcula]", disabled=True)
                                },
                                use_container_width=True,
                                key="table_edit_proforma"
                            )
                            
                            # Recálculo forzado en backend
                            edited_df_hist['Amount'] = edited_df_hist['Parcel'] * edited_df_hist['Price']
                            edit_cant = int(edited_df_hist['Parcel'].sum())
                            edit_sub = float(edited_df_hist['Amount'].sum())
                            
                            m1, m2, m3 = st.columns(3)
                            edit_tax = m1.number_input("Tax Rate", value=float(fac_data['tax_rate']), step=0.01, key="e_tax")
                            edit_otros = m2.number_input("Other Costs", value=float(fac_data['other_costs']), step=0.01, key="e_other")
                            
                            nuevo_total = edit_sub + edit_tax + edit_otros
                            
                            # Mostrar totales calculados en tiempo real antes de guardar
                            m3.markdown(f"**Subtotal Recalculado:**<br>${edit_sub:,.2f}", unsafe_allow_html=True)
                            st.write(f"### Nuevo Total Factura: ${nuevo_total:,.2f}")
                            
                            if st.button("💾 Guardar Cambios y Regenerar PDF", type="primary"):
                                with st.spinner("Actualizando..."):
                                    nuevo_json = edited_df_hist.to_json(orient='records')
                                    nuevo_pdf = generar_proforma_pdf(
                                        fac_data['tipo_factura'], fac_data['invoice_num'], fac_data['fecha'], 
                                        fac_data['cliente'], fac_data['direccion'], edited_df_hist, 
                                        edit_sub, edit_tax, edit_otros, nuevo_total
                                    )
                                    
                                    update_sql = """
                                        UPDATE facturas SET 
                                            cantidad_paquetes=%s, subtotal=%s, tax_rate=%s, other_costs=%s, total=%s, 
                                            pdf_file=%s, is_modified=1, modified_by=%s, items_json=%s 
                                        WHERE id=%s
                                    """
                                    cur.execute(update_sql, (
                                        edit_cant, edit_sub, edit_tax, edit_otros, nuevo_total, 
                                        nuevo_pdf, user_info['username'], nuevo_json, fac_id
                                    ))
                                    conn.commit()
                                    st.success("Proforma actualizada.")
                                    st.rerun()
            finally:
                conn.close()
