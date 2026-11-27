# HU-08 — Seguimiento del trabajo

## Encabezado

- **HU ID:** `HU-08`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-17 (reportar el avance: porcentaje, paso actual y tiempo transcurrido), RF-18 (registrar la lista de actividades realizadas durante el analisis), RF-21 (recuperar un analisis interrumpido sin intervencion manual)
- **ADR relacionados:** ADR-14 (seguimiento en la tabla `trabajos`, con latido), ADR-10 (la cola vive en el cliente, el estado vive en el servidor)
- **Bloquea:** HU-09 (consulta de resultados), HU-10 (reanalisis)
- **Bloqueado por:** HU-06 (documento registrado), HU-07 (el analisis reporta progreso)

---

## 1. Titulo y descripcion

**Titulo:** HU-08 — Seguimiento del trabajo

**Descripcion:** Saber **cuanto falta, cuanto lleva y que ha pasado** mientras el documento se
analiza, sin recargar la pagina, sin bloquear la aplicacion y sin intervention manual si
algo sale mal.

El analisis de un documento de 100 paginas tarda minutos. Para el usuario, una pantalla en
blanco durante cuatro minutos se lee como un cuelgue, y lo mas probable es que cierre la
pestana. Esta HU resuelve las dos cosas:

1. **Visibilidad.** Un panel en vivo con el progreso, el paso actual, el tiempo transcurrido
   y la bitacora de pasos ejecutados.
2. **Recuperacion.** Si el usuario cierra la pestana o el equipo se apaga, el trabajo se
   detecta como abandonado y el documento queda disponible para reintentarse, sin que nadie
   tenga que llamar a soporte.

El estado vive en el servidor (`trabajos` y `trabajo_actividades`), la ejecucion vive en el
navegador. El navegador **reporta**; el servidor **decide**.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Abrir un trabajo y registrar su estado inicial (`en_cola`) |
| 2 | Reportar progreso: porcentaje, paso actual y avance por bloque |
| 3 | Registrar la bitacora de actividades (extraccion, bloque, reduce, persistencia) |
| 4 | Calcular la duracion en el servidor, no en el cliente |
| 5 | Cerrar el trabajo como `completado`, `error` o `cancelado` |
| 6 | Detectar un trabajo abandonado por falta de latido y marcarlo `interrumpido` |
| 7 | Mostrar el panel de progreso en vivo con polling |
| 8 | Permitir reintentar un trabajo interrumpido |
| 9 | Encolar varios documentos y procesarlos uno a uno |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | La cola en el servidor (`pgmq`) | Fuera de la v1 (ADR-10). Se documenta para el modo hospedado |
| 2 | Pausar y reanudar un analisis a mitad | Fuera de alcance. El Web Worker no se puede reanudar |
| 3 | La ejecucion del ETL en el servidor | Fuera de la v1 (ADR-19) |
| 4 | Notificaciones por correo del avance | Fuera de alcance. El correo ya se usa para el alta de usuarios |
| 5 | La bitacora de auditoria de la organizacion | Gate de auditoria (`auditoria.ver`), no esta HU |
| 6 | El contenido de los resultados | HU-09 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-06** (el documento esta registrado y el trabajo tiene un `documento_id`)
- **HU-07** (el pipeline sabe reportar avance por bloque)

### Esta HU BLOQUEA

- **HU-09**: la consulta de resultados muestra el estado del trabajo y su bitacora.
- **HU-10**: el reanalyze nace de un trabajo interrumpido.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `intervalo_polling_ms` | 2000 | Frecuencia del polling al endpoint de trabajo |
| `timeout_latido_ms` | 120000 | **2 minutos.** Sin latido en este margen, el trabajo se considera abandonado |
| `duracion_latido_max_ms` | 30000 | Cada reporte de progreso lleva su propio latido |
| `progreso_por_bloque` | derivado | `100 / total_bloques`, repartido por etapas. Ver abajo |
| `max_intentos_reanudacion` | 3 | Intentos de reanudar un trabajo interrumpido desde la UI |
| `tamano_pagina_trabajos` | 20 | Pagina del listado de trabajos |

