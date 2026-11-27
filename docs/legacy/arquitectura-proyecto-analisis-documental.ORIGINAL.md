# Arquitectura del Proyecto: Análisis Privado de Documentos

## 1. Visión General y Requisitos

* **Objetivo:** Plataforma web para cargar documentos privados extensos (~100 páginas), limpiar su contenido (ETL), extraer información estructurada mediante un LLM y almacenar los registros resultantes en una base de datos centralizada.
* **Escala:** ~200 usuarios (concurrencia moderada, no todos simultáneos al mismo segundo).
* **Requisito Crítico:** Privacidad estricta de los documentos. El archivo original y su texto confidencial no deben enviarse a APIs públicas de terceros (como OpenAI o Anthropic).
* **Almacenamiento Central:** Supabase (PostgreSQL + Auth + RLS) para que los usuarios autorizados puedan consultar y compartir los registros extraídos desde cualquier navegador o computador.

---

## 2. Opciones de Arquitectura (Pros y Contras)

Para resolver el procesamiento de 100 páginas manteniendo la privacidad, existen dos enfoques principales (y una opción híbrida):

### Opción 1: Ejecución 100% Local en el Navegador del Usuario (Edge / WebGPU)

El computador de cada persona que entra a la URL actúa como el servidor de IA. Tras aceptar un aviso de consentimiento y almacenamiento persistente (`Cache API` / `IndexedDB`), el navegador descarga el modelo LLM una sola vez y ejecuta todo el ETL y análisis usando la GPU/CPU local del usuario.

* **Stack Técnico:**

  * **Frontend + ETL Local:** React (Vite) + Tailwind CSS + `pdf.js` (extracción de texto) + `LangChain.js` (chunking).
  * **Motor LLM en Navegador:** **WebLLM (`@mlc-ai/web-llm`)** ejecutándose en un *Web Worker* (para no congelar la interfaz) + **Transformers.js** (si se requieren *embeddings* locales).
  * **Base de Datos:** Supabase (recibe únicamente los registros JSON limpios al finalizar).
* **Pros:**

  * **Privacidad absoluta:** El documento jamás sale del computador del usuario.
  * **Costo $0 en servidores de IA:** No pagas GPUs en la nube; los 200 usuarios aportan su propio hardware.
  * **Escalabilidad automática:** Si entran 50 usuarios a la vez, cada uno usa su propio procesador sin saturar ningún servidor central.
* **Contras:**

  * **Dependencia del hardware del cliente:** Si un usuario entra desde un portátil antiguo con poca RAM/VRAM o desde un celular, el análisis de 100 páginas será muy lento o puede fallar por falta de memoria.
  * **Primera carga pesada:** El usuario debe aceptar descargar entre 1.5 GB y 3 GB la primera vez que entra a la URL.
  * **Compatibilidad de navegador:** Requiere navegadores modernos con soporte **WebGPU** (Chrome/Edge de escritorio funcionan ideal; Safari o Firefox antiguos pueden requerir modo CPU más lento).

---

### Opción 2: Backend Privado en Python (FastAPI) + LLM Autoalojado

El usuario sube el PDF a tu propio servidor privado. Python ejecuta un pipeline ETL profesional, divide en *chunks*, consulta un modelo LLM instalado localmente en tu servidor (sin internet externo) y guarda los resultados en Supabase.

* **Stack Técnico:**

  * **Frontend:** React (Vite) + Tailwind CSS + Supabase JS SDK.
  * **Backend & ETL:** Python + **FastAPI** + `PyMuPDF` (`fitz`) / `pdfplumber` / `Docling` + `LangChain Text Splitters`.
  * **Motor LLM Privado:** **Ollama** o **vLLM** corriendo en tu servidor privado + **Pydantic / Instructor** (garantiza salidas JSON exactas).
  * **Base de Datos:** Supabase (PostgreSQL + RLS).
* **Pros:**

  * **Rendimiento garantizado:** Cualquier usuario (incluso desde un celular o PC básico) puede analizar 100 páginas en segundos.
  * **ETL de nivel industrial:** Librerías como `PyMuPDF` o `Docling` limpian tablas complejas, encabezados y PDFs escaneados (OCR) mucho mejor que JavaScript en el navegador.
  * **Sin descargas para el usuario:** El usuario entra a la URL y usa la app al instante.
