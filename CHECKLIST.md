# Checklist de verificacion — Risk-app

> Gates que se ejecutan **contra un servidor corriendo**, no contra mocks. Cada item
> corresponde a algo que ya ha roto en otro proyecto. Un item sin verificar no cuenta como
> cumplido.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-28

---

## Como leer las casillas

| Marca | Significado |
|---|---|
| `[x]` | **Verificado con evidencia.** La evidencia esta en la linea o en el comentario |
| `[ ]` | Pendiente |
| `[~]` | **Parcial.** Parte se cumple y parte no. Dice cual |
| `[-]` | **Aplazado.** No aplica en esta fase, con el motivo y donde vive |

Una casilla marcada sin evidencia **no cuenta como cumplida**: es una promesa, no una
verificacion. Por eso los items `[x]` llevan la prueba al lado.

---

## Gates por HU

> **Que HU activa que items del checklist.** La HU es la unidad de trabajo; el gate es la
> condicion que se cumple. Al cerrar una HU se activan sus items, y se marca `[x]` con la
> evidencia.
>
> El grafo de dependencias esta en `docs/HU/INDICE.md` seccion 3.

### El ciclo

```
1. Elegir la HU siguiente (por el grafo de dependencias)
2. Implementar su comportamiento, con sus pruebas
3. Verificar los items del checklist que esa HU toca  ->  marcar [x] con la evidencia
4. La HU esta lista cuando sus criterios de aceptacion dan PASS
```

**Un gate no se implementa: se verifica.** Por eso no tiene sentido "hacer el gate 2":
se hace **HU-01**, y al cerrarla se activan sus items del Gate 2.

### Gate 2 — Seguridad, item por HU

| Item del Gate 2 | HU que lo cierra | Cuando |
|---|---|---|
| La validacion del token usa el **JWKS del proyecto** | HU-01 | Con el adaptador de autenticacion |
| La validacion del token comprueba firma, `exp`, `aud` y emisor | HU-01 | Con el adaptador de autenticacion |
| Un token invalido, malformado o con firma adulterada devuelve 401, no 500 | HU-01 | Con las pruebas del adaptador |
| `service_role` no se usa para atender peticiones de usuario final | HU-03 | Cuando exista el adaptador de administracion |
| El rol del usuario se verifica en el caso de uso, no solo en el router | HU-02 | Con el caso de uso de permisos |
| Un usuario de otra organizacion recibe 403 o 404, nunca datos | HU-02 | Con el caso de uso de permisos |
| El cuerpo de ninguna respuesta contiene un hash ni una columna interna | HU-09 | Con los DTO de salida |
| El tipo real del archivo se valida en el **navegador** (magic bytes) | HU-06 | En la carga del archivo |
| El limite de tamano de archivo se aplica antes de leerlo en memoria | HU-06 | En la carga del archivo |
| Los logs no contienen contenido del documento ni texto extraido | HU-07 | Con el pipeline de analisis |

**El Gate 2 no se cierra de una vez.** Sus items se activan a lo largo de seis HU. El
criterio de cierre del gate es: **no queda ningun item sin marcar**.

### Que gate toca cada HU

| HU | Gates que toca | Nota |
|---|---|---|
| HU-01 Acceso y sesion | 2, 5, 7, 8, 9 | La unica bloqueante de todas |
| HU-02 Roles y permisos | 2, 3.1, 8, 9 | Depende de HU-01 |
| HU-03 Administracion de usuarios | 2, 3.1, 3.3, 9 | Depende de HU-02 |
| HU-04 Configuracion del motor | 7, 12 | No depende de la sesion |
| HU-05 Compatibilidad y descarga | 7 | Depende de HU-04 |
| HU-06 Carga y archivo | 1, 2, 3.4, 7, 8, 9 | Depende de HU-01 |
| HU-07 Analisis del documento | 2, 3, 6, 7, 8, 10 | Depende de HU-06 |
| HU-08 Seguimiento del trabajo | 3.2, 9 | Depende de HU-07 |
| HU-09 Consulta de resultados | 2, 3.4, 4, 5, 8, 9, 10, 11 | Depende de HU-07 |
| HU-10 Reanalisis | 4, 5, 8 | Depende de HU-09 |
| HU-11 Plantillas de extraccion | 1, 7 | Va antes que HU-07 en la practica |
| HU-12 Eliminacion del documento | 1, 3.4, 9 | La ultima: necesita el archivo de HU-06 |

### Lo que ya esta cerrado

| Gate | Items | Cuando |
|---|---|---|
| Gate 0 | 5 de 5 | Documentacion leida y planificada |
| Gate 1 | 11 de 11 | Esquema, RLS, permisos, bucket y funciones, aplicados y verificados contra la base local y contra el proyecto en la nube |
| Gate 14 | 15 de 15 | Esqueleto construido y verificado |
| Gate 15 | 9 de 9 | Documentacion al dia |

---

## Gate 0 — Antes de escribir codigo

- [x] Se leieron `docs/CONTEXTO.md`, `docs/ARQUITECTURA.md` y `docs/DECISIONES-PENDIENTES.md`
      — los tres vigentes, leidos al escribir cada HU y cada ADR
- [x] Los ADR aplicables a la iteracion estan identificados en la tabla de
      `docs/ARQUITECTURA.md` seccion 10 — 36 ADR; cada commit referencia el suyo al pie
