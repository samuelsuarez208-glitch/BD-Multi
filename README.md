# Sistema de inventario

Aplicación de inventario con Streamlit y SQLite. El punto de entrada es `app.py`; el acceso a datos está separado en `database.py`.

## Ejecución local

1. Instala Python 3.10 o superior.
2. Crea un entorno virtual e instala las dependencias:

	```bash
	python -m venv .venv
	source .venv/bin/activate
	python -m pip install -r requirements.txt
	```

3. Inicia la aplicación:

	```bash
	streamlit run app.py
	```

La base `inventory.db` se crea junto a `app.py`. Para guardarla en otra ubicación, define `INVENTORY_DB_PATH` antes de iniciar Streamlit. Las cuentas tienen inventarios separados. Las contraseñas se almacenan como hashes PBKDF2 con salt aleatorio, no como texto plano.

## Despliegue

Puedes desplegarla en Streamlit Community Cloud desde GitHub, seleccionando `app.py` como archivo principal. No requiere Secrets ni credenciales de servicios externos.

**Importante:** el archivo SQLite vive en el sistema de archivos local de la instancia. Streamlit Community Cloud no garantiza que esos datos sobrevivan reinicios, recreación de la instancia o redespliegues. No uses esta modalidad para inventario persistente sin una estrategia externa de almacenamiento/backup. Para conservar una base SQLite, ejecuta la app en un servidor o contenedor con un volumen persistente y configura `INVENTORY_DB_PATH` apuntando a ese volumen. No compartas un archivo SQLite entre varias instancias de la app.

La base crea automáticamente las tablas `usuarios` y `articulos`, activa claves foráneas y crea índices para búsquedas por usuario y categoría.