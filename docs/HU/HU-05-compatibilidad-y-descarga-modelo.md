# HU-05 — Compatibilidad del equipo y descarga del modelo

## Encabezado

- **HU ID:** `HU-05`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-13 (detectar la capacidad del equipo y explicar cuando el modo navegador no es viable), RF-14 (parcial: el camino alterno no existe en la v1)
- **ADR relacionados:** ADR-06 (LLM en el navegador), ADR-19 (sin modo hospedado en la v1), ADR-08 (tamano de bloque derivado)
- **Bloquea:** HU-07 (analisis)
- **Bloqueado por:** HU-04 (configuracion del motor)

---

## 1. Titulo y descripcion

**Titulo:** HU-05 — Compatibilidad del equipo y descarga del modelo

**Descripcion:** Permitir que cualquier persona use la aplicacion **sin instalar nada**, y
que entienda de antemano si su equipo puede con el trabajo.

Esta historia tiene dos caras. La primera es la **comprobacion de capacidad**: al entrar,
la aplicacion revisa si el navegador soporta WebGPU, cuanto memoria de GPU hay y si el
modelo elegido cabe. Si no cabe, el usuario lo sabe **antes** de elegir un archivo, no
despues de esperar una descarga de 3 GB.

La segunda es la **descarga del modelo**: la primera vez, el navegador baja los pesos
(1.5 a 3 GB) y los guarda en Cache API. A partir de ahi, la aplicacion funciona sin
conexion y sin coste para el proyecto.

**El usuario objetivo es personal administrativo.** Eso obliga a que la descarga se
explique con palabras, no con jerga: que se diga cuanto va a tardar, que se diga que es una
sola vez, y que se pida permiso de forma explicita.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Detectar soporte de WebGPU, memoria de GPU y disponibilidad de almacenamiento persistente |
| 2 | Mostrar un aviso claro, con el motivo y la solucion, cuando el equipo no sirve |
| 3 | Pedir aceptacion explicita antes de descargar el modelo |
| 4 | Descargar el modelo con progreso visible |
| 5 | Persistir el modelo en Cache API / IndexedDB con `navigator.storage.persist()` |
| 6 | Reutilizar el modelo ya descargado en visitas posteriores |
| 7 | Permitir borrar el modelo del equipo |
| 8 | Sugerir el modelo segun la capacidad detectada |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Un modo servidor para quien no tiene WebGPU | Fuera de la v1 (DP-11) |
| 2 | Instalar el modelo fuera del navegador | No aplica: es personal administrativo |
| 3 | Cuotas o limites de descarga | `[PENDIENTE]` |
| 4 | Compartir el modelo entre usuarios del mismo equipo | `[PENDIENTE]` El cache es del navegador |
| 5 | Ejecutar el analisis | HU-07 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-04**: la configuracion dice que modelo se descarga.

### Esta HU BLOQUEA

- **HU-07**: sin modelo en el navegador, no hay analisis.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `MODELO_POR_DEFECTO` | el que sugiera la deteccion | Ver HU-04 |
| `TAMANO_MAXIMO_MODELO_MB` | `3072` | Above del limite de 3 GB |
| `MINIMO_VRAM_MB` | `1024` | Por debajo, se advierte en vez de bloquear |
| `MARGEN_VRAM` | `0.15` | 15% de margen al elegir el modelo |
| `TIMEOUT_DESCARGA_MS` | `600000` | 10 minutos. Si se supera, se cancela y se reintenta |
| `REINTENTOS_DESCARGA` | `2` | Acotados. Un reintento infinito es una descarga infinita |

---

## 5. Suposiciones

1. La deteccion de WebGPU es `navigator.gpu`. Su ausencia significa que **no hay ejecucion
   local en ese navegador**.
2. La VRAM **no es consultable de forma fiable** desde el navegador. La estimacion es
   aproximada: hay que tratarla como una sugerencia, no como un dato.
3. `navigator.storage.persist()` requiere interaccion del usuario. Por eso la aceptacion
   se pide en un boton, no al cargar la pagina.
4. Los pesos del modelo se guardan en **Cache API** (o IndexedDB). **No en cookies**: las
   cookies tienen un limite de 4 KB.
5. El modelo se guarda **en el navegador de ese usuario**. No se reparte entre equipos ni
   entre maquinas.
6. La descarga es **una sola vez**. Despues, el modelo esta disponible sin conexion.
7. Si el navegador no soporta `shader-f16`, algunos modelos no funcionan. La UI lo avisa
   en vez de fallar al descargar.
8. La deteccion de capacidad se hace **al entrar a la aplicacion**, no al elegir el
   archivo: el usuario debe saberlo antes de comprometerse.
