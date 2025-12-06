import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime
import plotly.express as px
from streamlit_calendar import calendar # Nueva librería visual

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Calendario Logístico Pro", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS PARA QUE SE PAREZCA A GOOGLE CALENDAR ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN BASE DE DATOS ---
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

def cargar_datos():
    conn = get_connection()
    query = "SELECT * FROM registro_diario"
    df = pd.read_sql(query, conn)
    conn.close()
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
    return df

def guardar_registro(fecha, paquetes, masters, proveedor, comentarios):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
    INSERT INTO registro_diario (fecha, paquetes, masters, proveedor, comentarios)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    paquetes=%s, masters=%s, proveedor=%s, comentarios=%s
    """
    vals = (fecha, paquetes, masters, proveedor, comentarios, paquetes, masters, proveedor, comentarios)
    cursor.execute(query, vals)
    conn.commit()
    conn.close()

# --- INTERFAZ PRINCIPAL ---

# 1. BARRA LATERAL (ENTRADA DE DATOS)
with st.sidebar:
    st.header("📝 Nuevo Registro")
    with st.form("entry_form"):
        fecha_in = st.date_input("Fecha", date.today())
        paq_in = st.number_input("📦 Paquetes", min_value=0, step=1)
        mast_in = st.number_input("🧱 Másters", min_value=0, step=1)
        prov_in = st.text_input("🚚 Proveedor")
        com_in = st.text_area("💬 Comentarios")
        
        submitted = st.form_submit_button("Guardar en Calendario", use_container_width=True)
        if submitted:
            guardar_registro(fecha_in, paq_in, mast_in, prov_in, com_in)
            st.success("Guardado")
            st.rerun()

# 2. CARGA DE DATOS
df = cargar_datos()

# 3. PESTAÑAS PRINCIPALES
tab_cal, tab_dash = st.tabs(["📅 Vista Calendario Visual", "📊 Dashboard de Análisis"])

# --- PESTAÑA 1: CALENDARIO TIPO GOOGLE ---
with tab_cal:
    col_main, col_detalles = st.columns([3, 1])
    
    with col_main:
        # Preparamos los eventos para el calendario visual
        events = []
        if not df.empty:
            for index, row in df.iterrows():
                # Creamos el "evento" visual
                events.append({
                    "title": f"📦{row['paquetes']} | 🧱{row['masters']}",
                    "start": row['fecha_str'],
                    "allDay": True,
                    "backgroundColor": "#3788d8", # Azul tipo Google
                    "borderColor": "#3788d8",
                    # Guardamos datos extra para cuando le den clic
                    "extendedProps": {
                        "proveedor": row['proveedor'],
                        "comentarios": row['comentarios'],
                        "paquetes": row['paquetes'],
                        "masters": row['masters']
                    }
                })

        # Configuración del calendario visual
        calendar_options = {
            "editable": False,
            "navLinks": True,
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "dayGridMonth,dayGridWeek,dayGridDay"
            },
            "initialView": "dayGridMonth",
        }

        # RENDERIZAR CALENDARIO
        state = calendar(events=events, options=calendar_options, key="calendar")

    with col_detalles:
        st.subheader("🔍 Detalle del Día")
        # Si hacen clic en un evento, mostramos los detalles aquí
        if state.get("eventClick"):
            event_data = state["eventClick"]["event"]
            props = event_data["extendedProps"]
            
            st.info(f"📅 Fecha: {event_data['start']}")
            
            st.metric("Paquetes", props['paquetes'])
            st.metric("Másters", props['masters'])
            
            st.write("---")
            st.markdown(f"**🚚 Proveedor:**\n{props['proveedor']}")
            st.markdown(f"**💬 Notas:**\n{props['comentarios']}")
        else:
            st.write("👈 Haz clic en un día del calendario para ver los detalles completos (Proveedor y notas).")

# --- PESTAÑA 2: ANÁLISIS DE DATOS ---
with tab_dash:
    if df.empty:
        st.warning("No hay datos suficientes para generar análisis.")
    else:
        # Filtros de Fecha para el Dashboard
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Fecha Inicio", df['fecha'].min())
        with c2:
            end_date = st.date_input("Fecha Fin", date.today())
            
        # Filtrar DF para gráficas
        mask = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
        df_filtered = df.loc[mask]

        st.markdown("---")
        
        # 1. TOTALES GENERALES (KPIs)
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Paquetes", df_filtered['paquetes'].sum())
        kpi2.metric("Total Másters", df_filtered['masters'].sum())
        kpi3.metric("Promedio Paquetes/Día", int(df_filtered['paquetes'].mean()) if not df_filtered.empty else 0)
        kpi4.metric("Días Operativos", len(df_filtered))

        st.markdown("---")

        # 2. GRÁFICAS INTERACTIVAS
        row1_1, row1_2 = st.columns(2)
        
        with row1_1:
            st.subheader("📈 Evolución Diaria")
            fig_line = px.line(df_filtered, x='fecha', y=['paquetes', 'masters'], 
                               markers=True, title="Tendencia de Recepción")
            st.plotly_chart(fig_line, use_container_width=True)
            
        with row1_2:
            st.subheader("🚚 Distribución por Proveedor")
            # Agrupar por proveedor
            df_prov = df_filtered.groupby('proveedor')[['paquetes']].sum().reset_index()
            fig_pie = px.pie(df_prov, values='paquetes', names='proveedor', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        row2_1, row2_2 = st.columns(2)
        
        with row2_1:
            st.subheader("📅 Actividad por Día de la Semana")
            df_filtered['dia_semana'] = df_filtered['fecha'].dt.day_name()
            # Ordenar días correctamente
            dias_orden = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            df_day = df_filtered.groupby('dia_semana')[['paquetes', 'masters']].sum().reindex(dias_orden).reset_index()
            
            fig_bar = px.bar(df_day, x='dia_semana', y=['paquetes', 'masters'], barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)

        with row2_2:
            st.subheader("📋 Resumen Semanal (Tabla)")
            df_filtered['Semana'] = df_filtered['fecha'].dt.isocalendar().week
            tabla_semanal = df_filtered.groupby('Semana')[['paquetes', 'masters']].sum().reset_index()
            st.dataframe(tabla_semanal, use_container_width=True, hide_index=True)
