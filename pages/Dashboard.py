import streamlit as st
import plotly.express as px
import pandas as pd
import utils # Reutilizamos la conexión

st.set_page_config(page_title="Dashboard Logístico", layout="wide")

st.title("📊 Dashboard de Análisis e Inteligencia")
st.markdown("---")

df = utils.cargar_datos()

if df.empty:
    st.info("No hay datos suficientes para mostrar métricas.")
else:
    # --- FILTROS LATERALES SOLO PARA ESTA PÁGINA ---
    with st.sidebar:
        st.header("Filtros de Análisis")
        f_mes = st.selectbox("Filtrar Mes", range(1, 13), index=pd.Timestamp.now().month-1)
        f_anio = st.number_input("Año", value=pd.Timestamp.now().year)
    
    # Filtrar datos
    df_filtered = df[(df['fecha'].dt.month == f_mes) & (df['fecha'].dt.year == f_anio)]

    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Total Paquetes", f"{df_filtered['paquetes'].sum():,}")
    m2.metric("🧱 Total Másters", f"{df_filtered['masters'].sum():,}")
    m3.metric("🚚 Proveedores Únicos", df_filtered['proveedor'].nunique())
    m4.metric("📅 Días Operativos", len(df_filtered))

    st.markdown("### 📈 Visualización de Datos")
    
    # --- FILA 1 DE GRÁFICOS ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Evolución Diaria")
        # Gráfico de línea limpio
        fig_line = px.line(df_filtered, x='fecha', y=['paquetes', 'masters'], 
                          markers=True, color_discrete_sequence=["#3788d8", "#2C3E50"])
        fig_line.update_layout(xaxis_title="Día", yaxis_title="Cantidad", template="plotly_white")
        st.plotly_chart(fig_line, use_container_width=True)
        
    with c2:
        st.subheader("Distribución por Proveedor")
        # Gráfico de dona
        df_prov = df_filtered.groupby('proveedor')[['paquetes']].sum().reset_index()
        fig_pie = px.pie(df_prov, values='paquetes', names='proveedor', hole=0.5)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- FILA 2 DE GRÁFICOS ---
    st.subheader("Análisis Semanal")
    df_filtered['Semana'] = df_filtered['fecha'].dt.isocalendar().week
    df_week = df_filtered.groupby('Semana')[['paquetes', 'masters']].sum().reset_index()
    
    fig_bar = px.bar(df_week, x='Semana', y=['paquetes', 'masters'], barmode='group',
                     text_auto=True, color_discrete_sequence=["#3788d8", "#2C3E50"])
    fig_bar.update_layout(template="plotly_white")
    st.plotly_chart(fig_bar, use_container_width=True)
