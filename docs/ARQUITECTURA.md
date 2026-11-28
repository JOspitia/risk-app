# Arquitectura tecnica — Risk-app

> Stack, estilo arquitectonico, estructura de carpetas, modelo de datos, despliegue y flujo
> del pipeline. Este documento es la fuente de verdad tecnica. El **por que** del producto
> esta en [CONTEXTO.md](CONTEXTO.md). Los **contratos de codigo** (como se escribe) estan en
> [../SKILL.md](../SKILL.md).

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-28

---

## 1. Stack y versiones

`[DECIDIDO]` Combinacion actual y estable para trabajar en conjunto. **Las versiones se
fijan con pin exacto** en `pyproject.toml` y `package.json`: un stack que se mueve solo es
un stack que se rompe en silencio, y la ruptura aparece en produccion, no en el
`pyproject.toml`.

### 1.0 Versiones fijadas

Verificadas contra los registros oficiales (PyPI, npm y nodejs.org) el **2026-11-27**.

| Componente | Version | Publicada | Nota |
|---|---|---|---|
| Python | **3.14.10** | 2026-10-07 | **No 3.15.** Vercel Functions no ofrece 3.15 todavia (ver 1.0.1) |
| FastAPI | **0.165.0** | 2026-11-18 | `requires_python >= 3.11`; declara `Python :: 3.15` |
| supabase (SDK de Python) | **2.34.1** | 2026-11-06 | `requires_python >= 3.11` (dejo 3.9 y 3.10 en 2.34.0) |
| Vue | **3.5.46** | 2026-11 | Rama 3.5, parche activo |
| Vite | **8.4.0** | 2026-11-26 | Empaquetador **Rolldown** (`rolldown ~1.3.2`) |
| TypeScript | **6.0.3** | 2026-10 | **No 7.x.** TypeScript 7 no expone API programatica estable y rompe `vue-tsc` (ver 1.0.2) |
| vue-tsc | **3.3.14** | 2026-10 | Verificacion de tipos de los `.vue`. Requiere TypeScript 6 |
| Node.js | **24 o 26** (LTS) | - | El piso real lo impone `@supabase/supabase-js`: `>= 22.0.0` |
| @supabase/supabase-js | **2.119.2** | 2026-11-19 | `engines.node >= 22.0.0` |
| @mlc-ai/web-llm | **0.2.89** | 2026-11-17 | 175 modelos en el catalogo. Ver 6.2 |
| Supabase CLI | **3.4.0** | 2026-11-24 | Rama v3 (`latest`). El dist-tag `v2.stable` apunta a 2.122.1 |
| PostgreSQL | **17** | - | Supabase mantiene las ramas 15 y 17; el soporte de 14 termino en 2026-07-01 |
| PostgREST | **14** | - | La Data API de Supabase |
| Supabase (plan) | **Free** | - | Primer despliegue, ADR-21. Sube a Pro si el demo es un trabajo facturado |

### 1.0.1 Por que Python 3.14 y no 3.15

`[DECIDIDO]` **Python 3.14.10.** Vercel Functions ofrece **3.12 (por defecto), 3.13 y 3.14**.
La version 3.15 todavia no esta disponible en el runtime de Vercel: fijar 3.15.2 en el
`pyproject.toml` seria una promesa que el despliegue no puede cumplir, y el error
apareceria en el primer `vercel deploy`, no en la revision.

Python 3.15 no esta *prohibido*: es la version mas nueva y FastAPI ya la declara soportada.
Simplemente **no se puede desplegar ahi todavia**. Si el cliente contrata un despliegue
propio (Docker, ADR-21), ahi si se puede subir a 3.15. El pin del repositorio sigue el
entorno de despliegue real, no el mas nuevo que exista.

### 1.0.2 Por que TypeScript 6 y no 7

`[DECIDIDO]` **TypeScript 6.0.3 con `vue-tsc` 3.3.14.** TypeScript 7 es el port nativo en
Go y ya es `latest` en npm, pero **no expone la API programatica de JavaScript** que
necesitan las herramientas del ecosistema:

- `vue-tsc` la necesita para verificar los tipos de los `.vue` desde la linea de comandos.
- `typescript-eslint` declara `>=4.8.4 <6.1.0` y **rechaza** 7.0.
- Vue Language Tools tiene la misma dependencia.

El proyecto usa componentes de archivo unico de Vue 3.5, asi que `vue-tsc` no es
opcional: sin el, los `.vue` no se verifican.

La combinacion que Microsoft publica para este caso es instalar las dos lineas con alias:

```jsonc
{
  "devDependencies": {
    "typescript": "npm:@typescript/typescript6@^6.0.2",   // API de JS: vue-tsc, eslint, tests
    "@typescript/native": "npm:typescript@^7.0.2"          // compilador nativo: build y watch
  }
}
```

En la v1 se usa **solo TypeScript 6**: una dependencia mas, un `tsc` mas lento, y nada
ganado. La linea 7 entra cuando el proyecto tenga volumen de build que lo justifique o
cuando `vue-tsc` lo soporte de forma estable.

**El SDK de Python va en 2.34.1, no en la ultima de la serie 2.** La 2.34.1 es la que
declara `requires_python >= 3.11` y por tanto admite 3.14 sin problema.

**El CLI tiene dos ramas vivas.** `latest` es la v3 (3.4.0) y la v2 sigue viva bajo el
dist-tag `v2.stable` (2.122.1). Se usa la **v3**; la v2 queda anotada por si una
herramienta del flujo de migraciones todavia la espera.

**`requirements.txt` no: es `pyproject.toml`.** El backend se gestiona con `uv`. Lo que
importa de la idea es que las dependencias del backend sean **ligeras**: la inferencia no
ocurre en Python, asi que no hay `torch` ni `numpy` con ruedas pesadas. Solo `fastapi`,
`pydantic`, `httpx` y el SDK de Supabase.

`[DECIDIDO]` El frontend es **Vue 3.5.46**, no React. La version original del documento de
contexto describia React; queda corregido aqui de forma explicita para evitar que el
documento viejo se lea como vigente.

### 1.1 Requisitos de navegador

`[DECIDIDO]` El modo navegador (ADR-06) exige **WebGPU**. El piso de navegador soportado
es el que aparece en `CONTEXTO.md` seccion 5.2: Chrome y Edge 113+, Firefox 141+ en
Windows, y **Safari 26 en macOS Tahoe 26 / iOS 26** — no en macOS 15 ni anteriores.

### 1.2 Toolchain del backend

| Categoria | Eleccion | Nota |
|---|---|---|
| Gestor de dependencias | `uv` | Recomendado por FastAPI; alternativa `pip` + venv |
| Validacion y config | `pydantic` v2 + `pydantic-settings` | `pydantic-settings` para leer `.env` |
| Acceso a datos | **Cliente HTTP de Supabase (PostgREST)** | Ver ADR-04. Sin `asyncpg` en el camino caliente |
| Migraciones | **Supabase CLI** (`supabase/migrations/*.sql`) | Una sola fuente de verdad. Ver ADR-32 |
| ETL de PDF (v2, servidor) | `pymupdf` (fitz), `docling` para OCR | Segun necesidad de OCR (DP-03) |
| LLM en navegador | `@mlc-ai/web-llm` + `pdf.js` | Camino principal de la v1 |
| LLM en servidor (v2) | `ollama` (cliente HTTP) o `vllm` | Solo para el modo servidor |
| Cola de tareas | **Aplazada a la v2** | La v1 no encola: el analisis ocurre en el cliente |
| Tests | `pytest`, `pytest-asyncio`, `httpx` | Tests de integracion contra Supabase real |
| Calidad | `ruff` (lint + format), `mypy` (tipos estricto), `import-linter` | El ultimo verifica la frontera hexagonal sin esperar a un humano |
| Tipos del cliente | `openapi-typescript` + `openapi-fetch` | Los tipos del frontend se generan del OpenAPI, no se escriben a mano |
| Containers | `docker compose` | Entorno local reproducible + worker de la v2 |

**El conjunto de dependencias del backend es deliberadamente ligero.** La inferencia ocurre
en el navegador, asi que Python no carga con el peso de la IA: no hay `torch`, ni `numpy`
con ruedas pesadas, ni servidor de modelos. El nucleo es `fastapi[standard]`, `pydantic`,
`httpx` y el SDK de Supabase, mas `pytest` para probar. **No hay Alembic**: las
migraciones son SQL que aplica el CLI de Supabase (ADR-32). Una dependencia que no
justifique su peso se rechaza en la revision.

**La frontera hexagonal se verifica sola.** `import-linter` corre en la integracion
continua desde el primer commit, con contratos explicitos:

```toml
# backend/pyproject.toml
[tool.importlinter]
root_package = "app"

[[tool.importlinter.contracts]]
name = "El dominio no depende de nadie"
type = "forbidden"
source_modules = ["app.domain"]
forbidden_modules = ["app.application", "app.adapters", "app.worker", "fastapi", "pydantic", "httpx", "supabase"]

[[tool.importlinter.contracts]]
name = "La aplicacion no conoce los adaptadores"
type = "forbidden"
source_modules = ["app.application"]
forbidden_modules = ["app.adapters", "fastapi"]
```

Una dependencia prohibida rompe la integracion continua antes de que la rompa la
reproduccion de la revision.

**Los tipos del frontend se generan, no se escriben.** El backend expone su OpenAPI y el
frontend lo consume:

```
npm run api:types    # lee backend/tests/contract/openapi.json y genera frontend/src/api/types.ts
```

El archivo generado se versiona, para que un cambio de contrato se vea en el diff y no
aparezca solo en el momento de compilar.

### 1.3 Toolchain del frontend

| Categoria | Eleccion | Nota |
|---|---|---|
| Framework | Vue 3.5.46 (`<script setup>`, Composition API) | |
| Build | Vite 8.4.0 + TypeScript 6.0.3 | Empaquetador Rolldown. `vue-tsc` 3.3.14 para los `.vue` |
| Estado | Pinia | Estado de sesion, configuracion del motor, documentos |
| Enrutado | Vue Router | |
| Estilos | Tailwind CSS | Coherente con la version original del documento |
| Cliente HTTP | `fetch` tipado con interceptor de token | `fetch` nativo basta para el volumen esperado |
| Cliente de datos | `@supabase/supabase-js` 2.119.2 | Requiere Node >= 22. Lo que habla con PostgREST |
| ETL en navegador | `pdf.js` | Extraccion de texto por pagina. **Empaquetado localmente**, no desde un CDN: el modo sin conexion lo exige |
| LLM en navegador | `@mlc-ai/web-llm` 0.2.89 | Ejecucion en Web Worker, **nunca** en el hilo principal |
| Chunking | Funcion propia compartida con el backend | Mismo algoritmo en ambos lados |
| Tests | `vitest` + `@vue/test-utils` | Con adaptadores de prueba para `WebGPU`, `WebWorker` y `Cache API` |

**El motor LLM vive en un Web Worker.** Cargar 1.5 a 3 GB de pesos y luego generar token a
token en el hilo principal bloquearia la interfaz: la app dejaria de responder mientras se
analiza, que es justo el requisito de que la aplicacion no se afecte. Vite 8 empaqueta los
modulos de WebAssembly de forma nativa, asi que el worker se importa sin rodeos.

**El troceado se prueba con casos dorados compartidos.** Python y TypeScript no pueden
importar el mismo archivo de codigo, asi que el algoritmo vive en los dos lados y se
verifica con el **mismo conjunto de datos**:

```
shared/chunking-casos.json
```

El archivo tiene entradas y salidas esperadas. `pytest` las corre en Python y `vitest` las
corre en TypeScript. Si los dos lados divergen, uno de los dos falla: es exactamente el
error que un documento con datos contradictorios entre bloques produce, y que en el
navegador seria muy dificil de diagnosticar.

---

## 2. Estilo arquitectonico

### 2.1 La decision

`[DECIDIDO]` **Hexagonal (puertos y adaptadores).** El nucleo de dominio no depende de
FastAPI, de la base de datos ni del motor LLM. FastAPI es el adaptador de entrada; Supabase,
el motor LLM y el almacenamiento son adaptadores de salida.

**Motivos de la decision:**

1. Hay **tres adaptadores de salida intercambiables**: Supabase, motor LLM (navegador o
   servidor) y almacenamiento. El puerto en el centro permite cambiar de motor sin tocar la
   logica de negocio.
2. El pipeline tiene **dos modos de ejecucion** (navegador y servidor). Con la arquitectura
   en capas, ese caso se resuelve con banderas `if` repartidas por los servicios; con
   puertos, se resuelve con un adaptador mas.
3. El **dominio se prueba sin base de datos ni red**, que es lo que hace barato construir
   el chunking, el Map-Reduce y la validacion de esquemas.
4. Es la decision **mas costosa de revertir**, asi que se toma antes de escribir codigo.

### 2.2 La invariante

```
Request HTTP
    |
    v
[Adaptador de entrada]  <- router FastAPI: valida, orquesta, elige status
    |
    v
[Caso de uso]           <- logica de negocio, transaccion, autorizacion
    |
    v
[Puertos]               <- interfaces que define el dominio
    |
    v
[Adaptadores de salida] <- Supabase, LLM, storage
    |
    v
[Entidad de dominio]
```

**Las dependencias apuntan hacia adentro y a un solo lado.**

