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

### Los dos `.env` y el de Supabase

Hay **tres** lugares donde viven las claves, y se confunden con facilidad:

| Archivo | Para que | Se versiona |
|---|---|---|
| `backend/.env` | La API: URL y llaves de Supabase | **No.** Esta en `.gitignore` |
| `frontend/.env` | El navegador: la URL y la llave publicable | **No** |
| `supabase/` (el CLI) | La base local que levanta el CLI | El codigo si; las llaves no |

**Supabase no usa "un `.env` propio": el CLI de Supabase administra el suyo.** El
stack local (`supabase start`) tiene sus propias llaves, y estan en la salida del
comando:

```
supabase start
# API URL: http://127.0.0.1:54321
# Publishable key: sb_publishable_...
# Secret key: sb_secret_...
```

El `backend/.env` apunta a **esa** API local mientras se desarrolla en local:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=sb_publishable_...        # la llave que imprime `supabase start`
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...      # la llave que imprime `supabase start`
```

### `SUPABASE_JWT_ISSUER`: la URL de conexion y la URL publica no son lo mismo

Supabase emite los tokens en `{URL_PUBLICA}/auth/v1`, y el backend comprueba que el
token venga de ahi. **La URL publica del proyecto no siempre es la misma que la de
conexion**, y en local con el backend en Docker no lo es:

| | URL de conexion (`SUPABASE_URL`) | URL publica (lo que va en el token) |
|---|---|---|
| Backend en el host | `http://127.0.0.1:54321` | `http://127.0.0.1:54321` |
| Backend en Docker | `http://host.docker.internal:54321` | `http://127.0.0.1:54321` |
| En la nube | `https://<ref>.supabase.co` | `https://<ref>.supabase.co` |

El token lo emite **el navegador**, y el navegador no conoce `host.docker.internal`.
Si el backend espera el emisor de su propia URL de conexion, **todo token valido se
rechaza** con `InvalidIssuerError` y el login falla con 401.

Por eso el emisor se puede fijar aparte:

```
SUPABASE_JWT_ISSUER=http://127.0.0.1:54321/auth/v1
```

Si no se define, se deriva de `SUPABASE_URL`, que es lo correcto cuando ambas
coinciden (la nube). El compose del backend lo define con el valor de arriba.

Cuando se trabaja contra el **proyecto en la nube**, cambian las dos llaves por las
del panel de Supabase (`Project Settings -> API`), y la URL pasa a
`https://<project-ref>.supabase.co`.

**Que NO hay que hacer:** poner las llaves de la nube en un archivo versionado, ni
copiar el `.env` de la nube sobre el del stack local sin avisar. Son dos entornos
distintos, con dos conjuntos de datos distintos.

> **Nomenclatura.** Supabase renombro la `anon key` a **publishable key**. El panel
> muestra `sb_publishable_...` y `sb_secret_...`. El proyecto las llama
> `SUPABASE_ANON_KEY` y `SUPABASE_SERVICE_ROLE_KEY` porque el SDK de Python las
> nombra asi, y porque el nombre "anon" todavia aparece en la documentacion vieja.
> `sb_publishable_` va en el frontend; `sb_secret_` **nunca**.

> **Las dos llaves del stack local y las de la nube son distintas**, aunque el
> nombre se parezca. El stack local genera las suyas al arrancar; la nube tiene las
> suyas en el panel. Un `.env` con las de la nube apuntando a
> `http://127.0.0.1:54321` no funciona, y al reves tampoco.

> **La diferencia entre las dos llaves de la nube.** La `anon` (hoy `publishable`)
> es la que viaja al navegador y la que aplica las politicas de RLS: el RLS es lo
> que protege los datos. La `service_role` salta el RLS, asi que **nunca** va al
> navegador ni a un `.env` del frontend. El backend la usa solo en el adaptador de
> administracion (ADR-13).

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

