# HU-11 — Plantillas de extracción

## Encabezado

- **HU ID:** `HU-11`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-11 (consultar y editar plantillas de extraccion sin migrar la base de datos)
- **ADR relacionados:** ADR-16 (la matriz de permisos vive en datos), ADR-34 (editar una plantilla crea una version nueva)
- **Bloquea:** HU-07 (el analisis usa una plantilla), HU-10 (el reanálisis usa la plantilla vigente)
- **Bloqueado por:** HU-02 (permisos), HU-01 (sesion)

---

## 1. Titulo y descripcion

**Titulo:** HU-11 — Plantillas de extracción

**Descripción:** Poder **cambiar qué se le pide al modelo** sin tocar el código y sin
migrar la base de datos.

La plantilla de extracción es la definición de los campos de riesgo que se le piden al
modelo: los nombres, los tipos, si son obligatorios, y la instrucción de extracción. Es la
pieza que hace que el sistema serve para un cliente concreto y no para otro: un cliente de
riesgo crediticio pide otros campos que uno de seguros.

Sin esto, cambiar lo que se extrae es un cambio de código, un despliegue, y una versión
nueva de la aplicación para todos los usuarios.

Esta HU cubre:

1. **Consultar** la plantilla activa y su historial de versiones.
2. **Editar** una plantilla creando una **versión nueva**, sin tocar la anterior.
3. **Activar** una versión concreta.
4. **Validar** que el esquema de la plantilla sea usable por el motor.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Listar las plantillas visibles para la organización |
| 2 | Consultar el detalle de una plantilla: campos, instrucción, versión, activa o no |
| 3 | Crear una plantilla nueva (admin) |
| 4 | Editar una plantilla creando una versión nueva (admin) |
| 5 | Activar o desactivar una versión |
| 6 | Validar el esquema contra el subconjunto de JSON Schema que admite el motor |
| 7 | Ver qué análisis usaron cada versión |
| 8 | Sembrar una plantilla genérica v1 que funcione desde la primera migración |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | **Editor visual** con arrastrar y soltar campos | Fuera de alcance. La v1 edita JSON y la instrucción |
| 2 | Plantillas **por documento** | Fuera de alcance. La plantilla es de la organización |
| 3 | **Historial** de analisis por version de plantilla | La tabla `analisis_documentos` guarda `plantilla_version`; la consulta ya existe |
| 4 | Plantillas del **modo hospedado** | Fuera de la v1 (ADR-19) |
| 5 | Traduccion de la instruccion | Fuera de alcance |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion: sin JWT no hay administracion)
- **HU-02** (permisos: `plantillas.editar` decide quien edita)

### Esta HU BLOQUEA

- **HU-07**: el analisis pide la plantilla activa y arma el esquema de salida.
- **HU-10**: el reanálisis compara la versión original con la vigente.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `version_inicial` | 1 | La primera versión de toda plantilla |
| `max_campos_por_plantilla` | 30 | `[PROPUESTO]` Tope de seguridad. Mas campos, mas tokens por bloque |
| `max_longitud_instruccion` | 4000 | Caracteres. La instruccion viaja en cada prompt |
| `plantilla_semilla_v1` | incluida | `[DECIDIDO]` Se siembra en `supabase/seed.sql` (ver seccion 6) |

### La estructura de una plantilla

```json
{
  "nombre": "Riesgo creditico v1",
  "instruccion": "Extrae los campos de riesgo del documento. Si un campo no aparece, dejalo en null. No inventes valores.",
  "esquema": {
    "type": "object",
    "properties": {
      "monto_solicitado": { "type": ["number", "null"], "description": "Monto solicitado en pesos" },
      "plazo_meses": { "type": ["integer", "null"], "description": "Plazo en meses" },
      "garante": { "type": ["boolean", "null"], "description": "Si tiene garante" }
    },
    "required": [],
    "additionalProperties": false
  }
}
```

El esquema es **JSON Schema**, no un formato propio: es lo que el motor entiende y lo que
Pydantic valida en el backend.

---

## 5. Suposiciones

1. **Editar no modifica: crea una versión.** La fila anterior queda intacta, con su
   `version`. El motivo es concreto: los análisis ya guardados apuntan a una versión, y si
   la plantilla se modificara en el sitio, un análisis de hace tres meses quedaría
   explicando con reglas que ya no son las que se aplicaron.
2. La **versión activa** es unico por plantilla. Una plantilla tiene exactamente una versión
   activa, o ninguna.
3. Un análisis guarda **`plantilla_version`**, no solo `plantilla_id`. Sin el numero de
   version, la version no se puede reconstruir.
4. El **esquema se valida en el backend** antes de guardar. Un esquema con construcciones
   que el motor no soporta es un error de guardado, no un fallo de ejecucion posterior.
5. La **instruccion se envia tal cual** en el prompt. No se concatena con datos del
   documento: la instruccion viene de la base, el documento viene del navegador, y el prompt
   los separa de forma explicita.
