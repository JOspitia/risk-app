# Risk-app

> Plataforma web de **analisis privado de documentos**: ETL, extraccion estructurada con un
> LLM local y persistencia en Supabase, para ~200 usuarios con roles y aislamiento por
> organizacion.

Este README es el **brief de entrada**. Sirve para dos cosas:

1. Que una persona nueva entienda el proyecto en diez minutos.
2. Que **otra IA** (Copilot, GPT, el agente que sea) pueda leer el repositorio, revisar la
   especificacion y devolver hallazgos utiles **sin necesitar contexto previo**.

- **Estado:** especificacion completa. **Esqueleto de codigo listo**: el backend y el frontend
  arrancan, compilan y pasan sus verificaciones. Todavia no hay logica de negocio.
- **Ultima actualizacion:** 2026-11-28
- **Idioma:** espanol (CO). La documentacion, los identificadores y los mensajes estan en
  espanol a proposito.

---

## 1. Que es el producto

El usuario sube un PDF privado extenso (del orden de 100 paginas), el sistema lo limpia,
lo divide en bloques, extrae informacion estructurada de cada bloque con un LLM, consolida
los resultados en un resumen ejecutivo y los guarda en una base centralizada para que otros
usuarios autorizados los consulten.

El dominio es el **analisis de riesgos documental**: el sistema no solo extrae datos, los
interpreta como riesgos.

**Lo unico que no hace:** enviar el texto de un documento a una API de terceros. El LLM se
ejecuta en el navegador del usuario.

### 1.1 Privacidad: el requisito critico

- El documento **se archiva** en almacenamiento privado bajo control del proyecto
  (Supabase Storage, bucket privado, RLS, URL firmadas de 1 hora).
- El **analisis ocurre en el equipo del usuario** (WebLLM sobre WebGPU). El documento no se
  procesa en ningun servidor.
- El texto de un documento **nunca** sale de la infraestructura del proyecto.
- Ni logs, ni trazas, ni metricas contienen texto de documento.

> **Aviso para quien revise con una IA externa:** este repositorio **no contiene ningun
> documento de cliente ni texto de ejemplo**. Solo especificacion. Compartirlo no expone
> datos del proyecto. El contenido que no debe compartirse jamas son los PDFs analizados.

---

## 2. Estado actual

| Area | Estado |
|---|---|
| Especificacion funcional | Completa. 25 RF + 9 RNF |
| Decisiones de arquitectura | Completas. 34 ADR |
| Decisiones de producto | Completas. 15 de 15 cerradas |
| Historias de usuario | **12 de 12** escritas |
| Metodo y contratos de codigo | Completo. `SKILL.md` |
| Gates de verificacion | Completos. 19 gates en `CHECKLIST.md`, 44 items ya verificados |
| **Esqueleto del proyecto** | **Listo.** Backend y frontend instalan, compilan y verifican |
| Logica de negocio | **No existe todavia.** Sin endpoints, sin dominio, sin adaptadores |
| Pendientes documentados | 14 (PP-01 a PP-14) |

**La siguiente fase** es la migracion: esquema con RLS, matriz de permisos y bucket privado,
aplicada contra una base **vacia**.

---

## 3. Stack

| Componente | Version | Verificado |
|---|---|---|
| Python | 3.14.10 | 2026-11-27 |
| FastAPI | 0.165.0 | 2026-11-27 |
| Vue | 3.5.46 | 2026-11-27 |
| Vite | 8.4.0 | 2026-11-27 |
| TypeScript | 6.0.3 | 2026-11-27 |
| PostgreSQL | 17 (Supabase) | 2026-11-27 |
| Supabase | Auth + Postgres + RLS + PostgREST + Storage | - |
| LLM | WebLLM en el navegador (Qwen3, Llama 3.2, Phi-4-mini, Gemma) | - |

---

## 4. Arquitectura en una pagina

### 4.1 Hexagonal: el nucleo no depende de nada

```
Request HTTP
    |
    v
[Adaptador de entrada]  -> router FastAPI: valida, orquesta, elige status
    |
    v
[Caso de uso]           -> logica de negocio, transaccion, autorizacion
    |
    v
[Puertos]               -> interfaces que define el DOMINIO
    |
    v
[Adaptadores de salida] -> Supabase, LLM, almacenamiento, correo
    |
    v
[Entidad de dominio]
```

**La invariante:** las dependencias apuntan hacia adentro y a un solo lado. `domain/` no
importa nada de `adapters/`, `application/` ni de frameworks. Se comprueba con
`import-linter`.

