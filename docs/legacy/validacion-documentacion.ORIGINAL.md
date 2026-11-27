# Validacion previa a la inicializacion — Risk-app

> **Documento temporal de analisis (no modifica archivos existentes).**
> **Fecha de revision:** 2026-11-27
> **Alcance revisado:** `README.md`, `AGENTS.md`, `SKILL.md`, `CHECKLIST.md`, `CONTRIBUTING.md`, `.gitignore`, `docs/CONTEXTO.md`, `docs/ARQUITECTURA.md`, `docs/DECISIONES-PENDIENTES.md`, `docs/HU/INDICE.md` y `docs/HU/HU-01` a `HU-10`.

---

## 1. Resumen ejecutivo

La especificacion de **Risk-app** tiene una base sobresaliente en claridad arquitectonica, trazabilidad (RF, ADR, DP, HU y Gates) y enfoque de privacidad. Sin embargo, al cruzar los documentos entre si y contrastarlos con el comportamiento real del stack elegido, aparecen **contradicciones estructurales y huecos tecnicos que romperian la implementacion desde la primera migracion y los primeros endpoints** si se inicializa el codigo tal como esta hoy.

### Conteo de hallazgos

| Severidad | Cantidad | Resumen |
|---|---|---|
| **Bloqueante** | 9 | Colision en `POST /api/v1/documentos`, incompatibilidad de `Python 3.15.2` en Vercel Functions y `TypeScript 7.0.2` con `vue-tsc`, desajuste en revocacion inmediata de JWT y `JWT_ISSUER`, contradiccion `403` vs `404` frente a RLS, DDL desincronizado con las historias de usuario, migraciones duales Alembic vs Supabase CLI, y cron de 2 minutos en Vercel Hobby. |
| **Importante** | 11 | Requisitos sin historia de usuario (`RF-11`, `RF-25`), tablas/endpoints faltantes (auditoria, comparticion, cambio de clave inicial, borrado de configuracion, cancelacion), fallos de RLS en Storage y tablas, calculo erroneo de bloques (`34` vs `~50`) y de progreso, limites reales de tokens por pagina, offline sin almacenamiento definido y CORS en Storage. |
| **Menor / Mejora** | 8 | Nomenclatura mixta espanol/ingles en DDL, referencias rotas en indices y anclas, duplicados en catalogos, spanglish (`reanalyze`) y herramientas de inicializacion faltantes (`.env.example`, OpenAPI codegen, `import-linter`, `Vitest`, golden tests de chunking). |

---

## 2. Incongruencias bloqueantes (corregir antes de escribir codigo)

### B-01. Dos flujos incompatibles compiten por `POST /api/v1/documentos` y `POST /api/v1/trabajos`
- **Donde:**
  - Flujo A: `docs/HU/HU-06-carga-y-archivo.md` (§7.2, lineas 170-197), `docs/ARQUITECTURA.md` (§5.7, lineas 756-763) y `SKILL.md` (§9.4, lineas 1205-1213).
  - Flujo B: `docs/ARQUITECTURA.md` (§6.7, lineas 995-999 y 1024-1028; §7, lineas 1123 y 1133), `SKILL.md` (§1.4-1.5, lineas 153-218; §6.1, lineas 883-937; §10.4, lineas 1536-1540) y `docs/HU/HU-07-analisis-documento.md` (§7.5, lineas 207-218).
- **Que esta mal:**
  - En el **Flujo A (HU-06)**, `POST /api/v1/documentos` se llama **al inicio** (antes de subir el PDF y antes de analizar): crea el registro en `documentos` (`estado = 'en_proceso'`), crea el `trabajo` y devuelve `201` con `{ documento_id, trabajo_id, url_subida_firmada }`.
  - En el **Flujo B (HU-07 / SKILL / ARQUITECTURA §6.7)**, primero se llama `POST /api/v1/trabajos` (`en_cola`), luego el navegador analiza, y **al final** llama a **`POST /api/v1/documentos`** (`201` o `202`), ejecutando la funcion Postgres `registrar_analisis` que hace `INSERT INTO public.documentos ... VALUES (..., 'completado')`.
  - Si coexisten ambos, un documento creado al inicio por HU-06 ya existe en `documentos` (y ademas `HU-08` §7.1 linea 184 asume que `POST /trabajos` recibe un `documento_id` existente). Llamar `POST /documentos` al final para insertar otro registro fallaria por hash duplicado o duplicaria el documento. Ademas, `SKILL.md` linea 153 usa `202 Accepted` con `CrearAnalisisRequest`, mientras `HU-06` y `HU-07` esperan `201 Created`.
- **Que cambiar:** Separar de forma unica el ciclo de vida:
  1. `POST /api/v1/documentos`: registra el documento (`en_proceso`), valida metadatos y firma la URL de subida (`201`).
  2. `POST /api/v1/trabajos`: crea el trabajo asociado a `documento_id` (`201`) o lo crea junto con el paso 1 si no habra paso separado.
  3. `POST /api/v1/documentos/{id}/analisis` (o `PUT`): recibe bloques, resumenes, riesgos y `trabajo_id`; actualiza el documento existente a `completado`, inserta `bloques` + `analisis_documentos` y cierra el `trabajo` en una sola RPC transaccional (`201`/`200`).

---

