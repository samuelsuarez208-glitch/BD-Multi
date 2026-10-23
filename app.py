import math

import pandas as pd
import streamlit as st
from supabase import Client, create_client


CATEGORIAS = ["Comida", "Ropa", "Electrodomésticos", "Otros"]
COLUMNAS = ["id", "nombre", "categoria", "precio", "cantidad"]


@st.cache_resource
def init_connection(url: str, key: str) -> Client:
    return create_client(url, key)


@st.cache_data(ttl=30, show_spinner=False)
def obtener_df_inventario(url: str, key: str) -> pd.DataFrame:
    client = init_connection(url, key)
    response = client.table("articulos").select("*").order("id").execute()
    if not response.data:
        return pd.DataFrame(columns=COLUMNAS)

    df = pd.DataFrame(response.data)
    for columna in COLUMNAS:
        if columna not in df.columns:
            df[columna] = None
    df = df[COLUMNAS]
    df["nombre"] = df["nombre"].fillna("").astype(str).str.capitalize()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0.0)
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    return df


class InventarioRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def agregar_o_incrementar(
        self, nombre: str, categoria: str, precio: float, cantidad: int
    ) -> None:
        nombre_norm = nombre.strip().lower()
        response = (
            self.client.table("articulos")
            .select("id,cantidad")
            .eq("nombre", nombre_norm)
            .limit(1)
            .execute()
        )
        if response.data:
            articulo = response.data[0]
            self.client.table("articulos").update(
                {
                    "cantidad": int(articulo["cantidad"]) + cantidad,
                    "precio": precio,
                    "categoria": categoria,
                }
            ).eq("id", articulo["id"]).execute()
            return

        self.client.table("articulos").insert(
            {
                "nombre": nombre_norm,
                "categoria": categoria,
                "precio": precio,
                "cantidad": cantidad,
            }
        ).execute()

    def retirar_stock(self, nombre: str, cantidad: int) -> int:
        nombre_norm = nombre.strip().lower()
        response = (
            self.client.table("articulos")
            .select("id,cantidad")
            .eq("nombre", nombre_norm)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise LookupError(f"'{nombre}' no existe.")

        articulo = response.data[0]
        stock_actual = int(articulo["cantidad"])
        if stock_actual < cantidad:
            raise ValueError(f"Solo quedan {stock_actual} unidades.")

        self.client.table("articulos").update(
            {"cantidad": stock_actual - cantidad}
        ).eq("id", articulo["id"]).execute()
        return stock_actual - cantidad

    def sincronizar_cambios(
        self, df_editado: pd.DataFrame, df_visible_original: pd.DataFrame
    ) -> None:
        ids_visibles = {
            int(value)
            for value in df_visible_original["id"].dropna()
        }
        filas_actuales = []
        ids_editados = set()

        for _, fila in df_editado.iterrows():
            nombre_value = fila.get("nombre")
            nombre = (
                ""
                if pd.isna(nombre_value)
                else str(nombre_value).strip().lower()
            )
            if not nombre:
                raise ValueError("Todos los productos deben tener un nombre.")

            categoria = fila.get("categoria")
            if pd.isna(categoria) or categoria not in CATEGORIAS:
                raise ValueError(f"Categoría no válida para '{nombre}'.")

            try:
                precio = float(fila.get("precio"))
                cantidad_num = float(fila.get("cantidad"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Precio o cantidad no válidos para '{nombre}'.") from exc

            if not math.isfinite(precio) or precio < 0:
                raise ValueError(f"El precio de '{nombre}' debe ser un número no negativo.")
            if (
                not math.isfinite(cantidad_num)
                or cantidad_num < 0
                or not cantidad_num.is_integer()
            ):
                raise ValueError(f"La cantidad de '{nombre}' debe ser un entero no negativo.")

            datos = {
                "nombre": nombre,
                "categoria": categoria,
                "precio": precio,
                "cantidad": int(cantidad_num),
            }
            id_value = fila.get("id")
            if pd.notna(id_value) and int(id_value) in ids_visibles:
                articulo_id = int(id_value)
                if articulo_id in ids_editados:
                    raise ValueError("Hay IDs duplicados en la tabla editada.")
                ids_editados.add(articulo_id)
                datos["id"] = articulo_id
            filas_actuales.append(datos)

        ids_a_eliminar = ids_visibles - ids_editados
        if ids_a_eliminar:
            self.client.table("articulos").delete().in_("id", list(ids_a_eliminar)).execute()

        actualizaciones = [fila for fila in filas_actuales if "id" in fila]
        inserciones = [fila for fila in filas_actuales if "id" not in fila]
        if actualizaciones:
            self.client.table("articulos").upsert(
                actualizaciones, on_conflict="id"
            ).execute()
        if inserciones:
            self.client.table("articulos").insert(inserciones).execute()


def mostrar_error(error: Exception) -> None:
    st.error(f"No se pudo completar la operación en Supabase: {error}")


def main() -> None:
    st.set_page_config(
        page_title="Sistema de Inventario", page_icon="🛍️", layout="wide"
    )
    st.title("🛍️ Control de Inventario Multicategoría")
    st.caption("Gestiona tus productos sincronizados con Supabase.")

    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = init_connection(url, key)
    except Exception as exc:
        st.error(
            "No se pudo iniciar la conexión. Configura `SUPABASE_URL` y "
            "`SUPABASE_KEY` en los Secrets de Streamlit."
        )
        st.stop()
        return

    repository = InventarioRepository(client)
    st.sidebar.header("⚡ Acción rápida")
    opcion = st.sidebar.radio("Operación:", ["Agregar / Incrementar", "Retirar stock"])
    nombre_in = st.sidebar.text_input("Nombre del producto:")
    categoria_in = st.sidebar.selectbox("Categoría:", CATEGORIAS)
    precio_in = st.sidebar.number_input(
        "Precio ($):", min_value=0.0, step=0.5, format="%.2f"
    )
    cantidad_in = st.sidebar.number_input(
        "Cantidad:", min_value=1, step=1, value=1
    )

    if opcion == "Agregar / Incrementar":
        if st.sidebar.button("➕ Guardar producto", use_container_width=True):
            if not nombre_in.strip():
                st.sidebar.warning("Escribe un nombre.")
            else:
                try:
                    repository.agregar_o_incrementar(
                        nombre_in, categoria_in, precio_in, cantidad_in
                    )
                    st.session_state["mensaje_exito"] = f"'{nombre_in.strip()}' actualizado."
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.sidebar.error(f"No se pudo guardar el producto: {exc}")
    elif st.sidebar.button("➖ Retirar unidades", use_container_width=True):
        if not nombre_in.strip():
            st.sidebar.warning("Escribe un nombre.")
        else:
            try:
                repository.retirar_stock(nombre_in, cantidad_in)
                st.session_state["mensaje_exito"] = f"Retiradas {cantidad_in} unidades."
                st.cache_data.clear()
                st.rerun()
            except LookupError as exc:
                st.sidebar.error(str(exc))
            except ValueError as exc:
                st.sidebar.error(str(exc))
            except Exception as exc:
                st.sidebar.error(f"No se pudo retirar el stock: {exc}")

    if mensaje := st.session_state.pop("mensaje_exito", None):
        st.success(mensaje)

    try:
        df_inventario = obtener_df_inventario(url, key)
    except Exception as exc:
        mostrar_error(exc)
        st.stop()
        return

    metrica_1, metrica_2, metrica_3, metrica_4 = st.columns(4)
    total_stock = int(df_inventario["cantidad"].sum()) if not df_inventario.empty else 0
    valor_inventario = (
        (df_inventario["precio"] * df_inventario["cantidad"]).sum()
        if not df_inventario.empty
        else 0
    )
    categorias = df_inventario["categoria"].dropna()
    categoria_principal = categorias.mode().iloc[0] if not categorias.empty else "N/A"

    metrica_1.metric("📦 Productos distintos", len(df_inventario))
    metrica_2.metric("📊 Stock total", total_stock)
    metrica_3.metric("💰 Valor del inventario", f"${valor_inventario:,.2f}")
    metrica_4.metric("🏷️ Categoría principal", categoria_principal)
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
        key="editor_tabla",
    )

    col_guardar, _ = st.columns([1, 3])
    with col_guardar:
        if st.button(
            "💾 Guardar cambios", type="primary", use_container_width=True
        ):
            try:
                repository.sincronizar_cambios(df_editado, df_filtrado)
                st.session_state["mensaje_exito"] = "Inventario actualizado correctamente."
                st.cache_data.clear()
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                mostrar_error(exc)


if __name__ == "__main__":
    main()