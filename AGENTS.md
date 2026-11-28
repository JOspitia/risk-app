# AGENTS.md — Risk-app

Plataforma web de **analisis privado de documentos**: ETL, extraccion estructurada con un
LLM local y persistencia en Supabase, para ~200 usuarios con roles y aislamiento por
organizacion.

---

## 1. Como trabajar en este repositorio

### 1.1 Orden de lectura obligatorio

Antes de escribir o modificar codigo:

1. `docs/CONTEXTO.md` — que hace el producto y por que.
2. `docs/ARQUITECTURA.md` — stack, estilo arquitectonico, estructura de carpetas, modelo de
   datos.
3. `docs/DECISIONES-PENDIENTES.md` — que falta definir y que supuesto se esta usando.
4. `SKILL.md` — los contratos de codigo. Es normativa, no referencia opcional.
5. `docs/HU/` — la historia de usuario de la funcionalidad que se va a tocar. Ahi esta el
   camino feliz, los caminos de error y los **criterios de aceptacion** que se traducen en
   pruebas.
6. `CHECKLIST.md` — los gates que hay que pasar.

### 1.2 Regla de la informacion faltante

- Todo lo funcional que **no** este en `docs/CONTEXTO.md` o `docs/ARQUITECTURA.md` se marca
  `[ABIERTO]` y se anota en `docs/DECISIONES-PENDIENTES.md`.
- Los cuatro marcadores significan cosas distintas y no son intercambiables:

  | Marcador | Significado |
  |---|---|
  | `[DECIDIDO]` | Esta decidido y documentado. Es un hecho del proyecto |
  | `[PROPUESTO]` | Hay una propuesta, pero el cliente todavia no la confirma |
  | `[ABIERTO]` | **No** hay decision, y hace falta una para continuar |
  | `[PENDIENTE]` | Hay decision, pero falta un **dato** que solo tiene el cliente |

- **No se inventan datos.** No se asumen competidores, normas, funcionalidades, campos de
  negocio ni personas que no esten nombrados. Un campo de riesgo desconocido se marca
  `[PENDIENTE]` en la plantilla, no se rellena con un ejemplo plausible.
- Cuando un supuesto deba implementarse para avanzar, se escribe como supuesto explicito en
  el ADR y en `DECISIONES-PENDIENTES.md`, nunca como hecho.

### 1.3 Decisiones

- Toda decision que cambie estructura de carpetas, modelo de datos o contrato de API se
  registra como **ADR** en la tabla de `docs/ARQUITECTURA.md` seccion 10, con fecha y
  motivo.
- Cerrar una pregunta abierta implica actualizarla en `DECISIONES-PENDIENTES.md` **y** el
  ADR en el mismo commit.

### 1.4 Commits y pull requests

- Los mensajes siguen **Conventional Commits** con el contenido en espanol:
  `<tipo>(<ámbito>): <descripcion>`. La guia completa esta en `CONTRIBUTING.md`.
- Un commit, un objetivo. Si el mensaje necesita una "y", son dos commits.
- `main` solo recibe cambios que pasaron los gates de `CHECKLIST.md`. El trabajo ocurre en
  una rama y llega por pull request.
- Cada commit que implemente un ADR o una HU lo referencia en el pie del mensaje.

---

## 2. Reglas que no se negocian

### 2.1 Privacidad

- El documento original y su texto **no salen** del servidor propio ni del navegador del
  usuario. Nada de OpenAI, Anthropic, Gemini ni ninguna otra API de terceros para contenido
  real.
- En la v1 el ETL y el LLM corren en el navegador. El archivo se archiva en Supabase
  Storage (bucket privado), no porque el servidor lo necesite, sino para poder volver a el.
- La regla se verifica en el **adaptador de salida**, no en el caso de uso: el dominio no
  sabe a donde viaja la llamada.
- El PDF se archiva en almacenamiento privado; se borra cuando se borra el documento, no
  "al terminar el pipeline".
- Logs, traces y metricas nunca contienen texto del documento.

### 2.2 Aislamiento de datos

- RLS activo en toda tabla con datos de usuario.
- El backend no usa `service_role` para atender peticiones de usuario final. La unica
  excepcion es el adaptador de administracion de usuarios, que esta acotado y documentado.
- La pertenencia a la organizacion se verifica en el caso de uso, no solo en la politica.
- Los permisos se comprueban en el caso de uso. Un permiso ausente se deniega.

