# Decisiones pendientes — Risk-app

> Preguntas abiertas que cambian la implementacion, y el historial de las ya cerradas.
> Cada una dice **que se decide**, **por que importa**, **que se asume mientras no se
> cierre** y **que bloquea**.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-27

Cuando una pregunta se cierra: se responde aqui, se registra como ADR en
[ARQUITECTURA.md](ARQUITECTURA.md#10-registro-de-decisiones-adr) y se actualiza el documento
afectado.

---

## Resumen

| ID | Pregunta | Impacto | Estado |
|---|---|---|---|
| DP-01 | Arquitectura del backend: hexagonal o en capas | Alto | **Cerrada** — hexagonal (ADR-02) |
| DP-02 | Modo de ejecucion del LLM en la v1 | Alto | **Cerrada** — navegador (ADR-06) |
| DP-03 | Tipo de documentos: digitales, escaneados o ambos | Alto | **Cerrada** — solo digitales (ADR-11) |
| DP-04 | Politica de visibilidad y roles | Alto | **Cerrada** — el permiso decide (ADR-12, ADR-13, ADR-17) |
| DP-05 | Autenticacion | Alto | **Cerrada** — Supabase Auth (ADR-05) |
| DP-06 | Donde corre el backend | Alto | **Cerrada** — Vercel + Supabase (ADR-07) |
| DP-07 | Que hace exactamente el LLM con cada bloque | Medio | **Cerrada** — resumenes por bloque en un JSON (ADR-15) |
| DP-08 | Hardware de los equipos de los usuarios | Medio | **Cerrada** — 8 a 16 GB, equipos de oficina |
| DP-09 | Formato de la entrega de resultados | Bajo | **Cerrada** — JSON mapeado por DTO (ADR-15) |
| DP-10 | Modelo por defecto y como se elige | Medio | **Cerrada** — default + panel de configuracion (ADR-16) |
| DP-11 | Caminos disponibles para quien no tiene WebGPU | Alto | **Cerrada** — solo navegador (ADR-19) |
| DP-12 | Presupuesto de tiempo de analisis | Medio | **Cerrada** — trabajo asincrono y progreso (ADR-14) |
| DP-13 | Que pasa con los resultados cuando cambia la plantilla | Bajo | **Cerrada** — se guardan los documentos (ADR-20) |
| DP-14 | Alta de usuarios desde la app | Medio | **Cerrada** — contrasena autogenerada por correo (ADR-18) |
| DP-15 | Politica de retencion de los documentos archivados | Medio | **Cerrada** — supuesto por defecto (ADR-22) |

---

# Cerradas

## DP-01 — Arquitectura del backend — CERRADA

**Decision.** `[DECIDIDO]` **Hexagonal (puertos y adaptadores).** ADR-02, 2026-11-27.

**Por que.** Hay tres adaptadores de salida intercambiables (Supabase, motor LLM,
almacenamiento) y dos modos de ejecucion del pipeline (navegador y servidor). La version en
capas resolveria el modo doble con banderas `if` repartidas por los servicios; con puertos
se resuelve con un adaptador mas. Ademas, el dominio se prueba sin base de datos ni red.

**Como se refleja en el codigo.** `domain/` sin dependencias de framework; los puertos los
define el dominio; `application/` con los casos de uso; `adapters/` con FastAPI, Supabase,
LLM y ETL. La tabla de mapeo contra la version en capas esta en `ARQUITECTURA.md` seccion
2.3, y los contratos del skill original se conservan mapeados uno a uno.

**El criterio de decision fue el costo de revertir.** Cambiar de estilo arquitectonico con
codigo escrito es caro; decidirlo antes de escribir la primera linea es gratis.

## DP-02 — Modo de ejecucion del LLM en la version 1 — CERRADA

**Decision.** `[DECIDIDO]` **El LLM se ejecuta en el navegador del usuario** (WebLLM sobre
WebGPU). ADR-06, 2026-11-27.

**Por que.** Tres razones se alinearon:

1. **Privacidad.** El documento no sale del equipo del usuario. Es la forma mas fuerte de
   cumplir el requisito critico.
2. **Costo.** No hay GPU que pagar. Los ~200 usuarios aportan su propio hardware.
3. **Despliegue.** Encaja con Vercel: la API solo recibe resultados ya calculados, asi que
   no necesita procesos largos ni cola de tareas.

**Como se refleja en el codigo.** El pipeline ETL + LLM vive en el frontend, en un Web
Worker. La API expone `POST /api/v1/documentos` para registrar resultados ya validados. El
modo `servidor_python` queda como un adaptador mas para la v2.

**Consecuencia asumida.** WebGPU no esta en todas las plataformas (~88.6% de cobertura
global). El camino alterno esta en DP-11.

## DP-05 — Autenticacion — CERRADA

**Decision.** `[DECIDIDO]` **Supabase Auth emite el JWT; el backend lo valida y lo reenvia a
Postgres para que RLS filtre.** ADR-05, 2026-11-27.

**Por que.** Una sola fuente de identidad. RLS deja de depender del codigo de aplicacion.
El hashing de contrasenas y la tabla de sesiones revocables quedan **fuera del alcance**, no
se mantienen como texto decorativo.

**Como se refleja en el codigo.** El backend valida firma, `exp`, `aud` e `iss` del token de
Supabase, resuelve el perfil (rol, `organizacion_id`) y construye el `AuditContext`. Nunca
usa la `service_role` para atender peticiones de usuario final; esa llave queda confinada al
adaptador de administracion (DP-14).

## DP-06 — Despliegue — CERRADA

**Decision.** `[DECIDIDO]` Despliegue en niveles. ADR-04, ADR-07, 2026-11-27.

| Nivel | Componente | Plataforma v1 |
|---|---|---|
| 1 | Frontend Vue estatico | Vercel (o cualquier CDN) |
| 2 | API FastAPI stateless | Vercel Functions (runtime de Python) |
| 3 | Datos, identidad y archivos | Supabase (Postgres + Auth + RLS + PostgREST + Storage) |
| 4 | Worker ETL con LLM hospedado | **No se desplega en la v1** (DP-11) |

**Por que.** El backend habla con Supabase **por HTTP**, no por TCP a Postgres. Eso lo deja
stateless y portable a Cloudflare Workers, Fly.io o un contenedor sin cambios de codigo. La
atomicidad de la persistencia se resuelve con funciones de Postgres (RPC), de modo que la
transaccion vive dentro de la base de datos.

**Sobre Docker.** Vercel **no** ejecuta contenedores Docker en produccion: compila desde el
codigo fuente. El `Dockerfile` sirve para el entorno local reproducible y para que el worker
de un futuro modo hospedado ya exista cuando se quiera ir a un servidor privado.

## DP-03 — Tipo de documentos — CERRADA

**Decision.** `[DECIDIDO]` **PDF con capa de texto (digitales). Sin OCR en la v1.**
ADR-11, 2026-11-27.

**Por que.** Los documentos que llegan al sistema son PDF generados digitalmente: el texto
se puede seleccionar y extraer directamente. Un escaneado se guarda como imagen y su texto
no existe hasta que alguien le haga OCR, que es un pipeline distinto.

**Como se refleja en el codigo.** Un PDF sin capa de texto se **detecta y se marca como
error explicito** (`estado = error`, `error_mensaje = "documento sin capa de texto: requiere
OCR"`), en vez de persistir un analisis vacio como si fuera valido. Ese es el fallo mas caro
del sistema porque no se ve: el documento queda "completado" y sin datos.

Cuando la operacion de OCR entre en el alcance, sera **otro adaptador de ETL**, no un
cambio en el pipeline. El puerto ya esta definido.

## DP-04 — Roles, permisos y creacion de usuarios — CERRADA

**Decision.** `[DECIDIDO]` Sistema de **roles y permisos granulares**, con la matriz en
datos, mas administracion de usuarios desde la propia aplicacion. ADR-12 y ADR-13.

**Por que.** El objetivo declarado es que el sistema sepa **que informacion puede ver cada
usuario que ingresa**, por encima del simple inicio de sesion. Y la administracion de
usuarios (crear cuentas, asignar roles) es parte del alcance.

**Como se refleja en el codigo.**

- La matriz de permisos vive en las tablas `permisos` y `rol_permisos`: agregar un permiso
  es un `insert`, no un despliegue.
- El permiso se comprueba **en el caso de uso**, no solo en el router.
- La regla de visibilidad es **"se ve lo que el permiso autoriza"**. No hay una regla fija
  de "solo lo propio" ni de "el equipo ve todo": lo decide la fila de `rol_permisos`. Por
  defecto el `analista` **no** recibe `analisis.ver_todos` y ve lo propio y lo que se le
  comparte de forma explicita (ADR-17).
- Crear usuarios usa la Admin API de Supabase, a traves de un **adaptador de
  administracion** que es el unico modulo autorizado a usar la `service_role`. La excepcion
  queda documentada y acotada, con auditoria.
- La matriz inicial por rol (`admin`, `analista`, `auditor`) esta en
  `ARQUITECTURA.md` seccion 5.5.

**Pendiente de refinamiento.** Que un `analista` vea los analisis de otros o no, y si un
`auditor` ve tambien los bloques crudos o solo el resumen consolidado.

## DP-07 — Que hace el LLM — CERRADA (para la v1)

**Decision.** `[DECIDIDO]` En la v1: el documento se divide en **50 bloques** (100 paginas a
3 por bloque), cada bloque genera un resumen, y esos 50 resumenes se consolidan en un
**JSON unico** junto con el resumen ejecutivo. ADR-15.

**Por que.** Es lo que el proyecto necesita hoy. La evolucion hacia responder preguntas
sobre el documento (RAG) **queda planteada pero no implementada**.

**Como se refleja en el codigo.** El JSON con los resumenes por bloque es el artefacto que
se guarda (`analisis_documentos.resumenes`) y el que consume la UI. Cada resumen conserva
su `indice` de bloque y su rango de paginas, que son las claves que permitiran indexar
mas adelante para el RAG. Guardarlos bien hoy es la mitad del trabajo del RAG de manana.

**Nota sobre los 50 bloques.** No es un numero fijo: sale de `total_paginas / 3` con el
tamano de bloque derivado de la ventana de contexto. Para un documento de 40 paginas
serian 20 bloques. El JSON no debe asumir 34.

## DP-08 — Hardware de los equipos — CERRADA

**Decision.** Equipos de trabajo de oficina, portatiles tipo ThinkPad, **8 a 16 GB de
RAM**. Las pruebas se hacen en un PC de prueba y los ajustes de hardware se aplican
despues.

**Por que importa.** Con 8 GB o mas y GPU con WebGPU (Chrome o Edge en Windows), el modo
navegador es viable. Los equipos de referencia son esos.

**Consecuencia.** El panel de configuracion debe **detectar** la capacidad del equipo y
sugerir el modelo que cabe, sin obligar al usuario a saber de VRAM.

## DP-09 — Entrega de resultados — CERRADA

**Decision.** `[DECIDIDO]` **El resultado es un JSON con las respuestas**, y se mapea con un
**DTO** para generar las respuestas de la API. ADR-15.

**Como se refleja en el codigo.** El JSONB de la base es un detalle de persistencia. El DTO
(`AnalisisResource`) es el contrato publico: decide que sale, y absorbe los cambios de
forma del JSON sin que el frontend se entere. Regla vigente: agregar un campo a la entidad
**no** lo agrega al DTO.

## DP-10 — Modelo por defecto y seleccion — CERRADA

**Decision.** `[DECIDIDO]` Hay un **modelo por defecto implementado**, y un **panel de
configuracion del motor** donde el usuario elige que modelo se ejecuta y ajusta sus
parametros. ADR-16.

**Como se refleja en el codigo.** El panel (`MotorConfigView`) ofrece: selector de modelo,
tamano de bloque, solapamiento, ventana de contexto y temperatura. La configuracion se
guarda por usuario o por organizacion y se aplica sin redesplegar.

**Complemento recomendado.** La app detecta la capacidad del equipo al entrar y **sugiere**
un modelo, dejando el selector por encima. Detectar es una ayuda; obligar a que cada
usuario investigue cuanta VRAM tiene antes de empezar es una barrera de adopcion.

## DP-12 — Tiempo de analisis y seguimiento — CERRADA

**Decision.** `[DECIDIDO]` El analisis entra en una **cola asincrona**, de modo que la app
siga funcionando mientras se procesa un documento, y se reporta **porcentaje de avance,
tiempo transcurrido y lista de actividades realizadas**. ADR-14.

**Como se refleja en el codigo.** La tabla `trabajos` y `trabajo_actividades`, el endpoint
`GET /api/v1/trabajos/{id}`, y la cola `pgmq` dentro de Postgres. Detalle completo en
`ARQUITECTURA.md` seccion 6.7.

**Un modelo unico para los dos modos.** El modo navegador no tiene cola, pero escribe en
la misma tabla `trabajos` y reporta por el mismo endpoint. La UI consume un solo contrato,
cualquiera que sea el modo.

**Lo que queda para el usuario final.** La UI debe mostrar: barra de progreso con
porcentaje, el paso actual en lenguaje llano ("analizando bloque 7 de 34"), el tiempo
transcurrido, y la bitacora de actividades. Sin esto, la espera en el equipo propio se
vive como un cuelgue.

**Donde vive la cola.** Con el LLM en el navegador, la cola **no esta en el servidor**: la
ejecucion vive en un Web Worker y la cola es del lado del cliente (varios documentos se
procesan en orden). El servidor es la autoridad sobre el estado: registra el trabajo,
recibe el progreso y lo persiste. La cola `pgmq` queda documentada para un eventual modo
hospedado, pero **no se construye en la v1**.

**Trabajo abandonado.** Si el usuario cierra la pestana a mitad del analisis, el trabajo se
queda en `en_proceso` para siempre. Se resuelve con un latido por reporte de progreso y
una tarea de mantenimiento que marca como `interrumpido` los trabajos sin latido.

## DP-11 — Caminos para quien no tiene WebGPU — CERRADA

**Decision.** `[DECIDIDO]` **Solo navegador.** El proyecto **no** hospeda el modelo.
ADR-19, 2026-11-27.

**Por que.** El usuario objetivo es personal administrativo que no va a instalar un LLM ni
a tener una GPU que dimensionar. El navegador es la unica via que no exige ninguna
intervencion tecnica.

**Consecuencias que quedan aceptadas:**

- La v1 **no necesita** servidor de modelos, GPU, memoria dedicada, worker con ETL en
  Python, ni cola en el servidor. Todo cabe en Vercel y Supabase.
- **Quien no tenga WebGPU no puede usar la aplicacion.** Cobertura global ~88.6%. La
  aplicacion debe decirlo de forma explicita y sugerir Chrome o Edge, no fallar en
  silencio.
- **La primera vez se descargan 1.5 a 3 GB.** Ese es el punto de friccion real: el usuario
  tiene que entender que esta descargando un modelo, cuanto lleva, y que queda guardado
  en su equipo. La interfaz de descarga debe explicar, mostrar el progreso y confirmar la
  persistencia.
- El modo hospedado queda documentado y **no construido**, con el contrato de `trabajo`
  preparado para que anadirlo no toque los casos de uso.

## DP-14 — Alta de usuarios desde la aplicacion — CERRADA

**Decision.** `[DECIDIDO]` El `admin` crea los usuarios **desde la aplicacion**. ADR-18,
2026-11-27.

**Datos que captura:** nombres, apellido 1, apellido 2, correo, y una **contrasena
autogenerada** que se envia al correo del usuario, seguida de confirmacion de la cuenta.

**Como se refleja en el codigo.**

- El caso de uso exige el permiso `usuarios.gestionar`.
- Genera la contrasena temporal, crea el usuario en Supabase con `email_confirm = false`,
  registra el perfil, envia el correo y marca `debe_cambiar_contrasena = true`.
- **El correo es un puerto de salida**, como el LLM o la base de datos: `NotificadorCorreo`,
  con una implementacion real (Resend, SES o SMTP) y una de desarrollo que solo escribe en
  el log. Sin esa segunda, el flujo no se puede probar sin contratar un servicio.
- La `service_role` queda confinada al adaptador de administracion, con la excepcion
  documentada (ADR-13).

**Riesgo aceptado.** La contrasena autogenerada viaja en claro por el correo y queda en el
buzon. Se mitiga obligando el cambio en el primer inicio de sesion. La alternativa mas
segura es un enlace de un solo uso para que el usuario elija su clave; es un cambio de
**solo el cuerpo del correo**, ni el puerto ni los casos de uso cambian.

---

## DP-13 — Que pasa con los resultados cuando cambia la plantilla — CERRADA

**Decision.** `[DECIDIDO]` **Se guardan los documentos y los resultados con la version de
plantilla con la que se hicieron.** Un analisis viejo no se reescribe; el documento
archivado permite re-analizar cuando se quiera.

**Por que.** La idea de negocio es guardar los documentos para poder volver a ellos. Eso
resuelve la pregunta de fondo: si la plantilla cambia, el documento sigue ahi, y volver a
analizarlo es una accion, no una migracion silenciosa.

**Como se refleja en el codigo.**

- `analisis_documentos` guarda `plantilla_id` y `plantilla_version`: el resultado es
  interpretable en el contexto de la plantilla con la que se produjo.
- `documentos.ruta_archivo` guarda el objeto archivado, con la clave
  `{organizacion_id}/{usuario_id}/{documento_id}.pdf`.
- Cambiar la plantilla **no** relanza nada. El resultado anterior se conserva intacto.
- **Re-analizar** es una accion explicita del dueno o de un admin: se descarga el archivo
  (URL firmada), el navegador lo analiza de nuevo con la plantilla vigente y el resultado
  se registra como un analisis nuevo. La version anterior se conserva.

**Consecuencia de privacidad.** Re-analizar significa que **el archivo vuelve a pasar por
el equipo del usuario**. Sigue sin procesarse en ningun servidor: el navegador lo analiza
como la primera vez. El unico sitio donde el archivo esta es el almacenamiento del
proyecto.

**Lo que queda por definir.** Si la plantilla es por organizacion o global, y si el
re-analisis reemplaza el resultado anterior o convive con el. La version anterior se
conserva en ambos casos; la reemplazo queda como la opcion mas simple.

**Cerrado al escribir HU-10.** La parte que faltaba —si el reanálisis reemplaza o convive—
queda **decidida**: el resultado vigente se reemplaza y el anterior **convive en el
historial** (ADR-25, tabla `analisis_historial`). Convivir por completo en
`analisis_documentos` obligaria a relajar el `unique` sobre `documento_id` y a hacer
ambigua la pregunta "cual es el analisis del documento". Lo que sigue abierto es
**quien puede pedir un reanálisis** (PP-10) y **cuantas veces** (PP-09).



## DP-15 — Politica de retencion de los documentos archivados — CERRADA (por ahora)

**Decision.** `[DECIDIDO]` **Supuesto por defecto: los documentos se conservan hasta que el
dueno o un administrador los elimina. Sin expiracion automatica.** ADR-22.

**Por que es un supuesto y no una politica.** El proyecto se va a presentar a una empresa
real, y ahi la retencion no es una decision de ingenieria: tiene plazos, base legal y
responsabilidad. Esos datos no existen todavia, y no se inventan.

**Que pasa cuando llegue el cliente.** Se cambia el valor y se actualiza este documento en
el mismo commit, con el ADR correspondiente. La mecanica ya esta: la eliminacion es una
accion del usuario, y el trabajo de borrado (base + archivo) ya esta especificado. Anadir
una expiracion automatica es una tarea de mantenimiento mas, no un cambio de modelo.

**Lo que hay que preguntarle al cliente cuando toque:**

- ¿Cuanto tiempo se conserva un documento?
- ¿Hay base legal para conservarlos, o es una decision de la empresa?
- ¿Quien puede eliminar un documento: solo el dueno, o tambien un administrador o un
  auditor?
- ¿Hay documentos que no se pueden eliminar (por obligacion legal) y que exijan una
  retencion mayor?

# Abiertas

_Ninguna abierta con impacto de arquitectura. Todas estan cerradas en la seccion de arriba.
Las siguientes son preguntas de parametrizacion, no de diseno, y se responden con los datos
del cliente cuando existan._

---

# Pendientes detectados al escribir las historias de usuario

Estos no surgieron de una decision de arquitectura, sino de **escribir los caminos de
error** de cada historia. Se anotan aqui para que no se pierdan dentro de los `.md` de HU,
que son documentos de trabajo y no la fuente de verdad.

| ID | Pendiente | Surge en | Impacto |
|---|---|---|---|
| PP-01 | Un usuario puede pertenecer a **varias organizaciones** con roles distintos. El modelo `organizaciones_miembros` lo permite, pero el `perfil` tiene un solo `organizacion_id` y el `AuditContext` no define como se elige la organizacion activa | HU-01 EC-06, HU-02 EC-02 | Medio. Afecta el modelo de contexto y el aislamiento |
| PP-02 | **Sesion en cookie `httpOnly`** en lugar de `localStorage` | HU-01 supuesto 5 | Bajo por ahora. Depende de la politica de seguridad del cliente |
| PP-03 | **SSO corporativo** (SAML u OIDC) | HU-01 fuera de alcance 8 | Bajo. Se resuelve con Supabase si el cliente lo pide |
| PP-04 | **Roles personalizados** creados por el administrador | HU-02 fuera de alcance 4 | Bajo. Se resuelve con una fila mas en `roles` |
| PP-05 | **Permisos individuales** por usuario, por encima del rol | HU-02 fuera de alcance 5 | Bajo. Requiere una tabla `usuario_permisos` |
| PP-06 | **Permisos de campo**: ver un dato pero no editarlo | HU-02 fuera de alcance 6 | Bajo. Es una decision de negocio, no tecnica |
| PP-07 | Un usuario **sin `organizacion_id`** puede iniciar sesion pero no operar | HU-01 SP-08 | Bajo. Falta confirmar si debe bloquearse antes |
| PP-08 | La gestion de **roles `is_system` en caliente** (sin migracion) | HU-02 supuesto 3 | Bajo. Hoy solo se cambian por migracion |
| PP-09 | El **limite de reananalisis por documento y por dia** | HU-10 variable `max_reanalisis_por_dia` | Bajo. Se fija cuando el cliente diga cuanto se reanaliza. Sin limite, el historial crece sin control |
| PP-10 | **Quien puede pedir un reanálisis**: cualquiera con `documentos.analizar` o solo un admin | HU-10 variable `permitir_reanalisis` | Medio. Es una politica del cliente. El interruptor por organizacion ya esta previsto |
| PP-11 | El **nombre definitivo del campo** que enlaza un analisis del historial con el que lo sustituyo | HU-10 seccion de modelo de datos | Bajo. Es una decision de la migracion. Se documenta `reemplazado_por` como nombre provisional |
| PP-12 | La **duracion de la URL firmada** de descarga | HU-09 variable `duracion_url_firmada` | Bajo. Se asume 1 hora. Confirmar con el cliente |
| PP-13 | Los **campos de riesgo concretos** que se extraen | HU-07 seccion 4, HU-10 comparacion de hallazgos | **Alto.** Depende del cliente. Sin esto la plantilla de extraccion sigue siendo generica y la demo no muestra el valor real |

**Supuesto mientras no se cierren:** se implementa lo minimo que las HU de la v1 necesitan.
PP-01 es el unico que toca el modelo de datos, y la decision ya esta tomada en el sentido de
**una organizacion activa por peticion**, con el resto como soporte para cuando el cliente
lo pida.

**PP-13 es el mas urgente de los nuevos:** sin los campos de riesgo concretos, la
extraccion es una demo generica. Es informacion que solo tiene el cliente.

---

## Preguntas de negocio heredadas del documento original

| ID | Pregunta | Impacto | Estado |
|---|---|---|---|
| DN-01 | ¿Que tipo de documentos son y como vienen? | ETL, OCR | **Cerrada** (DP-03): digitales |
| DN-02 | ¿Que equipos usan los ~200 usuarios? | Modo de ejecucion | **Cerrada** (DP-08): 8-16 GB, oficina |
| DN-03 | ¿Que debe hacer exactamente el LLM con las 100 paginas? | Esquema | **Cerrada** (DP-07): resumenes + JSON |
| DN-04 | ¿Quien ve los resultados de cada persona? | RLS, roles | **Cerrada** (DP-04): roles y permisos |
