---
name: riskapp-arquitectura
description: |
  Metodo y contratos de codigo del proyecto Risk-app (analisis privado de documentos:
  FastAPI + Vue + Supabase). Define los 9 contratos de la API (Request, Controller,
  Service, Repository, Model, Resource, Response, Exception, Auth filter), la invariante de
  dependencias, el gate de decision por entidad, el baseline de seguridad, las transacciones,
  la paginacion, el contexto de auditoria, las reglas del pipeline ETL/LLM, las convenciones
  de Vue, la estrategia de pruebas y los gates de verificacion.
  Trigger on: "crear un endpoint", "anadir una entidad", "revisar la arquitectura", "por que
  el router llama al repositorio", "que estructura de carpetas usamos", "como hago el
  repositorio", "escribe el caso de uso", "reglas del proyecto", "queReviso antes de
  entregar", "estructura del backend", "convenciones del frontend", "refactorizar el
  pipeline", "nueva tabla", "migracion".
  Use also when: se agrega un endpoint, un caso de uso, un puerto, un adaptador, una
  migracion, una plantilla de extraccion, o una pantalla nueva. Use for: revisar codigo
  existente del proyecto contra los contratos antes de darlo por terminado.
  Do NOT use for: proyectos que no sean Risk-app, ni para decidir la arquitectura (eso vive
  en docs/ARQUITECTURA.md y docs/DECISIONES-PENDIENTES.md), ni para la entrega de
  Assignments del MGA.
---

# Risk-app — Metodo y contratos de codigo

Este documento es la **normativa de codigo** del proyecto. Dice como se escribe, no que se
construye: el producto esta en `docs/CONTEXTO.md` y las decisiones tecnicas en
`docs/ARQUITECTURA.md`.

La idea central: **cada pieza tiene exactamente un trabajo, las dependencias apuntan en una
sola direccion, y cada logica vive en un solo lugar.**

---

## Indice

