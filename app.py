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


def mostrar_acceso(repository: InventoryRepository) -> None:
    st.subheader("Accede a tu inventario")
    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.form("formulario_login"):
            email = st.text_input("Correo electrónico", key="login_email")
            password = st.text_input(
                "Contraseña", type="password", key="login_password"
            )
            enviar_login = st.form_submit_button(
                "Iniciar sesión", type="primary", use_container_width=True
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
                "Crear cuenta", type="primary", use_container_width=True
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
    st.sidebar.header("⚡ Acción rápida")
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
        accion = st.sidebar.button("➕ Guardar producto", use_container_width=True)
    else:
        accion = st.sidebar.button("➖ Retirar unidades", use_container_width=True)

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

    metricas[0].metric("📦 Productos distintos", len(df_inventario))
    metricas[1].metric("📊 Stock total", total_stock)
    metricas[2].metric("💰 Valor del inventario", f"${valor_inventario:,.2f}")
    metricas[3].metric("🏷️ Categoría principal", categoria_principal)
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

    st.subheader("📋 Inventario")
    df_editado = st.data_editor(
        df_filtrado,
        num_rows="dynamic",
        use_container_width=True,
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
            "💾 Guardar cambios", type="primary", use_container_width=True
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
    st.title("🛍️ Control de Inventario Multicategoría")
    st.caption("Inventario local con cuentas independientes.")

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
    st.sidebar.caption(f"Sesión: {usuario['email']}")
    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state.pop("usuario", None)
        st.rerun()

    mostrar_accion_rapida(repository, user_id)
    if mensaje := st.session_state.pop("mensaje_exito", None):
        st.success(mensaje)
    mostrar_inventario(repository, user_id)


if __name__ == "__main__":
    main()