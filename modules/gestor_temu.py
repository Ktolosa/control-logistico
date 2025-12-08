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
        res = {}; sum_list = []
        h_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        h_cost = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]
        
        for m, g in grouped:
            rm=[]; rc=[]
            for _, r in g.iterrows():
                row=[""]*21; row[0]=str(r[7]).strip(); row[4]=str(r[10]).strip(); row[6]=str(r[14]).strip(); row[13]=str(r[3]).strip(); row[19]=str(r[5]).strip(); row[1]="YC - Log. for Temu"; rm.append(row)
                cos=[""]*16; cos[0]=str(r[7]).strip(); cos[5]=str(r[5]).strip(); rc.append(cos)
            res[m] = {"main": pd.DataFrame(rm,columns=h_main), "costos": pd.DataFrame(rc,columns=h_cost), "info": {"p": len(g), "c": g[5].nunique()}}
            sum_list.append({"Master": m, "Cajas": g[5].nunique(), "Paquetes": len(g)})
        return res, pd.DataFrame(sum_list), None
    except Exception as e: return None, None, str(e)

def show(user_info):
    st.title("Gestor TEMU")
    f = st.file_uploader("Excel", type=["xlsx","xls"])
    if f:
        res, df_sum, err = procesar_archivo_temu(f)
        if err: st.error(f"Error: {err}")
        elif res:
            st.subheader("Resumen"); st.dataframe(df_sum, use_container_width=True)
            fmt = st.radio("Formato Descarga", ["xlsx", "xls"], horizontal=True)
            ext = "xlsx" if fmt=="xlsx" else "xls"
            for m, d in res.items():
                with st.expander(f"📦 {m} ({d['info']['p']} paq / {d['info']['c']} caj)"):
                    search_q = st.text_input(f"🔍 Buscar en {m}", key=f"s_{m}")
                    c1,c2 = st.columns(2)
                    c1.download_button("📥 Manifiesto", to_excel_bytes(d['main'],ext), f"{m}.{ext}")
                    c2.download_button("💲 Costos", to_excel_bytes(d['costos'],ext), f"{m}_Costos.{ext}")
                    df_disp = d['main']
                    if search_q: df_disp = df_disp[df_disp.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)]
                    st.dataframe(df_disp, hide_index=True)
