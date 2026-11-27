# HU-10 — Reanalisis con la plantilla vigente

## Encabezado

- **HU ID:** `HU-10`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-24 (volver a analizar un documento archivado cuando cambie la plantilla, sin volver a pedir el archivo)
- **ADR relacionados:** ADR-20 (los documentos se archivan en Supabase Storage, en un bucket privado, subidos directo desde el navegador), ADR-25 (el resultado es un JSON de resumenes por bloque + resumen ejecutivo, entregado por DTO), ADR-26 (el reanálisis tiene su propio endpoint y el archivo viaja del bucket al navegador), ADR-14 (seguimiento en la tabla `trabajos`)
- **Decisiones abiertas que resuelve:** DP-13 (que pasa con los resultados cuando cambia la plantilla) — cerrada: **se guardan los documentos** (ADR-20)
- **Bloquea:** ninguna
- **Bloqueado por:** HU-04 (configuracion del motor), HU-05 (modelo descargado), HU-06 (documento archivado), HU-07 (pipeline de analisis), HU-08 (seguimiento del trabajo)

---

## 1. Titulo y descripcion

**Titulo:** HU-10 — Reanalisis con la plantilla vigente

**Descripcion:** La plantilla de extraccion cambia. El documento **sigue archivado**. El
usuario quiere volver a analizarlo con la plantilla nueva **sin volver a buscar el archivo
en su computador**.

Esta HU cierra DP-13, que estaba abierta justamente por esta pregunta: que hacer con los
resultados cuando la plantilla cambia. La decision fue **guardar los documentos** (ADR-20),
y esa decision es la que hace posible esta HU.

El reanálisis es un **analisis nuevo**, no una edicion del anterior:

- El resultado anterior **se conserva**. Es el historial de lo que se vio con la plantilla
  vieja.
- El resultado nuevo **se referencia a la version de plantilla que se uso**.
- Los dos se pueden consultar por separado.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Pedir el reanálisis de un documento archivado desde su detalle |
| 2 | Detectar que la plantilla activa **cambio** desde el analisis original |
| 3 | Descargar el archivo del almacenamiento privado, **en el navegador** |
| 4 | Reejecutar el pipeline completo con la plantilla vigente |
| 5 | Conservar el analisis anterior y referenciar el nuevo |
| 6 | Reportar el reanálisis como un trabajo mas, con su propio progreso |
| 7 | Marcar el documento con la version de plantilla vigente |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Reanalizar **en el servidor** | Fuera de la v1 (ADR-19). El pipeline corre en el navegador |
| 2 | Comparar el resultado viejo con el nuevo | Fuera de la v1. Los dos analisis quedan disponibles |
| 3 | Versionar el **documento** (subir una version corregida del PDF) | Fuera de alcance. Es una HU aparte |
| 4 | Reanalizar un **documento que no esta archivado** | Fuera de alcance: si esta en el equipo, el usuario lo reanaliza desde el archivo |
| 5 | Reanadir **varios documentos** a la vez | Fuera de alcance. La cola del cliente (HU-08) los procesa en orden, pero el reanálisis se pide de a uno |
| 6 | Notificar por correo que el reanálisis termino | Fuera de alcance |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-04** (configuracion del motor: el reanálisis usa la configuracion vigente)
- **HU-05** (modelo descargado: sin modelo no hay analisis)
- **HU-06** (el documento esta archivado en el bucket privado)
- **HU-07** (el pipeline a reejecutar)
- **HU-08** (el reanálisis es un trabajo con progreso)

### Esta HU BLOQUEA

- ninguna. Es la ultima HU del ciclo.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `permitir_reanalisis` | true | Interruptor por organizacion. `[PROPUESTO]` El cliente puede querer que el reanálisis solo lo haga un admin |
| `version_maxima_analisis` | sin limite | `[PROPUESTO]` Poner un tope evita crecimiento de la tabla |
| `comparar_con_anterior` | true | El reanálisis compara el resultado con el anterior y avisa si **cayo** el numero de campos obligatorios detectados |
| `max_reanalisis_por_dia` | `[PENDIENTE]` | Depende del uso. No se define sin conocer al cliente |

### La plantilla que se usa

El reanálisis usa **la plantilla activa en el momento de pedirlo**, no la que se uso en el
analisis original. El parametro `plantilla_id` es opcional: si no se envia, se toma la
activa de la organizacion.

---

## 5. Suposiciones

