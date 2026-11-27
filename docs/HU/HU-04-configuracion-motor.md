# HU-04 — Configuracion del motor IA

## Encabezado

- **HU ID:** `HU-04`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-02 (configurar el motor por usuario u organizacion), RF-20 (elegir y configurar el modelo desde un panel)
- **ADR relacionados:** ADR-16 (modelo por defecto y panel), ADR-08 (tamano de bloque derivado), ADR-06 (motor en el navegador)
- **Bloquea:** HU-05 (compatibilidad y descarga), HU-07 (analisis)
- **Bloqueado por:** HU-01 (sesion), HU-02 (permisos)

---

## 1. Titulo y descripcion

**Titulo:** HU-04 — Configuracion del motor IA

**Descripcion:** Permitir que cada persona, antes de analizar un documento, **elija con que
modelo se va a trabajar y ajuste sus parametros**, y que esa eleccion se guarde para que no
tenga que repetirla.

La configuracion tiene dos ambitos: **por usuario** (mi preferencia) y **por organizacion**
(la politica del equipo). Cuando existen las dos, manda la del usuario: es el caso tipico de
"en mi equipo analizamos con X, pero yo prefiero usar Y".

Los parametros que el usuario controla son el modelo, el tamano de bloque, el solapamiento,
la ventana de contexto, la temperatura y el modo de ejecucion.

**El tamano de bloque no se escribe a mano.** Es un valor **derivado** de la ventana de
contexto del modelo, y la interfaz lo muestra como tal. Un usuario que escribe "10 paginas"
en un modelo de 4K produce un error silencioso que se manifesta como "el modelo devuelve
basura".

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Ver la configuracion efectiva del motor (usuario + organizacion + defaults) |
| 2 | Guardar la configuracion por usuario |
| 3 | Guardar la configuracion por organizacion (permiso `configuracion.editar`) |
| 4 | Elegir el modelo de una lista de los disponibles en el navegador |
| 5 | Ver el tamano de bloque derivado y el motivo |
| 6 | Ajustar temperatura, ventana de contexto y solapamiento |
| 7 | Detectar la capacidad del equipo y sugerir un modelo |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Descargar el modelo al equipo | HU-05 |
| 2 | Ejecutar un analisis con la configuracion | HU-07 |
| 3 | Configuracion del servidor de modelos | Fuera de alcance (no hay en la v1) |
| 4 | Perfiles de configuracion guardados con nombre | `[PENDIENTE]` |
| 5 | Ajuste de la plantilla de extraccion | HU-09 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion): la configuracion es por usuario autenticado.
- **HU-02** (permisos): `configuracion.editar` distingue el ambito de organizacion.

### Esta HU BLOQUEA

- **HU-05**: la configuracion decide que modelo se descarga.
- **HU-07**: el analisis usa estos parametros.

---

## 4. Variables y configuracion

### Parametros por modelo

La configuracion guarda el **modelo**, y el resto de parametros por defecto se derivan de el.
El catalogo de modelos vive en el frontend (son los de WebLLM), pero **el backend valida**
que el modelo enviado exista.

| Modelo | VRAM estimada | Ventana | Notas |
|---|---|---|---|
| `gemma3-1b-it-q4f16_1-MLC` | 711 MB | 4K | La mas ligera |
| `Llama-3.2-1B-Instruct-q4f16_1-MLC` | 879 MB | 4K | Equipos con poca VRAM |
| `Qwen3-1.7B-q4f16_1-MLC` | 2.0 GB | 4K | Modo thinking: no recomendado para extraccion |
| `Llama-3.2-3B-Instruct-q4f16_1-MLC` | 2.2 GB | 4K | Buen equilibrio |
| `Phi-4-mini-instruct-q4f16_1-MLC` | 3.4 GB | 4K | Fuerte en extraccion estructurada |
| `gemma-4-E2B-it-q4f16_1-MLC` | 3.3 GB | 4K | Requiere `shader-f16` |

### Parametros editables