- El router puede llamar al caso de uso. **No** puede llamar al repositorio.
- El caso de uso puede llamar a los puertos. **No** puede conocer HTTP, JSON ni SQL.
- El adaptador de salida implementa un puerto. **No** decide nada: mapea datos, no politicas.
- El dominio no conoce ningun framework: ni FastAPI, ni SQLAlchemy, ni Pydantic.

> La violacion mas comun: un router que consulta el repositorio para verificar propiedad o
> existencia. Eso es logica de negocio vestida de controller. Va en el caso de uso.

### 2.3 Relacion con la version anterior del skill (en capas)

El skill original especificaba una API REST en capas
(`Controller -> Service -> Repository -> Model`). Sus contratos siguen siendo validos y se
conservan mapeados uno a uno. La diferencia no es de contratos sino de **vocabulario** y de
**donde viven las interfaces**.

| Contrato del skill en capas | Rol en hexagonal | Donde vive |
|---|---|---|
| Request (DTO de entrada) | Esquema de entrada del adaptador | `adapters/http/schemas/` |
| Controller (FastAPI router) | **Adaptador de entrada** | `adapters/http/routers/` |
| Service (logica de negocio) | **Caso de uso** (application layer) | `application/use_cases/` |
| Repository (interfaz + impl) | **Puerto de salida** / **adaptador de salida** | `domain/ports/` + `adapters/supabase/` |
| Model (entidad) | Entidad de dominio | `domain/entities/` |
| Resource (DTO de salida) | Mapper de salida / DTO de presentacion | `adapters/http/schemas/` |
| Response (envelope HTTP) | Envelope de API | `adapters/http/responses.py` |
| Exception (errores de dominio) | Errores de dominio + mapeo a HTTP | `domain/errors.py` + `adapters/http/error_handlers.py` |
| Auth filter | Middleware + guard | `adapters/http/middleware.py`, `deps.py` |
| Audit context | Contexto de auditoria transversal | `application/audit/` |
| Transacciones | Unit of work (puerto) | `application/unit_of_work.py` |

**La invariante es identica en ambos estilos.** Lo que cambia en hexagonal es que la
interface la define el dominio y la implementa la infraestructura, no al reves.

### 2.4 Lo que no se sobrediseña

`[DECIDIDO]` La arquitectura hexagonal **no** significa hexagonalizar todo.

- Un caso de uso que solo lee y escribe una tabla no necesita un puerto con cinco metodos.
  Se declara el port minimo que usa.
- No se crean puertos para librerias de terceros que no van a cambiar (un lector de PDF no
  es un puerto: es un detalle interno del adaptador ETL).
- Los puertos que si se justifican: **persistencia**, **motor LLM**, **almacenamiento de
  archivos**, **cola de tareas**, **reloj**.

---

## 3. Estructura de carpetas

`[DECIDIDO]` Monorepo simple: backend y frontend en el mismo repositorio.

```
Risk-app/
├── AGENTS.md                     # punto de entrada para cualquier agente
├── README.md                     # brief para revisores
├── SKILL.md                      # metodo y contratos de codigo (instalable como skill)
├── CHECKLIST.md                  # gates de verificacion
├── CONTRIBUTING.md               # convencion de commits y pull requests
├── vercel.json                   # config de despliegue de la API y el frontend
├── docs/
│   ├── CONTEXTO.md
│   ├── ARQUITECTURA.md
│   ├── DECISIONES-PENDIENTES.md
│   ├── ARRANQUE.md               # guia de arranque local
│   ├── HU/                       # historias de usuario
│   └── legacy/                   # documentos originales, sin procesar
├── backend/
│   ├── pyproject.toml            # pins exactos y configuracion de ruff/mypy/pytest
│   ├── Dockerfile                # entorno local y futuro despliegue self-hosted
│   ├── .env.example              # el contrato de variables; el `.env` no se versiona
│   ├── api/index.py              # handler de Vercel (@vercel/python) que expone `app`
│   ├── app/
│   │   ├── main.py               # composicion: app FastAPI + routers + handlers
│   │   ├── config.py             # pydantic-settings; falla al arrancar si falta config
│   │   ├── domain/               # SIN dependencias de framework ni de infra
│   │   │   ├── entities/         #   documento.py, bloque.py, analisis.py, plantilla.py
│   │   │   ├── value_objects/    #   paginas.py, configuracion_motor.py, hash_sha256.py
│   │   │   ├── ports/            #   repositorios, motor_llm, storage, cola, reloj
│   │   │   ├── services/         #   reglas puras: chunking, validacion de esquema
│   │   │   └── errors.py         #   errores de dominio (no HTTP)
│   │   ├── application/
│   │   │   ├── use_cases/        #   registrar_analisis.py, listar_documentos.py, ...
│   │   │   ├── dto/              #   command/query de entrada y salida de casos de uso
│   │   │   ├── audit/            #   contexto y logger de auditoria
│   │   │   └── unit_of_work.py   #   unit of work (puerto)
│   │   ├── adapters/
│   │   │   ├── http/
│   │   │   │   ├── routers/      #   documentos.py, configuracion.py, plantillas.py
│   │   │   │   ├── schemas/      #   Request / Resource (Pydantic)
│   │   │   │   ├── responses.py  #   envelope + paginacion
│   │   │   │   ├── error_handlers.py
│   │   │   │   └── deps.py       #   DI: caso de uso, usuario autenticado
│   │   │   ├── supabase/         #   implementaciones de repos via PostgREST
│   │   │   ├── llm/              #   ollama.py, vllm.py, stub_llm.py (v2)
│   │   │   ├── etl/              #   pymupdf.py, docling.py (v2)
│   │   │   ├── storage/          #   supabase_storage.py, temp_disk.py
│   │   │   └── queue/            #   cola (v2)
│   │   └── worker/               #   entrypoint del worker ETL (v2)
│   └── tests/
│       ├── unit/                 #   dominio y casos de uso, sin DB ni red
│       ├── integration/          #   contra Supabase real
│       └── contract/             #   OpenAPI snapshot + envelope
├── supabase/                     #   configuracion y migraciones (ADR-32)
│   ├── config.toml
│   ├── migrations/               #   *.sql, la unica fuente de verdad del esquema
│   │   ├── 001_esquema_inicial.sql
│   │   ├── 002_rls.sql
│   │   ├── 003_permisos_y_roles.sql
│   │   ├── 004_bucket_y_storage.sql
│   │   └── 005_funciones_rpc.sql
│   └── seed.sql                  #   datos semilla: roles, permisos, plantilla v1
├── shared/                       #   fixtures compartidas entre Python y TypeScript
│   └── chunking-casos.json       #   casos dorados del troceado (ver §1.2)
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── .env.example              # el contrato de variables; el `.env` no se versiona
    └── src/
        ├── main.ts
        ├── App.vue
        ├── router/
        ├── stores/                #   Pinia: sesion, motor, documentos
        ├── api/                   #   cliente HTTP + tipos
        ├── components/
        ├── views/
        │   ├── InicioView.vue
        │   ├── LoginView.vue
        │   ├── DocumentosView.vue
        │   ├── DocumentoDetalleView.vue
        │   └── MotorConfigView.vue
        ├── workers/               #   Web Worker: pdf.js + WebLLM
        └── shared/                #   chunking compartido con el backend
```

> **El arbol documentado y el arbol real no coinciden todavia.** Este bloque es el
> **destino**: la estructura que tendra el proyecto cuando la implementacion este
> completa. Lo que existe hoy es el esqueleto: las carpetas, la configuracion y los
> `__init__.py`; los archivos listados dentro de cada carpeta (`main.py`, los
> `errors.py`, los routers, las migraciones, `Dockerfile`, `seed.sql`) llegan con
> sus bloques.
>
> Un `.gitkeep` mantiene las carpetas vacias en el repositorio: git no versiona
> carpetas vacias, y sin el el arbol del clon no coincidiria con este.

**Regla de dependencia del nucleo:** `domain/` no importa nada de `adapters/`, `application/`
ni de frameworks (FastAPI, Pydantic, cliente HTTP). Los casos de uso conocen el dominio y los
puertos. Los adaptadores conocen los puertos y el framework. La comprobacion se automatiza
con `import-linter` (contrato `domain` no puede importar `adapters`).

---

## 4. Modelo de dominio

`[DECIDIDO]` Cuatro entidades centrales, mas las de soporte.

| Entidad | Responsabilidad | Campos clave |
|---|---|---|
| `Documento` | Un PDF analizado y su estado | `id`, `usuario_id`, `organizacion_id`, `nombre_archivo`, `hash_sha256`, `total_paginas`, `modo_procesamiento`, `estado`, `error_mensaje`, timestamps |
| `Bloque` | Unidad de analisis (fase Map) | `id`, `documento_id`, `indice`, `pagina_inicio`, `pagina_fin`, `resumen`, `datos_estructurados` (JSONB) |
| `Analisis` | Resultado consolidado (fase Reduce) | `id`, `documento_id` (unico), `resumen_ejecutivo`, `riesgos` (JSONB) |
| `PlantillaExtraccion` | Esquema dinamico de campos a extraer | `id`, `organizacion_id`, `nombre`, `version`, `esquema` (JSONB), `instruccion`, `activa` |
| `Trabajo` | Seguimiento de un analisis en curso | `id`, `documento_id`, `usuario_id`, `tipo`, `estado`, `progreso`, `paso_actual`, `iniciado_en`, `finalizado_en`, `duracion_ms`, `error_mensaje` |
| `TrabajoActividad` | Bitacora de pasos ejecutados | `id`, `trabajo_id`, `tipo`, `mensaje`, `pagina_inicio`, `pagina_fin`, `duracion_ms` |

Soporte: `Perfil` (rol y organizacion del usuario), `ConfiguracionMotor` (parametrizacion
del motor IA), `Organizacion` (equipo/area), `OrganizacionMiembro` (pertenencia y rol por
equipo), `Rol`, `Permiso` y `RolPermiso` (matriz de permisos granular).

**Invariantes de dominio** (no dependen de la base de datos):

- Un `Documento` con `estado = completado` tiene exactamente un `Analisis`.
- Un `Documento` con `estado = completado` tiene `total_paginas >= 1` y al menos un `Bloque`.
- La suma de paginas de los bloques cubre el documento sin huecos fuera del solapamiento
  configurado.
- El `hash_sha256` identifica el contenido: subir el mismo archivo dos veces no duplica el
  trabajo (ver DP-06).
- Un `Analisis` no existe sin `documento_id` valido; la FK es `ON DELETE CASCADE`.
- Un `Trabajo` con `estado = completado` tiene `progreso = 100` y `finalizado_en` no nulo.
- `progreso` es monotono: nunca disminuye dentro de un `Trabajo`.
- Un `Trabajo` pertenece a un solo `Documento`, y un `Documento` tiene a lo sumo un
  `Trabajo` activo a la vez.

---

## 5. Modelo de datos

`[DECIDIDO]` PostgreSQL en Supabase. **Migraciones con el CLI de Supabase** (SQL puro en
`supabase/migrations/`). El esquema nunca se edita a mano: cada cambio es una migracion
nueva. Ver ADR-32.

### 5.1 Tablas