### Reparto del progreso

El progreso **no se proyecta por tiempo transcurrido**. Con 50 bloques, cada bloque vale
2 puntos. Si un bloque tarda el doble que los demas, proyectar por tiempo miente: la
barra llegaria al 90% cuando apenas va por la mitad.

La formula es **una sola**, y las etapas tienen peso:

```
progreso = floor(
    5                                          # extraccion del texto
  + bloques_completados * 85 / total_bloques   # map
  + 8 * etapas_reduce_completadas / etapas_reduce  # reduce
  + 2                                          # persistencia
)
```

El progreso **es monotono**: nunca disminuye. Un reporte con un porcentaje menor que el
actual se ignora (o se rechaza con 409).

Las etapas tienen peso porque los pasos no tienen la misma duracion: extraer el texto es
rapido, reducir 50 resumenes es lo mas lento, y persistir es instantaneo. Repartir el
100% entre bloques sin mas haria que la barra se quedara en 5% durante casi todo el
trabajo.

**Un bloque pesa 85/50 = 1.7 puntos.** Con 100 paginas, tamano 3 y solapamiento 1, el
documento tiene 50 bloques, no 34: ver `ARQUITECTURA.md` seccion 6.4.

---

## 5. Suposiciones

1. El cliente reporta el progreso al endpoint de reporte. **Nunca** escribe en la base
   directamente: la base no acepta progreso de un cliente que no sea el dueno del trabajo.
2. El progreso es **monotono**: nunca disminuye. Un reporte con un porcentaje menor que el
   actual se ignora (o se rechaza con 409).
3. `duracion_ms` se calcula en el servidor a partir de `iniciado_en` y `finalizado_en`. El
   reloj del cliente no es confiable para esto.
4. `paso_actual` es **texto para humanos** ("analizando bloque 7 de 34"), no un estado de
   maquina. La UI lo muestra tal cual.
5. La **bitacora de actividades es aditiva**. Se pueden registrar varias filas por reporte;
   el backend solo inserta, no reemplaza.
6. El **latido viaja dentro del reporte de progreso**. No es un endpoint aparte: asi no se
   puede olvidar de enviarlo.
7. El marcado de trabajos abandonados lo hace el **servidor, en lectura**: cuando alguien
   consulta un trabajo, un documento o la lista de trabajos, los que no han reportado
   latido en mas de 2 minutos se marcan `interrumpido` en esa misma operacion. No hay
   `cron`: en Vercel Hobby los cron corren una vez al dia y una expresion cada 2 minutos
   falla el despliegue (ADR-24).
8. Un trabajo `interrumpido` **no se borra**: se conserva su bitacora, que es la evidencia de
   hasta donde llego el analisis.
9. El documento en `en_proceso` cuyo trabajo esta `interrumpido` queda **disponible para
   reintentar**. El reintento crea un trabajo nuevo; el anterior se conserva.
10. El polling es suficiente para este volumen. Si mas adelante hace falta tiempo real, el
    mismo endpoint sirve para SSE sin cambiar el contrato.
11. La cola del cliente procesa **un documento a la vez**, en el orden en que se anadieron.

---

## 6. Modelo de datos

```
trabajos
  id              uuid primary key
  documento_id    uuid -> documentos(id)
  usuario_id      uuid -> auth.users(id)
  tipo            text     -- analisis | reanalisis
  estado          text     -- en_cola | en_proceso | completado | error | cancelado | interrumpido
  progreso        int      -- 0 a 100, monotono
  paso_actual     text     -- 'analizando bloque 7 de 34'
  modo            text     -- navegador_local | servidor_python
  iniciado_en     timestamptz
  finalizado_en   timestamptz
  duracion_ms     bigint   -- calculado en el servidor
  error_mensaje   text
  created_at      timestamptz
```