### B-02. Versiones fijadas incompatibles con las herramientas elegidas
- **Donde:** `docs/ARQUITECTURA.md` (§1.0, lineas 24-39), `AGENTS.md` (§6) y `README.md` (§3, linea 73).
- **Que esta mal:**
  1. **Python `3.15.2` frente a Vercel Functions:** Los entornos de build y funciones de Vercel soportan Python **3.12, 3.13 y 3.14** (Python 3.15 figura unicamente como imagen para Vercel Sandbox, no para Vercel Functions). Fijar `requires-python = "==3.15.2"` puede bloquear o romper el despliegue en nivel 2.
  2. **TypeScript `7.0.2` frente a Vue `3.5.46` (`vue-tsc`):** TypeScript `7.0.x` (port nativo en Go, `tsgo`) elimino la API legacy en JavaScript del compilador que requiere `vue-tsc` para verificar tipos en archivos `.vue` desde linea de comandos. Para Vue 3.5 con `vue-tsc` se requiere mantener **TypeScript 5.9 / 6.x** (`@typescript/typescript6`) o usar **TypeScript 7.1+** (que introduce *content mappers* para SFC).
  3. **PostgreSQL `16` vs `17`:** `README.md` linea 73 indica `PostgreSQL 16 (Supabase)`, mientras `ARQUITECTURA.md` linea 36 y `AGENTS.md` §6 fijan `PostgreSQL 17`.
- **Que agregar/cambiar:** Validar en un ADR antes de crear `pyproject.toml` y `package.json`: evaluar **Python 3.14.x** (o verificar runtime exacto en Vercel antes del primer deploy), fijar **TypeScript 5.9 / 6.x** (o `7.1+` si ya soporta `vue-tsc` en el proyecto) y unificar PostgreSQL **17** en `README.md`.

---

### B-03. Revocacion inmediata de JWT y `JWT_ISSUER` rotos en el diseno de autenticacion
- **Donde:** `docs/HU/HU-01-acceso-y-sesion.md` (§4 linea 94; §10 CA-11 lineas 316-321), `CHECKLIST.md` (Gate 8, lineas 205-206), `docs/ARQUITECTURA.md` (§7 linea 1115; §8 linea 1182) y `SKILL.md` (§5.2-5.3, lineas 700-730).
- **Que esta mal:**
  1. **Logout vs JWT stateless:** `HU-01` CA-11 y `CHECKLIST.md` Gate 8 exigen que, tras cerrar sesion, *"el token anterior no vuelve a servir en la peticion siguiente, de inmediato, sin esperar la expiracion"*. En **Supabase Auth**, `signOut()` revoca el *refresh token*, pero el *access token* (JWT) sigue siendo criptograficamente valido hasta su `exp` (por defecto 1 hora) si el backend solo valida firma, `exp`, `aud` e `iss` localmente (`SKILL.md` §5.2).
  2. **`JWT_ISSUER = "risk-app"` en `HU-01` linea 94:** El emisor real (`iss`) de un JWT emitido por Supabase Auth es `<SUPABASE_URL>/auth/v1`. Si el middleware exige `"risk-app"`, rechazara todos los tokens reales con `401`.
  3. **`POST /api/v1/auth/login` listado en `ARQUITECTURA.md` linea 1115:** Contradice `HU-01` CA-03 (linea 266: *"no existe ningun endpoint que emita un token de sesion propio"*) y `AGENTS.md` §6.1.
  4. **Firma de JWT en proyectos nuevos de Supabase:** Los proyectos recientes de Supabase usan claves asimetricas (JWKS en `/auth/v1/.well-known/jwks.json`, `ES256`/`RS256`) ademas o en lugar de `HS256` con `SUPABASE_JWT_SECRET`.
- **Que cambiar:**
  - Eliminar `POST /api/v1/auth/login` de `ARQUITECTURA.md` §7 y `SKILL.md` §5.2 (el login va directo al SDK de Supabase en frontend).
  - Corregir `JWT_ISSUER` a `${SUPABASE_URL}/auth/v1` y prever validacion via JWKS ademas de `SUPABASE_JWT_SECRET`.
  - Para cumplir CA-11/Gate 8 sobre revocacion inmediata: o bien el backend consulta/verifica la sesion en Supabase Auth (`auth.getUser(jwt)` o verificacion de `session_id` revocado), o se documenta un mecanismo de revocacion de `session_id` (al llamar `POST /auth/logout` se guarda el `session_id` revocado hasta su `exp`, o se reduce el TTL del access token en Supabase). Sin esto, CA-11 fallara en pruebas reales.

---

### B-04. Contradiccion `403` vs `404` y su incompatibilidad tecnica con RLS
- **Donde:** `SKILL.md` (§9.1, lineas 1054-1056), `docs/ARQUITECTURA.md` (§5.5, lineas 600-602), `CHECKLIST.md` (Gate 3.1, linea 75) y `docs/HU/HU-02-roles-y-permisos.md` (CA-04, lineas 329-334) **VS** `docs/HU/HU-09-consulta-de-resultados.md` (§7.3 linea 194, SP-02, CE-02, CA-02 lineas 284-289) y `docs/HU/HU-10-reanalisis-con-plantilla-vigente.md` (SP-10 linea 248).
- **Que esta mal:**
  - La mitad de los documentos exige responder **`403`** para un recurso existente sin permiso (*"oculta la diferencia entre no existe y no es tuyo"*), mientras `HU-09` y `HU-10` exigen **`404`** (*"un documento invisible no se distingue de uno que no existe"*).
  - Ademas, si el backend reenvia el JWT del usuario por PostgREST y **RLS filtra la fila** (por ejemplo, de otra organizacion), Postgres devuelve **0 filas (`None`)**. El caso de uso **no puede saber** si el registro no existe o si fue ocultado por RLS sin usar `service_role` (lo cual esta prohibido en peticiones de usuario final).