```sql
-- Organizaciones (equipos / areas). Unidad de comparticion de datos.
create table organizaciones (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  creado_en   timestamptz not null default now()
);

-- Roles y permisos granulares. La matriz vive en datos, no en codigo: agregar un permiso
-- no requiere desplegar. Se definen antes que `perfiles` porque se referencian.
create table roles (
  clave       text primary key,   -- admin | analista | auditor
  nombre      text not null,
  descripcion text,
  -- True = el rol viene con el sistema y no se puede eliminar ni renombrar.
  is_system   boolean not null default false,
  creado_en   timestamptz not null default now()
);

create table permisos (
  clave       text primary key,   -- documentos.ver | documentos.analizar | ...
  nombre      text not null,
  descripcion text not null,
  creado_en   timestamptz not null default now()
);

create table rol_permisos (
  rol     text not null references roles(clave) on delete cascade,
  permiso text not null references permisos(clave) on delete cascade,
  primary key (rol, permiso)
);

-- Perfil del usuario. Extiende auth.users (Supabase Auth).
create table perfiles (
  id                        uuid primary key references auth.users(id) on delete cascade,
  organizacion_id           uuid references organizaciones(id),
  rol                       text not null default 'analista' references roles(clave),
  nombres                   text not null,
  apellido_1                text not null,
  apellido_2                text,
  display_name              text,
  -- Correo del usuario. Se copia desde `auth.users` al crear la cuenta, para que el
  -- listado de usuarios no tenga que leer `auth.users` con `service_role` en cada
  -- peticion. `auth.users` sigue siendo la fuente de verdad; esta es una copia.
  correo                    text not null,
  -- True mientras la credencial sigue siendo la autogenerada y enviada por correo.
  -- Se limpia en el primer inicio de sesion con cambio de contrasena.
  debe_cambiar_contrasena    boolean not null default false,
  -- False = el usuario esta desactivado: no puede iniciar sesion y el resolutor de
  -- permisos lo trata como sin permisos, sin consultar `auth.users` en cada peticion.
  activo                    boolean not null default true,
  creado_en                 timestamptz not null default now(),
  eliminado_en              timestamptz
);

-- Pertenencia a una organizacion con un rol propio por equipo.
create table organizaciones_miembros (
  organizacion_id uuid not null references organizaciones(id) on delete cascade,
  usuario_id      uuid not null references auth.users(id) on delete cascade,
  rol             text not null references roles(clave),
  creado_en       timestamptz not null default now(),
  primary key (organizacion_id, usuario_id)
);

-- Sesiones revocadas. El cierre de sesion invalida el token de inmediato (ADR-31).
-- Solo guarda el session_id, nunca el token. Las filas caducan con el token.
create table sesiones_revocadas (
  session_id   text primary key,
  usuario_id   uuid references auth.users(id) on delete cascade,
  revocado_en  timestamptz not null default now(),
  expira_en    timestamptz not null
);

-- Plantillas de extraccion: campos dinamicos sin migrar la BD.
create table plantillas_extraccion (
  id               uuid primary key default gen_random_uuid(),
  organizacion_id  uuid references organizaciones(id),
  nombre           text not null,
  version          int  not null default 1,
  esquema          jsonb not null,   -- {"campos":[{"clave","tipo","descripcion","obligatorio"}]}
  instruccion      text not null,
  activa           boolean not null default true,
  creado_en        timestamptz not null default now(),
  eliminado_en     timestamptz
);

-- Configuracion del motor IA, por usuario o por organizacion.
create table configuracion_motor (
  id                    uuid primary key default gen_random_uuid(),
  usuario_id            uuid references auth.users(id) on delete cascade,
  organizacion_id       uuid references organizaciones(id),
  ambito                text not null,          -- usuario | organizacion
  modelo                text not null,
  modo_ejecucion        text not null,          -- navegador_local | servidor_python
  tamano_chunk_paginas  int  not null default 3,
  overlap_paginas       int  not null default 1,
  ventana_contexto      int  not null default 4096,
  temperatura           numeric(3,2) not null default 0.10,
  actualizado_en        timestamptz not null default now(),
  eliminado_en          timestamptz,
  -- exactamente un ambito por fila
  constraint configuracion_motor_ambito_unico check (
    (ambito = 'usuario'     and usuario_id is not null and organizacion_id is null) or
    (ambito = 'organizacion' and organizacion_id is not null and usuario_id is null)
  )
);

-- Documento analizado.
create table documentos (
  id                uuid primary key default gen_random_uuid(),
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  organizacion_id   uuid references organizaciones(id),
  nombre_archivo    text not null,
  hash_sha256       text not null,
  -- Ruta del objeto en el almacenamiento privado. Nulo mientras no se ha subido.
  ruta_archivo      text,
  tamano_bytes      bigint not null default 0,
  tipo_mime         text not null default 'application/pdf',
  total_paginas     int,
  modo_procesamiento text not null,   -- navegador_local | servidor_python
  estado            text not null default 'en_proceso',  -- en_proceso | completado | error
  error_mensaje     text,
  -- Momento en que el archivo quedo archivado en el bucket privado. Nulo si nunca se subio.
  archivado_en      timestamptz,
  creado_en         timestamptz not null default now(),
  actualizado_en    timestamptz not null default now(),
  eliminado_en      timestamptz
);

-- Documentos compartidos con otro usuario de la misma organizacion.
create table documentos_compartidos (
  documento_id   uuid not null references documentos(id) on delete cascade,
  usuario_id     uuid not null references auth.users(id) on delete cascade,
  compartido_por uuid references auth.users(id) on delete set null,
  creado_en      timestamptz not null default now(),
  primary key (documento_id, usuario_id)
);

-- Bloque analizado (fase Map). Vive en cascada con el documento: no tiene borrado logico.
create table bloques (
  id                  uuid primary key default gen_random_uuid(),
  documento_id        uuid not null references documentos(id) on delete cascade,
  usuario_id          uuid not null references auth.users(id) on delete cascade,
  indice              int  not null,
  pagina_inicio       int  not null,
  pagina_fin          int  not null,
  resumen             text,
  datos_estructurados jsonb not null,
  creado_en           timestamptz not null default now(),
  unique (documento_id, indice)
);

-- Analisis consolidado (fase Reduce). Un analisis vigente por documento.
create table analisis_documentos (
  id                uuid primary key default gen_random_uuid(),
  documento_id      uuid not null unique references documentos(id) on delete cascade,
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  plantilla_id      uuid references plantillas_extraccion(id),
  plantilla_version int,
  -- Modelo que produjo este analisis. Se compara con el del reanálisis para explicar
  -- diferencias que no vienen de la plantilla (HU-10 EC-05).
  modelo            text,
  total_bloques     int,
  resumen_ejecutivo text,
  riesgos           jsonb,
  resumenes         jsonb not null default '[]'::jsonb,  -- un resumen por bloque
  creado_en         timestamptz not null default now()
);

-- Historial de analisis: cuando un documento se reanaliza con otra plantilla, el
-- analisis anterior se mueve aqui en vez de sobrescribirse (ADR-25).
create table analisis_historial (
  id                uuid primary key default gen_random_uuid(),
  documento_id      uuid not null references documentos(id) on delete cascade,
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  plantilla_id      uuid references plantillas_extraccion(id),
  plantilla_version int,
  modelo            text,          -- modelo usado en ese analisis
  resumen_ejecutivo text,
  riesgos           jsonb,
  resumenes         jsonb,
  -- Id del analisis vigente que sustituyo a este.
  reemplazado_por   uuid references analisis_documentos(id),
  creado_en         timestamptz not null default now()
);

-- Seguimiento de un analisis en curso.
create table trabajos (
  id              uuid primary key default gen_random_uuid(),
  documento_id    uuid not null references documentos(id) on delete cascade,
  usuario_id      uuid not null references auth.users(id) on delete cascade,
  tipo            text not null default 'analisis',  -- analisis | reanalisis
  estado          text not null default 'en_cola',
                  -- en_cola | en_proceso | completado | error | cancelado | interrumpido
  progreso        int  not null default 0 check (progreso between 0 and 100),
  paso_actual     text,      -- 'extrayendo' | 'analizando bloque 7 de 50' | 'reduciendo'
  modo            text not null,  -- navegador_local | servidor_python
  iniciado_en     timestamptz,
  finalizado_en   timestamptz,
  duracion_ms     bigint,
  -- Ultimo latido recibido. `created_at` no sirve: los reportes posteriores no lo actualizan.
  -- Es lo que permite detectar un trabajo abandonado (ADR-24).
  ultimo_latido_en timestamptz,
  error_mensaje   text,
  creado_en       timestamptz not null default now(),
  eliminado_en    timestamptz
);

-- Bitacora de pasos ejecutados (visible en la UI).
create table trabajo_actividades (
  id            uuid primary key default gen_random_uuid(),
  trabajo_id    uuid not null references trabajos(id) on delete cascade,
  -- Clave de idempotencia que envia el cliente. Un reintento de red con el mismo
  -- `id_reporte` no duplica filas (HU-08 CE-06).
  id_reporte    text not null,
  tipo          text not null,   -- extraccion | bloque | reduce | persistencia
  mensaje       text,
  pagina_inicio int,
  pagina_fin    int,
  duracion_ms   int,
  creado_en     timestamptz not null default now(),
  unique (trabajo_id, id_reporte)
);

-- Bitacora de auditoria. Quien hizo que, cuando y desde donde.
create table auditoria (
  id            uuid primary key default gen_random_uuid(),
  organizacion_id uuid references organizaciones(id),
  usuario_id    uuid references auth.users(id) on delete set null,
  actor         text not null,          -- correo o identificador del actor
  accion        text not null,          -- usuario.creado | documento.eliminado | ...
  entidad       text not null,          -- usuario | documento | plantilla | ...
  entidad_id    uuid,
  detalles      jsonb,
  ip            inet,
  user_agent    text,
  creado_en     timestamptz not null default now()
);

-- Indices
create index documentos_org_idx        on documentos (organizacion_id, creado_en desc);
create index documentos_usuario_idx    on documentos (usuario_id, creado_en desc);
create index bloques_documento_idx     on bloques (documento_id, indice);
create index analisis_documento_idx    on analisis_documentos (documento_id);
create index historial_documento_idx   on analisis_historial (documento_id, creado_en desc);
create index trabajos_documento_idx    on trabajos (documento_id);
-- Soporta la expiracion perezosa: buscar los trabajos activos sin latido reciente.
create index trabajos_latido_idx       on trabajos (estado, ultimo_latido_en);
create index trabajo_actividades_idx   on trabajo_actividades (trabajo_id, creado_en);
create index auditoria_org_idx         on auditoria (organizacion_id, creado_en desc);
-- Un documento con el mismo contenido no se vuelve a subir mientras siga vivo.
create unique index documentos_hash_unico
  on documentos (usuario_id, hash_sha256) where eliminado_en is null;
```

> **Nota sobre `tamano_chunk_paginas`.** El valor por defecto cambio de 10 a 3. Ver seccion
> 6.2: los modelos de WebLLM vienen con ventana de contexto de 4K tokens, y 10 paginas de
> texto denso la desbordan.

> **Idioma de las columnas de tiempo.** Todas usan `creado_en`, `actualizado_en` y
> `eliminado_en`, en espanol, sin excepcion. Antes se mezclaban `created_at` y
> `actualizado_en` en el mismo esquema, y esa mezcla habia llegado hasta los DTO del
> `SKILL.md`. Como el esquema todavia no existe en ninguna base, se unifica ahora y no
> despues: cambiar el nombre de una columna despues es una migracion, no un rename.

> **Que tablas tienen borrado logico.** Las que el usuario puede listar y citar por su
> cuenta: `perfiles`, `documentos`, `plantillas_extraccion`, `configuracion_motor` y
> `trabajos`. Las hijas (`bloques`, `analisis_documentos`, `analisis_historial`,
> `trabajo_actividades`, `documentos_compartidos`) se van en cascada con su padre: un
> bloque sin documento no tiene sentido y conservarlo no aporta nada.

### 5.2 RLS

`[DECIDIDO]` RLS activo en toda tabla con datos de usuario.

**El aislamiento de organizacion se resuelve desde `organizaciones_miembros`, no desde
`perfiles.organizacion_id`.** El motivo es concreto: `perfiles` tiene un solo
`organizacion_id`, pero un usuario puede pertenecer a varios equipos (PP-01). Si la politica
se apoyara en `perfiles`, el usuario de una segunda organizacion veria todo lo de la
primera. Y si se apoyara solo en `perfiles`, un `analista` sin `analisis.ver_todos` podria
leer por PostgREST, con su propio JWT, los documentos de otros analistas de su equipo: la
matriz de permisos se esquivaria por la puerta de atras.

```sql
-- Funcion estable: la organizacion activa del usuario en la peticion.
create or replace function organizacion_activa()
returns uuid
language sql stable
as $$
  select m.organizacion_id
  from organizaciones_miembros m
  join perfiles p on p.id = m.usuario_id
  where m.usuario_id = auth.uid()
    and p.activo
    and p.eliminado_en is null
  limit 1;
$$;

alter table documentos enable row level security;

-- Lectura: lo propio, lo compartido, y lo de la organizacion si el permiso lo autoriza.
create policy documentos_lectura on documentos
  for select using (
    eliminado_en is null
    and (
      usuario_id = auth.uid()
      or exists (
        select 1 from documentos_compartidos dc
        where dc.documento_id = documentos.id and dc.usuario_id = auth.uid()
      )
      or (
        organizacion_id = organizacion_activa()
        and public.usuario_tiene_permiso('analisis.ver_todos')
      )
    )
  );
```

**Dos capas, y por que son distintas.** RLS filtra **filas**: que documentos existen y son
visibles. El permiso filtra **acciones**: que se puede hacer con ellos. Las dos se
comprueban. RLS no puede implementar la matriz de permisos por si sola, y la matriz no
puede saber que filas existen en otra organizacion.

El caso de uso comprueba el permiso **antes** de consultar (ADR-30), asi que RLS no
necesita responder "403": si el permiso falta, el caso de uso no llega a consultar; si
falta el permiso de fila, RLS devuelve cero filas y eso es un 404.

Reglas:

- El backend **no** usa la `service_role` key para atender peticiones de usuario final: si la
  usa, RLS queda anulada y el aislamiento depende solo del codigo de aplicacion. Ver DP-05.
- Las claves de servicio se usan unicamente en el worker, y aun ahi la consulta se acota
  explicitamente por `usuario_id` u `organizacion_id`.
- Toda tabla con datos de usuario tiene RLS activo, **incluidas** `auditoria`,
  `documentos_compartidos` y `sesiones_revocadas`.

### 5.3 Indices

Los indices se crean junto con las tablas, en el mismo bloque de la seccion 5.1. Se
listan alli para que el DDL completo se lea en un solo sitio.

```sql
create index documentos_estado_idx      on documentos (estado) where estado = 'en_proceso';
create index bloques_riesgos_gin        on bloques using gin (datos_estructurados);
create index plantillas_org_idx         on plantillas_extraccion (organizacion_id, activa);
create index miembros_usuario_idx       on organizaciones_miembros (usuario_id);
create index trabajos_usuario_idx       on trabajos (usuario_id, created_at desc);
create index trabajos_activos_idx       on trabajos (estado) where estado in ('en_cola','en_proceso');
create index trabajos_documento_idx     on trabajos (documento_id);
create index actividades_trabajo_idx    on trabajo_actividades (trabajo_id, created_at);
```

### 5.4 Consultas parametrizadas