```
trabajo_actividades
  id            uuid primary key
  trabajo_id    uuid -> trabajos(id)
  tipo          text   -- extraccion | bloque | reduce | persistencia
  mensaje       text
  pagina_inicio int
  pagina_fin    int
  duracion_ms   int
  created_at    timestamptz
```

**`trabajo_actividades` no tiene `usuario_id`.** Pertenece al trabajo, y el trabajo ya tiene
dueno. Anadirlo duplicaria la fuente de verdad del aislamiento.

**`estado = 'interrumpido'` se agrega a la lista de estados.** Es el estado que deja el
trabajo abandonado cuando la expiracion perezosa lo detecta. No es un estado terminal de
exito: el documento sigue sin resultado.

**`trabajos.ultimo_latido_en` es obligatoria.** Sin ella no hay forma de saber cuando fue
el ultimo reporte: `created_at` no sirve, porque los reportes posteriores no lo actualizan.
El indice parcial `trabajos (estado, ultimo_latido_en)` soporta la consulta de expiracion.

---

## 7. Camino feliz principal

### 7.1 Abrir el trabajo

1. El usuario selecciona un PDF (HU-06 ya lo registro).
2. El frontend llama a `POST /api/v1/trabajos` con el `documento_id`.
3. El backend:
   - comprueba el permiso `documentos.analizar` **en el caso de uso**,
   - comprueba que el trabajo no este ya abierto para ese documento,
   - crea el trabajo en `en_cola`, `progreso = 0`,
   - responde 201 con `trabajo_id`, `estado` y `progreso`.
4. El frontend encola el trabajo en la cola del cliente.

### 7.2 Reportar el progreso

1. El Web Worker termina la extraccion y llama al endpoint de reporte con `progreso = 5`,
   `paso_actual = "extrayendo texto"` y la actividad `extraccion`.
2. Por cada bloque terminado, el cliente reporta:
   - `progreso` calculado por fraccion de bloques completados,
   - `paso_actual = "analizando bloque 7 de 34"`,
   - la actividad `bloque` con `pagina_inicio`, `pagina_fin` y `duracion_ms`.
3. Cada reporte lleva su **latido**: el campo `latido` con la hora del cliente.
4. El backend:
   - comprueba que el trabajo existe y que el cliente es el dueno,
   - **ignora** un reporte con progreso menor que el actual (no es un error, es ruido de red),
   - **rechaza con 409** un reporte para un trabajo ya cerrado,
   - actualiza `progreso`, `paso_actual` y `latido`,
   - inserta las filas de `trabajo_actividades`.
5. La UI, que consulta cada 2 segundos, refleja el nuevo estado.

### 7.3 Cerrar el trabajo

1. Al terminar el reduce, el cliente envia los resultados (HU-07) y el backend, en la misma
   transaccion, marca el trabajo `completado`, calcula `duracion_ms` y registra la actividad
   `persistencia`.
2. El frontend deja de consultar ese trabajo y muestra el resumen.

### 7.4 Recuperar un trabajo interrumpido

1. El usuario cierra la pestana a mitad del analisis. El trabajo queda en `en_proceso`.
2. Pasan 2 minutos sin latido.
3. Cuando el usuario vuelve a abrir la aplicacion y consulta sus documentos, el backend
   detecta el trabajo sin latido, lo marca `interrumpido`, libera el documento y escribe una
   actividad con el motivo. **Es la misma peticion**: no hay ninguna tarea de fondo que
   corra antes.
4. El usuario ve el documento con el estado "interrumpido" y la opcion de **reintentar**.
5. Al reintentar, se crea un **trabajo nuevo** (tipo `analisis`) que apunta al mismo
   documento. El trabajo anterior se conserva como historial.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El cliente reporta progreso de un trabajo **ajeno** | 403. La pertenencia se verifica en el caso de uso, no solo en la politica | 403 |
