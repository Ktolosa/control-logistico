import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import get_connection, to_excel_bytes, PROVEEDORES


PAISES_BASE = [
    "El Salvador",
    "Guatemala",
    "Honduras",
    "Costa Rica",
    "Nicaragua",
    "Panamá",
]

MESES_ES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

PROVEEDORES_LMD = sorted(set(["J&T"] + list(PROVEEDORES))) + ["Otro"]


def init_masters_db():
    """Crea la tabla regional de Másters si todavía no existe."""
    conn = get_connection()
    if not conn:
        return False, "No fue posible conectar con la base de datos."

    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS masters_regionales (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                pais VARCHAR(80) NOT NULL,
                master_cn_mia VARCHAR(120) NOT NULL,
                proveedor_lmd VARCHAR(120) NOT NULL,
                master_mia_destino VARCHAR(120) NOT NULL,
                anio SMALLINT NOT NULL,
                mes VARCHAR(20) NOT NULL,
                fecha_prealerta_cn_mia DATE NOT NULL,
                fecha_prealerta_mia_destino DATE NOT NULL,
                cajas INT NOT NULL DEFAULT 0,
                paquetes INT NOT NULL DEFAULT 0,
                peso_kg DECIMAL(16,2) NOT NULL DEFAULT 0,
                valor_fob DECIMAL(18,2) NOT NULL DEFAULT 0,
                created_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_masters_pais (pais),
                INDEX idx_masters_cn_mia (master_cn_mia),
                INDEX idx_masters_destino (master_mia_destino),
                INDEX idx_masters_periodo (anio, mes),
                UNIQUE KEY uq_master_regional (pais, master_cn_mia, master_mia_destino)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        conn.commit()
        conn.close()
        return True, "OK"
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return False, str(e)


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _periodo(fecha_ref):
    return int(fecha_ref.year), MESES_ES[int(fecha_ref.month)]


def guardar_master(data, user):
    conn = get_connection()
    if not conn:
        return False, "No fue posible conectar con la base de datos."

    try:
        cur = conn.cursor()
        anio, mes = _periodo(data["fecha_prealerta_cn_mia"])
        cur.execute(
            """
            INSERT INTO masters_regionales (
                pais, master_cn_mia, proveedor_lmd, master_mia_destino,
                anio, mes, fecha_prealerta_cn_mia, fecha_prealerta_mia_destino,
                cajas, paquetes, peso_kg, valor_fob, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                data["pais"],
                data["master_cn_mia"],
                data["proveedor_lmd"],
                data["master_mia_destino"],
                anio,
                mes,
                data["fecha_prealerta_cn_mia"],
                data["fecha_prealerta_mia_destino"],
                int(data["cajas"]),
                int(data["paquetes"]),
                float(data["peso_kg"]),
                float(data["valor_fob"]),
                user,
            ),
        )
        conn.commit()
        conn.close()
        return True, "Máster registrado correctamente."
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        if "Duplicate entry" in str(e) or "uq_master_regional" in str(e):
            return False, "Ya existe ese Máster CN-MIA + Máster destino para el país seleccionado."
        return False, str(e)


def actualizar_master(registro_id, data):
    conn = get_connection()
    if not conn:
        return False, "No fue posible conectar con la base de datos."

    try:
        cur = conn.cursor()
        anio, mes = _periodo(data["fecha_prealerta_cn_mia"])
        cur.execute(
            """
            UPDATE masters_regionales
            SET pais=%s,
                master_cn_mia=%s,
                proveedor_lmd=%s,
                master_mia_destino=%s,
                anio=%s,
                mes=%s,
                fecha_prealerta_cn_mia=%s,
                fecha_prealerta_mia_destino=%s,
                cajas=%s,
                paquetes=%s,
                peso_kg=%s,
                valor_fob=%s
            WHERE id=%s
            """,
            (
                data["pais"],
                data["master_cn_mia"],
                data["proveedor_lmd"],
                data["master_mia_destino"],
                anio,
                mes,
                data["fecha_prealerta_cn_mia"],
                data["fecha_prealerta_mia_destino"],
                int(data["cajas"]),
                int(data["paquetes"]),
                float(data["peso_kg"]),
                float(data["valor_fob"]),
                int(registro_id),
            ),
        )
        conn.commit()
        conn.close()
        return True, "Registro actualizado."
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        if "Duplicate entry" in str(e) or "uq_master_regional" in str(e):
            return False, "La combinación de Másters ya existe para ese país."
        return False, str(e)


def eliminar_master(registro_id):
    conn = get_connection()
    if not conn:
        return False, "No fue posible conectar con la base de datos."

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM masters_regionales WHERE id=%s", (int(registro_id),))
        conn.commit()
        conn.close()
        return True, "Registro eliminado."
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return False, str(e)


def cargar_masters(pais=None, anio=None, mes=None, proveedor=None, buscar=None):
    conn = get_connection()
    if not conn:
        return pd.DataFrame()

    where = []
    params = []

    if pais and pais != "Todos":
        where.append("pais=%s")
        params.append(pais)
    if anio and anio != "Todos":
        where.append("anio=%s")
        params.append(int(anio))
    if mes and mes != "Todos":
        where.append("mes=%s")
        params.append(mes)
    if proveedor and proveedor != "Todos":
        where.append("proveedor_lmd=%s")
        params.append(proveedor)
    if buscar:
        where.append("(master_cn_mia LIKE %s OR master_mia_destino LIKE %s)")
        patron = f"%{buscar.strip()}%"
        params.extend([patron, patron])

    sql = "SELECT * FROM masters_regionales"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fecha_prealerta_cn_mia DESC, id DESC"

    try:
        df = pd.read_sql(sql, conn, params=tuple(params))
        conn.close()
        return df
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return pd.DataFrame()


def obtener_registro(registro_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM masters_regionales WHERE id=%s", (int(registro_id),))
        row = cur.fetchone()
        conn.close()
        return row
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def _pais_input(default="El Salvador", key_prefix="new"):
    opciones = PAISES_BASE + ["Otro"]
    idx = opciones.index(default) if default in opciones else len(opciones) - 1
    pais_sel = st.selectbox("País *", opciones, index=idx, key=f"{key_prefix}_pais_sel")
    if pais_sel == "Otro":
        return st.text_input("Especificar país *", value="" if default in PAISES_BASE else default, key=f"{key_prefix}_pais_otro").strip()
    return pais_sel


def _proveedor_input(default="J&T", key_prefix="new"):
    opciones = PROVEEDORES_LMD
    idx = opciones.index(default) if default in opciones else opciones.index("Otro")
    prov_sel = st.selectbox("Proveedor LMD *", opciones, index=idx, key=f"{key_prefix}_prov_sel")
    if prov_sel == "Otro":
        return st.text_input("Especificar proveedor *", value="" if default in opciones else default, key=f"{key_prefix}_prov_otro").strip()
    return prov_sel


def _validar_form(data):
    obligatorios = [
        data.get("pais"),
        data.get("master_cn_mia"),
        data.get("proveedor_lmd"),
        data.get("master_mia_destino"),
    ]
    if not all(_normalizar_texto(x) for x in obligatorios):
        return False, "Completa todos los campos obligatorios (*)."
    if data["fecha_prealerta_mia_destino"] < data["fecha_prealerta_cn_mia"]:
        return False, "La fecha de prealerta MIA-Destino no puede ser anterior a la fecha CN-MIA."
    if min(data["cajas"], data["paquetes"], data["peso_kg"], data["valor_fob"]) < 0:
        return False, "Los valores numéricos no pueden ser negativos."
    return True, "OK"


@st.dialog("Editar registro de Máster")
def modal_editar(registro_id):
    row = obtener_registro(registro_id)
    if not row:
        st.error("No se pudo cargar el registro.")
        return

    fecha_cn = row.get("fecha_prealerta_cn_mia") or date.today()
    fecha_dest = row.get("fecha_prealerta_mia_destino") or fecha_cn
    if isinstance(fecha_cn, datetime):
        fecha_cn = fecha_cn.date()
    if isinstance(fecha_dest, datetime):
        fecha_dest = fecha_dest.date()

    c1, c2 = st.columns(2)
    with c1:
        pais = _pais_input(str(row.get("pais", "El Salvador")), key_prefix=f"edit_{registro_id}")
        master_cn = st.text_input("Máster (CN-MIA) *", value=str(row.get("master_cn_mia", "")), key=f"edit_{registro_id}_cn")
        fecha_cn_nueva = st.date_input("Fecha prealerta (CN-MIA) *", value=fecha_cn, key=f"edit_{registro_id}_fcn")
        cajas = st.number_input("Cajas", min_value=0, value=int(row.get("cajas", 0) or 0), step=1, key=f"edit_{registro_id}_cajas")
        peso = st.number_input("Peso (KG)", min_value=0.0, value=float(row.get("peso_kg", 0) or 0), step=0.01, format="%.2f", key=f"edit_{registro_id}_peso")

    with c2:
        proveedor = _proveedor_input(str(row.get("proveedor_lmd", "J&T")), key_prefix=f"edit_{registro_id}")
        master_dest = st.text_input("Máster (MIA-Destino) *", value=str(row.get("master_mia_destino", "")), key=f"edit_{registro_id}_dest")
        fecha_dest_nueva = st.date_input("Fecha prealerta (MIA-Destino) *", value=fecha_dest, key=f"edit_{registro_id}_fdest")
        paquetes = st.number_input("Paquetes", min_value=0, value=int(row.get("paquetes", 0) or 0), step=1, key=f"edit_{registro_id}_paq")
        valor_fob = st.number_input("Valor (FOB) USD", min_value=0.0, value=float(row.get("valor_fob", 0) or 0), step=0.01, format="%.2f", key=f"edit_{registro_id}_fob")

    data = {
        "pais": pais,
        "master_cn_mia": master_cn.strip(),
        "proveedor_lmd": proveedor,
        "master_mia_destino": master_dest.strip(),
        "fecha_prealerta_cn_mia": fecha_cn_nueva,
        "fecha_prealerta_mia_destino": fecha_dest_nueva,
        "cajas": cajas,
        "paquetes": paquetes,
        "peso_kg": peso,
        "valor_fob": valor_fob,
    }

    st.caption("Año y mes se recalculan automáticamente con la fecha prealerta CN-MIA.")
    b1, b2 = st.columns(2)
    if b1.button("💾 Guardar cambios", type="primary", use_container_width=True, key=f"save_{registro_id}"):
        ok_val, msg_val = _validar_form(data)
        if not ok_val:
            st.error(msg_val)
        else:
            ok, msg = actualizar_master(registro_id, data)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    confirmar = st.checkbox("Confirmo que deseo eliminar este registro", key=f"delete_confirm_{registro_id}")
    if b2.button("🗑️ Eliminar registro", use_container_width=True, key=f"delete_{registro_id}", disabled=not confirmar):
        ok, msg = eliminar_master(registro_id)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


def _form_nuevo(user_info):
    st.subheader("Nuevo registro")
    st.caption("Un único formulario regional. El país clasifica automáticamente cada Máster.")

    pais = st.selectbox("País *", PAISES_BASE, key="new_master_pais")

    with st.form("frm_master_regional", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            master_cn = st.text_input("Máster (CN-MIA) *", placeholder="Ej. 369-97922451")
            proveedor = st.text_input("Proveedor LMD *", value="J&T", placeholder="Ej. J&T")
            fecha_cn = st.date_input("Fecha prealerta (CN-MIA) *", value=date.today())
            cajas = st.number_input("Cajas", min_value=0, value=0, step=1)

        with c2:
            master_dest = st.text_input("Máster (MIA-Destino) *", placeholder="Ej. 810-50309184")
            fecha_dest = st.date_input("Fecha prealerta (MIA-Destino) *", value=date.today())
            paquetes = st.number_input("Paquetes", min_value=0, value=0, step=1)
            peso = st.number_input("Peso (KG)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
            valor_fob = st.number_input("Valor (FOB) USD", min_value=0.0, value=0.0, step=0.01, format="%.2f")

        anio, mes = _periodo(fecha_cn)
        st.info(f"País: **{pais}** · Periodo automático: **{mes} {anio}**")
        submitted = st.form_submit_button("💾 Registrar Máster", type="primary", use_container_width=True)

    if submitted:
        data = {
            "pais": pais,
            "master_cn_mia": master_cn.strip(),
            "proveedor_lmd": proveedor.strip(),
            "master_mia_destino": master_dest.strip(),
            "fecha_prealerta_cn_mia": fecha_cn,
            "fecha_prealerta_mia_destino": fecha_dest,
            "cajas": cajas,
            "paquetes": paquetes,
            "peso_kg": peso,
            "valor_fob": valor_fob,
        }
        ok_val, msg_val = _validar_form(data)
        if not ok_val:
            st.error(msg_val)
            return

        with st.spinner("Guardando registro..."):
            ok, msg = guardar_master(data, user_info.get("username", ""))
        if ok:
            st.success(msg)
            st.toast("Máster guardado", icon="✅")
        else:
            st.error(msg)

def _base_datos(user_info):
    st.subheader("Base de datos de Másters")

    all_df = cargar_masters()
    if all_df.empty:
        st.info("Todavía no hay registros de Másters.")
        return

    paises = ["Todos"] + sorted(all_df["pais"].dropna().astype(str).unique().tolist())
    anios = ["Todos"] + sorted(all_df["anio"].dropna().astype(int).unique().tolist(), reverse=True)
    meses_orden = [m for m in MESES_ES.values() if m in set(all_df["mes"].dropna().astype(str))]
    meses = ["Todos"] + meses_orden
    proveedores = ["Todos"] + sorted(all_df["proveedor_lmd"].dropna().astype(str).unique().tolist())

    f1, f2, f3, f4 = st.columns(4)
    pais = f1.selectbox("País", paises, key="flt_master_pais")
    anio = f2.selectbox("Año", anios, key="flt_master_anio")
    mes = f3.selectbox("Mes", meses, key="flt_master_mes")
    proveedor = f4.selectbox("Proveedor", proveedores, key="flt_master_prov")
    buscar = st.text_input("Buscar Máster", placeholder="CN-MIA o MIA-Destino", key="flt_master_buscar")

    df = cargar_masters(pais, anio, mes, proveedor, buscar)
    if df.empty:
        st.warning("No hay registros que coincidan con los filtros.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registros", f"{len(df):,}")
    m2.metric("Paquetes", f"{int(df['paquetes'].fillna(0).sum()):,}")
    m3.metric("Peso (KG)", f"{float(df['peso_kg'].fillna(0).sum()):,.2f}")
    m4.metric("FOB", f"${float(df['valor_fob'].fillna(0).sum()):,.2f}")

    vista = df[
        [
            "id",
            "pais",
            "master_cn_mia",
            "proveedor_lmd",
            "master_mia_destino",
            "anio",
            "mes",
            "fecha_prealerta_cn_mia",
            "fecha_prealerta_mia_destino",
            "cajas",
            "paquetes",
            "peso_kg",
            "valor_fob",
            "created_by",
            "created_at",
        ]
    ].copy()

    vista.columns = [
        "ID",
        "País",
        "Máster CN-MIA",
        "Proveedor LMD",
        "Máster MIA-Destino",
        "Año",
        "Mes",
        "Fecha Prealerta CN-MIA",
        "Fecha Prealerta MIA-Destino",
        "Cajas",
        "Paquetes",
        "Peso (KG)",
        "Valor (FOB)",
        "Creado por",
        "Fecha creación",
    ]

    st.dataframe(
        vista,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Peso (KG)": st.column_config.NumberColumn(format="%.2f"),
            "Valor (FOB)": st.column_config.NumberColumn(format="$%.2f"),
            "Fecha Prealerta CN-MIA": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Fecha Prealerta MIA-Destino": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Fecha creación": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
        },
    )

    x1, x2 = st.columns([1, 2])
    excel = to_excel_bytes(vista, "xlsx")
    x1.download_button(
        "📥 Exportar Excel",
        data=excel,
        file_name="masters_regionales.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    ids = df["id"].astype(int).tolist()
    selector = x2.selectbox(
        "Editar registro",
        ids,
        format_func=lambda rid: _format_registro_label(df, rid),
        key="edit_master_selector",
    )
    if st.button("✏️ Abrir registro seleccionado", use_container_width=True):
        modal_editar(selector)


def _format_registro_label(df, registro_id):
    row = df[df["id"].astype(int) == int(registro_id)]
    if row.empty:
        return f"ID {registro_id}"
    r = row.iloc[0]
    return f"#{registro_id} · {r['pais']} · {r['master_cn_mia']} → {r['master_mia_destino']}"


def _resumen():
    st.subheader("Resumen regional")
    df = cargar_masters()
    if df.empty:
        st.info("No hay información suficiente para mostrar el resumen.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Másters registrados", f"{len(df):,}")
    c2.metric("Paquetes", f"{int(df['paquetes'].fillna(0).sum()):,}")
    c3.metric("Cajas", f"{int(df['cajas'].fillna(0).sum()):,}")
    c4.metric("FOB total", f"${float(df['valor_fob'].fillna(0).sum()):,.2f}")

    por_pais = (
        df.groupby("pais", as_index=False)
        .agg(
            registros=("id", "count"),
            cajas=("cajas", "sum"),
            paquetes=("paquetes", "sum"),
            peso_kg=("peso_kg", "sum"),
            valor_fob=("valor_fob", "sum"),
        )
        .sort_values("paquetes", ascending=False)
    )
    por_pais.columns = ["País", "Registros", "Cajas", "Paquetes", "Peso (KG)", "Valor (FOB)"]

    st.markdown("#### Consolidado por país")
    st.dataframe(
        por_pais,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Peso (KG)": st.column_config.NumberColumn(format="%.2f"),
            "Valor (FOB)": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

    st.markdown("#### Paquetes por país")
    graf = por_pais.set_index("País")[["Paquetes"]]
    st.bar_chart(graf)


def show(user_info):
    ok, msg = init_masters_db()
    if not ok:
        st.error(f"No se pudo preparar la herramienta de Másters: {msg}")
        return

    st.title("📦 Másters Regionales")
    st.markdown("Registro, consulta y consolidación de Másters por país en una sola herramienta.")

    tab1, tab2, tab3 = st.tabs(["➕ Nuevo registro", "🗂️ Base de datos", "📊 Resumen"])
    with tab1:
        _form_nuevo(user_info)
    with tab2:
        _base_datos(user_info)
    with tab3:
        _resumen()
