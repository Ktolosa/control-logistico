import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io
import json
from utils import get_connection

# --- 1. INICIALIZAR/ACTUALIZAR BASE DE DATOS COMPARTIDA ---
def init_proformas_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Añadimos columnas nuevas a la tabla facturas para soportar el formato de Proformas
            try: cur.execute("ALTER TABLE facturas ADD COLUMN modulo VARCHAR(50) DEFAULT 'Finanzas';")
            except: pass
            try: cur.execute("ALTER TABLE facturas ADD COLUMN items_json TEXT DEFAULT NULL;")
            except: pass
            conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()

# --- 2. OBTENER CORRELATIVO COMPARTIDO GLOBAL ---
def get_shared_invoice_number():
    conn = get_connection()
    if not conn: return "0046"
    try:
        cur = conn.cursor()
        # Seleccionamos TODOS los invoice_num sin importar el tipo o módulo
        cur.execute("SELECT invoice_num FROM facturas")
        numeros_usados = [int(r[0]) for r in cur.fetchall() if r[0].isdigit()]
        conn.close()
        
        next_num = 46 
        while next_num in numeros_usados:
            next_num += 1
            
        return f"{next_num:04d}" 
    except:
        if conn: conn.close()
        return "0046"

# --- 3. GENERAR PDF (FORMATO PROFORMAS CON TABLA) ---
def generar_proforma_pdf(tipo_factura, inv_num, fecha, cliente, direccion, items_df, subtotal, tax, otros, total):
    pdf = FPDF()
    pdf.add_page()
    
    # --- Encabezado Azul ---
    pdf.set_fill_color(22, 60, 115) 
    pdf.rect(0, 0, 210, 45, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 22)
    pdf.text(10, 15, "Global Cargo de El Salvador S.A. de C.V")
    
    pdf.set_font("Arial", '', 9)
    pdf.text(10, 25, "Zona industrial Plan de la Laguna")
    pdf.text(10, 30, "Calle Circunvalacion, Poligono D, Lote No. 7")
    pdf.text(10, 35, "Antiguo Cuscatlan, La Libertad El Salvador El Salvador")
    
    # --- Metadatos (Invoice # y Fecha) ---
    pdf.set_text_color(22, 60, 115)
    pdf.set_font("Arial", 'B', 16)
    pdf.text(10, 60, f"INVOICE # {inv_num}")
    
    pdf.text(150, 60, "Date:")
    pdf.set_text_color(0, 0, 0)
    fecha_str = fecha.strftime("%d-%b-%Y") if isinstance(fecha, datetime) else str(fecha)
    pdf.set_font("Arial", '', 12)
    pdf.text(150, 68, fecha_str)
    
    # --- Bill To y For ---
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
    
    # Extraemos el texto "Per Package" que pide el formato
    pdf.set_xy(149, 90)
    pdf.cell(40, 5, "Per Package")
    
    # --- Tabla de Múltiples Filas ---
    pdf.set_y(120)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 11)
    
    # Cabeceras de tabla
    pdf.cell(80, 8, "MAWB", 1, 0, 'C', True)
    pdf.cell(30, 8, "Parcel", 1, 0, 'C', True)
    pdf.cell(30, 8, "Price", 1, 0, 'C', True)
    pdf.cell(50, 8, "Amount", 1, 1, 'C', True)
    
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    
    # Dibujar filas dinámicamente
    for index, row in items_df.iterrows():
        mawb = str(row.get("MAWB", ""))
        parcel = str(row.get("Parcel", "0"))
        price = float(row.get("Price", 0.0))
        amount = float(row.get("Amount", 0.0))
        
        if mawb.strip(): # Solo imprimir si la fila tiene datos
            pdf.cell(80, 8, mawb, 1, 0, 'C', True)
            pdf.cell(30, 8, parcel, 1, 0, 'C', True)
            pdf.cell(30, 8, f"${price:.2f}", 1, 0, 'C', True)
            pdf.cell(50, 8, f"${amount:,.2f}", 1, 1, 'C', True)
    
    # Relleno estético para alcanzar altura mínima de tabla si hay pocas filas
    filas_impresas = len([x for x in items_df['MAWB'] if str(x).strip()])
    for _ in range(max(0, 5 - filas_impresas)):
        pdf.cell(80, 8, "", 1, 0, 'L', False)
        pdf.cell(30, 8, "", 1, 0, 'L', False)
        pdf.cell(30, 8, "", 1, 0, 'L', False)
        pdf.cell(50, 8, "", 1, 1, 'C', False)
        
    # --- Totales ---
    pdf.ln(5)
    y_totales = pdf.get_y()
    
    # Notas al pie (Lado izquierdo)
    pdf.set_y(y_totales)
    pdf.set_font("Arial", '', 9)
    pdf.cell(100, 5, "Make all checks payable to Company Name", ln=True)
    pdf.cell(100, 5, "If you have any questions concerning this invoice, use the following contact information:", ln=True)
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(100, 5, "Thank you for your business!", ln=True)
    
    # Cuadros de Totales (Lado derecho)
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