| Parametro | Default | Rango | Nota |
|---|---|---|---|
| `modelo` | el que sugiera la deteccion | catalogo | |
| `modo_ejecucion` | `navegador_local` | `navegador_local` | En la v1 es el unico valor |
| `ventana_contexto` | la del modelo | 2048 a la del modelo | Verificable contra el modelo |
| `tamano_chunk_paginas` | **derivado** | 1 a 20 | **Calculado, no libre** |
| `overlap_paginas` | 1 | 0 a `tamano_chunk_paginas - 1` | Consume ventana |
| `temperatura` | 0.10 | 0.0 a 1.0 | Baja para analisis de riesgos |

### Variables de entorno

| Variable | Default | Nota |
|---|---|---|
| `MODELOS_DISPONIBLES` | catalogo de WebLLM | Permite recortarlo en equipos restringidos |
| `MAX_TEMPERATURA` | `1.0` | Tope del slider |

---

## 5. Suposiciones

1. La configuracion por **usuario** pisa a la de **organizacion**, que a su vez pisa a los
   defaults del sistema. La precedencia es: `usuario > organizacion > default`.
2. `tamano_chunk_paginas` **se calcula**, no se escribe. La interfaz lo muestra como
   resultado. Si se expone un campo editable, es una decision pendiente, no un default.
3. `tokens_por_pagina` (~600 a 900) es una **estimacion** que se calibra con documentos
   reales. `[PENDIENTE]` Medir con el PDF de referencia.
4. La **ventana de contexto pertenece al modelo**. Cambiar de modelo cambia la ventana, y
   con ella el tamano de bloque derivado.
5. La **temperatura baja** (0.1) es el default para analisis de riesgos: el LLM debe
   extraer, no inventar.
6. Los modelos con **modo thinking** (Qwen3, Qwen3.5) generan tokens de razonamiento que
   consumen ventana y ralentizan la extraccion sin aportar a un esquema fijo. La interfaz
   advierte de eso en vez de esconderlo.
7. El **ambito de organizacion** lo edita quien tenga `configuracion.editar` y ese permiso
   aplica al ambito de organizacion, no al personal.
8. La configuracion se aplica **sin redesplegar**: vive en la base y se lee en cada
   peticion.
9. La deteccion de capacidad es una **sugerencia**, no una imposicion: el usuario puede
   elegir otro modelo. `[PROPUESTO]` Salvo que el equipo no lo soporte en absoluto, en cuyo
   caso el modelo elegido no se puede descargar y la UI lo explica.

---

## 6. Modelo de datos

La tabla ya existe en el modelo: `configuracion_motor`.

```
id                   uuid primary key default gen_random_uuid()
usuario_id           uuid references auth.users(id) on delete cascade
organizacion_id      uuid references organizaciones(id)
ambito               text not null       -- usuario | organizacion
modelo               text not null
modo_ejecucion       text not null       -- navegador_local | servidor_python
tamano_chunk_paginas int not null default 3
overlap_paginas      int not null default 1
ventana_contexto     int not null default 4096
temperatura          numeric(3,2) not null default 0.10
updated_at           timestamptz not null default now()
```

**Restriccion:** exactamente un ambito por fila. Una fila de ambito `usuario` tiene
`usuario_id` y no `organizacion_id`; una de ambito `organizacion`, al reves. Verificado en
`CHECK`.

**Indice unico parcial por usuario:**

```sql
create unique index configuracion_motor_usuario_unico
  on configuracion_motor (usuario_id)
  where ambito = 'usuario';

create unique index configuracion_motor_organizacion_unico
  on configuracion_motor (organizacion_id)
  where ambito = 'organizacion';
```

Un usuario no puede tener dos configuraciones personales: la segunda escritura actualiza la
primera.

---

## 7. Camino feliz principal

### 7.1 Abrir el panel

1. El usuario entra a "Ajustes del Motor IA".
2. La UI llama a `GET /api/v1/configuracion/motor`.
3. El backend resuelve la configuracion efectiva aplicando la precedencia
   `usuario > organizacion > default`.
4. Responde con la configuracion **y con su origen**:

```json
{
  "success": true,
  "message": "OK",
  "data": {
    "modelo": "Phi-4-mini-instruct-q4f16_1-MLC",
    "origen_modelo": "usuario",
    "modo_ejecucion": "navegador_local",
    "ventana_contexto": 4096,
    "tamano_chunk_paginas": 3,
    "tamano_chunk_paginas_calculado": true,
    "overlap_paginas": 1,
    "temperatura": 0.10,
    "modelo_sugerido": "Llama-3.2-3B-Instruct-q4f16_1-MLC",
    "puede_usar_sugerido": false
  },
  "errors": null,
  "timestamp": "2026-11-27T14:00:00Z"
}
```

5. La UI muestra el selector de modelo, los deslizadores y el valor derivado del bloque.

### 7.2 Cambiar el modelo

1. El usuario elige otro modelo en el selector.
2. La UI **recalcula en el momento** el tamano de bloque derivado y lo muestra: "Con este
   modelo: 3 paginas por bloque".
3. La UI avisa si el modelo no cabe en el equipo: "Este modelo necesita 3.4 GB de VRAM y tu
   equipo reporta 2.1 GB. Puedes intentarlo, pero es probable que falle."
4. El usuario guarda.
5. La UI llama a `PUT /api/v1/configuracion/motor`.
6. El backend valida el modelo contra el catalogo, valida los rangos, **recalcula** el
   tamano de bloque y guarda.
7. Responde 200 con la configuracion efectiva.

### 7.3 Guardar la configuracion de la organizacion

1. Un usuario con `configuracion.editar` elige el ambito "Organizacion" en el panel.
2. Los cambios afectan a todos los miembros de la organizacion.
3. La UI pide confirmacion explicita antes de guardar.
4. El backend comprueba el permiso, guarda la fila de ambito `organizacion` y registra el
   cambio en auditoria: **que parametro, que valor anterior, que valor nuevo, quien**.

### 7.4 Sugerencia automatica

1. El usuario entra por primera vez.
2. El frontend detecta la capacidad del equipo (`navigator.gpu`, memoria de la GPU cuando el
   navegador la expone).
3. Compara con la VRAM estimada de cada modelo del catalogo.
4. Propone el mayor modelo que quepa con margen.
5. La sugerencia **no se aplica sola**: se muestra como sugerencia, y el usuario decide.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El actor no tiene `configuracion.editar` | No puede guardar en ambito organizacion. En ambito usuario si puede | 403 |
| SP-02 | El modelo enviado no existe en el catalogo | 422. **No** se guarda nada | 422 |
| SP-03 | El modelo existe pero no cabe en el equipo | Se guarda con una advertencia visible. **No** es un error: la deteccion de VRAM del navegador es aproximada | 200 |
| SP-04 | `temperatura` fuera de rango | 422 | 422 |
| SP-05 | `overlap_paginas` mayor o igual que `tamano_chunk_paginas` | 422. El chunking fallaria en tiempo de ejecucion | 422 |
| SP-06 | `ventana_contexto` mayor que la del modelo | 422. El modelo no puede responder con una ventana que no tiene | 422 |
| SP-07 | El usuario no tiene ninguna configuracion guardada | Se devuelven los defaults con `origen_modelo = default` | 200 |
| SP-08 | El modelo del catalogo fue retirado en una version nueva | El backend lo rechaza al guardar, pero la configuracion guardada sigue **válida para leer**. Se marca como `no_disponible` en la respuesta | 200 / 422 |
| SP-09 | El usuario pertenece a dos organizaciones | Se usa la organizacion del contexto activo (PP-01) | 200 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El modelo elegido tiene ventana de 4K y el bloque calculado es 1 pagina | Es valido. Con documentos muy densos es lo correcto |
| EC-02 | El solapamiento es 0 | Se permite. Sin solapamiento, un riesgo que cae justo en el corte entre bloques puede perderse. La UI lo advierte |
| EC-03 | La temperatura es 0 | Se permite. Es el valor mas conservador para extraccion |
| EC-04 | El equipo no reporta VRAM (el navegador no la expone) | No se puede calcular el modelo sugerido. Se ofrece el default y se pide elegir a mano |
| EC-05 | El usuario tiene configuracion de usuario y de organizacion con modelos distintos | Manda la del usuario. La respuesta dice de donde sale cada valor (`origen_modelo`) |
| EC-06 | El usuario borra su configuracion personal | Vuelve a aplicar la de organizacion. El borrado es explicito, no un fallback silencioso |
| EC-07 | La organizacion cambia su modelo por defecto | Afecta a los usuarios sin configuracion personal. Los que tienen la suya no se mueven |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente envia `tamano_chunk_paginas: 10` con un modelo de 4K | Se **ignora** el valor y se recalcula. Un valor que no cabe en la ventana es la causa del error mas dificil de diagnosticar del sistema |
| CE-02 | El cliente envia `ventana_contexto: 200000` con un modelo de 4K | 422 |
| CE-03 | El cliente envia `modelo: "../../etc/passwd"` | 422. El modelo se valida contra una lista cerrada, no se interpola en nada |
| CE-04 | El cliente envia `ambito: "organizacion"` sin ser admin | 403. El ambito lo decide el permiso, no el cuerpo |
| CE-05 | El cliente envie `usuario_id` de otra persona | Se ignora. La configuracion se guarda para el actor |
| CE-06 | El cliente envie `temperatura: "alta"` | 422. Es un numero, no una palabra |
| CE-07 | `overlap_paginas` negativo | 422 |
| CE-08 | El cliente envie `modo_ejecucion: "servidor_python"` | 422 en la v1. No hay servidor de modelos, asi que ese valor no describe nada real |