1. **El archivo esta en el almacenamiento privado**, no en el disco del usuario. Si el
   documento nunca se archivo, **no hay reanálisis**: hay que volver a subir el archivo.
2. La **descarga del archivo ocurre en el navegador**, del bucket privado al equipo del
   usuario, y de vuelta al pipeline. El PDF **no pasa por la funcion del backend** en
   ningun momento: ni al descargarlo, ni al procesarlo.
3. El **analisis anterior se conserva intacto**. El reanálisis **no** sobrescribe.
4. `analisis_documentos.documento_id` es `unique`. Un documento tiene **un** analisis
   persistido. Por eso el reanálisis **no** inserta una fila nueva en esa tabla: **actualiza**
   la fila existente y guarda el resultado anterior en el historial.
5. El **analisis anterior se conserva en una tabla de historial** (`analisis_historial`),
   con la version de plantilla y la fecha. Sin eso, el "no sobrescribir" seria una promesa
   sin almacenamiento.
6. El reanálisis **usa el motor vigente**. Si el modelo cambio desde el analisis original,
   el resultado puede diferir por el modelo, no solo por la plantilla. Por eso el historial
   guarda tambien el modelo usado.
7. La comparacion con el anterior es **informativa**: avisa que el numero de hallazgos
   cayo, pero **no bloquea** ni **no revierte**. Quien decide sobre el documento es el
   usuario.
8. El reanálisis **arranca un trabajo nuevo** con `tipo = 'reanalisis'`. El trabajo
   anterior no se toca.
9. El **estado del documento** pasa a `en_proceso` durante el reanálisis y vuelve a
   `completado` al terminar. El estado del documento no distingue "analizado por primera
   vez" de "reanalizado": es lo que se ve en la lista.
10. La plantilla se referencia con **version**, no solo con id. Una plantilla editada es una
    version nueva.

---

## 6. Modelo de datos

### Cambio en `analisis_documentos`

El analisis vigente **sigue siendo uno por documento**: la restriccion `unique` sobre
`documento_id` **se mantiene**. Lo que cambia es que, al reanalizar, el analisis anterior
**se mueve** a una tabla de historial en vez de sobrescribirse:

```sql
-- sin cambios: un documento, un analisis vigente
documento_id uuid not null unique references documentos(id) on delete cascade
```

Y se agrega la tabla del historial:

```
analisis_historial
  id                uuid primary key
  documento_id      uuid -> documentos(id) on delete cascade
  usuario_id        uuid -> auth.users(id)
  plantilla_id      uuid -> plantillas_extraccion(id)
  plantilla_version int
  modelo            text          -- modelo usado en ese analisis
  resumen_ejecutivo text
  riesgos           jsonb
  resumenes         jsonb
 reemplazado_por    uuid -> analisis_documentos(id)   -- id del analisis que lo sustituyo
  created_at        timestamptz
```

> El nombre del campo que apunta al analisis que sustituyo al anterior se documenta aqui
> con un nombre provisional. `[PENDIENTE]` Definir el nombre definitivo en la migracion.

**El reanálisis es una transaccion de dos movimientos:** el analisis vigente pasa al
historial, y el nuevo ocupa su lugar. Si falla uno, se deshacen los dos.

**Alternativa descartada:** conservar ambos analisis en `analisis_documentos` con un campo
`es_actual boolean`. Es mas simple de escribir, pero obliga a **relajar el `unique`** y
deja que "el analisis del documento" sea una consulta ambigua. La tabla aparte no obliga a
tocar la restriccion y deja el historial con su propia forma. `[PENDIENTE]` La decision
final se cierra en la migracion.

**El `trabajo` del reanálisis** es el mismo modelo:

```
trabajos
  tipo = 'reanalisis'
  documento_id -> el mismo documento
```

---

## 7. Camino feliz principal

### 7.1 Detectar que la plantilla cambio

1. El usuario abre el detalle de un documento archivado.
2. El detalle muestra la plantilla que se uso en el analisis original (`plantilla_version`)
   y la **version activa** de la plantilla de la organizacion.
3. Si son distintas, la UI ofrece la accion **"Reanalizar con la plantilla vigente"**.
4. Si son iguales, la accion **no** se ofrece: no hay nada que actualizar.

### 7.2 Pedir el reanálisis

