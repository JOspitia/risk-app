# HU-09 — Consulta de resultados y descarga

## Encabezado

- **HU ID:** `HU-09`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-09 (listar y consultar documentos y resultados, con paginacion y filtro por ambito), RF-19 (entregar el resultado como JSON de resumenes por bloque mas el resumen ejecutivo, mapeado por DTO), RF-23 (descargar el documento mediante un enlace temporal, solo para quien tenga permiso)
- **ADR relacionados:** ADR-15 (el resultado es un JSON de resumenes por bloque + resumen ejecutivo, entregado por DTO), ADR-17 (la visibilidad la determina el permiso), ADR-20 (el archivo esta en almacenamiento privado)
- **Bloquea:** HU-10 (reanalisis)
- **Bloqueado por:** HU-01 (sesion), HU-02 (permisos), HU-07 (el resultado existe)

---

## 1. Titulo y descripcion

**Titulo:** HU-09 — Consulta de resultados y descarga

**Descripcion:** Volver a un documento analizado y **ver lo que salio**: el resumen ejecutivo,
los campos de riesgo extraidos, el detalle bloque por bloque con la pagina de la que salio
cada dato, y la bitacora de como se proceso.

Y, si el documento se archivo, **descargarlo** para volver a el.

Tres cosas resuelven la visibilidad, que es el objetivo declarado del sistema de permisos:

1. **Listar** los documentos visibles con paginacion y filtro por ambito.
2. **Consultar** el detalle y el analisis completo en un formato estable, definido por un
   DTO, no por la forma de la tabla.
3. **Descargar** el archivo original con un enlace temporal que expira, y solo si el
   permiso lo autoriza.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Listar documentos con paginacion y metadatos de pagina |
| 2 | Filtrar el listado por estado, ambito y documento |
| 3 | Consultar el detalle de un documento: estado, paginas, error, trabajo asociado |
| 4 | Consultar el analisis completo mapeado por DTO |
| 5 | Consultar el detalle por bloques, con sus datos estructurados y su pagina |
| 6 | Descargar el archivo original mediante URL firmada de 1 hora |
| 7 | Ocultar los documentos que el usuario no puede ver, sin listarlos |
| 8 | Indicar que un documento esta en proceso y a cuanto va |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Exportar a Excel o CSV | Fuera de la v1. El DTO ya es el punto de extension |
| 2 | Buscar dentro del texto del documento | Fuera de alcance. El JSON guarda lo que se necesita |
| 3 | Chat conversacional sobre los resultados | Fuera de alcance (DP-07) |
| 4 | Eliminar documentos y sus archivos | RF-25, gate de borrado |
| 5 | Comparar dos analisis del mismo documento | Fuera de la v1. HU-10 deja la base para tener mas de uno |
| 6 | Compartir un documento con otro usuario | El permiso `documentos.compartir` ya existe; la pantalla de compartir no es de esta HU |
| 7 | Reanalizar | HU-10 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion: sin JWT no hay consulta)
- **HU-02** (permisos: sin permiso no hay visibilidad)
- **HU-07** (el resultado existe y esta validado)

### Esta HU BLOQUEA

- **HU-10**: el reanálisis parte de un documento archivado que se consulta desde aqui.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `page` | 1 | Se recorta, no se rechaza |
| `size` | 20 | Maximo 100 |
| `duracion_url_firmada` | 3600 s | **1 hora.** `[PROPUESTO]` Confirmar con el cliente |
| `filtro_estado` | todos | `en_proceso \| completado \| error \| interrumpido` |
| `filtro_ambito` | `mis_documentos` | `mis_documentos \| organizacion` |
| `filtro_plantilla` | sin filtro | Filtra por `plantilla_id` |
| `max_bloques_por_consulta` | 100 | Pagina del detalle por bloques |

### Filtro por ambito

El ambito es **lo que el permiso permite**, no una regla fija:

| Ambito | Que incluye |
|---|---|
| `mis_documentos` | Los documentos cuyo `usuario_id` es el usuario actual |
| `organizacion` | Todos los de su organizacion. **Requiere** `analisis.ver_todos` |

Un `analista` que pide `ambito = organizacion` **sin** `analisis.ver_todos` recibe la lista
propia, no un 403: la ausencia del permiso se traduce en menos resultados, no en un error.
El permiso ausente se deniega **para la accion**, no para la lectura de lo propio.