6. La plantilla pertenece a **la organizacion**. `organizacion_id` nulo significa plantilla
   del sistema, que todos pueden ver pero nadie puede editar sin ser admin.
7. **Desactivar no es eliminar.** Una plantilla desactivada no aparece en el selector, pero
   los analisis que la usaron siguen siendo consultables y muestran su version.
8. El **catalogo de modelos** de `HU-04` y la plantilla son cosas distintas: la plantilla
   define que se extrae, el modelo define con que se extrae.

---

## 6. Modelo de datos

La tabla ya existe en `ARQUITECTURA.md` seccion 5.1. Esta HU define su uso:

```
plantillas_extraccion
  id               uuid primary key
  organizacion_id  uuid -> organizaciones(id)     -- nulo = plantilla del sistema
  nombre           text not null
  version          int  not null default 1
  esquema          jsonb not null
  instruccion      text not null
  activa           boolean not null default true
  creado_en        timestamptz
  eliminado_en     timestamptz
```

**Como se versiona.** La version es una **columna de la misma tabla**, no una tabla aparte:
cada edicion inserta una fila nueva con `version = version_anterior + 1`, y las filas
anteriores se conservan con `activa = false`.

```sql
-- Solo una version activa por plantilla.
create unique index plantillas_version_activa_unico
  on plantillas_extraccion (organizacion_id, coalesce(nombre, ''))
  where activa and eliminado_en is null;
```

> **Una fila por version, no una fila con un JSON de versiones.** Un JSON de versiones
> seria mas compacto, pero no se podria indexar, ni consultar "que analisis usaron la
> version 3" con una consulta simple, ni garantizar en la base que hay una sola version
> activa. Con filas, esas tres cosas salen de un indice unico.

**La plantilla semilla v1.** `[DECIDIDO]` Se siembra en `supabase/seed.sql` con el esquema
generico de la seccion 4, para que el sistema pueda probarse de punta a punta desde la
primera migracion, sin esperar a que el cliente defina sus campos (PP-13).

```sql
insert into plantillas_extraccion (organizacion_id, nombre, version, esquema, instruccion, activa)
values (
  null,
  'Generica v1',
  1,
  '{"type":"object","properties":{"campo_1":{"type":["string","null"],"description":"Primer campo de riesgo"},"campo_2":{"type":["string","null"],"description":"Segundo campo de riesgo"}},"required":[],"additionalProperties":false}'::jsonb,
  'Extrae los campos de riesgo del documento. Si un campo no aparece, dejalo en null. No inventes valores.',
  true
);
```

---

## 7. Camino feliz principal

### 7.1 Consultar la plantilla activa

1. El usuario abre el selector de plantillas, o el pipeline pide la plantilla para
   analizar.
2. El frontend llama a `GET /api/v1/plantillas`.
3. El backend devuelve las plantillas visibles: las de su organizacion y las del sistema.
   Cada una trae su `version` y si esta activa.
4. Para una plantilla concreta, `GET /api/v1/plantillas/{id}` devuelve el esquema y la
   instruccion completos.

### 7.2 Crear una plantilla

1. El administrador abre el editor.
2. Escribe el nombre, la instruccion y el esquema (JSON).
3. El frontend llama a `POST /api/v1/plantillas`.
4. El caso de uso comprueba `plantillas.editar` **en el caso de uso**.
5. El backend valida:
   - que el esquema es JSON valido,
   - que el esquema cae dentro del **subconjunto que admite el motor** (seccion 6 de
     `SKILL.md`): sin `oneOf`, `anyOf`, `allOf`, `if/then/else` ni `patternProperties`,
   - que no hay mas de `max_campos_por_plantilla` campos,
   - que la instruccion no supera `max_longitud_instruccion`.
6. La plantilla se inserta con `version = 1` y `activa = true`.
7. Responde 201 con el recurso.

### 7.3 Editar una plantilla

1. El administrador edita una plantilla existente.
2. El frontend llama a `PUT /api/v1/plantillas/{id}` con el esquema y la instruccion
   nuevos.
3. El backend valida igual que en la creacion.
4. El backend **desactiva** la version activa e **inserta** la version nueva con
   `version = anterior + 1` y `activa = true`, en una transaccion.
5. Los analisis existentes **no se tocan**: siguen apuntando a la version que usaron.
6. Responde 200 con la version nueva.

### 7.4 Activar una version anterior

