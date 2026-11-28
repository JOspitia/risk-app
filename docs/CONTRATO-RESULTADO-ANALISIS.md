# El contrato del resultado del analisis

> Que forma tiene un riesgo cuando el analisis lo produce, y por que esa forma se fija
> ahora aunque todavia no exista la fase que la consume.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-28
- **Afecta a:** `ARQUITECTURA.md` seccion 7.4, `SKILL.md` contrato 1.8, `HU-07` seccion 4

---

## 1. El problema que esto resuelve

Hoy `analisis_documentos.riesgos` es un `jsonb` **sin forma definida**. El LLM devuelve
lo que la plantilla pida y el backend lo guarda tal cual.

Eso es comodo mientras la unica cosa que se hace con el resultado es **mostrarlo**. En
cuanto haya que **gestionarlo** —asignarle un responsable, ponerle fecha, aceptarlo o
cerrarlo— aparece un problema: cada documento tiene una forma distinta, porque cada
documento se analizo con una plantilla distinta.

El caso concreto: un analisis hecho con la plantilla A tiene `riesgos` con
`{categoria, severidad, descripcion}` y otro hecho con la plantilla B tiene
`{tipo_riesgo, criticidad, detalle}`. Para poder preguntar "cuales riesgos siguen
abiertos" habria que intersectar dos esquemas que no se conocen. Y el que seأرسل al
servidor en un `jsonb` no tiene donde apoyarse.

**La solucion no es una tabla nueva.** Es un **contrato**: un envoltorio fijo alrededor
de lo que la plantilla define.

---

## 2. El contrato

Cada elemento de `riesgos` es un objeto con esta forma:

```json
{
  "clave": "r-3f9a2c",
  "titulo": "Manejo de credenciales sin cifrar",
  "descripcion": "Las credenciales aparecen en texto plano en la seccion 4.2.",
  "datos": { "categoria": "Seguridad", "severidad": "Alta" },
  "evidencia": { "paginas": [12, 13], "cita": "El sistema almacena las claves en texto plano." },
  "confianza": "alta"
}
```

| Campo | Tipo | Quien lo pone | Que significa |
|---|---|---|---|
| `clave` | `str` | El pipeline | Identificador **estable** del riesgo. Unico dentro del analisis |
| `titulo` | `str` | El pipeline | Nombre corto del riesgo. Es lo que se ve en la lista |
| `descripcion` | `str` | El pipeline | Que ocurre y por que importa |
| `datos` | `dict` | **La plantilla** | Los campos de riesgo que el cliente definio. Aqui vive el `severity`, el `categoria`, el `cvss`… |
| `evidencia` | `dict` | El pipeline | **Donde** esta en el documento. `{paginas: [...], cita: "..."}` |
| `confianza` | `enum` | El pipeline | `alta` \| `media` \| `baja` |

### 2.1 La division clave

> **`datos` es del cliente. Todo lo demas es nuestro.**

Esa es la linea que hace que el contrato sobreviva a que PP-13 se cierre de cualquier
forma. Si mañana el cliente quiere `{categoria, severidad, cvss, responsable}` o
`{tipo_riesgo, criticidad, marco}`, eso vive **dentro de `datos`** y el contrato no
cambia. La plantilla define el contenido; nosotros definimos el envoltorio.

### 2.2 Por que `evidencia` es obligatoria

Un riesgo sin pagina de evidencia **no es verificable**. Es una afirmacion que el
usuario no puede comprobar sin releer el documento entero, y el documento entero es lo
que el usuario todavia no ha leido: por eso subio el PDF.

La `cita` es el fragmento literal que sustenta el riesgo. Sin ella, el resumen ejecutivo
es una afirmacion sin respaldo; con ella, el usuario puede ir a la pagina y ver el
texto. Es tambien lo que hace util el hallazgo mas adelante: una conversacion de
seguimiento puede citarlo.

`paginas` es una lista porque un riesgo puede aparecer en mas de un bloque: el
solapamiento de 1 pagina hace que un dato en el limite entre dos bloques se vea dos
veces, y las dos apariciones deben mapear al mismo `clave`.

### 2.3 Por que `confianza`

El LLM no tiene certeza, y el usuario no puede saber cuanto. Un campo de confianza
**distingue un hallazgo solido de uno dudoso**, que es justo lo que un gestor de riesgos
necesita: se prioriza lo confiado, y lo dudoso se revisa.

No es un adorno. Es lo que separa "el modelo dice que hay un riesgo" de "el modelo
**no esta seguro** de que haya un riesgo". Sin el, todo pesa igual.