`[DECIDIDO]` Toda consulta SQL va parametrizada. No se concatena entrada de usuario en
SQL, ni siquiera para construir `IN (...)`: se generan los placeholders (`?`, `?`, `?`) y se
pasan los valores por separado.

### 5.5 Roles, permisos y creacion de usuarios

`[DECIDIDO]` El sistema tiene un **sistema de roles y permisos** cuyo objetivo declarado es
que cada usuario vea exactamente la informacion que le corresponde, por encima del simple
inicio de sesion.

**La matriz vive en datos, no en codigo.** Un permiso es una fila. Agregar un permiso nuevo
(por ejemplo `plantillas.editar`) es un `insert`, no un despliegue.

**Permisos granulares** (catalogo inicial, `[PROPUESTO]`):

| Clave | Significado |
|---|---|
| `documentos.ver` | Ver documentos y sus resultados |
| `documentos.analizar` | Lanzar analisis |
| `documentos.borrar` | Eliminar (soft delete) documentos |
| `documentos.compartir` | Compartir un documento con su organizacion |
| `archivos.descargar` | Descargar el archivo original mediante URL firmada |
| `archivos.eliminar` | Eliminar el archivo del almacenamiento |
| `analisis.ver_todos` | Ver analisis de otros usuarios de la organizacion |
| `plantillas.ver` / `plantillas.editar` | Ver y modificar plantillas de extraccion |
| `configuracion.ver` / `configuracion.editar` | Ver y modificar la configuracion del motor |
| `usuarios.gestionar` | Crear usuarios y asignar roles |
| `organizacion.gestionar` | Cambiar roles y membresias del equipo |
| `auditoria.ver` | Consultar la bitacora de auditoria |

**Matriz inicial por rol** `[DECIDIDO]`, con la ambiguedad resuelta:

La regla general es **"se ve lo que el permiso autoriza"**. No hay una regla fija de "solo lo
propio" ni de "el equipo ve todo": lo que decide es la fila de `rol_permisos`. Eso permite
que la misma aplicacion tenga organizaciones con politicas distintas sin tocar codigo.

| Permiso | admin | analista | auditor |
|---|:---:|:---:|:---:|
| `documentos.ver` | si | si (los propios y los compartidos) | si (lectura) |
| `documentos.analizar` | si | si | no |
| `documentos.borrar` | si | los propios | no |
| `documentos.compartir` | si | si | no |
| `archivos.descargar` | si | el propio | si (lectura) |
| `archivos.eliminar` | si | el propio | no |
| `analisis.ver_todos` | si | **no** (por defecto) | si (lectura) |
| `plantillas.ver` | si | si | si (lectura) |
| `plantillas.editar` | si | no | no |
| `configuracion.ver` | si | si | si (lectura) |
| `configuracion.editar` | si | si (propia) | no |
| `usuarios.gestionar` | si | no | no |
| `organizacion.gestionar` | si | no | no |
| `auditoria.ver` | si | no | si (lectura) |

`[PROPUESTO]` El `analista` **no** recibe `analisis.ver_todos` por defecto: ve lo propio y lo
que se le comparte de forma explicita. El permiso existe como fila, asi que una
organizacion que quiera que su equipo se vea todo simplemente lo concede en la matriz, sin
cambiar codigo.

**Reglas de aplicacion:**

- El permiso se comprueba **en el caso de uso**, no solo en el router. Un router que
  consulta el permiso y el caso de uso que lo vuelve a comprobar es redundante; un router
  que lo consulta y el caso de uso que no, es un agujero.
- **La respuesta sigue un orden fijo** (ADR-30): primero el permiso, despues la fila.
  - Si el usuario **no tiene el permiso** que la accion exige: **403**.
  - Si lo tiene, pero la fila no aparece (no existe, o es de otra organizacion y RLS la
    filtro): **404**.

  Asi el caso de uso no necesita `service_role` para distinguir "no existe" de "no lo puedes
  ver": si el permiso falta, se responde 403 sin consultar; si el permiso esta, la consulta
  con el JWT del usuario ya aplico RLS, y lo que no aparece se responde 404.
- Un **403** es honesto cuando el usuario ya sabe que el recurso existe, porque esta en su
  propia organizacion. Un **404** evita confirmar que un identificador de otra organizacion
  existe.
- La pertenencia a la organizacion se resuelve desde `organizaciones_miembros`, de modo que
  un usuario puede estar en mas de un equipo con un rol distinto en cada uno.
- RLS y los permisos son capas complementarias, no redundantes: **RLS filtra filas**, el
  **permiso filtra acciones**. Un permiso ausente debe ser denegado, no "permitido por
  defecto".

### 5.6 Creacion de usuarios

`[DECIDIDO]` La creacion de usuarios es parte del alcance y se hace **desde la aplicacion**,
por el usuario `admin`.

**Datos que captura el admin:** nombres, apellido 1, apellido 2, correo, y una
**contrasena autogenerada** que se envia al correo del usuario, seguida de la confirmacion de
la cuenta.

**El primer administrador no se crea con SQL.** Insertar el primer usuario `admin` con un
`insert` en `auth.users` es fragil: Supabase espera filas coordinadas en `auth.users` y
`auth.identities`, con el formato interno de GoTrue, y ese formato cambia entre versiones.
Lo que hace el proyecto es un **script de bootstrap idempotente** que usa la API de
administracion de Supabase (`service_role`) despues de aplicar las migraciones:

```
uv run python -m scripts.bootstrap_admin --correo admin@ejemplo.com --organizacion "<nombre>"
```

El script es idempotente: si el correo ya existe, actualiza el perfil y no crea un
duplicado. Se ejecuta **una vez**, despues de `supabase db push` y antes de que la
aplicacion se use. Es el unico lugar del proyecto que usa `service_role` para crear
usuarios por consola, y esta justificado porque no hay todavia ningun `admin` que pueda
hacerlo desde la interfaz.

**Flujo.**

```
POST /api/v1/usuarios { nombres, apellido_1, apellido_2, correo }
  1. El caso de uso exige el permiso 'usuarios.gestionar'.
  2. Se genera una contrasena temporal criptograficamente fuerte.
  3. Se crea el usuario en Supabase con email_confirm = false.
  4. Se registra el perfil: nombres, apellidos, rol y organizacion.
  5. Se envia el correo con la contrasena temporal y el enlace de confirmacion.
  6. Se marca perfil.debe_cambiar_contrasena = true.
  7. Se registra la operacion en auditoria con el actor.
```

**El correo necesita su propio puerto.** `[DECIDIDO]` Enviar correo es una capacidad de
salida, como el LLM o la base de datos: se define un puerto y la infraestructura lo
implementa.

```python
# domain/ports/notificador.py
class NotificadorCorreo(Protocol):
    """Puerto de salida. Enviar correo, no decidir que se escribe."""

    async def enviar_credencial_temporal(
        self, correo: str, contrasena_temporal: str, enlace_confirmacion: str
    ) -> None: ...
```

Implementaciones: un proveedor real (Resend, Amazon SES o SMTP) y una de **desarrollo** que
solo escribe el correo en el log. La de desarrollo es la que permite probar el flujo sin
contratar un servicio de correo.

**La contrasena autogenerada es un riesgo con nombre propio.** `[PROPUESTO]` Viaja en
claro por el correo y queda en el buzon. Dos mitigaciones, ambas en el alcance:

1. **Se marca para cambio obligatorio.** `perfiles.debe_cambiar_contrasena = true`, y el
   frontend fuerza el cambio en el primer inicio de sesion. La contrasena temporal deja de
   servir para siempre.
2. **La alternativa mas segura es un enlace de un solo uso** en vez de la contrasena: el
   usuario elige su propia clave y nadie mas la ve. Es el flujo que ofrece Supabase con
   `generate_link`. Requiere configurar SMTP en Supabase y cambia el texto del correo.

La especificacion pide contrasena autogenerada, asi que se implementa asi y se deja la
alternativa documentada. Si se decide el enlace, el cambio es **solo el cuerpo del correo**:
el puerto no cambia y los casos de uso tampoco.

**Restriccion de seguridad.** Crear un usuario en Supabase requiere la `service_role`, que
por regla general no debe tocar el backend. La excepcion es **estrecha y delimitada**:

- La `service_role` vive en un **adaptador de administracion** (`adapters/supabase/admin.py`),
  que es el unico modulo del proyecto autorizado a usarla.
- Ese adaptador expone **solo** operaciones de aprovisionamiento: crear usuario, asignar
  rol y organizacion, desactivar, restablecer contrasena.
- Ningun router de peticiones de usuario final llega a ese adaptador. El unico endpoint que
  lo invoca exige el permiso `usuarios.gestionar`, que solo tiene `admin`.
- Toda operacion de aprovisionamiento se registra en la bitacora de auditoria con el actor.
- La `service_role` **nunca** se usa para leer o escribir datos de negocio: para eso se
  reenvia el JWT del usuario y deja que RLS filtre.

> Documentar la excepcion es obligatorio. Una regla que dice "no uses service_role" sin
> nombrar la excepcion produce dos ejemplos: el que la evade sin decirlo y el que la
> necesita y no la documenta.

**Alta por el panel de Supabase.** El adaptador de administracion es una capacidad, no una
obligacion: el mismo caso de uso puede resolver el alta contra la Admin API o delegar en
quien administers el panel de Supabase. La interfaz del caso de uso no cambia.

### 5.7 Almacenamiento de documentos

`[DECIDIDO]` **Los documentos se guardan.** ADR-20, 2026-11-27.

**El problema, con sus numeros.** Vercel Functions tiene el sistema de archivos **de solo
lectura**, con un `/tmp` de hasta 500 MB que es efimero, pertenece a una sola instancia y no
sobrevive a la invocacion. Ademas, el cuerpo de la peticion esta limitado a 4.5 MB (20 MiB
en beta). Un PDF de 100 paginas pesa habitualmente entre 5 y 30 MB: **no cabe ni por el
cuerpo ni en el disco**. No es que "no tengamos forma": en Vercel es fisicamente imposible,
y hay que usar un servicio de almacenamiento externo.

**Por que Supabase Storage.**

| Criterio | Supabase Storage | Vercel Blob | S3 / R2 directo |
|---|---|---|---|
| Ya esta en el stack | **Si** (es el nivel 3) | No | No: cuenta, llaves y bucket aparte |
| Modelo de permisos | **El mismo RLS y el mismo JWT** | Propio, sin RLS | Politicas IAM separadas |
| Acceso desde el navegador | Directo, con URL firmada | Directo | Directo |
| Sustitucion futura por S3/SFTP del cliente | Cambio de adaptador | Cambio de adaptador | Ya es S3 |
| Coste | Incluido en el plan de Supabase | Token y volumen aparte | Cuenta y billing aparte |

El argumento decisivo no es el coste: es que **Supabase Storage usa el mismo JWT y las
mismas politicas RLS que el resto del sistema**. El bucket hereda el modelo de permisos que
ya se esta construyendo, sin un concepto nuevo. Y cuando el cliente tenga su propio S3 o
SFTP, el cambio es **un adaptador mas**, no una reescritura.

**Bucket privado, con limites en el bucket.**

```sql
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documentos', 'documentos', false,
  52428800,                                  -- 50 MB (el limite del plan Free)
  array['application/pdf']
);

-- Policies sobre storage.objects: controlan toda operacion de archivo,
-- incluida la creacion de URLs firmadas.
-- La ruta es {organizacion_id}/{usuario_id}/{documento_id}.pdf, asi que se comprueban
-- LOS DOS primeros segmentos: validar solo el primero permitiria a un usuario escribir
-- dentro de la carpeta de otro usuario de su misma organizacion.
create policy archivos_insertar on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documentos'
    and (storage.foldername(name))[1] = organizacion_activa()::text
    and (storage.foldername(name))[2] = auth.uid()::text
    and (storage.foldername(name))[3] is not null
    and lower(right(name, 4)) = '.pdf'
  );

create policy archivos_leer on storage.objects
  for select to authenticated
  using (
    bucket_id = 'documentos'
    and (
      (storage.foldername(name))[1] = organizacion_activa()::text
      or exists (
        select 1 from documentos d
        where d.ruta_archivo = name
          and d.usuario_id = auth.uid()
          and d.eliminado_en is null
      )
    )
  );

-- El borrado del archivo se autoriza por la misma regla que la lectura. Sin esta
-- politica, un usuario no podria borrar su propio archivo, que es lo que exige RF-25.
create policy archivos_borrar on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'documentos'
    and exists (
      select 1 from documentos d
      where d.ruta_archivo = name
        and d.usuario_id = auth.uid()
        and d.eliminado_en is null
    )
  );
```

**La clave del objeto es la ruta, y la ruta codifica el ambito:**
`{organizacion_id}/{usuario_id}/{documento_id}.pdf`. Asi una politica de RLS se resuelve por
prefijo, sin una tabla de busqueda, y el archivo hereda el aislamiento de su documento.

**El archivo no pasa por el backend.** `[DECIDIDO]` La subida va **directo del navegador al
almacenamiento**. Es la recomendacion de la propia documentacion de Vercel para archivos por
encima del limite del cuerpo, y evita que un PDF de 30 MB tenga que atravesar una funcion
de 300 s.

