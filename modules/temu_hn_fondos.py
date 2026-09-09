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
            
            # NUEVO: Tabla para guardar el desglose de Impuestos por Máster
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
            
            # --- LECTOR INTELIGENTE DE EXCEL (IMPUESTOS POR MÁSTER) ---
            with st.expander("📂 Cargar Impuestos de Másters (Excel)", expanded=True):
                st.caption("Procesa los archivos de impuestos. El sistema convertirá HNL a USD automáticamente según la Tasa de Cambio declarada en el archivo.")
                archivos_excel = st.file_uploader("Subir archivos (El nombre del archivo debe ser la Máster)", type=["xlsx", "xls"], accept_multiple_files=True)
                
                if archivos_excel:
                    resultados = []
                    total_calculado = 0.0
                    
                    for archivo in archivos_excel:
                        try:
                            df_imp = pd.read_excel(archivo)
                            master_num = archivo.name.replace(".xlsx", "").replace(".xls", "")
                            
                            # Validar que tenga las columnas necesarias (hasta la S = índice 18)
                            if df_imp.shape[1] >= 19:
                                # Convertir a numérico para evitar errores de texto
                                df_imp.iloc[:, 7] = pd.to_numeric(df_imp.iloc[:, 7], errors='coerce').fillna(0) # H: Total Lempiras
                                df_imp.iloc[:, 8] = pd.to_numeric(df_imp.iloc[:, 8], errors='coerce').fillna(0) # I: DAI
                                df_imp.iloc[:, 9] = pd.to_numeric(df_imp.iloc[:, 9], errors='coerce').fillna(0) # J: SEL
                                df_imp.iloc[:, 10] = pd.to_numeric(df_imp.iloc[:, 10], errors='coerce').fillna(0) # K: IVA
                                df_imp.iloc[:, 18] = pd.to_numeric(df_imp.iloc[:, 18], errors='coerce').fillna(1) # S: Tasa Cambio
                                
                                # Convertir Lempiras a Dólares por fila (Monto / Tasa de cambio)
                                df_imp['DAI_USD'] = df_imp.iloc[:, 8] / df_imp.iloc[:, 18]
                                df_imp['SEL_USD'] = df_imp.iloc[:, 9] / df_imp.iloc[:, 18]
                                df_imp['IVA_USD'] = df_imp.iloc[:, 10] / df_imp.iloc[:, 18]
                                df_imp['Total_USD'] = df_imp.iloc[:, 7] / df_imp.iloc[:, 18]
                                
                                dai_usd = df_imp['DAI_USD'].sum()
                                sel_usd = df_imp['SEL_USD'].sum()
                                iva_usd = df_imp['IVA_USD'].sum()
                                tot_usd = df_imp['Total_USD'].sum()
                                
                                cant_paq = len(df_imp)
                                fecha_dec = str(df_imp.iloc[0, 17]) if len(df_imp) > 0 else "N/A"
                                
                                resultados.append({
                                    'Máster': master_num,
                                    'Fecha Decl.': fecha_dec,
                                    'Paquetes': cant_paq,
                                    'DAI ($)': dai_usd,
                                    'SEL ($)': sel_usd,
                                    'IVA ($)': iva_usd,
                                    'Total Impuestos ($)': tot_usd
                                })
                                total_calculado += tot_usd
                            else:
                                st.error(f"El archivo {archivo.name} no tiene la estructura correcta de columnas.")
                        except Exception as e:
                            st.error(f"Error procesando {archivo.name}: {e}")
                    
                    if resultados:
                        df_res_view = pd.DataFrame(resultados)
                        st.write("**Resumen de archivos listos para procesar:**")
                        # Formato de visualización de monedas
                        st.dataframe(df_res_view.style.format({"DAI ($)": "{:,.2f}", "SEL ($)": "{:,.2f}", "IVA ($)": "{:,.2f}", "Total Impuestos ($)": "{:,.2f}"}), hide_index=True)
                        st.success(f"**Total calculado para sumar al balance: ${total_calculado:,.2f} USD**")
                        
                        if st.button("💾 Guardar Másters y Sumar a Impuestos", type="primary"):
                            nuevos_ingresados = 0
                            suma_real = 0.0
                            
                            for r in resultados:
                                # Validación de seguridad: Evitar procesar la misma Máster 2 veces
                                cur.execute("SELECT id FROM temu_hn_impuestos_master WHERE master_num = %s", (r['Máster'],))
                                if cur.fetchone():
                                    st.warning(f"⚠️ La Máster **{r['Máster']}** ya existe en la base de datos. Se omitió para evitar cobros dobles.")
                                else:
                                    sql_m = """INSERT INTO temu_hn_impuestos_master 
                                               (master_num, fecha_declaracion, cantidad_paquetes, dai_usd, sel_usd, iva_usd, total_impuestos_usd, registrado_por) 
                                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                                    cur.execute(sql_m, (r['Máster'], r['Fecha Decl.'], r['Paquetes'], r['DAI ($)'], r['SEL ($)'], r['IVA ($)'], r['Total Impuestos ($)'], user_info['username']))
                                    suma_real += r['Total Impuestos ($)']
                                    nuevos_ingresados += 1
                                    
                            if nuevos_ingresados > 0:
                                # Actualizar el balance global automáticamente
                                cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados = impuestos_pagados + %s WHERE id = 1", (suma_real,))
                                conn.commit()
                                st.success(f"✅ Se guardaron {nuevos_ingresados} másters exitosamente y se sumaron ${suma_real:,.2f} a los impuestos pagados.")
                                st.rerun()

            with st.expander("📜 Historial de Másters Procesadas"):
                cur.execute("SELECT master_num as 'Máster', fecha_declaracion as 'Fecha Decl.', cantidad_paquetes as 'Paquetes', dai_usd as 'DAI ($)', iva_usd as 'IVA ($)', total_impuestos_usd as 'Total ($)', registrado_por as 'Responsable' FROM temu_hn_impuestos_master ORDER BY id DESC LIMIT 50")
                historial_masters = cur.fetchall()
                if historial_masters:
                    st.dataframe(pd.DataFrame(historial_masters), hide_index=True, use_container_width=True)
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
