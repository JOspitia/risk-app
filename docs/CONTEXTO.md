# Contexto de producto — Risk-app

> Que hace el sistema, para quien y con que restricciones. Este documento define el
> **producto**. Las decisiones tecnicas (stack, arquitectura, estructura de carpetas)
> viven en [ARQUITECTURA.md](ARQUITECTURA.md). Lo que aun no esta definido vive en
> [DECISIONES-PENDIENTES.md](DECISIONES-PENDIENTES.md).

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-27
- **Origen:** consolidado de `docs/legacy/arquitectura-proyecto-analisis-documental.ORIGINAL.md`

---

## Convenciones de estado

Toda afirmacion relevante lleva una marca. No hay afirmaciones sin marcar en este documento.

| Marca | Significado |
|---|---|
| `[DECIDIDO]` | Cerrado. Se implementa asi. Cambiarlo exige un ADR en `ARQUITECTURA.md`. |
| `[PROPUESTO]` | Recomendacion tecnica del equipo, pendiente de ratificacion por el usuario. |
| `[ABIERTO]` | Sin definicion. Bloquea trabajo hasta cerrarse. |

---

## 1. Que es

`[DECIDIDO]` Plataforma web para **cargar documentos privados extensos** (del orden de 100
paginas), limpiar su contenido (ETL), extraer informacion estructurada mediante un LLM y
almacenar los registros resultantes en una base de datos centralizada, de modo que usuarios
autorizados puedan consultarlos y compartirlos desde cualquier navegador.

El dominio de aplicacion es el **analisis de riesgos documental**: el sistema no solo extrae
datos, los interpreta como riesgos y produce un resumen ejecutivo por documento.

### 1.1 Que NO es

- No es un CRM ni un gestor documental con almacen de largo plazo. El PDF es insumo de
  analisis, no el activo a preservar. `[DECIDIDO]`
- No es un sistema multi-tenant comercial. Hay una organizacion por equipo, no un modelo de
  tenants con facturacion. `[PROPUESTO]`
- No envia documentos a APIs de terceros. Ver seccion 3.

---

## 2. Usuarios y escala

| Atributo | Valor | Estado |
|---|---|---|
| Numero de usuarios | ~200 | `[PROPUESTO]` estimada, sin confirmar |
| Concurrencia | Moderada, no todos simultaneos al mismo segundo | `[DECIDIDO]` |
| Perfiles de acceso | Administrador, Analista de Riesgos, Auditor | `[DECIDIDO]` |
| Unidad de comparticion | Equipo / area (organizacion) | `[PROPUESTO]` la politica exacta sigue abierta (DP-04) |
| Identidad | Supabase Auth | `[DECIDIDO]` ADR-05 |

---

## 3. Requisito critico: privacidad

`[DECIDIDO]` **El archivo original y su texto confidencial no deben enviarse a APIs publicas
de terceros** (OpenAI, Anthropic, Gemini u otra equivalente). El LLM que procesa los
documentos debe ejecutarse en un entorno bajo control del proyecto.

`[DECIDIDO]` En la version 1, **el ETL y el LLM corren en el navegador** y al servidor solo
llegan los resultados ya extraidos. El documento no se procesa en ningun servidor: no hay
llamada a ninguna API de terceros, ni propia ni ajena.

`[DECIDIDO]` **Excepcion: el archivo se archiva.** El documento se sube a almacenamiento
privado bajo control del proyecto (Supabase Storage, bucket privado, RLS, URL firmadas de
vida corta) para poder volver a el mas adelante. Eso no cambia **donde** se analiza el
documento, pero si cambia **que el archivo sale del equipo del usuario**.

**El requisito critico, en su forma final:** el archivo original y su texto confidencial no
se envian a APIs publicas de terceros, y el unico sitio donde pueden estar es la
infraestructura del propio proyecto, con control de acceso por permisos, cifrado en reposo,
URL firmadas de corta duracion y borrado a peticion. El analisis ocurre en el equipo del
usuario, no en ningun servidor.