1. El administrador elige una version anterior y la activa.
2. El backend desactiva la version activa actual y activa la elegida, en una transaccion.
3. El indice unico garantiza que no queden dos activas.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El usuario **no tiene `plantillas.editar`** | 403 | 403 |
| SP-02 | El esquema **no es JSON valido** | 422 con el error de parseo | 422 |
| SP-03 | El esquema usa **`oneOf` u otra construccion no soportada** | 422. Se dice **cual** construccion es el problema, no solo "invalido" | 422 |
| SP-04 | El esquema tiene **mas campos** que el maximo | 422 | 422 |
| SP-05 | La **instruccion es demasiado larga** | 422 | 422 |
| SP-06 | La plantilla es de **otra organizacion** | 404 | 404 |
| SP-07 | Se edita una plantilla **del sistema** (`organizacion_id` nulo) sin ser admin | 403. Las plantillas del sistema no se editan desde la interfaz | 403 |
| SP-08 | Se edita una plantilla que **no existe** | 404 | 404 |
| SP-09 | El **nombre ya existe** en la organizacion | 409. Se puede editar la existente en vez de crear otra | 409 |
| SP-10 | Dos admins **editan a la vez** la misma plantilla | La segunda edicion crea la version sobre la version que existia cuando envio. El indice unico de version activa resuelve el conflicto | 409 |
| SP-11 | La plantilla **no tiene ninguna version activa** | 422 al intentar analizar con ella. El pipeline no elige una version por su cuenta | 422 |
| SP-12 | Se **desactiva** la plantilla que esta en uso | Se permite. Los analisis en curso usan la version que ya tinham en memoria; los nuevos fallan con 422 hasta que se active una version | 200 / 422 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | La plantilla tiene **version 1 y version 3**, sin la 2 | Es valido. Las versiones no tienen que ser consecutivas: si una edicion se revierte, el numero se salta |
| EC-02 | La plantilla del sistema y una de la organizacion tienen **el mismo nombre** | La de la organizacion tiene prioridad en el selector. Se muestra de que organizacion es cada una |
| EC-03 | Se edita una plantilla **usada por 200 analisis** | Los 200 siguen apuntando a la version antigua. Es exactamente el motivo de versionar |
| EC-04 | La **version nueva** tiene menos campos que la anterior | Se permite. Los analisis nuevos traen menos datos, y eso se ve en la comparacion |
| EC-05 | El usuario **no tiene ninguna organizacion** | Solo ve las plantillas del sistema. No puede crear ninguna |
| EC-06 | Se **desactiva** la version activa de una plantilla que es la unica | La plantilla queda sin version activa. El analisis falla con 422 explicito, no con un error generico |
| EC-07 | La plantilla tiene **un solo campo** | Valida igual. No hay minimo imposed por la forma del esquema |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente manda `version = 99` al **crear** | Se ignora. La version la asigna el servidor |
| CE-02 | El cliente manda `activa = true` al **editar** | Se ignora. Editar siempre crea una version activa nueva |
| CE-03 | El cliente manda un esquema con **`{"type": "object"}` y sin `properties`** | Valida. Un esquema vacio es legitimo: significa "extrae lo que pida la instruccion" |
| CE-04 | El cliente manda `organizacion_id` de **otra organizacion** | Se ignora. La organizacion sale del contexto del actor |
| CE-05 | El cliente borra la plantilla con `DELETE` | No hay endpoint de borrado. Se desactiva. Una plantilla con analisis asociados no se borra nunca |
| CE-06 | El cliente manda la **instruccion en otro idioma** | Se acepta. El backend no valida el idioma de la instruccion: es contenido, no codigo |

---

## 10. Criterios de aceptacion

### CA-01: Editar crea una version, no modifica
**Dado** una plantilla en version 3
**Cuando** se edita
**Entonces** existe una version 4
**Y** la version 3 sigue intacta, con su esquema y su instruccion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Un analisis conserva la version que uso
**Dado** un analisis hecho con la version 3
**Cuando** la plantilla pasa a la version 4
**Entonces** el analisis sigue reportando `plantilla_version = 3`
**Y** su resumen no cambia
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: Solo una version esta activa
**Dado** una plantilla con varias versiones
**Cuando** se consulta
**Entonces** exactamente una version tiene `activa = true`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: El esquema se valida antes de guardarse
**Dado** un esquema con `oneOf`
**Cuando** se intenta guardar
**Entonces** la respuesta es 422
**Y** nombra la construccion no soportada
**Y** no se guarda ninguna version
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El permiso se comprueba en el caso de uso
**Dado** un usuario sin `plantillas.editar`
**Cuando** llama a `POST /api/v1/plantillas` por la API
**Entonces** la operacion se deniega aunque el router lo permitiera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Editar es atomico
**Dado** una plantilla con version activa
**Cuando** se edita y la insercion de la version nueva falla
**Entonces** la version anterior sigue activa
**Y** no queda ninguna version a medias
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: Desactivar no rompe los analisis
**Dado** una plantilla con 200 analisis asociados
**Cuando** se desactiva
**Entonces** los 200 analisis siguen consultables y muestran su version
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Sin version activa, el analisis falla con explicacion
**Dado** una plantilla sin version activa
**Cuando** se intenta analizar con ella
**Entonces** la respuesta es 422 y dice que la plantilla no tiene version activa
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: La plantilla semilla existe desde la primera migracion
**Dado** una base recien migrada con la semilla
**Cuando** se listan las plantillas
**Entonces** la plantilla generica v1 esta disponible y activa
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El nombre se unica por organizacion
**Dado** una plantilla llamada "Riesgo v1" en la organizacion
**Cuando** se crea otra con el mismo nombre
**Entonces** la respuesta es 409
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
