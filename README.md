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

## Acceso con huella o passkey

1. Abre la app desde el teléfono e inicia sesión con correo y contraseña.
2. En **Acceso biométrico**, elige **Añadir passkey a este dispositivo** y confirma con la huella, el rostro o el PIN que solicite el sistema.
3. En próximos accesos, escribe el correo, elige **Preparar inicio biométrico** y confirma con la passkey del navegador.

La huella nunca se envía ni se guarda en la app. El dispositivo crea y conserva una clave privada; SQLite guarda solo la clave pública necesaria para verificar los accesos. El navegador puede ofrecer huella, reconocimiento facial, PIN o una passkey sincronizada. La contraseña sigue disponible como alternativa.

Las passkeys requieren un origen HTTPS válido; `http://localhost` solo se permite para desarrollo. Streamlit Community Cloud proporciona HTTPS. Registra la passkey desde el mismo dominio que usarás luego, porque WebAuthn la vincula al dominio de la app.

Si Streamlit está detrás de un proxy y no detecta correctamente la URL pública, configura `PASSKEY_APP_URL` con el origen HTTPS exacto, por ejemplo `https://inventario.ejemplo.com`. No incluyas rutas ni una barra final. En pruebas locales se permite `http://localhost:8501`.

## Mantener la sesión iniciada

La app recuerda el acceso en el mismo navegador/dispositivo hasta que el usuario elija **Cerrar sesión**. El navegador conserva un token aleatorio; la base de datos conserva únicamente el hash y lo revoca al cerrar sesión. No se guarda la contraseña ni información biométrica en el navegador. Si se borran sus datos, se cambia de navegador o se usa otro teléfono, habrá que iniciar sesión nuevamente.

## Despliegue

Puedes desplegarla en Streamlit Community Cloud desde GitHub, seleccionando `app.py` como archivo principal. No requiere Secrets ni credenciales de servicios externos.

**Importante:** el archivo SQLite vive en el sistema de archivos local de la instancia. Streamlit Community Cloud no garantiza que esos datos sobrevivan reinicios, recreación de la instancia o redespliegues. No uses esta modalidad para inventario persistente sin una estrategia externa de almacenamiento/backup. Para conservar una base SQLite, ejecuta la app en un servidor o contenedor con un volumen persistente y configura `INVENTORY_DB_PATH` apuntando a ese volumen. No compartas un archivo SQLite entre varias instancias de la app.

La base crea automáticamente las tablas `usuarios` y `articulos`, activa claves foráneas y crea índices para búsquedas por usuario y categoría.