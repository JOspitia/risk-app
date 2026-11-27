# HU-12 — Eliminación de un documento y su archivo

## Encabezado

- **HU ID:** `HU-12`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-25 (eliminar el archivo del almacenamiento al eliminar el documento)
- **ADR relacionados:** ADR-20 (el archivo se archiva en almacenamiento privado), ADR-22 (retencion por defecto: se conserva hasta que el dueno o un admin borra)
- **Bloquea:** ninguna
- **Bloqueado por:** HU-01 (sesion), HU-02 (permisos), HU-06 (el documento tiene archivo archivado)

---

## 1. Titulo y descripcion

**Titulo:** HU-12 — Eliminación de un documento y su archivo

**Descripción:** Poder **borrar un documento** y que el PDFarchived desaparezca tambien del
almacenamiento.

El borrado logico (`eliminado_en`) hace que el documento deje de aparecer en la
aplicacion. Pero el PDF sigue en el bucket. Eso no es un borrado: es esconder el archivo
en un sitio al que todavia se puede llegar, y es exactamente la clase de sorpresa que
un sistema de documentos confidentiales no puede tener.

Esta HU define el borrado completo:

1. El documento se marca como eliminado (borrado logico).
2. El archivo se elimina del almacenamiento privado.
3. Los analisis y bloques se van en cascada.
4. Si el archivo **no** se puede borrar, el documento **no** se marca como eliminado: se
   responde con un error explicito y no se deja el sistema en un estado intermedio.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Que el dueno o un admin borre un documento |
| 2 | Borrado logico del documento: `eliminado_en` |
| 3 | Borrado fisico del archivo en Supabase Storage |
| 4 | Borrado en cascada de bloques, analisis e historial |
| 5 | Verificar que el archivo **realmente** desaparecio |
| 6 | Registrar la operacion en la bitacora de auditoria |
| 7 | Invalidar las URL firmadas que existieran para ese archivo |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | **Restaurar** un documento borrado | Fuera de alcance. El borrado es irreversible en la v1 |
| 2 | Borrado masivo de documentos | Fuera de alcance |
| 3 | Politica de **retencion automatica** | ADR-22: se conserva hasta que alguien borra. No hay expiracion |
| 4 | Limpieza de **logs** o de auditoria previa | La auditoria no se borra: es el registro de que el documento existio |
| 5 | Borrar la cuenta de un usuario | Fuera de alcance. El usuario se desactiva (HU-03) |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion)
- **HU-02** (permiso `documentos.borrar`)
- **HU-06** (el documento tiene `ruta_archivo` y `archivado_en`)

### Esta HU BLOQUEA

- ninguna. Es la ultima HU del ciclo.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `permitir_borrado_dueno` | true | El dueno puede borrar lo suyo. `[PROPUESTO]` El cliente puede querer que solo un admin borre |
| `verificar_borrado` | true | Se comprueba que el objeto **no existe** en Storage despues de borrar |
| `reintentos_borrado` | 3 | Si la llamada a Storage falla por un error transitorio, se reintenta |
| `retencion_auditoria` | indefinida | La fila de auditoria **no** se borra con el documento |

---

## 5. Suposiciones

1. **El borrado logico y el fisico van juntos.** Si el archivo no se puede borrar, el
   documento no se marca como eliminado. Un documento marcado como borrado con el archivo
   vivo es un documento que todavia existe, solo que escondido.
2. El **orden es: archivo primero, registro despues.** Si el borrado del registro se
   hiciera primero y el archivo fallara, quedaria un archivo huerfano sin ninguna fila que
   lo referencie: nadie podria borrarlo jamas.
3. **El analisis se borra en cascada.** `bloques`, `analisis_documentos` y
   `analisis_historial` cuelgan del documento con `on delete cascade`. Un analisis sin
   documento no tiene sentido.
4. **La auditoria no se borra.** La fila que dice "el usuario X elimino el documento Y" es
   la evidencia de que el documento existio. Borrarla seria borrar el rastro.
5. **Las URL firmadas dejan de servir.** La URL firmada caduca por si misma en una hora, y
   ademas el objeto ya no existe: el almacenamiento responde 404.
6. **Borrar no es resetear.** Un documento borrado no se puede volver a analizar desde la
   aplicacion, porque el archivo ya no esta.
7. El permiso es **`documentos.borrar`**, no `documentos.ver`. Verificar que el documento
   existe es distinto de poder borrarlo.
