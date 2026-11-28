# =============================================================================
# Dockerfile del backend
#
# Que es y que no es (ADR-07, ARQUITECTURA.md seccion 9.1):
#
# - **Vercel no ejecuta este Dockerfile en produccion.** El runtime de Python de
#   Vercel compila desde el codigo fuente. La produccion v1 es Vercel + Supabase.
# - Este Dockerfile existe para dos cosas concretas:
#   1. **Entorno local reproducible**, identico al de produccion, sin depender de
#      que el desarrollador tenga Python 3.14.10 y las dependencias bien instaladas.
#   2. **Camino de salida a servidor privado ya escrito.** Si manana se anade el
#      modo hospedado (el worker ETL con LLM en el nivel 4), la imagen ya existe y
#      ya esta probada.
#
# La imagen no lleva el codigo de la base de datos ni los secretos: el backend se
# conecta a Supabase por HTTP (ADR-04), asi que solo necesita las variables de
# entorno.
#
# -----------------------------------------------------------------------------
# OPTIMIZACIONES Y POR QUE
#
# - **Multi-stage**: la etapa de dependencias lleva el compilador y las cabeceras
#   que `uv` necesita para resolver paquetes con codigo nativo. La etapa final
#   no lleva nada de eso.
# - **`uv` no esta en la imagen final**: pesa 43,8 MB y en runtime no se usa para
#   nada. Solo hace falta durante la construccion.
# - **El cache de `uv` se borra despues de instalar**: son los paquetes
#   descargados, que ya quedaron instalados en el `.venv`. Sin esto, la imagen
#   lleva dos copias de lo mismo.
# - **Cache de capas por directorio**: los archivos se copian de menos a mas
#   cambiante. `pyproject.toml` cambia una vez al trimestre; `app/` cambia todos
#   los dias. Si se copiara el codigo primero, cambiar una linea invalidaria la
#   capa de dependencias y habria que reinstalar todo.
# - **Copia con `--chown` de una vez**: los archivos llegan con el usuario
#   correcto sin un `chown` recursivo despues, que es una operacion extra sobre
#   cada archivo de la imagen.
# - **Sin `--no-cache` en el `uv sync`**: `uv` solo descarga lo que falta.
# - **Un solo `COPY` por grupo**: cada `COPY` es una capa del historial. Menos
#   capas, menos metadatos que guardar.
# - **Usuario sin privilegios**: el proceso no corre como `root`. Si un proceso se
#   compromise, el atacante no gana tambien el sistema de archivos.
#
# Lo que **no** se optimiza, y por que: el `.venv` pesa 124 MB, y casi todo es
# transitive del SDK de Supabase (`opentelemetry`, `sentry_sdk`, `google`, `rich`,
# `pygments`, `uvloop`, `cryptography`). Quitar esas paquetes obligaria a
# recortar el SDK, y el SDK es una dependencia directa del proyecto (ADR-05).
# Un recorte del tamano de la imagen no puede costar una funcionalidad.
# =============================================================================

# -----------------------------------------------------------------------------
# Etapa 1: las dependencias
#
# Se resuelven y se instalan **antes** de copiar el codigo. Asi la capa de
# dependencias se reutiliza en cada cambio de codigo.
# -----------------------------------------------------------------------------
FROM python:3.14.10-slim AS deps

# `uv` instala y resuelve las dependencias. Se fija la version exacta: una
# herramienta que se mueve sola cambia el resultado sin que nadie lo decida.
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Solo los archivos de dependencias: la capa se invalida unicamente cuando
# cambian las pins, no cuando cambia el codigo.
#
# El `uv.lock` es obligatorio, no opcional: `uv sync --frozen` se niega a instalar
# sin el. Sin el, la imagen resolveria las dependencias en el momento de construir,
# y dos construcciones en dias distintos podrian instalar versiones distintas.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev \
    && uv cache clean --force

# -----------------------------------------------------------------------------
# Etapa 2: la aplicacion
# -----------------------------------------------------------------------------
FROM python:3.14.10-slim AS runtime

# El usuario del sistema. La imagen no corre como `root`: si un proceso se
# compromise, el atacante no gana tambien el sistema de archivos.
RUN groupadd --system --gid 1001 riskapp \
    && useradd --system --uid 1001 --gid riskapp --create-home riskapp

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Las dependencias primero: misma razon que en la etapa anterior. Se copian desde
# la etapa de deps, con `--chown` para que ya queden con el usuario correcto.
COPY --from=deps --chown=riskapp:riskapp /app/.venv /app/.venv

# Despues el codigo, tambien con `--chown`: los archivos llegan con el
# propietario definitivo y no hace falta un `chown` recursivo despues.
COPY --chown=riskapp:riskapp app/ ./app/
COPY --chown=riskapp:riskapp scripts/ ./scripts/
COPY --chown=riskapp:riskapp api/ ./api/

USER riskapp

EXPOSE 8000

# La comprobacion de salud es la misma que usa el despliegue: si la API no
# responde, el contenedor no esta listo.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/health').status_code==200 else 1)"

# `uvicorn` con `--host 0.0.0.0` porque dentro del contenedor la app no escucha en
# localhost: si lo hiciera, el puerto publicado no llegaria.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