1. El usuario pulsa la accion.
2. El frontend llama a `POST /api/v1/documentos/{id}/reanalisis`.
3. El backend, en el caso de uso:
   - comprueba el permiso `documentos.analizar` **en el caso de uso**,
   - comprueba que el documento esta archivado (`ruta_archivo` no es nula): si no, 409,
   - comprueba que el documento esta en `completado`: si esta en proceso, 409,
   - comprueba que la version de la plantilla **cambio** desde el analisis original: si no
     cambio, 409 con el motivo,
   - comprueba el limite de reananálisis, si hay,
   - abre un trabajo con `tipo = 'reanalisis'` y devuelve `trabajo_id`.
4. La UI muestra el panel de progreso (HU-08).

### 7.3 Traer el archivo al navegador

1. El frontend pide la URL firmada: `GET /api/v1/documentos/{id}/descarga`.
2. El navegador **descarga el PDF** directamente del bucket privado.
3. El PDF vive en memoria del navegador. **No se sube al backend.**
4. El frontend lo entrega al Web Worker, que repite el ETL (HU-07).

### 7.4 Reanalizar

1. El pipeline corre exactamente igual que en el analisis original:
   - se extrae el texto con `pdf.js`,
   - se divide en bloques con el tamano derivado de la ventana de contexto **vigente**,
   - se ejecuta Map y Reduce con la **plantilla vigente**,
   - se reportan las actividades al trabajo.
2. El backend recibe los resultados por el endpoint de registro, y en la **misma
   transaccion**:
   - mueve el analisis anterior al historial,
   - actualiza `analisis_documentos` con el resultado nuevo,
   - marca el documento `completado`,
   - marca el trabajo `completado` y calcula `duracion_ms`.

### 7.5 Avisar de una caida en los hallazgos

1. El backend compara el numero de campos obligatorios detectados en el analisis nuevo con
   el del anterior.
2. Si el nuevo tiene **menos** campos que el anterior, la respuesta lo dice de forma
   explicita: "el reanálisis detecto 2 campos obligatorios menos que el analisis anterior".
3. Es **informativo**. El resultado nuevo queda guardado de todos modos, y el anterior
   tambien.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El documento **no esta archivado** | 409. Sin el archivo no hay reanálisis. El mensaje dice que hay que volver a subirlo | 409 |
| SP-02 | La **plantilla no cambio** desde el analisis original | 409. No hay nada que actualizar | 409 |
| SP-03 | El documento **esta en proceso** | 409. No se reananaliza un documento que ya se esta analizando | 409 |
| SP-04 | La **URL firmada expiro** entre pedirla y usarla | El almacenamiento la rechaza. La UI pide una nueva y reintenta | error del almacenamiento |
| SP-05 | El **modelo no esta descargado** en el equipo | La UI lo detecta antes de empezar (HU-05) y lo dice. No se abre el trabajo | error en la UI |
| SP-06 | El **equipo no soporta WebGPU** | La UI lo explica y ofrece el camino alternativo. `[PROPUESTO]` En la v1 solo hay modo navegador (ADR-19) | error en la UI |
| SP-07 | La **plantilla activa fue eliminada** | 404. No hay plantilla vigente contra la cual reanalizar | 404 |
| SP-08 | El reanálisis **falla a mitad** (el Worker muere) | El trabajo queda `error`, el documento vuelve a `error`, y **el analisis anterior sigue intacto**. Se puede reintentar | 200 con `estado = error` |
| SP-09 | El usuario **no tiene `documentos.analizar`** | 403 | 403 |
| SP-10 | El documento es de **otro usuario** | 404 si es de otra organizacion; 403 si es de la misma y falta el permiso. Ver ADR-30 | 404 / 403 |
| SP-11 | Se supera el **limite de reananálisis** | 429. El limite se documenta cuando exista | 429 |
| SP-12 | El **resultado nuevo no supera la validacion** | 422 y no se persiste nada. El analisis anterior sigue siendo el vigente | 422 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | Se reanaliza el **mismo documento dos veces** | Cada intento deja su historial. El analisis actual es el ultimo. El historial conserva los dos |
| EC-02 | La plantilla **cambio y luego volvio** a la version anterior | El reanálisis se ofrece igual: la version vigente es la que se usa. El historial muestra el camino recorrido |
| EC-03 | El documento tiene **250 paginas** | ~84 bloques. El reanálisis tarda lo mismo que tardo la primera vez, o mas si la plantilla nueva pide mas campos |
| EC-04 | La plantilla nueva pide **mas campos** que la vieja | El resultado nuevo tiene mas informacion. La comparacion no avisa: solo avisa cuando el numero **baja** |
| EC-05 | El modelo **cambio** entre el analisis original y el reanálisis | El historial guarda el modelo de cada analisis. La diferencia de resultados puede venir de la plantilla, del modelo o de ambos |
| EC-06 | El reanálisis tarda **mas que el original** | Es normal: la plantilla nueva puede pedir mas campos por bloque. El timeout total de 1 hora aplica igual |
| EC-07 | El **hash del archivo** sigue siendo el mismo | Se usa para verificar integridad, no para identificar el analisis. Un reanálisis no es un documento nuevo |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente pide un reanálisis **con una plantilla inactiva** | 422. Solo la plantilla vigente se puede usar |
| CE-02 | El cliente reanaliza un documento **borrado logicamente** | 404. El documento eliminado no se reanálisis |
| CE-03 | El cliente pide el reanálisis **en bucle**, 500 veces | El limite de reananálisis lo corta. `[PENDIENTE]` Definir el limite |
| CE-04 | El documento archivado **ya no esta en el bucket** (borrado por fuera) | El reanálisis falla al descargar y el trabajo queda `error`. El analisis anterior **sigue disponible** |
| CE-05 | La plantilla vigente tiene un **esquema con campos que el modelo no puede llenar** | La validacion del backend lo rechaza (422). La plantilla activa es responsabilidad de quien la edita |
| CE-06 | El cliente pide un reanálisis de un documento **en otro ambito** | 404. La comprobacion de ambito es la misma de HU-09 |

