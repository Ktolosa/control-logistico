import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io
import json
import zipfile
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS ---
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

# --- 2. GENERAR PDF DINÁMICO ---
def generar_proforma_pdf(tipo_factura, inv_num, fecha, cliente, direccion, items_df, subtotal, tax, otros, total, col1_name, col2_name):
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
    # Etiqueta bajo 'For'
    label_for = "Per KG" if tipo_factura == "Adimex" else "Per Package"
    if col1_name == "Description": label_for = "Custom Service" # Para manual
    pdf.cell(40, 5, label_for)
    
    # --- Tabla Dinámica ---
    pdf.set_y(120)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 11)
    
    pdf.cell(80, 8, col1_name, 1, 0, 'C', True)
    pdf.cell(30, 8, col2_name, 1, 0, 'C', True)
    pdf.cell(30, 8, "Price", 1, 0, 'C', True)
    pdf.cell(50, 8, "Amount", 1, 1, 'C', True)
    
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    
    filas_impresas = 0
    for index, row in items_df.iterrows():
        c1_val = str(row.get("Col1", ""))
        c2_val = str(row.get("Col2", "0"))
        price = float(row.get("Price", 0.0))
        amount = float(row.get("Amount", 0.0))
        
        if c1_val.strip(): 
            pdf.cell(80, 8, c1_val[:45], 1, 0, 'C', True) # Truncado por seguridad
            pdf.cell(30, 8, c2_val, 1, 0, 'C', True)
            pdf.cell(30, 8, f"${price:,.2f}", 1, 0, 'C', True)
            pdf.cell(50, 8, f"${amount:,.2f}", 1, 1, 'C', True)
            filas_impresas += 1
    
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

# --- 3. CONFIGURACIÓN ---
CONFIG_PROFORMAS = {
    "CC service": {
        "cliente": "RADIANCE SEA HONG KONG LIMITED",
        "direccion": "United 417,4/f Lippo Ctr Tower Two, No. 89 Queensway Admiralty, Hong Kong.",
        "tax_rate": 0.00,
        "other_costs": 0.00,
        "default_price": 0.70,
        "col1": "MAWB",
        "col2": "Parcel"
    },
    "Adimex": {
        "cliente": "ADIMEX LOGISTICS INC.",
        "direccion": "123 Supply Chain Blvd, Miami, FL 33166, USA.",
        "tax_rate": 0.00,
        "other_costs": 15.00,
        "default_price": 0.35, # Tarifa por KG
        "col1": "Masters",
        "col2": "KG"
    }
}