---

## 5. Suposiciones

1. **El JSON de la base no sale crudo.** El DTO decide que se expone. Agregar una columna a
   la tabla no agrega un campo a la respuesta.
2. El DTO **no contiene logica de negocio ni acceso a datos**. Solo mapea.
3. El listado devuelve **metadatos de paginacion** (`total`, `totalPages`, `hasNext`,
   `hasPrevious`). Un array desnudo no alcanza para pintar los controles.
4. Los **documentos que el usuario no puede ver no aparecen**. No se devuelven con los
   campos vacios ni con un marcador: no aparecen. Un documento invisible no debe ser
   adivinable por su identificador.
5. El **detalle de bloques** se pagina igual que el listado. Un documento de 250 paginas
   tiene ~84 bloques.
6. La **descarga es por URL firmada**, no por el backend. El PDF no pasa por la funcion de
   Vercel: el cuerpo de peticion llega a 4.5 MB y el sistema de archivos es de solo
   lectura.
7. La **URL firmada expira en 1 hora**. Pasada la hora, el enlace deja de servir y hay que
   pedir uno nuevo.
8. El **hash SHA-256 se usa para deduplicar**, no se expone en las respuestas publicas. Es
   un identificador interno.
9. El **estado de un documento en proceso** se lee del trabajo: progreso, paso actual y
   duracion. Si el trabajo esta `interrumpido`, el documento se muestra como tal, no como
   "en proceso" para siempre.
10. El listado ordena por `created_at desc`. Es el orden que espera el usuario.
11. **El auditor ve en solo lectura.** Sus endpoints de escritura responden 403.

---

## 6. Modelo de datos

Esta HU **no crea tablas**. Consulta las existentes:

```
documentos       -> lista y detalle
bloques          -> detalle por bloques
analisis_documentos -> analisis completo (DTO de salida)
trabajos         -> estado y progreso del documento en proceso
```

### El DTO de salida

```python
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
```

**No sale:** `usuario_id`, `hash_sha256`, `ruta_archivo`, `organizacion_id` interno ni
ninguna columna que no este en el DTO. `ruta_archivo` es el **mas sensible**: es la ruta en
el bucket privado, y aunque sola no sirva para nada, no tiene por que viajar.

---

## 7. Camino feliz principal

### 7.1 Listar documentos

1. El usuario abre la lista de documentos.
2. El frontend llama a `GET /api/v1/documentos?page=1&size=20&ambito=mis_documentos`.
3. El backend:
   - resuelve el contexto de auditoria (usuario, rol, organizacion),
   - comprueba el permiso `documentos.ver` **en el caso de uso**,
   - arma la consulta con el filtro de ambito derivado del permiso,
   - cuenta el total y pagina,
   - responde con el envelope de paginacion.
4. La UI pinta los controles: pagina actual, total, siguiente, anterior.

### 7.2 Filtrar

1. El usuario elige un estado, un ambito o una plantilla.
2. El frontend repite la peticion con el filtro. La consulta **se recorta**, no se rechaza:
   un `size = 500` baja a 100.
3. La lista se actualiza. El filtro vive en la URL, de modo que el usuario puede compartir
   el enlace de su vista.

### 7.3 Consultar el detalle

1. El usuario abre un documento.
2. El frontend llama a `GET /api/v1/documentos/{id}`.
3. El backend comprueba **primero el permiso** y **despues la fila** (ADR-30):
   - si falta el permiso que la accion exige, responde **403**,
   - si el permiso esta pero la fila no aparece (no existe, o es de otra organizacion y RLS
     la filtro), responde **404**.
4. La respuesta trae nombre, paginas, estado, fechas, error si lo hay, y el estado del
   trabajo si sigue en proceso.
5. Si el documento esta en proceso, el frontend consulta el trabajo y muestra el progreso.

### 7.4 Consultar el analisis

1. El frontend llama a `GET /api/v1/documentos/{id}/analisis`.
2. El backend arma el `AnalisisResource` a partir del modelo: resumen ejecutivo, riesgos,
   resumenes por bloque y version de la plantilla.
3. La UI muestra el resumen ejecutivo y el listado de campos de riesgo.

### 7.5 Consultar el detalle por bloques