### 2.3 Contrato de la API

- Envelope unico, codigos de estado de la tabla del `SKILL.md`, paginacion con metadatos.
- Cambiar cualquiera de esas tres cosas es un ADR.

### 2.4 Idioma

- Documentacion, identificadores, comentarios, mensajes de commit y respuestas al usuario:
  **espanol (CO)**.
- Los nombres de tablas, columnas y endpoints van en `snake_case` / `kebab-case` segun el
  estandar de la capa.
- Los textos visibles en la interfaz, en espanol.

### 2.5 Sin abreviaturas impropias

- Se escribe completo: "base de datos", no "BD" en prosa; "por favor", no "pf". En codigo,
  los nombres si pueden ser cortos si son claros.

---

## 3. Convenciones de codigo

Las reglas finas viven en `SKILL.md`. Lo no negociable en resumen:

| Tema | Regla |
|---|---|
| Dominio | `domain/` no importa nada de `adapters/`, `application/` ni de frameworks |
| Casos de uso | No conocen HTTP. Devuelven DTOs, no entidades crudas |
| Errores | Errores de dominio con semantica HTTP propia. Nunca re-envueltos en genericos |
| Consultas | Parametrizadas siempre. Columnas desde una constante compartida |
| Transacciones | La abre el caso de uso. Una transaccion, un commit |
| Secretos | Variables de entorno. El arranque falla si falta una obligatoria |
| Validacion | La salida del LLM se valida contra esquema antes de persistir |
| Tests | Un endpoint no esta terminado hasta que tiene una prueba que falla si el endpoint esta mal |

---

## 4. Estructura de carpetas

El arbol completo esta en `docs/ARQUITECTURA.md` seccion 3. Version resumida:

```
backend/app/
  domain/        entidades, value objects, ports, reglas puras, errores
  application/   casos de uso, DTOs, auditoria, unit of work
  adapters/      http/ supabase/ llm/ etl/ storage/ queue/
  worker/        consumidor de la cola
frontend/src/
  api/ stores/ views/ components/ workers/ shared/
```

---

## 5. Comandos

Los comandos exactos. La guia completa de arranque esta en
[`docs/ARRANQUE.md`](docs/ARRANQUE.md).

```
# Backend (en backend/)
uv sync                # instala dependencias
uv run pytest          # suite completa
uv run pytest -m unit  # solo unitarias, sin base de datos
uv run ruff check .    # lint
uv run ruff format .   # formato
uv run mypy app        # tipos
uv run lint-imports    # contratos de la frontera hexagonal

# Migraciones (en la raiz)
supabase db reset      # aplica las migraciones en la base local (ADR-32)
supabase db push       # aplica las migraciones en el proyecto de Supabase

# Frontend (en frontend/)
npm install --legacy-peer-deps  # ver docs/ARRANQUE.md: openapi-typescript exige TS 5
npm run dev            # servidor de desarrollo
npm run typecheck      # vue-tsc sobre los .vue
npm run build          # typecheck + build de produccion
npm run test           # tests del frontend
npm run lint           # eslint
npm run api:types      # regenera los tipos desde el OpenAPI del backend
```

> Si un comando de build solo compila las fuentes de produccion, no se usa para validar. Un
> build que no incluye los tests reporta exito con los tests rotos.

> **`lint-imports` no es opcional.** Es el que verifica la invariante hexagonal: el
> `domain/` no importa nada de `application/`, `adapters/` ni de frameworks. Una
> violacion rompe la integracion continua antes de que rompa la revision.

---

## 6. Version del stack

**Pin exacto.** La tabla completa esta en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md)
seccion 1.0 (ADR-27). Lo que se ve al retomar el proyecto:

| Componente | Version | Verificado |
|---|---|---|
| Python | 3.14.10 | 2026-11-27 |
| FastAPI | 0.165.0 | 2026-11-27 |
| supabase (SDK de Python) | 2.34.1 | 2026-11-27 |
| Vue | 3.5.46 | 2026-11-27 |
| Vite | 8.4.0 | 2026-11-27 |
| TypeScript | 6.0.3 | 2026-11-27 |
| vue-tsc | 3.3.14 | 2026-11-27 |
| Node.js | 24 o 26 (LTS) | 2026-11-27 |
| @supabase/supabase-js | 2.119.2 | 2026-11-27 |
| @mlc-ai/web-llm | 0.2.89 | 2026-11-27 |
| Supabase CLI | 3.4.0 | 2026-11-27 |
| PostgreSQL | 17 (via Supabase) | 2026-11-27 |

