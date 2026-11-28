# Arranque local

Como se levanta Risk-app en una maquina nueva. El detalle de **que** es el producto
esta en [docs/CONTEXTO.md](docs/CONTEXTO.md); el de **como** esta en
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

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

### Comandos de verificacion

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

---

## 4. Base de datos local

```bash
supabase start          # Postgres + Auth + PostgREST + Storage en local
supabase db reset       # aplica las migraciones de supabase/migrations/
```

Las migraciones son **SQL puro** en `supabase/migrations/` y las aplica el CLI de
Supabase. No hay Alembic ni tabla `alembic_version` (ADR-32). El esquema nunca se
edita a mano: cada cambio es una migracion nueva.

> `supabase db reset` **borra** los datos de la base local. Es lo esperado: rehace
> el esquema desde cero.

Las variables del `.env` para la base local:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<la que imprime `supabase start`>
SUPABASE_SERVICE_ROLE_KEY=<la que imprime `supabase start`>
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
```

---

## 5. Orden de trabajo

El proyecto es incremental y cada capa se apoya en la anterior:

1. **Esqueleto** (este documento): estructura, configuracion, dependencias.
2. **Migracion**: esquema, RLS, matriz de permisos y bucket, contra una base vacia.
3. **Contratos**: envelope, codigos de estado, paginacion y OpenAPI.
4. **Adaptadores**: Supabase, almacenamiento, correo.
5. **Casos de uso**: permisos, transacciones, auditoria.
6. **Frontend**: sesion, documentos, motor, pipeline en el navegador.
7. **Pruebas**: unitarias, de integracion contra Supabase real y de contrato.

El pipeline de la v1 corre **en el navegador**: el backend persiste resultados
validados, no ejecuta el modelo (ADR-06).