# --- 4. CONFIGURACIÓN DE PROFORMAS ---
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
    st.caption("Módulo de facturación por paquete (Compartiendo correlativo con Finanzas)")
    
    t1, t2 = st.tabs(["Generar Proforma", "Historial y Edición"])
    
    with t1:
        st.subheader("Configuración")
        c_tipo, c_blank = st.columns([1, 1])
        tipo_sel = c_tipo.selectbox("Tipo de Proforma:", list(CONFIG_PROFORMAS.keys()))
        cfg = CONFIG_PROFORMAS[tipo_sel]
        
        c1, c2 = st.columns(2)
        inv_auto = get_shared_invoice_number() # Función compartida
        
        with c1:
            st.info(f"**Próximo Correlativo Global:** {inv_auto}")
            cliente = st.text_input("Cliente (Bill To)", value=cfg["cliente"], disabled=True, key="p_cli")
            direccion = st.text_area("Dirección del Cliente", value=cfg["direccion"], disabled=True, key="p_dir")
            
        with c2:
            st.write("**Detalle de MAWB y Paquetes**")
            st.caption("El 'Amount' se calcula automáticamente (Parcel x Price)")
            
            # Tabla editable para ingresar los MAWBs
            default_data = pd.DataFrame([{"MAWB": "", "Parcel": 0, "Price": cfg["default_price"], "Amount": 0.0} for _ in range(5)])
            
            edited_df = st.data_editor(
                default_data, 
                num_rows="dynamic",
                column_config={
                    "MAWB": st.column_config.TextColumn("MAWB", width="large"),
                    "Parcel": st.column_config.NumberColumn("Parcel", min_value=0, step=1),
                    "Price": st.column_config.NumberColumn("Price ($)", min_value=0.0, format="$%.2f"),
                    "Amount": st.column_config.NumberColumn("Amount ($)", disabled=True, format="$%.2f")
                },
                use_container_width=True,
                key="table_new_proforma"
            )
            
            # Autocalcular la columna Amount y el total de paquetes
            edited_df['Amount'] = edited_df['Parcel'] * edited_df['Price']
            cant_paq = int(edited_df['Parcel'].sum())
            subtotal_calc = float(edited_df['Amount'].sum())

        st.divider()
        st.subheader("Desglose Financiero")
        c3, c4, c5 = st.columns(3)
        st.markdown(f"**Total Paquetes:** {cant_paq}")
        
        subtotal = c3.number_input("Subtotal ($) - Autocalculado", value=subtotal_calc, disabled=True, key="p_sub")
        tax = c4.number_input("Tax Rate ($)", value=cfg["tax_rate"], disabled=True, key="p_tax")
        otros = c5.number_input("Other Costs ($)", value=cfg["other_costs"], disabled=True, key="p_other")
        
        total_calc = subtotal + tax + otros
        st.markdown(f"### Total Proforma: <span style='color:green;'>${total_calc:,.2f}</span>", unsafe_allow_html=True)
        
        if st.button("💾 Generar y Guardar Proforma", type="primary"):
            if total_calc <= 0:
                st.error("El total debe ser mayor a $0")
            elif cant_paq <= 0:
                st.error("Debes ingresar al menos un Parcel válido")
            else:
                with st.spinner("Generando PDF y guardando..."):
                    ahora = datetime.now()
                    items_json = edited_df.to_json(orient='records')
                    
                    pdf_bytes = generar_proforma_pdf(tipo_sel, inv_auto, ahora, cliente, direccion, edited_df, subtotal, tax, otros, total_calc)
                    
                    conn = get_connection()
                    if conn:
                        try:
                            cur = conn.cursor()
                            sql = """INSERT INTO facturas (modulo, tipo_factura, invoice_num, fecha, cliente, direccion, concepto, cantidad_paquetes, subtotal, tax_rate, other_costs, total, pdf_file, created_by, items_json) 
                                     VALUES ('Proformas', %s, %s, %s, %s, %s, 'Customs Clearance per Package', %s, %s, %s, %s, %s, %s, %s, %s)"""
                            cur.execute(sql, (tipo_sel, inv_auto, ahora, cliente, direccion, cant_paq, subtotal, tax, otros, total_calc, pdf_bytes, user_info['username'], items_json))
                            conn.commit()
                            st.success(f"Proforma #{inv_auto} ({tipo_sel}) generada exitosamente.")
                            st.download_button("⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Proforma_{tipo_sel}_{inv_auto}.pdf", mime="application/pdf")
                        except Exception as e:
                            st.error(f"Error BD: {e}")
                        finally:
                            conn.close()

    with t2:
        st.subheader("Gestión de Proformas")
        conn = get_connection()
        if conn:
            try:
                # Solo cargamos las que pertenecen a este módulo
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
                        accion = st.radio("Acción:", ["⬇️ Descargar PDF", "✏️ Editar Valores", "🗑️ Eliminar Proforma"], horizontal=True)
                        
                        if accion == "⬇️ Descargar PDF":
                            if fac_data['pdf_file']:
                                st.download_button("Descargar PDF", data=fac_data['pdf_file'], file_name=f"Proforma_{fac_data['invoice_num']}.pdf", mime="application/pdf", type="primary")
                        
                        elif accion == "🗑️ Eliminar Proforma":
                            st.warning(f"Eliminar proforma {fac_data['invoice_num']}. El correlativo será liberado globalmente.")
                            if st.button("🚨 Confirmar Eliminación", type="primary"):
                                cur.execute("DELETE FROM facturas WHERE id = %s", (fac_id,))
                                conn.commit()
                                st.success("Eliminada.")
                                st.rerun()
                                
                        elif accion == "✏️ Editar Valores":
                            st.info("ℹ️ Edita la tabla de MAWBs. El recálculo es automático.")
                            
                            # Recuperar los items guardados en JSON
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
                                    "Amount": st.column_config.NumberColumn("Amount ($)", disabled=True, format="$%.2f")
                                },
                                use_container_width=True,
                                key="table_edit_proforma"
                            )
                            
                            edited_df_hist['Amount'] = edited_df_hist['Parcel'] * edited_df_hist['Price']
                            edit_cant = int(edited_df_hist['Parcel'].sum())
                            edit_sub = float(edited_df_hist['Amount'].sum())
                            
                            m1, m2, m3 = st.columns(3)
                            st.write(f"**Subtotal Calculado:** ${edit_sub:,.2f}")
                            edit_tax = m2.number_input("Tax Rate", value=float(fac_data['tax_rate']), step=0.01, key="e_tax")
                            edit_otros = m3.number_input("Other Costs", value=float(fac_data['other_costs']), step=0.01, key="e_other")
                            
                            nuevo_total = edit_sub + edit_tax + edit_otros
                            st.write(f"**Nuevo Total:** ${nuevo_total:,.2f}")
                            
                            if st.button("💾 Guardar Cambios y Regenerar", type="primary"):
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
