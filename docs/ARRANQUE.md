# Arranque local

Como se levanta Risk-app en una maquina nueva. El detalle de **que** es el producto
esta en [CONTEXTO.md](CONTEXTO.md); el de **como** esta en
[ARQUITECTURA.md](ARQUITECTURA.md).

---

## 1. Requisitos

| Herramienta | Version | Nota |
|---|---|---|
| Python | 3.14.10 | **No 3.15.** Vercel no lo ofrece todavia (ADR-28) |
| `uv` | 0.13 o superior | Gestor de dependencias del backend |
| Node.js | 24 o 26 (LTS) | El piso real lo impone `@supabase/supabase-js`: `>= 22` |
| npm | 11 o superior | |
| Supabase CLI | 3.4.0 | Rama v3. Unica herramienta de migraciones (ADR-32) |
| Docker | Actual | Para `supabase start` |

El navegador del modo local exige **WebGPU**: Chrome y Edge 113+, Firefox 141+ en
Windows, Safari 26 en macOS Tahoe 26 / iOS 26.

---

## 2. Backend

```bash
cd backend

# Configuracion local. El `.env` nunca se versiona.
cp .env.example .env
# Edita .env y pega URL y llaves de tu proyecto de Supabase.

uv sync                  # instala dependencias y crea el .venv
uv run python -m uvicorn app.main:app --reload
```

La API queda en `http://localhost:8000` y la documentacion interactiva en
`http://localhost:8000/docs`.

**El arranque falla si falta una variable obligatoria.** Es intentional: una
configuracion incompleta que arranca es peor que una que se niega a arrancar,
porque el fallo aparece en produccion y no en el desarrollo.

### Comandos de verificacion del backend

```bash
uv run pytest              # suite completa
uv run pytest -m unit      # solo unitarias, sin base de datos
uv run ruff check .        # lint
uv run ruff format .       # formato
uv run mypy app            # tipos
uv run lint-imports        # contratos de la frontera hexagonal
```

`lint-imports` es el que verifica la invariante: el `domain/` no importa nada de
`application/`, `adapters/` ni de ningun framework. Una violacion rompe la
integracion continua antes de que rompa la revision.

---

## 3. Frontend

```bash
cd frontend

cp .env.example .env      # Edita con los mismos datos del backend.

npm install --legacy-peer-deps
npm run dev
```

La aplicacion queda en `http://localhost:5173`.

### Por que `--legacy-peer-deps`

`openapi-typescript` declara `peer typescript: ^5.x` y el proyecto usa
**TypeScript 6.0.3** (ADR-28: TypeScript 7 no expone la API de JavaScript que
necesitan `vue-tsc` y `typescript-eslint`). Ninguna version de `openapi-typescript`
admite TypeScript 6 todavia.

La herramienta solo genera un archivo de tipos a partir del OpenAPI: no participa
en el build ni en los tests. El `override` en `package.json` le fija la version del
proyecto, y el flag acepta la incompatibilidad declarada. Si `openapi-typescript`
publica soporte para TypeScript 6, se quita el flag y el `override`.

### Comandos de verificacion

```bash
npm run typecheck   # vue-tsc sobre los .vue
npm run build       # typecheck + build de produccion
npm run test        # vitest
npm run lint        # eslint
npm run api:types   # regenera src/api/types.ts desde el OpenAPI del backend
```

**Un build no valida los tests.** `npm run build` compila las fuentes de
produccion; los tests se corren aparte.

### `npm run api:types` todavia no funciona

El script genera `src/api/types.ts` desde el OpenAPI del backend:

```
npm run api:types    # lee backend/tests/contract/openapi.json
```

Ese archivo **aun no existe**: el snapshot de OpenAPI se genera cuando haya el primer
endpoint. hasta entonces el comando falla, y es lo esperado. No es un error de
configuracion.

El archivo generado se versiona a proposito: un cambio de contrato se ve en el diff y
no aparece solo en el momento de compilar.

---

## 4. Base de datos local

```bash
supabase start          # Postgres + Auth + PostgREST + Storage en local
supabase db reset       # aplica las migraciones de supabase/migrations/
```

Las migraciones son **SQL puro** en `supabase/migrations/` y las aplica el CLI de
Supabase. No hay Alembic ni tabla `alembic_version` (ADR-32). El esquema nunca se
edita a mano: cada cambio es una migracion nueva.

Las que existen hoy:

| Archivo | Que deja |
|---|---|
| `001_esquema_inicial.sql` | Las 16 tablas, sus indices y sus claves foraneas |
| `002_rls.sql` | RLS activo en las 17 tablas, y las funciones de apoyo del esquema `security` (ADR-35) |
| `003_permisos_y_roles.sql` | Los 3 roles, los 14 permisos y la matriz `rol_permisos` |
| `004_bucket_y_storage.sql` | El bucket privado `documentos` y las politicas sobre `storage.objects` |
| `005_funciones_rpc.sql` | Las funciones de atomicidad: `guardar_analisis`, `registrar_actividad`, `actualizar_trabajo`, `mis_permisos`, `revocar_sesion` |

Ademas, `supabase/seed.sql` siembra la **plantilla generica v1** (plantilla del
sistema, visible para todos). No siembra usuarios ni organizaciones: el primer
administrador lo crea el script de bootstrap.

> `supabase db reset` **borra** los datos de la base local. Es lo esperado: rehace
> el esquema desde cero.

