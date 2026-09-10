import streamlit as st
import pandas as pd
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS ---
def init_fondos_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Resumen global
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_resumen (
                    id INT PRIMARY KEY DEFAULT 1,
                    impuestos_pagados DECIMAL(15,2) DEFAULT 0.00,
                    liquidado_temu DECIMAL(15,2) DEFAULT 0.00,
                    deposito_inicial DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            cur.execute("INSERT IGNORE INTO temu_hn_resumen (id) VALUES (1);")
            
            # Movimientos operativos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_movimientos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    concepto VARCHAR(100),
                    entrada DECIMAL(15,2) DEFAULT 0.00,
                    salida DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            
            # Tabla de Impuestos por Máster
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_impuestos_master (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    master_num VARCHAR(100) UNIQUE,
                    fecha_declaracion VARCHAR(50),
                    cantidad_paquetes INT,
                    dai_usd DECIMAL(15,2),
                    sel_usd DECIMAL(15,2),
                    iva_usd DECIMAL(15,2),
                    total_impuestos_usd DECIMAL(15,2),
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    registrado_por VARCHAR(100)
                );
            """)
            
            # NUEVO: Tabla de Impuestos por Paquete (Tracking)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_impuestos_paquetes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    master_num VARCHAR(100),
                    tracking VARCHAR(100),
                    total_usd DECIMAL(10,2),
                    INDEX idx_tracking (tracking),
                    INDEX idx_master (master_num)
                );
            """)
            
            conn.commit()
        except Exception as e:
            pass
        finally:
            conn.close()