Tambien se puede levantar en Docker, con dos perfiles: `dev` (Vite, con recarga en
caliente) y `prod` (el bundle de produccion, servido por nginx). Ver la seccion 6.2.

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
| `006_advisor_supabase.sql` | Las correcciones que pidio el advisor oficial: indice en cada FK, `(select auth.uid())` en las politicas, y las politicas unificadas |
| `007_politicas_por_operacion.sql` | Cada politica `for all` partida en `for insert`, `for update` y `for delete` |
| `008_funciones_fuera_de_alcance_anon.sql` | Las funciones RPC fuera del alcance del rol `anon`, y `FORCE ROW LEVEL SECURITY` en las 17 tablas |
| `009_cerrar_funciones_al_rol_public.sql` | `EXECUTE` revocado al rol `public` en las funciones de apoyo y en las cinco RPC, y `USAGE` revocado al rol `public` en el esquema `security` |
| `010_funciones_rpc_en_public.sql` | Las cinco RPC de negocio vuelven a `public` con el ACL cerrado (ADR-37): `EXECUTE` solo para `authenticated` |
| `011_cerrar_esquema_security_al_rol_anon.sql` | `USAGE` y `EXECUTE` revocados a `anon` explicitamente en el esquema `security` y en sus nueve funciones de apoyo |

Ademas, `supabase/seed.sql` siembra la **plantilla generica v1** (plantilla del
sistema, visible para todos). No siembra usuarios ni organizaciones: el primer
administrador lo crea el script de bootstrap.

> `supabase db reset` **borra** los datos de la base local. Es lo esperado: rehace
> el esquema desde cero.

> **El advisor de Supabase.** `supabase db advisors` revisa la base con las mismas
> reglas que usa la plataforma. Sirve para comprobar que lo escrito aca es lo que
> Supabase espera, no solo lo que el proyecto espera:
>
> ```bash
> supabase db advisors --type all --level info
> ```
>
> La primera pasada dio 56 hallazgos (37 de `auth_rls_initplan`, 16 de
> `unindexed_foreign_keys`, 14 de `unused_index`, 7 de
> `multiple_permissive_policies`). Las migraciones 006 y 007 los corrigen. Quedan 29
> de nivel INFO: indices que el advisor no ve en uso porque la base esta vacia y el
> planificador no tiene datos para decidir. Ninguno se borra por eso.

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

### 7.2 Usuarios de prueba para validar a mano

Para recorrer la aplicacion a mano hacen falta usuarios de cada rol. El script
`backend/scripts/seed_usuarios.py` los siembra:

```bash
cd backend
uv run python -m scripts.seed_usuarios
uv run python -m scripts.seed_usuarios --contrasena "una-clave-fuerte"
```

Que crea:

| Correo | Que es | Que pasa al entrar |
|---|---|---|
| `admin@ejemplo.co` | Rol `admin` | Ve todo lo de la organizacion |
| `analista@ejemplo.co` | Rol `analista` | Ve lo del rol |
| `auditor@ejemplo.co` | Rol `auditor` | Solo lectura |
| `anonimo@ejemplo.co` | **Sin perfil** | La API responde `403` con el codigo `perfil_inexistente` |
| `inactivo@ejemplo.co` | Perfil con `activo = false` | La API responde `403`: la cuenta esta desactivada |

Los roles se **leen de la matriz** (`public.roles`), no estan escritos en el script:
si la matriz cambia, el seeder siembra lo que haya.

El "anonimo" es el caso de SP-07: entra en Supabase Auth, pero el backend no lo
reconoce porque no tiene fila en `perfiles`. El "inactivo" es el otro camino de
error: la cuenta existe, pero `activo = false` y el resolutor de permisos lo trata
como sin permisos.

Es **idempotente**: se puede volver a ejecutar y deja a los usuarios en el mismo
estado, con la contrasena que se indique. Los usuarios se crean con la **API de
administracion** de Supabase (`service_role`), nunca con un `insert` en
`auth.users`: por la misma razon que `supabase/seed.sql` no trae usuarios.