`[DECIDIDO]` **Que el motor sea reemplazable es una decision de construccion, no una
permision.** Si el cliente tiene un contrato con un proveedor de modelos (Anthropic,
OpenAI u otro), se puede conectar. Pero activarlo **cambia la postura de privacidad del
producto**, asi que:

- **No es un default.** El sistema arranca con el motor local.
- **Requiere un ADR propio** que registre que proveedor, que datos salen y quien lo aprobo.
- **No se mezcla en silencio**: el modo de ejecucion se elige y se le muestra al usuario.

Lo mismo aplica al almacenamiento: si el cliente tiene su propio S3 o su propio SFTP, se
conecta como un adaptador mas. El sistema esta construido para que esas decisiones del
cliente sean **un archivo nuevo, no un proyecto nuevo**. El detalle esta en
[ARQUITECTURA.md](ARQUITECTURA.md#95-perfil-de-despliegue-la-demo-gratuita).

Consecuencias tecnicas que se arrastran al codigo:

- La llamada al LLM es un **puerto de salida** del dominio y su unica implementacion permitida
  apunta a un motor local.
- No se instrumenta ningun cliente HTTP de terceros en las rutas que tocan texto del
  documento.
- El archivo se guarda en un **bucket privado**, nunca en un bucket publico. El acceso pasa
  por una URL firmada de vida corta, emitida por el backend solo si el permiso existe.
- El borrado del documento elimina tambien el archivo. Un soft delete en la base de datos
  sin borrar el objeto deja un PDF vivo que la interfaz ya no muestra: eso es una fuga.

---

## 4. Flujo funcional

`[DECIDIDO]` El flujo principal ocurre **en el navegador del usuario**. El servidor recibe
unicamente resultados ya extraidos y validados.

```
[Usuario autenticado]
   |
   v
1. Configura el motor IA (modelo, tamano de bloque, overlap, ventana, temperatura, modo)
   |
   v
2. Acepta el aviso de descarga del modelo (Cache API / IndexedDB)
   |
   v
3. Selecciona el PDF privado desde su equipo
   |
   v
4. ETL en el navegador (Web Worker): pdf.js extrae el texto y se divide en bloques
   |
   v
5. Fase Map: cada bloque se analiza por separado -> JSON estructurado + resumen parcial
   |
   v
6. Fase Reduce: los resumenes parciales se consolidan -> resumen ejecutivo del documento
   |
   v
7. El frontend envia los resultados a la API, que los valida y los persiste por lotes
   |
   v
[Otros usuarios autorizados consultan y comparten los resultados]
```

> **El PDF nunca pasa por la API.** No se sube al servidor en el camino principal: sube
> directo del navegador al almacenamiento privado, y el servidor guarda metadatos del
> documento y los resultados extraidos, nunca el archivo ni su texto. El unico lugar donde
> el archivo esta es el almacenamiento privado del proyecto (ADR-20).

### 4.1 Mapa-Reduce sobre bloques

`[DECIDIDO]` El documento se divide en bloques y el patron es **Map-Reduce**:

- **Map.** Cada bloque se procesa de forma independiente y produce un resumen parcial de
  riesgos. La independencia evita saturar la ventana de contexto y la memoria del motor.
- **Reduce.** Los resumenes parciales se consolidan para producir el resumen ejecutivo del
  documento completo.

`[DECIDIDO]` **El Reduce es jerarquico.** Con el tamano de bloque por defecto, un documento
de 100 paginas produce alrededor de 50 resumenes parciales, que no caben en la ventana de
contexto de un modelo de navegador. Se agrupan en lotes que quepan, se reduce cada lote, y
se reducen los resultados intermedios. Para documentos de hasta ~200 paginas cabe en dos
niveles.

### 4.2 Campos dinamicos

`[DECIDIDO]` En lugar de columnas rigidas por cada riesgo, los campos extraidos viven en
columnas **JSONB**, gobernados por una tabla de plantillas de extraccion. Hoy la plantilla
tiene una instruccion ("Generar resumen ejecutivo de riesgos"); manana se agregan preguntas
o campos nuevos desde la consola **sin tocar codigo ni migrar la base de datos**.

### 4.3 Consola de configuracion del motor IA

`[DECIDIDO]` El usuario ve una pantalla de "Ajustes del Motor IA" con deslizadores y
selectores que actualizan la configuracion antes de lanzar el analisis. La configuracion
tiene ambito por usuario o por organizacion.

| Parametro | Valor por defecto | Nota |
|---|---|---|
| `modelo` | a definir (DP-11) | Depende de la capacidad del equipo del usuario |
| `modo_ejecucion` | `navegador_local` | `[DECIDIDO]` ADR-06 |
| `tamano_chunk_paginas` | **3** | `[DECIDIDO]` Se deriva de la ventana de contexto, ver seccion 5.5 |
| `overlap_paginas` | 1 | Consume ventana: se resta antes de dividir |
| `ventana_contexto` | 4096 | La de los modelos de navegador por defecto |
| `temperatura` | 0.1 | Baja, para analisis de riesgos |

---

## 5. El motor LLM

### 5.1 Camino principal: en el navegador del usuario

`[DECIDIDO]` El equipo del usuario actua como servidor de IA. Tras consentimiento explicito y
almacenamiento persistente (`Cache API` / `IndexedDB`), el navegador descarga el modelo una
vez y ejecuta todo el ETL y el analisis con su GPU o CPU local.

- **A favor:** privacidad maxima (el documento nunca sale del equipo), costo cero de GPU en
  la nube, escalabilidad gratuita, encaja con el despliegue en Vercel sin servidor de
  proceso largo.
- **En contra:** depende del hardware del cliente, primera carga pesada (1.5 GB a 3 GB),
  requiere WebGPU.

`[DECIDIDO]` **El usuario objetivo es personal administrativo sin conocimiento tecnico.**
Esa condicion pone una barra alta a este camino: la descarga del modelo tiene que ser un
proceso guiado, con explicacion de que esta pasando y por que, y el sistema tiene que
detectar la capacidad del equipo y **sugerir** el modelo que cabe. Un administrador que
tiene que decidir entre "Qwen3 1.7B" y "Phi-4-mini" ya esta resolviendo un problema que
es del sistema, no suyo.

### 5.1.1 Roles y permisos

`[DECIDIDO]` El sistema tiene un **sistema de roles y permisos** cuyo proposito es
determinar **que informacion puede ver cada usuario que ingresa**. No basta con el inicio
de sesion: un usuario autenticado puede no tener derecho a ver un analisis, a compartir un
documento, a ver la bitacora o a administrar usuarios.

La matriz de permisos vive en datos, no en el codigo, para que agregar un permiso no
requiera un redespliegue. Roles iniciales: `admin`, `analista`, `auditor`. El detalle esta
en [ARQUITECTURA.md](ARQUITECTURA.md#55-roles-permisos-y-creacion-de-usuarios).

La creacion de usuarios tambien es parte del alcance: un administrador crea cuentas,
asigna rol y organizacion, y desactiva usuarios, todo desde la aplicacion.

### 5.2 Cobertura de WebGPU (dato verificado el 2026-11-27)

`[DECIDIDO]` WebGPU esta disponible por defecto en los tres motores principales, pero **no
en todas las plataformas**. Cobertura global estimada: **~88.6%** (86.83% completa +
1.8% parcial, dato de caniuse de octubre de 2026).

| Navegador | Desde | Plataformas con WebGPU por defecto |
|---|---|---|
| Chrome / Edge | 113 | Windows, macOS, ChromeOS. Android 121+ |
| Firefox | 141 | Windows. macOS solo en Apple Silicon (145+). **No en Linux, ni en Intel Macs, ni en Android** |
| Safari | 26 | macOS Tahoe 26, iOS 26, iPadOS 26. **No en macOS 15 ni anteriores** |
| Estado del estandar | W3C Candidate Recommendation (borrador de septiembre de 2026) | |

`[PROPUESTO]` El ~11% restante (Firefox en Linux o Intel Mac, Safari en macOS anterior,
dispositivos Android antiguos) necesita un camino alterno. Es el origen del modo servidor
de la v2 y de DP-12.

### 5.3 Camino alterno: modelo hospedado por el proyecto — NO ESTA EN LA v1

`[DECIDIDO]` **DP-11 cerro en solo navegador.** El proyecto **no** hospeda el modelo.

El motivo declarado: el usuario es personal administrativo y no va a instalar un LLM ni a
tener una GPU que dimensionar. El modelo se descarga al equipo desde el navegador, que es
la unica forma en que no requiere ninguna intervencion tecnica del usuario.

**Consecuencias de la decision, que hay que tener presentes:**

- La v1 **no necesita** servidor de modelos, ni GPU, ni memoria dedicada, ni worker con ETL
  en Python, ni cola en el servidor. Todo cabe en Vercel (frontend + API) y Supabase
  (datos). El costo de operacion es practicamente cero.
- **Quien no tenga WebGPU no puede usar la aplicacion.** La cobertura global es de ~88.6%.
  Los huecos: Firefox en Linux, en Macs Intel y en Android; Safari en macOS 15 y
  anteriores; Chrome en Linux sin GPU compatible. Ese ~11% queda fuera, y la aplicacion
  debe decirlo de forma explicita y sugerir Chrome o Edge, no fallar en silencio.
- **La primera vez, el usuario descarga 1.5 a 3 GB.** Ese es el punto de friccion real del
  producto, no la instalacion tecnica: el usuario administrativo tiene que entender que esta
  descargando un modelo, cuanto lleva, y que se queda guardado en su equipo para las
  siguientes veces. De ahi que la interfaz de descarga deba explicar, mostrar el progreso y
  confirmar la persistencia.
- El modo hospedado queda **documentado y no construido**, con el contrato de `trabajo`
  preparado para que anadirlo no toque los casos de uso.

### 5.4 Modelos candidatos para el navegador

`[DECIDIDO]` Se usan los modelos precompilados de WebLLM (`@mlc-ai/web-llm`), cuantizados a
4 bits. VRAM estimada segun la lista oficial de MLC (verificada el 2026-11-27):

| Modelo | VRAM estimada | Contexto | Nota |
|---|---|---|---|
| `gemma3-1b-it-q4f16_1-MLC` | 711 MB | 4K | La mas ligera con capacidad util |
| `Llama-3.2-1B-Instruct-q4f16_1-MLC` | 879 MB | 4K | Equipos con muy poca VRAM |
| `Qwen3-0.6B-q4f16_1-MLC` | 1.4 GB | 4K | Modo thinking: genera tokens extra, no recomendado para extraccion estricta |
| `Qwen3.5-0.8B-q4f16_1-MLC` | 1.6 GB | 4K | |
| `Qwen3-1.7B-q4f16_1-MLC` | 2.0 GB | 4K | |
| `gemma-2-2b-it-q4f16_1-MLC` | 1.9 GB | 4K | |
| `Llama-3.2-3B-Instruct-q4f16_1-MLC` | 2.2 GB | 4K | Buen equilibrio capacidad / VRAM |
| `Phi-4-mini-instruct-q4f16_1-MLC` | 3.4 GB | 4K | Fuerte en extraccion estructurada |
| `Qwen3-4B-q4f16_1-MLC` | 3.4 GB | 4K | Modo thinking: penaliza latencia |
| `gemma-4-E2B-it-q4f16_1-MLC` | 3.3 GB | 4K | Requiere `shader-f16` |

`[PROPUESTO]` El motor mas recomendado para extraccion estructurada es **Phi-4-mini** o
**Llama-3.2-3B**: el modo "thinking" de la familia Qwen genera tokens de razonamiento que
consumen ventana y ralentizan la extraccion sin aportar en un esquema fijo.

> Nota de implementacion: en el navegador no se usan cookies para guardar el modelo (solo
> soportan 4 KB). Se usa un modal de aceptacion explicita que activa
> `navigator.storage.persist()` y guarda los pesos en Cache API / IndexedDB hasta que el
> usuario decida limpiar sus datos.

### 5.5 La restriccion que define el tamano de bloque

`[DECIDIDO]` **El tamano del bloque se deriva de la ventana de contexto del modelo.**

Los modelos de navegador vienen con **4096 tokens** de contexto por defecto. Un bloque de 10
paginas de texto denso ronda las 4.000 a 6.000 tokens: no cabe. Con el valor original de 10
paginas, la llamada se trunca y el fallo se manifesta como "el modelo devuelve basura", no
como "el bloque es demasiado grande".

```
tokens_por_pagina  ~= 600 a 900   (estimado; se calibra con documentos reales)
tokens_reservados  = instruccion + esquema JSON + tokens de salida esperados
paginas_por_bloque = floor((ventana_contexto - tokens_reservados) / tokens_por_pagina)
```

Con 4K de ventana y 1.200 tokens reservados quedan ~2.900 tokens utiles: **3 paginas por
bloque**. Ese es el valor por defecto. `ventana_contexto` es una propiedad del modelo, no un
parametro global libre.

---

## 6. Almacenamiento central

`[DECIDIDO]` **Supabase** (PostgreSQL + Auth + RLS) es la fuente unica de verdad para los
usuarios autorizados.

- **Plan recomendado:** Supabase Pro (~$25/mes) para produccion: 8 GB de base de datos, sin
  pausas por inactividad, backups diarios y connection pooler ampliado. `[PROPUESTO]`
- **RLS en todas las tablas** con datos de usuario, filtrando por `auth.uid()` o por
  `organizacion_id` segun el ambito. `[DECIDIDO]`
- **Insercion por lotes:** enviar los registros extraidos de un documento en una sola
  peticion, no cientos de peticiones individuales. `[DECIDIDO]`

El modelo de datos completo esta en [ARQUITECTURA.md](ARQUITECTURA.md#5-modelo-de-datos).

---

## 7. Requisitos

### 7.1 Funcionales

| ID | Requisito | Estado |
|---|---|---|
| RF-01 | Autenticar al usuario y resolver su organizacion, rol y ambito de datos | `[DECIDIDO]` |
| RF-02 | Configurar el motor IA por usuario u organizacion antes de analizar | `[DECIDIDO]` |
| RF-03 | Seleccionar un PDF desde el equipo y registrar sus metadatos (nombre, paginas, hash) sin que el archivo salga del equipo | `[DECIDIDO]` |
| RF-04 | Extraer y limpiar el texto del documento en el navegador | `[DECIDIDO]` |
| RF-05 | Dividir el documento en bloques con tamano derivado de la ventana de contexto | `[DECIDIDO]` |
| RF-06 | Analizar cada bloque y extraer campos estructurados validos | `[DECIDIDO]` |
| RF-07 | Consolidar los analisis parciales en un resumen ejecutivo, de forma jerarquica | `[DECIDIDO]` |
| RF-08 | Persistir documento, bloques y analisis, con insercion por lotes | `[DECIDIDO]` |
| RF-09 | Listar y consultar documentos y resultados, con paginacion y filtro por ambito | `[DECIDIDO]` |
| RF-10 | Aplicar las politicas de visibilidad acordadas | `[DECIDIDO]` DP-04 (cerrada). ADR-30, ADR-33 |
| RF-11 | Consultar y editar plantillas de extraccion sin migrar la base de datos | `[DECIDIDO]` |
| RF-12 | Reportar el estado del procesamiento (en proceso / completado / error) | `[DECIDIDO]` |
| RF-13 | Detectar la capacidad del equipo y explicar cuando el modo navegador no es viable | `[DECIDIDO]` |
| RF-14 | Ofrecer un camino que funcione para usuarios sin WebGPU | `[DECIDIDO]` DP-11 (cerrada): **solo navegador**, sin modo hospedado. ADR-19. El camino es un equipo con WebGPU; no hay alternativa en la v1 |
| RF-15 | Aplicar un **sistema de roles y permisos** que determine que informacion ve cada usuario | `[DECIDIDO]` |
| RF-16 | **Administrar usuarios**: crear cuentas con nombres, apellidos, correo y contrasena autogenerada enviada por correo, asignar rol y organizacion, desactivar | `[DECIDIDO]` |
| RF-17 | Reportar el avance de un analisis: **porcentaje, paso actual y tiempo transcurrido** | `[DECIDIDO]` |
| RF-18 | Registrar la **lista de actividades** realizadas durante el analisis | `[DECIDIDO]` |
| RF-19 | Entregar el resultado como un JSON de resumenes por bloque mas el resumen ejecutivo, mapeado por DTO | `[DECIDIDO]` |
| RF-20 | Permitir elegir y configurar el modelo del motor desde un panel | `[DECIDIDO]` |
| RF-21 | Recuperar un analisis interrumpido (el usuario cerro la pestana) sin intervencion manual | `[DECIDIDO]` |
| RF-22 | **Archivar el documento** en almacenamiento privado, con control de acceso por permisos | `[DECIDIDO]` |
| RF-23 | **Descargar** el documento mediante un enlace temporal, solo para quien tenga permiso | `[DECIDIDO]` |
| RF-24 | Volver a analizar un documento archivado cuando cambie la plantilla, sin volver a pedir el archivo | `[DECIDIDO]` |
| RF-25 | Eliminar el archivo del almacenamiento al eliminar el documento | `[DECIDIDO]` |

### 7.2 No funcionales

| ID | Requisito | Estado |
|---|---|---|
| RNF-01 | El documento original y su texto no llegan a ninguna API de terceros; el unico sitio donde pueden estar es la infraestructura del proyecto | `[DECIDIDO]` |
| RNF-02 | El analisis no bloquea al usuario: ocurre en su equipo o en una cola asincrona, nunca en el hilo del request | `[DECIDIDO]` |
| RNF-03 | El backend debe responder en el tiempo de una peticion normal, no en el del analisis | `[DECIDIDO]` |
| RNF-04 | Aislamiento de datos entre usuarios y entre organizaciones | `[DECIDIDO]` |
| RNF-05 | La configuracion de motor IA se aplica sin redeploy | `[DECIDIDO]` |
| RNF-06 | Trazabilidad: quien subio que documento, cuando y con que configuracion | `[DECIDIDO]` |
| RNF-07 | Los campos extraidos se validan contra un esquema; un JSON invalido no llega a la base | `[DECIDIDO]` |
| RNF-08 | El backend es stateless y portable entre plataformas de funciones | `[DECIDIDO]` ADR-04 |
| RNF-09 | El progreso reportado es monotono: nunca retrocede | `[DECIDIDO]` |

---

## 8. Glosario

| Termino | Significado en este proyecto |
|---|---|
| Documento | PDF analizado. Insumo del analisis, no activo a preservar |
| Bloque / chunk | Segmento de N paginas del documento, unidad de analisis en la fase Map |
| Plantilla de extraccion | Esquema dinamico de campos a extraer, versionado, en JSONB |
| Modo de ejecucion | Donde corre el LLM: navegador del usuario o servidor propio |
| Analisis | Resultado consolidado de un documento (fase Reduce) |
| Organizacion | Unidad de comparticion de datos (equipo o area) |
| RLS | Row Level Security de Postgres, aplicado por politica a nivel de fila |

---

## 9. Referencia

- Documento original sin procesar: `docs/legacy/arquitectura-proyecto-analisis-documental.ORIGINAL.md`
- Decisiones tecnicas: [ARQUITECTURA.md](ARQUITECTURA.md)
- Metodo y contratos de codigo: [../SKILL.md](../SKILL.md)
- Preguntas abiertas: [DECISIONES-PENDIENTES.md](DECISIONES-PENDIENTES.md)