1. El frontend llama a `GET /api/v1/documentos/{id}/bloques?page=1&size=20`.
2. La respuesta trae, por bloque: indice, rango de paginas, resumen y datos estructurados.
3. La UI permite ver **de que pagina salio cada dato**.

### 7.6 Descargar el archivo

1. El usuario pulsa "Descargar original".
2. El frontend llama a `GET /api/v1/documentos/{id}/descarga`.
3. El backend:
   - comprueba el permiso `archivos.descargar` **en el caso de uso**,
   - comprueba que el documento tiene ruta de archivo,
   - genera una **URL firmada** de 1 hora contra el bucket privado,
   - responde 200 con la URL y la fecha de expiracion.
4. El navegador abre la URL. El archivo baja directamente desde el almacenamiento privado.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El documento **no existe** | 404 | 404 |
| SP-02 | El documento es de **otra organizacion** | 404. RLS filtra la fila y la respuesta no confirma que ese identificador exista | 404 |
| SP-02b | El documento es de la **misma organizacion** pero falta el permiso de la accion | 403. El usuario ya sabe que existe: esta en su equipo. Ocultarlo no aporta seguridad | 403 |
| SP-03 | El usuario **no tiene `documentos.ver`** | 403. La ausencia de permiso se deniega | 403 |
| SP-04 | Piden `ambito = organizacion` **sin `analisis.ver_todos`** | 200 con la lista propia. Menos resultados, no un error | 200 |
| SP-05 | `size = 500` | Se recorta a 100. No es un error | 200 |
| SP-06 | `page = 0` o `page = -1` | Se recorta a 1. No es un error | 200 |
| SP-07 | `size = 0` | Se recorta al minimo (1). No es un error | 200 |
| SP-08 | Se pide la **descarga** sin `archivos.descargar` | 403 | 403 |
| SP-09 | El documento **no tiene archivo archivado** | 409. El documento se analizado pero el archivo no se guardo. Se explica en el mensaje | 409 |
| SP-10 | La **URL firmada ya expiro** | El almacenamiento responde 400 o 403. La UI detecta que expiro y pide una nueva | error del almacenamiento |
| SP-11 | El **analisis no existe todavia** (documento en proceso) | 404 en el endpoint de analisis, y el detalle muestra el progreso. No se devuelve un analisis vacio | 404 |
| SP-12 | El **documento esta en error** | El detalle trae `error_mensaje`. El endpoint de analisis responde 404: no hay analisis | 404 |
| SP-13 | El usuario pide **paginas mas alla del total** | 200 con `data` vacio y los metadatos correctos. `hasNext = false` | 200 |
| SP-14 | El **JWT expiro o fue revocado** | El contexto es anonimo y la peticion se rechaza con 401 | 401 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El usuario **no pertenece a ninguna organizacion** | Solo ve sus propios documentos. La pertenencia nula no le da acceso a nada |
| EC-02 | El documento esta **completado pero sin resumen ejecutivo** (la plantilla no lo exige) | Se devuelve `resumen_ejecutivo = null`. La UI lo muestra como "sin resumen". No es un error |
| EC-03 | El analisis tiene **0 bloques** | `total_bloques = 0` y la lista de resumenes vacia. La UI lo dice |
| EC-04 | El documento tiene **1 solo bloque** | Se devuelve igual que con 50. La paginacion del detalle no muestra controles inútiles |
| EC-05 | El **total de la lista es 0** | `total = 0`, `totalPages = 0`, `hasNext = false`. La UI muestra el estado vacio |
| EC-06 | La **plantilla se desactivo** despues del analisis | El analisis conserva su `plantilla_version`. Se muestra la version usada, no la plantilla activa |
| EC-07 | El usuario pide **`ambito = organizacion`** y la organizacion tiene 500 documentos | Se pagina normal. El total es el de la organizacion |
| EC-08 | Un documento **borrado logicamente** (`eliminado_en`) | No aparece en el listado ni se puede abrir. La URL firmada del archivo deja de servir |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El usuario pide el detalle de un documento **con id inventado** | 404. Los UUID no se adivinan |
| CE-02 | El usuario intenta ver el **analisis de otro usuario** de la misma organizacion | 403 si no tiene `analisis.ver_todos`; 200 si lo tiene. Decide el permiso, y el permiso se comprueba antes de consultar |
| CE-03 | El cliente pide **1000 bloques** en una sola llamada | Se recorta a 100 y se devuelven los metadatos de paginacion |
| CE-04 | El usuario pide la **descarga 50 veces seguidas** | Cada peticion devuelve una URL nueva de 1 hora. No hay limite en la v1; se documenta como posible abuse |
| CE-05 | El documento tiene **el nombre con caracteres raros** (comillas, saltos de linea) | Se escapa al serializar. La UI lo muestra literal, sin interpretaion de HTML |
| CE-06 | El cliente pide el analisis con **el `documento_id` de otro** y el `id` de un analisis suyo | 404. El analisis se busca por `documento_id`, no se acepta un id suelto |
| CE-07 | El cliente pide el listado **sin el header de autorizacion** | 401 |
| CE-08 | La **ruta del bucket** se filtra en el listado | No ocurre: `ruta_archivo` no esta en ningun DTO de listado ni de detalle. Si aparece, es un fallo |