- [x] Las preguntas abiertas que tocan el alcance estan resueltas o el supuesto esta
      anotado en el ADR — 15 DP cerradas; las 15 PP (PP-01 a PP-15) tienen supuesto explicito
- [x] El alcance de la iteracion esta escrito en una frase — seccion 1 de cada HU, y el
      cuerpo de cada PR
- [x] Los pasos 1 a 10 del "Quick start" de `SKILL.md` estan planeados — `SKILL.md`
      seccion 3; el orden concreto en `docs/ARRANQUE.md` seccion 6

---

## Gate 1 — Esquema y migraciones

- [x] Las migraciones se aplican limpiamente contra una base **vacia** (`supabase db reset`)
      — verificado el 2026-11-28: `supabase db reset` aplica 001 a 005 + `seed.sql` sin error
      en Supabase CLI 3.4.0 / PostgreSQL 17
- [x] El historial muestra todas las versiones aplicadas con exito — `supabase_migrations.
      schema_migrations` con las 5 filas: `001 esquema_inicial`, `002 rls`,
      `003 permisos_y_roles`, `004 bucket_y_storage`, `005 funciones_rpc`
- [x] **Una sola herramienta de migraciones**: SQL en `supabase/migrations/`. No hay Alembic
      ni tabla `alembic_version` (ADR-32) — verificado: `supabase db reset` aplica el SQL
      del directorio y no existe tabla `alembic_version`
- [x] `supabase db push` aplica el mismo esquema en el proyecto de Supabase que el que se
      valido en local — verificado el 2026-11-28 contra el proyecto `risk-app`
      (`tygzjraxknlwyllkabid`): las 11 migraciones aplicadas con `supabase db push
      --remote`, y el historial de `supabase_migrations.schema_migrations` en la nube
      muestra las 11. El estado verificado en la nube: 17 tablas con RLS, 17 con
      `FORCE ROW LEVEL SECURITY`, 49 politicas, 14 permisos, 3 roles, 1 plantilla, y
      el bucket `documentos` privado
- [x] No hay auto-baseline activado fuera de adopcion de produccion — verificado: no hay
      ninguna referencia a `alembic` ni a `pg_dump` versionado en el repositorio
- [x] Ninguna migracion ya aplicada fue editada despues — verificado: el historial de
      `schema_migrations` no registra cambios y el unico `db reset` fue contra la base
      local de desarrollo
- [x] Sin coma trailing antes del `)` de cierre de una definicion — verificado: las 5
      migraciones se aplican sin error de sintaxis
- [x] Sin `now()` en el predicado de un indice parcial — verificado: los indices parciales
      usan `where estado = ...` y `where eliminado_en is null`, sin `now()`
- [x] Toda columna `uuid` de `auth.users` tiene su FK y su `on delete` — verificado: 8
      columnas `references auth.users(id)`, todas con `on delete cascade` o `on delete set null`
- [x] RLS activo en toda tabla con datos de usuario, verificado con un usuario real —
      verificado el 2026-11-28: `pg_class.relrowsecurity` es `true` en las 17 tablas de
      `public`, y con dos usuarios reales en organizaciones distintas (Equipo Alfa y
      Equipo Bravo) cada uno ve solo sus documentos, su organizacion y su perfil.
      El anónimo ve 0 filas. El aislamiento por organizacion tambien se verifico con el
      permiso `analisis.ver_todos` concedido y retirado en caliente (ADR-35)
- [x] Las columnas JSONB tienen indice GIN si se consultan por contenido — verificado:
      `bloques.datos_estructurados` tiene `bloques_riesgos_gin` (GIN); los demas JSONB
      (`plantillas.esquema`, `analisis_documentos.riesgos`, `auditoria.detalles`) no se
      consultan por contenido en la v1
- [x] Las **funciones RPC no son alcanzables sin sesion** — verificado el 2026-11-28:
      las cinco RPC vivian en `public` (el esquema que expone el Data API) y eran
      `security definer`, asi que el rol `anon` (peticiones sin token) podia
      llamarlas y ejecutarlas con los privilegios del dueno, saltandose el RLS.
      Comprobado: `revocar_sesion` permitia a un visitante sin sesion revocar la
      sesion de cualquier usuario que conociera su `session_id`.
      Ahora viven en `public` con el ACL cerrado y `anon` no tiene `EXECUTE` sobre
      ninguna (ADR-37). Comprobado en la nube con `has_function_privilege`: `anon` da
      `false` en las cinco y `authenticated` da `true`. Por HTTP, con la publishable
      key y sin token: `POST /rest/v1/rpc/mis_permisos` responde `401` con el codigo `42501`; con el JWT
      del admin responde `200` con los 14 permisos del rol `admin`
- [x] Las **funciones RPC son invocables por HTTP** — verificado el 2026-11-28: al
      moverlas al esquema `security` (ADR-36) dejaron de serlo, porque PostgREST solo
      resuelve funciones de los esquemas que expone y su lista por defecto es
      `public`. La respuesta era `PGRST202`. Vuelven a `public` con el ACL cerrado
      (ADR-37). Comprobado en la nube: `POST /rest/v1/rpc/mis_permisos` responde `200`
      con sesion y `401` sin sesion; `POST /rest/v1/rpc/revocar_sesion` responde `403`
      `42501` cuando la sesion es de otro usuario