9. Un equipo sin WebGPU **queda fuera del producto** en la v1. La aplicacion lo dice con
   claridad y sugiere Chrome o Edge. No hay modo alterno (DP-11).

---

## 6. Modelo de datos

Esta HU **no toca la base de datos**. El estado de la descarga vive en el navegador:

| Almacen | Que guarda |
|---|---|
| Cache API | Los pesos del modelo, por identificador de modelo |
| IndexedDB | Los metadatos de la cache: que modelos hay, cuando se descargaron |
| Store de Pinia | El estado en vivo: descargando, descargado, progreso, error |

**La base de datos no registra descargas.** Es informacion del equipo del usuario, no del
proyecto.

---

## 7. Camino feliz principal

### 7.1 Entrar y comprobar la capacidad

1. El usuario abre la aplicacion.
2. El frontend ejecuta la comprobacion de capacidad:
   - `navigator.gpu` existe
   - adaptador y dispositivo disponibles
   - VRAM estimada, si el navegador la expone
   - `navigator.storage.estimate()` para el espacio disponible
3. La UI guarda el resultado y decide que mostrar:
   - **Compatible:** sigue al panel del motor con el modelo sugerido.
   - **No compatible:** muestra el aviso de la seccion 8, SP-01.

### 7.2 Pedir permiso y descargar

1. El usuario llega al panel del motor y elige el modelo.
2. La UI detecta que el modelo **no** esta en la cache.
3. Aparece un modal: "Para analizar en tu equipo, tu navegador necesita descargar el
   modelo (2.2 GB). Se descarga una sola vez y queda guardado en este equipo. El documento
   nunca sale de tu equipo."
4. El usuario pulsa "Descargar el modelo".
5. La UI llama a `navigator.storage.persist()` **dentro del manejador del clic** (el
   navegador exige interaccion).
6. La UI empieza la descarga con WebLLM y muestra el progreso:

```
Descargando Llama-3.2-3B-Instruct…  43%  (950 MB de 2.2 GB)
Faltan unos 4 minutos
```

7. Al terminar, la UI confirma: "Modelo listo. Quedara guardado en este equipo, no tendras
   que descargarlo otra vez."
8. La UI ofrece "Borrar el modelo" en los ajustes, para quien quiera liberar espacio.

### 7.3 Visitas posteriores

1. El usuario vuelve a abrir la aplicacion.
2. La comprobacion de capacidad encuentra el modelo en la cache.
3. La UI muestra "Modelo listo" y no descarga nada. **La aplicacion funciona sin conexion.**

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El navegador **no soporta WebGPU** | Aviso claro al entrar: "Tu navegador no puede ejecutar el analisis en tu equipo. Usa Chrome o Edge en un computador de escritorio." **No** se permite continuar al analisis | bloqueado en la UI |
| SP-02 | El navegador soporta WebGPU pero el modelo **no cabe** en la VRAM | Aviso con las cifras: "Este modelo necesita 3.4 GB y tu equipo reporta 2.1 GB". Se ofrece uno que si quepa | 200 con advertencia |
| SP-03 | La descarga **falla por red** a mitad | Se cancela, se muestra el error y se ofrece reintentar. La cache parcial se limpia: una cache a medias no sirve | error en la UI |
| SP-04 | La descarga **supera el timeout** (10 min) | Se cancela con un mensaje claro | error en la UI |
| SP-05 | `navigator.storage.persist()` **es denegado** | El modelo se descarga igual, pero **no se garantiza** que sobreviva al cerrar el navegador. La UI lo dice: "Tu navegador no permite guardar el modelo, tendras que descargarlo la proxima vez" | aviso |
| SP-06 | No hay espacio en disco | Se detecta por el error de la descarga. El mensaje dice cuanto se necesita y cuanto hay | error en la UI |
| SP-07 | El modelo en cache **se corrompe** (descarga interrumpida en otra sesion) | WebLLM falla al cargar. La UI detecta que no se puede inicializar, **limpia la cache** y vuelve a descargar | error con auto-recuperacion |
| SP-08 | El navegador pide reiniciar para activar WebGPU | Se muestra el aviso y un enlace a la documentacion del navegador | aviso |
| SP-09 | El usuario **borra el modelo** a mano | La siguiente ejecucion lo vuelve a descargar. Es el comportamiento correcto | descarga normal |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El equipo reporta 0 MB de VRAM | Se trata como "VRAM desconocida": no se bloquea, se sugiere el modelo mas pequeno |
| EC-02 | El navegador expone VRAM pero el valor es una estimacion muy alta | Se aplica el margen del 15%. Es una heuristica, y el modelo puede fallar al ejecutar: la UI lo dice |
| EC-03 | El usuario abre la app en dos pestanas a la vez | Ambas detectan la cache. Si una esta descargando, la otra espera. WebLLM no admite dos motores en el mismo origen a la vez |
| EC-04 | La cache tiene el modelo pero con **otra version** | Se compara el identificador de version. Si no coincide, se vuelve a descargar |
| EC-05 | El dispositivo es un celular con WebGPU | Funciona, pero con 4 GB de RAM la eleccion razonable es el modelo de 1B. La sugerencia lo tiene en cuenta |
| EC-06 | El usuario cambia de modelo | Se descarga el nuevo. **El anterior no se borra automaticamente**: ocupa espacio. La UI lo dice y ofrece limpiarlo |
| EC-07 | La aplicacion se usa sin conexion despues de la primera descarga | Todo el pipeline funciona: extraccion, analisis y guardado local de resultados. Solo falla el envio de los resultados al servidor, que queda en cola |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El usuario pulsa "Descargar" diez veces | El boton se deshabilita mientras descarga. Solo hay una descarga |
| CE-02 | La pestana se cierra a mitad de la descarga | La descarga se cancela. Al volver, la cache parcial se detecta como invalida y se limpia |
| CE-03 | Se navega a otra pagina durante la descarga | La descarga sigue en el Web Worker. El estado se conserva en el store |
| CE-04 | El navegador esta en modo privado | `navigator.storage.persist()` suele denegarse. El modelo se descarga en cada sesion. La UI lo avisa |
| CE-05 | El usuario pide un modelo que no existe en el catalogo de WebLLM | La UI no lo muestra. Si llega por otro lado, la descarga falla con un error claro, no con un error de red |
| CE-06 | El cache esta lleno con otros sitios | El navegador puede descartar la cache por falta de espacio. La UI detecta que el modelo no esta y vuelve a descargar |