> **El esquema `security`.** Las politicas de RLS no pueden consultarse entre si: la
> de `documentos` llama a la de `documentos_compartidos`, que vuelve a consultar
> `documentos`, y Postgres aborta con "infinite recursion detected". Por eso las
> funciones de apoyo viven en el esquema `security` y leen con
> `set row_security = off`. El detalle esta en `ARQUITECTURA.md` seccion 5.2 y en el
> ADR-35. **Si anades una politica, no la escribas con un `exists` sobre otra tabla
> que tenga RLS: usa una funcion de `security`.**

Las variables del `.env` para la base local:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<la que imprime `supabase start`>
SUPABASE_SERVICE_ROLE_KEY=<la que imprime `supabase start`>
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
```

### Lo que cambia en el proyecto de Supabase en la nube

La base local tiene ajustes de desarrollo que **no** se replican tal cual:

| Ajuste | Local | Nube | Por que |
|---|---|---|---|
| Confirmacion de correo | `enable_confirmations = false` | **Activada** | En local el correo se lee en el log (`inbucket`). En la nube llega al buzon real |
| Correo de confirmacion al registrarse | No | **Si** | Es la unica prueba de que la direccion existe |
| Cuentas creadas por la app | Con correo confirmado | Con correo confirmado | `[DECIDIDO]` en HU-03 §5: `email_confirm = true` |

> **El correo se confirma siempre en las cuentas creadas por la app**, en local y en la
> nube. La credencial temporal se envia junto con la confirmacion. Sin confirmar, el
> `signInWithPassword` responde "Email not confirmed" y el usuario no puede entrar.

La llave de servicio (`service_role`) nunca va en el frontend: viaja solo en las
variables de entorno del backend.

---

## 5. El primer administrador

El proyecto arranca sin usuarios. El primer admin se crea con el script de bootstrap,
que es **idempotente**: si el correo ya existe, no falla ni duplica.

```bash
cd backend
uv run python -m scripts.bootstrap_admin --correo admin@ejemplo.com --organizacion "<nombre>"
```

El script usa la llave de servicio: es el unico lugar del backend, junto al adaptador de
administracion de usuarios, que puede usar `service_role`.

Lo que hace, en orden:

1. Crea el usuario en Supabase Auth, con el correo ya confirmado.
2. Registra el perfil con rol `admin` y `debe_cambiar_contrasena = true`.
3. Crea la organizacion, o la reutiliza si ya existe con ese nombre.
4. Registra la membresia: `organizaciones_miembros` con rol `admin`.

El paso 4 es el que no se puede saltar. El aislamiento se resuelve desde las
membresias (ADR-33): sin esa fila, el administrador no pertenece a ninguna
organizacion y no ve nada.

Es **idempotente**: si el correo ya existe, actualiza el usuario en vez de duplicarlo.
Verificado el 2026-11-28 contra el stack local.

> **Detalle de la API de administracion.** La API de Supabase **no** filtra usuarios
> por correo: `GET /auth/v1/admin/users?filter=email.eq....` devuelve una lista
> vacia aunque el usuario exista. El script lista las paginas y filtra en el cliente.
> Es un detalle que no se adivina: sale de un `email_exists` en la segunda
> ejecucion.

Para fijar la contrasena a mano (por ejemplo, en una prueba automatizada):

```bash
uv run python -m scripts.bootstrap_admin \
    --correo admin@ejemplo.com \
    --organizacion "<nombre>" \
    --contrasena "<clave>"
```

Sin `--contrasena`, se genera una contrasena temporal de 20 caracteres y se imprime
al final de la ejecucion.

---

## 6. Orden de trabajo

El proyecto es incremental y cada capa se apoya en la anterior:

| # | Bloque | Estado | Gates que lo cubren |
|---|---|---|---|
| 1 | **Esqueleto**: estructura, configuracion, dependencias | **Hecho** | Gate 14 |
| 2 | **Migracion**: esquema, RLS, matriz de permisos y bucket, contra una base vacia | Siguiente | Gate 1, 2, 3.1, 3.4 |
| 3 | **Contratos**: envelope, codigos de estado, paginacion y OpenAPI | Pendiente | Gate 5, 9 |
| 4 | **Adaptadores**: Supabase, almacenamiento, correo | Pendiente | Gate 3, 4 |
| 5 | **Casos de uso**: permisos, transacciones, auditoria | Pendiente | Gate 3.1, 3.2, 4 |
| 6 | **Frontend**: sesion, documentos, motor, pipeline en el navegador | Pendiente | Gate 7 |
| 7 | **Pruebas**: unitarias, de integracion contra Supabase real y de contrato | En curso | Gate 8 |
| 8 | **Fase 2**: ciclo de vida del riesgo, exportacion y correo | **Aplazada** | Gate 13 |

El pipeline de la v1 corre **en el navegador**: el backend persiste resultados
validados, no ejecuta el modelo (ADR-06).

### Que es la fase 2

La v1 entrega el **analisis**: extrae, consolida y persiste. La fase 2 es la que hace
que el resultado **se gestione**: estado, responsable, fecha objetivo, decision de
aceptacion e historial.

Esta **aplazada**, no descartada, y el trabajo para que sea posible ya esta hecho: el
contrato del resultado (`docs/CONTRATO-RESULTADO-ANALISIS.md`) fija la forma de cada
riesgo con un envoltorio nuestro y un contenido de la plantilla. Lo que falta es la
**decision del cliente** sobre si el resultado se gestiona o es solo una consulta
(**PP-15**).

Todo lo que esa fase necesita esta escrito en el **Gate 13** del `CHECKLIST.md`: el
modelo de datos, las reglas de negocio, la integracion con lo ya construido, la
exportacion y el correo. Las reglas de negocio de ahi salen del analisis del prototipo
de referencia (`docs/ANALISIS-REFERENCIA-VULNERABILITY-TRACKER.md`).