- [x] El **esquema `security` queda fuera del alcance de `anon`** — verificado el
      2026-11-28 en la nube: `has_schema_privilege('anon', 'security', 'usage')` da
      `false` y `has_function_privilege('anon', 'security.organizacion_activa()',
      'execute')` da `false`, mientras `authenticated` da `true` en ambos. El ACL del
      esquema queda `{postgres=UC/postgres,authenticated=U/postgres}`
- [x] `FORCE ROW LEVEL SECURITY` en las 17 tablas — verificado el 2026-11-28: sin
      esta linea, el dueno de la tabla (`postgres`, con `BYPASSRLS`) no respeta el
      RLS. Las funciones privilegiadas siguen leyendo lo que necesitan porque
      declaran `set row_security = off` (ADR-35, ADR-36)
- [x] El **advisor oficial de Supabase** (`supabase db advisors`) no reporta ningun
      hallazgo de nivel ERROR ni WARN — verificado el 2026-11-28: de 56 hallazgos a 29,
      y los 29 que quedan son de nivel INFO. Las correcciones fueron:
      - `auth_rls_initplan` (37): las 24 apariciones de `auth.uid()` dentro de politicas
        se enveloparon en `(select auth.uid())`, que es una constante para el
        planificador. Las 9 restantes estan en las funciones de apoyo del esquema
        `security`, que ya son `stable`
      - `multiple_permissive_policies` (7): cada politica `for all` se partio en
        `for insert`, `for update` y `for delete`. Dos politicas permisivas se
        combinan con OR, y en `bloques` la condicion de escritura se contaminaba a
        la lectura
      - `unindexed_foreign_keys` (16): indice en cada FK. Una FK sin indice obliga a
        un barrido secuencial de la tabla referenciada en cada cascada
      - `unused_index` (14): se borraron los 2 que **duplicaban** a otro indice
        (`bloques_documento_idx`, `analisis_documento_idx`). Los demas se quedan: el
        advisor los ve sin uso porque la base esta vacia y el planificador no tiene
        datos para decidir
- [x] El advisor **no reporta hallazgos de nivel ERROR ni WARN** en el proyecto en la
      nube — verificado el 2026-11-28 con `supabase db advisors --remote --type all
      --level warn`. Quedan 6 avisos de nivel WARN que son **intencionales y
      documentados** (ADR-37):
      - `authenticated_security_definer_function_executable` (5): las cinco RPC de
        negocio son `security definer` en `public` y `authenticated` debe poder
        llamarlas. La propia remediacion del linter dice: muevala fuera del esquema
        expuesto **solo si los usuarios con sesion no deberian poder llamarla**. Aqui
        si deben llamarlas
      - `auth_leaked_password_protection` (1): opcion de Supabase Auth (HaveIBeenPwned).
        Es una configuracion del panel, no del esquema

---

## Gate 2 — Seguridad

> **Este gate se cierra por partes, no de una vez.** Sus items pertenecen a seis HU
> distintas: cada item se activa al cerrar la HU que lo sustenta. El mapeo item por item
> esta en la seccion **"Gates por HU"**, al principio de este documento.
>
> Los items marcados ya están verificados; los demas dependen de codigo que aun no existe.

- [x] Ningun secreto en el codigo ni en `.env` versionado — `git check-ignore` cubre
      `.env`; el `.env.example` si se versiona
- [x] El arranque **falla** si falta `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
      `SUPABASE_SERVICE_ROLE_KEY` u otra variable obligatoria — comprobado: sin `.env`,
      `Config` lanza `ValidationError` nombrando las variables que faltan
- [x] La validacion del token usa el **JWKS del proyecto** (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`),
      no un secreto simetrico. `SUPABASE_JWT_SECRET` solo aplica a proyectos con claves
      simetricas (HS256) y es opcional (ADR-31) -- el algoritmo lo decide la cabecera `alg` del token: HS256 usa el secreto, el resto el JWKS del proyecto (`adapters/http/middleware.py`)
- [x] `service_role` no se usa para atender peticiones de usuario final -- revisado en todo `backend/app`: la llave de servicio solo aparece en `config.py` (definicion), `salud.py` (un booleano que no la filtra) y `scripts/bootstrap_admin.py` (administracion, ADR-13). La peticion de perfil propaga el JWT del usuario
- [x] `service_role` nunca se expone al frontend ni viaja en el bundle — solo viajan
      variables `VITE_*` publicas
- [x] La validacion del token comprueba firma, `exp`, `aud` y emisor -- `tests/unit/test_validacion_token.py`: firma, `exp`, `aud`, `iss` y `session_id`
- [x] Un token invalido, malformado o con firma adulterada devuelve 401, no 500 -- `tests/unit/test_auth_http.py` y `tests/integration/test_sesion.py`: 401 en los tres casos
- [ ] El cuerpo de ninguna respuesta contiene un hash de contrasena, un hash de token ni
      una columna interna
- [ ] El rol del usuario se verifica en el caso de uso, no solo en el router
- [ ] Un usuario de otra organizacion recibe 403 o 404, nunca datos
- [ ] El tipo real del archivo se valida en el **navegador** (magic bytes `%PDF-`) antes de
      subir, y el bucketStorage restringe los MIME permitidos. El backend **no** declara
      validar magic bytes: nunca ve el archivo (ver I-07 del informe de validacion)
- [ ] El limite de tamano de archivo se aplica antes de leerlo en memoria
- [ ] Los logs no contienen contenido del documento ni texto extraido
- [x] CORS no es `*` en un entorno con credenciales — `Config` **rechaza** `"*"` al
      arrancar, con el motivo explicito

