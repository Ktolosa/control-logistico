# utils.py
import streamlit as st
import mysql.connector
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- CONFIGURACIÓN CSS COMPARTIDA ---
def load_css(sidebar_width="70px"):
    # ... (PEGA AQUÍ TU CSS GIGANTE QUE YA TIENES EN APP.PY) ...
    # Asegúrate de mantener los media queries para móvil y escritorio.
    st.markdown(f"""<style> ... TU CSS ... </style>""", unsafe_allow_html=True)

# --- CONEXIÓN BASE DE DATOS ---
def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"]
        )
    except: return None

# --- AUTH ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

# --- UTILIDADES VARIAS ---
def decode_image(image_file):
    # ... (Tu función de decodificar) ...
    try:
        bytes_data = image_file.getvalue()
        file_bytes = np.asarray(bytearray(bytes_data), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        decoded_objects = decode(img)
        return [obj.data.decode('utf-8') for obj in decoded_objects]
    except: return []
