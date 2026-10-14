import streamlit as st
from openai import OpenAI
from utils import get_connection

APP_NAME = "Nexus AI"
DEFAULT_FAST_MODEL = "gpt-6-luna"
DEFAULT_SMART_MODEL = "gpt-6-sol"
MAX_HISTORY_MESSAGES = 30

SYSTEM_INSTRUCTIONS = """
Eres Nexus AI, un asistente general integrado dentro de Nexus Logística.

Tu función es ayudar al usuario con análisis, redacción, resúmenes, explicaciones,
cálculos conceptuales, programación, logística, e-commerce, operaciones y trabajo general.

Reglas:
- Responde en el mismo idioma del usuario, salvo que pida otro.
- Prioriza respuestas claras, precisas y accionables.
- Usa Markdown cuando ayude a organizar la respuesta.
- No inventes datos del sistema, clientes, operaciones o bases internas.
- Solo afirma que conoces información interna cuando esa información aparezca explícitamente
  en la conversación o sea proporcionada mediante una herramienta habilitada.
- Si una respuesta depende de datos que no tienes, indícalo con claridad.
- No reveles claves, secretos, credenciales ni información sensible.
"""


def _openai_secret(name, default=None):
    try:
        section = st.secrets["openai"]
        return section.get(name, default)
    except Exception:
        return default


def _model_options():
    fast = _openai_secret("model_fast", DEFAULT_FAST_MODEL)
    smart = _openai_secret("model_smart", DEFAULT_SMART_MODEL)
    return {
        "Rápido": fast,
        "Avanzado": smart,
    }


def _init_db():
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_conversations (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL DEFAULT 'Nueva conversación',
                model VARCHAR(100) NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_ai_conv_user_updated (username, updated_at)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                conversation_id BIGINT NOT NULL,
                role VARCHAR(20) NOT NULL,
                content LONGTEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ai_msg_conversation (conversation_id)
            )
            """
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def _list_conversations(username, limit=30):
    conn = get_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, title, model, created_at, updated_at
            FROM ai_conversations
            WHERE username = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (username, limit),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return []


def _conversation_belongs_to_user(conversation_id, username):
    if not conversation_id:
        return False

    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM ai_conversations WHERE id=%s AND username=%s LIMIT 1",
            (conversation_id, username),
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def _create_conversation(username, model):
    conn = get_connection()
    if not conn:
        return None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_conversations (username, title, model)
            VALUES (%s, %s, %s)
            """,
            (username, "Nueva conversación", model),
        )
        conversation_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        return conversation_id
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def _load_messages(conversation_id, username):
    conn = get_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT m.role, m.content, m.created_at
            FROM ai_messages m
            INNER JOIN ai_conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = %s
              AND c.username = %s
            ORDER BY m.id ASC
            """,
            (conversation_id, username),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return []


def _save_message(conversation_id, role, content):
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_messages (conversation_id, role, content)
            VALUES (%s, %s, %s)
            """,
            (conversation_id, role, content),
        )
        cur.execute(
            "UPDATE ai_conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (conversation_id,),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def _set_conversation_title(conversation_id, title):
    clean_title = " ".join((title or "").strip().split())
    if not clean_title:
        clean_title = "Nueva conversación"
    clean_title = clean_title[:80]

    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ai_conversations SET title=%s WHERE id=%s",
            (clean_title, conversation_id),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _update_conversation_model(conversation_id, model):
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ai_conversations SET model=%s WHERE id=%s",
            (model, conversation_id),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _delete_conversation(conversation_id, username):
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM ai_conversations WHERE id=%s AND username=%s LIMIT 1",
            (conversation_id, username),
        )
        if cur.fetchone() is None:
            cur.close()
            conn.close()
            return False

        cur.execute(
            "DELETE FROM ai_messages WHERE conversation_id=%s",
            (conversation_id,),
        )
        cur.execute(
            "DELETE FROM ai_conversations WHERE id=%s AND username=%s",
            (conversation_id, username),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def _prepare_api_history(messages, prompt):
    recent = messages[-MAX_HISTORY_MESSAGES:]
    payload = []

    for msg in recent:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            payload.append({"role": role, "content": content})

    payload.append({"role": "user", "content": prompt})
    return payload


def _ask_openai(client, model, messages, prompt, use_web):
    request = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": _prepare_api_history(messages, prompt),
        "max_output_tokens": 3500,
    }

    if use_web:
        request["tools"] = [{"type": "web_search"}]

    return client.responses.create(**request)


def _render_setup():
    st.warning("Nexus AI está instalado, pero falta configurar la API de OpenAI.")
    st.markdown(
        "Agrega la clave en los **Secrets** de tu aplicación de Streamlit. "
        "No guardes la API key dentro de GitHub."
    )
    st.code(
        """[openai]
api_key = "sk-..."
model_fast = "gpt-6-luna"
model_smart = "gpt-6-sol"
""",
        language="toml",
    )