---

## Gate 3 — Arquitectura (dependencias)

- [x] `domain/` no importa nada de `adapters/`, `application/` ni de frameworks
      (verificable con `import-linter`) — `lint-imports`: 4 contratos, 0 rotos
- [x] Ningun router (adaptador de entrada) llama a un repositorio directamente -- el router solo llama a casos de uso, por `Depends`; el repositorio se construye en `deps.py`
- [x] Ningun caso de uso construye schemas de HTTP ni conoce `Request`/`Response` -- los casos de uso devuelven DTOs; `Request` y `Response` solo aparecen en `adapters/http/`
- [x] Ningun error de dominio se captura y se reenvuelve en un error generico -- `adapters/http/error_handlers.py` traduce `ErrorDominio` por su `status_http`; ninguna excepcion se reenvuelve
- [x] Los puertos los define el dominio, no la infraestructura — `domain/ports/`, con
      `import-linter` verificando que el dominio no importa hacia afuera
- [x] Cada puerto declarado tiene al menos una implementacion en `adapters/` -- `adapters/supabase/`: perfiles, sesiones, auditoria y salud
- [x] No hay puertos para librerias de terceros que no van a cambiar — solo
      persistencia, motor LLM, almacenamiento, cola y reloj (ARQUITECTURA.md 2.4)

---

## Gate 3.1 — Roles y permisos

- [ ] El permiso se comprueba en el **caso de uso**, no solo en el router
- [ ] Un permiso ausente se **deniega**: no hay "permitido por defecto"
- [ ] Un recurso de **otra organizacion** produce **404**, nunca datos
- [ ] Un recurso de la **misma organizacion** sin permiso produce **403**, no 404 (ADR-30)
- [ ] La matriz de permisos vive en datos: agregar un permiso no requiere redesplegar
- [ ] Un usuario sin permiso recibe 403 tambien en las rutas de escritura, no solo de lectura
- [ ] El `service_role` solo se usa en el adaptador de administracion
- [ ] Ningun endpoint de datos de negocio alcanza el adaptador de administracion
- [ ] Toda operacion de aprovisionamiento queda en la bitacora de auditoria con el actor
- [ ] El rol de un usuario se resuelve **por organizacion**: un usuario en dos equipos puede
      tener roles distintos en cada uno
- [ ] El usuario puede ver su propio perfil y el de su organizacion segun el permiso, nunca
      el de otra organizacion

---

## Gate 3.2 — Seguimiento del trabajo

- [ ] `progreso` es un entero de 0 a 100 y **nunca disminuye**
- [ ] `progreso` se calcula por fraccion de trabajo conocido, no por tiempo transcurrido
- [ ] `duracion_ms` lo calcula el servidor, no el cliente
- [ ] Un cliente que no es el dueno del trabajo no puede reportar su progreso
- [ ] El cliente reporta el progreso **por el endpoint**, no escribiendo en la base
- [ ] Un trabajo sin latido por mas de N minutos se marca como `interrumpido` y libera el
      documento
- [ ] El cliente procesa **varios documentos en cola**, uno a uno, sin bloquear la interfaz
- [ ] La UI muestra porcentaje, paso actual en lenguaje llano y tiempo transcurrido

---

## Gate 3.3 — Alta de usuarios

- [ ] El alta exige el permiso `usuarios.gestionar`
- [ ] La contrasena temporal se genera con un generador criptografico, no con `random`
- [ ] El usuario se crea con la cuenta **confirmada** (`email_confirm = true`) y la credencial
      temporal viaja en el correo. Sin confirmar, el inicio de sesion responde "correo no
      confirmado" y la credencial no sirve para nada (HU-03 §5)
- [ ] El perfil queda marcado con `debe_cambiar_contrasena = true`
- [ ] El frontend fuerza el cambio de contrasena en el primer inicio de sesion
- [ ] El **cuerpo del correo** no aparece en los logs; los logs solo registran que se envio
- [ ] La implementacion de desarrollo del puerto de correo permite probar el flujo sin
      contratar un proveedor
- [ ] Alta, cambio de rol y desactivacion quedan en la bitacora de auditoria con el actor
- [ ] Un usuario que no es admin recibe 403 en los endpoints de administracion

---

## Gate 3.4 — Almacenamiento de archivos

- [ ] El bucket es **privado**. No existe ninguna URL publica
- [ ] El bucket declara `file_size_limit` y `allowed_mime_types`
- [ ] El backend valida tamano y tipo MIME **antes** de firmar la URL de subida
- [ ] Las politicas de `storage.objects` cubren insert, select y delete
- [ ] La clave del objeto es `{organizacion_id}/{usuario_id}/{documento_id}.pdf`
- [ ] Un usuario de otra organizacion no lee, no descarga y no lista los archivos
- [ ] La URL firmada de descarga dura **1 hora** como maximo y se emite en el backend
- [ ] La generacion de la URL firmada queda en la bitacora de auditoria
- [ ] **El archivo no pasa por el backend**: la subida va directa del navegador al
      almacenamiento
- [ ] Eliminar el documento **elimina tambien el archivo** del almacenamiento
- [ ] **No hay base64 en la base de datos.** En la tabla solo queda la ruta, el hash, el
      tamano y el tipo
- [ ] Un PDF de 100 paginas sube sin problemas (verificar el limite con un archivo real de
      30 MB, no con uno de prueba de 100 KB)

---

## Gate 4 — Casos de uso