- **Que cambiar:** Unificar la regla en un ADR:
  - Recursos de **otra organizacion** (filtrados por RLS): siempre **`404`** (evita fuga de existencia entre organizaciones).
  - Recursos de la **misma organizacion** sobre los que falta permiso (por ejemplo `analisis.ver_todos` o `archivos.descargar`): definir explicitamente si RLS filtra por organizacion y el caso de uso devuelve **`403`**, o si ambos devuelven `404`. Actualizar `HU-02`, `HU-09`, `HU-10`, `SKILL.md`, `ARQUITECTURA.md` y `CHECKLIST.md`.

---

### B-05. El DDL de `ARQUITECTURA.md` §5.1 esta desincronizado con las HUs y rompe las operaciones basicas
- **Donde:** `docs/ARQUITECTURA.md` (§5.1, lineas 314-486) frente a `HU-02`, `HU-03`, `HU-06`, `HU-08`, `HU-10` y `SKILL.md`.
- **Faltantes criticos detectados en las tablas actuales:**
  1. **`perfiles` no tiene columna `activo` (o `desactivado_en`):** `HU-03` (§7.1, §7.5, CA-11) y `HU-02` (CA-05) dependen de desactivar/reactivar usuarios y leer ese estado en el resolver de permisos sin usar `service_role` en cada request.
  2. **`documentos` no tiene `tamano_bytes`, `tipo_mime` ni `archivado_en`:** `HU-06` (§6, lineas 123-127) los agrega, pero no estan en `ARQUITECTURA.md` §5.1.
  3. **`roles` no tiene `is_system` ni `created_at`; `permisos` no tiene `nombre` ni `created_at`:** `HU-02` (§6, lineas 158 y 166) los define, pero faltan en `ARQUITECTURA.md` §5.1.
  4. **`trabajos` no tiene `ultimo_latido_en` y `trabajo_actividades` no tiene `id_reporte` (clave de idempotencia):** Sin `ultimo_latido_en`, la tarea de mantenimiento de `ADR-24` / `HU-08` no puede detectar abandono tras 2 minutos (usar `created_at` fallaria porque los reportes posteriores no lo actualizan). Sin `id_reporte` (`unique (trabajo_id, id_reporte)`), `HU-08` CE-06 / CA-08 sobre reintentos de red sin duplicar filas no es implementable.
  5. **`analisis_documentos` no tiene columna `modelo` (ni `total_bloques`):** `analisis_historial` si tiene `modelo` (`ARQUITECTURA.md` linea 420) y `HU-10` EC-05 exige conservar el modelo de cada analisis al moverlo al historial.
  6. **Faltan claves foraneas de integridad:** `perfiles.rol` y `organizaciones_miembros.rol` no tienen `REFERENCES roles(clave)`.
  7. **`eliminado_en` falta en todas las tablas excepto `documentos`:** `README.md` linea 173 y `SKILL.md` §4.1/§16 exigen `eliminado_en` en todas las tablas, pero en el SQL solo `documentos` lo tiene.
  8. **Falta tabla `auditoria` (`bitacora_auditoria`):** `HU-01`, `HU-02` (permiso `auditoria.ver`), `HU-03` CA-13, `HU-04` CA-10 y `CHECKLIST.md` Gate 3.1/3.3/3.4 exigen persistir y consultar eventos de auditoria, pero la tabla no existe en el modelo de datos ni tiene endpoint en `ARQUITECTURA.md` §7.
  9. **Falta soporte en BD para `documentos.compartir`:** `DP-04`, `HU-02` y `ARQUITECTURA.md` §5.5 indican que el analista ve *"los propios y los compartidos"*, pero no hay tabla `documentos_compartidos` ni columna equivalente.
  10. **Falta indice `UNIQUE` parcial en `documentos(usuario_id, hash_sha256) WHERE eliminado_en IS NULL`** (si la politica es `409` por duplicado como indica `HU-06` CE-08 y `SKILL.md` §1.5).
  11. **La RPC `registrar_analisis` (`SKILL.md` §6.1, lineas 883-937)** referencia funciones no definidas (`usuario_tiene_acceso_al_documento`, `organizacion_del_usuario`), omite `p_plantilla_id`, `p_plantilla_version` y `p_modelo`, y no contempla el caso de reanalisis (`HU-10`: mover `analisis_documentos` a `analisis_historial` en la misma transaccion).

---