* **Contras:**

  * **Costo de infraestructura:** Requiere alquilar o mantener un servidor propio con buena RAM y/o GPU dedicada.
  * **Gestión de colas:** Si varios de los 200 usuarios suben 100 páginas al mismo tiempo, necesitas una cola de tareas (ej. Celery o Redis) para procesar en orden sin tumbar el servidor.

---

### Opción 3: Arquitectura Híbrida (Inteligente / Fallback)

1. El frontend detecta automáticamente el hardware del usuario (`navigator.gpu`).
2. Si el PC del usuario tiene buena GPU y acepta la caché local, procesa el documento **100% en su navegador**.
3. Si el usuario entra desde un equipo limitado o rechaza la descarga del modelo, el sistema ofrece enviarlo al **Backend privado en Python** (procesando en memoria RAM y borrando el archivo al instante).

---

## 3. Modelos LLM Recomendados para Ejecución Local

Si se elige la **Opción 1 (Navegador con WebGPU)**, los modelos deben estar cuantizados a **4 bits (`q4f16_1`)** para equilibrar precisión y consumo de memoria:

| Modelo                                | Peso en Caché    | VRAM Mínima   | Fortalezas para este Proyecto                                                                                     |
| :------------------------------------ | :---------------- | :------------- | :---------------------------------------------------------------------------------------------------------------- |
| **Gemma 4 (E2B / E4B)**         | ~1.5 GB – 2.8 GB | 3 GB – 4 GB   | Diseñado para ejecución *edge*/local, ventana de contexto amplia (128K) y excelente comprensión en español. |
| **Qwen 3 (1.7B / 3B / 4B)**     | ~1.2 GB – 2.5 GB | 2.5 GB – 4 GB | Sobresaliente siguiendo instrucciones estrictas y extrayendo datos en formato JSON estructurado.                  |
| **Llama 3.2 (3B Instruct)**     | ~1.9 GB           | ~3.5 GB        | Muy estable y veloz en WebLLM; ideal para resúmenes por *chunk* y extracción directa.                         |
| **Phi-4 Mini / Phi-3.5 (3.8B)** | ~2.2 GB           | ~4 GB          | Gran capacidad de razonamiento analítico sobre textos técnicos o legales densos.                                |

> **Nota sobre Consentimiento y Caché:** En el navegador no se usan *cookies* para guardar el modelo (solo soportan 4 KB). Se utiliza un modal de aceptación explícita que activa `navigator.storage.persist()` para guardar los pesos del modelo en **Cache API / IndexedDB** de forma permanente hasta que el usuario decida limpiar sus datos.

---

## 4. Diseño de Base de Datos y Seguridad en Supabase

Independientemente de si el ETL ocurre en el navegador o en Python, **Supabase** actúa como la fuente única de verdad para los 200 usuarios:

* **Plan Recomendado:** **Supabase Pro ($25/mes)** para producción (8 GB de base de datos, sin pausas por inactividad, backups diarios y *Connection Pooler* ampliado).
* **Privacidad entre usuarios (RLS):** Activar **Row Level Security** en todas las tablas (`auth.uid() = user_id` o filtrado por `organizacion_id` si trabajan por equipos) para que cada persona vea solo lo que le corresponde.
* **Inserción por Lotes (*Batch Insert*):** Enviar todos los registros extraídos de las 100 páginas en una sola petición array (`insert([...])`) en lugar de hacer cientos de peticiones individuales.

### Esquema Inicial de Tablas

```sql
-- 1. Registro maestro de cada documento analizado
create table documentos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  nombre_archivo text not null,
  total_paginas int,
  modo_procesamiento text, -- 'navegador_local' o 'servidor_python'
  estado text default 'completado',
  created_at timestamptz default now()
);

-- 2. Registros extraídos de los chunks del documento
create table registros_extraidos (
  id uuid primary key default gen_random_uuid(),
  documento_id uuid references documentos(id) on delete cascade not null,
  user_id uuid references auth.users not null,
  pagina_inicio int,
  pagina_fin int,
  categoria text,
  datos_estructurados jsonb not null, -- Campos extraídos por el LLM
  resumen_chunk text,
  created_at timestamptz default now()
);
```

---

## 5. Flujo de Datos (Opción 1: 100% Navegador + Supabase)