---

## 6. Docker

El `Dockerfile` del backend existe para dos cosas (ADR-07, `ARQUITECTURA.md`
seccion 9.1):

1. **Entorno local reproducible**, identico al de produccion, sin depender de que
   el desarrollador tenga Python 3.14.10 y las dependencias bien instaladas.
2. **Camino de salida a servidor privado ya escrito.** Si manana se anade el modo
   hospedado (el worker ETL con LLM), la imagen ya existe y ya esta probada.

> **Vercel no ejecuta este Dockerfile en produccion.** El runtime de Python de
> Vercel compila desde el codigo fuente. La produccion v1 es Vercel + Supabase.

### 6.1 Solo el backend

```bash
cd backend
docker build -t risk-app-backend .
docker run --rm -p 8000:8000 \
    -e SUPABASE_URL=http://127.0.0.1:54321 \
    -e SUPABASE_ANON_KEY=<clave> \
    -e SUPABASE_SERVICE_ROLE_KEY=<clave> \
    -e CORS_ORIGINS=http://localhost:5173 \
    risk-app-backend
```

El contenedor arranca con el usuario `riskapp` (uid 1001), no como `root`, y su
`HEALTHCHECK` consulta `/health`. Para ver el estado:

```bash
docker inspect risk-app-backend --format '{{.State.Health.Status}}'
```

### 6.2 El entorno completo

`docker compose up -d` levanta Supabase (Postgres, Auth, Storage, PostgREST) y el
backend. El frontend se sirve con `npm run dev`, que recarga en caliente.

**El frontend tambien se puede levantar en Docker**, con dos perfiles que no
coexisten (los dos ocupan el puerto 5173):

```bash
docker compose --profile dev up -d     # Vite, con recarga en caliente
docker compose --profile prod up -d    # el bundle de produccion, servido por nginx
```

El perfil `prod` es el que conviene para validar antes de publicar: levanta
**exactamente el bundle que se despliega en Vercel**, con las variables `VITE_`
horneadas al compilar. El perfil `dev` es para trabajar dentro del contenedor.

Las variables `VITE_` se leen **al compilar**, no al arrancar. Si cambias una, hay que
reconstruir la imagen:

```bash
docker compose --profile prod build --no-cache
```

Lo que **no** hace el compose: aplicar migraciones. Se aplican con el CLI, que es
la unica herramienta de migraciones del proyecto (ADR-32):

```bash
supabase db reset          # recrea el esquema desde cero
supabase db push --local   # aplica solo las migraciones nuevas
```

### 6.3 Lo que se optimizo en la imagen

| decision | por que |
|---|---|
| Multi-stage | La etapa final no lleva el compilador ni las cabeceras que `uv` necesita |
| `uv` ausente de la etapa final | Pesa 43,8 MB y en runtime no se usa |
| Cache de `uv` limpio tras instalar | Sin esto, la imagen lleva dos copias de lo descargado |
| Capas ordenadas por frecuencia de cambio | `pyproject.toml` cambia poco; `app/` cambia todos los dias |
| `COPY --chown` de una vez | Evita un `chown` recursivo despues |
| `.dockerignore` | Sin el, el `.venv` y el `.env` viajan dentro del contexto de build |

Resultado: **337 MB**. El `.venv` pesa 124 MB y casi todo es transitive del SDK de
Supabase (`opentelemetry`, `sentry_sdk`, `google`, `rich`, `pygments`, `uvloop`,
`cryptography`). Quitarlo exigiria recortar el SDK, que es dependencia directa
(ADR-05): un recorte de tamano no puede costar una funcionalidad.

### 6.4 El `uv.lock` es obligatorio en la imagen

`uv sync --frozen` se niega a instalar sin el lockfile. Sin `uv.lock` dentro de la
imagen, la construccion resolveria las dependencias en ese momento, y dos
construcciones en dias distintos podrian instalar versiones distintas. El
`Dockerfile` copia `pyproject.toml` **y** `uv.lock` por eso.

