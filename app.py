import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from database import CATEGORIAS, InventoryRepository


DB_PATH = Path(
    os.environ.get("INVENTORY_DB_PATH", Path(__file__).with_name("inventory.db"))
)


@st.cache_resource
def obtener_repositorio(db_path: str) -> InventoryRepository:
    return InventoryRepository(db_path)


def aplicar_estilos() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

        :root {
            --ink: #202a26;
            --muted: #707b74;
            --paper: #f3f4ef;
            --surface: #ffffff;
            --line: #dfe4dc;
            --jade: #286653;
            --jade-dark: #173b32;
            --copper: #ba6947;
        }

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
            color: var(--ink);
            letter-spacing: 0;
        }
        .stApp { background: var(--paper); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stMainBlockContainer"] {
            max-width: 1420px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 {
            color: var(--ink);
            font-family: 'Playfair Display', Georgia, serif !important;
            letter-spacing: 0 !important;
        }
        h1 { font-size: 2.55rem !important; line-height: 1.12 !important; }
        h2 { font-size: 1.8rem !important; }
        h3 { font-size: 1.3rem !important; }
        [data-testid="stCaptionContainer"] p {
            color: var(--muted);
            font-size: 0.94rem;
        }
        .masthead {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--line);
            padding-bottom: 0.9rem;
            margin-bottom: 1.8rem;
            color: var(--jade);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .section-kicker {
            color: var(--copper);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        [data-testid="stSidebar"] {
            background: var(--jade-dark);
            border-right: 1px solid #31594e;
        }
        [data-testid="stSidebar"] * { color: #f2f4ee; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            color: #bdcec4;
        }
        [data-testid="stSidebar"] hr { border-color: #45675c; }
        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-top: 3px solid var(--jade);
            border-radius: 5px;
            padding: 1rem 1.15rem;
        }
        [data-testid="stMetricLabel"] p {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: var(--ink);
            font-family: 'Playfair Display', Georgia, serif;
        }
        [data-testid="stDataEditor"] {
            border: 1px solid var(--line);
            border-radius: 5px;
            background: var(--surface);
        }
        [data-testid="stForm"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 5px;
            padding: 1.35rem;
        }
        [data-baseweb="tab-list"] {
            gap: 1.1rem;
            border-bottom: 1px solid var(--line);
        }
        [data-baseweb="tab"] { color: var(--muted); }
        [data-baseweb="tab-highlight"] { background: var(--copper); }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button {
            border-radius: 4px;
            font-weight: 600;
            transition: transform 140ms ease, filter 140ms ease;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-1px);
            filter: brightness(0.96);
        }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: var(--jade);
            border-color: var(--jade);
        }
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input {
            background: #fff;
            border-color: var(--line);
        }
        @media (max-width: 760px) {
            [data-testid="stMainBlockContainer"] {
                padding: 1.2rem 1rem 2rem;
            }
            h1 { font-size: 2rem !important; }
            .masthead { font-size: 0.62rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_acceso(repository: InventoryRepository) -> None:
    st.markdown(
        '<div class="section-kicker">Acceso privado</div>',
        unsafe_allow_html=True,
    )
    col_intro, col_form = st.columns([0.9, 1.1], gap="large")
    with col_intro:
        st.subheader("Tu inventario, en orden.")
        st.caption("Control sencillo para cada producto y cada cuenta.")
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="section-kicker">INVENTARIO · CONTROL · CLARIDAD</div>',
            unsafe_allow_html=True,
        )

    with col_form:
        tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

        with tab_login:
            with st.form("formulario_login"):
                email = st.text_input("Correo electrónico", key="login_email")
                password = st.text_input(
                    "Contraseña", type="password", key="login_password"
                )
                enviar_login = st.form_submit_button(
                    "Iniciar sesión", type="primary", width="stretch"
                )

            if enviar_login:
                try:
                    usuario = repository.autenticar_usuario(email, password)
                    if usuario is None:
                        st.error("Correo o contraseña incorrectos.")
                    else:
                        st.session_state["usuario"] = usuario
                        st.rerun()
                except sqlite3.Error as exc:
                    st.error(f"No se pudo iniciar sesión en la base de datos: {exc}")

        with tab_registro:
            with st.form("formulario_registro"):
                email_nuevo = st.text_input("Correo electrónico", key="registro_email")
                password_nueva = st.text_input(
                    "Contraseña", type="password", key="registro_password"
                )
                confirmar_password = st.text_input(
                    "Confirmar contraseña", type="password", key="registro_confirmar"
                )
                enviar_registro = st.form_submit_button(
                    "Crear cuenta", type="primary", width="stretch"
                )

            if enviar_registro:
                if password_nueva != confirmar_password:
                    st.warning("Las contraseñas no coinciden.")
                else:
                    try:
                        usuario = repository.registrar_usuario(
                            email_nuevo, password_nueva
                        )
                        st.session_state["usuario"] = usuario
                        st.session_state["mensaje_exito"] = "Cuenta creada correctamente."
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except sqlite3.Error as exc:
                        st.error(f"No se pudo crear la cuenta: {exc}")


def mostrar_accion_rapida(repository: InventoryRepository, user_id: int) -> None:
    st.sidebar.markdown('<div class="section-kicker">ACCIONES</div>', unsafe_allow_html=True)
    st.sidebar.header("Movimiento de stock")
    opcion = st.sidebar.radio(
        "Operación:", ["Agregar / Incrementar", "Retirar stock"]
    )
    nombre = st.sidebar.text_input("Nombre del producto:")
    categoria = st.sidebar.selectbox("Categoría:", CATEGORIAS)
    precio = st.sidebar.number_input(
        "Precio ($):", min_value=0.0, step=0.5, format="%.2f"
    )
    cantidad = st.sidebar.number_input("Cantidad:", min_value=1, step=1, value=1)

    if opcion == "Agregar / Incrementar":
        accion = st.sidebar.button("➕ Guardar producto", width="stretch")
    else:
        accion = st.sidebar.button("➖ Retirar unidades", width="stretch")

    if not accion:
        return
    if not nombre.strip():
        st.sidebar.warning("Escribe un nombre.")
        return

    try:
        if opcion == "Agregar / Incrementar":
            repository.agregar_o_incrementar(
                user_id, nombre, categoria, precio, int(cantidad)
            )
            mensaje = f"'{nombre.strip()}' actualizado."
        else:
            repository.retirar_stock(user_id, nombre, int(cantidad))
            mensaje = f"Retiradas {cantidad} unidades."
        st.session_state["mensaje_exito"] = mensaje
        st.rerun()
    except LookupError as exc:
        st.sidebar.error(str(exc))
    except ValueError as exc:
        st.sidebar.error(str(exc))
    except sqlite3.Error as exc:
        st.sidebar.error(f"Error de SQLite: {exc}")


def mostrar_inventario(repository: InventoryRepository, user_id: int) -> None:
    try:
        df_inventario = repository.obtener_inventario(user_id)
    except sqlite3.Error as exc:
        st.error(f"No se pudo leer el inventario: {exc}")
        return

    metricas = st.columns(4)
    total_stock = (
        int(df_inventario["cantidad"].sum()) if not df_inventario.empty else 0
    )
    valor_inventario = (
        (df_inventario["precio"] * df_inventario["cantidad"]).sum()
        if not df_inventario.empty
        else 0
    )
    categorias = df_inventario["categoria"].dropna()
    categoria_principal = categorias.mode().iloc[0] if not categorias.empty else "N/A"

    metricas[0].metric("Productos distintos", len(df_inventario))
    metricas[1].metric("Unidades en stock", total_stock)
    metricas[2].metric("Valor del inventario", f"${valor_inventario:,.2f}")
    metricas[3].metric("Categoría principal", categoria_principal)
    st.divider()

    col_busqueda, col_filtro = st.columns([2, 1])
    with col_busqueda:
        busqueda = st.text_input(
            "🔍 Buscar producto:", placeholder="Escribe para buscar..."
        )
    with col_filtro:
        categoria_filtro = st.selectbox(
            "📂 Filtrar categoría:", ["Todas"] + CATEGORIAS
        )

    df_filtrado = df_inventario.copy()
    if categoria_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["categoria"] == categoria_filtro]
    if busqueda.strip():
        coincidencias = df_filtrado["nombre"].str.lower().str.contains(
            busqueda.strip().lower(), regex=False, na=False
        )
        df_filtrado = df_filtrado[coincidencias]

    st.markdown('<div class="section-kicker">CATÁLOGO</div>', unsafe_allow_html=True)
    st.subheader("Inventario")
    df_editado = st.data_editor(
        df_filtrado,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "nombre": st.column_config.TextColumn("Producto", required=True),
            "categoria": st.column_config.SelectboxColumn(
                "Categoría", options=CATEGORIAS, required=True
            ),
            "precio": st.column_config.NumberColumn(
                "Precio unitario", min_value=0.0, format="$%.2f", required=True
            ),
            "cantidad": st.column_config.NumberColumn(
                "Unidades en stock", min_value=0, step=1, required=True
            ),
        },
        hide_index=True,
        key=f"editor_{user_id}_{categoria_filtro}_{busqueda.strip().lower()}",
    )

    col_guardar, _ = st.columns([1, 3])
    with col_guardar:
        if st.button(
            "💾 Guardar cambios", type="primary", width="stretch"
        ):
            try:
                repository.sincronizar_cambios(
                    user_id, df_editado, df_filtrado
                )
                st.session_state["mensaje_exito"] = "Inventario actualizado correctamente."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.Error as exc:
                st.error(f"No se pudo guardar el inventario: {exc}")


def main() -> None:
    st.set_page_config(
        page_title="Sistema de Inventario", page_icon="🛍️", layout="wide"
    )
    aplicar_estilos()
    st.markdown(
        '<div class="masthead"><span>VERDE / INVENTARIO</span>'
        '<span>CONTROL DE EXISTENCIAS</span></div>',
        unsafe_allow_html=True,
    )

    try:
        repository = obtener_repositorio(str(DB_PATH))
    except sqlite3.Error as exc:
        st.error(f"No se pudo iniciar la base SQLite: {exc}")
        st.stop()
        return

    usuario = st.session_state.get("usuario")
    if usuario is None:
        mostrar_acceso(repository)
        st.stop()
        return

    user_id = int(usuario["id"])
    st.title("Inventario")
    st.caption("Resumen operativo de tus productos y existencias.")
    st.sidebar.caption(f"Sesión: {usuario['email']}")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("usuario", None)
        st.rerun()

    mostrar_accion_rapida(repository, user_id)
    if mensaje := st.session_state.pop("mensaje_exito", None):
        st.success(mensaje)
    mostrar_inventario(repository, user_id)


if __name__ == "__main__":
    main()