**Por que hexagonal:** hay tres adaptadores de salida intercambiables (Supabase, motor LLM,
almacenamiento) y dos modos de ejecucion del pipeline (navegador y servidor). Con puertos,
cambiar de proveedor es **un archivo nuevo**, no un proyecto nuevo.

### 4.2 Estructura de carpetas

```
backend/app/
  domain/        entidades, value objects, ports, reglas puras, errores
  application/   casos de uso, DTOs, auditoria, unit of work
  adapters/      http/ supabase/ llm/ etl/ storage/ queue/
  worker/        consumidor de la cola
frontend/src/
  api/ stores/ views/ components/ workers/
```

### 4.3 El pipeline

```
1. Seleccion      -> el usuario elige el PDF en su equipo
2. Descarga       -> se descarga el modelo al navegador (1.5 a 3 GB), una sola vez
3. ETL            -> pdf.js extrae el texto, se limpia, se divide en bloques
4. Map            -> cada bloque se analiza solo: JSON validado + resumen parcial
5. Reduce         -> los resumenes parciales se consolidan (jerarquico si no caben)
6. Archivo        -> el PDF sube directo a Supabase Storage (bucket privado)
7. Persistencia   -> la API valida el JSON contra la plantilla y lo guarda
8. Progreso       -> el cliente reporta % , paso actual y tiempo transcurrido
```

### 4.4 La restriccion que define el chunking

**El tamano de bloque se deriva de la ventana de contexto del modelo.** Los modelos de
WebLLM vienen con **4096 tokens**, y 10 paginas de texto denso rondan las 4.000 a 6.000
tokens: no caben. El sintoma de ese error no es "el bloque es grande", es "el modelo
devuelve basura".

```
paginas_por_bloque = floor((ventana_contexto - tokens_reservados) / tokens_por_pagina)
```

Con 4K y 1.200 tokens reservados salen **3 paginas por bloque**. Con un modelo de 200K de
ventana, el documento entero cabe y el reduce jerarquico deja de ser necesario.

**Consecuencia directa:** cambiar de motor cambia el chunking solo, y ese es el motivo por
el que el motor es configurable por usuario y por organizacion.

---

## 5. Modelo de datos

| Tabla | Para que |
|---|---|
| `organizaciones` | Unidad de comparticion (equipo o area) |
| `perfiles` | Extiende `auth.users`: rol, organizacion, nombres, `debe_cambiar_contrasena` |
| `organizaciones_miembros` | Pertenencia con rol por equipo |
| `roles`, `permisos`, `rol_permisos` | **La matriz de permisos vive en datos**, no en codigo |
| `configuracion_motor` | Parametrizacion del motor IA, por usuario o organizacion |
| `plantillas_extraccion` | Campos dinamicos a extraer, en JSONB, versionados |
| `documentos` | El PDF analizado: metadatos, hash, ruta del archivo, estado |
| `bloques` | Un registro por bloque analizado, con sus datos estructurados |
| `analisis_documentos` | Resultado consolidado: resumen ejecutivo, riesgos, resumenes por bloque |
| `trabajos` | Seguimiento: estado, progreso, paso actual, duracion |
| `trabajo_actividades` | Bitacora de pasos ejecutados |

**RLS activo en todas las tablas** con datos de usuario. La `service_role` no atiende
peticiones de usuario final: el backend reenvia el JWT del usuario y deja que RLS filtre.

**Soft delete** en todas las tablas (`eliminado_en`), y toda lectura filtra `eliminado_en IS
NULL`.

---

## 6. Despliegue

| Nivel | Componente | Plataforma v1 |
|---|---|---|
| 1 | Frontend Vue estatico | Vercel (o cualquier CDN) |
| 2 | API FastAPI stateless | Vercel Functions (runtime de Python) |
| 3 | Datos, identidad y archivos | Supabase |
| 4 | Worker ETL con LLM hospedado | **No se desplega en la v1** |

**Restricciones verificadas de la plataforma:**

- Vercel: filesystem de **solo lectura**, `/tmp` efimero de 500 MB, cuerpo de peticion
  limitado a 4.5 MB, funcion de 300 s. Por eso **el PDF nunca pasa por el backend**: sube
  directo del navegador al almacenamiento.
- El backend habla con Supabase **por HTTP (PostgREST)**, no por TCP. Eso lo deja stateless
  y portable a Cloudflare Workers. La atomicidad va en funciones de Postgres (RPC).
- **El costo no escala con los usuarios**: el LLM corre en sus equipos.