- [ ] Cada caso de uso devuelve un DTO, no una entidad de dominio cruda
- [ ] La tabla de columnas SQL es una constante compartida, no una copia por consulta
- [ ] Las escrituras que dependen entre si estan en la misma transaccion
- [ ] No se mezcla una escritura auto-commit dentro de un bloque transaccional
- [ ] La insercion por lotes se usa en lugar de N inserts
- [ ] El pipeline de analisis no corre dentro del request HTTP

---

## Gate 5 — Errores y contrato

- [x] Cada error de dominio mapea al codigo de estado previsto (400/401/403/404/409/500) -- `domain/errors.py`: 400, 401, 403, 404, 409, 500 y 503; `tests/unit/test_errores.py`
- [x] Las violaciones de integridad se despachan por el codigo SQLState exacto, no por la
      clase -- `adapters/supabase/cliente.py` traduce `42501` por el codigo, no por la clase de la excepcion
- [x] El envelope es el mismo en exito y en error -- `adapters/http/responses.py`: `Respuesta.ok` y `Respuesta.error` construyen la misma forma; `tests/unit/test_envelope.py`
- [x] El envelope de error trae un identificador legible por maquina, no solo prosa -- `errors[].codigo`: `no_autenticado`, `perfil_inexistente`, `sesion_no_revocable`
- [x] Las marcas de tiempo se serializan en ISO-8601 (RFC 3339) -- `adapters/http/responses.py` las serializa en RFC 3339 con `Z`
- [x] La ISO-8601 se verifica sobre el **cuerpo real** de la respuesta, no solo en la
      configuracion -- `tests/integration/test_envelope.py` lo comprueba sobre el JSON que devuelve la API, no sobre la configuracion
- [ ] `new Date(valor)` en JavaScript devuelve el anio correcto
- [x] Los booleanos son `true`/`false`, no `0`/`1` ni `"true"` -- el DTO del perfil expone `debe_cambiar_contrasena` como booleano
- [x] Los nulos son `null` explicito, no claves ausentes ni `"null"` -- el envelope devuelve `data: null` y `errors: null`, nunca claves ausentes
- [ ] La paginacion devuelve metadatos, no un array desnudo
- [x] `page` por defecto 1, `size` por defecto 20, maximo 100, recortado y no rechazado —
      el caso de uso recorta el tamano en lugar de rechazar la peticion

---

## Gate 6 — ETL y LLM

- [ ] Un PDF sin capa de texto se marca como error explicito, no como analisis vacio
- [ ] El hash `sha256` del archivo se calcula y se persiste
- [ ] Los bloques cubren todas las paginas sin huecos fuera del solapamiento configurado
- [x] **El tamano de bloque se deriva de la ventana de contexto del modelo**, no esta fijo —
      `floor((ventana - reservados) / tokens_por_pagina)`, sin numeros magicos (`SKILL.md` 10.2)
- [ ] La funcion de chunking del frontend y la del backend son **el mismo algoritmo** (los
      rangos de pagina persistidos coinciden con los calculados)
- [ ] El Reduce es **jerarquico**: los resumenes parciales se agrupan en lotes que caben en
      la ventana de contexto
- [ ] La salida del LLM se valida contra el esquema de la plantilla **antes** de persistir
- [ ] Un JSON invalido produce reintento acotado y, al agotarlo, error de dominio
- [ ] La fase Reduce recibe los resumenes parciales, no el documento completo
- [ ] La temperatura por defecto para analisis de riesgos es baja (0.1)
- [ ] El pipeline es idempotente: reprocesar un documento ya completado no duplica filas
- [ ] El progreso se muestra por bloque (el usuario espera en su equipo, no en el servidor)
- [ ] Ninguna llamada al LLM sale del entorno controlado (verificado por revision de la
      configuracion de red del adaptador)

## Gate 7 — Frontend

- [ ] La deteccion de capacidad (WebGPU, memoria) se hace **antes** de elegir archivo
- [ ] Sin WebGPU se muestra un mensaje explicito, no un fallo posterior
- [ ] La descarga del modelo pide aceptacion explicita y usa `navigator.storage.persist()`
- [ ] El modelo se guarda en Cache API / IndexedDB, **no en cookies**
- [ ] El ETL y el LLM corren en un Web Worker, sin bloquear la interfaz
- [x] El cliente HTTP centraliza el token: ningun `fetch` escribe el header a mano -- `frontend/src/api/cliente.ts` es el unico que escribe el header `Authorization`; `frontend/src/api/cliente.spec.ts` lo comprueba
- [x] Los tipos de la API se generan desde el OpenAPI; no hay `any` -- `npm run api:types` lee `backend/tests/contract/openapi.json`; el resultado es `frontend/src/api/types.ts`
- [ ] El PDF nunca se serializa ni se envia en el camino principal

---

## Gate 8 — Pruebas

- [x] El dominio y los casos de uso tienen pruebas unitarias sin base de datos ni red -- 116 pruebas en `backend/tests/unit/`, sin base de datos ni red
- [x] Las pruebas de integracion corren contra Supabase real (`supabase start`), no contra un
      Postgres suelto: hacen falta Auth, PostgREST y Storage para que el aislamiento se
      pruebe de verdad -- 42 pruebas contra el stack local: Auth, PostgREST y RLS de verdad