```
1. El navegador calcula el hash del PDF localmente.
2. POST /api/v1/documentos  { nombre_archivo, hash_sha256, total_paginas }
   -> el backend crea el documento (estado 'en_proceso') y el trabajo
   -> responde 201 con { documento_id, trabajo_id, url_subida_firmada }
3. El navegador sube el PDF directo al almacenamiento con esa URL.
4. POST /api/v1/documentos/{id}/archivo  -> el backend guarda la ruta y confirma.
```

El paso 2 tambien **valida el tamano y el tipo antes de firmar la URL**: las URLs firmadas
de Supabase no pueden llevar ni tamano ni tipo, asi que el limite del bucket es la segunda
linea de defensa, no la primera.

**Descarga por URL firmada, de vida corta.** `[DECIDIDO]` El bucket es privado: no hay URL
publica. El backend genera una URL firmada con una vida util de **1 hora** como maximo, solo
para quien tenga el permiso `documentos.ver`, y la registra en auditoria. Una URL firmada
funciona para cualquiera que la tenga, hasta que expira: por eso el TTL es corto y por eso
se genera en el backend, que es quien sabe si el permiso existe.

**El analisis no depende de la subida.** `[DECIDIDO]` Son dos acciones independientes: el
analisis ocurre en el navegador con el archivo local, y la subida es el archivado. El
pipeline nunca espera a la subida, ni al reves. Por eso el documento puede analizarse
aunque la subida falle, y viceversa.

**Retencion.** `[PROPUESTO]` En la v1 los documentos se conservan hasta que el dueno o un
administrador los elimina. No hay expiracion automatica. La politica de retencion real
(cuanto tiempo, con que base legal) es una pregunta abierta (DP-15), porque el destino del
proyecto es una empresa real y ahi la retencion no es una decision de ingenieria.

---

## 6. Pipeline ETL y LLM

### 6.1 Etapas

| Etapa | Entrada | Salida | Componente | Donde corre en la v1 |
|---|---|---|---|---|
| 0. Archivo | PDF local | Archivo en almacenamiento privado | Navegador -> Supabase Storage | Navegador (subida directa) |
| 1. Recepcion | Archivo PDF | Bytes en memoria del navegador | Seleccion de archivo | Navegador |
| 2. Extraccion | PDF | Texto por pagina | `pdf.js` en Web Worker | Navegador |
| 3. Limpieza | Texto por pagina | Texto normalizado | Funcion pura compartida | Navegador |
| 4. Chunking | Texto | Lista de bloques con rango de paginas | Funcion pura compartida | Navegador |
| 5. Map | Bloque + plantilla | JSON validado + resumen parcial | WebLLM | Navegador |
| 6. Reduce | Resumenes parciales | Resumen ejecutivo | WebLLM | Navegador |
| 7. Persistencia | Documento + bloques + analisis | Filas | Caso de uso + puerto de persistencia | Servidor |
| 8. Reporte | Trabajo en curso | Progreso, paso actual, duracion | Caso de uso + puerto de trabajos | Servidor |

**El PDF nunca sale del equipo del usuario.** El servidor recibe unicamente los resultados
ya extraidos, que el backend valida contra el esquema de la plantilla antes de persistir.

`[DECIDIDO]` **Excepcion: el archivo se archiva.** Con ADR-20 el documento se guarda en
almacenamiento privado para poder volver a el. El analisis sigue siendo local: el archivo
sube por archivado, no porque el servidor lo necesite para trabajar.

La consecuencia de privacidad es real y hay que decirla: **el documento ya no se queda en el
equipo del usuario**. El requisito critico del proyecto baja de "el archivo jamas sale" a
"el archivo sale unicamente hacia almacenamiento bajo control del proyecto, con RLS, URL
firmadas de vida corta y borrado a peticion". Ver seccion 3 de `CONTEXTO.md`.

### 6.2 La restriccion que define el chunking

`[DECIDIDO]` **El tamano del bloque se deriva de la ventana de contexto del modelo, no se
fija a mano.**

Los modelos precompilados de WebLLM vienen con una ventana de contexto por defecto de
**4096 tokens**. Un bloque de 10 paginas de texto denso ronda las 4.000 a 6.000 tokens: no
cabe. Con el valor original de 10 paginas, la llamada al modelo se trunca o falla, y el
fallo aparece como "el modelo devuelve basura" en lugar de "el bloque es muy grande".

Formula de calculo:

```
tokens_por_pagina  ~= 600 a 900   (estimado; se calibra con documentos reales)
tokens_reservados  = instruccion + esquema JSON + tokens de salida esperados
paginas_por_bloque = floor((ventana_contexto - tokens_reservados) / tokens_por_pagina)
```

Con la ventana de 4K y una reserva de 1.200 tokens, quedan ~2.900 tokens utiles, es decir
**3 o 4 paginas por bloque**. De ahi el valor por defecto de 3.

**El valor cambia con el motor.** El 3 no esta metido en el codigo: sale de la ventana de
contexto del modelo activo.

| Motor | Ventana | Paginas por bloque (aprox.) | Reduce jerarquico |
|---|---|---|---|
| Modelos de navegador (WebLLM) | 4.096 | 3 | Necesario: 100 paginas producen ~50 resumenes |
| Modelo pequeno en servidor | 8.192 | 8 | Necesario |
| Proveedor hospedado con ventana grande | 200.000 | ~200 (el documento entero) | Innecesario: cabe en una sola pasada |

Por eso el motor es configurable por usuario y por organizacion: el mismo sistema sirve
para un equipo con equipos modestos y para uno con un contrato de empresa con un modelo de
ventana grande, sin cambiar codigo.

Consecuencias que se deducen del camino:

- **El solapamiento tambien consume ventana.** `overlap_paginas` se resta antes de dividir.
- **El Reduce puede desbordarse.** Con 100 paginas y bloques de 3, salen ~50 resumenes
  parciales. A 200 tokens cada uno son ~10.000 tokens: no cabe en 4K. El Reduce debe ser
  **jerarquico**: se agrupan los resumenes en lotes que quepan y se reduce cada lote, y
  luego se reducen los resultados intermedios. Para documentos de hasta ~200 paginas cabe
  en dos niveles.
- **`ventana_contexto` es por modelo, no global.** Cambia el modelo, cambia el chunking.
  La consola de configuracion muestra el valor derivado, no un campo libre.

### 6.3 Donde vive el pipeline

`[DECIDIDO]` En la v1 el pipeline corre **en el navegador**. El frontend:

1. Detecta la capacidad del equipo (`navigator.gpu`, memoria,Cache API).
2. Pide aceptacion explicita y descarga el modelo a Cache API / IndexedDB.
3. Extrae el texto con `pdf.js` en un Web Worker.
4. Divide en bloques con la funcion compartida.
5. Ejecuta Map y Reduce con WebLLM.
6. Envia los resultados a la API, que los valida y persiste.

El backend **no encola nada en la v1**: recibe resultados ya calculados. La cola y el worker
ETL aparecen en la v2, cuando exista el modo servidor.

### 6.4 Salida estructurada del LLM

`[DECIDIDO]` La salida del LLM **se valida contra el esquema de la plantilla antes de
persistir**. Si la validacion falla, se reintenta con el error de validacion en el prompt
(numero de reintentos acotado, por defecto 2). Un JSON invalido nunca llega a la base.

```
plantilla.esquema  ->  modelo Pydantic dinamico  ->  llamada LLM con schema JSON
                    ->  parseo  ->  validacion  ->  reintento o error de dominio
```

WebLLM admite generacion restringida por gramatica (JSON Schema) a traves de
`response_format`. Eso reduce drasticamente los reintentos, pero **no los sustituye**: la
validacion en el backend sigue siendo obligatoria, porque el cliente no es una frontera de
confianza. Verificar la firma exacta en la version fijada de `@mlc-ai/web-llm`
(**0.2.89**, seccion 1.0).

### 6.5 Privacidad en el limite de salida

`[DECIDIDO]` **Por defecto, el port de motor LLM solo tiene implementaciones locales.** La
regla "ningun documento sale a un tercero" se verifica en el adaptador, no en el caso de
uso: el caso de uso no sabe a donde viaja la llamada.

En la v1 esto es literal: **el documento no llega al servidor**. El servidor nunca ve el
PDF, ni su texto, ni sus imagenes.

**El port esta preparado para un proveedor hospedado, pero activarlo es una decision
explicita.** `[DECIDIDO]` Si el cliente tiene un contrato con un proveedor de modelos
(Anthropic, OpenAI u otro), se puede anadir la implementacion correspondiente al port. Pero
eso **cambia la postura de privacidad del producto**, asi que:

1. Requiere un **ADR propio** que registre: que proveedor, que datos salen, que
   regiones, que contrato lo respalda, y quien lo aprobo.
2. **No es un default.** El port arranca con la implementacion local; la hosted se activa
   explicitamente.
3. **No se mezcla**: una peticion no va a un proveedor hospedado y otra a uno local sin que
   el usuario lo sepa. El modo de ejecucion se elige y se muestra.
4. El **texto que sale** sigue siendo el del documento. Por eso la decision exige que el
   contrato del cliente lo cubra de forma explicita, no que "este disponible".

> La razon de que esto sea posible sin reescribir es la decision hexagonal: el motor LLM es
> un puerto, no una llamada embebida. El dia que el cliente traiga su contrato, se escribe
> un adaptador mas. Los casos de uso, el dominio y la interfaz no cambian.

**El cambio de proveedor cambia el chunking, y el sistema lo sabe.** Ver seccion 6.2: el
tamano de bloque se deriva de la ventana de contexto del modelo. Un modelo con ventana de
4K produce bloques de 3 paginas; uno con ventana de 200K produce bloques mucho mas grandes,
y la reduccion jerarquica deja de ser necesaria. Al cambiar de motor, el valor derivado
cambia solo. Por eso `ventana_contexto` es una propiedad del modelo y no un parametro
libre.

### 6.6 Modo hospedado — fuera de la v1

`[DECIDIDO]` **DP-11 cerro en solo navegador.** El proyecto **no** hospeda el modelo: el
usuario es personal administrativo y no va a instalar un LLM ni a tener una GPU que
dimensionar. En consecuencia, la v1 **no necesita**:

- servidor de modelos (ni GPU, ni RAM dedicada),
- worker con ETL en Python,
- cola en el servidor.

Eso baja el costo de operacion a casi cero y hace que todo quepa en Vercel + Supabase.

`[PROPUESTO]` Cuando exista un modo hospedado (hoy no esta previsto), el cambio es:

- El frontend sube el PDF al endpoint de subida, que responde `202`.
- El worker (Docker) ejecuta ETL con PyMuPDF y LLM con Ollama o vLLM.
- El pipeline se mantiene el mismo; solo cambian los adaptadores de ETL y de LLM.
- La cola del servidor (`pgmq`) entra, y el worker corre en un contenedor.
- El contrato de `trabajo` **no cambia**: mismo progreso, misma bitacora, mismos estados.

El caso de uso es el mismo. Esa es exactamente la prueba de que la decision hexagonal era
la correcta.

### 6.7 Seguimiento del trabajo: progreso, duracion y actividades

`[DECIDIDO]` Un analisis es una operacion larga. El usuario tiene que poder saber **cuanto
falta, cuanto lleva y que ha pasado**, sin tener que recargar la pagina ni bloquear la
aplicacion.

**Un modelo unico para los dos modos.** El seguimiento no vive "en el navegador" o "en el
servidor": vive en la tabla `trabajos`, y los dos modos escriben en ella con el mismo
contrato. La UI consume un solo endpoint, y el modelo de datos no cambia cuando el modo
cambia.

| Momento | Quien escribe | Que escribe |
|---|---|---|
| Se lanza el analisis | API | `trabajo` en `en_cola`, `progreso = 0` |
| Empieza a procesar | API o navegador | `estado = en_proceso`, `iniciado_en`, `paso_actual` |
| Avanza | API o navegador | `progreso` y `paso_actual` (monotono) |
| Cada paso | API o navegador | fila en `trabajo_actividades` |
| Termina | API | `estado = completado \| error`, `finalizado_en`, `duracion_ms` |

**Reglas:**

- `progreso` es un entero de 0 a 100 y **nunca disminuye**. Escriba quien lo escriba.
- `progreso` se calcula por fraccion de trabajo conocido, no por tiempo transcurrido: con 34
  bloques, cada bloque vale ~1.7 puntos. Proyectar por tiempo miente cuando un bloque es
  mas lento que otros.
- `paso_actual` es texto para humanos: "analizando bloque 7 de 34". No es un estado de
  maquina: es la ultima cosa que el usuario quiere leer.
- `duracion_ms` se calcula en el servidor a partir de `iniciado_en` y `finalizado_en`. El
  reloj del cliente no es confiable para esto.
- El navegador reporta progreso **al endpoint de reporte**, no escribiendo en la base
  directamente. La base no acepta progreso de un cliente que no sea el dueno del trabajo.

**Cola asincrona: vive en el cliente.** `[DECIDIDO]` Como el LLM se ejecuta en el navegador
(ADR-06), **no hay cola en el servidor** en la v1. El trabajo se hace en el equipo del
usuario, y la asincronia la aportan dos cosas:

1. **El Web Worker**, que ejecuta la extraccion y el LLM sin bloquear la interfaz. La app
   sigue respondiendo mientras se analiza un documento: es exactamente el requisito de que
   la aplicacion no se afecte.
2. **Una cola del lado del cliente**: si el usuario selecciona varios documentos, se
   encolan y se procesan uno a uno, en orden. Cada uno tiene su `Trabajo`.