def show(user_info):
    username = user_info.get("username", "usuario")
    api_key = _openai_secret("api_key")

    st.title("✨ Nexus AI")
    st.caption("Asistente de inteligencia artificial integrado a Nexus Logística")

    if not api_key:
        _render_setup()
        return

    if not _init_db():
        st.error("No fue posible inicializar el historial de Nexus AI en la base de datos.")
        return

    model_options = _model_options()

    if "nexus_ai_conversation_id" not in st.session_state:
        st.session_state["nexus_ai_conversation_id"] = None

    if "nexus_ai_mode" not in st.session_state:
        st.session_state["nexus_ai_mode"] = "Rápido"

    active_id = st.session_state["nexus_ai_conversation_id"]
    if active_id and not _conversation_belongs_to_user(active_id, username):
        active_id = None
        st.session_state["nexus_ai_conversation_id"] = None

    history_col, chat_col = st.columns([1.2, 4], gap="large")

    with history_col:
        st.subheader("Conversaciones")

        if st.button("＋ Nueva conversación", use_container_width=True, type="primary"):
            st.session_state["nexus_ai_conversation_id"] = None
            st.rerun()

        st.write("")
        conversations = _list_conversations(username)

        if not conversations:
            st.caption("Aún no tienes conversaciones guardadas.")
        else:
            for conv in conversations:
                title = conv.get("title") or "Nueva conversación"
                is_active = conv["id"] == active_id
                label = f"{'● ' if is_active else ''}{title}"
                if st.button(
                    label,
                    key=f"nexus_ai_conv_{conv['id']}",
                    use_container_width=True,
                ):
                    st.session_state["nexus_ai_conversation_id"] = conv["id"]
                    if conv.get("model"):
                        for mode_name, model_name in model_options.items():
                            if model_name == conv["model"]:
                                st.session_state["nexus_ai_mode"] = mode_name
                                break
                    st.rerun()

        if active_id:
            with st.expander("Opciones de conversación"):
                if st.button(
                    "Eliminar conversación",
                    key=f"delete_nexus_ai_{active_id}",
                    use_container_width=True,
                ):
                    if _delete_conversation(active_id, username):
                        st.session_state["nexus_ai_conversation_id"] = None
                        st.rerun()
                    else:
                        st.error("No se pudo eliminar la conversación.")

    with chat_col:
        control_a, control_b = st.columns([1, 1])

        with control_a:
            selected_mode = st.selectbox(
                "Modelo",
                options=list(model_options.keys()),
                key="nexus_ai_mode",
                help="Rápido prioriza costo/velocidad. Avanzado prioriza capacidad.",
            )
            selected_model = model_options[selected_mode]

        with control_b:
            use_web = st.toggle(
                "Buscar en Internet",
                value=False,
                help="Permite que Nexus AI consulte información pública actual cuando sea necesario.",
            )

        if active_id:
            _update_conversation_model(active_id, selected_model)
            messages = _load_messages(active_id, username)
        else:
            messages = []

        if not messages:
            st.markdown(
                """
                ### ¿En qué te ayudo?
                Puedes pedirme que redacte, analice, explique, resuma, compare,
                programe o resuelva dudas de trabajo y logística.
                """
            )
            st.caption(
                "El historial se guarda por usuario en Nexus. "
                "La búsqueda web solo se activa cuando enciendes el interruptor."
            )

        for msg in messages:
            role = msg.get("role", "assistant")
            with st.chat_message(role):
                st.markdown(msg.get("content", ""))

        prompt = st.chat_input("Escribe un mensaje para Nexus AI...")

        if prompt:
            if not active_id:
                active_id = _create_conversation(username, selected_model)
                if not active_id:
                    st.error("No se pudo crear la conversación.")
                    return
                st.session_state["nexus_ai_conversation_id"] = active_id
                _set_conversation_title(active_id, prompt)

            if not _save_message(active_id, "user", prompt):
                st.error("No se pudo guardar tu mensaje.")
                return

            with st.chat_message("user"):
                st.markdown(prompt)

            try:
                client = OpenAI(api_key=api_key)
                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        response = _ask_openai(
                            client=client,
                            model=selected_model,
                            messages=messages,
                            prompt=prompt,
                            use_web=use_web,
                        )
                        answer = (response.output_text or "").strip()

                    if not answer:
                        answer = "No recibí contenido de respuesta. Intenta nuevamente."

                    st.markdown(answer)

                    usage = getattr(response, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "input_tokens", None)
                        output_tokens = getattr(usage, "output_tokens", None)
                        if input_tokens is not None and output_tokens is not None:
                            st.caption(
                                f"Uso de esta respuesta: {input_tokens:,} tokens de entrada · "
                                f"{output_tokens:,} tokens de salida"
                            )

                _save_message(active_id, "assistant", answer)
                st.rerun()

            except Exception as exc:
                st.error(
                    "Nexus AI no pudo completar la respuesta. "
                    "Verifica la API key, el modelo configurado y el saldo/límites de la API."
                )
                with st.expander("Detalle técnico"):
                    st.code(str(exc))
