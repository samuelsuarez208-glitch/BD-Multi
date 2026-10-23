import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd


CATEGORIAS = ["Comida", "Ropa", "Electrodomésticos", "Otros"]
COLUMNAS_INVENTARIO = ["id", "nombre", "categoria", "precio", "cantidad"]
ITERACIONES_PASSWORD = 600_000


class InventoryRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.db_path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        password_hash BLOB NOT NULL,
                        password_salt BLOB NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS articulos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        nombre TEXT NOT NULL COLLATE NOCASE,
                        categoria TEXT NOT NULL,
                        precio REAL NOT NULL CHECK (precio >= 0),
                        cantidad INTEGER NOT NULL CHECK (cantidad >= 0),
                        FOREIGN KEY (user_id) REFERENCES usuarios (id)
                            ON DELETE CASCADE,
                        UNIQUE (user_id, nombre)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_articulos_usuario_categoria
                    ON articulos (user_id, categoria)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_articulos_usuario_nombre
                    ON articulos (user_id, nombre)
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS passkeys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        credential_id BLOB NOT NULL UNIQUE,
                        public_key BLOB NOT NULL,
                        sign_count INTEGER NOT NULL DEFAULT 0,
                        transports TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES usuarios (id)
                            ON DELETE CASCADE
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_passkeys_usuario
                    ON passkeys (user_id)
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sesiones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        token_hash BLOB NOT NULL UNIQUE,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES usuarios (id)
                            ON DELETE CASCADE
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sesiones_token_hash
                    ON sesiones (token_hash)
                    """
                )

    @staticmethod
    def _normalizar_email(email: str) -> str:
        email_normalizado = email.strip().lower()
        if (
            len(email_normalizado) > 254
            or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email_normalizado) is None
        ):
            raise ValueError("Escribe un correo electrónico válido.")
        return email_normalizado

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, ITERACIONES_PASSWORD
        )

    def registrar_usuario(self, email: str, password: str) -> dict[str, int | str]:
        email_normalizado = self._normalizar_email(email)
        if len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")

        salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt)
        try:
            with self._connection() as connection:
                with closing(connection.cursor()) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO usuarios (email, password_hash, password_salt)
                        VALUES (?, ?, ?)
                        """,
                        (email_normalizado, password_hash, salt),
                    )
                    user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe una cuenta con ese correo.") from exc

        return {"id": int(user_id), "email": email_normalizado}

    def autenticar_usuario(
        self, email: str, password: str
    ) -> dict[str, int | str] | None:
        try:
            email_normalizado = self._normalizar_email(email)
        except ValueError:
            return None

        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT id, email, password_hash, password_salt
                    FROM usuarios
                    WHERE email = ?
                    """,
                    (email_normalizado,),
                )
                usuario = cursor.fetchone()

        if usuario is None:
            return None

        password_hash = self._hash_password(password, usuario["password_salt"])
        if not hmac.compare_digest(password_hash, usuario["password_hash"]):
            return None

        return {"id": int(usuario["id"]), "email": usuario["email"]}

    def crear_sesion_persistente(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    "INSERT INTO sesiones (user_id, token_hash) VALUES (?, ?)",
                    (user_id, token_hash),
                )
        return token

    def autenticar_sesion_persistente(
        self, token: str
    ) -> dict[str, int | str] | None:
        if not token or len(token) > 256:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT usuarios.id, usuarios.email
                    FROM sesiones
                    JOIN usuarios ON usuarios.id = sesiones.user_id
                    WHERE sesiones.token_hash = ?
                    """,
                    (token_hash,),
                )
                user = cursor.fetchone()
        if user is None:
            return None
        return {"id": int(user["id"]), "email": user["email"]}

    def cerrar_sesion_persistente(self, token: str) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    "DELETE FROM sesiones WHERE token_hash = ?", (token_hash,)
                )

    def obtener_passkeys(self, user_id: int) -> list[dict]:
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT credential_id, public_key, sign_count, transports
                    FROM passkeys
                    WHERE user_id = ?
                    ORDER BY id
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        return [
            {
                "credential_id": bytes(row["credential_id"]),
                "public_key": bytes(row["public_key"]),
                "sign_count": int(row["sign_count"]),
                "transports": json.loads(row["transports"]),
            }
            for row in rows
        ]

    def obtener_passkey_por_email(
        self, email: str, credential_id: bytes
    ) -> dict | None:
        try:
            email_normalizado = self._normalizar_email(email)
        except ValueError:
            return None

        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT usuarios.id AS user_id, usuarios.email,
                           passkeys.credential_id, passkeys.public_key,
                           passkeys.sign_count
                    FROM usuarios
                    JOIN passkeys ON passkeys.user_id = usuarios.id
                    WHERE usuarios.email = ? AND passkeys.credential_id = ?
                    """,
                    (email_normalizado, credential_id),
                )
                row = cursor.fetchone()

        if row is None:
            return None
        return {
            "user_id": int(row["user_id"]),
            "email": row["email"],
            "credential_id": bytes(row["credential_id"]),
            "public_key": bytes(row["public_key"]),
            "sign_count": int(row["sign_count"]),
        }

    def obtener_usuario_y_passkeys(self, email: str) -> dict | None:
        try:
            email_normalizado = self._normalizar_email(email)
        except ValueError:
            return None

        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT usuarios.id AS user_id, usuarios.email,
                           passkeys.credential_id, passkeys.transports
                    FROM usuarios
                    LEFT JOIN passkeys ON passkeys.user_id = usuarios.id
                    WHERE usuarios.email = ?
                    ORDER BY passkeys.id
                    """,
                    (email_normalizado,),
                )
                rows = cursor.fetchall()

        if not rows:
            return None
        return {
            "user_id": int(rows[0]["user_id"]),
            "email": rows[0]["email"],
            "passkeys": [
                {
                    "credential_id": bytes(row["credential_id"]),
                    "transports": json.loads(row["transports"]),
                }
                for row in rows
                if row["credential_id"] is not None
            ],
        }

    def guardar_passkey(
        self,
        user_id: int,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int,
        transports: list[str],
    ) -> None:
        try:
            with self._connection() as connection:
                with closing(connection.cursor()) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO passkeys
                            (user_id, credential_id, public_key, sign_count, transports)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            credential_id,
                            public_key,
                            sign_count,
                            json.dumps(transports),
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Esta passkey ya está registrada en una cuenta.") from exc

    def actualizar_contador_passkey(
        self, user_id: int, credential_id: bytes, sign_count: int
    ) -> None:
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    UPDATE passkeys
                    SET sign_count = ?
                    WHERE user_id = ? AND credential_id = ?
                    """,
                    (sign_count, user_id, credential_id),
                )
                if cursor.rowcount != 1:
                    raise LookupError("La passkey no está registrada en esta cuenta.")

    def obtener_inventario(self, user_id: int) -> pd.DataFrame:
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT id, nombre, categoria, precio, cantidad
                    FROM articulos
                    WHERE user_id = ?
                    ORDER BY id
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame(columns=COLUMNAS_INVENTARIO)
        df = pd.DataFrame([dict(row) for row in rows], columns=COLUMNAS_INVENTARIO)
        df["nombre"] = df["nombre"].str.capitalize()
        return df

    def agregar_o_incrementar(
        self, user_id: int, nombre: str, categoria: str, precio: float, cantidad: int
    ) -> None:
        nombre_normalizado = nombre.strip().lower()
        if not nombre_normalizado:
            raise ValueError("Escribe un nombre de producto.")
        if categoria not in CATEGORIAS:
            raise ValueError("Selecciona una categoría válida.")
        if precio < 0 or cantidad < 1:
            raise ValueError("El precio o la cantidad no son válidos.")

        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT id, cantidad
                    FROM articulos
                    WHERE user_id = ? AND nombre = ?
                    """,
                    (user_id, nombre_normalizado),
                )
                articulo = cursor.fetchone()
                if articulo:
                    cursor.execute(
                        """
                        UPDATE articulos
                        SET cantidad = ?, precio = ?, categoria = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        (
                            int(articulo["cantidad"]) + cantidad,
                            precio,
                            categoria,
                            articulo["id"],
                            user_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO articulos
                            (user_id, nombre, categoria, precio, cantidad)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, nombre_normalizado, categoria, precio, cantidad),
                    )

    def retirar_stock(self, user_id: int, nombre: str, cantidad: int) -> int:
        nombre_normalizado = nombre.strip().lower()
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT id, cantidad
                    FROM articulos
                    WHERE user_id = ? AND nombre = ?
                    """,
                    (user_id, nombre_normalizado),
                )
                articulo = cursor.fetchone()
                if articulo is None:
                    raise LookupError(f"'{nombre}' no existe en tu inventario.")

                stock_actual = int(articulo["cantidad"])
                if cantidad < 1 or stock_actual < cantidad:
                    raise ValueError(f"Solo quedan {stock_actual} unidades.")

                stock_nuevo = stock_actual - cantidad
                cursor.execute(
                    """
                    UPDATE articulos
                    SET cantidad = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (stock_nuevo, articulo["id"], user_id),
                )
                return stock_nuevo

    def sincronizar_cambios(
        self, user_id: int, df_editado: pd.DataFrame, df_visible_original: pd.DataFrame
    ) -> None:
        ids_visibles = {
            int(value) for value in df_visible_original["id"].dropna()
        }
        ids_editados: set[int] = set()
        nombres_editados: set[str] = set()
        actualizaciones = []
        inserciones = []

        for _, fila in df_editado.iterrows():
            nombre_value = fila.get("nombre")
            nombre = (
                "" if pd.isna(nombre_value) else str(nombre_value).strip().lower()
            )
            if not nombre:
                raise ValueError("Todos los productos deben tener un nombre.")
            if nombre in nombres_editados:
                raise ValueError(f"El producto '{nombre}' está duplicado.")
            nombres_editados.add(nombre)

            categoria = fila.get("categoria")
            if pd.isna(categoria) or categoria not in CATEGORIAS:
                raise ValueError(f"Categoría no válida para '{nombre}'.")

            try:
                precio = float(fila.get("precio"))
                cantidad_num = float(fila.get("cantidad"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Precio o cantidad no válidos para '{nombre}'.") from exc

            if not math.isfinite(precio) or precio < 0:
                raise ValueError(f"El precio de '{nombre}' debe ser no negativo.")
            if (
                not math.isfinite(cantidad_num)
                or cantidad_num < 0
                or not cantidad_num.is_integer()
            ):
                raise ValueError(f"La cantidad de '{nombre}' debe ser un entero no negativo.")

            datos = (nombre, categoria, precio, int(cantidad_num))
            id_value = fila.get("id")
            if pd.notna(id_value):
                articulo_id = int(id_value)
                if articulo_id not in ids_visibles:
                    raise ValueError("ID de producto no válido para esta tabla.")
                if articulo_id in ids_editados:
                    raise ValueError("Hay IDs duplicados en la tabla editada.")
                ids_editados.add(articulo_id)
                actualizaciones.append((*datos, articulo_id, user_id))
            else:
                inserciones.append((user_id, *datos))

        ids_a_eliminar = ids_visibles - ids_editados
        with self._connection() as connection:
            with closing(connection.cursor()) as cursor:
                if ids_a_eliminar:
                    cursor.executemany(
                        "DELETE FROM articulos WHERE id = ? AND user_id = ?",
                        [(articulo_id, user_id) for articulo_id in ids_a_eliminar],
                    )
                if actualizaciones:
                    cursor.executemany(
                        """
                        UPDATE articulos
                        SET nombre = ?, categoria = ?, precio = ?, cantidad = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        actualizaciones,
                    )
                if inserciones:
                    cursor.executemany(
                        """
                        INSERT INTO articulos
                            (user_id, nombre, categoria, precio, cantidad)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        inserciones,
                    )