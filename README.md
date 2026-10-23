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
- En Supabase, habilita el proveedor **Authentication > Sign In / Providers > Email**. Si está activa la confirmación de correo, el usuario deberá confirmarlo antes de iniciar sesión.
- Activa RLS en `public.articulos` y crea una política que permita operaciones solo a usuarios autenticados. Para un inventario compartido por todas las cuentas registradas, puedes usar:

	```sql
	alter table public.articulos enable row level security;

	drop policy if exists "inventory for authenticated users" on public.articulos;
	create policy "inventory for authenticated users"
	on public.articulos
	for all
	to authenticated
	using (true)
	with check (true);
	```

- Ese ejemplo hace que todas las cuentas registradas compartan el mismo inventario. Para inventarios privados por usuario, la tabla necesita una columna `user_id` y políticas basadas en `auth.uid()`; este código todavía no implementa esa separación.
- Revisa y elimina políticas antiguas que concedan acceso a `anon`; la pantalla de login no sustituye las políticas RLS.

La tabla `articulos` debe tener, como mínimo, las columnas `id`, `nombre`, `categoria`, `precio` y `cantidad`. El nombre debe ser único si se requiere impedir duplicados.