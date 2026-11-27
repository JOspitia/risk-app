# Checklist de verificacion — Risk-app

> Gates que se ejecutan **contra un servidor corriendo**, no contra mocks. Cada item
> corresponde a algo que ya ha roto en otro proyecto. Un item sin verificar no cuenta como
> cumplido.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-27

---

## Gate 0 — Antes de escribir codigo

- [ ] Se leyeron `docs/CONTEXTO.md`, `docs/ARQUITECTURA.md` y `docs/DECISIONES-PENDIENTES.md`
- [ ] Los ADR aplicables a la iteracion estan identificados en la tabla de
      `docs/ARQUITECTURA.md` seccion 10
- [ ] Las preguntas abiertas que tocan el alcance estan resueltas o el supuesto esta
      anotado en el ADR
- [ ] El alcance de la iteracion esta escrito en una frase
- [ ] Los pasos 1 a 10 del "Quick start" de `SKILL.md` estan planeados

---

## Gate 1 — Esquema y migraciones

- [ ] Las migraciones se aplican limpiamente contra una base **vacia** (`supabase db reset`)
- [ ] El historial muestra todas las versiones aplicadas con exito
- [ ] **Una sola herramienta de migraciones**: SQL en `supabase/migrations/`. No hay Alembic
      ni tabla `alembic_version` (ADR-32)
- [ ] `supabase db push` aplica el mismo esquema en el proyecto de Supabase que el que se
      valido en local
- [ ] No hay auto-baseline activado fuera de adopcion de produccion
- [ ] Ninguna migracion ya aplicada fue editada despues
- [ ] Sin coma trailing antes del `)` de cierre de una definicion
- [ ] Sin `now()` en el predicado de un indice parcial
- [ ] Toda columna `uuid` de `auth.users` tiene su FK y su `on delete`
- [ ] RLS activo en toda tabla con datos de usuario, verificado con un usuario real
- [ ] Las columnas JSONB tienen indice GIN si se consultan por contenido

---

## Gate 2 — Seguridad

- [ ] Ningun secreto en el codigo ni en `.env` versionado
- [ ] El arranque **falla** si falta `JWT_SECRET` u otra variable obligatoria
- [ ] `JWT_SECRET` tiene 32 caracteres o mas
- [ ] `service_role` no se usa para atender peticiones de usuario final
- [ ] `service_role` nunca se expone al frontend ni viaja en el bundle
- [ ] La validacion del token comprueba firma, `exp`, `aud` y emisor
- [ ] Un token invalido, malformado o con firma adulterada devuelve 401, no 500
- [ ] El cuerpo de ninguna respuesta contiene un hash de contrasena, un hash de token ni
      una columna interna
- [ ] El rol del usuario se verifica en el caso de uso, no solo en el router
- [ ] Un usuario de otra organizacion recibe 403 o 404, nunca datos
- [ ] El tipo real del archivo se valida en el **navegador** (magic bytes `%PDF-`) antes de
      subir, y el bucketStorage restringe los MIME permitidos. El backend **no** declara
      validar magic bytes: nunca ve el archivo (ver I-07 del informe de validacion)
- [ ] El limite de tamano de archivo se aplica antes de leerlo en memoria
- [ ] Los logs no contienen contenido del documento ni texto extraido
- [ ] CORS no es `*` en un entorno con credenciales

---

## Gate 3 — Arquitectura (dependencias)

- [ ] `domain/` no importa nada de `adapters/`, `application/` ni de frameworks
      (verificable con `import-linter`)
- [ ] Ningun router (adaptador de entrada) llama a un repositorio directamente
- [ ] Ningun caso de uso construye schemas de HTTP ni conoce `Request`/`Response`
- [ ] Ningun error de dominio se captura y se reenvuelve en un error generico
- [ ] Los puertos los define el dominio, no la infraestructura
- [ ] Cada puerto declarado tiene al menos una implementacion en `adapters/`
- [ ] No hay puertos para librerias de terceros que no van a cambiar

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
- [ ] El usuario se crea con la cuenta **sin confirmar**, y la confirmacion va en el correo
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
- [ ] El backend valida tamano y tipo MIM **antes** de firmar la URL de subida
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

- [ ] Cada error de dominio mapea al codigo de estado previsto (400/401/403/404/409/500)
- [ ] Las violaciones de integridad se despachan por el codigo SQLState exacto, no por la
      clase