---

## 10. Criterios de aceptacion

### CA-01: La configuracion efectiva
**Dado** un usuario con configuracion de usuario y de organizacion
**Cuando** pide `GET /api/v1/configuracion/motor`
**Entonces** responde 200 con la configuracion de usuario aplicada
**Y** el campo `origen_modelo` dice de donde sale cada valor
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: El tamano de bloque se calcula, no se escribe
**Dado** un modelo con ventana de 4K
**Cuando** se guarda la configuracion
**Entonces** el `tamano_chunk_paginas` guardado es el derivado, **no** el que envio el
cliente
**Y** el backend rechaza con 422 un `ventana_contexto` incompatible con el modelo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: El modelo se valida contra el catalogo
**Dado** un modelo inexistente
**Cuando** se guarda la configuracion
**Entonces** responde 422 y no se guarda nada
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: La precedencia es correcta
**Dado** un usuario con configuracion propia y otra de su organizacion
**Cuando** borra su configuracion personal
**Entonces** la siguiente lectura devuelve la de organizacion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El ambito de organizacion exige permiso
**Dado** un usuario sin `configuracion.editar`
**Cuando** intenta guardar en ambito organizacion
**Entonces** responde 403
**Y** su configuracion personal **no** se ve afectada
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: La sugerencia no se aplica sola
**Dado** un usuario nuevo
**Cuando** entra por primera vez
**Entonces** el sistema propone un modelo segun la capacidad del equipo
**Y** **no** guarda ese modelo sin que el usuario lo confirme
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: La deteccion de VRAM es una sugerencia
**Dado** un modelo que no cabe en el equipo
**Cuando** se elige
**Entonces** la UI advierte con la cifra concreta
**Y** el guardado **no** falla
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Sin configuracion hay defaults
**Dado** un usuario sin ninguna configuracion
**Cuando** pide la configuracion
**Entonces** responde 200 con los defaults y `origen_modelo = default`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: Aplicar sin redesplegar
**Dado** una configuracion guardada
**Cuando** el usuario la cambia
**Entonces** el siguiente analisis usa los valores nuevos, sin reiniciar nada
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El cambio de organizacion queda auditado
**Dado** un cambio de modelo a nivel de organizacion
**Cuando** se consulta la bitacora
**Entonces** hay una entrada con el parametro, el valor anterior, el valor nuevo y el actor
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: El modo servidor no existe en la v1
**Dado** un cliente que envia `modo_ejecucion = servidor_python`
**Cuando** se guarda la configuracion
**Entonces** responde 422
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
