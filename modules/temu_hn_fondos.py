import streamlit as st
import pandas as pd
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
                    INDEX idx_tracking_a (tracking_a),
                    INDEX idx_tracking_b (tracking_b),
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
        # --- DATOS FINANCIEROS ---
        cur.execute("SELECT * FROM temu_hn_resumen WHERE id = 1")
        resumen = cur.fetchone()
        
        impuestos = float(resumen['impuestos_pagados'])
        liquidado = float(resumen['liquidado_temu'])
        deposito = float(resumen['deposito_inicial'])
        
        total_pagos = liquidado + deposito
        saldo_disponible = total_pagos - impuestos

        # --- DATOS DE PAQUETES ---
        cur.execute("SELECT COUNT(*) as total FROM temu_hn_impuestos_paquetes")
        tot_paq = cur.fetchone()['total'] or 0
        
        cur.execute("SELECT COUNT(*) as liquidados FROM temu_hn_impuestos_paquetes WHERE liquidado = TRUE")
        tot_liq = cur.fetchone()['liquidados'] or 0
        
        tot_pend = tot_paq - tot_liq

        t1, t2 = st.tabs(["📊 Resumen y Másters", "📦 Liquidación y Correcciones"])
        
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
                
                st.write("### Estado de Paquetes")
                cp1, cp2, cp3 = st.columns(3)
                cp1.metric("Imp. Pagados", f"{tot_paq:,} pq")
                cp2.metric("Liquidados", f"{tot_liq:,} pq")
                cp3.metric("Pendientes", f"{tot_pend:,} pq")
                st.divider()
                
                with st.expander("📂 Cargar Impuestos de Másters (Excel)", expanded=True):
                    archivos_excel = st.file_uploader("Subir archivos (El nombre del archivo debe ser la Máster)", type=["xlsx", "xls"], accept_multiple_files=True)
                    
                    if archivos_excel:
                        resultados = []
                        total_calculado = 0.0
                        
                        for archivo in archivos_excel:
                            try:
                                df_imp = pd.read_excel(archivo)
                                master_num = archivo.name.replace(".xlsx", "").replace(".xls", "")
                                
                                if df_imp.shape[1] >= 19:
                                    trackings_a = df_imp.iloc[:, 0].astype(str).str.strip().tolist()
                                    trackings_b = df_imp.iloc[:, 1].astype(str).str.strip().tolist()
                                    
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
                                    
                                    paquetes_data = list(zip(
                                        [master_num] * len(df_imp), trackings_a, trackings_b, df_imp['Total_USD'].tolist()
                                    ))
                                    
                                    resultados.append({
                                        'Máster': master_num,
                                        'Fecha Decl.': str(df_imp.iloc[0, 17]) if len(df_imp) > 0 else "N/A",
                                        'Paquetes': len(df_imp),
                                        'DAI ($)': df_imp['DAI_USD'].sum(),
                                        'SEL ($)': df_imp['SEL_USD'].sum(),
                                        'IVA ($)': df_imp['IVA_USD'].sum(),
                                        'Total Impuestos ($)': tot_usd,
                                        'paquetes_data': paquetes_data
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
                                        sql_m = """INSERT INTO temu_hn_impuestos_master 
                                                   (master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, registrado_por) 
                                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                                        cur.execute(sql_m, (r['Máster'], r['Fecha Decl.'], r['Paquetes'], r['DAI ($)'], r['SEL ($)'], r['IVA ($)'], r['Total Impuestos ($)'], user_info['username']))
                                        
                                        sql_p = "INSERT INTO temu_hn_impuestos_paquetes (master_num, tracking_a, tracking_b, total_usd) VALUES (%s, %s, %s, %s)"
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
                            'master_num':'Máster', 'fecha_declaracion':'Fecha Decl.', 'cantidad_paquetes':'Paq.', 
                            'dai_usd':'DAI ($)', 'sel_usd':'SEL ($)', 'iva_usd':'IVA ($)', 
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
                                cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados - %s WHERE id = 1", (m_data['total_impuestos_usd'],))
                                cur.execute("DELETE FROM temu_hn_impuestos_master WHERE id = %s", (m_data['id'],))
                                cur.execute("DELETE FROM temu_hn_impuestos_paquetes WHERE master_num = %s", (master_sel,))
                                conn.commit()
                                st.success(f"Máster eliminada. Se restaron ${m_data['total_impuestos_usd']:,.2f} y se borraron sus paquetes.")
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
                                cur.execute("INSERT INTO temu_hn_movimientos (concepto, entrada, salida) VALUES (%s, %s, %s)", (concepto, entrada, salida))
                                conn.commit()
                                st.rerun()
                            else:
                                st.error("Debe ingresar un concepto.")
                                
                if st.button("🗑️ Limpiar Historial de Movimientos"):
                    cur.execute("TRUNCATE TABLE temu_hn_movimientos")
                    conn.commit()
                    st.rerun()

        # ==========================================
        # PESTAÑA 2: LIQUIDACIÓN POR PAQUETES Y CORRECCIÓN
        # ==========================================
        with t2:
            st.write("### 🔍 Conciliación y Liquidación de Paquetes")
            
            c_liq1, c_liq2 = st.columns([1, 1])
            
            with c_liq1:
                # NUEVO: Selector de acción (Liquidar vs Deshacer)
                operacion = st.radio("Acción a realizar:", ["✅ Liquidar Paquetes (Sumar al fondo)", "⏪ Revertir Liquidación (Restar del fondo)"])
                
                st.markdown("Pega la lista de Trackings a procesar. El sistema buscará en la Columna A o B.")
                txt_trackings = st.text_area("Pegar Trackings (Uno por línea)", height=300)
                
                if st.button("🔍 Calcular", type="primary"):
                    if txt_trackings.strip():
                        lista_raw = [x.strip() for x in txt_trackings.split('\n') if x.strip()]
                        lista_unicos = list(set(lista_raw))
                        
                        with st.spinner("Buscando paquetes..."):
                            todos_los_datos = []
                            BATCH_SIZE = 1000 
                            for i in range(0, len(lista_unicos), BATCH_SIZE):
                                lote = lista_unicos[i : i + BATCH_SIZE]
                                format_strings = ','.join(['%s'] * len(lote))
                                
                                query = f"""
                                    SELECT id, master_num, tracking_a, tracking_b, total_usd, liquidado 
                                    FROM temu_hn_impuestos_paquetes 
                                    WHERE tracking_a IN ({format_strings}) OR tracking_b IN ({format_strings})
                                """
                                cur.execute(query, tuple(lote) + tuple(lote))
                                todos_los_datos.extend(cur.fetchall())
                            
                            df_found = pd.DataFrame(todos_los_datos)
                            
                            if not df_found.empty:
                                df_found = df_found.drop_duplicates(subset=['tracking_a', 'tracking_b'])
                                
                                # NUEVO: Separar los válidos dependiendo de la operación elegida
                                if "Liquidar" in operacion:
                                    df_validos = df_found[df_found['liquidado'] == False] # Queremos cobrar los pendientes
                                    df_omitidos = df_found[df_found['liquidado'] == True] # Ya los cobramos antes
                                else:
                                    df_validos = df_found[df_found['liquidado'] == True]  # Queremos revertir los que ya cobramos
                                    df_omitidos = df_found[df_found['liquidado'] == False]# No se pueden revertir si están pendientes
                                
                                total_operacion = float(df_validos['total_usd'].sum()) if not df_validos.empty else 0.0
                                
                                st.session_state['liq_op'] = operacion
                                st.session_state['liq_total'] = total_operacion
                                st.session_state['liq_df_validos'] = df_validos
                                st.session_state['liq_omitidos'] = len(df_omitidos)
                                st.session_state['liq_faltantes'] = len(lista_unicos) - len(df_found)
                            else:
                                st.warning("No se encontró ningún tracking de esta lista en la base de datos.")
                                if 'liq_total' in st.session_state: del st.session_state['liq_total']
                    else:
                        st.warning("Debe ingresar al menos un tracking.")
            
            with c_liq2:
                if 'liq_total' in st.session_state:
                    if "Liquidar" in st.session_state['liq_op']:
                        st.success(f"### Total a Liquidar: ${st.session_state['liq_total']:,.2f} USD")
                    else:
                        st.error(f"### Total a Revertir: ${st.session_state['liq_total']:,.2f} USD")
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Paquetes Válidos", len(st.session_state['liq_df_validos']))
                    m2.metric("Omitidos (Estado incorrecto)", st.session_state['liq_omitidos'])
                    m3.metric("No Encontrados", st.session_state['liq_faltantes'])
                    
                    if not st.session_state['liq_df_validos'].empty:
                        df_display = st.session_state['liq_df_validos'].rename(columns={
                            'master_num':'Máster', 'tracking_a':'Guía A', 'tracking_b':'Platform B', 'total_usd':'Impuesto ($)'
                        })
                        st.dataframe(df_display[['Máster', 'Guía A', 'Platform B', 'Impuesto ($)']], height=150, use_container_width=True)
                    else:
                        st.info("Todos los trackings pegados fueron omitidos o no encontrados.")
                    
                    st.info(f"Fondo 'Liquidado por TEMU' actual: **${liquidado:,.2f}**")
                    
                    # LOGICA DE APLICACIÓN
                    if not st.session_state['liq_df_validos'].empty:
                        ids_paquetes = st.session_state['liq_df_validos']['id'].tolist()
                        format_ids = ','.join(['%s'] * len(ids_paquetes))
                        
                        if "Liquidar" in st.session_state['liq_op']:
                            accion_liq = st.radio("Método de aplicación:", ["Sumarlo al balance actual", "Reemplazar balance completamente"])
                            if st.button("💾 Aplicar Liquidación y Marcar como Pagados", type="primary"):
                                
                                if "Sumarlo" in accion_liq:
                                    nuevo_liq = liquidado + st.session_state['liq_total']
                                    cur.execute(f"UPDATE temu_hn_impuestos_paquetes SET liquidado = TRUE WHERE id IN ({format_ids})", tuple(ids_paquetes))
                                else:
                                    nuevo_liq = st.session_state['liq_total']
                                    cur.execute("UPDATE temu_hn_impuestos_paquetes SET liquidado = FALSE") # Limpia todo
                                    cur.execute(f"UPDATE temu_hn_impuestos_paquetes SET liquidado = TRUE WHERE id IN ({format_ids})", tuple(ids_paquetes))
                                
                                cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = %s WHERE id = 1", (nuevo_liq,))
                                conn.commit()
                                
                                del st.session_state['liq_total']
                                st.success("¡Balance actualizado y paquetes marcados como Liquidados!")
                                st.rerun()
                                
                        else: # Es una Reversión
                            if st.button("⚠️ Confirmar Reversión (Restar dinero y volver a Pendientes)", type="primary"):
                                nuevo_liq = max(0, liquidado - st.session_state['liq_total']) # Evita que baje de cero
                                
                                cur.execute(f"UPDATE temu_hn_impuestos_paquetes SET liquidado = FALSE WHERE id IN ({format_ids})", tuple(ids_paquetes))
                                cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = %s WHERE id = 1", (nuevo_liq,))
                                conn.commit()
                                
                                del st.session_state['liq_total']
                                st.success("¡Liquidación revertida! El dinero fue restado y los paquetes vuelven a estar pendientes.")
                                st.rerun()
                else:
                    st.info("Ingrese los trackings y presione 'Calcular' para ver los resultados aquí.")
            
            st.divider()
            # NUEVO: Botón de Limpieza Global en caso de emergencia
            with st.expander("🚨 Opciones Avanzadas (Limpieza General)", expanded=False):
                st.warning("Si tus balances están descuadrados o quieres volver a hacer tu liquidación desde cero, utiliza este botón. **OJO: Esto no borra tus archivos Másters**, solo reinicia a cero el fondo 'Liquidado por TEMU' y vuelve todos los paquetes al estado 'Pendientes'.")
                if st.button("Limpiar TODAS las Liquidaciones (Reset a Cero)"):
                    cur.execute("UPDATE temu_hn_resumen SET liquidado_temu = 0 WHERE id = 1")
                    cur.execute("UPDATE temu_hn_impuestos_paquetes SET liquidado = FALSE")
                    conn.commit()
                    st.success("Se ha reiniciado el sistema. Todos los paquetes están pendientes de liquidar.")
                    st.rerun()
                    
            st.write("### 📦 Visualizador General de Paquetes")
            cur.execute("SELECT master_num as 'Máster', tracking_a as 'Guía (A)', tracking_b as 'Platform (B)', total_usd as 'Impuesto USD ($)', liquidado as '¿Liquidado?' FROM temu_hn_impuestos_paquetes ORDER BY id DESC LIMIT 100")
            
            datos_prev = cur.fetchall()
            if datos_prev:
                df_preview = pd.DataFrame(datos_prev)
                df_preview['¿Liquidado?'] = df_preview['¿Liquidado?'].apply(lambda x: "✅ Sí" if x else "❌ No")
                st.dataframe(df_preview, hide_index=True, use_container_width=True)
            else:
                st.caption("No hay paquetes registrados.")

    finally:
        conn.close()