---

## 10. Criterios de aceptacion

### CA-01: La capacidad se comprueba antes de elegir archivo
**Dado** un usuario que entra a la aplicacion
**Cuando** se carga la pantalla principal
**Entonces** la comprobacion de WebGPU y de almacenamiento ya ocurrio
**Y** el resultado determina que se muestra
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Sin WebGPU el mensaje es util
**Dado** un navegador sin soporte de WebGPU
**Cuando** el usuario intenta analizar
**Entonces** ve un mensaje que **dice que falta, por que y que hacer**: usar Chrome o Edge
**Y** no ve una pantalla vacia ni un error generico
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: La descarga pide permiso
**Dado** un modelo que no esta en la cache
**Cuando** el usuario llega al panel
**Entonces** ve un modal con el tamano, el tiempo estimado y que es una sola vez
**Y** la descarga **no** empieza hasta que pulsa el boton
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: La persistencia se pide en la interaccion
**Dado** el boton de descarga
**Cuando** el usuario lo pulsa
**Entonces** se llama a `navigator.storage.persist()` **dentro del manejador del clic**
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El progreso es visible
**Dado** una descarga en curso
**Cuando** el usuario mira la pantalla
**Entonces** ve el porcentaje, los bytes descargados y una estimacion de tiempo restante
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: No se usa cookies para el modelo
**Dado** el codigo del frontend
**Cuando** se busca donde se guarda el modelo
**Entonces** se encuentra Cache API o IndexedDB
**Y** **no** hay ninguna escritura en `document.cookie` con pesos del modelo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: La segunda visita no descarga
**Dado** un modelo ya descargado
**Cuando** el usuario vuelve a abrir la aplicacion
**Entonces** no hay descarga y el modelo se inicializa desde la cache
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Un fallo de descarga se limpia
**Dado** una descarga interrumpida
**Cuando** el usuario reintenta
**Entonces** la cache parcial se limpio antes de reintentar
**Y** no hay un error de "modelo corrupto" persistido
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: La VRAM es una sugerencia, no un bloqueo
**Dado** un modelo que no cabe en el equipo
**Cuando** el usuario lo elige
**Entonces** ve el aviso con las cifras
**Y** el guardado de la configuracion **no** falla
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: Se puede liberar espacio
**Dado** un modelo descargado
**Cuando** el usuario pulsa "Borrar el modelo"
**Entonces** la cache se limpia y el espacio se libera
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: Sin conexion, el analisis local funciona
**Dado** un equipo con el modelo ya descargado y sin conexion
**Cuando** el usuario analiza un documento
**Entonces** la extraccion y el analisis se completan
**Y** los resultados quedan en cola para enviarse al servidor cuando vuelva la conexion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
