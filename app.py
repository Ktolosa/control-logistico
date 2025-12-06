import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, timedelta
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema Logístico", layout="wide")

# --- CONEXIÓN A LA BASE DE DATOS ---
# Usamos st.secrets para producción, o conexión directa para pruebas
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- FUNCIONES DE BASE DE DATOS ---
def cargar_datos():
    conn = get_connection()
    query = "SELECT * FROM registro_diario"
    df = pd.read_sql(query, conn)
    conn.close()
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
    return df

def guardar_registro(fecha, paquetes, masters, proveedor, comentarios):
    conn = get_connection()
    cursor = conn.cursor()
    # Usamos INSERT ON DUPLICATE KEY UPDATE para insertar o actualizar si ya existe el día
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

# --- INTERFAZ DE USUARIO ---
st.title("📦 Sistema de Control de Calendario Logístico")

# 1. BARRA LATERAL (REGISTRO)
st.sidebar.header("📝 Registrar Día")
with st.sidebar.form("entry_form"):
    fecha_in = st.date_input("Fecha", date.today())
    paq_in = st.number_input("Cantidad Paquetes", min_value=0, step=1)
    mast_in = st.number_input("Cantidad Másters", min_value=0, step=1)
    prov_in = st.text_input("Proveedor")
    com_in = st.text_area("Comentarios")
    
    submitted = st.form_submit_button("Guardar Datos")
    if submitted:
        guardar_registro(fecha_in, paq_in, mast_in, prov_in, com_in)
        st.success("¡Información registrada correctamente!")
        st.rerun() # Recargar la página para ver cambios

# CARGAR DATOS
df = cargar_datos()

if df.empty:
    st.info("Aún no hay datos registrados. Usa el panel izquierdo para comenzar.")
else:
    # FILTRO POR MES PARA EL CALENDARIO
    col_mes1, col_mes2 = st.columns([1, 4])
    with col_mes1:
        mes_seleccionado = st.selectbox("Seleccionar Mes", range(1, 13), index=date.today().month - 1)
        anio_seleccionado = st.number_input("Año", value=date.today().year)

    # Filtrar DF por mes y año
    df_mes = df[(df['fecha'].dt.month == mes_seleccionado) & (df['fecha'].dt.year == anio_seleccionado)]

    # --- PESTAÑAS ---
    tab1, tab2 = st.tabs(["📅 Vista Calendario & Totales", "📊 Resúmenes y Gráficas"])

    with tab1:
        st.subheader(f"Vista Detallada: Mes {mes_seleccionado}/{anio_seleccionado}")
        
        # Totales Generales (Top)
        total_paq = df_mes['paquetes'].sum()
        total_mast = df_mes['masters'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Paquetes (Mes)", total_paq)
        c2.metric("Total Másters (Mes)", total_mast)
        c3.metric("Días Registrados", len(df_mes))

        st.markdown("---")

        # CREACIÓN DE LA VISTA TIPO CALENDARIO CON TOTALES
        # Preparamos los datos para mostrar
        if not df_mes.empty:
            df_view = df_mes.copy()
            df_view['Dia'] = df_view['fecha'].dt.day_name() # Nombre del día (Monday, etc)
            df_view['Semana'] = df_view['fecha'].dt.isocalendar().week
            df_view['Fecha_Str'] = df_view['fecha'].dt.strftime('%Y-%m-%d')
            
            # Mostramos la tabla "cruda" pero bonita
            st.dataframe(
                df_mes[['fecha', 'paquetes', 'masters', 'proveedor', 'comentarios']].sort_values('fecha'),
                use_container_width=True,
                column_config={
                    "fecha": "Fecha",
                    "paquetes": st.column_config.NumberColumn("Paquetes", format="%d 📦"),
                    "masters": st.column_config.NumberColumn("Másters", format="%d 🧱"),
                }
            )
            
            st.markdown("### 🗓️ Matriz Semanal (Totales Calculados)")
            # Hacemos una tabla pivote para simular el calendario visual con totales
            # Filas = Número de semana, Columnas = Día de la semana
            pivot_paq = df_view.pivot_table(
                index='Semana', 
                columns='Dia', 
                values='paquetes', 
                aggfunc='sum', 
                fill_value=0,
                margins=True, # ESTO AGREGA LOS TOTALES (Derecha y Abajo)
                margins_name='Total'
            )
            
            st.write("**Totales de Paquetes por Semana y Día:**")
            st.dataframe(pivot_paq, use_container_width=True)

            pivot_mast = df_view.pivot_table(
                index='Semana', 
                columns='Dia', 
                values='masters', 
                aggfunc='sum', 
                fill_value=0,
                margins=True,
                margins_name='Total'
            )
            st.write("**Totales de Másters por Semana y Día:**")
            st.dataframe(pivot_mast, use_container_width=True)

    with tab2:
        st.subheader("Análisis de Datos")
        
        # Agrupar por día de la semana
        df['dia_nombre'] = df['fecha'].dt.day_name()
        resumen_dia = df.groupby('dia_nombre')[['paquetes', 'masters']].sum().reset_index()
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.write("📦 **Paquetes por Día de la Semana**")
            fig = px.bar(resumen_dia, x='dia_nombre', y='paquetes', color='dia_nombre')
            st.plotly_chart(fig, use_container_width=True)
            
        with col_g2:
            st.write("📅 **Evolución Diaria (Línea de tiempo)**")
            fig2 = px.line(df, x='fecha', y=['paquetes', 'masters'], markers=True)
            st.plotly_chart(fig2, use_container_width=True)

        st.write("🏭 **Resumen por Proveedor**")
        resumen_prov = df.groupby('proveedor')[['paquetes', 'masters']].sum().reset_index()
        st.dataframe(resumen_prov, use_container_width=True)