8. **La eliminacion es logica en la base y fisica en el almacenamiento.** Son dos sistemas
   distintos y no se pueden confirmar en la misma transaccion. Por eso el orden importa y
   por eso se verifica despues.

---

## 6. Modelo de datos

No hay tablas nuevas. Esta HU usa lo que ya existe:

```
documentos.eliminado_en   timestamptz   -- se llena al borrar
documentos.ruta_archivo   text          -- deja de ser valido al borrar
```

Y las que se van en cascada por `on delete cascade`:

```
bloques            -> documentos
analisis_documentos -> documentos
analisis_historial  -> documentos
trabajos            -> documentos
trabajo_actividades -> trabajos
documentos_compartidos -> documentos
```

**La fila de `documentos` no se borra.** Se marca con `eliminado_en`. Esto sirve para tres
cosas:

1. Que el indice unico `documentos_hash_unico` (por `usuario_id` y `hash_sha256`, donde
   `eliminado_en is null`) libere el hash, para que el usuario pueda volver a subir el
   mismo PDF mas adelante.
2. Que el `hash_sha256` siga disponible para **detectar** que el usuario esta subiendo de
   nuevo el mismo archivo, sin duplicarlo en la base.
3. Que exista la evidencia de que el documento existio, sin conservar su contenido.

**La auditoria es la unica que sobrevive**, y no por accidento: vive en su propia tabla,
sin clave foranea hacia `documentos`.

---

## 7. Camino feliz principal

### 7.1 Pedir el borrado

1. El usuario abre el detalle de un documento y pulsa "Eliminar".
2. La UI pide confirmacion **explicita**: el archivo se elimina de forma permanente y no
   se puede recuperar. El texto de la confirmacion dice que se borra **tambien** el
   archivo, no solo el registro.
3. El frontend llama a `DELETE /api/v1/documentos/{id}`.

### 7.2 Comprobar permisos y existencia

1. El caso de uso comprueba el permiso **`documentos.borrar`** (ADR-30: primero el
   permiso, despues la fila).
2. Si el documento no aparece (no existe, o es de otra organizacion), responde **404**.
3. Si el documento ya esta eliminado, responde **404** tambien: borrarlo dos veces no es un
   error nuevo, y el recurso ya no esta. La UI lo trata como "ya no existe".

### 7.3 Borrar el archivo

1. Si `ruta_archivo` es nula (el documento nunca se archivo), se salta al paso 5.
2. Si no es nula, el backend llama al almacenamiento privado y **borra el objeto**.
3. Si la llamada falla por un error transitorio, se reintenta hasta `reintentos_borrado`.
4. Si sigue fallando:
   - el documento **no** se marca como eliminado,
   - se responde **500** con un mensaje que dice que el archivo no se pudo eliminar,
   - se registra el error en auditoria.
5. Con `verificar_borrado`, se comprueba que el objeto ya no existe.

### 7.4 Marcar el documento como eliminado

1. El backend marca `eliminado_en` y limpia `ruta_archivo`.
2. Los hijos (`bloques`, `analisis_documentos`, `analisis_historial`, `trabajos`) se
   eliminan en cascada.
3. La **URL firmada** que existia para el archivo deja de servir: el objeto ya no esta.

### 7.5 Registrar y responder

1. Se registra la operacion en `auditoria` con el actor, la entidad y la fecha.
2. Responde **200** con un envelope de exito y un mensaje que dice que se elimino el
   documento y su archivo.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El usuario **no tiene `documentos.borrar`** | 403 | 403 |