# --- 2. INTERFAZ GRÁFICA ---
def show(user_info):
    init_fondos_db()
    st.title("🇭🇳 Control de Fondos - TEMU HN")
    
    conn = get_connection()
    if not conn:
        st.error("Error de conexión a la base de datos.")
        return
        
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM temu_hn_resumen WHERE id = 1")
        resumen = cur.fetchone()
        
        impuestos = float(resumen['impuestos_pagados'])
        liquidado = float(resumen['liquidado_temu'])
        deposito = float(resumen['deposito_inicial'])
        
        total_pagos = liquidado + deposito
        saldo_disponible = total_pagos - impuestos

        # Dividimos la herramienta en dos pestañas principales
        t1, t2 = st.tabs(["📊 Resumen y Másters", "📦 Liquidación por Paquetes"])
        
        # ==========================================
        # PESTAÑA 1: RESUMEN Y MÁSTERS
        # ==========================================
        with t1:
            col_izq, col_espacio, col_der = st.columns([5, 1, 5])
            
            # --- COLUMNA DERECHA: RESUMEN GLOBAL Y LECTOR EXCEL ---
            with col_der:
                st.write("### Resumen Global")
                
                df_resumen = pd.DataFrame([
                    {"CONCEPTO": "Impuestos pagados", "MONTO": f"${impuestos:,.2f}"},
                    {"CONCEPTO": "Liquidado por TEMU", "MONTO": f"${liquidado:,.2f}"},
                    {"CONCEPTO": "Deposito inicial", "MONTO": f"${deposito:,.2f}"},
                    {"CONCEPTO": "Total pagos TEMU", "MONTO": f"${total_pagos:,.2f}"},
                    {"CONCEPTO": "Saldo disponible para impuesto", "MONTO": f"${saldo_disponible:,.2f}"}
                ])
                st.dataframe(df_resumen, hide_index=True, use_container_width=True)
                
                with st.expander("📂 Cargar Impuestos de Másters (Excel)", expanded=True):
                    st.caption("Procesa los archivos. El sistema extraerá los montos y guardará el impuesto individual de cada paquete.")
                    archivos_excel = st.file_uploader("Subir archivos (El nombre del archivo debe ser la Máster)", type=["xlsx", "xls"], accept_multiple_files=True)
                    
                    if archivos_excel:
                        resultados = []
                        total_calculado = 0.0
                        
                        for archivo in archivos_excel:
                            try:
                                df_imp = pd.read_excel(archivo)
                                master_num = archivo.name.replace(".xlsx", "").replace(".xls", "")
                                
                                if df_imp.shape[1] >= 19:
                                    # Extraer Trackings (Columna A / Índice 0)
                                    trackings_list = df_imp.iloc[:, 0].astype(str).tolist()
                                    
                                    df_imp.iloc[:, 7] = pd.to_numeric(df_imp.iloc[:, 7], errors='coerce').fillna(0)
                                    df_imp.iloc[:, 8] = pd.to_numeric(df_imp.iloc[:, 8], errors='coerce').fillna(0)
                                    df_imp.iloc[:, 9] = pd.to_numeric(df_imp.iloc[:, 9], errors='coerce').fillna(0)
                                    df_imp.iloc[:, 10] = pd.to_numeric(df_imp.iloc[:, 10], errors='coerce').fillna(0)
                                    df_imp.iloc[:, 18] = pd.to_numeric(df_imp.iloc[:, 18], errors='coerce').fillna(1)
                                    
                                    df_imp['DAI_USD'] = df_imp.iloc[:, 8] / df_imp.iloc[:, 18]
                                    df_imp['SEL_USD'] = df_imp.iloc[:, 9] / df_imp.iloc[:, 18]
                                    df_imp['IVA_USD'] = df_imp.iloc[:, 10] / df_imp.iloc[:, 18]
                                    df_imp['Total_USD'] = df_imp.iloc[:, 7] / df_imp.iloc[:, 18]
                                    
                                    tot_usd = df_imp['Total_USD'].sum()
                                    
                                    # Emparejar cada tracking con su impuesto total
                                    paquetes_data = list(zip(
                                        [master_num] * len(df_imp),
                                        trackings_list,
                                        df_imp['Total_USD'].tolist()
                                    ))
                                    
                                    resultados.append({
                                        'Máster': master_num,
                                        'Fecha Decl.': str(df_imp.iloc[0, 17]) if len(df_imp) > 0 else "N/A",
                                        'Paquetes': len(df_imp),
                                        'DAI ($)': df_imp['DAI_USD'].sum(),
                                        'SEL ($)': df_imp['SEL_USD'].sum(),
                                        'IVA ($)': df_imp['IVA_USD'].sum(),
                                        'Total Impuestos ($)': tot_usd,
                                        'paquetes_data': paquetes_data # Guardamos los datos de los paquetes
                                    })
                                    total_calculado += tot_usd
                                else:
                                    st.error(f"El archivo {archivo.name} no tiene la estructura correcta.")
                            except Exception as e:
                                st.error(f"Error procesando {archivo.name}: {e}")
                        
                        if resultados:
                            df_res_view = pd.DataFrame(resultados).drop(columns=['paquetes_data'])
                            st.write("**Resumen de Másters listas para registrar:**")
                            st.dataframe(df_res_view.style.format({"DAI ($)": "{:,.2f}", "SEL ($)": "{:,.2f}", "IVA ($)": "{:,.2f}", "Total Impuestos ($)": "{:,.2f}"}), hide_index=True)
                            st.success(f"**Total a sumar al balance: ${total_calculado:,.2f} USD**")
                            
                            if st.button("💾 Guardar Datos, Paquetes y Sumar a Impuestos", type="primary"):
                                nuevos = 0; suma_real = 0.0
                                for r in resultados:
                                    cur.execute("SELECT id FROM temu_hn_impuestos_master WHERE master_num = %s", (r['Máster'],))
                                    if cur.fetchone():
                                        st.warning(f"⚠️ La Máster **{r['Máster']}** ya existe. Se omitió.")
                                    else:
                                        # 1. Guardar la Máster
                                        sql_m = """INSERT INTO temu_hn_impuestos_master 
                                                   (master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, registrado_por) 
                                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                                        cur.execute(sql_m, (r['Máster'], r['Fecha Decl.'], r['Paquetes'], r['DAI ($)'], r['SEL ($)'], r['IVA ($)'], r['Total Impuestos ($)'], user_info['username']))
                                        
                                        # 2. Guardar todos los paquetes individuales asociados
                                        sql_p = "INSERT INTO temu_hn_impuestos_paquetes (master_num, tracking, total_usd) VALUES (%s, %s, %s)"
                                        cur.executemany(sql_p, r['paquetes_data'])
                                        
                                        suma_real += r['Total Impuestos ($)']
                                        nuevos += 1
                                        
                                if nuevos > 0:
                                    cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados + %s WHERE id = 1", (suma_real,))
                                    conn.commit()
                                    st.success("✅ Datos guardados exitosamente.")
                                    st.rerun()

                with st.expander("📜 Historial de Másters Procesadas", expanded=False):
                    cur.execute("SELECT id, master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, registrado_por FROM temu_hn_impuestos_master ORDER BY id DESC")
                    historial_masters = cur.fetchall()
                    
                    if historial_masters:
                        df_hist = pd.DataFrame(historial_masters)
                        df_view = df_hist.rename(columns={
                            'master_num':'Máster', 'fecha_declaracion':'Fecha Decl.', 
                            'cantidad_paquetes':'Paq.', 'dai_usd':'DAI ($)', 
                            'sel_usd':'SEL ($)', 'iva_usd':'IVA ($)', 
                            'total_impuestos_usd':'Total ($)', 'registrado_por':'Responsable'
                        })
                        st.dataframe(df_view[['Máster', 'Fecha Decl.', 'Paq.', 'DAI ($)', 'SEL ($)', 'IVA ($)', 'Total ($)', 'Responsable']], hide_index=True)
                        
                        st.divider()
                        st.write("**Opciones de Gestión**")
                        master_sel = st.selectbox("Seleccione la Máster si necesita corregir el saldo:", df_hist['master_num'].tolist())
                        
                        cur.execute("SELECT id, total_impuestos_usd FROM temu_hn_impuestos_master WHERE master_num = %s", (master_sel,))
                        m_data = cur.fetchone()
                        
                        if st.button("🗑️ Eliminar Máster y Revertir Balance", type="primary"):
                            if m_data:
                                # Restar globales
                                cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados - %s WHERE id = 1", (m_data['total_impuestos_usd'],))
                                # Borrar máster
                                cur.execute("DELETE FROM temu_hn_impuestos_master WHERE id = %s", (m_data['id'],))
                                # Borrar paquetes asociados a la máster
                                cur.execute("DELETE FROM temu_hn_impuestos_paquetes WHERE master_num = %s", (master_sel,))
                                conn.commit()
                                st.success(f"Máster eliminada. Se restaron ${m_data['total_impuestos_usd']:,.2f} del total pagado y se borraron sus paquetes.")
                                st.rerun()
                    else:
                        st.info("Aún no se han registrado másters.")

                with st.expander("✏️ Editar manualmente Montos Globales"):
                    with st.form("form_global"):
                        new_imp = st.number_input("Impuestos pagados", value=impuestos, step=100.0)
                        new_liq = st.number_input("Liquidado por TEMU", value=liquidado, step=100.0)
                        new_dep = st.number_input("Deposito inicial", value=deposito, step=100.0)
                        if st.form_submit_button("Actualizar Todo", type="primary"):
                            cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados=%s, liquidado_temu=%s, deposito_inicial=%s WHERE id=1", 
                                        (new_imp, new_liq, new_dep))
                            conn.commit()
                            st.success("Montos actualizados.")
                            st.rerun()

            # --- COLUMNA IZQUIERDA: FLUJO OPERATIVO ---
            with col_izq:
                st.write("### Flujo Operativo")
                
                cur.execute("SELECT concepto, entrada, salida FROM temu_hn_movimientos ORDER BY id ASC")
                movimientos = cur.fetchall()
                
                filas = []
                balance_actual = saldo_disponible
                
                filas.append({
                    "CONCEPTO": "DISPONIBLE SEGÚN TEMU", 
                    "ENTRADAS": f"${saldo_disponible:,.2f}", 
                    "SALIDAS": "", 
                    "BALANCE": f"${balance_actual:,.2f}"
                })
                
                for mov in movimientos:
                    ent = float(mov['entrada'])
                    sal = float(mov['salida'])
                    balance_actual = balance_actual + ent - sal
                    
                    filas.append({
                        "CONCEPTO": mov['concepto'],
                        "ENTRADAS": f"${ent:,.2f}" if ent > 0 else "",
                        "SALIDAS": f"${sal:,.2f}" if sal > 0 else "",
                        "BALANCE": f"${balance_actual:,.2f}"
                    })
                    
                st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)
                
                with st.expander("➕ Agregar Movimiento (Gasto / Ajuste)"):
                    with st.form("form_movimiento"):
                        c1, c2, c3 = st.columns(3)
                        concepto = c1.text_input("Concepto (Ej. MULTA 3%)")
                        entrada = c2.number_input("Entrada (+)", min_value=0.0, step=10.0)
                        salida = c3.number_input("Salida (-)", min_value=0.0, step=10.0)
                        
                        if st.form_submit_button("Registrar Movimiento", type="primary"):
                            if concepto:
                                cur.execute("INSERT INTO temu_hn_movimientos (concepto, entrada, salida) VALUES (%s, %s, %s)", 
                                            (concepto, entrada, salida))
                                conn.commit()
                                st.rerun()
                            else:
                                st.error("Debe ingresar un concepto.")
                                
                if st.button("🗑️ Limpiar Historial de Movimientos"):
                    cur.execute("TRUNCATE TABLE temu_hn_movimientos")
                    conn.commit()
                    st.rerun()

        # ==========================================
        # PESTAÑA 2: LIQUIDACIÓN POR PAQUETES
        # ==========================================
        with t2:
            st.write("### 🔍 Conciliación y Liquidación de Paquetes")
            st.markdown("Pega la lista de Trackings que TEMU ha reportado como liquidados para saber exactamente cuánto dinero representa en impuestos.")
            
            c_liq1, c_liq2 = st.columns([1, 1])
            
            with c_liq1:
                txt_trackings = st.text_area("Pegar Trackings (Uno por línea)", height=300)
                
                if st.button("🔍 Calcular Liquidación", type="primary"):
                    if txt_trackings.strip():
                        lista_raw = [x.strip() for x in txt_trackings.split('\n') if x.strip()]
                        lista_unicos = list(set(lista_raw))
                        
                        with st.spinner("Buscando paquetes en la base de datos..."):
                            # Buscar en lotes para evitar saturar la base de datos
                            todos_los_datos = []
                            BATCH_SIZE = 1000 
                            for i in range(0, len(lista_unicos), BATCH_SIZE):
                                lote = lista_unicos[i : i + BATCH_SIZE]
                                format_strings = ','.join(['%s'] * len(lote))
                                query = f"SELECT tracking, total_usd FROM temu_hn_impuestos_paquetes WHERE tracking IN ({format_strings})"
                                cur.execute(query, tuple(lote))
                                todos_los_datos.extend(cur.fetchall())
                            
                            df_found = pd.DataFrame(todos_los_datos)
                            
                            if not df_found.empty:
                                total_liquidado = df_found['total_usd'].sum()
                                encontrados = len(df_found)
                                no_encontrados = len(lista_unicos) - encontrados
                                
                                st.session_state['liq_total'] = float(total_liquidado)
                                st.session_state['liq_df'] = df_found
                                st.session_state['liq_enc'] = encontrados
                                st.session_state['liq_falt'] = no_encontrados
                            else:
                                st.warning("No se encontró ningún tracking de esta lista en la base de datos.")
                                if 'liq_total' in st.session_state:
                                    del st.session_state['liq_total']
                    else:
                        st.warning("Debe ingresar al menos un tracking.")
            
            with c_liq2:
                if 'liq_total' in st.session_state:
                    st.success(f"### Total Calculado: ${st.session_state['liq_total']:,.2f} USD")
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Paquetes Encontrados", st.session_state['liq_enc'])
                    m2.metric("No Encontrados", st.session_state['liq_falt'])
                    
                    st.dataframe(st.session_state['liq_df'].rename(columns={'tracking':'Tracking', 'total_usd':'Impuesto Pagado ($)'}), height=200, use_container_width=True)
                    
                    st.info(f"Liquidado actualmente: **${liquidado:,.2f}**")
                    accion_liq = st.radio("¿Qué desea hacer con este cálculo?", ["Sumarlo al 'Liquidado por TEMU' actual", "Reemplazar completamente el 'Liquidado por TEMU'"])
                    
                    if st.button("💾 Aplicar Liquidación al Balance", type="primary"):
                        nuevo_liquidado = (liquidado + st.session_state['liq_total']) if "Sumarlo" in accion_liq else st.session_state['liq_total']
                        
                        cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = %s WHERE id = 1", (nuevo_liquidado,))
                        conn.commit()
                        
                        # Limpiar caché de búsqueda
                        del st.session_state['liq_total']
                        del st.session_state['liq_df']
                        
                        st.success("¡Balance global actualizado exitosamente!")
                        st.rerun()
                else:
                    st.info("Ingrese los trackings y presione 'Calcular' para ver los resultados aquí.")
            
            st.divider()
            st.write("### 📦 Visualizador General de Paquetes")
            st.caption("Últimos 100 paquetes registrados en la base de datos de impuestos.")
            cur.execute("SELECT master_num as 'Máster', tracking as 'Tracking', total_usd as 'Impuesto USD ($)' FROM temu_hn_impuestos_paquetes ORDER BY id DESC LIMIT 100")
            df_preview = pd.DataFrame(cur.fetchall())
            if not df_preview.empty:
                st.dataframe(df_preview, hide_index=True, use_container_width=True)
            else:
                st.caption("No hay paquetes registrados.")

    finally:
        conn.close()