# --- 4. INTERFAZ GRÁFICA ---
def show(user_info):
    init_proformas_db()
    st.title("📑 Proformas de Servicios")
    st.caption("Generación con correlativo manual, formatos adaptables y gestión en bloque.")
    
    t1, t2 = st.tabs(["Generación de Proformas", "Historial (Edición y Borrado Masivo)"])
    
    # ==========================================
    # PESTAÑA 1: GENERACIÓN
    # ==========================================
    with t1:
        c_tipo, c_corr = st.columns([1, 1])
        tipo_sel = c_tipo.selectbox("Tipo de Proforma:", list(CONFIG_PROFORMAS.keys()))
        cfg = CONFIG_PROFORMAS[tipo_sel]
        
        # Correlativo Manual
        inv_start = c_corr.number_input("Correlativo Inicial (Ej. 46)", min_value=1, value=46, step=1)
        
        modo = "Masivo (Excel)"
        if tipo_sel == "CC service":
            modo = st.radio("Modo de Ingreso:", ["Masivo (Excel)", "Manual (Detalle y Monto Exacto)"], horizontal=True)

        parsed_items = []
        lotes = []
        is_manual = (modo == "Manual (Detalle y Monto Exacto)")
        
        if is_manual:
            st.info("Ingresa el detalle personalizado a facturar en una sola línea.")
            det_manual = st.text_input("Detalle a facturar")
            monto_manual = st.number_input("Monto Total Exacto ($)", min_value=0.0, step=0.01)
            
            if det_manual and monto_manual > 0:
                parsed_items = [{"Col1": det_manual, "Col2": "1", "Price": monto_manual, "Amount": monto_manual}]
                lotes = [parsed_items]
                df_preview = pd.DataFrame(parsed_items)
                st.dataframe(df_preview, use_container_width=True)
                
        else: # MODO MASIVO EXCEL (Para CC Service y Adimex)
            st.write(f"### 📥 Pegar datos desde Excel")
            st.info(f"Pega 3 columnas: **{cfg['col1']} 1 | {cfg['col1']} 2 | {cfg['col2']}**")
            
            raw_text = st.text_area("Pegar aquí:", height=150)
            
            if raw_text:
                lines = raw_text.strip().split('\n')
                for line in lines:
                    cols = line.split('\t')
                    if len(cols) >= 3:
                        c1_str = f"{cols[0].strip()}/{cols[1].strip()}"
                        try: c2_val = float(cols[2].strip().replace(',', ''))
                        except: c2_val = 0.0
                        
                        amount = c2_val * cfg['default_price']
                        # Normalizamos a 'Col1' y 'Col2' para el PDF general
                        parsed_items.append({"Col1": c1_str, "Col2": c2_val, "Price": cfg['default_price'], "Amount": amount})
                        
                if parsed_items:
                    df_preview = pd.DataFrame(parsed_items)
                    df_preview.columns = [cfg['col1'], cfg['col2'], "Price", "Amount"] # Mostrar real
                    st.write("### 🔍 Vista Previa")
                    st.dataframe(df_preview, use_container_width=True)
                    
                    lotes = [parsed_items[i:i + 10] for i in range(0, len(parsed_items), 10)]
                    st.success(f"✅ Detectadas {len(parsed_items)} filas. Se generarán **{len(lotes)} Proformas**.")

        if parsed_items and st.button("🚀 Generar Proforma(s)", type="primary"):
            with st.spinner("Procesando..."):
                ahora = datetime.now()
                current_inv = inv_start
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    conn = get_connection()
                    cur = conn.cursor()
                    
                    for lote in lotes:
                        inv_num_str = f"{current_inv:04d}"
                        
                        df_lote = pd.DataFrame(lote)
                        subtotal = df_lote['Amount'].sum()
                        tax = cfg['tax_rate']
                        otros = cfg['other_costs']
                        total_lote = subtotal + tax + otros
                        
                        # Definir cabeceras reales para el PDF
                        pdf_col1 = "Description" if is_manual else cfg['col1']
                        pdf_col2 = "Qty" if is_manual else cfg['col2']
                        
                        pdf_bytes = generar_proforma_pdf(
                            tipo_sel, inv_num_str, ahora, cfg['cliente'], cfg['direccion'], 
                            df_lote, subtotal, tax, otros, total_lote, pdf_col1, pdf_col2
                        )
                        
                        items_json = df_lote.to_json(orient='records')
                        # Solo sumamos la cantidad para estadística si no es modo manual
                        cant_global = 1 if is_manual else int(df_lote['Col2'].sum())
                        
                        sql = """INSERT INTO facturas (modulo, tipo_factura, invoice_num, fecha, cliente, direccion, concepto, cantidad_paquetes, subtotal, tax_rate, other_costs, total, pdf_file, created_by, items_json) 
                                 VALUES ('Proformas', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                        concepto_bd = "Manual Service" if is_manual else f"{cfg['col1']} Billing"
                        cur.execute(sql, (tipo_sel, inv_num_str, ahora, cfg['cliente'], cfg['direccion'], concepto_bd, cant_global, subtotal, tax, otros, total_lote, pdf_bytes, user_info['username'], items_json))
                        
                        # Si es 1 sola, la preparamos suelta, si son varias, van al ZIP
                        zip_file.writestr(f"Proforma_{tipo_sel}_{inv_num_str}.pdf", pdf_bytes)
                        
                        current_inv += 1
                        
                    conn.commit()
                    conn.close()
                
                st.success("¡Generación completada!")
                if len(lotes) == 1:
                    st.download_button("⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Proforma_{tipo_sel}_{inv_start:04d}.pdf", mime="application/pdf", type="primary")
                else:
                    st.download_button("⬇️ Descargar ZIP (Lote completo)", data=zip_buffer.getvalue(), file_name=f"Lote_{tipo_sel}_{inv_start:04d}_al_{current_inv-1:04d}.zip", mime="application/zip", type="primary")

    # ==========================================
    # PESTAÑA 2: HISTORIAL Y BORRADO MASIVO
    # ==========================================
    with t2:
        st.subheader("Gestión de Proformas")
        conn = get_connection()
        if conn:
            try:
                query = """
                    SELECT id, tipo_factura as 'Tipo', invoice_num as 'Invoice #', fecha as 'Fecha', 
                    cliente as 'Cliente', total as 'Total ($)', created_by as 'Creado Por', 
                    is_modified as 'Modif', pdf_file, items_json 
                    FROM facturas WHERE modulo = 'Proformas' ORDER BY invoice_num DESC
                """
                df_fac = pd.read_sql(query, conn)
                
                if df_fac.empty:
                    st.info("No hay proformas generadas aún.")
                else:
                    # Mostrar tabla con checkboxes (Select)
                    df_display = df_fac.drop(columns=['pdf_file', 'items_json', 'id'])
                    df_display['Modif'] = df_display['Modif'].apply(lambda x: "Sí" if x else "No")
                    df_display.insert(0, "Seleccionar", False)
                    
                    st.write("**Selecciona las proformas para borrar o descarga individualmente:**")
                    edited_df = st.data_editor(
                        df_display, 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={"Seleccionar": st.column_config.CheckboxColumn("Eliminar", required=True)}
                    )
                    
                    selected_indices = edited_df[edited_df['Seleccionar']].index.tolist()
                    
                    c_del, c_down = st.columns(2)
                    
                    # Acción 1: Borrado Masivo
                    if selected_indices:
                        ids_to_delete = df_fac.iloc[selected_indices]['id'].tolist()
                        c_del.warning(f"Has seleccionado {len(ids_to_delete)} proformas.")
                        if c_del.button("🚨 Eliminar Seleccionadas", type="primary"):
                            cur = conn.cursor()
                            format_strings = ','.join(['%s'] * len(ids_to_delete))
                            cur.execute(f"DELETE FROM facturas WHERE id IN ({format_strings})", tuple(ids_to_delete))
                            conn.commit()
                            st.success("Proformas eliminadas con éxito.")
                            st.rerun()
                    
                    # Acción 2: Descargar individual
                    st.divider()
                    st.write("### ⬇️ Descargar Individual o Editar")
                    df_fac['Label'] = df_fac['Tipo'] + " - " + df_fac['Invoice #'] + " | $" + df_fac['Total ($)'].astype(str)
                    dic_map = dict(zip(df_fac['Label'], df_fac['id']))
                    
                    inv_sel_display = st.selectbox("Seleccione una proforma para acciones individuales:", df_fac['Label'].tolist())
                    fac_id = dic_map[inv_sel_display]
                    
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT * FROM facturas WHERE id = %s", (fac_id,))
                    fac_data = cur.fetchone()
                    
                    if fac_data and fac_data['pdf_file']:
                        c_down.download_button(
                            label=f"⬇️ Descargar PDF ({fac_data['invoice_num']})", 
                            data=fac_data['pdf_file'], 
                            file_name=f"Proforma_{fac_data['tipo_factura']}_{fac_data['invoice_num']}.pdf", 
                            mime="application/pdf"
                        )
            finally:
                conn.close()