### B-06. Conflicto de herramientas de migracion: Alembic vs Supabase CLI
- **Donde:** `AGENTS.md` §5, `CHECKLIST.md` Gate 1 (lineas 26-28), `docs/ARQUITECTURA.md` §1.2/§5/§9.2 y `SKILL.md` §3.2-3.3 (lineas 578-606).
- **Que esta mal:** `SKILL.md` §3.2 lista tanto `supabase db reset` / `supabase migration new` como `uv run alembic upgrade head`. Usar ambos a la vez sobre la misma base local provoca conflictos: `supabase db reset` ejecuta `supabase/migrations/*.sql` y borra la tabla `alembic_version`, mientras que Alembic no gestiona de forma nativa el despliegue hacia Supabase Cloud (`supabase db push`) ni suele coexistir limpio con `supabase/migrations/`.
- **Que cambiar:** Elegir **una sola fuente de verdad para migraciones**:
  - **Opcion recomendada con Supabase:** `supabase/migrations/*.sql` (SQL puro ejecutado con `supabase db reset` en local y `supabase db push` en CI/prod), manteniendo un script de validacion contra base vacia.
  - **Alternativa:** Alembic puro contra `DATABASE_URL` (incluso para `storage.buckets` y `storage.objects`), eliminando `supabase migration new` del flujo. Registrar la eleccion en un ADR y actualizar `AGENTS.md`, `SKILL.md` y `CHECKLIST.md`.

---

### B-07. Contradiccion sobre el requisito critico de privacidad (archivo local vs Storage)
- **Donde:** `SKILL.md` (§14, linea 2040), `CHECKLIST.md` (Gate 10, linea 240), `docs/CONTEXTO.md` (§4, linea 139) frente a `ADR-20`, `AGENTS.md` §2.1 y `HU-06`.
- **Que esta mal:**
  - `SKILL.md` linea 2040 dice: **`"El PDF se borra al terminar el pipeline"`** (regla obsoleta previa a `ADR-20` que contradice `AGENTS.md` §2.1 y rompe `HU-10`).
  - `CHECKLIST.md` linea 240 y `CONTEXTO.md` linea 139 dicen: *"El PDF original no sale del equipo del usuario en el camino principal"*, cuando `ADR-20` y `HU-06` lo suben directo a Supabase Storage privado para archivarlo.
- **Que cambiar:** Actualizar esas tres lineas para que coincidan con `ADR-20` y `CONTEXTO.md` linea 71: *"El analisis ocurre en el equipo del usuario; el archivo original se archiva unicamente en almacenamiento privado controlado del proyecto y solo se elimina al borrar el documento."*

---

### B-08. Ejemplos de `SKILL.md` usan SQLAlchemy TCP, contradiciendo ADR-04 (PostgREST HTTP)
- **Donde:** `SKILL.md` (§1.1 linea 83, §1.6 lineas 274-289, §6 lineas 863-870) y `CHECKLIST.md` (§Gate 8, linea 201).
- **Que esta mal:** Los ejemplos normativos de repositorio y Unit of Work en `SKILL.md` usan `sqlalchemy.ext.asyncio.AsyncSession` y `select(...)`, mientras `ADR-04` prohibe conexiones TCP/SQLAlchemy en el camino de ejecucion (solo cliente HTTP PostgREST/RPC). Ademas `CHECKLIST.md` linea 201 pide pruebas *"contra Postgres real en Docker"* en vez de `supabase start` (Postgres + Auth + PostgREST + Storage).
- **Que cambiar:** Reescribir los ejemplos de `SKILL.md` §1.6 y §6 usando el cliente HTTP de Supabase / PostgREST + RPC (y explicar que `UnitOfWork` se reserva para operaciones atomicas via RPC o futuras implementaciones TCP), y alinear `CHECKLIST.md` linea 201 con `supabase start`.

---

### B-09. Cron de 2 minutos en Vercel Hobby es inviable en el plan gratuito
- **Donde:** `docs/ARQUITECTURA.md` (§9.4 linea 1297, §9.5), `ADR-21`, `ADR-24` y `docs/HU/HU-08-seguimiento-del-trabajo.md` (§4 linea 86: `timeout_latido_ms = 120000`).
- **Que esta mal:** `HU-08` espera que una tarea de mantenimiento (`cron` de Vercel) marque como `interrumpido` los trabajos sin latido a los 2 minutos. En **Vercel Hobby** (plan gratuito elegido en `ADR-21`), los Cron Jobs estan limitados a **1 ejecucion por dia** (no por minuto). En la demo gratuita, cualquier analisis abandonado quedaria atascado en `en_proceso` hasta 24 horas.
- **Que cambiar:** Complementar o reemplazar el cron frecuente con **expiracion perezosa en lectura/apertura** (en `GET /documentos/{id}`, `GET /trabajos/{id}` y `POST /trabajos` / `POST /documentos`: si existe un trabajo en `en_proceso` con `now() - ultimo_latido_en > 120 s`, marcarlo `interrumpido` atomicamente antes de responder) o usar `pg_cron` si esta disponible, dejando documentada esta limitacion en `ARQUITECTURA.md` §9.5.

---

## 3. Huecos funcionales, de seguridad y tecnicos (importantes)

