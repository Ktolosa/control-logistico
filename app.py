import streamlit as st
import pandas as pd
import mysql.connector
from datetime import date, datetime, timedelta
from streamlit_calendar import calendar
import plotly.express as px
import re
import io

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(
    page_title="Nexus Logística", 
    layout="wide", 
    initial_sidebar_state="expanded" 
)

# Inicializar estado
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'current_view' not in st.session_state: st.session_state['current_view'] = "calendar"

# --- 2. CSS (DISEÑO LIGHT & SLIM) ---
SIDEBAR_WIDTH = "60px"

base_css = """
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { visibility: hidden !important; }
    footer { display: none !important; }
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
</style>
"""

login_css = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 400px; padding-top: 15vh; margin: 0 auto; }
    div[data-testid="stTextInput"] input { border: 1px solid #e2e8f0; padding: 12px; border-radius: 10px; }
    div.stButton > button { width: 100%; border-radius: 10px; padding: 12px; font-weight: 600; background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; color: white; }
</style>
"""

dashboard_css = f"""
<style>
    [data-testid="collapsedControl"] {{ display: none !important; }}
    section[data-testid="stSidebar"] {{
        display: block !important; width: {SIDEBAR_WIDTH} !important; min-width: {SIDEBAR_WIDTH} !important;
        max-width: {SIDEBAR_WIDTH} !important; transform: none !important; visibility: visible !important;
        position: fixed !important; top: 0 !important; left: 0 !important; bottom: 0 !important; z-index: 99999;
        background-color: #ffffff !important; border-right: 1px solid #f1f5f9; box-shadow: 4px 0 20px rgba(0,0,0,0.03);
    }}
    section[data-testid="stSidebar"] > div {{
        height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-top: 0px !important; 
    }}
    .main .block-container {{
        margin-left: {SIDEBAR_WIDTH} !important; width: calc(100% - {SIDEBAR_WIDTH}) !important;
        padding: 2rem !important; max-width: 100% !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        display: flex !important; justify-content: center !important; align-items: center !important;
        width: 42px !important; height: 42px !important; border-radius: 12px !important; cursor: pointer;
        background: transparent; color: #64748b; font-size: 22px !important; border: 1px solid transparent; transition: all 0.2s; margin: 0 !important;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: #f1f5f9; color: #0f172a; transform: scale(1.1); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
        background: #eff6ff; color: #2563eb; border: 1px solid #dbeafe; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.15);
    }}
    .avatar-float {{ position: absolute; top: 20px; left: 0; right: 0; margin: auto; width: 35px; height: 35px; background: #f8fafc; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid #e2e8f0; font-size: 18px; color: #334155; }}
    .logout-float {{ position: absolute; bottom: 20px; left: 0; right: 0; margin: auto; text-align: center; }}
    .kpi-card {{ background: white; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; }}
    .kpi-lbl {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 700; }}
    .kpi-val {{ font-size: 1.5rem; color: #0f172a; font-weight: 800; }}
    .count-ok {{ color: #16a34a; font-weight: bold; font-size: 0.9rem; }}
    .count-err {{ color: #dc2626; font-weight: bold; font-size: 0.9rem; }}
</style>
"""

st.markdown(base_css, unsafe_allow_html=True)
if st.session_state['logged_in']:
    st.markdown(dashboard_css, unsafe_allow_html=True)
else:
    st.markdown(login_css, unsafe_allow_html=True)

# --- 3. CONEXIÓN ---
AVATARS = {"avatar_1": "👨‍💼", "avatar_2": "👩‍💼", "avatar_3": "👷‍♂️", "avatar_4": "👩‍💻"} 
PROVEEDORES = ["Mail Americas", "APG", "IMILE", "GLC"]
PLATAFORMAS = ["AliExpress", "Shein", "Temu"]
SERVICIOS = ["Aduana Propia", "Solo Ultima Milla"]

def get_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"], user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"], database=st.secrets["mysql"]["database"]
        )
    except: return None

# --- FUNCIONES LÓGICAS ---
def verificar_login(u, p):
    conn = get_connection()
    if not conn: return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=1", (u, p))
        res = cur.fetchone(); conn.close(); return res
    except: return None

def validar_admin_pass(password):
    conn = get_connection()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE rol='admin' AND activo=1 AND password=%s", (password,))
        res = cur.fetchone(); conn.close(); return True if res else False
    except: return False

def cargar_datos():
    conn = get_connection(); 
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT * FROM registro_logistica ORDER BY fecha DESC", conn)
        conn.close()
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['fecha_str'] = df['fecha'].dt.strftime('%Y-%m-%d')
            df['Año'] = df['fecha'].dt.year
            df['Mes'] = df['fecha'].dt.month_name()
            df['Semana'] = df['fecha'].dt.isocalendar().week
            df['DiaSemana'] = df['fecha'].dt.day_name()
            def contar(t):
                if not t: return 0
                return len([p for p in re.split(r'[\n, ]+', str(t)) if p.strip()])
            df['conteo_masters_real'] = df['master_lote'].apply(contar)
        return df
    except: return pd.DataFrame()

def guardar_registro(id_reg, fecha, prov, plat, serv, mast_str, paq, com):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            user = st.session_state['user_info']['username']
            lista_masters = [m.strip() for m in re.split(r'[\n, ]+', mast_str) if m.strip()]
            clean_masters_str = " ".join(lista_masters)
            registro_id = id_reg
            if id_reg is None:
                sql = "INSERT INTO registro_logistica (fecha, proveedor_logistico, plataforma_cliente, tipo_servicio, master_lote, paquetes, comentarios, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, user))
                registro_id = cur.lastrowid
                st.toast("✅ Guardado Exitosamente")
            else:
                sql = "UPDATE registro_logistica SET fecha=%s, proveedor_logistico=%s, plataforma_cliente=%s, tipo_servicio=%s, master_lote=%s, paquetes=%s, comentarios=%s WHERE id=%s"
                cur.execute(sql, (fecha, prov, plat, serv, clean_masters_str, paq, com, id_reg))
                cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,))
                st.toast("✅ Registro Actualizado")
            if lista_masters:
                vals = [(registro_id, m, fecha) for m in lista_masters]
                cur.executemany("INSERT INTO masters_detalle (registro_id, master_code, fecha_registro) VALUES (%s, %s, %s)", vals)
            conn.commit(); conn.close()
        except Exception as e: st.error(f"Error BD: {e}")

def eliminar_registro(id_reg, admin_pass):
    if not validar_admin_pass(admin_pass):
        st.error("🔒 Clave de administrador incorrecta.")
        return False
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM masters_detalle WHERE registro_id=%s", (id_reg,)) 
            cur.execute("DELETE FROM registro_logistica WHERE id=%s", (id_reg,))
            conn.commit(); conn.close()
            st.toast("🗑️ Registro eliminado permanentemente")
            return True
        except Exception as e: st.error(str(e)); return False
    return False

# --- LÓGICA GESTOR TEMU ---
def procesar_archivo_temu(uploaded_file):
    try:
        df_raw = pd.read_excel(uploaded_file, header=None).fillna("")
        data_rows = df_raw.iloc[1:]
        data_rows = data_rows[data_rows[3].astype(str).str.strip() != ""]
        if data_rows.empty: return None, None, "No se encontraron datos en columna Master (D)."

        grouped = data_rows.groupby(3)
        resultados = {}
        resumen_list = []

        headers_main = ["HAWB", "Sender Name", "City", "Country", "Name of Consignee", "Consignee Country", "Consignee Address", "State / Departamento", "Municipality / Municipio", "ZiP Code", "Contact Number", "Email", "Goods Desc", "N. MAWB (Master)", "No of Item", "Weight(kg)", "Customs Value USD (FOB)", "HS CODE", "Customs Currency", "BOX NO.", "ID / DUI"]
        headers_costos = ["TRAKING", "PESO", "CLIENTE", "DESCRIPTION", "REF", "N° de SACO", "VALUE", "DAI", "IVA", "TOTAL IMPUESTOS", "COMISION", "MANEJO", "IVA COMISION", "IVA MANEJO", "TOTAL IVA", "TOTAL"]

        for master, group in grouped:
            rows_main = []
            for _, row in group.iterrows():
                r = [""] * 21
                r[0]=str(row[7]).strip(); r[4]=str(row[10]).strip(); r[6]=str(row[14]).strip(); r[7]=str(row[11]).strip();
                r[8]=str(row[12]).strip(); r[9]=str(row[13]).strip(); r[10]=str(row[16]).strip(); r[11]=str(row[17]).strip();
                r[12]=str(row[15]).strip(); r[13]=str(row[3]).strip(); r[19]=str(row[5]).strip();
                r[1]="YC - Log. for Temu"; r[2]="Zhaoqing"; r[3]="CN"; r[5]="SLV"; r[18]="USD";
                r[14]="1"; r[15]="0.45"; r[16]="0.01"; r[17]="N/A"; r[20]="N/A";
                rows_main.append(r)
            
            rows_costos = []
            for _, row in group.iterrows():
                c = [""] * 16
                c[0]=str(row[7]).strip(); c[2]=str(row[10]).strip(); c[3]=str(row[15]).strip(); c[5]=str(row[5]).strip();
                c[7]="0.00"; c[8]="0.01"; c[9]="0.01"; c[10]="0.00"; c[11]="0.00"; c[12]="0.00"; c[13]="0.00"; c[14]="0.00"; c[15]="0.01";
                rows_costos.append(c)

            paquetes = len(group)
            cajas = group[5].nunique()

            resultados[master] = {
                "main": pd.DataFrame(rows_main, columns=headers_main),
                "costos": pd.DataFrame(rows_costos, columns=headers_costos),
                "info": {"paquetes": paquetes, "cajas": cajas}
            }
            resumen_list.append({"Master": master, "Cajas": cajas, "Paquetes": paquetes})
        
        df_resumen = pd.DataFrame(resumen_list)
        return resultados, df_resumen, None

    except Exception as e: return None, None, str(e)

def to_excel_bytes(df, fmt='xlsx'):
    output = io.BytesIO()
    if fmt == 'xlsx':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
    else:
        with pd.ExcelWriter(output, engine='xlwt') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()


# --- FUNCIONES ADMIN ---
def admin_crear_usuario(u, r):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO usuarios (username, password, rol, avatar) VALUES (%s, '123456', %s, 'avatar_1')", (u, r))
            conn.commit()
            conn.close()
            return True
        except:
            pass
    return False

def admin_get_users():
    conn = get_connection()
    if conn:
        df = pd.read_sql("SELECT id, username, rol, activo FROM usuarios", conn)
        conn.close()
        return df
    return pd.DataFrame()

def admin_toggle(uid, curr):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        new_status = 0 if curr == 1 else 1
        cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (new_status, uid))
        conn.commit()
        conn.close()

def admin_update_role(uid, new_role):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET rol=%s WHERE id=%s", (new_role, uid))
            conn.commit()
            conn.close()
            return True
        except:
            pass
    return False

def admin_restablecer_password(rid, uname):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET password='123456' WHERE username=%s", (uname,))
        cur.execute("UPDATE password_requests SET status='resuelto' WHERE id=%s", (rid,))
        conn.commit()
        conn.close()

def solicitar_reset_pass(username):
    conn = get_connection()
    if not conn: return "error"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username=%s", (username,))
        user_exists = cur.fetchone()
        
        if user_exists:
            cur.execute("SELECT id FROM password_requests WHERE username=%s AND status='pendiente'", (username,))
            if not cur.fetchone():
                cur.execute("INSERT INTO password_requests (username) VALUES (%s)", (username,))
                conn.commit()
                conn.close()
                return "ok"
            conn.close()
            return "pendiente"
        conn.close()
        return "no_user"
    except:
        return "error"

def cambiar_password(uid, np):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET password=%s WHERE id=%s", (np, uid))
            conn.commit()
            conn.close()
            return True
        except:
            pass
    return False

# --- 4. MODAL ---
@st.dialog("Gestión de Carga")
def modal_registro(datos=None):
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
        d_serv = datos.get('servicio', SERVICIOS[0])
        d_mast = datos.get('master', "")
        d_paq = datos.get('paquetes', 0)
        d_com = datos.get('comentarios', "")
        d_esp = len([x for x in re.split(r'[\n, ]+', d_mast) if x.strip()]) or 1
    with st.form("frm"):
        c1, c2 = st.columns(2)
        with c1:
            fin = st.date_input("Fecha Llegada", d_fecha, disabled=disabled)
            pin = st.selectbox("Proveedor", PROVEEDORES, index=PROVEEDORES.index(d_prov), disabled=disabled)
            clin = st.selectbox("Cliente", PLATAFORMAS, index=PLATAFORMAS.index(d_plat), disabled=disabled)
        with c2:
            sin = st.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(d_serv) if d_serv in SERVICIOS else 0, disabled=disabled)
            pain = st.number_input("Total Paquetes", 0, value=int(d_paq), disabled=disabled)
            esperados = st.number_input("Masters Esperadas", min_value=1, value=d_esp, disabled=disabled)
        st.markdown("---")
        st.write("📋 **Masters (Pegar Bloque)**")
        min_ = st.text_area("Códigos separados por espacio/enter", d_mast, height=100, disabled=disabled)
        lista_masters = [m for m in re.split(r'[\n, ]+', min_) if m.strip()]
        conteo_actual = len(lista_masters)
        col_val1, col_val2 = st.columns(2)
        col_val1.caption(f"Detectadas: {conteo_actual}")
        if conteo_actual == esperados: col_val2.markdown(f"<span class='count-ok'>✅ Cuadra</span>", unsafe_allow_html=True)
        else: col_val2.markdown(f"<span class='count-err'>⚠️ Diferencia: {conteo_actual - esperados}</span>", unsafe_allow_html=True)
        com = st.text_area("Notas", d_com, disabled=disabled)
        if not disabled:
            if st.form_submit_button("💾 Guardar / Actualizar", type="primary", use_container_width=True):
                guardar_registro(d_id, fin, pin, clin, sin, min_, pain, com)
                st.rerun()
    if d_id is not None and not disabled:
        st.markdown("---")
        with st.expander("🗑️ Eliminar este Registro"):
            st.warning("Esta acción es irreversible.")
            del_pass = st.text_input("Ingresa contraseña de Administrador:", type="password")
            if st.button("Confirmar Eliminación", type="secondary"):
                if eliminar_registro(d_id, del_pass): st.rerun()

# ==============================================================================
#  INTERFAZ PRINCIPAL
# ==============================================================================

if not st.session_state['logged_in']:
    st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #1e293b;'>Nexus Logística</h2>", unsafe_allow_html=True)
    u = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
    st.write("")
    p = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
    st.write("")
    if st.button("ACCEDER"):
        user = verificar_login(u, p)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user
            st.rerun()
        else: st.error("Credenciales inválidas")
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Recuperar contraseña"):
        ur = st.text_input("Usuario")
        if st.button("Solicitar Reset"):
            r = solicitar_reset_pass(ur)
            if r=="ok": st.success("Enviado.")
            else: st.warning("Error.")

else:
    u_info = st.session_state['user_info']
    rol = u_info['rol']
    
    with st.sidebar:
        av = AVATARS.get(u_info.get('avatar'), '👤')
        st.markdown(f"<div class='avatar-float' title='{u_info['username']}'>{av}</div>", unsafe_allow_html=True)
        
        opciones = ["📅", "📈", "📑", "⚙️"] 
        if rol == 'admin': opciones.extend(["👥", "🔑"])
        
        seleccion = st.radio("Menu", opciones, label_visibility="collapsed")
        
        mapa = {
            "📅": "calendar", 
            "📈": "analytics_pro", 
            "📑": "temu_manager", 
            "⚙️": "user_settings", 
            "👥": "admin_users", 
            "🔑": "admin_reqs"
        }
        st.session_state['current_view'] = mapa.get(seleccion, "calendar")

        st.markdown("<div class='logout-float'></div>", unsafe_allow_html=True)
        if st.sidebar.button("🚪", help="Salir"):
            st.session_state['logged_in'] = False
            st.rerun()

    vista = st.session_state['current_view']
    df = cargar_datos()

    if vista == "calendar":
        c1, c2 = st.columns([6, 1])
        c1.title("Calendario Operativo")
        if rol != 'analista':
            if c2.button("➕ Nuevo", type="primary"): modal_registro(None)

        evts = []
        if not df.empty:
            for _, r in df.iterrows():
                color = "#3b82f6" 
                if "AliExpress" in r['plataforma_cliente']: color = "#f97316"
                elif "Temu" in r['plataforma_cliente']: color = "#10b981"
                props = {
                    "id": int(r['id']), "fecha_str": str(r['fecha_str']),
                    "proveedor": str(r['proveedor_logistico']), "plataforma": str(r['plataforma_cliente']),
                    "servicio": str(r['tipo_servicio']), "master": str(r['master_lote']),
                    "paquetes": int(r['paquetes']), "comentarios": str(r['comentarios'])
                }
                evts.append({"title": f"📦{int(r['paquetes'])} | 🔑{r['conteo_masters_real']}", "start": r['fecha_str'], "backgroundColor": color, "borderColor": color, "extendedProps": props})
        cal = calendar(events=evts, options={"initialView": "dayGridMonth", "height": "750px"}, key="cal_main")
        if cal.get("eventClick"): modal_registro(cal["eventClick"]["event"]["extendedProps"])

    elif vista == "analytics_pro":
        st.title("Analytics & Reportes")
        if df.empty:
            st.warning("Sin datos.")
        else:
            with st.container(border=True):
                c_search, c_date = st.columns([1, 2])
                search_master = c_search.text_input("🔍 Buscar Master Exacta", placeholder="Escribe el código...")
                min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
                rango = c_date.date_input("Rango", [min_d, max_d])
            df_fil = df.copy()
            if search_master:
                conn = get_connection()
                try:
                    q = f"SELECT registro_id, fecha_registro FROM masters_detalle WHERE master_code LIKE '%{search_master}%'"
                    df_masters_found = pd.read_sql(q, conn)
                    conn.close()
                    if not df_masters_found.empty:
                        df_fil = df_fil[df_fil['id'].isin(df_masters_found['registro_id'].unique())]
                        st.success(f"✅ Encontrada en {len(df_fil)} viaje(s).")
                        st.dataframe(df_masters_found[['master_code', 'fecha_registro']], hide_index=True)
                    else:
                        st.error("❌ No encontrada.")
                        df_fil = pd.DataFrame()
                except: pass
            elif len(rango) == 2:
                df_fil = df_fil[(df_fil['fecha'].dt.date >= rango[0]) & (df_fil['fecha'].dt.date <= rango[1])]
            st.divider()
            if not df_fil.empty:
                k1, k2, k3, k4 = st.columns(4)
                k1.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Paquetes</div><div class='kpi-val'>{df_fil['paquetes'].sum():,.0f}</div></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Masters Reales</div><div class='kpi-val'>{df_fil['conteo_masters_real'].sum():,.0f}</div></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Viajes</div><div class='kpi-val'>{len(df_fil)}</div></div>", unsafe_allow_html=True)
                k4.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Promedio</div><div class='kpi-val'>{df_fil['paquetes'].mean():,.0f}</div></div>", unsafe_allow_html=True)
                st.write("")
                tab1, tab2, tab3 = st.tabs(["📅 Resumen Semanal", "📊 Gráficos", "📥 Matriz"])
                with tab1:
                    st.subheader("Resumen Semanal de Operaciones")
                    resumen = df_fil.groupby(['Año', 'Semana', 'Mes']).agg(
                        Paquetes=('paquetes', 'sum'), Masters=('conteo_masters_real', 'sum'), Viajes=('id', 'count')
                    ).reset_index()
                    def get_week_dates(year, week):
                        d = date.fromisocalendar(year, week, 1); return f"{d.strftime('%d-%b')} al {(d + timedelta(days=6)).strftime('%d-%b')}"
                    resumen['Rango'] = resumen.apply(lambda x: get_week_dates(x['Año'], x['Semana']), axis=1)
                    resumen = resumen[['Año', 'Semana', 'Mes', 'Rango', 'Viajes', 'Masters', 'Paquetes']]
                    st.dataframe(resumen, use_container_width=True, hide_index=True)
                with tab2:
                    g1, g2 = st.columns(2)
                    with g1: st.plotly_chart(px.bar(df_fil.groupby('fecha')['paquetes'].sum().reset_index(), x='fecha', y='paquetes'), use_container_width=True)
                    with g2: st.plotly_chart(px.pie(df_fil, names='proveedor_logistico', values='paquetes', hole=0.5), use_container_width=True)
                with tab3:
                    st.dataframe(df_fil, use_container_width=True)
                    csv = df_fil.to_csv(index=False).encode('utf-8')
                    st.download_button("Descargar CSV", csv, "reporte.csv", "text/csv")

    elif vista == "temu_manager":
        st.title("Gestor TEMU | Multi-Formato")
        st.markdown("Procesamiento inteligente de archivos Excel.")
        
        with st.container(border=True):
            f_temu = st.file_uploader("Cargar Archivo de DATOS (.xlsx, .xls)", type=["xlsx", "xls"])
            if f_temu:
                resultados, df_resumen, error = procesar_archivo_temu(f_temu)
                
                if error:
                    st.error(f"Error al procesar: {error}")
                elif resultados:
                    # TABLA RESUMEN PEQUEÑA
                    st.subheader("📋 Resumen de Carga")
                    st.dataframe(df_resumen, hide_index=True, use_container_width=False)
                    
                    st.divider()
                    st.subheader("📁 Descargas Disponibles")
                    
                    # Selector de Formato
                    fmt_option = st.radio("Formato de salida:", ["Excel Moderno (.xlsx)", "Excel 97-2003 (.xls)"], horizontal=True)
                    fmt_ext = "xlsx" if "Moderno" in fmt_option else "xls"
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt_ext == "xlsx" else "application/vnd.ms-excel"

                    for master, data in resultados.items():
                        with st.expander(f"📦 Master: {master} ({data['info']['paquetes']} paq)", expanded=False):
                            
                            # BARRA DE BÚSQUEDA INTERACTIVA
                            search_q = st.text_input(f"🔍 Buscar en Master {master}", key=f"s_{master}", placeholder="Escribe para filtrar...")
                            
                            c_main, c_cost = st.columns(2)
                            
                            c_main.download_button(
                                label=f"📥 Manifiesto .{fmt_ext}",
                                data=to_excel_bytes(data["main"], fmt_ext),
                                file_name=f"{master}.{fmt_ext}",
                                mime=mime_type,
                                key=f"btn_main_{master}"
                            )
                            
                            c_cost.download_button(
                                label=f"💲 Costos .{fmt_ext}",
                                data=to_excel_bytes(data["costos"], fmt_ext),
                                file_name=f"{master}_Costos.{fmt_ext}",
                                mime=mime_type,
                                key=f"btn_cost_{master}"
                            )
                            
                            st.write("---")
                            st.caption("Vista Previa del Manifiesto:")
                            
                            # FILTRO DINÁMICO
                            df_display = data["main"]
                            if search_q:
                                mask = df_display.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)
                                df_display = df_display[mask]
                                
                            st.dataframe(df_display, hide_index=True)

    elif vista == "user_settings":
        st.title("Configuración")
        with st.container(border=True):
            st.subheader("Cambiar Contraseña")
            p1 = st.text_input("Nueva", type="password")
            p2 = st.text_input("Confirmar", type="password")
            if st.button("Actualizar", type="primary"):
                if p1 and p1==p2:
                    if cambiar_password(u_info['id'], p1): st.success("OK")
                    else: st.error("Error")
                else: st.warning("No coinciden")

    elif vista == "admin_users":
        st.title("Usuarios")
        t1, t2 = st.tabs(["Crear", "Lista"])
        with t1:
            with st.form("new_u"):
                nu = st.text_input("User"); nr = st.selectbox("Rol", ["user", "analista", "admin"])
                if st.form_submit_button("Crear"): 
                    if admin_crear_usuario(nu, nr): st.success("Creado")
        with t2:
            df_u = admin_get_users()
            st.dataframe(df_u, use_container_width=True)
            if not df_u.empty:
                c1, c2, c3 = st.columns(3)
                uid = c1.selectbox("Seleccionar Usuario", df_u['id'].tolist())
                if uid:
                    current_user_data = df_u[df_u['id'] == uid].iloc[0]
                    current_role = current_user_data['rol']
                    current_active = current_user_data['activo']
                    new_role = c2.selectbox("Cambiar Rol", ["user", "analista", "admin"], index=["user", "analista", "admin"].index(current_role))
                    if c2.button("💾 Actualizar Rol"):
                        if admin_update_role(uid, new_role): st.success("Rol actualizado"); st.rerun()
                        else: st.error("Error")
                    btn_lbl = "🔴 Desactivar" if current_active == 1 else "🟢 Reactivar"
                    if c3.button(btn_lbl):
                        admin_toggle(uid, current_active); st.rerun()

    elif vista == "admin_reqs":
        st.title("Claves")
        reqs = pd.read_sql("SELECT * FROM password_requests WHERE status='pendiente'", get_connection())
        if reqs.empty: st.success("Limpio")
        else:
            for _, r in reqs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"{r['username']}")
                if c2.button("Reset", key=r['id']): admin_restablecer_password(r['id'], r['username']); st.rerun()