El servidor no ejecuta el analisis, pero **si es la autoridad sobre el estado**: registra el
trabajo, recibe el progreso y lo persiste. El cliente reporta; el servidor decide.

```
Cliente (navegador)                      Servidor
---------------------                     --------
Usuario selecciona 5 PDFs
 -> crea 5 Trabajos  ------------------>  POST /trabajos  (en_cola)
 -> Web Worker procesa el primero
    -> reporta progreso  --------------->  POST /trabajos/{id}/progreso
    -> al terminar, envia resultados -->  POST /documentos (registro atomico)
 -> siguiente documento...
```

**El estado vive en el servidor, la ejecucion vive en el cliente.** Por eso el contrato de
`trabajo` es el mismo que usaria un worker: si manana se decide anadir un modo hospedado,
el worker consume el mismo contrato y la UI no cambia.

**Trabajo abandonado.** `[DECIDIDO]` Si el usuario cierra la pestana a mitad del analisis, el
trabajo se queda en `en_proceso` para siempre. Se resuelve con dos mecanismos:

- El cliente envia un **latido** con cada reporte de progreso. Un trabajo sin latido por mas
  de N minutos se considera abandonado.
- La **expiracion perezosa** marca los trabajos sin latido como `interrumpido` cuando
  alguien los mira (ADR-24). No hay un proceso que vaya a buscarlos.

Sin esto, un analisis abandonado deja el documento en un limbo que el usuario ve como "en
proceso" para siempre.

**Por que no hay un `cron`.** En Vercel Hobby los Cron Jobs corren **una vez al dia**, y
una expresion mas frecuente **falla el despliegue**. Una tarea cada 2 minutos no es
configurable en el plan que usa el primer despliegue (ADR-21). La expiracion perezosa
resuelve el mismo problema sin depender del plan: el trabajo se limpia la primera vez que
alguien lo mira, que es justo cuando importa.

**Cola en el servidor: para el futuro, no para la v1.** `[PROPUESTO]` Si se anade un modo
hospedado, la cola entra como `pgmq` dentro de Postgres: el mensaje lleva `trabajo_id` y
`documento_id`, y el worker consume desde alli. Se deja documentada porque el diseno del
trabajo ya la contempla, pero **la v1 no la necesita y no debe construirla**.

```
[POST /trabajos]        ->  crea el trabajo (en_cola) y devuelve { trabajo_id }
[POST /trabajos/{id}/progreso]  ->  el cliente reporta progreso y actividades
[POST /documentos]      ->  registra el resultado atomico (documento + bloques + analisis)
                           y marca el trabajo como completado
```

**Actualizacion en la UI.** `[DECIDIDO]` Polling al endpoint de trabajo. Es suficiente para
este volumen y no obliga a mantener conexiones abiertas, lo que es una restriccion real en
plataformas de funciones. Si mas adelante hace falta, el mismo endpoint sirve para SSE.

### 6.8 El artefacto JSON y el DTO de salida

`[DECIDIDO]` **El resultado del analisis es un JSON con los resumenes de todos los bloques y
el resumen ejecutivo**, y ese JSON es lo que se guarda y lo que se consulta.

```json
{
  "documento_id": "...",
  "plantilla": { "id": "...", "version": 1 },
  "total_bloques": 34,
  "resumenes": [
    { "indice": 0, "paginas": "1-3", "resumen": "...", "datos": { } },
    { "indice": 1, "paginas": "4-6", "resumen": "...", "datos": { } }
  ],
  "resumen_ejecutivo": "...",
  "riesgos": [ ]
}
```

**Como se guarda.** `analisis_documentos.resumenes` (JSONB) guarda el arreglo completo;
`resumen_ejecutivo` y `riesgos` se separan porque se consultan y filtran distinto. Los
bloques tambien se guardan en su propia tabla, que es la fuente para el detalle.

**Como se entrega.** El JSON **no** sale crudo de la API. Un DTO de salida lo mapea:

```python
# adapters/http/schemas/analisis.py
class ResumenBloqueResource(BaseModel):
    indice: int
    paginas: str
    resumen: str

class AnalisisResource(BaseModel):
    """Lo que el cliente ve del analisis. La frontera de seguridad."""
    documento_id: UUID
    total_bloques: int
    resumen_ejecutivo: str | None
    riesgos: list[dict]
    resumenes: list[ResumenBloqueResource]
    plantilla_version: int | None

    @classmethod
    def from_model(cls, analisis: Analisis) -> "AnalisisResource":
        # usuario_id, hash_sha256, columnas internas: NO se exponen
        ...
```

Reglas:

- El DTO decide que sale. Agregar un campo a la entidad **no** lo agrega al DTO.
- El DTO **no** contiene logica de negocio ni acceso a datos.
- El `JSONB` de la base es un detalle de persistencia. El DTO es el contrato publico: si
  el JSON cambia de forma, el DTO absorbe el cambio y el frontend no se entera.

**A futuro.** Cuando el sistema guarde registros para responder preguntas (RAG), este JSON
es el punto de entrada: los resumenes por bloque son los fragmentos que se indexan. El
`documento_id` y el `indice` de bloque son las claves que permiten reconstruir de donde sale
cada respuesta. Por eso el JSON se guarda con la referencia a la plantilla y la pagina.

---

## 7. API HTTP