---

## 7. El proyecto en la nube

El proyecto en la nube es el que se usa para el despliegue. **El CLI de Supabase
administra su propia configuracion**: no hay un `.env` para el, hay un enlace.

### 7.1 Las cuatro cosas que hacen falta

Son cuatro y se confunden entre si, asi que conviene separarlas:

| Que | Donde sale | Para que |
|---|---|---|
| El **project ref** | `Project Settings -> General -> Reference ID`. Sale en la URL del panel | Identifica el proyecto |
| La **publishable key** | `Project Settings -> API Keys` | La app en el navegador |
| La **secret key** | `Project Settings -> API Keys` | El backend |
| El **access token** | `Account Preferences -> Access Tokens` | **La CLI** |

Las tres primeras son del **proyecto**. El access token es **de la cuenta**, y no
tiene nada que ver con ellas: es lo que autoriza a la CLI a hablar con la
plataforma.

> **El access token no es la secret key.** Son cosas distintas, de sitios distintos
> del panel, con propositos distintos. Confundirlas es el error mas comun al
> enlistar un proyecto: la `secret key` la usa la aplicacion, el access token lo
> usa la CLI.

El **project ref** ya se ve en la URL del panel: `supabase.com/dashboard/project/<ref>/...`.

### 7.1.1 El access token, y los permisos que pide

El CLI 3.4.0 trabaja con **tokens con permisos** (`sbp_...`), no con el token de
cuenta completo que usaba antes. Se genera en `Account Preferences -> Access
Tokens`, y se puede limitar a lo que el proyecto necesita:

| Comando | Permiso que pide |
|---|---|
| `supabase link` | `project_admin_read` (obligatorio), `projects_read`, `database_pooling_config_read` |
| `supabase db push` | `database_write` (obligatorio), `projects_read` |

El token de cuenta por defecto los trae todos. Un token "scoped" con esos
permisos tambien sirve.

### 7.1.2 La contrasena de la base de datos

El `supabase db push` la pide, porque se conecta a Postgres para aplicar las
migraciones. Si el proyecto todavia no tiene, se establece en
`Project Settings -> Database -> Postgres`, y el panel la muestra una sola vez.

### 7.2 El enlace

```bash
supabase login                              # pide el access token, o:
$env:SUPABASE_ACCESS_TOKEN = "<token>"      # en Powershell

supabase link --project-ref <project-ref>
```

El enlace guarda la referencia en `supabase/.temp/`, que esta en `.gitignore`. A
partir de ahi, `supabase db push` y `supabase db advisors` ya apuntan al proyecto
sin que haya que repetir el `--project-ref`.

### 7.3 Aplicar el esquema

```bash
supabase db push --remote --password "<contrasena de postgres>" --yes
```

Esto aplica **el mismo SQL** del directorio `supabase/migrations/` que se valido en
local. No hay conversion: el mismo archivo que se aplico con `db reset` local es el
que se aplica aqui. Por eso el item del Gate 1 sobre `supabase db push` es el que
falta cerrar.

> **La contrasena de Postgres no es la del administrador de la app.** Son dos cosas
> distintas: la de Postgres abre la conexion para aplicar migraciones, y la del
> administrador es la que se usa para entrar a la aplicacion. La CLI la pide en
> cada `db push` si no se la pasas con `--password`.

### 7.4 Configurar el backend