### I-01. Requisitos funcionales sin historia de usuario (`RF-11` y `RF-25`) y estados obsoletos en `CONTEXTO.md`
- **`RF-11` (Consultar y editar plantillas de extraccion):** No tiene HU ni endpoints de edicion/versionamiento (`PUT/PATCH /api/v1/plantillas/{id}`, activacion de nueva version). Ademas `HU-04` linea 59 remite a `HU-09`, donde tampoco esta.
- **`RF-25` (Eliminar documento y su archivo en Storage):** No tiene HU. `HU-06` remite a `HU-09` y `HU-09` §2 lo deja fuera de alcance (*"gate de borrado"*). Queda sin definir el manejo transaccional entre soft delete en `documentos` (`eliminado_en`) y hard delete en Supabase Storage: si se borra el PDF del bucket pero el registro queda con `eliminado_en`, hay que garantizar que nunca pueda "restaurarse" un documento sin archivo, y definir el rollback si falla la llamada HTTP a Storage.
- **`CONTEXTO.md` §7.1 (lineas 338 y 342):** `RF-10` sigue marcado `[ABIERTO] DP-04` y `RF-14` sigue `[ABIERTO] DP-11`, aunque ambas DP ya estan cerradas en `DECISIONES-PENDIENTES.md`.

### I-02. Huecos en politicas RLS de tablas y de `storage.objects`
- **Aislamiento por `organizaciones_miembros` vs `perfiles.organizacion_id`:** Las politicas RLS de ejemplo (`ARQUITECTURA.md` lineas 499-504 y 722-745) consultan `perfiles.organizacion_id`. Si un usuario esta en dos organizaciones (`organizaciones_miembros`, `PP-01`), o si un `analista` no tiene `analisis.ver_todos`, consultar directamente PostgREST con su JWT le permitiria ver documentos y descargar archivos de otros analistas de su organizacion, burlando la matriz de permisos de la API.
- **Falta politica `DELETE` en `storage.objects`:** `CHECKLIST.md` Gate 3.4 linea 122 exige politicas para `insert`, `select` y `delete`, pero `ARQUITECTURA.md` §5.7 solo muestra `insert` y `select`.
- **`archivos_insertar` demasiado permisiva:** La politica `archivos_insertar` (`ARQUITECTURA.md` linea 726) solo verifica el primer segmento (`organizacion_id`), no el segundo (`usuario_id = auth.uid()::text`). Un usuario podria escribir en la carpeta de otro usuario dentro de su organizacion.
- **Descarga como `attachment`:** `HU-06` CE-07 exige `Content-Disposition: attachment` para PDFs con JS embebido. El adaptador `supabase_storage.py` debe usar la opcion `download=True` al crear la URL firmada de descarga (de lo contrario Supabase sirve `inline`).

### I-03. Endpoints faltantes en `ARQUITECTURA.md` §7 frente a las HUs
Faltan los siguientes endpoints necesarios segun las historias de usuario y checklists:
1. **`POST /api/v1/auth/cambiar-contrasena`** (o confirmacion segura de cambio de clave): `HU-03` §7.2 paso 5 indica que el usuario cambia su clave temporal y se limpia `perfiles.debe_cambiar_contrasena`. Si el frontend cambia la clave directo con Supabase Auth, falta definir como el backend verifica y limpia esa bandera sin permitir que un usuario la desactive arbitrariamente por PostgREST.
2. **`POST /api/v1/usuarios/{id}/reenviar-credencial`:** Mencionado en `HU-03` SP-08 y EC-06 (genera nueva clave temporal, marca `debe_cambiar_contrasena = true` y reenvia correo).
3. **`DELETE /api/v1/configuracion/motor`:** Exigido por `HU-04` EC-06 y CA-04 para borrar la configuracion personal y volver a la de organizacion.
4. **`POST /api/v1/trabajos/{id}/cancelar`:** Necesario para el estado `cancelado` definido en `trabajos` (`ARQUITECTURA.md` linea 464 y `HU-08` linea 48).
5. **`GET /api/v1/auditoria`:** Necesario para el permiso `auditoria.ver` (`ARQUITECTURA.md` §5.5 y `HU-02` §4).
6. **`PUT/PATCH /api/v1/plantillas/{id}` y `GET /api/v1/documentos/{id}/historial`:** Necesarios para gestionar versiones de plantillas (`RF-11`) y consultar analisis historicos (`HU-10` CA-02: *"el analisis anterior sigue consultable"*).
7. **Ajuste en `GET /api/v1/auth/me`:** Devolver `permisos: list[str]` efectivos junto con el perfil, para que el frontend Vue oculte botones/rutas sin necesidad de exponer `GET /api/v1/roles` a usuarios no administradores (`HU-02` §7.3 restringe `/roles` a `organizacion.gestionar`).

### I-04. Flujo de alta de usuarios (`HU-03`): conflicto entre `email_confirm = false` y contraseña temporal
- **Donde:** `docs/HU/HU-03-administracion-usuarios.md` (§5 supuesto 4, §7.1-7.2) y `docs/ARQUITECTURA.md` (§5.6).
- **Problema:** En Supabase Auth, un usuario creado con `email_confirm = false` **no puede iniciar sesion con `signInWithPassword`** hasta que confirme su correo (`Email not confirmed`). En `HU-03` falta especificar:
  - Como se genera el `enlace_confirmacion` (`admin.generate_link` en Supabase requiere cuidado porque un enlace tipo `signup`/`magiclink` suele autenticar al usuario y confirmar la cuenta en un paso, haciendo innecesaria o confusa la clave temporal).
  - El camino triste cuando el usuario intenta entrar con la clave temporal **antes** de hacer clic en el enlace de confirmacion.
  - De donde sale el campo `correo` al listar usuarios en `GET /api/v1/usuarios` (`HU-03` §7.3), ya que `perfiles` no tiene columna `correo` y los endpoints de lectura no deben consultar `auth.users` sin `service_role`.

