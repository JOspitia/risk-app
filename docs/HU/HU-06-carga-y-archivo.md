# HU-06 — Carga y archivo de un documento

## Encabezado

- **HU ID:** `HU-06`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-03 (seleccionar un PDF y registrar sus metadatos sin que el archivo salga del equipo, salvo el archivado), RF-22 (archivar el documento en almacenamiento privado)
- **ADR relacionados:** ADR-20 (Supabase Storage, bucket privado, subida directa), ADR-15 (hash como identidad del contenido)
- **Bloquea:** HU-07 (analisis), HU-08 (seguimiento)
- **Bloqueado por:** HU-01 (sesion), HU-02 (permisos)

---

## 1. Titulo y descripcion

**Titulo:** HU-06 — Carga y archivo de un documento

**Descripcion:** Permitir que una persona **seleccione un PDF de su equipo**, lo registre en el
sistema y lo archive en el almacenamiento privado del proyecto.

El archivo **no se procesa en el servidor**: se sube directo del navegador al almacenamiento,
sin pasar por la API. El backend valida y firma; el navegador transfiere; el backend
confirma y vincula.

El PDF se archiva por una razon que no es el analisis: **volver a el**. Un documento
analizado se puede reanalizar con otra plantilla sin volver a pedir el archivo.

**La subida y el analisis son independientes.** La subida es archivado; el analisis ocurre en
el navegador. Uno puede fallar sin que el otro se caiga.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Seleccionar un PDF desde el equipo |
| 2 | Calcular en el navegador el hash SHA-256 y el numero de paginas |
| 3 | Validar tipo real (magic bytes) y tamano antes de firmar |
| 4 | Crear el documento y el trabajo, y devolver una URL firmada de subida |
| 5 | Subir el archivo directo del navegador al almacenamiento |
| 6 | Confirmar la subida y vincular la ruta al documento |
| 7 | Detectar el documento duplicado por hash |
| 8 | Descargar el archivo mediante URL firmada de corta duracion |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Extraer el texto del PDF | HU-07 |
| 2 | Analizar con el LLM | HU-07 |
| 3 | OCR de documentos escaneados | Fuera de la v1 (ADR-11) |
| 4 | Editar o convertir el archivo | Fuera de alcance |
| 5 | Compartir el documento con otro usuario | HU-09 |
| 6 | Eliminar el documento y su archivo | HU-09 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion), **HU-02** (permisos: `documentos.analizar`, `archivos.descargar`).

### Esta HU BLOQUEA

- **HU-07**: el analisis necesita el documento registrado.
- **HU-08**: el trabajo nace aqui.
- **HU-10**: el reanálisis necesita el archivo archivado.

---

## 4. Variables y configuracion

| Parametro | Default | Nota |
|---|---|---|
| `MAX_UPLOAD_MB` | `50` | Limite del bucket en el plan Free |
| `MIME_PERMITIDOS` | `application/pdf` | El bucket lo enforce con `allowed_mime_types` |
| `TIPOS_MIME_DETECTADOS` | lista de magic bytes de PDF | El backend **no** confia en la extension |
| `RUTA_PREFIJO` | `{organizacion_id}/{usuario_id}/` | El prefijo de la clave codifica el ambito |
| `NOMBRE_ARCHIVO_EN_BUCKET` | `{documento_id}.pdf` | Nunca el nombre original del cliente |
| `URL_FIRMADA_TTL_SEGUNDOS` | `3600` | Descarga |
| `URL_SUBIDA_TTL_SEGUNDOS` | `900` | Subida |
| `TIMEOUT_SUBIDA_MS` | `300000` | 5 minutos para el PUT del navegador |

---

## 5. Suposiciones

1. El **nombre original del archivo no viaja al servidor** como nombre de objeto. Se
   guarda como metadato (`nombre_archivo`) y el objeto se llama `{documento_id}.pdf`. Un
   nombre de cliente puede contener rutas, comillas o caracteres que rompen cosas.
2. El **hash SHA-256 se calcula en el navegador**, con la Web Crypto API. Es el mismo
   algoritmo que usaria el servidor, y evita subir el archivo dos veces (una para el hash,
   otra para el archivo).
3. El **numero de paginas** se obtiene con `pdf.js` en el navegador, antes de subir. El
   servidor no lo necesita para archivar.
4. El **tipo se valida por magic bytes**, no por la extension. Un archivo `.pdf` que en
   realidad es un `.exe` se rechaza.
5. **La subida no pasa por la API.** El cuerpo de una funcion de Vercel esta limitado a
   4.5 MB y un PDF de 100 paginas pesa mucho mas.
6. La **URL firmada de subida no puede llevar tamano ni tipo**. Por eso el backend valida
   antes de firmar, y el bucket es la segunda linea de defensa.
7. El **documento se crea antes de subir el archivo**. Si la subida falla, el documento
   queda registrado sin archivo, y se puede reintentar sin duplicar el registro.
8. El **hash identifica el contenido**: el mismo archivo subido dos veces por la misma
   persona se detecta como duplicado. `[PROPUESTO]` No se bloquea el segundo uso: se avisa
   y se permite, porque puede ser un analisis con otra plantilla.