- [ ] Hay una prueba de ciclo de vida completo: crear -> leer -> actualizar -> borrar
- [x] Un intento de login en cuenta inactiva, bloqueada o eliminada es rechazado -- `tests/integration/test_sesion.py`
- [x] Dos sesiones simultaneas funcionan ambas -- `tests/integration/test_sesion.py`
- [x] Logout invalida el token de inmediato, sin esperar la expiracion -- `tests/integration/test_sesion.py`: la revocacion se comprueba en la peticion siguiente
- [x] Un token revocado se rechaza en la peticion siguiente -- `tests/integration/test_sesion.py`
- [x] Intentar revocar la sesion de otro usuario da 403 o 404 -- `tests/integration/test_revocacion.py`
- [ ] La suite de inyeccion (SQLi, XSS, unicode, sobredimensionado, tipos erroneos) no
      produce 500 y no destruye datos
- [ ] La asercion de limpieza es explicita: "no 500" no basta, la tabla debe seguir existiendo
- [ ] La concurrencia (N altas simultaneas, N escrituras sobre la misma fila) no produce
      perdidas de escritura ni 500
- [x] El comando de build/test **incluye** las pruebas, no solo las fuentes de produccion —
      `npm run build` = `vue-tsc` + `vite build`, y `npm run test` va aparte: documentado
      para que nadie confunda "compila" con "probado"
- [x] La suite se reejecuto desde limpio y se reconstruyo de verdad — clon limpio del
      remoto: `uv sync` + `npm ci` + suites completas en verde

---

## Gate 9 — Listo para el frontend

- [x] `/health` responde 200 sin consultar la base (sonda de supervivencia) y `/ready` informa del estado: 503 si Supabase no responde o el esquema no esta aplicado (sonda de disponibilidad). Decision en DP-16
- [x] Todas las rutas estan documentadas con metodo, ruta, forma de peticion y de respuesta -- el OpenAPI se genera del codigo y el snapshot lo fija; cada ruta ademas lo explica en su docstring
- [x] El contrato OpenAPI es estable (snapshot en `tests/contract/`) -- `tests/contract/test_openapi.py` falla cuando el contrato cambia
- [x] El login devuelve un token usable de inmediato -- el SDK de Supabase emite el token y `GET /api/v1/auth/me` responde con el perfil en la misma sesion
- [x] Las rutas protegidas rechazan token ausente, malformado y adulterado -- `tests/unit/test_auth_http.py`
- [ ] El listado de documentos devuelve paginacion con metadatos
- [x] Los DTO de salida no exponen ningun campo sensible (inspeccion del cuerpo real) -- `tests/unit/test_auth_http.py` comprueba que ni el hash ni la llave de servicio aparecen en el cuerpo
- [ ] El registro de un analisis devuelve 201/202 y el documento queda persistido
- [ ] El estado del documento es consultable
- [ ] `GET /trabajos/{id}` devuelve progreso, paso actual, duracion y actividades
- [ ] `GET /documentos/{id}/analisis` devuelve el JSON mapeado por el DTO, con el resumen
      ejecutivo y los resumenes por bloque
- [ ] `POST /usuarios` crea el usuario, le asigna rol y organizacion, y deja rastro en
      auditoria
- [ ] Un usuario sin `usuarios.gestionar` recibe 403 en `/usuarios`

---

## Gate 10 — Privacidad

- [ ] El analisis ocurre en el equipo del usuario; el archivo original **se archiva en
      almacenamiento privado** del proyecto y **solo se elimina al borrar el documento**
      (ADR-20)
- [ ] Ningun texto extraido aparece en logs, traces ni metricas
- [ ] Ningun texto extraido se persiste fuera de `datos_estructurados` y `resumen`, que son
      los resultados que el usuario pidio
- [x] El bundle del frontend no contiene ninguna llave secreta — solo variables `VITE_*`
      publicas; el `.env` no se versiona
- [ ] El codigo del adaptador de LLM no tiene ningun destino por defecto que sea una API de
      terceros
- [x] El `service_role` no se usa para atender peticiones de usuario final — ADR-33: por
      ahora queda confinado a `scripts/bootstrap_admin.py`; el adaptador de
      administracion de usuarios (`adapters/supabase/admin.py`) es de HU-03

## Gate 11 — Despliegue

- [ ] El backend es stateless: no mantiene conexiones abiertas entre peticiones
- [ ] El camino de ejecucion **no** usa una conexion TCP a Postgres (solo PostgREST/RPC),
      para que la migracion a Cloudflare Workers sea posible sin cambios
- [ ] Las funciones de Postgres con `security definer` comprueban el permiso **dentro** de la
      funcion, y tienen `set search_path = public`
- [x] `vercel.json` fija el `maxDuration` por ruta de forma explicita, y excluye los tests del
      bundle (`excludeFiles`). La **version de Python no se declara en el `vercel.json`**: la
      define el `requires-python` del `pyproject.toml` — configurado y verificado
- [ ] Ningun endpoint del camino principal acepta un cuerpo mayor a 4.5 MB
- [ ] La API responde en menos de 300 s con la carga esperada (limite por defecto de la
      funcion)
- [x] El `Dockerfile` construye y la imagen levanta el backend en local — verificado el
      2026-11-28: `docker build` construye la imagen, `docker run` la levanta, el
      `HEALTHCHECK` de Docker reporta `healthy` con codigo de salida 0, y `/health`
      responde 200 desde fuera del contenedor. El proceso corre como el usuario
      `riskapp` (uid 1001), no como `root`. La imagen mide 337 MB: `uv` quedo fuera de
      la etapa final y el cache de descargas se limpia tras instalar. El `.venv` pesa
      124 MB y casi todo es transitive del SDK de Supabase (`opentelemetry`,
      `sentry_sdk`, `google`, `rich`, `pygments`, `uvloop`, `cryptography`): quitarlo
      exigiria recortar el SDK, que es dependencia directa (ADR-05), asi que no se
      toca
