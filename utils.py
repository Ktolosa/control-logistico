import streamlit as st
import mysql.connector
import pandas as pd

# Configuración de conexión segura
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# Cargar datos formateados
def cargar_datos():
    try:
        conn = get_connection()
        query = "SELECT * FROM registro_diario"
        df = pd.read_sql(query, conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# Guardar o Actualizar registro
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
