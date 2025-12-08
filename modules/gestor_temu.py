import streamlit as st
import pandas as pd
from utils import to_excel_bytes

def procesar_archivo_temu(uploaded_file):
    try:
        df_raw = pd.read_excel(uploaded_file, header=None).fillna("")
        data_rows = df_raw.iloc[1:]
        data_rows = data_rows[data_rows[3].astype(str).str.strip() != ""]
        if data_rows.empty: return None, None, "Sin datos en columna D."
        grouped = data_rows.groupby(3)
        resultados = {}; resumen_list = []
        h_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        h_cost = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]
        
        for master, group in grouped:
            r_m = []; r_c = []
            for _, row in group.iterrows():
                r = [""]*21; r[0]=str(row[7]).strip(); r[4]=str(row[10]).strip(); r[6]=str(row[14]).strip(); r[7]=str(row[11]).strip(); r[8]=str(row[12]).strip(); r[9]=str(row[13]).strip(); r[10]=str(row[16]).strip(); r[11]=str(row[17]).strip(); r[12]=str(row[15]).strip(); r[13]=str(row[3]).strip(); r[19]=str(row[5]).strip(); r[1]="YC - Log. for Temu"; r[2]="Zhaoqing"; r[3]="CN"; r[5]="SLV"; r[18]="USD"; r[14]="1"; r[15]="0.45"; r[16]="0.01"; r[17]="N/A"; r[20]="N/A"; r_m.append(r)
                c = [""]*16; c[0]=str(row[7]).strip(); c[2]=str(row[10]).strip(); c[3]=str(row[15]).strip(); c[5]=str(row[5]).strip(); c[7]="0.00"; c[8]="0.01"; c[9]="0.01"; c[10]="0.00"; c[11]="0.00"; c[12]="0.00"; c[13]="0.00"; c[14]="0.00"; c[15]="0.01"; r_c.append(c)
            resultados[master] = {"main": pd.DataFrame(r_m, columns=h_main), "costos": pd.DataFrame(r_c, columns=h_cost), "info": {"paquetes": len(group), "cajas": group[5].nunique()}}
            resumen_list.append({"Master": master, "Cajas": group[5].nunique(), "Paquetes": len(group)})
        return resultados, pd.DataFrame(resumen_list), None
    except Exception as e: return None, None, str(e)

def show(user_info):
    st.title("Gestor TEMU")
    f = st.file_uploader("Cargar Excel (.xlsx)", type=["xlsx","xls"])
    if f:
        res, df_sum, err = procesar_archivo_temu(f)
        if err:
            st.error(f"Error: {err}")
        elif res:
            st.subheader("Resumen")
            st.dataframe(df_sum, use_container_width=True)
            
            fmt = st.radio("Formato Descarga", ["xlsx", "xls"], horizontal=True)
            ext = "xlsx" if fmt=="xlsx" else "xls"
            
            for m, d in res.items():
                with st.expander(f"📦 {m} ({d['info']['paquetes']} paq)"):
                    search_q = st.text_input(f"🔍 Buscar en {m}", key=f"s_{m}")
                    
                    c1,c2 = st.columns(2)
                    c1.download_button("📥 Manifiesto", to_excel_bytes(d['main'],ext), f"{m}.{ext}")
                    c2.download_button("💲 Costos", to_excel_bytes(d['costos'],ext), f"{m}_Costos.{ext}")
                    
                    df_disp = d['main']
                    if search_q: 
                        df_disp = df_disp[df_disp.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)]
                    st.dataframe(df_disp, hide_index=True)