- [ ] El envelope es el mismo en exito y en error
- [ ] El envelope de error trae un identificador legible por maquina, no solo prosa
- [ ] Las marcas de tiempo se serializan en ISO-8601 (RFC 3339)
- [ ] La ISO-8601 se verifica sobre el **cuerpo real** de la respuesta, no solo en la
      configuracion
- [ ] `new Date(valor)` en JavaScript devuelve el anio correcto
- [ ] Los booleanos son `true`/`false`, no `0`/`1` ni `"true"`
- [ ] Los nulos son `null` explicito, no claves ausentes ni `"null"`
- [ ] La paginacion devuelve metadatos, no un array desnudo
- [ ] `page` por defecto 1, `size` por defecto 20, maximo 100, recortado y no rechazado

---

## Gate 6 — ETL y LLM

- [ ] Un PDF sin capa de texto se marca como error explicito, no como analisis vacio
- [ ] El hash `sha256` del archivo se calcula y se persiste
- [ ] Los bloques cubren todas las paginas sin huecos fuera del solapamiento configurado
- [ ] **El tamano de bloque se deriva de la ventana de contexto del modelo**, no esta fijo
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
- [ ] El cliente HTTP centraliza el token: ningun `fetch` escribe el header a mano
- [ ] Los tipos de la API se generan desde el OpenAPI; no hay `any`
- [ ] El PDF nunca se serializa ni se envia en el camino principal

---

## Gate 8 — Pruebas

- [ ] El dominio y los casos de uso tienen pruebas unitarias sin base de datos ni red
- [ ] Las pruebas de integracion corren contra Postgres real en Docker
- [ ] Hay una prueba de ciclo de vida completo: crear -> leer -> actualizar -> borrar
- [ ] Un intento de login en cuenta inactiva, bloqueada o eliminada es rechazado
- [ ] Dos sesiones simultaneas funcionan ambas
- [ ] Logout invalida el token de inmediato, sin esperar la expiracion
- [ ] Un token revocado se rechaza en la peticion siguiente
- [ ] Intentar revocar la sesion de otro usuario da 403 o 404
- [ ] La suite de inyeccion (SQLi, XSS, unicode, sobredimensionado, tipos erroneos) no
      produce 500 y no destruye datos
- [ ] La asercion de limpieza es explicita: "no 500" no basta, la tabla debe seguir existiendo
- [ ] La concurrencia (N altas simultaneas, N escrituras sobre la misma fila) no produce
      perdidas de escritura ni 500
- [ ] El comando de build/test **incluye** las pruebas, no solo las fuentes de produccion
- [ ] La suite se reejecuto desde limpio y se reconstruyo de verdad

---

## Gate 9 — Listo para el frontend

- [ ] `GET /health` responde 200 e informa el estado de la base de datos
- [ ] Todas las rutas estan documentadas con metodo, ruta, forma de peticion y de respuesta
- [ ] El contrato OpenAPI es estable (snapshot en `tests/contract/`)
- [ ] El login devuelve un token usable de inmediato
- [ ] Las rutas protegidas rechazan token ausente, malformado y adulterado
- [ ] El listado de documentos devuelve paginacion con metadatos
- [ ] Los DTO de salida no exponen ningun campo sensible (inspeccion del cuerpo real)
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
- [ ] El bundle del frontend no contiene ninguna llave secreta
- [ ] El codigo del adaptador de LLM no tiene ningun destino por defecto que sea una API de
      terceros
- [ ] El `service_role` no se usa para atender peticiones de usuario final

## Gate 11 — Despliegue

- [ ] El backend es stateless: no mantiene conexiones abiertas entre peticiones
- [ ] El camino de ejecucion **no** usa una conexion TCP a Postgres (solo PostgREST/RPC),
      para que la migracion a Cloudflare Workers sea posible sin cambios
- [ ] Las funciones de Postgres con `security definer` comprueban el permiso **dentro** de la
      funcion, y tienen `set search_path = public`
- [ ] `vercel.json` declara el runtime de Python y el `maxDuration` por ruta, de forma
      explicita
- [ ] Ningun endpoint del camino principal acepta un cuerpo mayor a 4.5 MB
- [ ] La API responde en menos de 300 s con la carga esperada (limite por defecto de la
      funcion)
- [ ] El `Dockerfile` construye y la imagen levanta el backend en local
- [ ] Las variables de entorno del entorno de produccion estan definidas en el proveedor,
      no en un archivo versionado

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

## Regla de la puerta

> Si un item falla, el entregable no esta listo. Un frontend construido sobre una API a
> medias absorbe cada hueco como si fuera su propio error, y el diagnostico se pierde.