### I-05. Calculo incorrecto de bloques (`34` vs `~50`) y contradiccion en el calculo de progreso
- **Donde:** `README.md` (linea 146), `docs/CONTEXTO.md` (lineas 153, 176, 301), `docs/ARQUITECTURA.md` (lineas 834, 841, 851-852), `SKILL.md` (lineas 1307-1321, 1341) y `docs/HU/HU-08-seguimiento-del-trabajo.md` (lineas 99-110, 254-256).
- **Detalle:**
  1. `SKILL.md` linea 1314 dice `4 paginas` (`floor((4096-1200)/700) = 4`), mientras el resto dice `3 paginas`.
  2. La funcion `calcular_paginas_por_bloque` en `SKILL.md` **no recibe `overlap_paginas`**, aunque `CONTEXTO.md` y `ARQUITECTURA.md` dicen que `overlap_paginas` se resta antes de dividir.
  3. Con `tamano = 3` y `overlap = 1`, `paso = 3 - 1 = 2`. Un documento de 100 paginas produce **50 bloques** (`ceil((100 - 1) / 2)`), **no ~34 bloques**. El Reduce de 50 resumenes de ~200 tokens son ~10.000 tokens (al menos 3 lotes en nivel 1).
  4. En `HU-08`, la formula de linea 99 (`floor(bloques_completados * 100 / total_bloques)`) contradice la tabla por etapas de lineas 104-110 (`5%` extraccion + `85%` map + `8%` reduce + `2%` persistencia). Hay que unificar la formula en `HU-08` usando los pesos por etapa.

### I-06. Riesgo real en LLM local: paginas densas vs ventana de 4096 tokens y `response_format` en WebLLM
- **Donde:** `SKILL.md` (§10.2-10.3, lineas 1300-1425) y `docs/HU/HU-07-analisis-documento.md` (§4, §7).
- **Problema:**
  1. Estimar un bloque solo por **numero de paginas** (`paginas_por_bloque`) falla cuando un PDF tiene paginas de tablas densas o anexos financieros (~2.000 a 3.000 tokens en una sola pagina): 3 paginas superarian 4.096 tokens y el modelo fallaria o truncaria silenciosamente. **Mejora requerida:** agregar un tope de seguridad por longitud de texto/tokens estimados (`chars / 3.5` en espanol) que subdivida automaticamente un bloque si excede `ventana_contexto - tokens_reservados`.
  2. En `SKILL.md` linea 1411 aparece `response_format: { type: 'json_object', schema: esquema }` pasando `esquema` como `object`. En `@mlc-ai/web-llm`, `schema` espera un **string JSON (`JSON.stringify(...)`)** y el motor XGrammar soporta un subconjunto acotado de JSON Schema (requiere definir en `plantillas_extraccion` que construcciones de JSON Schema se permiten, por ejemplo `additionalProperties: false`).
  3. En `HU-04` §4 y `CONTEXTO.md` §5.4 hay que alinear el catalogo de modelos (por ejemplo, `CONTEXTO.md` lista 10 modelos y `HU-04` solo 6) y advertir que `gemma-4-E2B-it-q4f16_1-MLC` requiere `shader-f16` (debe comprobarse en `HU-05` antes de sugerirlo).

### I-07. Validacion de magic bytes imposible en el backend sin el archivo (`CHECKLIST.md` Gate 2 / 3.4)
- **Donde:** `CHECKLIST.md` (linea 51 y linea 121) y `docs/HU/HU-06-carga-y-archivo.md` (§2, §7.2).
- **Problema:** La API recibe un JSON pequeno (`nombre_archivo, hash_sha256, total_paginas, tamano_bytes`), nunca el PDF (el PDF sube directo al bucket). El backend puede validar `tamano_bytes` (y validar despues contra Storage), pero **no puede inspeccionar los magic bytes reales en el servidor** antes de firmar la URL de subida. `SKILL.md` §12.11 prohibe declarar defensas que el codigo no ejecuta.
- **Que cambiar:** Aclarar que la validacion de magic bytes (`%PDF-`) ocurre en el **navegador** antes de subir (o opcionalmente enviando los primeros bytes de cabecera si se desea doble verificacion) y en la politica `allowed_mime_types` del bucket en Storage, y ajustar `CHECKLIST.md` para reflejarlo con honestidad. Ademas, en `POST /api/v1/documentos/{id}/archivo`, el backend debe consultar los metadatos del objeto en Supabase Storage (existencia, tamano y MIME real guardado) antes de confirmar `ruta_archivo`.

### I-08. Cola offline de resultados (`HU-05` CA-11 y `HU-07` SP-09) sin almacenamiento ni renovacion de sesion definidos
- **Donde:** `docs/HU/HU-05-compatibilidad-y-descarga-modelo.md` (EC-07 y CA-11, lineas 197 y 280-285) y `docs/HU/HU-07-analisis-documento.md` (SP-09 y CA-12).
- **Problema:** Se promete que un analisis completado sin red *"queda en cola para enviarse al servidor cuando vuelva la conexion"*. Sin embargo, no esta definido donde se persiste esa cola (debe ser **IndexedDB**, no `localStorage`, por el tamano de 50-100 bloques + resumenes), ni como se evita que `trabajo` quede marcado `interrumpido` mientras estuvo offline, ni que ocurre si el JWT expiro durante el corte de red.