**Perfil de demo gratuita** (Vercel Hobby + Supabase Free, $0) con tres trampas
documentadas: Supabase Free **se pausa a la semana sin uso**, el SMTP incluido manda **2
correos por hora** y solo al equipo, y Vercel Hobby es de uso **personal o no comercial**.

---

## 7. Mapa del repositorio

| Archivo | Que contiene | Cuando leerlo |
|---|---|---|
| `README.md` | Este brief | Primero, siempre |
| `AGENTS.md` | Reglas del repositorio y orden de lectura | Antes de tocar nada |
| `docs/CONTEXTO.md` | Producto: que hace, para quien, con que restricciones | Para entender el **que** |
| `docs/ARQUITECTURA.md` | Stack, estructura, modelo de datos, despliegue y los **34 ADR** | Para entender el **como** |
| `docs/DECISIONES-PENDIENTES.md` | Las 15 decisiones (cerradas), los pendientes y los **PP-01 a PP-14** | Para saber que esta abierto |
| `docs/HU/INDICE.md` | Indice de historias de usuario y grafo de dependencias | Para planificar trabajo |
| `docs/HU/HU-0*.md` | Historias de usuario completas | Antes de implementar una funcionalidad |
| `docs/CONTRATO-RESULTADO-ANALISIS.md` | **La forma de un riesgo**: que envuelve a lo que el LLM extrae | Al implementar la extraccion o la comparacion de analisis |
| `SKILL.md` | Los **9 contratos de codigo**, el baseline de seguridad, las transacciones, las pruebas | Al escribir codigo. Es normativa |
| `CHECKLIST.md` | Los **19 gates** de verificacion y la tabla **"Gates por HU"**. Los `[x]` llevan la evidencia al lado | Antes de dar algo por terminado |
| `CONTRIBUTING.md` | Convencion de commits y pull requests | Al commitear |
| `docs/ARRANQUE.md` | **Guia de arranque local**: requisitos, comandos, orden de trabajo | Al clonar y correr el proyecto |
| `backend/` | Codigo de la API (FastAPI, hexagonal). `app/`, `tests/`, `api/` | Al tocar el backend |
| `frontend/` | Codigo de la SPA (Vue 3.5, Vite 8). `src/`, `workers/` | Al tocar el frontend |
| `supabase/` | `config.toml` y `migrations/*.sql`: el **esquema** del proyecto | Al tocar el modelo de datos |
| `shared/` | Fixtures compartidas entre Python y TypeScript (casos dorados del chunking) | Al tocar el troceado |
| `referencias/` | Codigo de terceros clonado **solo para leer**. El analisis esta en `docs/` | Antes de implementar una funcionalidad similar |
| `docs/legacy/` | Los documentos originales sin procesar | Solo como referencia historica. **No se editan** |

### 7.1 Orden de lectura para trabajar

```
1. README.md              este brief
2. AGENTS.md              las reglas
3. docs/CONTEXTO.md       el producto
4. docs/ARQUITECTURA.md   la arquitectura y los ADR
5. docs/DECISIONES-PENDIENTES.md   que esta abierto
6. docs/HU/               la historia de usuario de lo que se va a tocar
7. SKILL.md               los contratos de codigo
8. CHECKLIST.md           los gates
```

---

## 8. Reglas del proyecto

1. **No se inventan datos.** Lo que no este en `CONTEXTO.md` o `ARQUITECTURA.md` se marca
   `[ABIERTO]` y se anota en `DECISIONES-PENDIENTES.md`. Un campo de riesgo desconocido se
   marca `[PENDIENTE]` en la plantilla, no se rellena con un ejemplo plausible.
2. **Todo cambio de decision es un ADR**, con fecha y motivo, en la tabla de
   `ARQUITECTURA.md` seccion 10. Cerrar una pregunta abierta actualiza el ADR **y** la
   decision, en el mismo commit.
3. **Documentacion, codigo y respuestas en espanol.**
4. **El permiso se comprueba en el caso de uso**, no solo en el router. Un permiso ausente se
   deniega.
5. **Los errores de dominio no se reenvuelven** en errores genericos: cada uno lleva su
   status HTTP.
6. **Los secretos van en variables de entorno**, y el arranque falla si falta una.
7. **Un commit, un objetivo**, en Conventional Commits con contenido en espanol.

---

## 9. Como pedir una revision a otra IA

### 9.1 Que se le debe dar

El repositorio completo, o en este orden: `README.md`, `AGENTS.md`, `docs/CONTEXTO.md`,
`docs/ARQUITECTURA.md`, `docs/DECISIONES-PENDIENTES.md`, `docs/HU/`, `SKILL.md`,
`CHECKLIST.md`, y despues `docs/ARRANQUE.md` y `backend/`/`frontend/` para revisar el
esqueleto.

