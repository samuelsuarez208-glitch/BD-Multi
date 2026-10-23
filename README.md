# Sistema de inventario

Aplicación de inventario con Streamlit y Supabase. El punto de entrada para el despliegue es `app.py`.

## Ejecución local

1. Instala Python 3.10 o superior.
2. Crea un entorno virtual e instala las dependencias:

	```bash
	python -m venv .venv
	source .venv/bin/activate
	python -m pip install -r requirements.txt
	```

3. Crea `.streamlit/secrets.toml` con las credenciales de tu proyecto:

	```toml
	SUPABASE_URL = "https://tu-proyecto.supabase.co"
	SUPABASE_KEY = "tu-clave-publishable-o-anon"
	```

4. Inicia la aplicación:

	```bash
	streamlit run app.py
	```

## Despliegue en Streamlit Community Cloud

1. Sube este proyecto a un repositorio de GitHub. No subas `.streamlit/secrets.toml` ni claves de Supabase.
2. En [share.streamlit.io](https://share.streamlit.io/), inicia sesión y elige **Create app**.
3. Selecciona el repositorio, la rama que quieras desplegar y `app.py` como **Main file path**.
4. En **Advanced settings**, agrega los Secrets con formato TOML:

	```toml
	SUPABASE_URL = "https://tu-proyecto.supabase.co"
	SUPABASE_KEY = "tu-clave-publishable-o-anon"
	```

5. Despliega la aplicación. Streamlit instalará las librerías declaradas en `requirements.txt`.

## Seguridad de Supabase

- Usa una clave publishable o `anon`, nunca la clave `service_role` en una aplicación cliente.
- Configura RLS y políticas en la tabla `articulos` según quién debe poder leer y modificar el inventario. La clave publishable por sí sola no autentica a cada visitante.
- La aplicación actual no incluye inicio de sesión de usuarios. Si se despliega públicamente, cualquiera que pueda abrirla podría intentar modificar los datos permitidos por las políticas RLS. Añade autenticación antes de usarla con datos sensibles o en producción.

La tabla `articulos` debe tener, como mínimo, las columnas `id`, `nombre`, `categoria`, `precio` y `cantidad`. El nombre debe ser único si se requiere impedir duplicados.