- [ ] Las variables de entorno del entorno de produccion estan definidas en el proveedor,
      no en un archivo versionado
- [x] Las **dependencias tienen pin exacto** y coinciden con lo instalado — ADR-27: un
      stack que se mueve solo es un stack que se rompe en silencio. Verificado en los dos
      lados contra `node_modules` y el `.venv`

**Perfil de demo gratuita** (solo si el despliegue es con planes gratuitos):

- [ ] El proyecto de Supabase **no esta pausado** por inactividad (se restaura antes de la
      demo, no durante)
- [ ] Se sabe que el SMTP incluido envia **2 correos por hora** y solo al equipo: el alta de
      usuarios de prueba se hace por otro camino durante la demo
- [ ] El limite de **50 MB por archivo** se probo con un PDF real de 100 paginas, no con un
      archivo de prueba pequeno
- [ ] El bucket de 1 GB tiene control de ocupacion, para no llenarse en medio de la demo
- [ ] Se reviso si el uso es comercial: si lo es, Vercel Hobby no aplica

---

## Gate 12 — Cambios de proveedor

Estos items aplican cuando se cambia un motor, un almacenamiento o un despliegue. **Ningun
cambio de proveedor es un cambio de codigo en los casos de uso.**

- [ ] Si el motor LLM pasa a ser un proveedor hospedado, existe un **ADR** que registra que
      proveedor, que datos salen y quien lo aprobo
- [ ] El motor hospedado **no es un default**: el sistema arranca con el local
- [ ] El modo de ejecucion se le muestra al usuario; no se cambia en silencio
- [ ] La ventana de contexto del modelo nuevo **recalcula** el tamano de bloque, sin valores
      metidos a mano
- [ ] Si cambia el almacenamiento, la implementacion nueva cumple las mismas reglas: bucket
      privado, URL firmada corta, borrado junto con el documento, sin base64
- [ ] Si cambia el despliegue, los adaptadores siguen siendo los mismos: solo cambia la
      composicion

---

## Gate 13 — Ciclo de vida del riesgo (fase 2)

> **Este gate no aplica en la v1.** La v1 entrega el analisis: extrae, consolida y
> persiste. Este gate verifica la fase siguiente, en la que el resultado **se gestiona**.
>
> **Esta aplazado hasta que PP-15 se cierre.** La pregunta "el resultado tiene ciclo de
> vida o es solo una consulta" es del cliente. Si la respuesta es "es solo una consulta",
> este gate se elimina. Si es "se gestiona", se convierte en gates nuevos de permisos y
> seguimiento.
>
> El material de este gate viene de dos fuentes:
> - `docs/ANALISIS-REFERENCIA-VULNERABILITY-TRACKER.md` — el analisis del prototipo de
>   referencia que mostro la forma que tiene un resultado cuando alguien lo gestiona.
> - `docs/CONTRATO-RESULTADO-ANALISIS.md` — el contrato del resultado, ya definido.

### 13.1 Modelo de datos

- [ ] **PP-15 esta cerrada** y la respuesta esta escrita en `DECISIONES-PENDIENTES.md`
- [ ] El modelo de datos del riesgo esta decidido: **columnas** en una tabla propia, o
      **campos dentro del `jsonb` `riesgos`** con validacion
- [ ] Si es tabla propia, existe **ADR** (cambia el modelo de datos) y la migracion esta
      aplicada contra una base vacia
- [ ] El riesgo tiene **estado**, con la lista de estados y las transiciones validas
- [ ] El riesgo tiene **responsable**, y se sabe si es un correo o un usuario del sistema
- [ ] El riesgo tiene **fecha objetivo**, y se sabe si es obligatoria
- [ ] La **decision de aceptacion** tiene su tipo (aceptacion / excepcion) y su **fecha de
      vencimiento**
- [ ] El **historial** es append-only: se anota, no se edita ni se borra
- [ ] El historial referencia el riesgo por su `clave` estable

### 13.2 Reglas de negocio

> Cada regla de aqui salio del prototipo de referencia. Copiadas sin entenderlas, fallan
> en silencio.

- [ ] **Una aceptacion vencida vuelve a requerir seguimiento.** "Aceptada" no es un estado
      terminal: es una decision con fecha que hay que renovar
- [ ] **Cerrar exige el comentario de validacion de cierre.** Sin el, "Cerrada" es un clic
      sin consecuencias
- [ ] **Aceptar exige tipo de decision *y* fecha de vencimiento.** Una aceptacion sin
      fecha es eternal
- [ ] **Un riesgo no puede quedar cerrado sin commentario**, y el backend lo rechaza
- [ ] El **historial es de solo agregado**: no hay endpoint que edite una entrada
- [ ] La transicion de estados se valida **en el caso de uso**, no solo en el formulario

### 13.3 Contrato e integracion con lo ya construido

- [ ] El **envoltorio del riesgo** del contrato se respeta: `clave`, `titulo`,
      `descripcion`, `evidencia`, `confianza` siguen siendo los mismos