**No se le debe dar ningun documento de cliente.** Este repositorio no los contiene.

### 9.2 Que buscar

Aqui esta el trabajo real. Una IA externa es util sobre todo para esto:

| # | Que buscar | Como se detecta |
|---|---|---|
| 1 | **Contradicciones entre documentos** | Un ADR que contradice a una HU, un RF que contradice a un ADR, dos archivos que dicen cosas distintas de la misma cosa |
| 2 | **Criterios sin cobertura** | Un RF sin HU, una HU sin criterio de aceptacion, un ADR sin efecto en el codigo |
| 3 | **Huecos de seguridad** | Un permiso que nadie comprueba, un endpoint sin regla de RLS, un dato sensible sin `Resource` |
| 4 | **Casos de error no contemplados** | Caminos tristes y "estupidos" ausentes en las HU |
| 5 | **Supuestos que ya no se sostienen** | Los `[PROPUESTO]` y `[PENDIENTE]`: hoy son 14 (PP-01 a PP-14), mas los marcados en las HU |
| 6 | **Consecuencias no escritas** | Una decision que tenga un efecto que nadie documento (por ejemplo, cambiar de motor cambia el chunking) |
| 7 | **Riesgos de operacion** | Los limites de la plataforma free, la pausa de Supabase, la cobertura de WebGPU |
| 8 | **Deuda de la v1** | Lo que se aplazo y si el aplazamiento sigue siendo valido |

### 9.3 Como pedirlo

Este prompt funciona tanto en Copilot Chat como en GPT:

```
Revisa este repositorio (leeme README.md primero).

Contexto: es un proyecto web de analisis privado de documentos. FastAPI + Vue + Supabase.
La especificacion esta completa (25 RF, 34 ADR, 12 HU). El esqueleto de codigo existe y
verifica, pero **todavia no hay logica de negocio**: ni endpoints, ni dominio, ni
adaptadores. El codigo es solo la estructura y la configuracion.

No propongas cambios de estilo ni reescribas texto. Busca:
1. Contradicciones entre documentos (compara ADR, RF, HU y SKILL.md entre si).
2. Requisitos o criterios de aceptacion sin cobertura en ninguna HU.
3. Huecos de seguridad: permisos que no se comprueban, endpoints sin RLS, datos
   sensibles que se exponen.
4. Caminos de error ausentes en las historias de usuario.
5. Supuestos ya invalidos o que el lector no puede verificar.
6. Consecuencias de decisiones que no estan escritas en ningun sitio.
7. Riesgos de operacion que no estan documentados.

Para cada hallazgo da: archivo y linea, que esta mal, por que importa, y una propuesta
concreta. Marca con [PENDIENTE] lo que sea informacion de negocio que no puedas
inventar: no supongas datos de la empresa.
```

### 9.4 Como reportar los hallazgos

Si la IA devuelve hallazgos, el formato que mas rinde es una tabla:

| # | Hallazgo | Archivo | Severidad | Propuesta |
|---|---|---|---|---|

Y el criterio de severidad que conviene darle:

- **Bloqueante**: contradice una decision cerrada, o deja un requisito sin cobertura.
- **Importante**: un camino de error sin cubrir, o una consecuencia no documentada.
- **Menor**: una aclaracion o una referencia que falta.

---

## 10. Lo que viene ahora

1. **La migracion**: esquema con RLS, matriz de permisos y bucket privado, aplicada contra
   una base **vacia** (no se acepta una migracion que nunca se ejecuto).
2. **Los contratos**: entidades, puertos, casos de uso, envelope, errores.
3. **Los adaptadores**: Supabase (PostgREST), almacenamiento, correo.
4. **Las pruebas**: traducidas de los criterios de aceptacion de cada HU.

El esqueleto ya existe y verifica: `backend/` y `frontend/` instalan, compilan y pasan
`ruff`, `mypy`, `lint-imports`, `pytest`, `eslint`, `vue-tsc` y `vitest`. La guia de
arranque esta en [`docs/ARRANQUE.md`](docs/ARRANQUE.md).

---

## 11. Referencias externas

- [FastAPI 0.165.0 en PyPI](https://pypi.org/project/fastapi/)
- [Vue 3.5.46 en npm](https://www.npmjs.com/package/vue)
- [Supabase Storage](https://supabase.com/docs/guides/storage)
- [WebLLM](https://github.com/mlc-ai/web-llm)
- [Vercel: limites de las funciones](https://vercel.com/docs/limits)
- [PostgREST](https://postgrest.org/)