Las variables del `backend/.env` cambian a las del proyecto en la nube:

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<publishable key del panel>
SUPABASE_SERVICE_ROLE_KEY=<secret key del panel>
```

Y el `frontend/.env` lleva la URL y la llave **publicable**:

```
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<publishable key del panel>
```

> **El prefijo es `VITE_`, no `NEXT_PUBLIC_`.** El prefijo lo elige el bundler, no
> Supabase. Este proyecto usa Vite, y Vite solo expone al navegador las variables
> que empiezan por `VITE_`. Con `NEXT_PUBLIC_` (que es el de Next.js) la variable
> llega al navegador como `undefined`: **no hay error al compilar**, el error sale en
> la consola del navegador, en produccion. El `.env.example` del frontend lo
> advierte, y hay una prueba (`frontend/src/env.spec.ts`) que falla en la
> compilacion si las variables no llegan.

> **El nombre de la variable en el backend es distinto a propósito.** Ahi se llama
> `SUPABASE_ANON_KEY`, porque asi la llama el SDK de Python. El **valor** es el
> mismo: la publishable key. Solo cambia el nombre para que el backend y el
> frontend no se confundan: en el backend hay dos llaves y una de ellas no puede
> tocar el navegador.

> **El secret key no viaja al navegador.** Va solo en el backend, y ahi solo lo usa
> el adaptador de administracion (ADR-13).

### 7.5 Crear el primer administrador

Con el proyecto enlazado, el bootstrap se corre contra la nube:

```bash
cd backend
uv run python -m scripts.bootstrap_admin \
    --correo admin@ejemplo.com \
    --organizacion "<nombre de la organizacion>"
```

El script imprime la contrasena temporal si no se le pasa una.

### 7.6 Comprobar el proyecto enlazado

```bash
supabase db advisors --remote --type all --level warn
```

Es el mismo advisor que se corrio en local, pero contra el proyecto de la nube. Si
no reporta ningun WARN ni ERROR, el esquema desplegado cumple lo mismo que el
validado.

> **Los seis WARN que quedan son intencionales.** Verificado el 2026-11-28 contra el
> proyecto `risk-app`:
>
> - `authenticated_security_definer_function_executable` (5): las cinco funciones RPC
>   de negocio (`guardar_analisis`, `registrar_actividad`, `actualizar_trabajo`,
>   `mis_permisos`, `revocar_sesion`) son `security definer` en `public` y
>   `authenticated` debe poder llamarlas: son la via de escritura del pipeline y la
>   via de lectura de los permisos del usuario (ADR-37). La propia remediacion del
>   linter dice: muevala fuera del esquema expuesto **solo si los usuarios con sesion
>   no deberian poder llamarla**.
> - `auth_leaked_password_protection` (1): es una opcion de Supabase Auth
>   (HaveIBeenPwned), se activa en el panel. No es del esquema.

### 7.7 El proyecto que esta desplegado

Verificado el 2026-11-28 contra el proyecto `risk-app`:

| Que | Valor |
|---|---|
| Project ref | `tygzjraxknlwyllkabid` |
| URL | `https://tygzjraxknlwyllkabid.supabase.co` |
| Migraciones aplicadas | 11 (`001` a `011`) |
| Tablas con RLS | 17, todas con `FORCE ROW LEVEL SECURITY` |
| Politicas | 49 |
| Permisos | 14, en 3 roles |
| Plantillas | 1 (la generica v1) |
| Administrador | `admin@ejemplo.com`, rol `admin`, organizacion "Equipo inicial" |

Comprobaciones hechas contra ese proyecto:

- `POST /rest/v1/rpc/mis_permisos` sin token -> `401` `42501 permission denied`.
- La misma llamada con el JWT del administrador -> `200` con los 14 permisos de `admin`.
- `GET /rest/v1/perfiles` sin token -> `200` con 0 filas; con token -> 1 fila.
- `POST /rest/v1/rpc/revocar_sesion` sobre la sesion de otro usuario -> `403` `42501`.

---

## 8. Orden de trabajo

El proyecto es incremental y cada capa se apoya en la anterior:

| # | Bloque | Estado | Gates que lo cubren |
|---|---|---|---|
| 1 | **Esqueleto**: estructura, configuracion, dependencias | **Hecho** | Gate 14 |
| 2 | **Migracion**: esquema, RLS, matriz de permisos y bucket, contra una base vacia | **Hecho** | Gate 1, 2, 3.1, 3.4 |
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
