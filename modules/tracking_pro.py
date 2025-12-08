import streamlit as st
import pandas as pd
import time
from utils import (
    guardar_base_tracking, 
    buscar_trackings_masivo, 
    obtener_resumen_bases, 
    eliminar_base_invoice, 
    to_excel_bytes,
    init_tracking_db
)

def show(user_info):
    # Aseguramos que la tabla exista
    init_tracking_db()
    
    st.title("🔍 Tracking Pro")
    st.markdown("Gestión masiva de bases de datos de guías e Invoices.")

    t1, t2, t3 = st.tabs(["📊 Comparar Trackings", "➕ Crear Base de Datos", "⚙️ Gestionar Bases"])

    # --- PESTAÑA 1: COMPARAR ---
    with t1:
        st.subheader("Comparar contra Base de Datos")
        st.caption("Pega una lista de trackings para saber a qué Invoice pertenecen.")
        
        txt_input = st.text_area("Pegar trackings (uno por línea)", height=200, key="compare_input")
        
        if st.button("🔍 Comparar", type="primary"):
            if not txt_input.strip():
                st.warning("La lista está vacía")
            else:
                lista_raw = [x.strip() for x in txt_input.split('\n') if x.strip()]
                lista_unicos = list(set(lista_raw))
                
                with st.spinner(f"Buscando {len(lista_unicos)} guías..."):
                    df_found = buscar_trackings_masivo(lista_unicos)
                
                # Procesar resultados
                resultados = []
                mapa_invoices = {}
                encontrados_set = set()
                
                if not df_found.empty:
                    df_found['tracking'] = df_found['tracking'].astype(str)
                    mapa_invoices = dict(zip(df_found['tracking'], df_found['invoice']))
                    encontrados_set = set(df_found['tracking'])
                
                for t in lista_unicos:
                    status = mapa_invoices.get(str(t), "❌ NO ENCONTRADO")
                    resultados.append({"Tracking": t, "Status / Invoice": status})
                
                df_res = pd.DataFrame(resultados)
                
                # Métricas
                total = len(lista_unicos)
                enc = len(encontrados_set)
                falt = total - enc
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Consultados", total)
                m2.metric("Encontrados", enc)
                m3.metric("No Encontrados", falt, delta_color="inverse")
                
                st.dataframe(df_res, use_container_width=True)
                
                excel_data = to_excel_bytes(df_res, 'xlsx')
                st.download_button("📥 Descargar Resultados (Excel)", excel_data, "resultados_tracking.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

    # --- PESTAÑA 2: CREAR ---
    with t2:
        st.subheader("Crear Nueva Base (Invoice)")
        
        c1, c2 = st.columns([1, 2])
        invoice_num = c1.text_input("Número de Invoice / Contenedor")
        
        st.write("Pegar lista de Trackings para este Invoice:")
        txt_create = st.text_area("Trackings (uno por línea)", height=200, key="create_input")
        
        lista_clean = []
        if txt_create:
            lista_clean = [x.strip() for x in txt_create.split('\n') if x.strip()]
            lista_clean = list(set(lista_clean))
        
        st.caption(f"Trackings detectados: {len(lista_clean)}")
        
        if st.button("💾 Guardar Base de Datos", type="primary"):
            if not invoice_num or not lista_clean:
                st.error("Faltan datos (Invoice o Lista de Trackings)")
            else:
                with st.spinner("Guardando en la nube..."):
                    ok, msg = guardar_base_tracking(invoice_num, lista_clean)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.balloons()
                        time.sleep(1)
                        st.rerun() # Recarga para actualizar la lista de gestión
                    else:
                        st.error(f"Error: {msg}")

    # --- PESTAÑA 3: GESTIONAR ---
    with t3:
        st.subheader("Invoices Registrados")
        
        df_summary = obtener_resumen_bases()
        
        if df_summary.empty:
            st.info("No se encontraron bases de datos registradas.")
        else:
            st.dataframe(
                df_summary, 
                column_config={
                    "invoice": "Número de Invoice",
                    "cantidad": st.column_config.NumberColumn("Cantidad Trackings", format="%d"),
                    "fecha_creacion": st.column_config.DatetimeColumn("Fecha Creación", format="DD/MM/YYYY HH:mm")
                },
                use_container_width=True
            )
            
            st.divider()
            st.write("🗑️ **Eliminar Invoice**")
            
            list_inv = df_summary['invoice'].tolist()
            sel_del = st.selectbox("Seleccionar Invoice a Eliminar", list_inv)
            
            if st.button("Eliminar Base Seleccionada", type="primary"):
                if eliminar_base_invoice(sel_del):
                    st.success(f"Base {sel_del} eliminada.")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Error al eliminar.")