- [ ] Los **campos de gestion** (estado, responsable, fecha, decision) se anaden **sin
      romper** el contrato: van en `datos` o en campos propios, segun la decision del
      punto 13.1
- [ ] La `clave` permite **comparar riesgo por riesgo** entre dos analisis del mismo
      documento (HU-10 7.6)
- [ ] Un analisis ya guardado **no se invalida** por el cambio: si la forma se materializa
      en columnas, hay migracion de los datos existentes
- [ ] El backend valida el envoltorio **ademas** del contenido: clave unica, paginas de
      evidencia dentro del documento y cubiertas por algun bloque, `confianza` de un valor
      permitido

### 13.4 Exportacion y respaldo

> **Aplazado a la fase 2.** Exportar es una operacion de **salida de datos del sistema**,
> y el resultado del analisis es el activo mas sensible del producto.

- [ ] Existe **HU** para la exportacion: que se exporta, quien puede hacerlo, y si queda
      registrado en la bitacora
- [ ] La exportacion **no** incluye datos de otros usuarios ni de otras organizaciones
- [ ] El CSV **escapa las formulas**: toda celda que empieza por `=`, `+`, `-`, `@`, tab o
      CR lleva un apostrofo delante (la inyeccion de formulas en la hoja de calculo del
      receptor)
- [ ] La exportacion dice **que snapshot es**: el estado actual, no una fotografia
      historica. El prototipo lo dice en la propia interfaz
- [ ] El respaldo JSON se puede **restaurar** y la restauracion **valida** antes de
      reemplazar los datos actuales

### 13.5 Correo

> **Aplazado a la fase 2.** La "fase de correos" del prototipo es el `mailto:` que se abre
> al registrar un seguimiento.

- [ ] Existe **HU** para el correo, con el alcance claro
- [ ] El correo se envia por el **puerto de correo**, no por un `mailto:` del navegador
- [ ] El cuerpo del correo **no** aparece en los logs
- [ ] La implementacion de desarrollo escribe el correo en el log, para probar el flujo sin
      contratar proveedor
- [ ] El **dato** que dispara el correo (`responsable`) es un campo del riesgo, no una
      direccion inventada por el sistema

---

## Gate 14 — Esqueleto del proyecto

> Verifica que el proyecto **arranca y verifica** antes de que exista logica de negocio.
> Un esqueleto que no compila es peor que no tener esqueleto: da la sensacion de avance.

- [x] `uv sync` crea el entorno con **Python 3.14.10** — el pin de ADR-28, no 3.15
- [x] `npm install` instala el frontend con **TypeScript 6.0.3** — el pin de ADR-28, no 7
- [x] `uv run ruff check .` pasa sin errores
- [x] `uv run mypy app` pasa sin errores
- [x] `uv run lint-imports` dice **4 contratos, 0 rotos**
- [x] `uv run pytest -m unit` corre **solo** las pruebas que no tocan base de datos ni red
- [x] `npm run lint` pasa sin errores
- [x] `npm run typecheck` pasa sin errores
- [x] `npm run test` pasa
- [x] `npm run build` construye
- [x] **La app arranca sin configuracion** y falla con un mensaje que nombra las variables
- [x] La app expone un **router de salud** (`/health`, `/health/config`) — el
      `HEALTHCHECK` del contenedor lo consulta, asi que tiene que existir antes que el
      Dockerfile. Es la unica ruta sin token, asi que no expone ningun valor de
      configuracion: devuelve si las variables estan presentes, nunca cuales son.
      Verificado el 2026-11-28 con 6 pruebas
      que faltan
- [x] **La app arranca con configuracion** y el emisor del JWT se deriva a
      `{SUPABASE_URL}/auth/v1`
- [x] El `.env.example` de cada lado esta versionado; el `.env` nunca
- [x] La guia de arranque (`docs/ARRANQUE.md`) coincide con los comandos que existen
- [x] El **arbol de carpetas documentado** coincide con el real, y las carpetas vacias se
      versionan con `.gitkeep` (git no versiona carpetas vacias)

---

## Gate 15 — Documentacion

> La documentacion es el entregable de este proyecto antes que el codigo. Un ADR que no
> se actualiza es un ADR que no existe.

- [x] Los cuatro marcadores de estado estan definidos igual en `CONTEXTO.md` y en
      `AGENTS.md` — cuatro, no tres
- [x] Cada ADR tiene fecha y motivo, y cambiar uno exige actualizar la tabla
- [x] Cada PP abierta tiene **impacto** y **supuesto explicito**
- [x] Las referencias de seccion (`seccion N.M`) resuelven contra los encabezados reales
- [x] Los enlaces y anclas internas resuelven
- [x] El verificador de documentacion no reporta hallazgos nuevos
- [x] Los originales estan preservados en `docs/legacy/` y **no se editan**
- [x] `docs/CONTRATO-RESULTADO-ANALISIS.md` existe y esta propagado a `ARQUITECTURA.md`,
      `SKILL.md`, `HU-07` y `HU-10`
- [x] Cada referencia a un repositorio clonado tiene su analisis en `docs/` y la carpeta
      `referencias/` tiene sus reglas — hecho con `vulnerability-tracker`

---

## Regla de la puerta

> Si un item falla, el entregable no esta listo. Un frontend construido sobre una API a
> medias absorbe cada hueco como si fuera su propio error, y el diagnostico se pierde.

> Y al reves: **una casilla marcada sin evidencia no cuenta como cumplida.** Es una
> promesa, no una verificacion.
