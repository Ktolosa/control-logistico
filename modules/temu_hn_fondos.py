import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS ---
def init_fondos_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_resumen (
                    id INT PRIMARY KEY DEFAULT 1,
                    impuestos_pagados DECIMAL(15,2) DEFAULT 0.00,
                    liquidado_temu DECIMAL(15,2) DEFAULT 0.00,
                    deposito_inicial DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            cur.execute("INSERT IGNORE INTO temu_hn_resumen (id) VALUES (1);")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_movimientos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    concepto VARCHAR(100),
                    entrada DECIMAL(15,2) DEFAULT 0.00,
                    salida DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            
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
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_impuestos_paquetes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    master_num VARCHAR(100),
                    tracking_a VARCHAR(100),
                    tracking_b VARCHAR(100),
                    total_usd DECIMAL(10,2),
                    liquidado BOOLEAN DEFAULT FALSE,
                    liquidacion_id INT DEFAULT NULL,
                    INDEX idx_tracking_a (tracking_a),
                    INDEX idx_tracking_b (tracking_b),
                    INDEX idx_master (master_num)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_liquidaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    invoice_num VARCHAR(100) UNIQUE,
                    fecha_invoice DATE,
                    paquetes_declarados INT,
                    monto_pagado DECIMAL(15,2),
                    paquetes_encontrados INT,
                    paquetes_faltantes INT,
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    registrado_por VARCHAR(100)
                );
            """)
            
            try: cur.execute("ALTER TABLE temu_hn_impuestos_paquetes ADD COLUMN liquidacion_id INT DEFAULT NULL;")
            except: pass
            
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
        # --- DATOS FINANCIEROS ---
        cur.execute("SELECT * FROM temu_hn_resumen WHERE id = 1")
        resumen = cur.fetchone()
        
        impuestos = float(resumen['impuestos_pagados'])
        liquidado = float(resumen['liquidado_temu'])
        deposito = float(resumen['deposito_inicial'])
        
        total_pagos = liquidado + deposito
        saldo_disponible = total_pagos - impuestos

        # --- DATOS DE PAQUETES ---
        cur.execute("SELECT COUNT(*) as total FROM temu_hn_impuestos_paquetes WHERE master_num != 'FALTANTE'")
        tot_paq = cur.fetchone()['total'] or 0
        
        cur.execute("SELECT COUNT(*) as liquidados FROM temu_hn_impuestos_paquetes WHERE liquidado = TRUE AND master_num != 'FALTANTE'")
        tot_liq = cur.fetchone()['liquidados'] or 0
        
        tot_pend = tot_paq - tot_liq

        t1, t2 = st.tabs(["📊 Resumen y Másters", "🧾 Conciliación y Liquidaciones"])
        
        # ==========================================
        # PESTAÑA 1: RESUMEN Y MÁSTERS
        # ==========================================
        with t1:
            col_izq, col_espacio, col_der = st.columns([5, 1, 5])
            
            with col_der:
                st.write("### Resumen Financiero")
                
                df_resumen = pd.DataFrame([
                    {"CONCEPTO": "Impuestos pagados", "MONTO": f"${impuestos:,.2f}"},
                    {"CONCEPTO": "Liquidado por TEMU", "MONTO": f"${liquidado:,.2f}"},
                    {"CONCEPTO": "Deposito inicial", "MONTO": f"${deposito:,.2f}"},
                    {"CONCEPTO": "Total pagos TEMU", "MONTO": f"${total_pagos:,.2f}"},
                    {"CONCEPTO": "Saldo disponible para impuesto", "MONTO": f"${saldo_disponible:,.2f}"}
                ])
                st.dataframe(df_resumen, hide_index=True, use_container_width=True)
                
                st.write("### Estado de Paquetes Reales")
                cp1, cp2, cp3 = st.columns(3)
                cp1.metric("Imp. Pagados", f"{tot_paq:,} pq")
                cp2.metric("Liquidados", f"{tot_liq:,} pq")
                cp3.metric("Pendientes", f"{tot_pend:,} pq")
                st.divider()
                
                # --- VISOR DE REPORTES DE CARGA ---
                if 'upload_report' in st.session_state:
                    report = st.session_state['upload_report']
                    st.write("### 📋 Resultados de la última carga")
                    
                    if report['success_count'] > 0:
                        st.success(f"✅ Se guardaron **{report['success_count']}** archivos exitosamente. Los archivos con errores fueron descartados y no afectaron los cálculos.")
                    
                    if report['errors']:
                        st.error(f"❌ **{len(report['errors'])} archivos fueron OMITIDOS por tener errores:**")
                        for arch, err in report['errors']:
                            st.write(f"- 📄 `{arch}`: {err}")
                            
                    if report['warnings']:
                        with st.expander(f"⚠️ {len(report['warnings'])} Advertencias", expanded=False):
                            for adv in report['warnings']:
                                st.write(f"- {adv}")
                                
                    if st.button("Cerrar Reporte"):
                        del st.session_state['upload_report']
                        st.rerun()
                    st.divider()

                with st.expander("📂 Cargar Impuestos de Másters (Excel)", expanded=True):
                    st.caption("Solo se procesarán los archivos con estructura correcta. Los defectuosos serán aislados.")
                    archivos_excel = st.file_uploader("Subir archivos (El nombre del archivo debe ser la Máster)", type=["xlsx", "xls"], accept_multiple_files=True)
                    
                    if archivos_excel:
                        if st.button("🚀 Procesar Archivos", type="primary"):
                            resultados = []
                            archivos_con_error = []
                            archivos_con_advertencia = []
                            
                            barra_progreso = st.progress(0)
                            texto_estado = st.empty()
                            total_archivos = len(archivos_excel)
                            
                            for idx, archivo in enumerate(archivos_excel):
                                texto_estado.text(f"Leyendo Excel: {archivo.name} ({idx+1}/{total_archivos})")
                                try:
                                    df_imp = pd.read_excel(archivo, usecols="A:S") 
                                    master_num = archivo.name.replace(".xlsx", "").replace(".xls", "")
                                    
                                    if df_imp.shape[1] >= 19:
                                        
                                        # 1. VALIDACIÓN ESTRICTA ANTI-NaN: Intentar convertir a números. Si hay celdas vacías o texto inválido, genera NaNs.
                                        col_total = pd.to_numeric(df_imp.iloc[:, 7], errors='coerce')
                                        col_dai = pd.to_numeric(df_imp.iloc[:, 8], errors='coerce')
                                        col_sel = pd.to_numeric(df_imp.iloc[:, 9], errors='coerce')
                                        col_iva = pd.to_numeric(df_imp.iloc[:, 10], errors='coerce')
                                        tasa_cambio = pd.to_numeric(df_imp.iloc[:, 18], errors='coerce')
                                        
                                        # Si alguna de las columnas clave tiene NaN (celdas vacías), rechazamos el archivo por completo.
                                        if col_total.isna().any() or col_dai.isna().any() or col_sel.isna().any() or col_iva.isna().any() or tasa_cambio.isna().any() or (tasa_cambio == 0).any():
                                            archivos_con_error.append((archivo.name, "Rechazado: Contiene celdas vacías, texto inválido o tasas en cero en la zona de impuestos."))
                                            continue # <--- ESTO OMITE EL ARCHIVO Y SALTA AL SIGUIENTE
                                            
                                        trackings_a = df_imp.iloc[:, 0].fillna("N/A").astype(str).str.strip().tolist()
                                        trackings_b = df_imp.iloc[:, 1].fillna("N/A").astype(str).str.strip().tolist()
                                        
                                        df_imp['DAI_USD'] = col_dai / tasa_cambio
                                        df_imp['SEL_USD'] = col_sel / tasa_cambio
                                        df_imp['IVA_USD'] = col_iva / tasa_cambio
                                        df_imp['Total_USD'] = col_total / tasa_cambio
                                        
                                        tot_usd = float(df_imp['Total_USD'].sum())
                                        totales_lista = [float(x) for x in df_imp['Total_USD']]
                                        
                                        paquetes_data = list(zip(
                                            [master_num] * len(df_imp), trackings_a, trackings_b, totales_lista
                                        ))
                                        
                                        fecha_bruta = df_imp.iloc[0, 17] if len(df_imp) > 0 else "N/A"
                                        fecha_dec = str(fecha_bruta) if pd.notna(fecha_bruta) else "N/A"
                                        
                                        # Si pasó la validación, lo agregamos a la lista de "buenos"
                                        resultados.append({
                                            'Máster': master_num,
                                            'Fecha Decl.': fecha_dec,
                                            'Paquetes': len(df_imp),
                                            'DAI ($)': float(df_imp['DAI_USD'].sum()),
                                            'SEL ($)': float(df_imp['SEL_USD'].sum()),
                                            'IVA ($)': float(df_imp['IVA_USD'].sum()),
                                            'Total Impuestos ($)': tot_usd,
                                            'paquetes_data': paquetes_data
                                        })
                                    else:
                                        archivos_con_error.append((archivo.name, "Rechazado: No tiene las 19 columnas requeridas."))
                                except Exception as e:
                                    archivos_con_error.append((archivo.name, f"Rechazado: Archivo corrupto o no se pudo leer."))
                                    continue 
                                
                                barra_progreso.progress((idx + 1) / total_archivos)
                                
                            texto_estado.text("¡Lectura finalizada! Guardando los archivos válidos en base de datos...")
                            
                            nuevos_guardados = 0
                            suma_real = 0.0
                            
                            if resultados:
                                for r in resultados:
                                    try:
                                        cur.execute("SELECT id FROM temu_hn_impuestos_master WHERE master_num = %s", (r['Máster'],))
                                        if cur.fetchone():
                                            # Esto sí es una advertencia, porque el archivo estaba bueno pero ya lo habías subido antes.
                                            archivos_con_advertencia.append(f"**{r['Máster']}**: Ya estaba registrado, omitido para no duplicar.")
                                        else:
                                            sql_m = """INSERT INTO temu_hn_impuestos_master 
                                                       (master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, registrado_por) 
                                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                                            cur.execute(sql_m, (r['Máster'], r['Fecha Decl.'], r['Paquetes'], r['DAI ($)'], r['SEL ($)'], r['IVA ($)'], r['Total Impuestos ($)'], user_info['username']))
                                            
                                            sql_p = "INSERT INTO temu_hn_impuestos_paquetes (master_num, tracking_a, tracking_b, total_usd) VALUES (%s, %s, %s, %s)"
                                            paquetes = r['paquetes_data']
                                            chunk_sz = 5000
                                            for i in range(0, len(paquetes), chunk_sz):
                                                cur.executemany(sql_p, paquetes[i:i+chunk_sz])
                                            
                                            conn.commit()
                                            suma_real += r['Total Impuestos ($)']
                                            nuevos_guardados += 1
                                    except Exception as db_err:
                                        conn.rollback() 
                                        archivos_con_error.append((r['Máster'], f"Error de BD: {str(db_err)}"))
                                        
                                if nuevos_guardados > 0:
                                    cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados + %s WHERE id = 1", (suma_real,))
                                    conn.commit()
                            
                            st.session_state['upload_report'] = {
                                'success_count': nuevos_guardados,
                                'errors': archivos_con_error,
                                'warnings': archivos_con_advertencia
                            }
                            st.rerun()

                with st.expander("📜 Historial de Másters Procesadas", expanded=False):
                    cur.execute("SELECT id, master_num, fecha_declaracion, cantidad_paquetes, total_impuestos_usd, registrado_por FROM temu_hn_impuestos_master ORDER BY id DESC LIMIT 50")
                    historial_masters = cur.fetchall()
                    if historial_masters:
                        df_hist = pd.DataFrame(historial_masters)
                        st.dataframe(df_hist.rename(columns={'master_num':'Máster', 'cantidad_paquetes':'Paq.', 'total_impuestos_usd':'Total ($)', 'registrado_por':'Por'}), hide_index=True, height=250)
                        
                        st.write("**Opciones de Gestión**")
                        master_sel = st.selectbox("Seleccione la Máster a eliminar:", df_hist['master_num'].tolist())
                        cur.execute("SELECT id, total_impuestos_usd FROM temu_hn_impuestos_master WHERE master_num = %s", (master_sel,))
                        m_data = cur.fetchone()
                        
                        btn_c1, btn_c2 = st.columns(2)
                        
                        if btn_c1.button("🗑️ Eliminar Solo Esta Máster", type="primary"):
                            if m_data:
                                cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados - %s WHERE id = 1", (m_data['total_impuestos_usd'],))
                                cur.execute("DELETE FROM temu_hn_impuestos_master WHERE id = %s", (m_data['id'],))
                                cur.execute("DELETE FROM temu_hn_impuestos_paquetes WHERE master_num = %s", (master_sel,))
                                conn.commit()
                                st.success("Máster eliminada exitosamente.")
                                st.rerun()
                                
                        if btn_c2.button("🚨 Eliminar TODAS las Másters", type="primary"):
                            cur.execute("SELECT SUM(total_impuestos_usd) as total_sum FROM temu_hn_impuestos_master")
                            sum_res = cur.fetchone()
                            total_a_restar = float(sum_res['total_sum']) if sum_res and sum_res['total_sum'] else 0.0
                            
                            cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados - %s WHERE id = 1", (total_a_restar,))
                            cur.execute("DELETE FROM temu_hn_impuestos_master")
                            cur.execute("DELETE FROM temu_hn_impuestos_paquetes WHERE master_num != 'FALTANTE'")
                            conn.commit()
                            
                            st.success(f"Se eliminaron todas las Másters y se restaron ${total_a_restar:,.2f} del balance.")
                            st.rerun()
                    else:
                        st.info("Sin registros.")

                with st.expander("✏️ Editar manualmente Montos Globales"):
                    with st.form("form_global"):
                        new_imp = st.number_input("Impuestos pagados", value=impuestos, step=100.0)
                        new_liq = st.number_input("Liquidado por TEMU", value=liquidado, step=100.0)
                        new_dep = st.number_input("Deposito inicial", value=deposito, step=100.0)
                        if st.form_submit_button("Actualizar Todo", type="primary"):
                            cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados=%s, liquidado_temu=%s, deposito_inicial=%s WHERE id=1", (new_imp, new_liq, new_dep))
                            conn.commit()
                            st.rerun()

            with col_izq:
                st.write("### Flujo Operativo")
                
                cur.execute("SELECT concepto, entrada, salida FROM temu_hn_movimientos ORDER BY id ASC")
                movimientos = cur.fetchall()
                
                filas = []
                balance_actual = saldo_disponible
                filas.append({"CONCEPTO": "DISPONIBLE SEGÚN TEMU", "ENTRADAS": f"${saldo_disponible:,.2f}", "SALIDAS": "", "BALANCE": f"${balance_actual:,.2f}"})
                
                for mov in movimientos:
                    ent = float(mov['entrada'])
                    sal = float(mov['salida'])
                    balance_actual = balance_actual + ent - sal
                    filas.append({"CONCEPTO": mov['concepto'], "ENTRADAS": f"${ent:,.2f}" if ent > 0 else "", "SALIDAS": f"${sal:,.2f}" if sal > 0 else "", "BALANCE": f"${balance_actual:,.2f}"})
                    
                st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)
                
                with st.expander("➕ Agregar Movimiento"):
                    with st.form("form_movimiento"):
                        c1, c2, c3 = st.columns(3)
                        concepto = c1.text_input("Concepto")
                        entrada = c2.number_input("Entrada (+)", min_value=0.0, step=10.0)
                        salida = c3.number_input("Salida (-)", min_value=0.0, step=10.0)
                        
                        if st.form_submit_button("Registrar Movimiento", type="primary"):
                            if concepto:
                                cur.execute("INSERT INTO temu_hn_movimientos (concepto, entrada, salida) VALUES (%s, %s, %s)", (concepto, entrada, salida))
                                conn.commit()
                                st.rerun()

        # ==========================================
        # PESTAÑA 2: LIQUIDACIONES (INVOICES)
        # ==========================================
        with t2:
            st.write("### 🧾 Registrar Nueva Liquidación (Invoice)")
            st.markdown("Registra los datos de TEMU para cruzar la información y calcular el ajuste financiero.")
            
            c_liq1, c_liq2 = st.columns([1, 1])
            
            with c_liq1:
                st.write("**Datos de la Factura (Invoice)**")
                inv_num = st.text_input("Número de Invoice", placeholder="Ej: INV-2023-001")
                
                l1, l2 = st.columns(2)
                fecha_liq = l1.date_input("Fecha de Invoice")
                paq_liq = l2.number_input("Total Pq Liquidados", min_value=1)
                
                monto_liq = st.number_input("Monto total pagado por TEMU ($)", min_value=0.0, step=10.0)
                trackings_txt = st.text_area("Pegar Listado de Trackings Liquidados", height=150)
                
                if st.button("🔍 Verificar Conciliación", type="primary"):
                    if not inv_num.strip():
                        st.error("Debes ingresar un número de Invoice.")
                    elif not trackings_txt.strip():
                        st.warning("Debes ingresar al menos un tracking.")
                    else:
                        cur.execute("SELECT id FROM temu_hn_liquidaciones WHERE invoice_num = %s", (inv_num,))
                        if cur.fetchone():
                            st.error(f"El Invoice '{inv_num}' ya fue registrado previamente.")
                        else:
                            lista_raw = [x.strip() for x in trackings_txt.split('\n') if x.strip()]
                            lista_unicos = list(set(lista_raw))
                            
                            with st.spinner("Conciliando y calculando prorrateo..."):
                                todos_los_datos = []
                                BATCH_SIZE = 1000 
                                for i in range(0, len(lista_unicos), BATCH_SIZE):
                                    lote = lista_unicos[i : i + BATCH_SIZE]
                                    format_strings = ','.join(['%s'] * len(lote))
                                    
                                    query = f"""
                                        SELECT id, tracking_a, tracking_b, total_usd 
                                        FROM temu_hn_impuestos_paquetes 
                                        WHERE tracking_a IN ({format_strings}) OR tracking_b IN ({format_strings})
                                    """
                                    cur.execute(query, tuple(lote) + tuple(lote))
                                    todos_los_datos.extend(cur.fetchall())
                                
                                df_found = pd.DataFrame(todos_los_datos)
                                encontrados = 0
                                total_impuestos_db = 0.0
                                faltantes_list = lista_unicos.copy()
                                ids_encontrados = []
                                
                                if not df_found.empty:
                                    df_found = df_found.drop_duplicates(subset=['tracking_a', 'tracking_b'])
                                    encontrados = len(df_found)
                                    ids_encontrados = df_found['id'].tolist()
                                    total_impuestos_db = float(df_found['total_usd'].sum())
                                    
                                    found_trackings = set(df_found['tracking_a'].tolist() + df_found['tracking_b'].tolist())
                                    faltantes_list = [t for t in lista_unicos if t not in found_trackings]
                                
                                faltantes = len(faltantes_list)
                                
                                # --- LÓGICA DE PRORRATEO Y DIFERENCIAL ---
                                diferencia = monto_liq - total_impuestos_db
                                ajuste_por_paquete = diferencia / paq_liq if paq_liq > 0 else 0.0
                                
                                st.session_state['liq_preview'] = {
                                    'inv_num': inv_num,
                                    'fecha_liq': fecha_liq,
                                    'paq_liq': paq_liq,
                                    'monto_liq': monto_liq,
                                    'encontrados': encontrados,
                                    'faltantes': faltantes,
                                    'faltantes_list': faltantes_list,
                                    'ids_encontrados': ids_encontrados,
                                    'total_impuestos_db': total_impuestos_db,
                                    'diferencia': diferencia,
                                    'ajuste_por_paquete': ajuste_por_paquete
                                }
            
            with c_liq2:
                if 'liq_preview' in st.session_state:
                    prev = st.session_state['liq_preview']
                    st.write(f"### 📋 Previsualización: {prev['inv_num']}")
                    
                    # COMPARATIVA FINANCIERA
                    f1, f2, f3 = st.columns(3)
                    f1.metric("Aduana (Lo que tú pagaste)", f"${prev['total_impuestos_db']:,.2f}")
                    f2.metric("TEMU (Lo que te deposita)", f"${prev['monto_liq']:,.2f}")
                    
                    # Color del delta según si es ganancia o pérdida
                    diff_color = "normal" if prev['diferencia'] >= 0 else "inverse"
                    f3.metric("Diferencial Global", f"${prev['diferencia']:,.2f}", delta=f"${prev['diferencia']:,.2f}", delta_color=diff_color)
                    
                    if prev['diferencia'] > 0.01:
                        st.success(f"📈 **TEMU está pagando de MÁS.** \nTienes un ajuste a favor prorrateado de **+${prev['ajuste_por_paquete']:,.4f}** por paquete.")
                    elif prev['diferencia'] < -0.01:
                        st.error(f"📉 **TEMU está pagando de MENOS.** \nTienes una pérdida prorrateada de **${prev['ajuste_por_paquete']:,.4f}** por paquete.")
                    else:
                        st.info("⚖️ **Conciliación Exacta.** \nTEMU pagó exactamente lo mismo que gastaste en impuestos aduanales.")
                    
                    st.divider()
                    st.write("**Desglose de Trackings**")
                    m1, m2 = st.columns(2)
                    m1.metric("Paquetes Conciliados", prev['encontrados'])
                    m2.metric("Paquetes Faltantes", prev['faltantes'])
                    
                    if prev['faltantes'] > 0:
                        st.warning(f"⚠️ **Alerta:** Hay {prev['faltantes']} paquetes liquidados por TEMU que NO están en tus reportes de aduana. Al guardar, se agregarán como 'FALTANTE' con un impuesto de $0.00 para no alterar tus gastos.")
                        with st.expander("Ver Trackings Faltantes"):
                            st.write(prev['faltantes_list'])
                    else:
                        st.success("✅ Todos los paquetes están en tu base de datos.")
                        
                    if st.button("💾 Confirmar y Registrar Liquidación", type="primary"):
                        try:
                            # 1. Insertar el Invoice
                            sql_liq = """INSERT INTO temu_hn_liquidaciones 
                                         (invoice_num, fecha_invoice, paquetes_declarados, monto_pagado, paquetes_encontrados, paquetes_faltantes, registrado_por) 
                                         VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                            cur.execute(sql_liq, (prev['inv_num'], prev['fecha_liq'], prev['paq_liq'], prev['monto_liq'], prev['encontrados'], prev['faltantes'], user_info['username']))
                            liq_id = cur.lastrowid
                            
                            # 2. Actualizar los encontrados
                            if prev['ids_encontrados']:
                                ids = prev['ids_encontrados']
                                chunk_sz = 2000
                                for i in range(0, len(ids), chunk_sz):
                                    lote_ids = ids[i:i+chunk_sz]
                                    format_ids = ','.join(['%s'] * len(lote_ids))
                                    cur.execute(f"UPDATE temu_hn_impuestos_paquetes SET liquidado = TRUE, liquidacion_id = %s WHERE id IN ({format_ids})", [liq_id] + lote_ids)
                            
                            # 3. Insertar los faltantes con $0.00
                            if prev['faltantes_list']:
                                sql_f = "INSERT INTO temu_hn_impuestos_paquetes (master_num, tracking_a, tracking_b, total_usd, liquidado, liquidacion_id) VALUES (%s, %s, %s, %s, %s, %s)"
                                data_f = [("FALTANTE", t, "N/A", 0.00, True, liq_id) for t in prev['faltantes_list']]
                                chunk_sz = 2000
                                for i in range(0, len(data_f), chunk_sz):
                                    cur.executemany(sql_f, data_f[i:i+chunk_sz])
                                    
                            # 4. Sumar el dinero de TEMU al balance global
                            cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = liquidado_temu + %s WHERE id = 1", (prev['monto_liq'],))
                            conn.commit()
                            
                            del st.session_state['liq_preview']
                            st.success("¡Invoice registrado y paquetes liquidados exitosamente!")
                            st.rerun()
                        except Exception as eliq:
                            conn.rollback()
                            st.error(f"Error al guardar liquidación: {eliq}")
                else:
                    st.info("Ingresa los datos de la Factura y presiona 'Verificar Conciliación' para ver el análisis aquí.")

            st.divider()
            
            # --- HISTORIAL DE LIQUIDACIONES ---
            with st.expander("📜 Historial de Liquidaciones (Invoices)", expanded=False):
                cur.execute("SELECT id, invoice_num, fecha_invoice, paquetes_declarados, monto_pagado, paquetes_faltantes, registrado_por FROM temu_hn_liquidaciones ORDER BY id DESC")
                hist_liq = cur.fetchall()
                if hist_liq:
                    df_liq = pd.DataFrame(hist_liq)
                    st.dataframe(df_liq.rename(columns={'invoice_num':'Invoice', 'fecha_invoice':'Fecha', 'paquetes_declarados':'Paq.', 'monto_pagado':'Monto ($)', 'paquetes_faltantes':'Faltantes'}), hide_index=True, use_container_width=True)
                    
                    st.write("**Opciones de Gestión**")
                    liq_sel = st.selectbox("Seleccione Invoice a eliminar:", df_liq['invoice_num'].tolist())
                    
                    cur.execute("SELECT id, monto_pagado FROM temu_hn_liquidaciones WHERE invoice_num = %s", (liq_sel,))
                    liq_data = cur.fetchone()
                    
                    if st.button("⚠️ Eliminar Invoice y Revertir Liquidación", type="primary"):
                        if liq_data:
                            l_id = liq_data['id']
                            cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = liquidado_temu - %s WHERE id = 1", (liq_data['monto_pagado'],))
                            cur.execute("DELETE FROM temu_hn_impuestos_paquetes WHERE master_num = 'FALTANTE' AND liquidacion_id = %s", (l_id,))
                            cur.execute("UPDATE temu_hn_impuestos_paquetes SET liquidado = FALSE, liquidacion_id = NULL WHERE liquidacion_id = %s", (l_id,))
                            cur.execute("DELETE FROM temu_hn_liquidaciones WHERE id = %s", (l_id,))
                            
                            conn.commit()
                            st.success(f"Invoice {liq_sel} revertido exitosamente.")
                            st.rerun()
                else:
                    st.info("No hay liquidaciones registradas aún.")

    except Exception as general_error:
        st.error(f"Error general en el módulo: {general_error}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