9. El analisis **no depende** de que la subida haya terminado. Se puede analizar en local
   mientras el archivo sube.
10. El **archivo se borra junto con el documento**. Un soft delete en la base sin borrar el
    objeto deja un PDF vivo que la interfaz ya no muestra.

---

## 6. Modelo de datos

```sql
-- documentos: se agrega la ruta del objeto archivado
alter table documentos
  add column ruta_archivo text,
  add column tamano_bytes bigint,
  add column tipo_mime text not null default 'application/pdf',
  add column archivado_en timestamptz;
```

**Invariante:** `ruta_archivo IS NOT NULL` significa que el archivo esta archivado. Un
documento con `estado = completado` y `ruta_archivo IS NULL` es un documento analizado
localmente cuyo archivo no se pudo subir: **estado valido**, y la UI lo dice.

### Politicas del bucket

```sql
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documentos', 'documentos', false, 52428800, array['application/pdf']);
```

Las politicas sobre `storage.objects` resuelven el ambito **por prefijo**, sin una tabla de
busqueda:

```sql
create policy archivos_insertar on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documentos'
    and (storage.foldername(name))[1] = (
      select p.organizacion_id::text from perfiles p where p.id = auth.uid()
    )
  );
```

---

## 7. Camino feliz principal

### 7.1 Seleccionar el archivo

1. El usuario pulsa "Analizar documento".
2. El navegador abre el selector de archivos. Se acepta `application/pdf`.
3. Al elegirlo, el frontend **en el navegador**:
   - lee los primeros bytes para verificar los magic bytes de PDF,
   - calcula el SHA-256 con Web Crypto,
   - abre el PDF con `pdf.js` para contar paginas.
4. La UI muestra una ficha: nombre, numero de paginas, tamano y un aviso de que se
   archivara.

### 7.2 Registrar y obtener la URL de subida

1. El frontend llama a `POST /api/v1/documentos` con nombre, hash, paginas y tamano.
2. El caso de uso comprueba `documentos.analizar`.
3. El backend valida el tamano y el tipo. Si no cumple, responde 413 o 415 **antes** de
   firmar nada.
4. El backend comprueba el hash: si ya existe un documento de esta persona con el mismo
   contenido, responde 409 con la referencia al documento existente.
5. El backend crea el documento (`estado = en_proceso`) y el trabajo.
6. El backend firma una URL de subida con TTL de 15 minutos, restringida a la ruta
   `{organizacion_id}/{usuario_id}/{documento_id}.pdf`.
7. Responde `201`:

```json
{
  "success": true,
  "message": "Documento registrado. Sube el archivo para archivarlo.",
  "data": {
    "documento_id": "d81f...",
    "trabajo_id": "3a02...",
    "url_subida_firmada": "https://.../storage/v1/object/sign/documentos/...token",
    "ruta": "c41a.../9b2e.../d81f....pdf",
    "caduca_en": 900
  },
  "errors": null,
  "timestamp": "2026-11-27T14:00:00Z"
}
```

### 7.3 Subir el archivo

1. El navegador hace el `PUT` del PDF **directo a Supabase Storage**, con la URL firmada.
2. La UI muestra el progreso de la subida.
3. El navegador llama a `POST /api/v1/documentos/{id}/archivo` para confirmar.
4. El backend guarda `ruta_archivo`, `tamano_bytes` y `archivado_en`.
5. Responde 200.

### 7.4 Descargar despues