---

## 10. Criterios de aceptacion

### CA-01: El JSON no sale crudo
**Dado** un analisis persistido con `usuario_id` y `hash_sha256`
**Cuando** se consulta el endpoint de analisis
**Entonces** la respuesta no contiene `usuario_id`, `hash_sha256` ni `ruta_archivo`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: La respuesta distingue permiso de aislamiento
**Dado** un documento de **otra organizacion**
**Cuando** se pide su detalle
**Entonces** la respuesta es 404
**Y** el cuerpo no confirma que el documento existe
**Dado** un documento de la **misma organizacion** sobre el que falta el permiso
**Cuando** se pide su detalle
**Entonces** la respuesta es 403
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: La paginacion trae metadatos
**Dado** 47 documentos visibles
**Cuando** se pide la pagina 1 con tamano 20
**Entonces** la respuesta trae `data`, `page`, `size`, `total`, `totalPages`, `hasNext` y
`hasPrevious`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: Los parametros fuera de rango se recortan
**Dado** una peticion con `size = 500` y `page = 0`
**Cuando** se procesa
**Entonces** se responde 200 con `size = 100` y `page = 1`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El ambito lo decide el permiso
**Dado** un `analista` sin `analisis.ver_todos`
**Cuando** pide `ambito = organizacion`
**Entonces** la respuesta es 200 con solo sus documentos
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: El permiso se comprueba en el caso de uso
**Dado** un usuario sin `documentos.ver`
**Cuando** invoca el endpoint de listado por la API
**Entonces** la operacion se deniega aunque el router lo permitiera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: La descarga va por URL firmada
**Dado** un documento con archivo archivado
**Cuando** se pide la descarga
**Entonces** la respuesta es una URL firmada con expiracion de 1 hora
**Y** el PDF no pasa por la funcion del backend
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: La descarga exige permiso
**Dado** un usuario sin `archivos.descargar`
**Cuando** pide la descarga
**Entonces** la respuesta es 403 y no se genera ninguna URL
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: El detalle por bloque dice de que pagina salio cada dato
**Dado** un analisis de 50 bloques
**Cuando** se consulta el detalle por bloques
**Entonces** cada bloque trae su indice, su rango de paginas y sus datos estructurados
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: Un documento en proceso muestra su avance
**Dado** un documento cuyo trabajo va en el bloque 7 de 34
**Cuando** se consulta el detalle
**Entonces** la respuesta incluye el progreso y el paso actual
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: Un documento sin analisis no devuelve analisis vacio
**Dado** un documento en `en_proceso` o en `error`
**Cuando** se pide el endpoint de analisis
**Entonces** la respuesta es 404, no un analisis con campos vacios
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: El auditor solo lee
**Dado** un usuario con rol `auditor`
**Cuando** intenta una operacion de escritura sobre documentos
**Entonces** la respuesta es 403
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-13: El filtro vive en la URL
**Dado** una lista filtrada por estado
**Cuando** el usuario recarga la pagina
**Entonces** el filtro se mantiene y la lista es la misma
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-14: La ruta del bucket nunca se expone
**Dado** cualquier listado o detalle
**Cuando** se revisa la respuesta
**Entonces** ningun campo contiene la ruta del objeto en el almacenamiento
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
