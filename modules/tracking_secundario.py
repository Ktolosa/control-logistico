import streamlit as st
import pandas as pd
import time
from utils import (
    guardar_base_tracking_2, 
    buscar_trackings_masivo_2, 
    obtener_resumen_bases_2, 
    eliminar_base_invoice_2, 
    to_excel_bytes,
    init_tracking_db_2
)

def show(user_info):
    # Aseguramos que la tabla 2 exista con la nueva estructura
    init_tracking_db_2()
    
    st.title("🔎 Tracking Secundario (Honduras)")
    st.markdown("Gestión de bases de datos de aduanas e impuestos (Estructura Master Honduras).")

    t1, t2, t3 = st.tabs(["📊 Comparar Guías", "➕ Cargar Base Master", "⚙️ Gestionar Bases"])

    # --- PESTAÑA 1: COMPARAR ---
    with t1:
        st.subheader("Búsqueda de Guías (Tracking / Package Number)")
        st.caption("Verifica si las guías consultadas existen en la base. Si NO existen, podrás descargar el reporte de los faltantes.")
        
        metodo_comparar = st.radio(
            "Método de entrada de guías a buscar:", 
            ["📝 Pegar Texto Manualmente", "📁 Cargar Archivo (Excel/CSV)"], 
            horizontal=True,
            key="metodo_comp_2"
        )
        
        lista_buscar = []
        
        if metodo_comparar == "📁 Cargar Archivo (Excel/CSV)":
            uploaded_file_comp = st.file_uploader(
                "Sube tu archivo con los trackings a buscar", 
                type=["xlsx", "xls", "csv"], 
                key="uploader_comp_2"
            )
            if uploaded_file_comp is not None:
                try:
                    if uploaded_file_comp.name.endswith('.csv'):
                        df_input = pd.read_csv(uploaded_file_comp)
                    else:
                        df_input = pd.read_excel(uploaded_file_comp)
                    
                    col_selected = st.selectbox(
                        "Selecciona la columna que contiene los Trackings / Package Numbers:", 
                        df_input.columns,
                        key="col_select_comp_2"
                    )
                    
                    raw_list = df_input[col_selected].dropna().astype(str).str.strip().tolist()
                    lista_buscar = list(set([x for x in raw_list if x]))
                    st.info(f"📋 Se detectaron **{len(lista_buscar)}** números únicos para buscar.")
                except Exception as e:
                    st.error(f"Error al leer el archivo de búsqueda: {e}")
        else:
            txt_input = st.text_area("Pegar trackings (uno por línea)", height=200, key="compare_input_2", help="Pega aquí Tracking Numbers o Package Numbers.")
            if txt_input.strip():
                lista_raw = [x.strip() for x in txt_input.split('\n') if x.strip()]
                lista_buscar = list(set(lista_raw))

        if st.button("🔍 Comparar contra Base", type="primary", key="btn_compare_2"):
            if not lista_buscar:
                st.warning("No hay números para consultar. Ingrese texto o suba un archivo.")
            else:
                with st.spinner(f"Buscando {len(lista_buscar)} números en la base general (Tracking y Package Number)..."):
                    df_found = buscar_trackings_masivo_2(lista_buscar)
                
                encontrados_set = set()
                
                if not df_found.empty:
                    # Garantizar que son string para comparar
                    df_found['tracking'] = df_found['tracking'].astype(str)
                    df_found['package_number'] = df_found['package_number'].astype(str)
                    
                    # Un set con todos los identificadores encontrados en BD
                    encontrados_set = set(df_found['tracking']).union(set(df_found['package_number']))
                
                # Clasificar qué se encontró y qué NO
                no_encontrados = []
                encontrados_lista = []
                
                for t in lista_buscar:
                    if t in encontrados_set:
                        encontrados_lista.append(t)
                    else:
                        no_encontrados.append(t)
                
                # Métricas
                total = len(lista_buscar)
                enc = len(encontrados_lista)
                falt = len(no_encontrados)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Consultados", total)
                m2.metric("Encontrados (OK)", enc, delta_color="normal")
                m3.metric("NO Encontrados (Faltantes)", falt, delta_color="inverse")
                
                # Generar Excel de NO ENCONTRADOS
                if falt > 0:
                    st.warning(f"⚠️ Hay {falt} paquetes que NO se encontraron en la base de datos.")
                    df_faltantes = pd.DataFrame(no_encontrados, columns=["Guías NO encontradas (Faltantes)"])
                    st.dataframe(df_faltantes, use_container_width=True, height=250)
                    
                    excel_faltantes = to_excel_bytes(df_faltantes, 'xlsx')
                    st.download_button(
                        "📥 Descargar Archivo (Solo NO Encontrados)", 
                        excel_faltantes, 
                        "guias_no_encontradas.xlsx", 
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                        type="primary", 
                        key="btn_down_faltantes"
                    )
                else:
                    st.success("✅ ¡Todos los números consultados fueron encontrados en la base de datos!")

                # Opcional: Mostrar los encontrados detallados
                if not df_found.empty:
                    with st.expander("Ver detalle de los paquetes ENCONTRADOS"):
                        st.dataframe(df_found.drop(columns=['id'], errors='ignore'), use_container_width=True)

    # --- PESTAÑA 2: CARGAR BASE DE DATOS MASTER ---
    with t2:
        st.subheader("Cargar Base de Datos (Estructura Master Honduras)")
        st.caption("Sube el archivo Excel original. Se guardará toda la información: Máster, Tracking, Package, Impuestos, Ducas, etc.")
        
        uploaded_master = st.file_uploader(
            "Sube el archivo Excel (Ej. Master Honduras...)", 
            type=["xlsx", "xls"], 
            key="uploader_master"
        )
        
        if uploaded_master is not None:
            try:
                # Se fuerza la lectura de la hoja "Control paquetes HN" si existe, o la primera por defecto
                excel_file = pd.ExcelFile(uploaded_master)
                sheet_name = "Control paquetes HN" if "Control paquetes HN" in excel_file.sheet_names else 0
                df_master = pd.read_excel(uploaded_master, sheet_name=sheet_name)
                
                # Validar limpieza básica (quitar vacíos puros)
                df_master = df_master.dropna(subset=['Tracking number', 'Package Number'], how='all')
                
                st.success(f"Archivo leído correctamente. Se detectaron **{len(df_master)}** registros válidos.")
                
                # Mostrar muestra de datos
                st.dataframe(df_master.head(), use_container_width=True)
                
                if st.button("💾 Procesar y Subir Base de Datos", type="primary"):
                    with st.spinner("Subiendo miles de registros a la base de datos (Esto puede tomar varios segundos)..."):
                        ok, msg = guardar_base_tracking_2(df_master)
                        if ok:
                            st.success(f"✅ ¡Éxito! {msg}")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Error al subir: {msg}")
                            
            except Exception as e:
                st.error(f"Error al leer el archivo Excel: {e}")

    # --- PESTAÑA 3: GESTIONAR ---
    with t3:
        st.subheader("Bases Maestras Registradas")
        
        df_summary = obtener_resumen_bases_2()
        
        if df_summary.empty:
            st.info("No hay datos registrados en la tabla secundaria.")
        else:
            st.dataframe(
                df_summary, 
                column_config={
                    "invoice": "Máster",
                    "cantidad": st.column_config.NumberColumn("Cantidad Registros", format="%d"),
                    "fecha_creacion": st.column_config.DatetimeColumn("Última Actualización", format="DD/MM/YYYY HH:mm")
                },
                use_container_width=True
            )
            
            st.divider()
            st.write("🗑️ **Eliminar Registro por Máster**")
            st.caption("Si eliminas un máster, se borrarán todos sus trackings asociados de la base de datos.")
            
            list_inv = df_summary['invoice'].tolist()
            sel_del = st.selectbox("Seleccionar Máster a Eliminar", list_inv, key="sel_del_2")
            
            if st.button("Eliminar Base Seleccionada", type="primary", key="btn_del_2"):
                if eliminar_base_invoice_2(sel_del):
                    st.success(f"Máster {sel_del} eliminado correctamente.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error al eliminar.")