| SP-02 | El cliente reporta progreso de un trabajo **ya cerrado** | 409. El progreso de un trabajo terminado no se acepta | 409 |
| SP-03 | Un reporte trae un **progreso menor** que el actual | Se ignora y se responde con el estado actual. Es ruido de red, no un fallo | 200 |
| SP-04 | El trabajo **no existe** | 404 | 404 |
| SP-05 | El cliente **no tiene permiso** para analizar | 403 | 403 |
| SP-06 | Ya existe un trabajo **abierto** para el mismo documento | 409. Un documento no se analiza dos veces a la vez | 409 |
| SP-07 | El cliente **pierde la conexion** a mitad del analisis | El analisis local continua. Los reportes fallan, se reintentan al volver la conexion y el trabajo queda `interrumpido` si no se recupera dentro del margen | 503 en el reporte |
| SP-08 | La **pestana se cierra** a mitad | El trabajo queda `en_proceso` sin latido. La expiracion perezosa lo marca `interrumpido` en la siguiente lectura | HU-08 (mecanismo) |
| SP-09 | El navegador **se queda sin memoria** o el Worker muere | Se reporta `error` con el motivo. El documento queda en `error` y se puede reintentar | 200 con `estado = error` |
| SP-10 | **Nadie consulta** el trabajo abandonado | El trabajo sigue en `en_proceso` hasta que alguien lo mire. Es inocuo: el documento solo se libera cuando el usuario vuelve | comportamiento diferido |
| SP-11 | El cliente reporta una **bitacora enorme** (miles de filas) | 422 por el limite de actividades por reporte. El backend no acepta lo que sea | 422 |
| SP-12 | El **reporte tiene un latido con fecha futura** | Se ignora el latido para la deteccion de abandono (el reloj del cliente no es confiable), pero se acepta el resto del reporte | 200 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | Un documento de **1 pagina** | Un bloque. El progreso salta de 5 a 90 y luego a 100. Se ve raro pero es correcto |
| EC-02 | El documento tiene **0 bloques** | Error antes de abrir el trabajo. No hay nada que reportar |
| EC-03 | El total de bloques es **1** | `floor(100/1) = 100` puntos por bloque. La barra avanza de golpe. Correcto |
| EC-04 | La fraccion de fracciones **suma mas de 100** | El calculo se normaliza: la suma real de las fracciones es la que se usa. No hay hardcodeo de numeros sueltos |
| EC-05 | Un trabajo queda en `en_proceso` **sin ninguna actividad** | Es valido: el trabajo se creo pero el Worker no arranco. La expiracion perezosa lo marca `interrumpido` |
| EC-06 | El cliente reporta **muchas actividades a la vez** | Se insertan todas en una sola transaccion. O se guardan todas o ninguna |
| EC-07 | El trabajo **se reintenta tres veces** | Al cuarto intento se deja de ofrecer el reintento automatico. Un bucle de reintentos sobre un documento problematico es un fallo del cliente, no del sistema |
| EC-08 | Dos pestanas del **mismo usuario** con el mismo documento | La segunda recibe 409 en la apertura del trabajo. El documento no se procesa dos veces |
| EC-09 | El analisis termina **en menos de un segundo** | `duracion_ms` puede ser 0. Se muestra como "menos de un segundo" |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente reporta progreso **sin haber hecho nada** | Se acepta. El backend no puede saber si el Worker avanza; solo sabe que el dueno del trabajo reporta |
| CE-02 | El cliente reporta `progreso = 100` de golpe | Se acepta. El progreso lo declara el cliente. Lo que el backend garantiza es que **no** se guarde un resultado que no paso la validacion |
| CE-03 | El cliente manda la **bitacora con el texto del documento** dentro del mensaje | 422. La bitacora es un mensaje corto de estado. El texto del documento nunca se escribe en el log ni en la bitacora |
| CE-04 | El cliente reporta con un `trabajo_id` **inventado** | 404. Los UUID ajenos no se adivinan |
| CE-05 | El cliente intenta **cerrar el trabajo de otro** | 403 |
| CE-06 | El cliente **repite el mismo reporte** tres veces (reintento de red) | Las actividades se insertan por id de reporte del cliente, de modo que el reintento **no duplica** filas |
| CE-07 | El cliente reporta un latido con la **hora del cliente muy atrasada** | El latido se compara contra el reloj del servidor para decidir abandono, pero la **duracion** se calcula siempre con el reloj del servidor |