---

## 3. La `clave` estable

Cada riesgo lleva una clave que **no cambia** entre analisis del mismo documento.

**Como se genera.** En la fase Map, cada bloque produce sus riesgos con una clave
local. En el Reduce, un riesgo que aparece en varios bloques **conserva la clave del
primer bloque donde aparece**. Un riesgo que solo aparece en un bloque conserva la suya.

**Para que sirve.** Tres cosas, todas de la fase 2:

1. **Comparar analisis.** HU-10 (reanalisis) puede decir "el riesgo `r-3f9a2c` sigue
   abierto y `r-7b1e04` desaparecio" en vez de comparar dos JSONB completos. Es la
   diferencia entre un diff legible y un diff de texto.
2. **Referenciar un riesgo.** Un correo, un comentario o una conversacion puede
   apuntar a un riesgo concreto. Sin clave, no hay a que apuntar.
3. **Anotar el historial.** El historial del prototipo (que es append-only) se
   referencia por clave.

**Lo que NO es la clave.** No es un codigo de negocio tipo `F-001`. Es un identificador
opaco generado por el pipeline. El codigo de negocio es un campo **de negocio**, que
depende del cliente, y por eso va en `datos` (o se asigna en la fase de gestion), no en
el envoltorio.

> **La clave no es estable entre documentos.** Solo dentro de un analisis. Comparar
> riesgos entre dos documentos distintos no tiene sentido sin un identificador de
> negocio, y ese es un problema de la fase 2.

---

## 4. Lo que esto NO decide

Este documento **no** introduce la fase de gestion. No dice que los riesgos tengan
estado, ni responsable, ni fecha de vencimiento. Esas son las preguntas de **PP-15**, y
dependen del cliente.

Lo que si hace es dejar el terreno preparado:

| Si en la fase 2 se decide... | Este contrato ya tiene... |
|---|---|
| Un estado por riesgo | La `clave` para colgarlo |
| Un responsable | El lugar natural es `datos` (lo define el cliente) o un campo propio si se decide |
| Una fecha objetivo | El lugar natural es `datos` o un campo propio |
| Una decision de aceptacion con vencimiento | La `clave` y la `evidencia` que la sustenta |
| Un historial append-only | La `clave` que lo referencia |

**Sin esto, la fase 2 arranca con una migracion** sobre documentos ya analizados,
convirtiendo `jsonb` libre en filas identificables. Con esto, arranca con un
`INSERT` sobre lo que ya esta.

---

## 5. Como se valida en el backend

El backend ya valida el resultado contra la plantilla. Ahora validara **ademas** el
envoltorio:

1. Cada elemento de `riesgos` tiene `clave`, `titulo`, `descripcion`, `datos`,
   `evidencia` y `confianza`.
2. Las `clave` son **unicas** dentro del analisis. Una repetida es 422: significaria
   que el Reduce no consolido dos riesgos que son el mismo.
3. `evidencia.paginas` son paginas que existen en el documento y que **estan cubiertas**
   por algun bloque del analisis. Una pagina fuera de rango es 422.
4. `confianza` es uno de los tres valores permitidos.
5. `datos` cumple el esquema de la plantilla (lo que ya se validaba).

> **La validacion es en el backend, no en el cliente.** El cliente no es una frontera de
> confianza. El mismo criterio que aplica a la salida del LLM aplica aqui.

---

## 6. Que queda pendiente de responder

| Pregunta | Donde |
|---|---|
| Que campos de riesgo concretos quiere el cliente | **PP-13** |
| Si el resultado tiene ciclo de vida o es solo consulta | **PP-15** |
| Que campos de la plantilla van en `datos` y cuales en el envoltorio | **PP-13**, con este documento como guia |

Todo lo demas de la fase de gestion (estados, correos, exportacion) queda **fuera**
hasta que PP-15 se cierre.

---

## 7. Trazabilidad

- **HU-07** (analisis del documento): produce el resultado que este contrato define.
- **HU-09** (consulta de resultados): lo expone.
- **HU-10** (reanalisis): lo compara, y gana con la `clave` estable.
- **ADR-15** (artefacto JSON): define el formato del resultado.
- **PP-13, PP-15**: las dos preguntas abiertas que este documento deja mas precisas.
- **Analisis de referencia**: `docs/ANALISIS-REFERENCIA-VULNERABILITY-TRACKER.md`, que
  mostro la forma que tiene un resultado cuando alguien lo gestiona despues.