| SP-02 | El documento es de **otra organizacion** | 404. No se confirma que exista | 404 |
| SP-03 | El documento **no existe** | 404 | 404 |
| SP-04 | El documento **ya fue borrado** | 404. Borrarlo dos veces no es un error nuevo | 404 |
| SP-05 | El **almacenamiento falla** y no se puede borrar el archivo | 500. El documento **no** se marca como eliminado: no queda un archivo vivo con un registro escondido | 500 |
| SP-06 | El objeto **ya no estaba** en Storage (borrado por fuera) | Se trata como exito. El objetivo es que no exista, y no existe | 200 |
| SP-07 | La **verificacion posterior** dice que el objeto sigue ahi | 500. El documento no se marca. Se registra la inconsistencia en auditoria | 500 |
| SP-08 | El documento **no tiene archivo** (`ruta_archivo` nula) | Se borra igual, sin llamar a Storage | 200 |
| SP-09 | El usuario intenta borrar un documento **compartido** con el | 403. Compartir da lectura, no propiedad | 403 |
| SP-10 | Un **analisis se borra** con el documento | Es lo esperado: el analisis cuelga del documento. Si el cliente quiere conservar el analisis, la decision es de negocio y va en PP-10 | 200 |
| SP-11 | El usuario **revierte** la operacion | No hay soporte. El borrado es irreversible en la v1 | 409 |
| SP-12 | Dos borrados **simultaneos** del mismo documento | El segundo recibe 404. El archivo se borra una sola vez | 404 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El documento **nunca tuvo archivo** | Se borra igual. No hay llamada al almacenamiento |
| EC-02 | El documento esta **en proceso** cuando se borra | Se permite. El trabajo se borra en cascada. Si el cliente estaba analizando, su reporte de progreso recibe 404 y el cliente lo trata como "el documento ya no existe" |
| EC-03 | El documento fue **compartido** con tres personas | Las tres pierden el acceso: las filas de `documentos_compartidos` se van en cascada |
| EC-04 | El documento tiene **5 analisis en el historial** (fue reanalizado 4 veces) | Todos se borran en cascada |
| EC-05 | El archivo es de **30 MB** | Se borra igual. El tamano no cambia el mecanismo |
| EC-06 | El mismo PDF se vuelve a subir **despues** de borrarlo | Se acepta. El indice unico del hash solo aplica a documentos vivos |
| EC-07 | El usuario borra **todos** sus documentos | Se borran uno a uno. El borrado masivo no es un endpoint, pero el resultado es el mismo |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente llama a `DELETE` con un **`id` inventado** | 404. Los UUID no se adivinan |
| CE-02 | El cliente intenta `DELETE /documentos/{id}` **de otro** | 404 si es de otra organizacion; 403 si es de la misma y falta el permiso |
| CE-03 | El cliente pide **restaurar** con `PUT` | No hay endpoint. 404 |
| CE-04 | El cliente manda `eliminado_en` en el cuerpo del `DELETE` | Se ignora. Lo pone el servidor, con la hora del servidor |
| CE-05 | El usuario borra un documento **y al instante lo vuelve a subir** | Funciona. El hash quedo libre al marcar `eliminado_en` |
| CE-06 | El cliente pide borrar un documento **en proceso** con `?forzar=true` | El parametro no existe. Se ignora. El borrado ya funciona en ese caso |

---

## 10. Criterios de aceptacion

### CA-01: El archivo se borra, no solo se esconde
**Dado** un documento con archivo archivado
**Cuando** se borra
**Entonces** el objeto **no existe** en el almacenamiento privado
**Y** una peticion a la URL firmada responde 404
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Si el archivo no se borra, el documento no se marca
**Dado** que el almacenamiento falla al borrar el archivo
**Cuando** se pide el borrado del documento
**Entonces** la respuesta es 500
**Y** el documento **sigue visible**, con `eliminado_en` nulo
**Y** no queda un archivo vivo con un registro que dice que ya no existe
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: El permiso se comprueba en el caso de uso
**Dado** un usuario sin `documentos.borrar`
**Cuando** llama a `DELETE /api/v1/documentos/{id}` por la API
**Entonces** la operacion se deniega aunque el router lo permitiera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: Los hijos se van en cascada
**Dado** un documento con bloques, analisis e historial
**Cuando** se borra
**Entonces** no queda ningun bloque, analisis ni historial de ese documento
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: La auditoria sobrevive
**Dado** un documento borrado
**Cuando** se consulta la bitacora de auditoria
**Entonces** sigue la fila que registra quien lo elimino y cuando
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Borrar dos veces no es un error nuevo
**Dado** un documento ya borrado
**Cuando** se vuelve a pedir el borrado
**Entonces** la respuesta es 404
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: El hash se libera
**Dado** un documento borrado
**Cuando** el usuario vuelve a subir el mismo archivo
**Entonces** el documento se crea sin conflicto de unicidad
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Un documento de otra organizacion no se puede borrar
**Dado** un documento de otra organizacion
**Cuando** se pide su borrado
**Entonces** la respuesta es 404 y el documento sigue intacto
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: La confirmacion de la UI es explicita
**Dado** un documento con archivo archivado
**Cuando** el usuario pulsa "Eliminar"
**Entonces** la confirmacion dice que se borra **tambien** el archivo y que no se puede recuperar
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El documento desaparece de los listados
**Dado** un documento borrado
**Cuando** se listan los documentos
**Entonces** no aparece en ninguna lista, ni en la propia ni en la de la organizacion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