1. [Los 9 contratos](#1-los-9-contratos)
2. [Gate de decision por entidad](#2-gate-de-decision-por-entidad)
3. [Quick start](#3-quick-start-como-se-levanta-un-proyecto-nuevo)
4. [Reglas de datos](#4-reglas-de-datos)
5. [Baseline de seguridad](#5-baseline-de-seguridad)
6. [Transacciones](#6-transacciones)
7. [Inyeccion de dependencias](#7-inyeccion-de-dependencias)
8. [Paginacion](#8-paginacion)
9. [Contexto de auditoria](#9-contexto-de-auditoria)
10. [Pipeline ETL y LLM](#10-pipeline-etl-y-llm)
11. [Convenciones del frontend](#11-convenciones-del-frontend-vue-35)
12. [Errores frecuentes](#12-errores-frecuentes-aprendidos-a-la-fuerza)
13. [Estrategia de pruebas](#13-estrategia-de-pruebas)
14. [Checklist de verificacion](#14-checklist-de-verificacion)
15. [Como se trabaja: la HU guia, el checklist verifica](#15-como-se-trabaja-la-hu-guia-el-checklist-verifica)
16. [Gate de readiness](#16-gate-de-readiness-el-backend-esta-listo-para-un-frontend)
17. [Anadir una entidad nueva](#17-anadir-una-entidad-nueva)

---

## 1. Los 9 contratos

### 1.1 La invariante

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
[Adaptadores de salida] <- Supabase, LLM, storage, cola
    |
    v
[Entidad de dominio]
```

**Las dependencias apuntan hacia adentro y a un solo lado.**

- El router puede llamar al caso de uso. **No** puede llamar al repositorio.
- El caso de uso puede llamar a los puertos. **No** puede conocer HTTP, JSON ni SQL.
- El adaptador de salida implementa un puerto. **No** decide nada: mapea filas, no politicas.
- El dominio no conoce ningun framework: ni FastAPI, ni SQLAlchemy, ni Pydantic.

> La violacion mas comun: un router que consulta el repositorio para verificar propiedad o
> existencia. Eso es logica de negocio vestida de controller. Va en el caso de uso.

### 1.2 Tabla de mapeo (capas <-> hexagonal)

La version anterior de este skill especificaba una API REST en capas. Los contratos se
conservan; lo que cambia es el vocabulario y donde viven las interfaces.

| Capa (skill original) | Contrato | Rol en Risk-app | Ubicacion |
|---|---|---|---|
| Request | DTO de entrada | Esquema de entrada del adaptador | `adapters/http/schemas/` |
| Controller | Router | **Adaptador de entrada** | `adapters/http/routers/` |
| Service | Logica de negocio | **Caso de uso** | `application/use_cases/` |
| Service interface | Contrato de servicio | **Puerto** del caso de uso | `domain/ports/` |
| Repository interface | Contrato de datos | **Puerto de salida** | `domain/ports/` |
| Repository impl | SQL | **Adaptador de salida** | `adapters/supabase/` |
| Model | Entidad | **Entidad de dominio** | `domain/entities/` |
| Resource | DTO de salida | **Mapper de salida** | `adapters/http/schemas/` |
| Response | Envelope | **Envelope de API** | `adapters/http/responses.py` |
| Exception | Errores de dominio | **Errores de dominio** + mapeo a HTTP | `domain/errors.py`, `adapters/http/error_handlers.py` |
| Auth filter | Filtro de autenticacion | **Middleware + guard** | `adapters/http/middleware.py`, `deps.py` |
| Audit context | Contexto de auditoria | Contexto transversal | `application/audit/` |
| Transaction manager | Unit of work | **Unit of work** (puerto) | `application/unit_of_work.py` |

**En ambos estilos la regla de dependencia es la misma.** La version hexagonal cambia una
cosa: **la interface la define el dominio y la implementa la infraestructura**, no al reves.

### 1.3 Request (DTO de entrada)

**Hace:** recibir datos del cliente, validacion declarativa, inmutabilidad.
**No hace:** logica de negocio, acceso a base de datos.
**Regla:** si necesitas mutarlo despues de recibirlo, esta en el lugar equivocado.

```python
# adapters/http/schemas/analisis.py
from pydantic import BaseModel, Field, field_validator

class CrearAnalisisRequest(BaseModel):
    """Comando de entrada. Cero logica de negocio."""

    documento_id: str = Field(description="UUID del documento a procesar")
    plantilla_id: str | None = Field(
        default=None,
        description="Plantilla de extraccion a aplicar. Si se omite, la activa de la organizacion",
    )

    model_config = {"extra": "forbid"}
```

`extra = "forbid"` es una decision consciente: un cliente que manda una clave desconocida
recibe 422 en vez de un 400 silencioso. Es comportamiento deliberado y esta documentado.

### 1.4 Controller / Adaptador de entrada

**Hace:** recibir el request, delegar validacion, llamar al caso de uso, mapear
dominio -> Resource, elegir el status HTTP, mapear errores de dominio a status, recibir el
contexto de auditoria.
**No hace:** logica de negocio, SQL, verificaciones de propiedad, transformaciones de datos.
**Regla:** si copias este router a otro proyecto y solo cambia el negocio, esta en el lugar
equivocado.

```python
# adapters/http/routers/documentos.py
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/api/v1/documentos", tags=["documentos"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def crear_documento(
    cmd: CrearAnalisisRequest,
    ctx: AuditContext = Depends(contexto_auditoria),
    caso: CrearDocumento = Depends(caso_crear_documento),
):
    """Sube un documento y encola el analisis. Responde 202: el analisis no se completa aqui."""
    documento = await caso.ejecutar(cmd, ctx)
    return Respuesta.ok(
        data=DocumentoResource.from_model(documento),
        mensaje="Documento en proceso",
    )
```

Lo que el router **no** tiene: un `if usuario_id != documento.usuario_id`, un `await
repo.find_by_id(...)`, un `try/except` que reenvuelva en `HTTPException(500)`.

### 1.5 Service / Caso de uso

**Hace:** reglas de negocio reales, normalizacion, orquestacion de varios pasos,
transacciones, validaciones de negocio (duplicado, propiedad, transiciones de estado),
auditoria.
**No hace:** HTTP, JSON, SQL crudo, construccion de Resources.
**Regla:** dos o mas llamadas a la base de datos, o cualquier condicional sobre un resultado
de la base -> esto es un caso de uso.

```python
# application/use_cases/crear_documento.py
from dataclasses import dataclass

@dataclass(frozen=True)
class CrearDocumento:
    documentos: DocumentoRepository      # puerto
    documentos_por_hash: DocumentoPorHash  # puerto
    storage: Almacenamiento              # puerto
    cola: ColaDeTrabajos                # puerto
    reloj: Reloj                       # puerto
    uow: UnitOfWork                    # puerto

    async def ejecutar(self, cmd, ctx: AuditContext) -> Documento:
        # 1. Politica de negocio: no reprocesar el mismo archivo.
        previo = await self.documentos_por_hash.buscar(cmd.hash_sha256, ctx.usuario_id)
        if previo is not None:
            raise DocumentoDuplicadoError(previo.id)

        # 2. Regla de negocio: el estado arranca en en_proceso.
        documento = Documento(
            usuario_id=ctx.usuario_id,
            organizacion_id=ctx.organizacion_id,
            nombre_archivo=cmd.nombre_archivo,
            hash_sha256=cmd.hash_sha256,
            modo_procesamiento=cmd.modo,
            estado=EstadoDocumento.EN_PROCESO,
            creado_en=self.reloj.ahora(),
        )

        # 3. La transaccion la abre el caso de uso, no el repositorio.
        async with self.uow.transaccion() as u:
            documento_id = await u.documentos.crear(documento)

        # 4. Encolar. El pipeline NO corre dentro del request.
        await self.cola.encolar(documento_id=documento_id)

        await ctx.auditoria.registrar("documento.creado", documento_id)
        return documento
```

> **Nunca reenvuelvas un error de dominio en un error generico.** Los errores de dominio
> ya son unchecked y llevan su propia semantica HTTP. Si los capturas y los conviertes en
> un `RuntimeError`, el manejador global deja de reconocerlos y cada error de negocio se
> degrada en 500. Es un fallo silencioso y total del mapeo de errores.
> **Prueba:** dispara un error de dominio y afirma el codigo de estado exacto. Si todo
> devuelve 500, lo reenvuelto.

### 1.6 Repository / Puerto de salida

**Hace:** una consulta por metodo, mapeo fila -> entidad, manejo de conexion.
**No hace:** logica de negocio, encadenar un metodo de repositorio con otro, ramificar
sobre el resultado de la consulta.
**Regla:** `listar` / `obtener_por_id` / `crear` / `actualizar` / `eliminar` — una operacion
por metodo.

Dos convenciones que se adoptan:

- **Una interfaz por repositorio.** Permite probar sin base de datos y aplica la inversion de
  dependencias.
- **Variantes con sesion.** Cada metodo de escritura recibe la sesion abierta, para que el
  caso de uso la incluya en su transaccion.

```python
# domain/ports/documentos.py
from typing import Protocol, Sequence
from uuid import UUID

class DocumentoRepository(Protocol):
    """Puerto de salida. Lo define el dominio, lo implementa la infraestructura."""

    async def listar(
        self,
        usuario_id: UUID,
        organizacion_id: UUID | None,
        estado: str | None,
        pagina: int,
        tamano: int,
    ) -> tuple[Sequence[Documento], int]: ...

    async def obtener_por_id(self, documento_id: UUID) -> Documento | None: ...

    async def obtener_por_hash(
        self, hash_sha256: str, usuario_id: UUID
    ) -> Documento | None: ...

    async def crear(self, documento: Documento) -> UUID: ...

    async def marcar_completado(
        self, documento_id: UUID, total_paginas: int
    ) -> None: ...

    async def marcar_error(self, documento_id: UUID, mensaje: str) -> None: ...
```

```python
# adapters/supabase/documentos.py
from supabase import AsyncClient

class DocumentoRepositorySupabase:
    """Implementa el puerto con el cliente HTTP de Supabase (PostgREST).

    La peticion lleva el JWT del usuario: PostgREST lo usa para evaluar las politicas
    RLS. Por eso el repositorio no decide la visibilidad.
    """

    def __init__(self, cliente: AsyncClient) -> None:
        self._cliente = cliente

    async def obtener_por_id(self, documento_id: UUID) -> Documento | None:
        respuesta = await self._cliente.table("documentos").select(
            "*",
        ).eq("id", str(documento_id)).is_("eliminado_en", "null").limit(1).execute()
        filas = respuesta.data
        return mapear_a_entidad(filas[0]) if filas else None
```

> **Este adaptador no usa SQLAlchemy ni `asyncpg`.** El acceso a datos es por HTTP
> (ADR-04): el backend no abre una conexion TCP a Postgres en el camino de ejecucion. Asi
> el servicio es stateless y portable a runtimes sin conexiones persistentes.
>
> **Lo que si necesita SQL es la atomicidad**, y por eso existe el puerto de RPC: hay
> operaciones que deben ser una transaccion (registrar un analisis completo, mover un
> analisis al historial). Esas se resuelven con funciones de Postgres (`security definer`,
> con `set search_path = public` y sus propias comprobaciones de permiso), llamadas por
> RPC. La transaccion vive dentro de la base, donde pertenece. Ver seccion 6.1.
>
> **El repositorio mapea filas, no politicas.** Que un documento sea visible lo decide
> RLS y el permiso; el repositorio solo traduce.

### 1.7 Model / Entidad de dominio

**Hace:** representar el dominio, inmutable, sin anotaciones de framework si se puede evitar.
**No hace:** HTTP, JSON, SQL, logica de aplicacion. **Nunca concerns de serializacion.**

```python
# domain/entities/documento.py
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

class EstadoDocumento(StrEnum):
    EN_PROCESO = "en_proceso"
    COMPLETADO = "completado"
    ERROR = "error"

@dataclass(frozen=True)
class Documento:
    id: UUID
    usuario_id: UUID
    organizacion_id: UUID | None
    nombre_archivo: str
    hash_sha256: str
    total_paginas: int | None
    modo_procesamiento: str
    estado: EstadoDocumento
    error_mensaje: str | None
    creado_en: datetime
```

La entidad **no** lleva `password_hash`, ni `eliminado_en`, ni columnas de auditoria
internas. Eso vive en el modelo de persistencia, que es otra cosa.

### 1.8 Resource (DTO de salida) — la frontera de seguridad

**Hace:** decidir que campos salen de la API, transformar formatos (timestamp -> string
ISO-8601), desacoplar el versionado de la API del dominio.
**No hace:** logica de negocio, acceso a base de datos.
**Regla:** agregar un campo a la entidad **no** debe agregar automaticamente el campo al
Resource.

> **Nunca devuelvas una entidad de dominio directamente desde un router.** Eso elimina el
> unico proposito de la capa Resource. Cualquier campo sensible del modelo — hash de
> contrasena, llaves internas, banderas de soft delete, columnas de auditoria — se filtra
> de forma automatica, silenciosa y permanente.
> **Prueba:** inspecciona el cuerpo real de la respuesta HTTP. Busca en el cada secreto que
> carga el modelo.

```python
# adapters/http/schemas/documento.py
class DocumentoResource(BaseModel):
    """Lo que el cliente ve. La frontera de seguridad de la API."""

    id: UUID
    nombre_archivo: str
    total_paginas: int | None
    modo_procesamiento: str
    estado: str
    error_mensaje: str | None
    creado_en: datetime          # serializado en ISO-8601 por configuracion global

    @classmethod
    def from_model(cls, documento: Documento) -> "DocumentoResource":
        # usuario_id, hash_sha256, organizacion_id interna: NO se exponen
        return cls(
            id=documento.id,
            nombre_archivo=documento.nombre_archivo,
            total_paginas=documento.total_paginas,
            modo_procesamiento=documento.modo_procesamiento,
            estado=documento.estado.value,
            error_mensaje=documento.error_mensaje,
            creado_en=documento.creado_en,
        )
```

### 1.9 Response / Envelope

**Hace:** envolver toda respuesta de la API.
**No hace:** logica de negocio, acceso a base de datos.
**Regla:** el cliente recibe `success`, `message`, `data`, `errors`, `timestamp`. El estado
HTTP va en el status y en la cabecera: repetirlo en el cuerpo es redundante y filtra
detalle de implementacion.

```python
# adapters/http/responses.py
from datetime import datetime, timezone
from typing import Generic, TypeVar

T = TypeVar("T")

class Respuesta(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T | None = None
    errors: list["DetalleError"] | None = None
    timestamp: datetime

    @classmethod
    def ok(cls, data: T, mensaje: str = "OK") -> "Respuesta[T]":
        return cls(
            success=True,
            message=mensaje,
            data=data,
            errors=None,
            timestamp=datetime.now(timezone.utc),
        )
```

### 1.10 Exception / Errores

**Hace:** cada error de dominio lleva su propia semantica HTTP; un manejador global los
mapea.
**No hace:** depender de errores genericos de runtime.

| Error de dominio | Status |
|---|---|
| `ValidacionError` | 400 |
| `NoAutenticadoError` | 401 |
| `ProhibidoError` | 403 |
| `NoEncontradoError` | 404 |
| `ConflictoError` / `DocumentoDuplicadoError` | 409 |
| `PayloadDemasiadoError` | 413 |
| `ErrorInesperado` | 500 |

```python
# domain/errors.py
class ErrorDominio(Exception):
    """Base. Los errores de dominio son unchecked y no se reenvuelven."""
    codigo: str = "error_dominio"
    status_http: int = 500
    mensaje: str = "Error inesperado"

class DocumentoDuplicadoError(ErrorDominio):
    codigo = "documento_duplicado"
    status_http = 409
    def __init__(self, documento_id: UUID) -> None:
        super().__init__(f"El documento {documento_id} ya fue procesado")
        self.documento_id = documento_id
```

```python
# adapters/http/error_handlers.py
@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(request: Request, exc: ErrorDominio) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_http,
        content={
            "success": False,
            "message": str(exc),
            "data": None,
            "errors": [{"codigo": exc.codigo, "detalle": str(exc)}],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
```

### 1.11 Auth filter (middleware)

**Hace:** extraer la credencial del header, validar firma / expiracion / emisor, resolver el
usuario, construir el contexto de auditoria.
**No hace:** decidir permisos. Eso lo hace el caso de uso o el guard.

**Regla de la v1:** la emision del token depende de DP-05 (Supabase Auth o JWT propio). Las
dos variantes:

| Variante | Que hace el backend | Que aplica del baseline |
|---|---|---|
| Supabase Auth | Valida el JWT de Supabase (firma, `exp`, `aud`, `role`) y resuelve `sub` | Sin hashing de contrasenas, sin tabla de sesiones propias |
| JWT propio | Emite, firma, guarda `sha256(token)` en tabla de sesiones, revoca | Todo el baseline de la seccion de seguridad |

En ambos casos el backend **nunca** usa la `service_role` para atender peticiones de
usuario final: eso desactiva RLS y deja el aislamiento en manos del codigo de aplicacion
solamente.

```python
# adapters/http/middleware.py
class ContextoAuditoriaMiddleware(BaseHTTPMiddleware):
    """Construye el contexto antes del handler. Credenciales invalidas -> contexto
    anonimo, no 401 inmediato. Los endpoints protegidos llaman a un guard."""

    async def dispatch(self, request, call_next):
        request.state.auditoria = await self._construir_contexto(request)
        return await call_next(request)
```

---

## 2. Gate de decision por entidad

**No todas las entidades necesitan los 9 contratos.** Suponer que si produce abstracciones
vacias: un `Create` para una entidad que el cliente nunca crea, un servicio que solo hace
passthrough al repositorio.

Se aplica por entidad, de arriba abajo:

| Pregunta | Si es SI | Si es NO |
|---|---|---|
| 1. ¿El **cliente envia campos** para crearla o modificarla? | Construye un **Request** | Omite Request. Nombralo `<Entity>Command` si quieres claridad |
| 2. ¿El **cliente la lee** de vuelta? | Construye un **Resource** | Omite Resource |
| 3. ¿Tiene **reglas de negocio** mas alla de CRUD: transiciones de estado, unicidad, propiedad, limites? | Construye un **caso de uso** | Un caso de uso solo-passthrough es peso muerto |
| 4. ¿Tiene **campos sensibles**? | Construye un **Resource** aunque la 2 sea NO | - |
| 5. ¿Es **solo del servidor** (sesiones, auditoria, trabajos)? | Omite Request y usualmente omite caso de uso: el creador es el dueño | - |

### 2.1 Ejemplo trabajado: por que existe el gate

Una entidad `Sesion` que respalda la revocacion de tokens:

- ¿El cliente envia campos para crearla? **No**: el servidor la crea durante el login.
  -> **Sin Request.** Un `CreateSesionRequest` tendria cero campos.
- ¿El cliente la lee? **Si**: para listar dispositivos activos y revocar uno por id.
  -> **Resource obligatorio**, y **debe ocultar el hash del token**.
- ¿Reglas de negocio? Ownership al revocar ("solo el dueno puede revocar"). -> **Caso de uso
  obligatorio**, porque esa regla no va en el router.
- ¿Solo del servidor? **Si**.

**Resultado:** Entidad + Resource + caso de uso. Sin Request. Construir los 9 "porque la
lista de verificacion lo decia" deja un DTO vacio y un error de autorizacion en el router.

---

## 3. Quick start: como se levanta un proyecto nuevo

Se sigue en orden. **El orden importa**: el esquema antes del codigo que lo consulta.

1. **Arma el esqueleto.** Gestor de dependencias, base de datos local en contenedor,
   configuracion por entorno.
2. **Decide la estrategia de carpetas.** Por feature (una carpeta por entidad) desde el
   principio en este proyecto: el nucleo ya esta organizado por puertos, y las entidades de
   riesgo son pocas pero con dependencias cruzadas.
3. **Escribe la migracion** con el esquema de seguridad completo.
4. **Verifica que la migracion aplica limpio contra una base vacia.** Ejecutala. Lee el error
   real. Una migracion que nunca se ejecuto es una migracion que no funciona.
5. **Implementa los contratos** de la seccion 1.
6. **Conecta la inyeccion de dependencias.** Resoluble en cualquier orden.
7. **Por cada entidad: pasa el gate** de la seccion 2. No todas necesitan todo.
8. **Implementa el baseline de seguridad** (seccion 5).
9. **Escribe las pruebas** mientras avanzas, no al final.
10. **Pasa el checklist** (`CHECKLIST.md`) y el **gate de readiness** (seccion 15).

No saltes el paso 4. Cada defecto serio de la seccion 12 es una migracion o un mapeo que
nunca se ejecuto.

**Lee las pruebas antes de escribir la funcionalidad.** La estrategia de pruebas (seccion
13) dice que comportamiento se requiere: manejo de duplicados, visibilidad de soft delete,
revocacion inmediata. Escribirlas despues significa escribir lo que el codigo hace.

### 3.1 Configuracion del entorno

**Los secretos vienen del entorno.** Nunca del codigo, nunca con un valor por defecto real
versionado.

```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sin default: el arranque falla si falta. Minimo 32 caracteres.
    supabase_jwt_secret: str = Field(min_length=32)
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Solo para el script de validacion de migraciones en desarrollo.
    # No es parte del camino de ejecucion.
    database_url: str

    max_upload_mb: int = 50
    cors_origins: list[str] = Field(default_factory=list)

    log_level: str = "INFO"
```

**Falla rapido si falta configuracion.** Un secreto por defecto es una vulnerabilidad; un
secreto faltante que rompe el arranque es una caracteristica. Se valida al inicio, antes de
servir trafico.

> **Nunca versiones un secreto real, nunca envies un default utilizable.** El unico default
> aceptable para una llave de firma es "ausente", y su ausencia debe abortar el arranque.

### 3.2 Comandos

Estos son el ciclo de feedback. Deben existir antes de escribir codigo.

```
uv sync                        # instala dependencias
supabase start                 # stack local: Postgres + Auth + PostgREST + Storage
supabase db reset              # destruye y recrea la base desde las migraciones
                               #   <- la forma mas rapida de probar
supabase migration new         # crea una migracion nueva (SQL puro)
supabase db push               # aplica las migraciones al proyecto de Supabase
uv run pytest                  # suite completa
uv run pytest -m unit          # solo unitarias, sin base de datos
uv run pytest -m integration   # contra Supabase real
uv run ruff check .            # lint
uv run ruff format .           # formato
uv run mypy app                # tipos
uv run fastapi dev             # servidor local con recarga
```

> **Una sola herramienta de migraciones.** El esquema vive en `supabase/migrations/*.sql` y
> lo aplica el CLI de Supabase. **No hay Alembic** en este proyecto (ADR-32): las dos
> herramientas sobre la misma base se pisarian, porque `supabase db reset` borra la tabla
> `alembic_version` y Alembic no sabe desplegar hacia Supabase Cloud.

> **Revisa el paso de build que realmente usas.** Un comando que compila solo las fuentes
> de produccion reporta exito aunque las pruebas no compilen. Prefiere el que compila todo.

### 3.3 Base de datos local

`[DECIDIDO]` El stack local de **Supabase** (CLI) es la base de desarrollo: trae Postgres,
Auth, PostgREST y Storage, con el mismo shape que produccion. Eso evita el clasico
"funciona en local y falla en produccion" por diferencias de version o de RLS.

```
supabase start          # levanta el stack local completo
supabase status         # URL y llaves del stack local
supabase db reset       # destruye y recrea la base  <- la forma mas rapida de probar
                        #   que las migraciones aplican limpio
supabase migration new  # crea una migracion nueva
```

Aun asi, se conserva un `docker compose` minimo para el servicio de cola (Redis) que
necesita el worker de la v2.

**Fija siempre la zona horaria.** Sin eso, la semantica de las marcas de tiempo difiere
entre local y produccion, y cada asercion de fecha queda dependiente del entorno.

---

## 4. Reglas de datos

### 4.1 Campos obligatorios desde el dia uno

Retrofitear seguridad a un esquema vivo es mucho mas caro que empezar con ella.

| Campo | Proposito |
|---|---|
| `creado_en` / `actualizado_en` | Metadatos de auditoria |
| `eliminado_en` | Soft delete. Nulo = vivo. La fila persiste para auditoria e integridad referencial |
| `hash_sha256` | Identidad del contenido: subir el mismo archivo dos veces no duplica trabajo |
| `organizacion_id` | Ambito de comparticion (RLS) |

### 4.2 Soft delete

- Toda lectura filtra `eliminado_en IS NULL`.
- Las consultas de unicidad (por ejemplo, `hash_sha256`) tambien deben filtrar soft delete,
  o un documento borrado bloquea una resubida para siempre.
- El borrado real (hard delete) es una operacion administrativa, con su propio permiso.

### 4.3 La invariante del `password_hash NOT NULL`

`password_hash NOT NULL` significa que **cada fila es una credencial**. Elimina por
completo el estado "cuenta sin contrasena".

Para altas de nivel superior sin contrasena (administrador, semilla, invitacion),
genera un **hash inservible** en vez de permitir nulo: hashea un valor aleatorio
criptograficamente seguro. La cuenta existe, es estructuralmente valida, y es imposible de
autenticar hasta que un registro o un restablecimiento le ponga una credencial real.

> No anadas un metodo de repositorio que cree la fila "sin contrasena". Es una trampa:
> parece comodo, produce una violacion NOT NULL en cuanto el esquema es correcto, y
> empuja a cada llamador a inventar su propio rodeo.

### 4.4 Columnas: una sola constante

Cuando el modelo gana un campo, **todas** las proyecciones, todos los `RETURNING` y todos
los mapeadores de fila tienen que cambiar. Un desajuste aparece como un fallo en runtime
lejos de la edicion que lo causo.

```python
# adapters/supabase/columnas.py
COLUMNAS_DOCUMENTO = (
    "id, usuario_id, organizacion_id, nombre_archivo, hash_sha256, "
    "total_paginas, modo_procesamiento, estado, error_mensaje, "
    "creado_en, actualizado_en, eliminado_en"
)
```

Duplicar la proyeccion en varias consultas garantiza que se desincronizan.

---

## 5. Baseline de seguridad

### 5.1 Hash de contrasenas — FUERA DE ALCANCE

`[DECIDIDO]` **No aplica en este proyecto.** Las credenciales las emite Supabase Auth, y el
hashing vive ahi. La tabla `auth.users` no se replica en las tablas del proyecto, y el
backend nunca ve una contrasena.

Se conserva la regla general por si el proyecto llegara a emitir credenciales propias:

Usa **argon2id** (preferido) o **bcrypt**. Nunca a mano.

| Propiedad | Valor |
|---|---|
| Sal | Automatica, por hash, ~128 bits |
| Factor de costo | Ajustable. 10 es un minimo razonable en bcrypt; subirlo con el hardware |
| Tablas arcoiris | Derrotadas por la sal por hash |
| Ataques de tiempo | La funcion de verificacion usa comparacion en tiempo constante |

El factor de trabajo escala con el hardware del atacante, no con el tuyo. Sube con el
tiempo: esta disenado para subir.

> **Nunca copies un hash de contrasena de un fixture, un blog u otro proyecto.** Un hash que
> no generaste verifica contra una contrasena que no conoces. Falla **en silencio**: se
> encuentra el usuario, la comparacion falla, llega un 401, y nada en los logs dice "hash
> incorrecto".
> **Regla:** genera cada hash semilla con la libreria real y verificalo con la funcion de
> verificacion real antes de versionarlo. Una prueba de login sobre un usuario semilla es
> obligatoria.

### 5.2 Autenticacion con Supabase Auth — DECIDIDO

`[DECIDIDO]` **Supabase Auth emite el JWT; el backend lo valida.** ADR-05, ADR-31.

El backend valida el JWT emitido por Supabase:

```
1. Extraer el bearer token del header Authorization.
2. Verificar la firma. La clave publica sale del JWKS del proyecto
   ({SUPABASE_URL}/auth/v1/.well-known/jwks.json). Los proyectos antiguos usan HS256
   con SUPABASE_JWT_SECRET.
3. Verificar exp, aud e iss. El iss esperado es {SUPABASE_URL}/auth/v1, NO una cadena
   inventada por la aplicacion.
4. Verificar que el session_id no este revocado (ver revocacion, mas abajo).
5. Resolver el perfil (rol, organizacion_id) desde la tabla perfiles.
6. Construir el AuditContext con usuario_id, rol y organizacion_id.
7. Si algo falla -> contexto anonimo. Los endpoints protegidos llaman a un guard que
   levanta 401.
```

**Reglas:**

- La peticion **propaga el JWT del usuario** a Postgres (por PostgREST o por el pooler), para
  que RLS filtre. Si el backend se conecta con `service_role`, RLS no aplica: el aislamiento
  queda solo en el codigo de aplicacion, que es exactamente donde no se quiere.
- El `service_role` solo se usa en el worker, y aun ahi la consulta se acota
  explicitamente por `usuario_id` u `organizacion_id`.
- El frontend usa el SDK de Supabase para el login. El backend **no emite tokens**: no hay
  ningun endpoint de emision. `signInWithPassword` se llama **directo** al SDK, y
  `POST /api/v1/auth/login` **no existe**. Si aparece en un router, es un error.

### 5.3 Revocacion de sesion — DECIDIDO

`[DECIDIDO]` **El cierre de sesion invalida el token de inmediato, no al expirar.** ADR-31.

Un JWT es stateless: verificar firma, `exp`, `aud` e `iss` no detecta que la sesion se
cerró. En Supabase Auth, `signOut()` revoca el *refresh token*, pero el *access token*
sigue siendo criptograficamente valido hasta su `exp` (por defecto una hora). Un criterio
de aceptacion que exija "401 de inmediato" no se cumple solo con validacion local.

**Como se resuelve.**

1. El access token de Supabase lleva un claim `session_id`.
2. `POST /api/v1/auth/logout` recibe el token, extrae su `session_id` y lo inserta en
   `sesiones_revocadas (session_id, revocado_en, expira_en)`.
3. El filtro de autenticacion consulta esa tabla en cada peticion: si el `session_id` del
   token esta revocado y su `expira_en` no ha pasado, la peticion es **401**.
4. `expira_en` es el `exp` del propio token. La fila se puede borrar cuando pasa esa
   fecha, y **deja de ser un registro de sesiones**: solo guarda `session_id`, nunca el token.

El costo es una consulta local indexada por peticion. La alternativa —validar la sesion
contra el servidor de Auth en cada peticion— es una llamada de red por peticion, y no se
justifica para este volumen.

**El registro de revocacion es append-only.** Nunca se borra una fila para "desrevocar" una
sesion: se espera a que expire.

### 5.4 Sesiones revocables propias — FUERA DE ALCANCE

`[DECIDIDO]` No aplica: Supabase Auth ya gestiona la revocacion de sesiones. Se conserva la
especificacion por si la decision se revierte.

Un JWT puro sin estado no se puede revocar. Si un token se filtra, sigue siendo valido hasta
que expira. Se combina un token firmado con estado de sesion en el servidor.

**Flujo de login**

```
POST /api/v1/auth/login { email, password }
  1. Buscar usuario por correo
  2. Rechazar si esta inactivo / eliminado / bloqueado      <- estado, no solo contrasena
  3. Verificar hash (argon2id/bcrypt), comparacion en tiempo constante,
     hash ficticio en caso de fallo
  4. Generar un JTI unico (UUID)
  5. Firmar el JWT con el JTI dentro
  6. Persistir la sesion: jti, usuario_id, sha256(token), issued_at, expires_at, ip, user_agent
  7. Reiniciar failed_login_attempts, poner last_login_at
  8. Devolver el token
```

**Flujo de logout**

```
POST /api/v1/auth/logout
  1. El filtro de auth extrae el JTI
  2. Marcar la sesion como revocada (revoked = true, revoked_at = now)
  3. El token es invalido de inmediato, sin esperar la expiracion
```

**Validacion por peticion**

```
Filtro de auth, antes de cada handler
  1. Extraer el bearer token
  2. Verificar firma, expiracion, emisor
  3. Buscar la sesion por JTI: activa AND no revocada AND no expirada
  4. Activa -> construir contexto autenticado con usuario_id y JTI
     No     -> construir contexto anonimo
  5. Los endpoints que requieren auth llaman a un guard que levanta 401
```

La firma prueba **autenticidad**. La fila de sesion prueba **que sigue activo**. Las dos
juntas.

**Almacenamiento del hash del token:** guarda `sha256(token)`, nunca el token. Si la base se
filtra, un digest SHA-256 de un JWT de vida corta es mucho menos util que el token.

### 5.4 Checks de estado de la cuenta — FUERA DE ALCANCE

`[DECIDIDO]` No aplica: el estado de la cuenta (activo, bloqueado, verificado) lo administra
Supabase Auth. El backend no implementa bloqueo por intentos fallidos ni contador de
reintentos: **no tiene donde**, porque no ve las contrasenas.

Se conserva la regla general por si la decision se revierte:

Los campos de estado no hacen nada salvo que el login los aplique:

- Inactivo, eliminado o bloqueado -> rechazar **antes** de verificar la contrasena.
- Contrasena fallida -> incrementar `failed_login_attempts`; al cruzar el umbral, fijar
  `locked_until`.
- Login exitoso -> reiniciar el contador, poner `last_login_at`.

> **Un helper `can_login()` en el modelo al que nada llama es peor que no tenerlo.** Se lee
> como implementado, pasa la revision de codigo, y deja la funcion de bloqueo de cuenta
> completamente inerte. Cada campo de estado necesita una ruta de escritura y una de
> lectura, o es decoracion.
> **Prueba:** intenta login en una cuenta deshabilitada y en una bloqueada. Ambos deben ser
> rechazados.

### 5.5 Oraculo de tiempo en usuarios desconocidos — FUERA DE ALCANCE

`[DECIDIDO]` No aplica al login del backend: el login lo resuelve Supabase Auth. Se conserva
la regla general porque **si aplica al endpoint que recibe el correo del usuario** para
buscar su perfil, y a cualquier busqueda por correo.

Cuando el correo no existe, devolver de inmediato se salta la comparacion de contrasena, y
el **tiempo** de la respuesta revela que correos estan registrados.

Mitiga ejecutando una verificacion ficticia contra un hash fijo cuando el usuario no se
encuentra, para que ambos caminos cuesten lo mismo.

> Se honesto en el codigo y en la documentacion sobre que mitigaciones estan realmente
> implementadas. No documente una defensa que el codigo no ejecuta.

### 5.6 Carga de archivos

- Validar el **tipo real** del archivo (magic bytes), no solo la extension. **En el
  navegador**: el backend nunca ve el archivo, asi que no puede inspeccionar sus magic
  bytes. La validacion ocurre antes de subir, y el bucket restringe los MIME permitidos.
- Limitar el tamano **antes** de leer el archivo en memoria.
- Sanear el nombre: no se usa el nombre del cliente como nombre en disco.
- **El archivo se archiva** en almacenamiento privado (ADR-20), y se borra cuando se borra
  el documento. No se borra "al terminar el pipeline": el pipeline no es su unico consumidor.
- En la v1 el archivo **sube directo del navegador al almacenamiento**. No pasa por la
  funcion: su cuerpo esta limitado a 4.5 MB y un PDF de 100 paginas pesa mucho mas.
- El analisis ocurre en el navegador, sobre el archivo local. Que el archivo se archive no
  significa que el servidor lo procese.
- Cuando el backend confirma la subida (`POST /documentos/{id}/archivo`), **consulta los
  metadatos del objeto** en Storage: existencia, tamano real y MIME guardado. Si no
  coinciden con lo que declaro el cliente, no confirma la ruta.

---

## 6. Transacciones

En una arquitectura hexagonal, la transaccion es un **puerto** (`UnitOfWork`) que el caso de
uso usa. Lo que cambia con el acceso por HTTP es **como se implementa**: no hay una sesion
de SQL que abrir y cerrar, hay una operacion atomica que se pide a la base.

```python
# application/unit_of_work.py
class UnitOfWork(Protocol):
    """Una transaccion. Un caso de uso, un commit."""

    documentos: DocumentoRepository
    bloques: BloqueRepository
    analisis: AnalisisRepository

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

La forma del caso de uso:

```python
async with self.uow as u:
    try:
        documento_id = await u.analisis.registrar(documento, bloques, analisis)
        await u.commit()
    except Exception:
        await u.rollback()
        raise
```

**Regla:** nunca mezcles una escritura auto-commit dentro de un bloque transaccional. Una
operacion, una transaccion, un commit.

**Como se implementa sin conexion TCP.** La operacion atomica se pide a Postgres por RPC
(seccion 6.1): una funcion que inserta el documento, sus bloques y su analisis, o nada.
La atomicidad la garantiza la base de datos, no el backend. Por eso el puerto de
persistencia declara **una sola operacion**, no varias.

Lo que **no** se hace: abrir una conexion TCP, empezar una transaccion en Python, y
mandar sentencias una a una. Eso contradice ADR-04 y hace que el servicio dependa de un
pool de conexiones que las funciones de Vercel no mantienen.

```python
# El repositorio pide la operacion atomica. No compone varias escrituras.
async def registrar(self, documento: Documento, bloques: list[Bloque], analisis: Analisis) -> UUID:
    respuesta = await self._cliente.rpc(
        "registrar_analisis",
        {
            "p_documento_id": str(documento.id),
            "p_bloques": [b.to_dict() for b in bloques],
            "p_resumen_ejecutivo": analisis.resumen_ejecutivo,
            "p_riesgos": analisis.riesgos,
            "p_plantilla_id": str(analisis.plantilla_id),
            "p_plantilla_version": analisis.plantilla_version,
            "p_modelo": analisis.modelo,
            "p_total_bloques": len(bloques),
        },
    ).execute()
    return UUID(respuesta.data)
```

### 6.1 Transacciones sin conexion TCP (PostgREST)

`[DECIDIDO]` El backend habla con Supabase **por HTTP**, no por una conexion TCP a Postgres.
Eso lo deja stateless y portable entre plataformas de funciones. Ver ADR-04.

El precio es que **PostgREST no tiene transacciones de varias sentencias**. La operacion
atomica "guardar documento + N bloques + analisis" se resuelve con una **funcion de Postgres**
llamada por RPC:

```sql
-- supabase/migrations/005_funciones_rpc.sql
create or replace function public.registrar_analisis(
  p_documento_id       uuid,
  p_bloques            jsonb,
  p_resumen_ejecutivo  text,
  p_riesgos            jsonb,
  p_plantilla_id       uuid,
  p_plantilla_version  int,
  p_modelo             text,
  p_total_bloques      int
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_bloque jsonb;
  v_indice int := 0;
  v_documento uuid;
  v_analisis_id uuid;
  v_plantilla_anterior uuid;
  v_version_anterior int;
  v_modelo_anterior text;
  v_resumen_anterior text;
  v_riesgos_anterior jsonb;
  v_resumenes_anterior jsonb;
  v_hay_anterior boolean := false;
begin
  -- 1. El aislamiento NO se da por sentado: se comprueba aqui, dentro de la transaccion.
  select d.id into v_documento
  from public.documentos d
  where d.id = p_documento_id
    and d.usuario_id = auth.uid()
    and d.eliminado_en is null;

  if v_documento is null then
    raise exception 'not_found' using errcode = 'P0002';
  end if;

  -- 2. Se captura el analisis vigente ANTES de sobrescribirlo: despues ya no existira.
  select a.id, a.plantilla_id, a.plantilla_version, a.modelo,
         a.resumen_ejecutivo, a.riesgos, a.resumenes
  into v_analisis_id, v_plantilla_anterior, v_version_anterior, v_modelo_anterior,
       v_resumen_anterior, v_riesgos_anterior, v_resumenes_anterior
  from public.analisis_documentos a
  where a.documento_id = v_documento;

  v_hay_anterior := v_analisis_id is not null;

  delete from public.bloques where documento_id = v_documento;

  for v_bloque in select * from jsonb_array_elements(p_bloques) loop
    insert into public.bloques (
      documento_id, usuario_id, indice, pagina_inicio, pagina_fin,
      resumen, datos_estructurados
    )
    values (
      v_documento, auth.uid(), v_indice,
      (v_bloque->>'pagina_inicio')::int, (v_bloque->>'pagina_fin')::int,
      v_bloque->>'resumen', v_bloque->'datos_estructurados'
    );
    v_indice := v_indice + 1;
  end loop;

  -- 3. El analisis vigente. Uno por documento.
  insert into public.analisis_documentos (
    documento_id, usuario_id, plantilla_id, plantilla_version, modelo,
    total_bloques, resumen_ejecutivo, riesgos, resumenes
  )
  values (
    v_documento, auth.uid(), p_plantilla_id, p_plantilla_version, p_modelo,
    p_total_bloques, p_resumen_ejecutivo, p_riesgos,
    (select coalesce(jsonb_agg(jsonb_build_object(
        'indice', b.indice,
        'paginas', b.pagina_inicio || '-' || b.pagina_fin,
        'resumen', b.resumen
     ) order by b.indice), '[]'::jsonb)
     from public.bloques b where b.documento_id = v_documento)
  )
  on conflict (documento_id) do update set
    plantilla_id = excluded.plantilla_id,
    plantilla_version = excluded.plantilla_version,
    modelo = excluded.modelo,
    total_bloques = excluded.total_bloques,
    resumen_ejecutivo = excluded.resumen_ejecutivo,
    riesgos = excluded.riesgos,
    resumenes = excluded.resumenes
  returning id into v_analisis_id;

  -- 4. El analisis anterior pasa al historial (ADR-25).
  if v_hay_anterior then
    insert into public.analisis_historial (
      documento_id, usuario_id, plantilla_id, plantilla_version, modelo,
      resumen_ejecutivo, riesgos, resumenes, reemplazado_por, creado_en
    )
    values (
      v_documento, auth.uid(), v_plantilla_anterior, v_version_anterior,
      v_modelo_anterior, v_resumen_anterior, v_riesgos_anterior,
      v_resumenes_anterior, v_analisis_id, now()
    );
  end if;

  -- 5. El documento y el trabajo quedan cerrados en la MISMA transaccion.
  update public.documentos
  set estado = 'completado', error_mensaje = null, actualizado_en = now()
  where id = v_documento;

  update public.trabajos
  set estado = 'completado', finalizado_en = now(),
      duracion_ms = extract(epoch from (now() - iniciado_en)) * 1000
  where documento_id = v_documento and estado in ('en_cola', 'en_proceso');

  return v_documento;
end;
$$;
```

> **`resumenes` se construye dentro de la base.** El cliente envia los bloques, no el
> arreglo de resumenes duplicado. Si el payload trajera los dos, un documento de 250
> paginas (125 bloques) mandaria el doble de lo necesario y se acercaria al limite de
> 4.5 MB de Vercel Functions. Ver I-10 del informe de validacion.

Reglas para las funciones de Postgres:

- `security definer` cambia el contexto de ejecucion: **la funcion tiene que comprobar el
  permiso a mano**, porque RLS no aplica dentro de un `definer` con el rol del propietario.
  La comprobacion va dentro de la funcion, en la misma transaccion.
- `set search_path = public` es obligatorio: sin eso, la funcion es vulnerable a secuestro
  de objetos.
- El JSONB entra por el cuerpo de la funcion y se valida en Python **antes** de llamar.
  La funcion no es la frontera de confianza.
- `raise exception ... using errcode` permite mapear el error a un codigo HTTP concreto en
  el manejador global.

**Consecuencia para los puertos:** el puerto de persistencia declara la operacion de
persistencia atomica como **una sola llamada** (`registrar_analisis`), no tres llamadas
separadas. El caso de uso no necesita saber que por debajo hay una funcion de Postgres.

**`registrar_analisis` cubre tambien el reanálisis.** La funcion es la misma para el
analisis inicial y para el reanálisis (HU-10): si ya habia un analisis vigente, este pasa
al historial y el nuevo lo sustituye. Todo en la misma transaccion: o quedan los dos, o
no queda ninguno.

---

## 7. Inyeccion de dependencias

El `new` manual deja de escalar a partir de unos pocos componentes. En FastAPI, la
dependencia se declara con `Depends` y la composicion vive en un unico lugar.

```python
# adapters/http/deps.py
def caso_crear_documento(
    uow: UnitOfWork = Depends(unit_of_work),
    documentos: DocumentoRepository = Depends(documento_repository),
    storage: Almacenamiento = Depends(almacenamiento),
    cola: ColaDeTrabajos = Depends(cola),
    reloj: Reloj = Depends(reloj_sistema),
) -> CrearDocumento:
    return CrearDocumento(
        documentos=documentos,
        documentos_por_hash=documentos,
        storage=storage,
        cola=cola,
        reloj=reloj,
        uow=uow,
    )
```

Reglas:

- **Inyeccion por constructor** en todo el codigo de dominio y aplicacion. Hace las
  dependencias explicitas y mantiene la clase testeable sin framework.
- El **router** es el unico lugar donde se conocen FastAPI y las dependencias.
- Los puertos se resuelven en un unico modulo de composicion, no dispersos por los routers.
- El filtro de autenticacion se registra **exactamente una vez**. Registrarlo dos veces
  produce el doble de trabajo por peticion y dos contextos de auditoria.

---

## 8. Paginacion

**Peticion:** `(page, size)` con valores por defecto — pagina 1, tamano 20, maximo 100. Se
**recorta** (clamp), no se rechaza.

**Respuesta:** la pagina de datos mas los metadatos que la UI necesita para pintar los
controles.

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

Devuelve los metadatos. Un cliente que recibe solo un array desnudo no puede construir los
controles de paginacion sin una segunda peticion.

---

## 9. Contexto de auditoria

Un objeto que lleva **quien** esta haciendo la peticion, construido por el middleware antes
del handler y pasado a los casos de uso.

**Campos:** id de usuario (nulo si anonimo), nombre de usuario, id de sesion o token (la
llave de revocacion), rol, id de organizacion, accion, IP del cliente.

**Reglas:**

- Los casos de uso reciben este objeto y **nunca ven el token**.
- Credenciales invalidas, expiradas o revocadas producen un contexto **anonimo**, no un 401
  inmediato. Los endpoints que requieren autenticacion llaman a un guard.
- Para pruebas, se reemplaza el middleware por uno que fije el contexto directamente.

La bitacora de auditoria escribe a un **canal separado** de los logs de negocio, con
retencion independiente. Los datos de auditoria y los de depuracion tienen ciclos de vida
y audiencias distintos; rutearlos juntos significa que no puedes conservar los registros
de auditoria sin conservar el ruido de depuracion, ni soltar el ruido sin soltar la
auditoria.

> **El contenido del documento nunca se registra.** Ni en auditoria, ni en logs, ni en
> trazas, ni en metricas.

### 9.1 Roles y permisos

**Hace:** determinar que puede hacer cada usuario, con una matriz que vive en datos.
**No hace:** reemplazar RLS. Son capas complementarias: **RLS filtra filas**, el **permiso
filtra acciones**.

**Reglas:**

- El permiso se comprueba **en el caso de uso**. Un router que consulta el permiso y un
  caso de uso que lo vuelve a comprobar es redundante; un router que lo consulta y un caso
  de uso que no, es un agujero.
- Un permiso **ausente se deniega**. Nunca "permitido por defecto".
- **La respuesta depende del orden de las comprobaciones, y el orden es fijo** (ADR-30):

  | Situacion | Respuesta |
  |---|---|
  | El usuario **no tiene el permiso** que la accion exige | **403** |
  | El usuario **si tiene el permiso**, pero la fila no aparece (no existe, o es de otra organizacion y RLS la filtro) | **404** |

  El caso de uso comprueba **el permiso primero** y la fila despues. Por eso no necesita
  `service_role` para distinguir "no existe" de "no lo puedes ver": si el permiso falta, la
  respuesta es 403 sin haber consultado nada; si el permiso esta, la consulta con el JWT
  del usuario ya aplico RLS, y lo que no aparece se responde 404.

- Por que no se responde siempre 404: un 403 es honesto cuando el usuario **ya sabe** que
  el recurso existe, porque esta en su propia organizacion. Ocultarlo no aporta seguridad:
  el permiso ya no deja pasar la accion.
- Por que no se responde siempre 403: un 403 sobre un recurso de **otra organizacion**
  confirmaria que ese identificador existe. Ahi si es 404.
- La comprobacion produce `ProhibidoError`, un error de dominio con status 403.

```python
# domain/services/permisos.py
@dataclass(frozen=True)
class Permisos:
    """Permisos efectivos de un usuario, resueltos una vez por peticion."""

    _concedidos: frozenset[str]

    def exige(self, permiso: str) -> None:
        if permiso not in self._concedidos:
            raise ProhibidoError(f"Falta el permiso '{permiso}'")

    def permite(self, permiso: str) -> bool:
        return permiso in self._concedidos
```

```python
# application/use_cases/eliminar_documento.py
async def ejecutar(self, cmd, ctx: AuditContext) -> None:
    ctx.permisos.exige("documentos.borrar")          # <- aqui, no en el router

    documento = await self.documentos.obtener_por_id(cmd.documento_id)
    if documento is None:
        raise NoEncontradoError("Documento no encontrado")
    if documento.usuario_id != ctx.usuario_id and not ctx.permisos.permite(
        "analisis.ver_todos"
    ):
        raise ProhibidoError("No puede eliminar un documento de otro usuario")

    await self.documentos.marcar_eliminado(cmd.documento_id)
```

**La matriz vive en datos.** Un permiso es una fila en `permisos` y su asignacion, una fila
en `rol_permisos`. Agregar `plantillas.editar` es un `insert`, no un despliegue.

```sql
insert into permisos (clave, descripcion) values ('plantillas.editar', 'Modificar plantillas');
insert into rol_permisos (rol, permiso) values ('admin', 'plantillas.editar');
```

### 9.2 Administracion de usuarios

Crear usuarios en Supabase requiere la `service_role`, que por regla general no debe tocar
el backend. La excepcion es **estrecha, delimitada y documentada**:

- La `service_role` vive **solo** en `adapters/supabase/admin.py`.
- Ese adaptador expone **unicamente** operaciones de aprovisionamiento: crear usuario,
  asignar rol y organizacion, desactivar, restablecer contrasena.
- Ningun router de peticiones de usuario final llega a el. El unico endpoint que lo invoca
  exige `usuarios.gestionar`.
- Toda operacion se registra en la bitacora de auditoria con el actor.
- La `service_role` **nunca** lee ni escribe datos de negocio: para eso se reenvia el JWT
  del usuario y deja que RLS filtre.

> Documentar la excepcion es obligatorio. Una regla "no uses service_role" sin nombrar la
> excepcion produce dos ejemplos: el que la evade sin decirlo y el que la necesita y no la
> documenta.

### 9.3 El puerto de correo
`[DECIDIDO]` Enviar correo es una capacidad de **salida**, como el LLM o la base de datos:
se define un puerto y la infraestructura lo implementa. Nunca se llama a un proveedor de
correo desde un caso de uso.

```python
# domain/ports/notificador.py
class NotificadorCorreo(Protocol):
    """Puerto de salida. Enviar correo, no decidir que se escribe."""

    async def enviar_credencial_temporal(
        self, correo: str, contrasena_temporal: str, enlace_confirmacion: str
    ) -> None: ...
```

Implementaciones:

- **Real:** un proveedor (Resend, Amazon SES o SMTP). Requiere una variable de entorno
  mas y, en el caso de SMTP, configuracion de remitente y TLS.
- **Desarrollo:** una que solo escribe el correo en el log. Sin ella, el flujo de alta de
  usuarios no se puede probar sin contratar un servicio de correo.

**El cuerpo del correo es del caso de uso, el envio es del adaptador.** Si manana se cambia
a un enlace de un solo uso en vez de una contrasena autogenerada, el unico archivo que
cambia es el que compone el mensaje.

**Reglas de seguridad del correo con credenciales:**

- La contrasena temporal se genera con un generador criptografico, no con `random`.
- El perfil se marca con `debe_cambiar_contrasena = true`, y el frontend fuerza el cambio
  en el primer inicio de sesion. La contrasena temporal deja de servir para siempre.
- El correo **nunca** se registra en logs de negocio. Se registra que se envio, no su
  contenido.

```python
# domain/services/credenciales.py
import secrets

def generar_contrasena_temporal(longitud: int = 20) -> str:
    """Credencial de un solo uso para el alta de usuarios.

    Se genera con secrets, no con random: una contrasena predecible para un usuario
    recien creado es una puerta abierta, no una comodidad.
    """
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))
```

### 9.4 El puerto de almacenamiento

`[DECIDIDO]` Guardar y leer archivos es una capacidad de **salida**, como el LLM, el correo o
la base de datos. Se define un puerto y la infraestructura lo implementa.

```python
# domain/ports/almacenamiento.py
from typing import Protocol

class Archivo(Protocol):
    nombre: str
    tipo_mime: str
    tamano: int
    contenido: bytes

class Almacenamiento(Protocol):
    """Puerto de salida. Guardar, descargar y eliminar archivos.

    No decide quien puede ver que: eso lo resuelve el caso de uso, con el permiso.
    """

    async def guardar(self, bucket: str, ruta: str, archivo: Archivo) -> str: ...

    # `como_descarga=True` pide la URL como adjunto (Content-Disposition: attachment),
    # no para ver en linea. Un PDF con JavaScript embebido servido en linea se ejecuta
    # en el origen del navegador: por eso la descarga de un documento es siempre
    # una descarga, nunca una vista.
    async def url_firmada(
        self, bucket: str, ruta: str, duracion_s: int, *, como_descarga: bool = True
    ) -> str: ...

    async def eliminar(self, bucket: str, ruta: str) -> None: ...
```

Implementaciones:

- **Supabase Storage** (v1): bucket privado, RLS sobre `storage.objects`, clave del objeto
  `{organizacion_id}/{usuario_id}/{documento_id}.pdf`. La URL firmada de descarga se pide
  **con la opcion de descarga** (`download=True`): sin ella, Supabase sirve el objeto en
  linea.
- **S3** o **SFTP** (futuro, si el cliente tiene los suyos): otro adaptador. Los casos de uso
  no cambian.

**El archivo no pasa por el backend.** `[DECIDIDO]` La subida va **directo del navegador al
almacenamiento**. Motivo: el cuerpo de una funcion de Vercel esta limitado a 4.5 MB y un PDF
de 100 paginas pesa entre 5 y 30 MB. Ademas, el archivo nunca queda en memoria de la
funcion.

```
POST /documentos
  -> valida tamano y tipo MIME, crea el documento y el trabajo
  -> devuelve { documento_id, trabajo_id, url_subida_firmada }

Navegador
  -> PUT del PDF a esa URL, directo al almacenamiento
  -> POST /documentos/{id}/archivo  -> el backend guarda la ruta
```

**Reglas de seguridad del almacenamiento:**

- El bucket es **privado**. Nunca publico. Sin URL publica.
- **La URL firmada se emite en el backend**, no en el cliente, y solo si el permiso existe.
  Duracion maxima de **1 hora**.
- **El bucket impone los limites**: `file_size_limit` y `allowed_mime_types`. Las URLs
  firmadas de Supabase **no pueden llevar tamano ni tipo**, asi que el limite del bucket es
  la segunda linea de defensa. La primera es la validacion del backend antes de firmar.
- **La clave del objeto codifica el ambito** (`organizacion_id/usuario_id/documento_id.pdf`),
  para que la politica de RLS se resuelva por prefijo.
- **Borrar el documento borra el archivo.** Un soft delete en la base sin borrar el objeto
  deja un PDF vivo que la interfaz ya no muestra. Eso es una fuga, no un detalle.
- **Nunca se guarda un archivo en base64 dentro de la base de datos.** El binario vive en el
  almacenamiento; en la base solo la ruta, el hash, el tamano y el tipo.

> Una URL firmada funciona para cualquiera que la tenga, hasta que expira. De ahi la vida
> corta, y de ahi que se emita desde el unico lugar que sabe si el permiso existe.

---

## 10. Pipeline ETL y LLM

### 10.1 Reglas del pipeline

1. **En la v1 el pipeline corre en el navegador del usuario.** El documento no sale de su
   equipo. La API solo recibe resultados ya calculados y validados.
2. **La cola de analisis es del lado del cliente.** El servidor lleva el estado
   (`trabajos`), no la ejecucion. No hay cola en el servidor en la v1.
3. **El pipeline es idempotente.** Reprocesar un documento ya completado no duplica filas.
4. **El texto se valida antes de persistir.** La salida del LLM se valida contra el esquema
   de la plantilla; un JSON invalido nunca llega a la base.
5. **El documento sin capa de texto se marca como error explicito**, no como analisis vacio
   con estado `completado`.
6. **La fase Reduce recibe los resumenes parciales**, nunca el documento completo, y es
   **jerarquica** cuando los resumenes no caben en la ventana de contexto.
7. **El hash identifica el contenido.** La misma carga no se procesa dos veces.
8. **El tamano de bloque se deriva de la ventana de contexto del modelo**, no se fija a
   mano. Ver seccion 10.2.
9. **Un trabajo abandonado se detecta y se libera.** Latido por reporte de progreso y tarea
   de mantenimiento que marca los trabajos sin latido como `interrumpido`.

### 10.2 Chunking (regla de dominio pura)

El chunking no depende de nada externo: es una funcion pura del texto y de la
configuracion. Vive en el dominio, **se comparte con el frontend**, y se prueba sin base de
datos ni red.

```python
# domain/services/chunking.py
def dividir_en_bloques(
    paginas: Sequence[str],
    tamano_paginas: int,
    overlap_paginas: int,
) -> list[Bloque]:
    """Divide el texto por paginas en bloques de N paginas con solapamiento.

    Invariante: los bloques cubren todas las paginas; el unico solapamiento es el
    configurado.
    """
    if tamano_paginas < 1:
        raise ValueError("tamano_paginas debe ser >= 1")
    if overlap_paginas >= tamano_paginas:
        raise ValueError("overlap_paginas debe ser menor que tamano_paginas")

    bloques: list[Bloque] = []
    paso = tamano_paginas - overlap_paginas
    indice = 0
    inicio = 0
    while inicio < len(paginas):
        fin = min(inicio + tamano_paginas, len(paginas))
        bloques.append(
            Bloque(
                indice=indice,
                pagina_inicio=inicio + 1,
                pagina_fin=fin,
                texto="\n\n".join(paginas[inicio:fin]),
            )
        )
        indice += 1
        inicio += paso
    return bloques
```

**El numero de bloques sale del solapamiento, no del tamano.** Con `tamano_paginas = 3` y
`overlap_paginas = 1`, el paso es 2, y un documento de 100 paginas produce
`ceil((100 - 1) / 2) = 50` bloques. No 34: ese numero sale de dividir 100 entre 3 e
ignorar que las ventanas se solapan.

```python
def contar_bloques(total_paginas: int, tamano_paginas: int, overlap_paginas: int) -> int:
    paso = tamano_paginas - overlap_paginas
    return max(1, ceil((total_paginas - overlap_paginas) / paso))
```

**El solapamiento no es gratis.** Con 50 bloques, el texto se procesa
`50 * 3 = 150` paginas por 100 del documento: un 50% mas de trabajo. Es el precio de que
un dato que cae en la frontera entre dos bloques no se pierda. El valor por defecto es 1
pagina, que es el minimo que todavía sirve para eso.

#### 10.2.2 Un tope por tokens, no solo por paginas

`[DECIDIDO]` **El numero de paginas es una estimacion; el limite real es de tokens.**

Contar paginas falla con documentos reales: una pagina con una tabla densa o un anexo
financiero puede tener 2.000 a 3.000 tokens, mientras que una pagina de texto corrido
tiene 400. Con `tokens_por_pagina = 700` y 3 paginas por bloque, un bloque puede llevar
9.000 tokens en una ventana de 4.096. El sintoma no es "el bloque es grande": es que el
modelo **devuelve basura** o se corta en silencio.

Por eso, despues de trocear por paginas, **cada bloque se subdivide por longitud**:

```python
# domain/services/chunking.py
CARACTERES_POR_TOKEN = 3.5   # español: ~3.5 caracteres por token

def tokens_estimados(texto: str) -> int:
    return int(len(texto) / CARACTERES_POR_TOKEN)

def subdividir_por_tokens(
    bloque: Bloque,
    maximo_tokens: int,
) -> list[Bloque]:
    """Parte un bloque que excede el maximo, sin partir una pagina a la mitad."""
    if tokens_estimados(bloque.texto) <= maximo_tokens:
        return [bloque]
    partes: list[Bloque] = []
    for pagina in bloque.paginas:          # el bloque guarda sus paginas sueltas
        partes.append(Bloque(indice=0, pagina_inicio=..., pagina_fin=..., texto=pagina))
    return partes
```

La subdivision **nunca parte una pagina por la mitad**: una tabla partida es ilegible.
Si una sola pagina excede el maximo, se procesa sola y el caso queda marcado para
revision: es un documento con una pagina imposible, no un error del troceador.

El `tokens_por_pagina` que se guarda en la configuracion es **una estimacion para el
troceado inicial**, no una garantia. El limite que manda es `ventana_contexto -
tokens_reservados`, y se comprueba bloque a bloque.

#### 10.2.3 El tamano de bloque se deriva de la ventana de contexto

`[DECIDIDO]` No se fija a mano. Los modelos precompilados de WebLLM vienen con **4096
tokens** de contexto por defecto, y 10 paginas de texto denso rondan las 4.000 a 6.000
tokens: no caben. El sintoma de ese error no es "el bloque es grande", es "el modelo
devuelve basura", que es mucho mas dificil de diagnosticar.

```python
# domain/services/chunking.py
def calcular_paginas_por_bloque(
    ventana_contexto: int,
    tokens_reservados: int,
    tokens_por_pagina: int,
) -> int:
    """Deriva el tamano de bloque a partir de la ventana del modelo.

    Con 4096 de ventana, 1200 reservados y 700 tokens por pagina: 4 paginas.
    Con 900 tokens por pagina: 3 paginas.

    El resultado es una estimacion de partida. El limite real se comprueba por bloque
    con tokens estimados (seccion 10.2.2).

    **Esta funcion no recibe `overlap_paginas`, y no es un olvido.** El solapamiento
    no cambia cuantas paginas caben en la ventana: cambia **cuanto se avanza** entre
    bloque y bloque. El tamano sale de los tokens (`utiles // tokens_por_pagina`), el
    avance sale del solapamiento (`tamano - overlap`) y el numero de bloques sale de
    ambos (`contar_bloques`). Son tres preguntas distintas, y por eso son tres funciones.
    """
    utiles = ventana_contexto - tokens_reservados
    if utiles <= 0:
        raise VentanaDeContextoInsuficienteError(
            f"La ventana de {ventana_contexto} tokens no alcanza para instruccion y salida"
        )
    return max(1, utiles // tokens_por_pagina)
```

`tokens_por_pagina` (~600 a 900) se estima y **se calibra con documentos reales**. No es una
constante de la libreria: es un parametro de la configuracion del motor, y por eso vive en
la base de datos, no en el codigo.

**El valor cambia con el motor.** El 3 no esta metido en el codigo: sale de la ventana de
contexto del modelo activo.

| Motor | Ventana | Paginas por bloque | Reduce jerarquico |
|---|---|---|---|
| Modelos de navegador (WebLLM) | 4.096 | 3 | Necesario (~50 resumenes en 100 paginas) |
| Modelo pequeno en servidor | 8.192 | 8 | Necesario |
| Proveedor hospedado de ventana grande | 200.000 | ~200 | Innecesario: cabe en una pasada |

Cuando el motor cambia, el valor derivado cambia solo. Por eso el motor es configurable por
usuario y por organizacion, y por eso un bloque de 3 paginas no es un supuesto codificado:
es el resultado de una formula con la ventana del modelo que se este usando.

**El Reduce jerarquico.** Con 3 paginas por bloque, 100 paginas producen ~50 resumenes
parciales. A ~200 tokens cada uno son ~10.000 tokens: no caben en 4K. El Reduce agrupa los
resumenes en lotes que quepan, reduce cada lote, y reduce los resultados intermedios.

```python
# domain/services/reduccion.py
def reducir_jerarquico(
    resumenes: Sequence[str],
    ventana_contexto: int,
    tokens_por_resumen: int,
    maximo_por_lote: int,
) -> list[str]:
    """Agrupa los resumenes en lotes que quepan y devuelve resumenes por lote."""
    return [
        resumenes[i : i + maximo_por_lote]
        for i in range(0, len(resumenes), maximo_por_lote)
    ]
```

Para documentos de hasta ~200 paginas cabe en dos niveles de reduccion.

### 10.3 Salida estructurada del LLM

#### El port, y por que hay mas de una implementacion

El motor LLM es un **puerto**. Hoy tiene una implementacion local (WebLLM en el navegador).
Mañana puede tener una de un proveedor hospedado, si el cliente tiene un contrato con el.

Reglas para anadir una implementacion hospedada:

1. **Requiere un ADR propio** que registre: que proveedor, que datos salen, que regiones,
   que contrato lo respalda y quien lo aprobo.
2. **No es un default.** El sistema arranca con la implementacion local.
3. **No se mezcla**: una peticion no va a un proveedor hospedado y otra a uno local sin que
   el usuario lo sepa. El modo se elige y se muestra.
4. El **texto que sale** sigue siendo el del documento. Por eso la decision exige que el
   contrato del cliente lo cubra de forma explicita, no que "este disponible".

La razon por la que esto es barato: el motor LLM es un puerto, no una llamada embebida. Se
escribe un adaptador mas y los casos de uso, el dominio y la interfaz no cambian.

> **La regla de privacidad y la regla de intercambiabilidad no se contradicen.** Una dice
> que el default es local. La otra dice que el default se puede cambiar, con registro. Lo
> que no se permite es cambiarlo sin que quede escrito.

#### Adaptador de navegador (camino principal, v1)

El motor corre en el Web Worker del navegador. El adaptador de navegador no es un
adaptador de salida del backend: vive en el frontend. El backend **no** implementa el port
de LLM en la v1; solo lo recibe y lo valida.

```typescript
// frontend/src/workers/llm.worker.ts
import { WebWorkerMLCEngine, type MLCEngineConfig } from '@mlc-ai/web-llm'

export async function analizarBloque(
  engine: WebWorkerMLCEngine,
  prompt: string,
  esquema: object,
  temperatura: number,
  intentos = 2,
): Promise<object> {
  let ultimoError: Error | null = null

  for (let intento = 0; intento <= intentos; intento++) {
    const respuesta = await engine.chat.completions.create({
      messages: [{ role: 'user', content: prompt }],
      temperature: temperatura,
      // Generacion restringida por gramatica: reduce mucho los JSON invalidos,
      // pero NO sustituye la validacion del backend.
      // OJO: `schema` es un STRING JSON, no un objeto. WebLLM lo serializa.
      response_format: {
        type: 'json_object',
        schema: JSON.stringify(esquema),
      },
    })

    try {
      const contenido = respuesta.choices[0]?.message?.content ?? '{}'
      return JSON.parse(contenido)
    } catch (error) {
      ultimoError = error as Error
      prompt = prompt + '\n\nLa respuesta anterior no era JSON valido: ' + String(error)
    }
  }

  throw new Error('La salida del modelo no cumple el esquema: ' + String(ultimoError))
}
```

La validacion definitiva ocurre en el backend, contra el esquema de la plantilla. El
cliente **no es una frontera de confianza**.

**Que construcciones de JSON Schema admite el motor.** La generacion restringida usa
XGrammar, que soporta un **subconjunto acotado** de JSON Schema. La plantilla de
extraccion tiene que declarar solo lo que el motor entiende:

| Se admite | Se evita |
|---|---|
| `type`, `properties`, `required`, `items`, `enum` | `oneOf`, `anyOf`, `allOf`, `not` |
| `additionalProperties: false` | `patternProperties`, `dependentSchemas` |
| `type: ["string", "null"]` para opcionales | `if` / `then` / `else` |

La plantilla **valida en el servidor** que su esquema cae dentro del subconjunto antes de
aceptarla. Una plantilla con `oneOf` no es un error de ejecucion: es una plantilla que no
se puede usar con generacion restringida, y el backend lo dice al guardarla, no cuando el
modelo ya fallo.

**El `schema` se serializa, no se pasa como objeto.** WebLLM espera `schema` como un
**string** JSON (`JSON.stringify(esquema)`). Pasarlo como objeto no falla con un error
claro: produce una generacion sin restringir, y el sintoma es un JSON invalido en la
salida, muy lejos de la causa.

#### Adaptador de servidor (v2)

```python
# adapters/llm/ollama.py
class MotorLLMOllama:
    """Adaptador de salida. Su unico trabajo: hablar con el motor local y devolver JSON.

    La regla de privacidad vive aqui: este adaptador no tiene ningun destino por defecto
    que sea una API de terceros.
    """

    def __init__(self, base_url: str, modelo: str, cliente: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._modelo = modelo
        self._cliente = cliente

    async def extraer(
        self, prompt: str, esquema: type[BaseModel], temperatura: float
    ) -> BaseModel:
        ultimo_error: Exception | None = None
        for intento in range(3):
            respuesta = await self._cliente.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": esquema.model_json_schema(),  # structured output
                    "options": {"temperature": temperatura},
                },
                timeout=300,
            )
            respuesta.raise_for_status()
            try:
                return esquema.model_validate_json(respuesta.json()["message"]["content"])
            except ValidationError as exc:
                # Reintento con el error de validacion en el prompt.
                ultimo_error = exc
                prompt = prompt + "\n\nLa respuesta anterior no cumple el esquema: " + str(exc)
        raise RespuestaInvalidaError(str(ultimo_error))
```

El **caso de uso** no sabe a donde va la llamada. La politica de privacidad se verifica en el
adaptador.

### 10.4 Seguimiento del trabajo: progreso, duracion y actividades

Un analisis es largo. El usuario tiene que saber **cuanto falta, cuanto lleva y que ha
pasado**, sin recargar la pagina y sin bloquear la aplicacion.

**Un modelo unico para los dos modos.** El seguimiento no vive "en el navegador" o "en el
servidor": vive en la tabla `trabajos`, y los dos modos escriben en ella con el mismo
contrato. La UI consume un solo endpoint y el modelo de datos no cambia cuando cambia el
modo.

**Reglas:**

- `progreso` es un entero de 0 a 100 y **nunca disminuye**. Escriba quien lo escriba.
- `progreso` se calcula por **fraccion de trabajo conocido**, no por tiempo transcurrido:
  con 50 bloques, cada bloque vale ~1.7 puntos. Proyectar por tiempo miente cuando un
  bloque es mas lento que los demas.
- `paso_actual` es texto para humanos ("analizando bloque 7 de 34"), no un estado de
  maquina: es lo ultimo que el usuario quiere leer.
- `duracion_ms` lo calcula el **servidor** a partir de `iniciado_en` y `finalizado_en`. El
  reloj del cliente no es confiable para eso.
- El navegador reporta el progreso **por el endpoint**, no escribiendo en la base. La base
  no acepta progreso de un cliente que no sea el dueno del trabajo.

```python
# application/use_cases/reportar_progreso.py
async def ejecutar(self, cmd: ReportarProgreso, ctx: AuditContext) -> Trabajo:
    ctx.permisos.exige("documentos.analizar")

    trabajo = await self.trabajos.obtener_por_id(cmd.trabajo_id)
    if trabajo is None:
        raise NoEncontradoError("Trabajo no encontrado")
    if trabajo.usuario_id != ctx.usuario_id:
        raise ProhibidoError("No puede reportar el progreso de otro trabajo")

    # Monotonia: el progreso no retrocede.
    if cmd.progreso <= trabajo.progreso:
        return trabajo

    await self.trabajos.actualizar_progreso(
        trabajo.id, progreso=cmd.progreso, paso_actual=cmd.paso_actual
    )
    if cmd.actividad is not None:
        await self.trabajos.registrar_actividad(trabajo.id, cmd.actividad)
    return trabajo
```

**Cola asincrona: vive en el cliente.** `[DECIDIDO]` Como el LLM se ejecuta en el navegador
(ADR-06), **no hay cola en el servidor** en la v1. La asincronia la aportan dos cosas:

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

**Trabajo abandonado.** Si el usuario cierra la pestana a mitad del analisis, el trabajo se
queda en `en_proceso` para siempre. Se resuelve con dos mecanismos:

- El cliente envia un **latido** con cada reporte de progreso. Un trabajo sin latido por mas
  de N minutos se considera abandonado.
- Una tarea de mantenimiento (un `cron` de Vercel) marca los trabajos sin latido como
  `interrumpido`, liberando el documento para poder reintentarse.

Sin esto, un analisis abandonado deja el documento en un limbo que el usuario ve como "en
proceso" para siempre.

**Cola en el servidor: para el futuro, no para la v1.** `[PROPUESTO]` Si se anade un modo
hospedado, la cola entra como `pgmq` dentro de Postgres: el mensaje lleva `trabajo_id` y
`documento_id`, y el worker consume desde alli. Se deja documentada porque el diseno del
trabajo ya la contempla, pero **la v1 no la necesita y no debe construirla**.

**Actualizacion en la UI.** Polling al endpoint de trabajo. Es suficiente para este volumen
y no obliga a mantener conexiones abiertas, lo que es una restriccion real en plataformas de
funciones. Si mas adelante hace falta, el mismo endpoint sirve para SSE.

### 10.5 El artefacto JSON y el DTO de salida

El resultado del analisis es **un JSON con los resumenes de todos los bloques y el resumen
ejecutivo**. Ese JSON es lo que se guarda y lo que se consulta.

```json
{
  "documento_id": "...",
  "plantilla": { "id": "...", "version": 1 },
  "total_bloques": 50,
  "resumenes": [
    { "indice": 0, "paginas": "1-3", "resumen": "...", "datos": { } }
  ],
  "resumen_ejecutivo": "...",
  "riesgos": [
    {
      "clave": "r-3f9a2c",
      "titulo": "Manejo de credenciales sin cifrar",
      "descripcion": "Las credenciales aparecen en texto plano en la seccion 4.2.",
      "datos": { "categoria": "Seguridad", "severidad": "Alta" },
      "evidencia": { "paginas": [12, 13], "cita": "El sistema almacena las claves en texto plano." },
      "confianza": "alta"
    }
  ]
}
```

**Como se guarda.** `analisis_documentos.resumenes` (JSONB) guarda el arreglo completo;
`resumen_ejecutivo` y `riesgos` se separan porque se consultan y filtran distinto. Los
bloques tambien se guardan en su propia tabla, que es la fuente para el detalle.

**Como se entrega.** El JSON **no** sale crudo de la API. Un DTO de salida lo mapea:

```python
class ResumenBloqueResource(BaseModel):
    indice: int
    paginas: str
    resumen: str

class EvidenciaResource(BaseModel):
    """Donde esta el riesgo en el documento. Sin esto no es verificable."""
    paginas: list[int]
    cita: str | None = None

class RiesgoResource(BaseModel):
    """Un riesgo. El envoltorio es fijo; `datos` lo define la plantilla."""
    clave: str
    titulo: str
    descripcion: str
    datos: dict
    evidencia: EvidenciaResource
    confianza: Literal["alta", "media", "baja"]

class AnalisisResource(BaseModel):
    """Lo que el cliente ve del analisis. La frontera de seguridad."""
    documento_id: UUID
    total_bloques: int
    resumen_ejecutivo: str | None
    riesgos: list[RiesgoResource]
    resumenes: list[ResumenBloqueResource]
    plantilla_version: int | None
```

**El contrato del resultado.** El `jsonb` de `riesgos` tiene una forma **fija**:
`clave`, `titulo`, `descripcion`, `evidencia` y `confianza` son **nuestros**;
`datos` es **de la plantilla** y ahi viven los campos de riesgo que defina el cliente.

Esa division es lo que permite que PP-13 se cierre de cualquier forma sin romper lo ya
construido, y lo que deja preparada la fase de gestion: la `clave` es estable dentro de
un analisis y la `evidencia` permite verificar el riesgo en la pagina del documento.

El contrato completo, con el porque de cada campo y las reglas de validacion, esta en
[`docs/CONTRATO-RESULTADO-ANALISIS.md`](docs/CONTRATO-RESULTADO-ANALISIS.md).

Reglas:

- El DTO decide que sale. Agregar un campo a la entidad **no** lo agrega al DTO.
- El DTO no contiene logica de negocio ni acceso a datos.
- El `JSONB` de la base es un detalle de persistencia. El DTO es el contrato publico: si el
  JSON cambia de forma, el DTO absorbe el cambio y el frontend no se entera.
- El backend valida el envoltorio **ademas** del contenido: `clave` unica, paginas de
  `evidencia` dentro del documento y cubiertas por algun bloque, `confianza` de un valor
  permitido. El cliente no es una frontera de confianza.

**El `indice` de bloque y el rango de paginas no son decoracion.** Cuando el sistema guarde
registros para responder preguntas (RAG), los resumenes por bloque son los fragmentos que
se indexan, y esas dos claves son lo que permite reconstruir de donde sale cada respuesta.
Guardarlos bien hoy es la mitad del trabajo del RAG de manana.

### 10.6 Reintentos y timeouts

- El numero de reintentos esta acotado (por defecto 2). Un reintento infinito en un worker
  es una bomba de trabajo.
- Cada llamada al LLM tiene timeout explicito. Sin timeout, un motor colgado deja el
  worker bloqueado para siempre.
- El backoff es exponencial con un tope.

---

## 11. Convenciones del frontend (Vue 3.5)

### 11.1 Estructura

```
frontend/src/
  api/         cliente HTTP tipado + interceptores
  stores/      Pinia: sesion, motor, documentos
  views/       paginas (rutas)
  components/  componentes presentacionales
  workers/     Web Worker para ETL/LLM en navegador (modo navegador_local)
```

### 11.2 Reglas

- **`<script setup>` con Composition API** en todos los componentes. Sin Options API.
- **TypeScript estricto.** Los tipos de la API se generan desde el OpenAPI del backend; no
  se escriben a mano.
- **El cliente HTTP centraliza el token.** Un solo interceptor anade el bearer y maneja 401
  con redireccion a login. Nunca se escribe el header de autorizacion a mano en un fetch.
- **El estado global vive en Pinia** (sesion, configuracion del motor, listado de
  documentos). El estado local de un componente vive en el componente.
- **Los componentes no llaman a la API directamente** si hay una tienda que lo hace. El
  componente pide a la tienda; la tienda llama a la API.
- **Nada de `any`.** Si el tipo no existe, se define o se genera.
- **Las marcas de tiempo se parsean en el limite.** La API entrega ISO-8601; el frontend no
  adivina el formato.

### 11.3 Cliente HTTP tipado

```typescript
// api/cliente.ts
const cliente = createClient({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  onRequest({ request, accessToken }) {
    if (accessToken) {
      request.headers.set('Authorization', `Bearer ${accessToken}`)
    }
  },
  onResponseError({ response }) {
    if (response.status === 401) {
      // limpiar sesion y redirigir a login, una sola vez
    }
  },
})
```

### 11.4 El modo navegador

`[DECIDIDO]` Es el **unico** camino de la v1. No hay modo hospedado (ADR-19).

- El ETL y el LLM corren en un **Web Worker**, para no bloquear la interfaz. Varios
  documentos se encolan en el cliente y se procesan uno a uno.
- El modelo se guarda en Cache API / IndexedDB con `navigator.storage.persist()`, previa
  aceptacion explicita en un modal. **No se usan cookies**: soportan 4 KB.
- La capacidad del equipo se detecta al entrar (`navigator.gpu`, memoria disponible) y se
  muestra **antes** de que el usuario elija un archivo. Si no hay WebGPU, el mensaje es
  explicito y sugiere Chrome o Edge: **nunca** un fallo posterior.
- **La descarga de 1.5 a 3 GB es el punto de friccion real del producto.** El usuario es
  personal administrativo: tiene que entender que esta descargando un modelo, cuanto
  lleva, y que se queda guardado en su equipo para las siguientes veces. La interfaz
  muestra el progreso de la descarga, explica que es una sola vez, y confirma la
  persistencia. Un `alert` generico no sirve.
- El progreso se muestra por bloque ("bloque 7 de 34"), porque el tiempo de espera es real
  y largo. Sin progreso visible, el usuario abandona.
- La funcion de chunking se **comparte con el backend** (mismo archivo, mismo algoritmo): si
  divergen, los rangos de pagina persistidos no coinciden con los calculados.
- El backend solo recibe los resultados ya extraidos y los persiste validando el esquema.
- **El cliente reporta el progreso, el servidor decide.** El cliente nunca escribe
  directamente en la base.

### 11.5 Despliegue

`[DECIDIDO]` Despliegue en niveles. Ver `docs/ARQUITECTURA.md` seccion 9 para el detalle.

| Nivel | Componente | Plataforma v1 |
|---|---|---|
| 1 | Frontend Vue estatico | Vercel (o cualquier CDN) |
| 2 | API FastAPI stateless | Vercel Functions (runtime de Python) |
| 3 | Datos e identidad | Supabase (Postgres + Auth + RLS + PostgREST) |
| 4 | Worker ETL con LLM | Docker en Cloud Run / Fly.io / servidor propio (v2) |

**Reglas que se derivan de la plataforma:**

- **El backend es stateless y HTTP adentro y HTTP afuera.** No usa conexion TCP a Postgres
  en el camino de ejecucion. Eso es lo que lo hace portable a Cloudflare Workers.
- **El limite de 4.5 MB del cuerpo de peticion es una restriccion de diseno, no un
  escollo.** El resultado del analisis cabe; el PDF no. Si alguna vez hay que subir el
  PDF, es porque se activo el modo servidor, y ese endpoint no va por Vercel Functions.
- **La funcion tiene 300 s por defecto.** La API solo recibe resultados: cabe de sobra.
- **Vercel no ejecuta Docker en produccion.** El `Dockerfile` es para el entorno local
  reproducible y para el worker de la v2.
- El `vercel.json` fija el `maxDuration` por ruta. Se fija explicitamente, para que un
  cambio de comportamiento no dependa del default.

```json
// vercel.json
{
  "functions": {
    "backend/api/index.py": {
      "maxDuration": 60,
      "excludeFiles": "{tests/**,**/*.test.py,fixtures/**}"
    }
  },
  "rewrites": [
    { "source": "/api/v1/(.*)", "destination": "/backend/api/index.py" }
  ]
}
```

**La version de Python NO se declara en el `vercel.json`.** Vercel la lee del
`requires-python` del `pyproject.toml` o de un `.python-version` en la raiz. La propiedad
`runtime` de `functions` es para runtimes **no soportados** de forma nativa (como
`vercel-php`); usarla para Python se ignora o rompe el despliegue. Lo mismo aplica a
`builds`/`routes`: `rewrites` es la forma actual.

> `excludeFiles` no es cosmetico. Las funciones de Python no se tree-shakean: Vercel
> empaqueta **todo** lo que alcanza en tiempo de build. Sin esto, los tests viajan al
> bundle de produccion.

---

## 12. Errores frecuentes (aprendidos a la fuerza)

Cada uno de estos se rompio, fue invisible, y costo tiempo de depuracion. estan aqui porque
vuelven.

### 12.1 Nunca auto-baselines las migraciones en desarrollo

Las herramientas de migracion tipo Flyway tienen una opcion de "baseline" para adoptar una
base de datos de produccion existente. En desarrollo **se salta silenciosamente la primera
migracion**.

Observado: la herramienta escribio una marca de baseline en la version 1 y nunca ejecuto la
migracion 1. La base conservo una tabla de 4 columnas mientras el codigo seleccionaba 13.
Todas las pruebas de seguridad pasaron, contra un esquema que no coincidia con el codigo.

- Desarrollo: las migraciones deben aplicar limpiamente a una base vacia, siempre.
- Nunca actives auto-baseline fuera de la adopcion en produccion.
- **Regla:** si tus pruebas pasan pero nunca ejecutaste la migracion contra una base vacia,
  tus pruebas no prueban nada.

### 12.2 Nunca edites una migracion ya aplicada

Las herramientas de migracion calculan un checksum de sus archivos. Editar una migracion
aplicada hace fallar la validacion al arrancar, con un error que senala a la herramienta, no
a tu cambio.

- Las correcciones de esquema o datos van en una **migracion nueva**.
- Excepcion: una base de desarrollo desechable. Borrala y vuelve a ejecutar desde cero: es
  mas rapido y mas limpio que una correccion incremental que nadie va a leer.

### 12.3 Las comas trailing antes del parentesis de cierre son errores de sintaxis

Una definicion de columna con coma antes del `)` —sobrante de agregar campos— falla al
parsear. Se ve bien mientras se lee.

- **Regla:** ejecuta cada migracion contra una base vacia antes de confiar en ella.

### 12.4 `now()` no puede aparecer en el predicado de un indice parcial

Los predicados de indice deben ser **IMMUTABLES**. Las funciones dependientes del tiempo
son STABLE, asi que se rechazan — y aunque se aceptaran, un indice cuyo predicado cambia con
el reloj esta semanticamente roto.

```sql
-- RECHAZADO: las funciones en el predicado deben ser IMMUTABLE
CREATE INDEX idx_locked ON usuarios (email)
    WHERE locked_until IS NOT NULL AND locked_until > NOW();

-- CORRECTO: indexa las filas; filtra por tiempo en la consulta
CREATE INDEX idx_locked ON usuarios (locked_until)
    WHERE locked_until IS NOT NULL;
```

### 12.5 Las clases de SQLState no son tipos de error

Una violacion de restriccion de integridad es una **clase**, no un codigo. `23502` es
not-null, `23503` es llave foranea, `23505` es unico, `23514` es check. Mapear toda la
clase a un solo mensaje convierte cada fallo de integridad en la misma mentira.

Observado: una violacion NOT NULL se reporto como "el correo ya existe", escondiendo el
error real detras de un mensaje plausible, y mandando la depuracion en direccion contraria.

- **Regla:** despacha por el codigo **exacto**, y deja que cualquier cosa desconocida caiga
  en un error de base de datos generico que preserve el original.

### 12.6 Reenvolver errores de dominio rompe el mapeo HTTP

Capturar un error de dominio y relanzarlo como error generico destruye su tipo. La mayoria
de los frameworks resuelven los manejadores por la clase del error **realmente lanzado** —
un 409 se degrada a 500.

- La capa de caso de uso no debe envolver errores: los errores de dominio ya son unchecked.

### 12.7 La concatenacion de bloques de texto no inserta espacios

En varios lenguajes, una cadena multilinea usada dentro de una concatenacion empieza
inmediatamente en su primer caracter. Una sentencia que termina en `RETURNING`
concatenada con una constante que empieza en `id` produce `RETURNINGid`.

- **Regla:** nunca dependas de espacios implicitos al componer SQL de fragmentos. Se
  explicito, y verifica la sentencia compuesta.

### 12.8 Una suite en verde puede no haber compilado

Algunos comandos de build compilan solo las fuentes de produccion. Los fuentes de prueba
que fallan al compilar simplemente no se construyen — y el resultado de la corrida anterior
se reporta como si fuera actual.

Observado: un metodo de prueba duplicado. Todos los "compile" pasaron, porque ninguno
compilo las pruebas.

- **Regla:** antes de confiar en una suite en verde, confirma que realmente reconstruyo.
  Limpia y ejecuta. Si viste "nothing to compile", no ejecutaste las pruebas.

### 12.9 El mapeo de filas debe coincidir columna por columna

Cuando un modelo gana un campo, todas las proyecciones, todos los `RETURNING` y todos los
mapeadores de fila deben cambiar. El desajuste aparece como un fallo en runtime lejos de la
edicion.

- **Regla:** mantén las listas de columnas como una constante compartida.

### 12.10 La serializacion de instantes necesita configuracion explicita

La mayoria de las librerias serializan instantes como un numero decimal de epoca si no se
les dice otra cosa. `1791569826.341885000` es tecnicamente valido y practicamente incorrecto
para una API.

- **Regla:** configura ISO-8601 explicitamente y afirmalo en una prueba sobre el **cuerpo
  real** de la respuesta.

### 12.11 No declares una defensa que el codigo no ejecuta

Documentar mitigaciones de seguridad que no estan implementadas es peor que no
documentarlas: genera confianza falsa. Se honesto en el codigo y en la documentacion sobre
que mitigaciones estan realmente activas.

---

## 13. Estrategia de pruebas

Las pruebas no son el ultimo paso. Son el contrato que dice que el backend se puede
conectar a un frontend sin sorpresas.

**Regla: un endpoint no esta terminado hasta que tiene una prueba que falla cuando el
endpoint esta mal.** Una prueba que no puede fallar no prueba nada.

Se organizan por superficie de ataque y etapa del ciclo de vida, no por clase. Quien integra
el frontend pregunta en este orden: ¿arranca?, ¿autentica?, ¿hace CRUD?, ¿aguanta carga?,
¿se rompe si alguien escribe mal?

**Donde vive cada prueba.** El backend y el frontend no usan la misma convencion, y no es
un descuido: lo que se prueba y la forma de probarlo son cosas distintas.

| Capa | Convencion | Ejemplo |
|---|---|---|
| Backend | Carpeta por tipo de prueba: `tests/unit/`, `tests/integration/`, `tests/contract/` | `backend/tests/unit/test_config.py` |
| Frontend | Archivo `*.spec.ts` **junto al componente** que prueba | `frontend/src/views/DocumentosView.spec.ts` |

En el frontend, la prueba vive con el componente porque el componente es la unidad que se
mueve: cuando cambia, la prueba se mueve con el. La convencion de carpeta del backend
responde a otra pregunta —¿esta prueba necesita una base de datos real?— y en el
frontend casi ninguna la necesita.

La consequencea practica: `npm run test` corre **todas** las pruebas del frontend, sin
filtros por tipo. Un filtro por carpeta solo tiene sentido cuando hay pruebas de un tipo
que no se pueden correr en cualquier maquina.

### 13.1 Capa 1 — Bootstrap

| Caso | Afirma |
|---|---|
| Endpoint de salud | 200 |
| Base de datos alcanzable | La salud informa "conectado" |
| Migraciones aplicadas | El historial lista todas las versiones, con exito |
| Arranque con base de datos vacia | Sin errores: detecta los defectos de migracion que nunca se ejecutan |

### 13.2 Capa 2 — Ciclo de vida del recurso central

Ciclo completo contra un servidor real. No mocks.

| Caso | Afirma |
|---|---|
| Crear valido | 202, el cuerpo refleja la entrada, persistido |
| Crear con hash duplicado | 409 — no 500 |
| Crear sin campo obligatorio | 422 / 400 |
| Crear con formato invalido | 400 |
| Leer existente | 200, datos exactos |
| Leer inexistente | 404 |
| Listar | 200, paginado con metadatos correctos |
| Listar vacio | 200, array vacio — no null |
| Actualizar existente | 200, campos cambiados |
| Actualizar inexistente | 404 |
| Borrar existente | 200, luego leer devuelve 404 |
| Borrar inexistente | 404 |
| Borrar dos veces | La segunda devuelve 404, no un error |
| Ciclo completo en secuencia | Crear -> leer -> actualizar -> borrar, estado correcto en cada paso |

**Afirma el cuerpo de la respuesta, no solo el status.** Un 201 con el payload equivocado
pasa una prueba de solo-status y rompe el frontend.

### 13.3 Capa 3 — Autenticacion

| Caso | Afirma |
|---|---|
| Credenciales validas | 200, token devuelto |
| Correo desconocido | 401 |
| Contrasena incorrecta | 401 |
| Cuenta inactiva | 401 |
| Cuenta bloqueada | 401 |
| Correo sin verificar | 401 si se exige verificacion |
| Login sin cuerpo | 400 |
| Login con campos vacios | 400 |
| Respuesta a credenciales invalidas | Mensaje **identico** para usuario desconocido y contrasena incorrecta |

### 13.4 Capa 4 — Ciclo de vida de la sesion

Los casos que de verdad rompen las integraciones de frontend.

| Caso | Afirma |
|---|---|
| Peticion autenticada con token valido | 200 |
| Peticion sin token | 401 en rutas protegidas |
| Peticion con token malformado | 401 — no 500 |
| Peticion con firma adulterada | 401 |
| **Dos logins, ambos tokens usados** | **Ambos funcionan: varios dispositivos es normal** |
| Logout, reuso del mismo token | **401 de inmediato, sin esperar la expiracion** |
| Revocar todas las sesiones | Todos los tokens previos dan 401 |
| Listar propias sesiones | Devuelve solo las de ese usuario |
| Revocar la sesion de otro usuario | 403 / 404 — **nunca** tiene exito |
| Token tras eliminar la cuenta | 401 |

Dos merecen enfasis:

- **El logout debe invalidar de inmediato.** Si el token sigue funcionando tras el logout,
  la revocacion no esta implementada y todo el diseno de sesion con estado es decoracion.
- **El acceso cruzado a sesiones de otro usuario debe rechazarse.** Devolver las sesiones
  de otro usuario es un error de autorizacion, no un detalle estetico.

### 13.5 Capa 5 — Inyeccion

Contra un servidor real con base de datos real. Los repositorios mockeados no detectan
esto: **la vulnerabilidad esta en la consulta**.

| Ataque | Entrada | Afirma |
|---|---|---|
| SQLi en un campo de texto | `' OR '1'='1' --` | Se trata como dato literal; sin 500; se guarda como la cadena literal |
| SQLi en un correo | `' UNION SELECT ... --` | 400 o se guarda literal, nunca se ejecuta |
| SQLi para borrado masivo | `'; DROP TABLE usuarios; --` | La tabla sigue existiendo despues |
| Ráfaga de SQLi concurrente | Mismo payload x 20 concurrentes | Sin 500 |
| XSS almacenado | `<script>alert(1)</script>` en un nombre | Se guarda y se devuelve tal cual; **la API no lo ejecuta** |
| Unicode / emoji | Correos y nombres con ellos | Aceptados o 400 limpio — nunca 500 |
| Entrada sobredimensionada | Cadena de 10 MB | 400 / 413 — no un error de memoria |
| Null / tipo equivocado | `"nombre": null`, `"nombre": 123` | 400 |
| Campos desconocidos en el cuerpo | Claves JSON extra | El comportamiento es deliberado y esta documentado |

**La asercion de limpieza es obligatoria para los payloads destructivos.** "No 500" no
basta: hay que afirmar que la tabla sobrevivio.

### 13.6 Capa 6 — Abuso y concurrencia

| Caso | Afirma |
|---|---|
| N usuarios creados simultaneamente | Todos tienen exito; sin 500; sin escrituras perdidas |
| Altas concurrentes con el mismo correo | Exactamente un 201; el resto 409 |
| 100 altas secuenciales | Sin agotamiento de conexiones, sin 500 |
| 100 actualizaciones sobre una fila | Estado final consistente |
| 100 borrados sobre una fila | El primero tiene exito; el resto 404 |
| CRUD mixto, muchos hilos | Sin 500 en ninguna parte |

### 13.7 Capa 7 — Contrato de serializacion

El integrador de frontend se amarra a esto, asi que se prueba explicitamente.

| Campo | Afirma |
|---|---|
| Marcas de tiempo | Cadena ISO-8601 que cumple RFC 3339 — **no** un numero decimal |
| Las marcas de tiempo parsean en JS | `new Date(valor)` devuelve el anio correcto |
| Booleanos | `true` / `false` de JSON, no `0`/`1` ni `"true"` |
| Nulos | `null` explicito donde falta — ni claves ausentes ni `"null"` |
| IDs | Los numeros siguen siendo numeros; los IDs grandes no pierden precision |
| Envelope | La misma forma en exito y en error |
| Envelope de error | Contiene un identificador legible por maquina, no solo prosa |

> Un epoch decimal para `Instant` es el ejemplo clasico de un campo que pasa todas las
> pruebas de status y aun asi rompe el frontend: JavaScript espera milisegundos, la API
> envia segundos, y el cliente renderiza 1970 sin error en ninguna parte.
> **Afirma el formato en el cuerpo de la respuesta.**

### 13.8 Capa 8 — Dominio y pipeline (unitaria)

Sin base de datos, sin red, sin LLM real.

| Caso | Afirma |
|---|---|
| Chunking con solapamiento | Los bloques cubren todas las paginas; el solapamiento es el configurado |
| Chunking con parametros invalidos | `tamano_paginas < 1` y `overlap >= tamano` lanzan error |
| Validacion de la salida del LLM | Un JSON que no cumple el esquema produce reintento y, agotado, error de dominio |
| Idempotencia | Reprocesar un documento completado no duplica filas |
| Documento sin capa de texto | Se marca como error explicito, no como analisis vacio |
| Calculo del hash | El mismo contenido produce el mismo hash; contenido distinto, otro hash |

---

## 14. Checklist de verificacion

La version completa, con los gates de privacidad y de entrega, esta en
[`CHECKLIST.md`](CHECKLIST.md). Resumen:

**Esquema**
- [ ] Las migraciones aplican limpio contra una base **vacia**
- [ ] No hay auto-baseline fuera de adopcion en produccion
- [ ] Ninguna migracion aplicada fue editada
- [ ] RLS activo y verificado con un usuario real

**Seguridad**
- [ ] Contrasenas con argon2id/bcrypt (si el backend emite credenciales)
- [ ] Cada hash semilla **verificado** con la funcion de verificacion real
- [ ] Ningun cuerpo de respuesta contiene un hash de contrasena ni de token
- [ ] `service_role` no atiende peticiones de usuario final
- [ ] El tipo real del archivo se valida, no solo la extension

**Arquitectura**
- [ ] Ningun router llama a un repositorio directamente
- [ ] Ningun caso de uso construye schemas de HTTP
- [ ] `domain/` no importa nada de `adapters/` ni de frameworks
- [ ] Cada entidad paso el gate de decision: sin DTOs vacios, sin casos de uso passthrough
- [ ] Las listas de columnas son una constante compartida

**Errores**
- [ ] Cada error de dominio mapea a su status previsto
- [ ] Ningun error de dominio se captura y reenvuelve en un generico
- [ ] Las violaciones de integridad se despachan por el codigo SQLState exacto

**Correccion**
- [ ] Las marcas de tiempo se serializan en ISO-8601, afirmadas sobre el **cuerpo real**
- [ ] Un build limpio compila **las pruebas**, no solo las fuentes de produccion
- [ ] La suite se reejecuto desde limpio y se reconstruyo de verdad

**Privacidad**
- [ ] El PDF se archiva en almacenamiento privado y **solo** se elimina al borrar el
      documento. No se borra al terminar el pipeline (ADR-20)
- [ ] Ningun texto extraido aparece en logs, trazas ni metricas

---

## 15. Como se trabaja: la HU guia, el checklist verifica

> Esta seccion se lee **antes** de escribir codigo. Es la que evita las dos equivocaciones
> mas comunes: implementar "el gate" sin saber que HU es, y cerrar una HU sin activar los
> items del checklist que le tocan.

### 15.1 La regla

**Las HU guian.** Son la unidad de trabajo. Cada una describe un comportamiento del
usuario, con su camino feliz, sus caminos de error y sus criterios de aceptacion. Se
implementa **una HU**, no "un gate".

**El checklist verifica.** Un gate **no se implementa**: es una condicion que el codigo
tiene o no tiene. Se marca `[x]` cuando el codigo que lo sustenta existe y esta
verificado, **con la evidencia al lado**.

> Un gate no es una tarea. Es una propiedad que el codigo tiene o no tiene.

### 15.2 El ciclo, en cuatro pasos

```
1. Elegir la HU siguiente (por el grafo de dependencias de docs/HU/INDICE.md)
2. Implementar su comportamiento, con sus pruebas
3. Verificar los items del checklist que esa HU toca  ->  marcar [x] con la evidencia
4. La HU esta lista cuando sus criterios de aceptacion dan PASS
```

El paso 3 es el que conecta las dos cosas: **al cerrar una HU se activan sus items**. No
al reves.

**El criterio de "PR" de un item es concreto:** o hay una prueba que lo demuestra, o se
puede señalar la linea de codigo o el comando que lo demuestra, o **no esta cumplido**.
Un `[x]` sin evidencia es una promesa, y una promesa no cierra un gate.

### 15.3 Que HU toca que gate

El mapa esta en [`CHECKLIST.md`](CHECKLIST.md), seccion **"Gates por HU"**. Es el unico
lugar donde se ve, para todas las HU, que items se activan al cerrar cada una.

Antes de empezar una HU, mirar esa fila. Al terminar, marcar esos items.

### 15.4 El nombre de la rama

La rama es la unidad de entrega, y la **HU** es lo que se entrega. Por eso lleva el
numero de la HU:

```
feat/hu-01-sesion
feat/hu-06-carga-documento
fix/hu-09-consulta-paginacion
```

| Que hace la rama | Nombre | Ejemplo |
|---|---|---|
| Cierra una HU | `feat/hu-<NN>-<que hace>` | `feat/hu-06-carga-documento` |
| Cierra una HU y arregla algo | `fix/hu-<NN>-<que hace>` | `fix/hu-09-consulta-paginacion` |
| Es un bloque que **no** es una HU | `feat/<bloque>-<que hace>` | `feat/migracion-esquema-rls` |
| Solo documentacion | `docs/<que documenta>` | `docs/contrato-resultado` |

El tercer caso existe porque hay trabajo que no cierra ninguna HU: la migracion, el
esqueleto y los contratos son **bloques**, y se nombran por lo que hacen.

> El numero de HU es lo que hace util la convencion: sin el, una rama dice que *area*
> toca, pero no que **cierra**.

### 15.5 Una rama por HU, no una por capa

El backend y el frontend de una HU van **en la misma rama**, en el mismo pull request.

La razon es el ciclo: una HU se cierra cuando sus criterios de aceptacion dan PASS y sus
items del checklist quedan marcados con la evidencia. Con ramas separadas, la HU queda
abierta dos pull requests y hay un estado intermedio en el que "la HU esta a medio hacer".

### 15.6 Antes de abrir el pull request

- [ ] La rama esta actualizada con `main`
- [ ] La rama dice que HU cierra, y el PR lo repite en el titulo
- [ ] Los **criterios de aceptacion** de la HU tienen prueba
- [ ] Los **items del checklist** que esa HU toca estan marcados, con evidencia
- [ ] El PR explica el **por que**, no solo el **que**
- [ ] No hay secretos, ni `.env`, ni datos reales de cliente

La guia completa de commits y pull requests esta en
[`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 16. Gate de readiness: el backend esta listo para un frontend?

Ejecutar antes de declarar la API consumible. Cada item debe verificarse contra un
**servidor corriendo**, no un mock.

**Endpoints**
- [ ] El endpoint de salud responde
- [ ] Toda ruta esta documentada con metodo, ruta, forma de peticion y de respuesta
- [ ] Los status coinciden con la tabla de la seccion 1.10

**Contrato**
- [ ] Las marcas de tiempo son ISO-8601 y verificadas en un `Date` de JavaScript
- [ ] Las respuestas de error comparten una sola forma de envelope
- [ ] La paginacion devuelve metadatos, no un array desnudo
- [ ] Los DTO de salida no exponen ningun campo sensible (inspeccion del cuerpo real)

**Auth**
- [ ] El login devuelve un token usable de inmediato
- [ ] Las rutas protegidas rechazan tokens ausentes, malformados y adulterados
- [ ] El logout invalida el token de inmediato
- [ ] Dos logins simultaneos funcionan ambos

**Datos**
- [ ] El ciclo de vida CRUD pasa de punta a punta
- [ ] Las filas con soft delete quedan excluidas de las lecturas
- [ ] Los valores unicos duplicados devuelven 409

**Resiliencia**
- [ ] La suite de inyeccion pasa sin 500 y sin destruir datos
- [ ] La suite de concurrencia pasa
- [ ] Las cuentas bloqueadas, inactivas y eliminadas no pueden iniciar sesion

**Reproducibilidad**
- [ ] Las migraciones aplican limpio a una base vacia
- [ ] Los logins de los datos semilla estan verificados contra el verificador real

**Pipeline**
- [ ] La subida devuelve 202 y el documento queda encolado
- [ ] El estado del documento es consultable hasta que el pipeline termina
- [ ] Un documento invalido produce un error explicito, no un analisis vacio

**Regla de la puerta:** si un item falla, el backend no esta listo. Un frontend construido
sobre una API a medias absorbe cada hueco como si fuera su propio error.

---

## 17. Anadir una entidad nueva

1. **Escribe la migracion.** Incluye los campos de seguridad desde el dia uno
   (`creado_en`, `actualizado_en`, `eliminado_en`, `organizacion_id`).
2. **Ejecutala contra una base vacia.** Confirma.
3. **Entidad de dominio.** Inmutable, sin concerns de serializacion, en `domain/entities/`.
4. **Puertos.** En `domain/ports/`, solo los metodos que el caso de uso usa.
5. **Gate de decision.** Crea solo lo que las respuestas exigen.
6. **Implementacion del puerto.** En `adapters/supabase/`, con la constante de columnas
   compartida.
7. **Caso de uso.** En `application/use_cases/`. La transaccion vive aqui.
8. **Adaptador de entrada.** En `adapters/http/routers/`. Solo orquestacion.
9. **Schemas de entrada y salida.** En `adapters/http/schemas/`. La Resource decide que
   sale.
10. **Registra el router** en `main.py`, una sola vez.
11. **Conecta las dependencias** en `adapters/http/deps.py`.
12. **Escribe las pruebas** del caso de uso: ciclo de vida CRUD como minimo.
13. **Si la entidad exige una accion controlada**, agrega el permiso a la matriz en datos
    (`permisos` + `rol_permisos`) y comprueba el permiso en el caso de uso. No lo
    compruebes solo en el router, y no lo codifiques como un `if rol == "admin"`.
14. **Pasa el checklist y el gate de readiness.**

---

## 18. Referencia

| Documento | Que contiene |
|---|---|
| [`docs/CONTEXTO.md`](docs/CONTEXTO.md) | Producto: que hace, para quien, con que restricciones |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Stack, estructura, modelo de datos, ADR |
| [`docs/DECISIONES-PENDIENTES.md`](docs/DECISIONES-PENDIENTES.md) | Preguntas abiertas con supuestos |
| [`CHECKLIST.md`](CHECKLIST.md) | Gates de verificacion completos |
| [`AGENTS.md`](AGENTS.md) | Reglas del repositorio |
| `docs/legacy/SKILL.ORIGINAL.md` | Version original de este skill (en capas, multi-lenguaje) |