1. El usuario pide el archivo desde el detalle del documento.
2. La UI llama a `GET /api/v1/documentos/{id}/descarga`.
3. El backend comprueba `archivos.descargar`.
4. Responde con una URL firmada de 1 hora.
5. El navegador la abre y el archivo se descarga.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El archivo **no es un PDF** (magic bytes distintos) | El frontend lo detecta antes de subir. Si llega al backend, el backend lo rechaza | 415 |
| SP-02 | El archivo **supera el limite de tamano** | Se rechaza antes de firmar la URL | 413 |
| SP-03 | El **hash ya existe** para esta persona | 409 con el `documento_id` existente y la opcion de continuar | 409 |
| SP-04 | La **subida falla** por red | Se reintenta hasta 2 veces. El documento **queda registrado** sin archivo y se puede reintentar la subida | error en la UI |
| SP-05 | La **URL firmada caduca** antes de subir | 401 de Storage. El frontend pide una nueva al backend y reintenta | 401 |
| SP-06 | La politica de RLS del bucket **rechaza** la subida | 403 de Storage. El backend no puede hacer mas: la clave esta mal construida | 403 |
| SP-07 | El usuario **no tiene permiso** `documentos.analizar` | 403 en el `POST` | 403 |
| SP-08 | El documento **no tiene archivo** y se pide la descarga | 404 con el mensaje "Este documento no tiene archivo archivado" | 404 |
| SP-09 | La **URL de descarga caduca** mientras el usuario la tiene abierta | El enlace deja de funcionar. Se pide uno nuevo | 403 de Storage |
| SP-10 | El **nombre del archivo** tiene caracteres raros o una ruta | No se usa como nombre de objeto. El objeto es `{documento_id}.pdf` | — |
| SP-11 | El PDF **esta cifrado con contrasena** | `pdf.js` no puede abrirlo. Se detecta en el navegador y se informa antes de subir | error en la UI |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | PDF de 100 paginas y 30 MB | Cabe en el limite de 50 MB del plan Free. La subida es directa, asi que no choca con el limite de 4.5 MB de la funcion |
| EC-02 | PDF de 200 paginas y 80 MB | Supera el limite del bucket en el plan Free. Se responde 413 con el limite exacto. En Pro el limite sube a 500 GB |
| EC-03 | PDF de una sola pagina | Es valido. El chunking produce un bloque |
| EC-04 | PDF con 0 paginas | El navegador lo detecta: no hay nada que analizar. Se rechaza con un mensaje claro |
| EC-05 | El hash es identico y el documento anterior fue **borrado** | Se permite la carga nueva. El hash duplicado solo se detecta entre documentos vivos |
| EC-06 | El navegador pierde la conexion a mitad de la subida | La subida se cancela. La cache parcial de Storage no se considera valida y la politica la rechaza en el siguiente intento |
| EC-07 | El mismo archivo, subido por **dos personas distintas** | Se permiten las dos copias. El hash detecta duplicados **por usuario**, no globalmente |
| EC-08 | El PDF tiene paginas en blanco al final | `pdf.js` las cuenta. El chunking puede producir bloques vacios, que se descartan al extraer |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El nombre es `../../etc/passwd.pdf` | Se guarda como metadato de texto, con los caracteres de ruta eliminados. **Nunca** se usa como nombre de objeto |
| CE-02 | El nombre tiene 300 caracteres | Se trunca a 255 para la visualizacion |
| CE-03 | El cliente envia un `nombre_archivo` con codigo de control | Se sanea. La UI escapa al renderizar |
| CE-04 | El cliente intenta enviar `ruta_archivo` en el `POST` | Se ignora. La ruta la genera el backend, no el cliente |
| CE-05 | El cliente intenta enviar `usuario_id` de otra persona | Se ignora. El usuario sale del token |
| CE-06 | Un archivo con la extension `.pdf` pero que es un ZIP | El magic bytes no coincide. 415 |
| CE-07 | Un PDF valido con metadatos que contienen codigo JavaScript | Se archiva tal cual. **El backend nunca lo sirve como HTML**: la descarga es un `Content-Type: application/pdf` con `Content-Disposition: attachment` |
| CE-08 | Dos subidas simultaneas del mismo documento | La segunda recibe 409 por el indice unico del hash |

---

## 10. Criterios de aceptacion

### CA-01: El archivo no pasa por el backend
**Dado** el codigo del frontend
**Cuando** se busca la subida del PDF
**Entonces** el `PUT` va **directo a Supabase Storage**, no a un endpoint de la API
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: El tipo se valida por contenido
**Dado** un archivo con extension `.pdf` que no es un PDF
**Cuando** se selecciona
**Entonces** el navegador lo detecta por sus magic bytes y lo rechaza **antes** de subirlo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: El tamano se valida antes de firmar
**Dado** un archivo mayor al limite
**Cuando** se registra el documento
**Entonces** responde 413 con el limite y **no** se firma ninguna URL
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: El hash se calcula en el navegador
**Dado** el codigo del frontend
**Cuando** se calcula el hash
**Entonces** usa la Web Crypto API con SHA-256, **no** una libreria de JS sin revisar
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El duplicado se detecta
**Dado** un documento ya subido con el mismo hash por la misma persona
**Cuando** se vuelve a registrar
**Entonces** responde 409 con la referencia al documento existente
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: El bucket es privado
**Dado** las politicas de `storage.objects`
**Cuando** se inspecciona el bucket
**Entonces** `public = false`
**Y** existe una politica de lectura que exige pertenencia a la organizacion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: El prefijo codifica el ambito
**Dado** la ruta de un objeto archivado
**Cuando** se inspecciona
**Entonces** es `{organizacion_id}/{usuario_id}/{documento_id}.pdf`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: La descarga es temporal
**Dado** un usuario con `archivos.descargar`
**Cuando** pide la descarga
**Entonces** recibe una URL firmada con TTL de 1 hora
**Y** **no** recibe una URL publica ni permanente
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: Sin permiso no hay descarga
**Dado** un usuario sin `archivos.descargar`
**Cuando** pide la descarga de un documento que no es suyo
**Entonces** responde 403
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: Un fallo de subida no rompe el documento
**Dado** una subida que falla por red
**Cuando** se reintenta
**Entonces** el documento sigue registrado, no se duplica, y se puede reintentar la subida
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: El nombre del cliente no es el nombre del objeto
**Dado** un archivo llamado `../../etc/passwd.pdf`
**Cuando** se archiva
**Entonces** el objeto se llama `{documento_id}.pdf`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: El PDF se sirve como descarga, no como pagina
**Dado** un archivo subido
**Cuando** se sirve la URL firmada
**Entonces** el `Content-Type` es `application/pdf` y el `Content-Disposition` es
`attachment`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
