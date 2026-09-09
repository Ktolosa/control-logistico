import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS ---
def init_finanzas_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS facturas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tipo_factura VARCHAR(50) NOT NULL,
                    invoice_num VARCHAR(20) NOT NULL,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cliente VARCHAR(255),
                    direccion TEXT,
                    concepto TEXT,
                    cantidad_paquetes INT,
                    subtotal DECIMAL(10,2),
                    tax_rate DECIMAL(10,2),
                    other_costs DECIMAL(10,2),
                    total DECIMAL(10,2),
                    pdf_file LONGBLOB,
                    created_by VARCHAR(100),
                    is_modified BOOLEAN DEFAULT FALSE,
                    modified_by VARCHAR(100) DEFAULT NULL,
                    UNIQUE KEY unique_tipo_inv (tipo_factura, invoice_num)
                );
            """)
            
            # Migraciones seguras para tablas existentes
            try: cur.execute("ALTER TABLE facturas ADD COLUMN tipo_factura VARCHAR(50) DEFAULT 'Funds' AFTER id;")
            except: pass
            try: cur.execute("ALTER TABLE facturas DROP INDEX invoice_num;")
            except: pass
            try: cur.execute("ALTER TABLE facturas ADD UNIQUE KEY unique_tipo_inv (tipo_factura, invoice_num);")
            except: pass
            try: cur.execute("ALTER TABLE facturas ADD COLUMN is_modified BOOLEAN DEFAULT FALSE;")
            except: pass
            try: cur.execute("ALTER TABLE facturas ADD COLUMN modified_by VARCHAR(100) DEFAULT NULL;")
            except: pass
                
            conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()

# --- 2. OBTENER SIGUIENTE CORRELATIVO (LÓGICA DE HUECOS) ---
def get_next_invoice_number(tipo_factura):
    conn = get_connection()
    if not conn: return "0046"
    try:
        cur = conn.cursor()
        cur.execute("SELECT invoice_num FROM facturas WHERE tipo_factura = %s", (tipo_factura,))
        # Extraemos los números usados y los convertimos a enteros
        numeros_usados = [int(r[0]) for r in cur.fetchall() if r[0].isdigit()]
        conn.close()
        
        # El requerimiento dice empezar desde el 46
        next_num = 46 
        
        # Busca el primer número que NO esté en la lista de usados
        while next_num in numeros_usados:
            next_num += 1
            
        return f"{next_num:04d}" 
    except:
        if conn: conn.close()
        return "0046"

# --- 3. GENERAR PDF ---
def generar_factura_pdf(tipo_factura, inv_num, fecha, cliente, direccion, concepto, cant_paq, subtotal, tax, otros, total):
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
    
    # Si la fecha es un string (desde BD) o datetime
    if isinstance(fecha, str):
        try: fecha = datetime.strptime(fecha, '%Y-%m-%d %H:%M:%S')
        except: pass
    
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
    pdf.cell(40, 5, str(tipo_factura))
    
    pdf.set_y(120)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 11)
    
    pdf.cell(140, 8, "Item Description", 1, 0, 'C', True)
    pdf.cell(50, 8, "Amount", 1, 1, 'C', True)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    
    desc_completa = f"{concepto} ({cant_paq}pq)"
    pdf.cell(140, 8, desc_completa, 1, 0, 'L', True)
    pdf.cell(50, 8, f"${total:,.2f}", 1, 1, 'C', True)
    
    for _ in range(4):
        pdf.cell(140, 8, "", 1, 0, 'L', False)
        pdf.cell(50, 8, "", 1, 1, 'C', False)
        
    pdf.ln(10)
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

# --- 4. CONFIGURACIÓN DE TIPOS DE FACTURA ---
CONFIG_TIPOS = {
    "Funds": {
        "cliente": "RADIANCE SEA HONG KONG LIMITED",
        "direccion": "United 417,4/f Lippo Ctr Tower Two, No. 89 Queensway Admiralty, Hong Kong.",
        "tax_rate": 0.00,
        "other_costs": 0.00
    },
    "Logistics": {
        "cliente": "LOGISTICS PARTNER S.A.",
        "direccion": "Av. Logística 123, Ciudad de Prueba, El Salvador.",
        "tax_rate": 0.00,
        "other_costs": 15.50
    },
    "Customs": {
        "cliente": "AGENCIA ADUANAL S.A. DE C.V.",
        "direccion": "Aduana Marítima, Edificio 4, Acajutla.",
        "tax_rate": 13.00,
        "other_costs": 5.00
    },
    "Storage": {
        "cliente": "ALMACENADORA GLOBAL",
        "direccion": "Bodega 9, Zona Industrial Plan de la Laguna.",
        "tax_rate": 0.00,
        "other_costs": 0.00
    }
}

# --- 5. INTERFAZ GRÁFICA ---
def show(user_info):
    init_finanzas_db()
    st.title("💰 Finanzas y Facturación")
    
    t1, t2 = st.tabs(["Generar Nueva Factura", "Historial y Edición"])
    
    # ==========================================
    # PESTAÑA 1: GENERAR NUEVA
    # ==========================================
    with t1:
        st.subheader("Configuración y Detalles")
        
        c_tipo, c_blank = st.columns([1, 1])
        lista_tipos = list(CONFIG_TIPOS.keys())
        tipo_sel = c_tipo.selectbox("Tipo de Factura (Campo 'For'):", lista_tipos)
        
        cfg = CONFIG_TIPOS[tipo_sel]
        
        c1, c2 = st.columns(2)
        inv_auto = get_next_invoice_number(tipo_sel)
        
        with c1:
            st.info(f"**Próximo Invoice # para {tipo_sel}:** {inv_auto}")
            cliente = st.text_input("Cliente (Bill To)", value=cfg["cliente"], disabled=True)
            direccion = st.text_area("Dirección del Cliente", value=cfg["direccion"], disabled=True)
        
        with c2:
            st.write("Datos del Cobro")
            concepto = st.text_input("Descripción del Servicio", value="Tax payment for packages as per detail")
            cant_paq = st.number_input("Cantidad de Paquetes (pq)", min_value=1, step=1)
            
        st.divider()
        st.subheader("Desglose Financiero")
        c3, c4, c5 = st.columns(3)
        subtotal = c3.number_input("Subtotal ($)", min_value=0.0, step=0.01)
        tax = c4.number_input("Tax Rate ($)", value=cfg["tax_rate"], disabled=True)
        otros = c5.number_input("Other Costs ($)", value=cfg["other_costs"], disabled=True)
        
        total_calc = subtotal + tax + otros
        st.markdown(f"### Total Calculado: <span style='color:green;'>${total_calc:,.2f}</span>", unsafe_allow_html=True)
        
        if st.button("💾 Generar y Guardar Factura", type="primary"):
            if total_calc <= 0:
                st.error("El total de la factura debe ser mayor a $0.00")
            else:
                with st.spinner("Generando PDF y guardando..."):
                    ahora = datetime.now()
                    pdf_bytes = generar_factura_pdf(tipo_sel, inv_auto, ahora, cliente, direccion, concepto, cant_paq, subtotal, tax, otros, total_calc)
                    
                    conn = get_connection()
                    if conn:
                        try:
                            cur = conn.cursor()
                            sql = """INSERT INTO facturas (tipo_factura, invoice_num, fecha, cliente, direccion, concepto, cantidad_paquetes, subtotal, tax_rate, other_costs, total, pdf_file, created_by) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                            cur.execute(sql, (tipo_sel, inv_auto, ahora, cliente, direccion, concepto, cant_paq, subtotal, tax, otros, total_calc, pdf_bytes, user_info['username']))
                            conn.commit()
                            st.success(f"Factura #{inv_auto} ({tipo_sel}) generada exitosamente.")
                            st.download_button("⬇️ Descargar PDF Ahora", data=pdf_bytes, file_name=f"Invoice_{tipo_sel}_{inv_auto}.pdf", mime="application/pdf")
                        except Exception as e:
                            st.error(f"Error al guardar en base de datos: {e}")
                        finally:
                            conn.close()
    
    # ==========================================
    # PESTAÑA 2: HISTORIAL, EDICIÓN Y ELIMINACIÓN
    # ==========================================
    with t2:
        st.subheader("Gestión de Invoices")
        conn = get_connection()
        if conn:
            try:
                # Obtenemos los datos incluyendo los nuevos campos de auditoría
                query = """
                    SELECT id, tipo_factura as 'Tipo', invoice_num as 'Invoice #', fecha as 'Fecha', 
                    cliente as 'Cliente', total as 'Total ($)', created_by as 'Creado Por', 
                    is_modified as 'Modificada', modified_by as 'Modif. Por' 
                    FROM facturas ORDER BY tipo_factura, invoice_num DESC
                """
                df_fac = pd.read_sql(query, conn)
                
                if df_fac.empty:
                    st.info("No hay facturas generadas aún.")
                else:
                    # Damos formato visual a la columna 'Modificada'
                    df_fac['Modificada'] = df_fac['Modificada'].apply(lambda x: "⚠️ Sí" if x else "No")
                    st.dataframe(df_fac, use_container_width=True)
                    
                    st.divider()
                    st.write("### 🛠️ Acciones de Factura")
                    
                    # Selector unificado
                    df_fac['Label'] = df_fac['Tipo'] + " - " + df_fac['Invoice #'] + " | " + df_fac['Cliente']
                    dic_map = dict(zip(df_fac['Label'], df_fac['id']))
                    
                    inv_sel_display = st.selectbox("Seleccione la factura que desea gestionar:", df_fac['Label'].tolist())
                    fac_id = dic_map[inv_sel_display]
                    
                    # Extraer datos específicos de la factura seleccionada
                    cur = conn.cursor(dictionary=True)
                    cur.execute("SELECT * FROM facturas WHERE id = %s", (fac_id,))
                    fac_data = cur.fetchone()
                    
                    if fac_data:
                        acc1, acc2, acc3 = st.columns(3)
                        accion = st.radio("¿Qué desea hacer con esta factura?", ["⬇️ Descargar PDF", "✏️ Editar Valores", "🗑️ Eliminar Factura"], horizontal=True)
                        
                        # --- ACCIÓN: DESCARGAR ---
                        if accion == "⬇️ Descargar PDF":
                            if fac_data['pdf_file']:
                                st.download_button(
                                    label=f"Descargar Invoice {fac_data['invoice_num']}", 
                                    data=fac_data['pdf_file'], 
                                    file_name=f"Invoice_{fac_data['tipo_factura']}_{fac_data['invoice_num']}.pdf", 
                                    mime="application/pdf",
                                    type="primary"
                                )
                        
                        # --- ACCIÓN: ELIMINAR ---
                        elif accion == "🗑️ Eliminar Factura":
                            st.warning(f"Está a punto de eliminar la factura {fac_data['tipo_factura']} - {fac_data['invoice_num']}. El correlativo quedará libre para ser usado nuevamente.")
                            if st.button("🚨 Confirmar Eliminación", type="primary"):
                                cur.execute("DELETE FROM facturas WHERE id = %s", (fac_id,))
                                conn.commit()
                                st.success("Factura eliminada. El número ha sido liberado.")
                                st.rerun()
                                
                        # --- ACCIÓN: EDITAR ---
                        elif accion == "✏️ Editar Valores":
                            st.info("ℹ️ Al editar, los campos de montos están desbloqueados independientemente del tipo de factura.")
                            
                            e1, e2 = st.columns(2)
                            with e1:
                                edit_cliente = st.text_input("Cliente (Bill To)", value=fac_data['cliente'])
                                edit_direccion = st.text_area("Dirección del Cliente", value=fac_data['direccion'])
                            with e2:
                                edit_concepto = st.text_input("Descripción del Servicio", value=fac_data['concepto'])
                                edit_cant = st.number_input("Cantidad de Paquetes", value=int(fac_data['cantidad_paquetes']), step=1)
                            
                            st.write("**Montos:**")
                            m1, m2, m3 = st.columns(3)
                            edit_sub = m1.number_input("Subtotal", value=float(fac_data['subtotal']), step=0.01)
                            edit_tax = m2.number_input("Tax Rate", value=float(fac_data['tax_rate']), step=0.01)
                            edit_otros = m3.number_input("Other Costs", value=float(fac_data['other_costs']), step=0.01)
                            
                            nuevo_total = edit_sub + edit_tax + edit_otros
                            st.write(f"**Nuevo Total Calculado:** ${nuevo_total:,.2f}")
                            
                            if st.button("💾 Guardar Cambios y Regenerar PDF", type="primary"):
                                with st.spinner("Actualizando registro y PDF..."):
                                    # Generar PDF nuevo con los datos editados
                                    nuevo_pdf = generar_factura_pdf(
                                        fac_data['tipo_factura'], fac_data['invoice_num'], fac_data['fecha'], 
                                        edit_cliente, edit_direccion, edit_concepto, edit_cant, 
                                        edit_sub, edit_tax, edit_otros, nuevo_total
                                    )
                                    
                                    # Actualizar BD dejando huella de auditoría
                                    update_sql = """
                                        UPDATE facturas SET 
                                            cliente=%s, direccion=%s, concepto=%s, cantidad_paquetes=%s, 
                                            subtotal=%s, tax_rate=%s, other_costs=%s, total=%s, 
                                            pdf_file=%s, is_modified=1, modified_by=%s 
                                        WHERE id=%s
                                    """
                                    cur.execute(update_sql, (
                                        edit_cliente, edit_direccion, edit_concepto, edit_cant, 
                                        edit_sub, edit_tax, edit_otros, nuevo_total, 
                                        nuevo_pdf, user_info['username'], fac_id
                                    ))
                                    conn.commit()
                                    st.success("Factura actualizada exitosamente.")
                                    st.rerun()

            finally:
                conn.close()