---

## 10. Criterios de aceptacion

### CA-01: El reanálisis no pide el archivo al usuario
**Dado** un documento archivado
**Cuando** el usuario pide el reanálisis
**Entonces** el frontend obtiene el PDF desde el bucket privado por URL firmada
**Y** el PDF **nunca** pasa por la funcion del backend
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: El analisis anterior se conserva
**Dado** un documento con un analisis previo
**Cuando** se completa un reanálisis
**Entonces** el analisis anterior sigue consultable
**Y** no se sobrescribio
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: Un reanálisis es un trabajo mas
**Dado** un reanálisis en curso
**Cuando** se consulta el trabajo
**Entonces** tiene `tipo = 'reanalisis'`, su propio progreso y su propia bitacora
**Y** el trabajo anterior no se modifico
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: Solo se ofrece si la plantilla cambio
**Dado** un documento cuyo analisis uso la version vigente de la plantilla
**Cuando** se abre el detalle
**Entonces** la accion de reanálisis no se ofrece
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: La version de plantilla queda registrada
**Dado** un reanálisis con la version 2 de la plantilla
**Cuando** se consulta el analisis
**Entonces** la respuesta trae `plantilla_version = 2`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Un fallo no deja al documento sin analisis
**Dado** un reanálisis que falla a mitad
**Cuando** el trabajo termina en `error`
**Entonces** el analisis anterior sigue siendo el vigente y consultable
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: La caida de hallazgos se avisa
**Dado** un analisis anterior con 5 campos obligatorios detectados
**Cuando** el reanálisis detecta 3
**Entonces** la respuesta dice que se detectaron menos campos que en el analisis anterior
**Y** el resultado nuevo queda guardado de todos modos
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Un documento no archivado no se reanálisis
**Dado** un documento sin archivo en el almacenamiento
**Cuando** se pide el reanálisis
**Entonces** la respuesta es 409 y explica que hay que volver a subir el archivo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: El permiso se comprueba en el caso de uso
**Dado** un usuario sin `documentos.analizar`
**Cuando** pide el reanálisis por la API
**Entonces** la operacion se deniega aunque el router lo permitiera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El reanálisis usa la plantilla vigente
**Dado** una plantilla activa de version 2
**Cuando** se reanaliza un documento
**Entonces** el pipeline usa el esquema y la instruccion de la version 2
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: La persistencia del reanálisis es atomica
**Dado** un reanálisis completo
**Cuando** se persiste
**Entonces** el analisis anterior pasa al historial, el nuevo queda vigente y el documento
queda `completado`, **en una sola transaccion**
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: El reanálisis no crea un documento nuevo
**Dado** un documento archivado
**Cuando** se reanaliza
**Entonces** sigue siendo **el mismo** `documento_id`
**Y** el hash del archivo no cambia
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