### I-09. Falta configuracion de CORS en Supabase Storage y empaquetado local del worker de `pdf.js`
- **Donde:** `docs/ARQUITECTURA.md` (§1.3, §5.7) y `docs/HU/HU-06-carga-y-archivo.md`.
- **Problema:**
  1. Subir archivos directo del navegador (Vercel origin) a Supabase Storage mediante `PUT` firmado requiere configurar **CORS** en Supabase Storage / proyecto para permitir `PUT`/`GET` desde los origenes del frontend; si falta, fallara en produccion.
  2. `pdf.js` usa su propio Web Worker (`pdf.worker.mjs`). Si se carga desde un CDN externo en vez de empaquetarlo localmente con Vite, se rompe el modo offline (`HU-05` CA-11) y se introduce una dependencia externa de red innecesaria.

### I-10. Riesgo de superar 4.5 MB en `POST` de resultados para documentos largos (~200-250 paginas)
- **Donde:** `docs/ARQUITECTURA.md` (§9.3) y `docs/HU/HU-07-analisis-documento.md` (EC-06, CE-04).
- **Problema:** Un documento de 250 paginas con bloques de 3 paginas y solapamiento de 1 genera **125 bloques**. Si `analisis_documentos.resumenes` duplica los datos de `bloques` dentro del mismo payload JSON enviado al backend, se envia el doble de tamano y podria acercarse al tope de 4.5 MB de Vercel Functions. El cliente no deberia duplicar el arreglo completo de `datos_estructurados` dos veces en el cuerpo HTTP; el RPC de Postgres puede construir `analisis_documentos.resumenes` o recibir una sola estructura normalizada.

### I-11. Bootstrap del primer administrador y validacion de `POST /api/v1/documentos/{id}/archivo`
- **Donde:** `docs/HU/HU-03-administracion-usuarios.md` (§5 supuesto 1) y `docs/ARQUITECTURA.md` (§5.6).
- **Problema:** Insertar el primer usuario `admin` directamente en `auth.users` con SQL en una migracion es fragil en Supabase (requiere filas coordinadas en `auth.users` y `auth.identities` con formato interno de GoTrue). Es mejor definir un comando/script de bootstrap idempotente que cree el primer administrador usando la Admin API (`service_role`) tras aplicar las migraciones.

---

## 4. Inconsistencias menores, errores tipograficos y nomenclatura

1. **Idioma mixto en columnas SQL vs `SKILL.md` / `AGENTS.md`:**
   - `ARQUITECTURA.md` §5.1 usa `created_at` y `updated_at` (ingles) junto a `eliminado_en` (espanol), mientras `SKILL.md` (§1.7, §4.1, §4.4, §16) usa `creado_en` y `actualizado_en`. Unificar a un solo idioma antes de crear la primera migracion.
2. **Carpetas y nombres de clases divergentes en `SKILL.md`:**
   - `SKILL.md` usa `adapters/db/` (lineas 100, 275) frente a `adapters/supabase/` en `ARQUITECTURA.md` linea 236 y `SKILL.md` linea 169.
   - `SKILL.md` §1.2 menciona `application/ports/` (no existe en `ARQUITECTURA.md` §3).
   - `HU-02` linea 235 usa `DocumentoDTO` frente a `DocumentoResource` en `SKILL.md` §1.8.
3. **Catalogo de permisos duplicado e incompleto en `ARQUITECTURA.md` §5.5:**
   - `documentos.compartir` esta repetido en las lineas 558 y 561.
   - `plantillas.ver` y `configuracion.ver` aparecen en el catalogo (lineas 563-564) pero faltan en la tabla de la matriz de roles (lineas 575-588); en `HU-02` §4 si estan.
4. **Numeracion y referencias cruzadas rotas:**
   - `ARQUITECTURA.md` §6 salta de `6.7` (linea 946) a `6.9` (linea 1034) y luego `6.8` (linea 1046).
   - `HU/INDICE.md` linea 96 cita *"gate 8 (listo para el frontend)"*, pero en `CHECKLIST.md` ese es el **Gate 9** (el 8 es Pruebas).
   - `CONTEXTO.md` linea 91 enlaza a `#95-perfil-de-despliegue-la-demo-gratuita` para explicar adaptadores de almacenamiento S3/SFTP.
   - `README.md` linea 237 escribe `[PENDIENTE]` mientras `AGENTS.md` §1.2 pide `[ABIERTO]`.
   - `AGENTS.md` §2.4-2.5 exige espanol (CO) sin abreviaturas impropias, pero en `HU-03`, `HU-05`, `HU-08`, `HU-10`, `SKILL.md` y `CHECKLIST.md` hay palabras en spanglish/typos (`reanalyze`, `analysed`, `no setrust`, `unaROW`, `Above del limite`, `Depends del uso`, `tipo MIM`, `reenvuelveste`, `desplega`, `filra`, `reanalisises`, `analisises`).
5. **`.gitignore` incompleto para el stack real:**
   - Faltan entradas de Supabase local (`supabase/.branches/`, `supabase/.temp/`), Vercel (`.vercel/`), artefactos de cobertura (`coverage.xml`) y temporales (`*.tmp`, `*.tmp.md`, `*.mdtmp`).

