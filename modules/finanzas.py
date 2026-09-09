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
                    UNIQUE KEY unique_tipo_inv (tipo_factura, invoice_num)
                );
            """)
            
            try:
                cur.execute("ALTER TABLE facturas ADD COLUMN tipo_factura VARCHAR(50) DEFAULT 'Funds' AFTER id;")
                cur.execute("ALTER TABLE facturas DROP INDEX invoice_num;")
                cur.execute("ALTER TABLE facturas ADD UNIQUE KEY unique_tipo_inv (tipo_factura, invoice_num);")
            except:
                pass 
                
            conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()

# --- 2. OBTENER SIGUIENTE CORRELATIVO POR TIPO ---
def get_next_invoice_number(tipo_factura):
    conn = get_connection()
    if not conn: return "0001"
    try:
        cur = conn.cursor()
        cur.execute("SELECT invoice_num FROM facturas WHERE tipo_factura = %s ORDER BY id DESC LIMIT 1", (tipo_factura,))
        res = cur.fetchone()
        conn.close()
        if res:
            last_num = int(res[0])
            return f"{(last_num + 1):04d}" 
        return "0001"
    except:
        if conn: conn.close()
        return "0001"

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
    pdf.set_font("Arial", '', 12)
    pdf.text(150, 68, fecha.strftime("%d-%b-%Y"))
    
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
# Aquí puedes editar los datos fijos para cada tipo de invoice
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
    
    t1, t2 = st.tabs(["Generar Nueva Factura", "Historial de Facturas"])
    
    with t1:
        st.subheader("Configuración y Detalles")
        
        c_tipo, c_blank = st.columns([1, 1])
        lista_tipos = list(CONFIG_TIPOS.keys())
        tipo_sel = c_tipo.selectbox("Tipo de Factura (Campo 'For'):", lista_tipos)
        
        # Extraer configuración del tipo seleccionado
        cfg = CONFIG_TIPOS[tipo_sel]
        
        c1, c2 = st.columns(2)
        inv_auto = get_next_invoice_number(tipo_sel)
        
        with c1:
            st.info(f"**Próximo Invoice # para {tipo_sel}:** {inv_auto}")
            # Campos bloqueados con disabled=True
            cliente = st.text_input("Cliente (Bill To)", value=cfg["cliente"], disabled=True)
            direccion = st.text_area("Dirección del Cliente", value=cfg["direccion"], disabled=True)
        
        with c2:
            st.write("Datos del Cobro")
            concepto = st.text_input("Descripción del Servicio", value="Tax payment for packages as per detail")
            cant_paq = st.number_input("Cantidad de Paquetes (pq)", min_value=1, step=1)
            
        st.divider()
        st.subheader("Desglose Financiero")
        c3, c4, c5 = st.columns(3)
        # Solo el subtotal es editable
        subtotal = c3.number_input("Subtotal ($)", min_value=0.0, step=0.01)
        # Tax y Other Costs bloqueados
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
    
    with t2:
        st.subheader("Historial de Invoices")
        conn = get_connection()
        if conn:
            try:
                df_fac = pd.read_sql("SELECT id, tipo_factura as 'Tipo', invoice_num as 'Invoice #', fecha as 'Fecha', cliente as 'Cliente', cantidad_paquetes as 'Paquetes', total as 'Total ($)' FROM facturas ORDER BY id DESC", conn)
                if df_fac.empty:
                    st.info("No hay facturas generadas aún.")
                else:
                    st.dataframe(df_fac, use_container_width=True)
                    
                    st.divider()
                    st.write("**Reimprimir Factura**")
                    
                    opciones_descarga = df_fac.apply(lambda row: f"{row['Tipo']} - {row['Invoice #']}", axis=1).tolist()
                    inv_sel_display = st.selectbox("Seleccione la factura a descargar:", opciones_descarga)
                    
                    if st.button("Obtener PDF"):
                        tipo_busqueda, num_busqueda = inv_sel_display.split(" - ")
                        cur = conn.cursor()
                        cur.execute("SELECT pdf_file FROM facturas WHERE tipo_factura = %s AND invoice_num = %s", (tipo_busqueda, num_busqueda))
                        pdf_data = cur.fetchone()
                        if pdf_data and pdf_data[0]:
                            st.download_button(f"⬇️ Descargar Invoice {num_busqueda}", data=pdf_data[0], file_name=f"Invoice_{tipo_busqueda}_{num_busqueda}.pdf", mime="application/pdf")
            finally:
                conn.close()