---

## 10. Criterios de aceptacion

### CA-01: El progreso nunca disminuye
**Dado** un trabajo con `progreso = 40`
**Cuando** el cliente reporta `progreso = 20`
**Entonces** el valor almacenado sigue siendo 40
**Y** la respuesta devuelve el estado actual, no un error
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Un trabajo de otro usuario no se puede tocar
**Dado** un trabajo de otro usuario
**Cuando** el cliente reporta progreso
**Entonces** la respuesta es 403
**Y** no se modifica ni el trabajo ni su bitacora
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: Un trabajo cerrado no admite progreso
**Dado** un trabajo en `completado`
**Cuando** el cliente reporta progreso
**Entonces** la respuesta es 409
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: La duracion la calcula el servidor
**Dado** un trabajo con `iniciado_en` y `finalizado_en`
**Cuando** se consulta el trabajo
**Entonces** `duracion_ms` es la diferencia calculada por el servidor
**Y** el cliente no puede escribirla
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El abandono se detecta sin intervencion
**Dado** un trabajo en `en_proceso` sin latido por mas de 2 minutos
**Cuando** alguien consulta el trabajo o el documento
**Entonces** el trabajo queda en `interrumpido`
**Y** el documento queda disponible para reintentar
**Y** la operacion no depende de ninguna tarea de fondo ni de un `cron`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Reintentar crea un trabajo nuevo
**Dado** un trabajo `interrumpido`
**Cuando** el usuario reintenta
**Entonces** se crea un trabajo nuevo que apunta al mismo documento
**Y** el trabajo anterior se conserva con su bitacora
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: La bitacora es aditiva
**Dado** un trabajo con 12 actividades
**Cuando** el cliente reporta 3 actividades mas
**Entonces** el trabajo queda con 15
**Y** ninguna de las 12 anteriores se modifica
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Un reintento de red no duplica la bitacora
**Dado** un reporte ya recibido
**Cuando** el cliente lo reenvia por el mismo id de reporte
**Entonces** las actividades no se duplican
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: El progreso se calcula por fraccion de trabajo
**Dado** un documento de 50 bloques
**Cuando** se completan 17 bloques
**Entonces** el progreso informado incluye la fraccion de bloques completados
**Y** no se proyecta por tiempo transcurrido
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El panel se actualiza solo
**Dado** un trabajo en curso
**Cuando** el usuario mira la pantalla
**Entonces** el progreso, el paso actual y la bitacora se actualizan sin recargar la pagina
**Y** la aplicacion responde durante el analisis
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: El texto del documento no llega a la bitacora
**Dado** un analisis con actividad de tipo `bloque`
**Cuando** se lee la bitacora
**Entonces** contiene estado, paginas y duracion
**Y** ningun fragmento del texto del documento
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: El permiso se comprueba en el caso de uso
**Dado** un usuario sin `documentos.analizar`
**Cuando** abre un trabajo por el endpoint de la API
**Entonces** la operacion se deniega aunque el router lo permitiera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-13: Varios documentos se procesan en orden
**Dado** cinco documentos encolados
**Cuando** el cliente procesa la cola
**Entonces** se procesa uno a uno, en el orden en que se anadieron
**Y** cada uno tiene su propio trabajo con su propio progreso
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-14: El analisis no bloquea la interfaz
**Dado** un documento de 50 bloques
**Cuando** se analiza
**Entonces** la interfaz sigue respondiendo durante todo el analisis
**Y** el trabajo pesado corre en el Web Worker
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