---

## 5. Novedades y mejoras tecnicas recomendadas antes de inicializar

1. **Definir la cadena de generacion de tipos OpenAPI -> TypeScript:**
   - `SKILL.md` §11.2 exige generar tipos desde OpenAPI sin escribir interfaces a mano. Agregar al setup `openapi-typescript` + `openapi-fetch` (o equivalente) y un script `npm run api:types` que lea el snapshot `backend/tests/contract/openapi.json` en CI.
2. **Automatizar la frontera hexagonal con `import-linter` desde el commit 1:**
   - Configurar `[tool.importlinter]` en `backend/pyproject.toml` con contratos explicitos:
     - `domain` no importa `application`, `adapters`, `worker`, `fastapi`, `pydantic`, `httpx` ni `supabase`.
     - `application` no importa `adapters` ni `fastapi`.
3. **Golden tests compartidos para `chunking` y limpieza de texto entre Python y TypeScript:**
   - Como el backend (Python) y el frontend (TypeScript) no pueden importar literalmente el mismo archivo de codigo, crear un archivo de fixture compartido (por ejemplo `shared/chunking-casos.json`) y ejecutar las mismas entradas/salidas esperadas en `pytest` y en `Vitest`.
4. **Definir el tooling de pruebas del frontend (`Vitest`):**
   - `AGENTS.md` §5 menciona `npm run test` pero `ARQUITECTURA.md` §1.3 no define el runner ni los mocks de `WebGPU` / `WebWorker` / `Cache API`. Fijar `vitest`, `@vue/test-utils` y adaptadores de prueba en `frontend/package.json`.
5. **Plantilla de extraccion semilla v1 (`PP-13`):**
   - Aunque los campos de riesgo finales dependan del cliente (`PP-13`), definir desde ya el esquema JSON de la plantilla generica v1 (estructura exacta de `plantillas_extraccion.esquema`, restricciones compatibles con XGrammar/Pydantic dinamico, e instruccion base de Map y Reduce) para poder probar de punta a punta desde la migracion 001.
6. **Healthcheck realista en `/health`:**
   - Definir explicitamente que hace `GET /health` en modo stateless PostgREST (consulta ligera a una vista/RPC publica o `roles` sin exponer datos de negocio ni usar `service_role`, devolviendo `200` o `503` si Supabase no responde).
7. **Incluir `.env.example` para backend y frontend antes de iniciar:**
   - Documentar todas las variables obligatorias de `ARQUITECTURA.md` §8 y las `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` del frontend.

---

## 6. Orden recomendado de correccion antes del primer commit de codigo

1. **Cerrar decisiones tecnicas de inicializacion (nuevo ADR-28 / actualizacion de ADR-01 y ADR-27):**
   - Fijar version de Python compatible con Vercel Functions (`3.14.x`) y TypeScript compatible con `vue-tsc` (`5.9.x` / `6.x`, o `7.1+`).
   - Elegir herramienta unica de migraciones (`supabase/migrations/*.sql` vs Alembic) y estrategia de revocacion de sesion en logout (`CA-11`).
   - Unificar politica `403` vs `404` compatible con RLS.
2. **Corregir el diseno de flujo y DDL antes de la migracion 001:**
   - Resolver la colision de `POST /api/v1/documentos` vs `POST /api/v1/trabajos` vs endpoint de registro de analisis.
   - Completar el DDL de `ARQUITECTURA.md` §5.1 con todas las columnas y tablas faltantes (`activo` en `perfiles`, `tamano_bytes`/`tipo_mime`/`archivado_en` en `documentos`, `is_system`/`nombre` en roles/permisos, `ultimo_latido_en`, `id_reporte`, `modelo` en `analisis_documentos`, `auditoria`, `documentos_compartidos`, politicas RLS completas en tablas y Storage, e idioma unico en timestamps).
   - Agregar los endpoints faltantes a `ARQUITECTURA.md` §7 (`cambiar-contrasena`, `reenviar-credencial`, `DELETE configuracion/motor`, `cancelar trabajo`, `auditoria`, `plantillas/{id}`, `historial`).
3. **Completar cobertura de RF y ajustar docs normativos:**
   - Crear o asignar HUs para `RF-11` (plantillas) y `RF-25` (borrado de documento + archivo), y actualizar estados en `CONTEXTO.md` (`RF-10`, `RF-14`).
   - Corregir `SKILL.md` (quitar ejemplos SQLAlchemy, corregir linea 2040, corregir `response_format.schema`, formula de chunking con `overlap_paginas` y tope por tokens reales), `CHECKLIST.md` (magic bytes, logout, Postgres en `supabase start`), `HU-01` (`JWT_ISSUER`), `HU-08` (formula de progreso y expiracion perezosa de trabajos sin latido) y `README.md` (PostgreSQL 17, 50 bloques con overlap=1).
4. **Inicializar el esqueleto del monorepo:**
   - `.gitignore`, `.env.example`, `backend/pyproject.toml` (con `import-linter`, `ruff`, `mypy`, `pytest`), `frontend/package.json` (con `vitest`, `openapi-typescript`), `vercel.json` actualizado, y `shared/chunking-casos.json`.
