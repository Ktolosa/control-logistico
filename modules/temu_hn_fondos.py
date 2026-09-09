import streamlit as st
import pandas as pd
from utils import get_connection

# --- 1. INICIALIZAR BASE DE DATOS ---
def init_fondos_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Resumen global de fondos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_resumen (
                    id INT PRIMARY KEY DEFAULT 1,
                    impuestos_pagados DECIMAL(15,2) DEFAULT 0.00,
                    liquidado_temu DECIMAL(15,2) DEFAULT 0.00,
                    deposito_inicial DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            cur.execute("INSERT IGNORE INTO temu_hn_resumen (id) VALUES (1);")
            
            # Movimientos (Entradas y Salidas extras)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_movimientos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    concepto VARCHAR(100),
                    entrada DECIMAL(15,2) DEFAULT 0.00,
                    salida DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            
            # Tabla de Impuestos por Máster (AHORA CON LONGBLOB PARA GUARDAR EL EXCEL)
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
                    archivo_excel LONGBLOB,
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    registrado_por VARCHAR(100)
                );
            """)
            
            # Script de seguridad: Añadir la columna de archivo a tablas existentes sin borrar datos
            try: cur.execute("ALTER TABLE temu_hn_impuestos_master ADD COLUMN archivo_excel LONGBLOB;")
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
        cur.execute("SELECT * FROM temu_hn_resumen WHERE id = 1")
        resumen = cur.fetchone()
        
        impuestos = float(resumen['impuestos_pagados'])
        liquidado = float(resumen['liquidado_temu'])
        deposito = float(resumen['deposito_inicial'])
        
        total_pagos = liquidado + deposito
        saldo_disponible = total_pagos - impuestos

        col_izq, col_espacio, col_der = st.columns([5, 1, 5])
        
        # ==========================================
        # TABLA DERECHA: RESUMEN GLOBAL Y LECTOR EXCEL
        # ==========================================
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
            
            # --- LECTOR INTELIGENTE DE EXCEL ---
            with st.expander("📂 Cargar Impuestos de Másters (Excel)", expanded=True):
                st.caption("Procesa los archivos de impuestos. El sistema convertirá HNL a USD automáticamente según la Tasa de Cambio.")
                archivos_excel = st.file_uploader("Subir archivos (El nombre del archivo debe ser la Máster)", type=["xlsx", "xls"], accept_multiple_files=True)
                
                if archivos_excel:
                    resultados = []
                    total_calculado = 0.0
                    
                    for archivo in archivos_excel:
                        try:
                            # Guardamos los bytes originales para meterlos a la BD después
                            file_bytes = archivo.getvalue()
                            
                            df_imp = pd.read_excel(archivo)
                            master_num = archivo.name.replace(".xlsx", "").replace(".xls", "")
                            
                            if df_imp.shape[1] >= 19:
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
                                
                                resultados.append({
                                    'Máster': master_num,
                                    'Fecha Decl.': str(df_imp.iloc[0, 17]) if len(df_imp) > 0 else "N/A",
                                    'Paquetes': len(df_imp),
                                    'DAI ($)': df_imp['DAI_USD'].sum(),
                                    'SEL ($)': df_imp['SEL_USD'].sum(),
                                    'IVA ($)': df_imp['IVA_USD'].sum(),
                                    'Total Impuestos ($)': tot_usd,
                                    'Archivo_Bytes': file_bytes
                                })
                                total_calculado += tot_usd
                            else:
                                st.error(f"El archivo {archivo.name} no tiene la estructura correcta.")
                        except Exception as e:
                            st.error(f"Error procesando {archivo.name}: {e}")
                    
                    if resultados:
                        df_res_view = pd.DataFrame(resultados).drop(columns=['Archivo_Bytes'])
                        st.write("**Resumen de archivos listos para procesar:**")
                        st.dataframe(df_res_view.style.format({"DAI ($)": "{:,.2f}", "SEL ($)": "{:,.2f}", "IVA ($)": "{:,.2f}", "Total Impuestos ($)": "{:,.2f}"}), hide_index=True)
                        st.success(f"**Total a sumar al balance: ${total_calculado:,.2f} USD**")
                        
                        if st.button("💾 Guardar Másters y Sumar a Impuestos", type="primary"):
                            nuevos = 0; suma_real = 0.0
                            for r in resultados:
                                cur.execute("SELECT id FROM temu_hn_impuestos_master WHERE master_num = %s", (r['Máster'],))
                                if cur.fetchone():
                                    st.warning(f"⚠️ La Máster **{r['Máster']}** ya existe. Se omitió.")
                                else:
                                    sql_m = """INSERT INTO temu_hn_impuestos_master 
                                               (master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, archivo_excel, registrado_por) 
                                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                                    cur.execute(sql_m, (r['Máster'], r['Fecha Decl.'], r['Paquetes'], r['DAI ($)'], r['SEL ($)'], r['IVA ($)'], r['Total Impuestos ($)'], r['Archivo_Bytes'], user_info['username']))
                                    suma_real += r['Total Impuestos ($)']
                                    nuevos += 1
                                    
                            if nuevos > 0:
                                cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados + %s WHERE id = 1", (suma_real,))
                                conn.commit()
                                st.success("✅ Guardado exitosamente.")
                                st.rerun()

            # --- NUEVO GESTOR DE HISTORIAL Y ELIMINACIÓN ---
            with st.expander("📜 Historial y Gestión de Másters", expanded=False):
                cur.execute("SELECT id, master_num, fecha_declaracion, cantidad_paquetes, total_impuestos_usd, registrado_por FROM temu_hn_impuestos_master ORDER BY id DESC")
                historial_masters = cur.fetchall()
                
                if historial_masters:
                    df_hist = pd.DataFrame(historial_masters)
                    # Renombrar para visualización
                    df_view = df_hist.rename(columns={'master_num':'Máster', 'fecha_declaracion':'Fecha Decl.', 'cantidad_paquetes':'Paq.', 'total_impuestos_usd':'Total ($)', 'registrado_por':'Responsable'})
                    st.dataframe(df_view[['Máster', 'Fecha Decl.', 'Paq.', 'Total ($)', 'Responsable']], hide_index=True)
                    
                    st.divider()
                    st.write("**Opciones de Gestión**")
                    master_sel = st.selectbox("Seleccione la Máster:", df_hist['master_num'].tolist())
                    
                    # Recuperar el ID y el Blob del archivo seleccionado
                    cur.execute("SELECT id, total_impuestos_usd, archivo_excel FROM temu_hn_impuestos_master WHERE master_num = %s", (master_sel,))
                    m_data = cur.fetchone()
                    
                    c1, c2 = st.columns(2)
                    
                    if m_data and m_data['archivo_excel']:
                        c1.download_button(
                            label="⬇️ Descargar Excel Original", 
                            data=m_data['archivo_excel'], 
                            file_name=f"{master_sel}.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        c1.info("Sin archivo adjunto")
                        
                    if c2.button("🗑️ Eliminar y Revertir Balance", type="primary", use_container_width=True):
                        if m_data:
                            # 1. Restarle los impuestos al Total Global
                            cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados - %s WHERE id = 1", (m_data['total_impuestos_usd'],))
                            # 2. Borrar el registro
                            cur.execute("DELETE FROM temu_hn_impuestos_master WHERE id = %s", (m_data['id'],))
                            conn.commit()
                            st.success(f"La Máster {master_sel} ha sido eliminada y se restaron ${m_data['total_impuestos_usd']:,.2f} del total pagado.")
                            st.rerun()
                else:
                    st.info("Aún no se han procesado másters.")

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

        # ==========================================
        # TABLA IZQUIERDA: FLUJO Y BALANCE
        # ==========================================
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

    finally:
        conn.close()
