import streamlit as st
import pandas as pd
import plotly.express as px
from utils import get_connection

def show(user_info):
    st.title("Analytics Pro")
    
    conn = get_connection()
    if not conn: st.error("Error BD"); return
    
    # Cargar datos base
    df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
    
    if df.empty: st.warning("Sin datos"); conn.close(); return
    
    df['fecha'] = pd.to_datetime(df['fecha'])
    df['Año'] = df['fecha'].dt.year
    df['Semana'] = df['fecha'].dt.isocalendar().week
    df['Mes'] = df['fecha'].dt.month_name()
    
    # Filtros
    with st.container(border=True):
        c_s, c_d = st.columns([1,2])
        s_mast = c_s.text_input("🔍 Buscar Master")
        rango = c_d.date_input("Rango", [df['fecha'].min(), df['fecha'].max()])
    
    df_fil = df.copy()
    
    # Lógica de búsqueda Master
    if s_mast:
        q = f"SELECT registro_id FROM masters_detalle WHERE master_code LIKE '%{s_mast}%'"
        found = pd.read_sql(q, conn)
        if not found.empty: df_fil = df_fil[df_fil['id'].isin(found['registro_id'])]
        else: st.error("No encontrado"); df_fil = pd.DataFrame()
    elif len(rango)==2: 
        df_fil = df_fil[(df_fil['fecha'].dt.date>=rango[0])&(df_fil['fecha'].dt.date<=rango[1])]
    
    conn.close()
    
    if not df_fil.empty:
        # Calcular conteo real de masters
        import re
        def contar(t): return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()]) if t else 0
        df_fil['conteo_masters_real'] = df_fil['master_lote'].apply(contar)

        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Paquetes</div><div class='kpi-val'>{df_fil['paquetes'].sum():,.0f}</div></div>",unsafe_allow_html=True)
        k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Masters</div><div class='kpi-val'>{df_fil['conteo_masters_real'].sum():,.0f}</div></div>",unsafe_allow_html=True)
        k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Viajes</div><div class='kpi-val'>{len(df_fil)}</div></div>",unsafe_allow_html=True)
        k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio</div><div class='kpi-val'>{df_fil['paquetes'].mean():,.0f}</div></div>",unsafe_allow_html=True)
        
        t1,t2,t3 = st.tabs(["📅 Resumen", "📊 Gráficos", "📥 Data"])
        with t1:
            res = df_fil.groupby(['Año','Semana','Mes']).agg(Paquetes=('paquetes','sum'), Masters=('conteo_masters_real','sum'), Viajes=('id','count')).reset_index()
            st.dataframe(res, use_container_width=True)
        with t2:
            g1,g2 = st.columns(2)
            with g1: st.plotly_chart(px.bar(df_fil.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes'), use_container_width=True)
            with g2: st.plotly_chart(px.pie(df_fil, names='proveedor_logistico', values='paquetes'), use_container_width=True)
        with t3:
            st.dataframe(df_fil)
            st.download_button("Descargar CSV", df_fil.to_csv(index=False).encode('utf-8'), "reporte.csv", "text/csv")
