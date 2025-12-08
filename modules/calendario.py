import streamlit as st
import pandas as pd
from datetime import datetime, date
from streamlit_calendar import calendar
import re
from utils import get_connection, decode_image, PROVEEDORES, PLATAFORMAS, SERVICIOS

def cargar_datos():
    conn = get_connection()
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            # Conteo simple
            def contar(t): return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()]) if t else 0
            df['conteo_masters_real'] = df['master_lote'].apply(contar)
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast_str, paq, com, user):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Limpieza básica
            lista_masters = [m.strip() for m in re.split(r'[\n, ]+', mast_str) if m.strip()]
            clean_masters_str = " ".join(lista_masters)
            
            if id_reg is None:
                sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, user))
                id_reg = cur.lastrowid
                st.toast("✅ Guardado")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, id_reg))
                cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,))
                st.toast("✅ Actualizado")
            
            # Guardar detalle
            if lista_masters:
                vals = [(id_reg, m, fecha) for m in lista_masters]
                cur.executemany("INSERT INTO masters_detalle (registro_id, master_code, fecha_registro) VALUES (%s, %s, %s)", vals)
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error BD: {e}")

@st.dialog("Gestión de Carga")
def modal_registro(datos, user):
    rol = st.session_state['user_info']['rol']
    disabled = (rol == 'analista')
    d_fecha, d_prov, d_plat = date.today(), PROVEEDORES[0], PLATAFORMAS[0]
    d_serv, d_mast, d_paq, d_com, d_id = SERVICIOS[0], "", 0, "", None
    d_esp = 1
    
    if datos:
        d_id = datos.get('id')
        if datos.get('fecha_str'): d_fecha = datetime.strptime(datos['fecha_str'], '%Y-%m-%d').date()
        if datos.get('proveedor') in PROVEEDORES: d_prov = datos['proveedor']
        if datos.get('plataforma') in PLATAFORMAS: d_plat = datos['plataforma']
        d_serv = datos.get('servicio', SERVICIOS[0]); d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0); d_com = datos.get('comentarios', "")
        d_esp = len([x for x in re.split(r'[\n, ]+', d_mast) if x.strip()]) or 1

    st.write("📋 **Escaneo / Ingreso**")
    
    # Cámara
    col_cam, col_txt = st.columns([1,2])
    if col_cam.toggle("📷 Abrir Cámara"):
        img = st.camera_input("Escanear")
        if img:
            codes = decode_image(img)
            if codes:
                if codes[0] not in st.session_state.get('scan_buffer_modal', []):
                    st.session_state.setdefault('scan_buffer_modal', []).append(codes[0])
                    st.success(f"Leído: {codes[0]}")

    if st.session_state.get('scan_buffer_modal'):
        if st.button("Borrar Escaneos"): st.session_state['scan_buffer_modal'] = []; st.rerun()
        d_mast += "\n" + "\n".join(st.session_state['scan_buffer_modal'])

    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            esperados = st.number_input("Esperadas", min_value=1, value=d_esp, disabled=disabled)
            pain = st.number_input("Total Paquetes", 0, value=int(d_paq), disabled=disabled)

        masters_input = st.text_area("Masters", value=d_mast, height=150, disabled=disabled)
        
        # Validar
        real = len([m for m in re.split(r'[\n, ]+', masters_input) if m.strip()])
        c_v1, c_v2 = st.columns(2); c_v1.caption(f"Leídos: {real}")
        if esperados > 0:
            if real == esperados: c_v2.markdown(f"<div class='count-ok'>✅ Cuadra</div>", unsafe_allow_html=True)
            else: c_v2.markdown(f"<div class='count-err'>❌ Dif: {real-esperados}</div>", unsafe_allow_html=True)

        com = st.text_area("Notas", d_com, disabled=disabled)
        
        if not disabled:
            if st.form_submit_button("💾 Guardar", type="primary"):
                guardar_registro(d_id, fin, pin, clin, sin, masters_input, pain, com, user)
                st.session_state['scan_buffer_modal'] = []
                st.rerun()

def show(user_info):
    c1, c2 = st.columns([6, 1])
    c1.title("Calendario Operativo")
    if user_info['rol'] != 'analista' and c2.button("➕ Nuevo", type="primary"): 
        modal_registro(None, user_info['username'])
    
    df = cargar_datos()
    evts = []
    if not df.empty:
        for _, r in df.iterrows():
            col = "#3b82f6"
            if "AliExpress" in r['plataforma_cliente']: col = "#f97316"
            elif "Temu" in r['plataforma_cliente']: col = "#10b981"
            props = {"id": int(r['id']), "fecha_str": str(r['fecha_str']), "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']), "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']), "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])}
            evts.append({"title": f"📦{int(r['paquetes'])} | 🔑{r['conteo_masters_real']}", "start": r['fecha_str'], "backgroundColor": col, "borderColor": col, "extendedProps": props})
    
    cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "650px"}, key="cal_main")
    if cal.get("eventClick"): 
        modal_registro(cal["eventClick"]["event"]["extendedProps"], user_info['username'])
