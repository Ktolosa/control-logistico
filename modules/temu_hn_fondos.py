import streamlit as st
import pandas as pd
from utils import get_connection

def init_fondos_db():
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Tabla para el resumen global (solo tendrá 1 fila de configuración)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_resumen (
                    id INT PRIMARY KEY DEFAULT 1,
                    impuestos_pagados DECIMAL(15,2) DEFAULT 0.00,
                    liquidado_temu DECIMAL(15,2) DEFAULT 0.00,
                    deposito_inicial DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            cur.execute("INSERT IGNORE INTO temu_hn_resumen (id) VALUES (1);")
            
            # Tabla para los movimientos (entradas y salidas)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temu_hn_movimientos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    concepto VARCHAR(100),
                    entrada DECIMAL(15,2) DEFAULT 0.00,
                    salida DECIMAL(15,2) DEFAULT 0.00
                );
            """)
            conn.commit()
        except Exception as e:
            pass
        finally:
            conn.close()

def show(user_info):
    init_fondos_db()
    st.title("🇭🇳 Control de Fondos - TEMU HN")
    
    conn = get_connection()
    if not conn:
        st.error("Error de conexión a la base de datos.")
        return
        
    try:
        # --- CARGAR DATOS GLOBALES ---
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM temu_hn_resumen WHERE id = 1")
        resumen = cur.fetchone()
        
        impuestos = float(resumen['impuestos_pagados'])
        liquidado = float(resumen['liquidado_temu'])
        deposito = float(resumen['deposito_inicial'])
        
        total_pagos = liquidado + deposito
        saldo_disponible = total_pagos - impuestos

        # --- MAQUETACIÓN EN 2 COLUMNAS (Igual a tu Excel) ---
        col_izq, col_espacio, col_der = st.columns([5, 1, 4])
        
        # ==========================================
        # TABLA DERECHA: RESUMEN GLOBAL
        # ==========================================
        with col_der:
            st.write("### Resumen Global")
            
            # Mostrar tabla estática
            df_resumen = pd.DataFrame([
                {"CONCEPTO": "Impuestos pagados", "MONTO": f"${impuestos:,.2f}"},
                {"CONCEPTO": "Liquidado por TEMU", "MONTO": f"${liquidado:,.2f}"},
                {"CONCEPTO": "Deposito inicial", "MONTO": f"${deposito:,.2f}"},
                {"CONCEPTO": "Total pagos TEMU", "MONTO": f"${total_pagos:,.2f}"},
                {"CONCEPTO": "Saldo disponible para impuesto", "MONTO": f"${saldo_disponible:,.2f}"}
            ])
            st.dataframe(df_resumen, hide_index=True, use_container_width=True)
            
            with st.expander("✏️ Actualizar Montos Globales"):
                with st.form("form_global"):
                    new_imp = st.number_input("Impuestos pagados", value=impuestos, step=100.0)
                    new_liq = st.number_input("Liquidado por TEMU", value=liquidado, step=100.0)
                    new_dep = st.number_input("Deposito inicial", value=deposito, step=100.0)
                    if st.form_submit_button("Actualizar", type="primary"):
                        cur.execute("UPDATE temu_hn_resumen SET impuestos_pagados=%s, liquidado_temu=%s, deposito_inicial=%s WHERE id=1", 
                                    (new_imp, new_liq, new_dep))
                        conn.commit()
                        st.rerun()

        # ==========================================
        # TABLA IZQUIERDA: FLUJO Y BALANCE
        # ==========================================
        with col_izq:
            st.write("### Flujo Operativo")
            
            # Cargar movimientos
            cur.execute("SELECT concepto, entrada, salida FROM temu_hn_movimientos ORDER BY id ASC")
            movimientos = cur.fetchall()
            
            # Construir el DataFrame con Balance Dinámico
            filas = []
            balance_actual = saldo_disponible
            
            # Fila 1 obligatoria: El disponible que viene del resumen
            filas.append({
                "CONCEPTO": "DISPONIBLE SEGÚN TEMU", 
                "ENTRADAS": f"${saldo_disponible:,.2f}", 
                "SALIDAS": "", 
                "BALANCE": f"${balance_actual:,.2f}"
            })
            
            # Procesar el resto de movimientos
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