```
[Usuario abre URL en su Navegador]
   │
   ├── 1. Inicia sesión (Supabase Auth) y acepta aviso de caché local.
   ├── 2. Navegador descarga modelo (ej. Qwen 3 3B / Gemma 4 E4B) en Cache API.
   ├── 3. Usuario selecciona PDF privado (100 págs) desde su PC.
   ├── 4. Web Worker ejecuta ETL (pdf.js limpia texto y divide en chunks).
   ├── 5. WebLLM procesa cada chunk en la GPU local y extrae JSON.
   │      (El PDF nunca sale del computador del usuario)
   ▼
[Supabase (PostgreSQL)]
   │
   └── 6. Frontend envía por Batch Insert solo los registros JSON extraídos.
          Otros usuarios autorizados consultan los datos al entrar a la URL.
```



Preguntas clave para definir el proyecto antes de empezar:

¿Qué tipo de documentos son y cómo vienen? ¿Son PDFs generados digitalmente (con texto seleccionable, como contratos, reportes o facturas) o también incluyen documentos escaneados como imágenes (que exigirían OCR)?



¿Qué tipo de computadores usan los 200 usuarios? ¿Son equipos de oficina modernos (portátiles recientes/PCs de escritorio con al menos 8–16 GB de RAM) o entran desde equipos muy básicos/celulares? (Esto define si apostamos 100% por el navegador o si necesitamos el backend en Python).



¿Qué debe hacer exactamente el LLM con las 100 páginas? ¿Extraer campos específicos a una tabla (ej. fechas, nombres, montos, cláusulas), generar un resumen ejecutivo por secciones, o permitir hacer preguntas tipo chat sobre el documento?



Visibilidad entre los 200 usuarios: Cuando una persona sube y analiza un documento, ¿los registros extraídos deben ser privados solo para ella, visibles para un equipo/área específica, o compartidos para los 200 usuarios?


Sí, todo lo que planteas encaja perfectamente en una arquitectura modular de nivel empresarial. Al tratarse de análisis de riesgos con necesidad de ETL limpio, roles y permisos granulares, parametrización dinámica y escalabilidad, la mejor decisión técnica es combinar lo mejor de ambos mundos: un backend robusto en Python para el ETL, la seguridad, los roles y la configuración dinámica, manteniendo la opción de ejecutar el LLM en el navegador (WebGPU) o en un servidor privado (Ollama/vLLM) según el perfil de cada usuario.



Respuestas a tus requerimientos clave

Consola de configuración parametrizable por el usuario:



Totalmente viable. Puedes guardar en Supabase una tabla de configuracion_ia (por usuario o por rol/empresa) con campos como: modelo_seleccionado (ej. Gemma 4 E4B, Qwen 3 4B), tamano_chunk_paginas (ej. 10 páginas), overlap_paginas (ej. 1 página), ventana_contexto (ej. 8192 o 32768 tokens), temperatura (ej. 0.1 para análisis de riesgos) y modo_ejecucion (Navegador vs. Servidor).



Desde el frontend, el usuario ve una pantalla de "Ajustes del Motor IA" con deslizadores (sliders) y selectores que actualizan esos valores antes de lanzar el análisis.



Procesamiento por bloques de 10 páginas + Consolidación (Map-Reduce):



Al dividir 100 páginas en bloques de 10, obtienes 10 chunks. El flujo ideal para análisis de riesgos es el patrón Map-Reduce:



Fase Map: El LLM analiza cada bloque de 10 páginas por separado y extrae un resumen de riesgos de ese fragmento.



Fase Reduce: Una vez procesados los 10 bloques, se le pasan los 10 resúmenes parciales al LLM en una última llamada para que genere el resumen ejecutivo consolidado de todo el documento (sin saturar la ventana de contexto ni la memoria VRAM).



Preguntas y campos dinámicos a futuro:



En PostgreSQL (Supabase), en lugar de crear columnas rígidas para cada pregunta o riesgo, usa columnas de tipo JSONB y una tabla de plantillas_extraccion. Hoy la plantilla solo tiene una instrucción ("Generar resumen ejecutivo de riesgos"), y mañana desde la misma consola agregas nuevas preguntas o campos JSON sin tocar el código ni migrar la base de datos.



Framework en Python para Roles, Permisos y Gran Cantidad de Usuarios:



Opción recomendada (Rápida y moderna): FastAPI + fastapi-users + Supabase Auth (JWT). Te da rendimiento asíncrono altísimo para cientos de usuarios concurrentes, validación automática de esquemas y control de roles (Admin, Analista de Riesgos, Auditor) mediante dependencias inyectables.



Opción alternativa (Todo incluido): Django + Django Ninja (o DRF). Si prefieres tener un panel administrativo visual ya construido de fábrica para gestionar usuarios, grupos y permisos complejos sin programarlo desde cero, Django lo trae nativo y soporta miles de usuarios.