`[DECIDIDO]` REST. Prefijo `/api/v1`. El envelope y los codigos de estado son los del
[SKILL.md](../SKILL.md#19-response--envelope).

| Metodo | Ruta | Descripcion | Auth |
|---|---|---|---|
| GET | `/health` | Sonda de vida y estado de la base | No |
| POST | `/api/v1/auth/logout` | Cierra la sesion y revoca el `session_id` de inmediato | Si |
| POST | `/api/v1/auth/cambiar-contrasena` | Confirma el cambio de la credencial temporal y limpia la bandera | Si |
| GET | `/api/v1/auth/me` | Usuario, rol, organizacion y permisos efectivos | Si |
| GET | `/api/v1/configuracion/motor` | Configuracion efectiva del motor | Si |
| PUT | `/api/v1/configuracion/motor` | Guarda configuracion (usuario u organizacion) | Si |
| DELETE | `/api/v1/configuracion/motor` | Borra la configuracion personal y vuelve a la de la organizacion | Si |
| GET | `/api/v1/plantillas` | Lista plantillas de extraccion activas | Si |
| POST | `/api/v1/plantillas` | Crea plantilla (admin) | Si, `plantillas.editar` |
| GET | `/api/v1/plantillas/{id}` | Detalle de una plantilla y sus versiones | Si |
| PUT | `/api/v1/plantillas/{id}` | Edita la plantilla creando una version nueva | Si, `plantillas.editar` |
| GET | `/api/v1/documentos` | Lista paginada con filtro por estado y ambito | Si |
| POST | `/api/v1/documentos` | Registra el documento y devuelve la URL de subida firmada | Si, `documentos.analizar` |
| POST | `/api/v1/documentos/subir` | Sube el PDF para analisis en servidor (v2) | Si |
| GET | `/api/v1/documentos/{id}` | Detalle, estado y analisis | Si |
| GET | `/api/v1/documentos/{id}/bloques` | Bloques con sus datos estructurados | Si |
| GET | `/api/v1/documentos/{id}/historial` | Analisis anteriores del documento (tras un reanálisis) | Si |
| DELETE | `/api/v1/documentos/{id}` | Soft delete y borrado del archivo archivado | Si, dueno o admin |
| GET | `/api/v1/documentos/{id}/analisis` | Analisis completo (DTO de salida) | Si |
| POST | `/api/v1/documentos/{id}/analisis` | Registra el resultado del analisis y lo persiste | Si (dueno) |
| POST | `/api/v1/documentos/{id}/archivo` | Confirma la subida y guarda la ruta | Si, dueno |
| GET | `/api/v1/documentos/{id}/descarga` | URL firmada de descarga (1 h) | Si, `documentos.ver` |
| POST | `/api/v1/documentos/{id}/reanalisis` | Reanaliza un documento archivado con la plantilla vigente | Si, `documentos.analizar` |
| GET | `/api/v1/trabajos/{id}` | Progreso, paso actual, duracion y actividades | Si |
| POST | `/api/v1/trabajos` | Abre un trabajo para un documento (el cliente lo reporta) | Si |
| POST | `/api/v1/trabajos/{id}/progreso` | El cliente reporta progreso y actividades | Si (dueno) |
| POST | `/api/v1/trabajos/{id}/cancelar` | Cancela un trabajo en curso y libera el documento | Si (dueno) |
| GET | `/api/v1/trabajos` | Listado de trabajos del usuario | Si |
| GET | `/api/v1/usuarios` | Listado de usuarios de la organizacion | Si, admin |
| POST | `/api/v1/usuarios` | Crea un usuario, le asigna rol y envia la credencial temporal | Si, admin |
| PATCH | `/api/v1/usuarios/{id}` | Cambia rol, organizacion o estado | Si, admin |
| POST | `/api/v1/usuarios/{id}/reenviar-credencial` | Genera una credencial temporal nueva y la reenvia por correo | Si, admin |
| GET | `/api/v1/roles` | Catalogo de roles y sus permisos | Si, `organizacion.gestionar` |
| GET | `/api/v1/auditoria` | Bitacora de auditoria de la organizacion, paginada | Si, `auditoria.ver` |

**Por que `GET /api/v1/auth/me` devuelve los permisos efectivos.** La UI los necesita para
ocultar botones y rutas. Si el frontend los obtuviera de `GET /api/v1/roles`, ese endpoint
tendria que estar abierto a todo el mundo, y con el exponiendo el catalogo completo de la
organizacion. Con los permisos efectivos en `me`, `GET /roles` queda para quien administra.

**Por que cambiar la contrasena tiene endpoint propio.** El frontend puede llamar a
Supabase Auth para cambiar la clave, pero entonces nadie limpia
`perfiles.debe_cambiar_contrasena`, y la bandera quedaría diciéndole al usuario que la
cambie cuando ya la cambió. El
backend recibe la peticion, verifica el token, confirma el cambio y limpia la bandera en
la misma operacion.

### 7.0 Ciclo de vida de un analisis

`[DECIDIDO]` **Seis pasos, seis endpoints, y ningun endpoint con dos meanings.** El error
que este diseño evita: usar `POST /api/v1/documentos` tanto para crear el documento como
para entregar el resultado. Dos operaciones con permisos y precondiciones distintas no
comparten una ruta.

| # | Quien | Endpoint | Que hace |
|---|---|---|---|
| 1 | Cliente | `POST /api/v1/documentos` | Registra el documento (nombre, hash, paginas, tamano). Crea el documento en `en_proceso` y devuelve la **URL de subida firmada** |
| 2 | Cliente | `PUT` a Supabase Storage | Sube el PDF **directo** al bucket privado. El PDF no pasa por la funcion |
| 3 | Cliente | `POST /api/v1/documentos/{id}/archivo` | Confirma la subida. El backend verifica el objeto en Storage y guarda `ruta_archivo` |
| 4 | Cliente | `POST /api/v1/trabajos` | Abre el trabajo de analisis para ese documento. Responde `trabajo_id` |
| 5 | Cliente | `POST /api/v1/trabajos/{id}/progreso` | Reporta avance y bitacora mientras corre el pipeline |
| 6 | Cliente | `POST /api/v1/documentos/{id}/analisis` | Registra el resultado. Se valida contra el esquema de la plantilla y se persiste en **una sola transaccion** |

El paso 6 cierra tambien el trabajo: documento en `completado`, trabajo en `completado` y
`duracion_ms` calculada por el servidor. Todo en la misma transaccion.

**Por que el resultado no viaja en el paso 1.** El paso 1 ocurre **antes** de que exista
el archivo: todavia no se sabe si el analisis va a funcionar. Entregar el resultado ahi
obligaria a que el documento existiera antes de saber si se podia procesar.

**Por que el trabajo se abre aparte (paso 4).** Un documento y un trabajo no son lo mismo:
el documento es la entrada, el trabajo es el proceso. Un reanálisis (ADR-25) crea un
trabajo nuevo sobre el mismo documento. Si el trabajo se creara al registrar el
documento, no habria forma de reanalizar sin crear otro documento.

### 7.1 Envelope

```json
{
  "success": true,
  "message": "Analisis registrado",
  "data": { "id": "...", "estado": "completado" },
  "errors": null,
  "timestamp": "2026-11-27T12:00:00Z"
}
```

El codigo HTTP va en el status y en la cabecera, no en el cuerpo.

### 7.2 Paginacion

```json
{
  "data": [],
  "page": 1,
  "size": 20,
  "total": 47,
  "totalPages": 3,
  "hasNext": true,
  "hasPrevious": false
}
```

`page` por defecto 1, `size` por defecto 20, maximo 100. Se **recorta** (clamp), no se
rechaza.

---

## 8. Seguridad

| Aspecto | Decision | Estado |
|---|---|---|
| Autenticacion | **Supabase Auth emite el JWT; el backend lo valida** | `[DECIDIDO]` |
| Autorizacion | RLS en Postgres + **sistema de roles y permisos granular** comprobado en el caso de uso | `[DECIDIDO]` |
| Administracion de usuarios | Crear, asignar rol y desactivar usuarios desde la app, via un **adaptador de administracion** que es el unico autorizado a usar `service_role` | `[DECIDIDO]` |
| Hash de contrasenas | Vive en Supabase Auth. No aplica en este proyecto | `[DECIDIDO]` |
| Sesiones revocables | Las maneja Supabase Auth. No aplica en este proyecto | `[DECIDIDO]` |
| Secretos | Variables de entorno. Ningun valor por defecto utilizable. El arranque falla si falta una obligatoria | `[DECIDIDO]` |
| CORS | Lista de origenes permitidos por entorno, nunca `*` con credenciales | `[DECIDIDO]` |
| Carga de archivos | Validar tipo real (magic bytes), limite de tamano, nombre saneado | `[DECIDIDO]` |
| Logs | Nunca se loguea el contenido del documento ni el texto extraido | `[DECIDIDO]` |

Variables de entorno obligatorias:

| Variable | Default | Nota |
|---|---|---|
| `SUPABASE_URL` | ninguno | Tambien define el emisor del JWT: `{SUPABASE_URL}/auth/v1` |
| `SUPABASE_ANON_KEY` | ninguno | Llave publica para el frontend |
| `SUPABASE_SERVICE_ROLE_KEY` | ninguno | Solo backend. Nunca en el frontend |
| `SUPABASE_JWT_SECRET` | ninguno | Solo para proyectos con claves simetricas (HS256). Los proyectos nuevos usan JWKS |
| `SUPABASE_JWKS_URL` | `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` | Claves publicas para validar tokens asimetricos (RS256/ES256) |
| `DATABASE_URL` | ninguno | Solo para el script de validacion de migraciones en desarrollo |
| `MAX_UPLOAD_MB` | `50` | Solo aplica a partir de la v2 |
| `CORS_ORIGINS` | ninguno | Lista separada por comas |
| `LOG_LEVEL` | `INFO` | |

Variables del frontend (publicas por definicion, `VITE_` las expone al bundle):

| Variable | Default | Nota |
|---|---|---|
| `VITE_SUPABASE_URL` | ninguno | La misma URL del backend |
| `VITE_SUPABASE_ANON_KEY` | ninguno | La llave publica. **Nunca** la `service_role` |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Donde vive la API |

**El `.env.example` se versiona antes de la primera linea de codigo.** Es el contrato
entre la maquina y el proyecto: si una variable no esta en el `.env.example`, no existe.
El `.env` local **no** se versiona nunca (ya esta en `.gitignore`).

```
backend/.env.example
  SUPABASE_URL=https://TU-PROYECTO.supabase.co
  SUPABASE_ANON_KEY=tu-llave-publica
  SUPABASE_SERVICE_ROLE_KEY=tu-llave-de-servicio
  SUPABASE_JWT_SECRET=                      # solo con claves simetricas
  SUPABASE_JWKS_URL=https://TU-PROYECTO.supabase.co/auth/v1/.well-known/jwks.json
  DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
  MAX_UPLOAD_MB=50
  CORS_ORIGINS=http://localhost:5173
  LOG_LEVEL=INFO

frontend/.env.example
  VITE_SUPABASE_URL=https://TU-PROYECTO.supabase.co
  VITE_SUPABASE_ANON_KEY=tu-llave-publica
  VITE_API_BASE_URL=http://localhost:8000
```

### 8.1 Que hace `GET /health`

`[DECIDIDO]` La sonda **no** dice "estoy vivo" sin mas. Consulta una vista publica que
confirma que la base responde y que las migraciones estan aplicadas:

```sql
-- Vista publica: no expone datos de negocio.
create or replace view public.salud as
  select
    (select count(*) from public.roles) as roles_cargados,
    (select count(*) from public.permisos) as permisos_cargados;
```

`GET /health` responde **200** si la consulta devuelve filas y los roles estan cargados, y
**503** si Supabase no responde o el esquema no esta aplicado. Sin `service_role`: la
vista es legible por todos y no contiene datos de usuario.

Un healthcheck que siempre responde 200 no sirve para nada: no distingue "todo bien" de
"la base no esta".

---

## 9. Despliegue

`[DECIDIDO]` El despliegue se organiza en niveles, cada uno con su propia plataforma y su
propia forma de escalar. La separacion no es estetica: es lo que permite migrar un nivel sin
tocar los demas.

| Nivel | Componente | Plataforma v1 | Alternativa portatil |
|---|---|---|---|
| 1 | Frontend Vue (estatico) | Vercel (build estatico) o cualquier CDN | Cloudflare Pages, Netlify, Nginx |
| 2 | API FastAPI (stateless) | Vercel Functions (runtime de Python) | Cloudflare Workers, Fly.io, Docker en cualquier VPS |
| 3 | Datos, identidad y archivos | Supabase (Postgres + Auth + RLS + PostgREST + Storage) | Postgres autogestionado + Auth propio |
| 4 | Worker ETL con LLM hospedado | **No se desplega en la v1** | Docker en Cloud Run / Fly.io, si manana se anade el modo hospedado |

### 9.1 Que significa "Docker para que la migracion sea facil"

`[DECIDIDO]` Se mantiene un `Dockerfile` y un `docker compose` para el entorno de desarrollo
y para el nivel 4. **Vercel no ejecuta contenedores Docker en produccion**: el runtime de
Python de Vercel compila desde el codigo fuente. El Dockerfile sirve para dos cosas
concretas:

1. **Entorno local reproducible**, identico al de produccion, sin depender de que el
   desarrollador tenga Python y las dependencias bien instaladas.
2. **Camino de salida a servidor privado ya escrito.** Si manana se anade el modo hospedado o
   hace falta mover algo, la imagen del worker ya existe y ya esta probada.

**El nivel 4 no se despliega en la v1.** Como el LLM corre en el navegador (ADR-06), la v1
no tiene worker, ni cola, ni servidor de modelos. Todo cabe en tres niveles: Vercel para el
frontend y la API, Supabase para los datos. Eso tambien significa que **la v1 no tiene un
unico punto de falla caro**: sin GPU, sin memoria dedicada, sin cola que perder.

### 9.2 La palanca de portabilidad del backend

`[DECIDIDO]` El nivel 2 se comunica con el nivel 3 **por HTTP, no por una conexion TCP a
Postgres**. Concretamente, usa la API REST de Supabase (PostgREST) reenviando el JWT del
usuario.

Esto no es un detalle menor, es lo que hace que la migracion a Cloudflare Workers sea
trivial:

- Un backend que habla SQL por TCP depende de `asyncpg` y de un socket persistente: eso
  **no** corre en Cloudflare Workers (Pyodide), y obliga a mantener una pieza de
  infraestructura con conexiones abiertas.
- Un backend que habla HTTP con Supabase es **stateless, HTTP adentro y HTTP afuera**:
  corre igual en Vercel Functions, en Cloudflare Workers, en Fly.io y en un contenedor
  Docker, sin cambios de codigo.

Consecuencias que hay que aceptar:

- **PostgREST no tiene transacciones de varias sentencias.** La operacion atomica
  "crear documento + N bloques + analisis" se resuelve con una **funcion de Postgres**
  (`security definer`, con sus propias comprobaciones de RLS) llamada por RPC. La
  transaccion vive dentro de la base de datos, donde pertenece.
- **Las migraciones se aplican con el CLI de Supabase**, no con Alembic. `supabase db push`
  en el despliegue y `supabase db reset` en local. Ver ADR-32.
- El filtrado por RLS sigue funcionando: si el backend reenvia el `Authorization: Bearer`
  del usuario, PostgREST lo usa para evaluar las politicas. Es el mecanismo correcto.

### 9.3 Limites de la plataforma que condicionan el diseno

`[DECIDIDO]` Los limites de Vercel se verificaron contra la documentacion oficial el
2026-11-27. Estos son los que restringen el diseno:

| Limite | Valor | Efecto en este proyecto |
|---|---|---|
| Duracion maxima de la funcion | 300 s por defecto en todos los planes (Fluid compute); 800 s maximo en Pro/Enterprise; 1800 s en beta extendida | La API solo recibe resultados ya calculados: cabe de sobra. **Un ETL de 100 paginas en la funcion no cabe** |
| Tamano del cuerpo de peticion | 4.5 MB por defecto; hasta 20 MiB en beta publica con Fluid compute y `VERCEL_SUPPORT_LARGE_REQUEST_BODY=1` (Node, Python, Bun) | El resultado del analisis (JSON de bloques + resumen) cabe en 4.5 MB. **El PDF no cabe**, lo que refuerza que no se suba |
| Tamano del cuerpo de respuesta | 4.5 MB, exento si es streaming | El listado paginado cabe |
| Memoria | 2 GB / 1 vCPU en Hobby; hasta 4 GB / 2 vCPU en Pro | Suficiente para la API |
| Workers persistentes | Vercel Daemons en beta publica (celery, BullMQ) | El worker ETL **no** corre en Vercel: corre en un contenedor. La cola si puede vivir en Supabase, con `pgmq` |

El limite de 4.5 MB es, en realidad, una confirmacion del diseño: el PDF **no debe** viajar
al servidor en el camino principal.

### 9.4 Colas y asincronia

`[DECIDIDO]` **La v1 no tiene cola en el servidor.** El analisis ocurre en el navegador; el
cliente reporta el progreso al endpoint y la tabla `trabajos` lleva el estado. La asincronia
la dan el Web Worker y la cola del cliente (ver seccion 6.7).

Si manana se anade el modo hospedado, la cola entra como `pgmq` dentro de Postgres: el
mensaje lleva `trabajo_id` y `documento_id`, y el worker consume desde alli.

Por que en la base y no en Redis, cuando llegue:

- **Un componente menos.** Redis seria un servicio adicional que desplegar, monitorear y
  respaldar, para mover mensajes que Postgres ya sabe guardar.
- **Coherencia transaccional.** El mensaje se puede insertar en la **misma transaccion**
  que crea el `trabajo`. Con Redis, o el mensaje existe sin el trabajo, o el trabajo existe
  sin mensaje. Ese es un fallo de entrega que no se ve hasta que alguien pierde un analisis.

El **worker**, en cambio, si necesita un proceso que viva: por eso va en un contenedor
(nivel 4), no en Vercel Functions.

Lo que si hay en la v1 es la **expiracion perezosa** de los trabajos abandonados (la
pestana se cerro a mitad del analisis): cuando alguien consulta un trabajo, un documento o
la lista de trabajos, los que no han reportado latido en mas de 2 minutos se marcan
`interrumpido` en la misma operacion. Es un `update` barato, indexado, y no depende de que
haya un plan de Vercel con cron frecuente. Ver ADR-24.

### 9.5 Perfil de despliegue: la demo gratuita

`[DECIDIDO]` El primer despliegue apunta a **planes gratuitos**, para poder mostrar el
producto sin gastar. ADR-21.

| Pieza | Plan | Limites que importan |
|---|---|---|
| Frontend + API | Vercel Hobby ($0) | 100 GB de transferencia, 1M invocaciones/mes, 4 CPU-h/mes, 100 despliegues/dia |
| Datos | Supabase Free ($0) | 500 MB de base, **1 GB de archivos**, 50 MB maximo por archivo, 50.000 MAU |
| Modelo | En el navegador ($0) | Sin costo variable de inferencia |
| Correo | SMTP incluido de Supabase ($0) | **2 correos por hora**, y solo a correos del equipo |

**Tres limitaciones que hay que conocer antes de la demo, no durante:**

1. **Supabase Free pausa el proyecto a la semana sin uso.** Los datos no se pierden, pero la
   API responde error hasta que se restaura a mano desde el panel. Si la demo es en vivo,
   hay que restaurar **antes** de mostrarla.
2. **El SMTP incluido no sirve para altas de usuarios.** Dos correos por hora y solo a
   correos del equipo: un usuario de prueba con correo real no recibe nada. Durante la demo
   los usuarios se crean desde el panel de Supabase, o se configura un SMTP propio (Resend
   tiene plan gratuito de 3.000 correos/mes).
3. **Vercel Hobby es de uso personal o no comercial.** Si el demo es parte de un trabajo
   facturado, o el cliente paga por el, aplica el plan Pro. No es un limite tecnico: es de
   terminos.

**El costo cuando el proyecto sea real:** Vercel Pro ($20) + Supabase Pro ($25) = $45/mes,
mas el proveedor de correo. Lo que **no** cambia es el modelo: corre en el equipo del
usuario, asi que **el numero de usuarios no mueve el costo**. Ese es el numero que hace
que la demo sea barato de mostrar y que el proyecto sea barato de operar.

**Como se migra si el cliente quiere otra cosa.** Cada pieza tiene su puerto:

| Si el cliente quiere... | Se implementa... | Que se toca |
|---|---|---|
| Su propio S3 o SFTP | `AlmacenamientoS3` / `AlmacenamientoSftp` | El adaptador. Ningun caso de uso |
| Un modelo hospedado con contrato | `MotorLLMAnthropico` (u otro) | El adaptador. **Y un ADR**: cambia la postura de privacidad |
| Otro despliegue | Un `main.py` nuevo | La composicion. Los adaptadores siguen igual |
| Su propio Postgres | Un `Almacenamiento...` no: un `RepositorioSql` | La implementacion del puerto de datos |

Este es el motivo de haber elegido la arquitectura hexagonal: **cada una de esas decisiones
es un archivo nuevo, no un proyecto nuevo**.

---

## 10. Registro de decisiones (ADR)

| ID | Decision | Fecha | Estado | Motivo |
|---|---|---|---|---|
| ADR-01 | Python 3.14.10 + FastAPI 0.165.0 + Vue 3.5.46 | 2026-11-27 | Aceptada | Combinacion actual y estable; versiones verificadas contra PyPI, npm, python.org y los runtimes de Vercel. El pin exacto esta en la seccion 1.0 (ADR-27 y ADR-28) |
| ADR-02 | Nucleo hexagonal (puertos y adaptadores) | 2026-11-27 | Aceptada | Tres adaptadores de salida intercambiables y dos modos de ejecucion del pipeline. Decidirlo antes de escribir codigo, porque revertirlo es caro |
| ADR-03 | Frontend Vue 3.5.46 + Vite + TypeScript + Pinia | 2026-11-27 | Aceptada | Correccion explicita del React del documento original |
| ADR-04 | Acceso a datos por HTTP (PostgREST) en vez de TCP a Postgres | 2026-11-27 | Aceptada | Hace el backend stateless y portable a Cloudflare Workers sin cambios. La atomicidad se resuelve con funciones de Postgres (RPC) |
| ADR-05 | Autenticacion: Supabase Auth emite, el backend valida | 2026-11-27 | Aceptada | Una sola fuente de identidad. Elimina el hashing de contrasenas y la tabla de sesiones propias del alcance |
| ADR-06 | LLM ejecutado en el navegador del usuario como camino principal | 2026-11-27 | Aceptada | Privacidad maxima (el documento no sale del equipo), cero costo de GPU, y encaja con Vercel: sin ETL pesado en el servidor. DP-11 lo confirma: sin modelo hospedado, la v1 no necesita GPU, ni worker, ni cola en el servidor |
| ADR-07 | Despliegue en niveles: Vercel (frontend + API), Supabase (datos), Docker (entorno local) | 2026-11-27 | Aceptada | Vercel no ejecuta Docker en produccion; el Dockerfile sirve para reproducibilidad local y para el camino a servidor privado |
| ADR-08 | El tamano de bloque se deriva de la ventana de contexto del modelo | 2026-11-27 | Aceptada | Los modelos de WebLLM vienen con 4K de contexto; 10 paginas desbordan la ventana |
| ADR-09 | El Reduce es jerarquico | 2026-11-27 | Aceptada | Con bloques de 3 paginas, 100 paginas producen ~50 resumenes que no caben en 4K |
| ADR-10 | La cola de analisis vive en el cliente (Web Worker); el servidor solo lleva el estado | 2026-11-27 | Aceptada | El LLM corre en el navegador, asi que no hay cola en el servidor. El `pgmq` queda documentado para un eventual modo hospedado, no se construye en la v1 |
| ADR-11 | Documentos digitales con capa de texto; sin OCR en la v1 | 2026-11-27 | Aceptada | Un PDF escaneado se marca como error explicito, nunca como analisis vacio |
| ADR-12 | Sistema de roles y permisos granular, con la matriz en datos | 2026-11-27 | Aceptada | El objetivo declarado es controlar que informacion ve cada usuario. La matriz en tablas permite agregar permisos sin desplegar |
| ADR-13 | Administracion de usuarios desde la app, via un adaptador de administracion | 2026-11-27 | Aceptada | Crear y asignar roles es parte del alcance. La `service_role` queda confinada a ese adaptador, con la excepcion documentada |
| ADR-14 | Seguimiento del trabajo en la tabla `trabajos`, con latido para detectar trabajos abandonados | 2026-11-27 | Aceptada | El analisis es largo: hace falta progreso, duracion y bitacora. La cola no es del servidor, pero el estado si es del servidor |
| ADR-15 | El resultado es un JSON de resumenes por bloque + resumen ejecutivo, entregado por DTO | 2026-11-27 | Aceptada | Es el artefacto que consume la UI hoy y que sera el indice del RAG a futuro |
| ADR-16 | El modelo por defecto se puede cambiar desde el panel de configuracion del motor | 2026-11-27 | Aceptada | Un panel con selector de modelo y de parametros, con deteccion automatica de la capacidad del equipo como sugerencia |
| ADR-17 | La visibilidad la determina el permiso, no una regla fija de "propio" o "de la organizacion" | 2026-11-27 | Aceptada | La matriz en datos permite que cada organizacion aplique su propia politica sin cambiar codigo. El `analista` ve lo propio por defecto |
| ADR-18 | Alta de usuarios desde la app, con contrasena autogenerada enviada por correo y confirmacion posterior | 2026-11-27 | Aceptada | Requisito explicito del usuario. Exige un puerto de correo y la excepcion acotada de `service_role` ya documentada |
| ADR-19 | Sin modo hospedado en la v1 | 2026-11-27 | Aceptada | El usuario objetivo es personal administrativo: no va a instalar un LLM ni a tener una GPU. Consecuencia: la v1 no necesita GPU, ni worker, ni cola en el servidor |
| ADR-20 | Los documentos se archivan en Supabase Storage, en un bucket privado, subidos directo desde el navegador | 2026-11-27 | Aceptada | Vercel no puede persistir archivos (sistema de archivos de solo lectura, `/tmp` efimero) y su cuerpo de peticion llega a 4.5 MB. Supabase Storage ya esta en el stack, comparte el JWT y el RLS, y hace que el paso a S3 o SFTP del cliente sea un adaptador mas |
| ADR-21 | El primer despliegue usa planes gratuitos (Vercel Hobby + Supabase Free) | 2026-11-27 | Aceptada | Permite mostrar el producto sin gasto. Se documentan las tres limitaciones del plan gratuito (pausa por inactividad, SMTP de 2 correos/hora, uso no comercial en Hobby) para que se anticipen y no se descubran en vivo |
| ADR-22 | Retencion por defecto: los documentos se conservan hasta que el dueno o un admin los borra, sin expiracion automatica | 2026-11-27 | Aceptada | Es el supuesto que menos impone para la demo. Se cambia por decision del cliente cuando se conozca su politica y su base legal. **No es una politica de retencion final** |
| ADR-23 | El motor LLM, el almacenamiento y el despliegue son intercambiables por diseño; un proveedor de modelos hospedado exige un ADR propio | 2026-11-27 | Aceptada | El cliente puede tener un contrato con un proveedor de modelos, o su propio S3 o SFTP. Los puertos lo permiten; lo que cambia es el adaptador. Un motor hospedado cambia la postura de privacidad, asi que no es un default: se activa explicitamente y queda registrado |
| ADR-24 | El trabajo abandonado se marca `interrumpido` por **expiracion perezosa**, no por un `cron` | 2026-11-27 | Aceptada | Sin un estado que distinga "abandonado" de "en curso", un documento queda en un limbo que el usuario ve como "en proceso" para siempre. La deteccion no puede estar en el cliente: el cliente que cerro la pestana no puede marcar nada. Y no puede depender de un `cron` frecuente: Vercel Hobby corre los cron una vez al dia y una expresion cada 2 minutos falla el despliegue. La expiracion perezosa marca el trabajo la primera vez que alguien lo mira, que es cuando importa. Cierra HU-08 |
| ADR-25 | El reanálisis conserva el análisis anterior en una tabla de historial y actualiza el vigente | 2026-11-27 | Aceptada | "No sobrescribir" es una promesa vacia si no hay donde conservar lo anterior. La tabla aparte evita relajar el `unique` de `analisis_documentos` y deja el historial con su propia forma. Cierra HU-10 y la parte de DP-13 que faltaba |
| ADR-26 | El reanálisis se pide por un endpoint propio y el archivo viaja del bucket privado al navegador, nunca por el backend | 2026-11-27 | Aceptada | Reutilizar `POST /documentos` para el reanálisis mezclaría dos operaciones con permisos y precondiciones distintas. Y el PDF no puede pasar por la funcion: el cuerpo de peticion llega a 4.5 MB. Cierra HU-10 |
| ADR-27 | Las versiones del stack se fijan con pin exacto, verificadas contra los registros oficiales | 2026-11-27 | Aceptada | Un rango abierto ("FastAPI ^0.165") se rompe en produccion, no en el `pyproject.toml`. La tabla de la seccion 1.0 es la unica fuente: si una version cambia, se actualiza la tabla **y** este ADR en el mismo commit |
| ADR-28 | El pin del stack se ajusta a lo que la plataforma de despliegue soporta, no a la ultima version publicada | 2026-11-27 | Aceptada | Python 3.15.2 y TypeScript 7.0.2 son las ultimas versiones de sus respectivos registros, pero **Vercel Functions no ofrece Python 3.15** y **TypeScript 7 rompe `vue-tsc`**. Fijar lo mas nuevo que existe es una promesa que el despliegue no puede cumplir: el error aparece en el primer deploy, no en la revision. Ver 1.0.1 y 1.0.2 |
| ADR-29 | El ciclo de vida de un analisis son seis endpoints: documento, subida, archivo, trabajo, progreso y resultado | 2026-11-27 | Aceptada | `POST /documentos` se usaba tanto para crear el documento como para entregar el resultado: dos operaciones con permisos y precondiciones distintas sobre la misma ruta. Ademas el resultado no puede entregarse al crear el documento, porque todavia no se sabe si el analisis va a funcionar. El documento es la entrada, el trabajo es el proceso, y el resultado llega al final. Ver seccion 7.0 |
| ADR-30 | La respuesta es 403 cuando falta el permiso y 404 cuando la fila no existe; el permiso se comprueba antes que la fila | 2026-11-27 | Aceptada | La mitad de los documentos exigia 403 y la otra mitad 404, para el mismo caso. Ademas hay una restriccion tecnica: cuando RLS filtra una fila de otra organizacion, Postgres devuelve cero filas, y el caso de uso no puede distinguir "no existe" de "ocultado" sin usar `service_role`, que esta prohibido. Comprobar el permiso primero resuelve las dos cosas: si falta, 403 sin consultar nada; si esta, la consulta ya aplico RLS y lo que no aparece es 404 |
| ADR-31 | El backend valida el JWT de Supabase contra el JWKS del proyecto y el cierre de sesion se hace efectivo de inmediato | 2026-11-27 | Aceptada | El emisor real es `{SUPABASE_URL}/auth/v1`; exigir una cadena propia rechazaba todos los tokens reales. Y un JWT stateless no sabe que la sesion se cerro: `signOut()` revoca el refresh token, pero el access token sigue valido hasta su `exp`. Sin un registro de `session_id` revocados, el criterio "401 de inmediato" es falso. El costo es una consulta local indexada, contra una llamada de red por peticion que haria el enfoque alternativo |
| ADR-32 | Las migraciones son SQL puro en `supabase/migrations/`, aplicadas con el CLI de Supabase | 2026-11-27 | Aceptada | Alembic y el CLI de Supabase sobre la misma base se pisan: `supabase db reset` ejecuta el SQL de `supabase/migrations/` y borra la tabla `alembic_version`, y Alembic no sabe desplegar hacia Supabase Cloud. Como el proyecto ya usa el CLI para el stack local, tener las dos herramientas es una fuente de verdad doble. Ademas el CLI es el unico que sabe aplicar las politicas de `storage.buckets` y `storage.objects`, que Alembic no gestiona |
| ADR-33 | El aislamiento se resuelve desde `organizaciones_miembros`, y el esquema se completa con las tablas que las historias ya exigian | 2026-11-27 | Aceptada | `perfiles.organizacion_id` es un solo campo, pero un usuario puede pertenecer a varios equipos: una politica que se apoyara en el perfil le daria acceso a la otra organizacion. Y `organizaciones_miembros` no cubre el caso de un `analista` sin `analisis.ver_todos`, que por la puerta de PostgREST leeria los documentos de sus companeros: la matriz de permisos se esquivaba. El DDL, ademas, estaba desincronizado con las historias: faltaban la tabla de auditoria, la de compartidos, la de sesiones revocadas y varias columnas. Como el esquema todavia no existe en ninguna base, se corrige ahora |
| ADR-34 | Editar una plantilla de extraccion crea una version nueva; la anterior se conserva | 2026-11-27 | Aceptada | Los analisis guardan la version de plantilla que usaron. Si la plantilla se modificara en el sitio, un analisis de hace tres meses quedaria explicando con reglas que ya no son las que se aplicaron, y no habria forma de reconstruir cual era. Versionar tambien permite volver a una version anterior. El precio es una tabla que crece, y una version activa unica garantizada con un indice parcial |

### 10.1 Como se registra una decision nueva

1. Se asigna el siguiente ADR-NN.
2. Se anota decision, fecha, estado y motivo en la tabla.
3. Si la decision cambia la estructura de carpetas, el modelo de datos o el contrato de la
   API, se actualiza la seccion correspondiente de este documento **en el mismo commit**.
4. Si cierra una pregunta abierta, se marca en `DECISIONES-PENDIENTES.md`.

---

## 11. Referencias

- Contexto de producto: [CONTEXTO.md](CONTEXTO.md)
- Preguntas abiertas: [DECISIONES-PENDIENTES.md](DECISIONES-PENDIENTES.md)
- Metodo y contratos de codigo: [../SKILL.md](../SKILL.md)
- Gates de verificacion: [../CHECKLIST.md](../CHECKLIST.md)
- Documento original sin procesar: `docs/legacy/arquitectura-proyecto-analisis-documental.ORIGINAL.md`
- Documento original del skill: `docs/legacy/SKILL.ORIGINAL.md`