> **Python 3.14, no 3.15, y TypeScript 6, no 7.** No es que esten mal: es que Vercel
> Functions no ofrece Python 3.15 y TypeScript 7 no expone la API que necesita `vue-tsc`.
> El pin sigue al entorno de despliegue real. El detalle esta en `ARQUITECTURA.md` secciones
> 1.0.1 y 1.0.2 (ADR-28).

Si al retomar el proyecto una de estas versiones ya no es la actual, verificar contra los
registros oficiales (PyPI, npm, nodejs.org) y **registrar el cambio como ADR** antes de
actualizar el codigo. La tabla de `ARQUITECTURA.md` seccion 1.0 es la unica fuente de
verdad: las dos se actualizan en el mismo commit.

### 6.1 Decisiones vigentes que no se negocian sin ADR

| Decision | Consecuencia practica |
|---|---|
| Nucleo hexagonal | `domain/` no importa nada de `adapters/` ni de frameworks |
| Autenticacion: Supabase Auth | No hay endpoint de emision de tokens propio, ni hashing de contrasenas, ni tabla de sesiones |
| Roles y permisos granulares | La matriz vive en datos (`permisos`, `rol_permisos`). El permiso se comprueba en el caso de uso, nunca solo en el router |
| Administracion de usuarios en la app | Un solo adaptador puede usar `service_role`. Todo lo demas propaga el JWT del usuario y deja que RLS filtre |
| LLM en el navegador (v1) | El pipeline ETL + LLM vive en el frontend; la API solo persiste resultados validados |
| Cola de analisis del lado del cliente | El Web Worker ejecuta el pipeline y el servidor lleva el estado en `trabajos`. Sin cola en el servidor |
| Sin modo hospedado en la v1 | El LLM corre en el navegador. La v1 no necesita GPU, ni worker, ni servidor de modelos |
| Seguimiento en la tabla `trabajos` | Un solo modelo para los dos modos: progreso monotono, paso actual y duracion calculada en el servidor |
| Datos por HTTP (PostgREST/RPC) | Sin conexion TCP a Postgres en el camino de ejecucion. La atomicidad va en funciones de Postgres |
| Archivos en Supabase Storage | Bucket privado, subida directa desde el navegador, URL firmada de 1 h. Vercel no puede persistir archivos ni aceptar un PDF de 30 MB |
| Retencion por defecto | Se conserva hasta que el dueno o un admin borra. Sin expiracion automatica. Es un supuesto, no una politica final |
| Proveedores intercambiables | Motor LLM, almacenamiento y despliegue son puertos. Cambiar de proveedor es un adaptador nuevo, no un proyecto nuevo. Un motor hospedado exige ADR |
| Despliegue en niveles | Vercel (frontend + API), Supabase (datos y archivos), Docker (local) |
| Tamano de bloque derivado | Se calcula de la ventana de contexto del modelo, no se fija a mano |

---

## 7. Mapa del repositorio

| Ruta | Que es |
|---|---|
| `docs/CONTEXTO.md` | Producto: que hace, para quien, con que restricciones |
| `docs/ARQUITECTURA.md` | Stack, arquitectura, carpetas, modelo de datos, ADR |
| `docs/DECISIONES-PENDIENTES.md` | Preguntas abiertas con impacto y supuestos |
| `docs/HU/` | Historias de usuario: camino feliz, caminos de error y criterios de aceptacion |
| `docs/ARRANQUE.md` | Guia de arranque local: requisitos, comandos, orden de trabajo |
| `SKILL.md` | Metodo y contratos de codigo (skill instalable) |
| `CHECKLIST.md` | Gates de verificacion |
| `CONTRIBUTING.md` | Convencion de commits y pull requests |
| `backend/` | Codigo de la API (FastAPI). `app/`, `tests/`, `api/` |
| `frontend/` | Codigo de la SPA (Vue 3.5). `src/`, `workers/` |
| `supabase/` | `config.toml` y `migrations/*.sql`: el esquema del proyecto |
| `shared/` | Fixtures compartidas entre Python y TypeScript (casos dorados del chunking) |
| `docs/legacy/` | Documentos originales sin procesar. No se editan |
