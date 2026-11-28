-- =============================================================================
-- 001 — Esquema inicial
--
-- Todas las tablas del proyecto en un solo bloque, en el orden en que se
-- referencian entre si.
--
-- Reglas que se respetan aqui (Gate 1):
-- - Sin coma trailing antes del `)` de cierre de una definicion.
-- - Toda columna `uuid` que apunta a `auth.users` tiene su FK y su `on delete`.
-- - Las columnas de tiempo se llaman `creado_en`, `actualizado_en` y `eliminado_en`.
-- - Los indices se crean aqui, no en otra migracion.
-- =============================================================================

-- Organizaciones (equipos / areas). Unidad de comparticion de datos.
create table organizaciones (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  creado_en   timestamptz not null default now()
);

-- Roles y permisos granulares. La matriz vive en datos, no en codigo: agregar un
-- permiso no requiere desplegar. Se definen antes que `perfiles` porque se referencian.
create table roles (
  clave       text primary key,   -- admin | analista | auditor
  nombre      text not null,
  descripcion text,
  -- True = el rol viene con el sistema y no se puede eliminar ni renombrar.
  is_system   boolean not null default false,
  creado_en   timestamptz not null default now()
);

create table permisos (
  clave       text primary key,   -- documentos.ver | documentos.analizar | ...
  nombre      text not null,
  descripcion text not null,
  creado_en   timestamptz not null default now()
);

create table rol_permisos (
  rol     text not null references roles(clave) on delete cascade,
  permiso text not null references permisos(clave) on delete cascade,
  primary key (rol, permiso)
);

-- Perfil del usuario. Extiende auth.users (Supabase Auth).
create table perfiles (
  id                        uuid primary key references auth.users(id) on delete cascade,
  organizacion_id           uuid references organizaciones(id),
  rol                       text not null default 'analista' references roles(clave),
  nombres                   text not null,
  apellido_1                text not null,
  apellido_2                text,
  display_name              text,
  -- Correo del usuario. Se copia desde `auth.users` al crear la cuenta, para que el
  -- listado de usuarios no tenga que leer `auth.users` con `service_role` en cada
  -- peticion. `auth.users` sigue siendo la fuente de verdad; esta es una copia.
  correo                    text not null,
  -- True mientras la credencial sigue siendo la autogenerada y enviada por correo.
  -- Se limpia en el primer inicio de sesion con cambio de contrasena.
  debe_cambiar_contrasena    boolean not null default false,
  -- False = el usuario esta desactivado: no puede iniciar sesion y el resolutor de
  -- permisos lo trata como sin permisos, sin consultar `auth.users` en cada peticion.
  activo                    boolean not null default true,
  creado_en                 timestamptz not null default now(),
  eliminado_en              timestamptz
);

-- Pertenencia a una organizacion con un rol propio por equipo.
-- **El aislamiento se resuelve desde aqui**, no desde `perfiles.organizacion_id`:
-- un usuario puede pertenecer a varios equipos, y `perfiles` solo tiene uno (ADR-33).
create table organizaciones_miembros (
  organizacion_id uuid not null references organizaciones(id) on delete cascade,
  usuario_id      uuid not null references auth.users(id) on delete cascade,
  rol             text not null references roles(clave),
  creado_en       timestamptz not null default now(),
  primary key (organizacion_id, usuario_id)
);

-- Sesiones revocadas. El cierre de sesion invalida el token de inmediato (ADR-31).
-- Solo guarda el session_id, nunca el token. Las filas caducan con el token.
create table sesiones_revocadas (
  session_id   text primary key,
  usuario_id   uuid references auth.users(id) on delete cascade,
  revocado_en  timestamptz not null default now(),
  expira_en    timestamptz not null
);

-- Plantillas de extraccion: campos dinamicos sin migrar la BD.
create table plantillas_extraccion (
  id               uuid primary key default gen_random_uuid(),
  organizacion_id  uuid references organizaciones(id),
  nombre           text not null,
  version          int  not null default 1,
  esquema          jsonb not null,   -- {"campos":[{"clave","tipo","descripcion","obligatorio"}]}
  instruccion      text not null,
  activa           boolean not null default true,
  creado_en        timestamptz not null default now(),
  eliminado_en     timestamptz
);

-- Configuracion del motor IA, por usuario o por organizacion.
create table configuracion_motor (
  id                    uuid primary key default gen_random_uuid(),
  usuario_id            uuid references auth.users(id) on delete cascade,
  organizacion_id       uuid references organizaciones(id),
  ambito                text not null,          -- usuario | organizacion
  modelo                text not null,
  modo_ejecucion        text not null,          -- navegador_local | servidor_python
  tamano_chunk_paginas  int  not null default 3,
  overlap_paginas       int  not null default 1,
  ventana_contexto      int  not null default 4096,
  temperatura           numeric(3,2) not null default 0.10,
  actualizado_en        timestamptz not null default now(),
  eliminado_en          timestamptz,
  -- exactamente un ambito por fila
  constraint configuracion_motor_ambito_unico check (
    (ambito = 'usuario'     and usuario_id is not null and organizacion_id is null) or
    (ambito = 'organizacion' and organizacion_id is not null and usuario_id is null)
  )
);

-- Documento analizado.
create table documentos (
  id                uuid primary key default gen_random_uuid(),
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  organizacion_id   uuid references organizaciones(id),
  nombre_archivo    text not null,
  hash_sha256       text not null,
  -- Ruta del objeto en el almacenamiento privado. Nulo mientras no se ha subido.
  ruta_archivo      text,
  tamano_bytes      bigint not null default 0,
  tipo_mime         text not null default 'application/pdf',
  total_paginas     int,
  modo_procesamiento text not null,   -- navegador_local | servidor_python
  estado            text not null default 'en_proceso',  -- en_proceso | completado | error
  error_mensaje     text,
  -- Momento en que el archivo quedo archivado en el bucket privado. Nulo si nunca se subio.
  archivado_en      timestamptz,
  creado_en         timestamptz not null default now(),
  actualizado_en    timestamptz not null default now(),
  eliminado_en      timestamptz
);

-- Documentos compartidos con otro usuario de la misma organizacion.
create table documentos_compartidos (
  documento_id   uuid not null references documentos(id) on delete cascade,
  usuario_id     uuid not null references auth.users(id) on delete cascade,
  compartido_por uuid references auth.users(id) on delete set null,
  creado_en      timestamptz not null default now(),
  primary key (documento_id, usuario_id)
);

-- Bloque analizado (fase Map). Vive en cascada con el documento: no tiene borrado logico.
create table bloques (
  id                  uuid primary key default gen_random_uuid(),
  documento_id        uuid not null references documentos(id) on delete cascade,
  usuario_id          uuid not null references auth.users(id) on delete cascade,
  indice              int  not null,
  pagina_inicio       int  not null,
  pagina_fin          int  not null,
  resumen             text,
  datos_estructurados jsonb not null,
  creado_en           timestamptz not null default now(),
  unique (documento_id, indice)
);

-- Analisis consolidado (fase Reduce). Un analisis vigente por documento.
create table analisis_documentos (
  id                uuid primary key default gen_random_uuid(),
  documento_id      uuid not null unique references documentos(id) on delete cascade,
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  plantilla_id      uuid references plantillas_extraccion(id),
  plantilla_version int,
  -- Modelo que produjo este analisis. Se compara con el del reanálisis para explicar
  -- diferencias que no vienen de la plantilla (HU-10 EC-05).
  modelo            text,
  total_bloques     int,
  resumen_ejecutivo text,
  riesgos           jsonb,
  resumenes         jsonb not null default '[]'::jsonb,  -- un resumen por bloque
  creado_en         timestamptz not null default now()
);

-- Historial de analisis: cuando un documento se reanaliza con otra plantilla, el
-- analisis anterior se mueve aqui en vez de sobrescribirse (ADR-25).
create table analisis_historial (
  id                uuid primary key default gen_random_uuid(),
  documento_id      uuid not null references documentos(id) on delete cascade,
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  plantilla_id      uuid references plantillas_extraccion(id),
  plantilla_version int,
  modelo            text,          -- modelo usado en ese analisis
  resumen_ejecutivo text,
  riesgos           jsonb,
  resumenes         jsonb,
  -- Id del analisis vigente que sustituyo a este.
  reemplazado_por   uuid references analisis_documentos(id),
  creado_en         timestamptz not null default now()
);

-- Seguimiento de un analisis en curso.
create table trabajos (
  id              uuid primary key default gen_random_uuid(),
  documento_id    uuid not null references documentos(id) on delete cascade,
  usuario_id      uuid not null references auth.users(id) on delete cascade,
  tipo            text not null default 'analisis',  -- analisis | reanalisis
  estado          text not null default 'en_cola',
                  -- en_cola | en_proceso | completado | error | cancelado | interrumpido
  progreso        int  not null default 0 check (progreso between 0 and 100),
  paso_actual     text,      -- 'extrayendo' | 'analizando bloque 7 de 50' | 'reduciendo'
  modo            text not null,  -- navegador_local | servidor_python
  iniciado_en     timestamptz,
  finalizado_en   timestamptz,
  duracion_ms     bigint,
  -- Ultimo latido recibido. `creado_en` no sirve: los reportes posteriores no lo
  -- actualizan. Es lo que permite detectar un trabajo abandonado (ADR-24).
  ultimo_latido_en timestamptz,
  error_mensaje   text,
  creado_en       timestamptz not null default now(),
  eliminado_en    timestamptz
);

-- Bitacora de pasos ejecutados (visible en la UI).
create table trabajo_actividades (
  id            uuid primary key default gen_random_uuid(),
  trabajo_id    uuid not null references trabajos(id) on delete cascade,
  -- Clave de idempotencia que envia el cliente. Un reintento de red con el mismo
  -- `id_reporte` no duplica filas (HU-08 CE-06).
  id_reporte    text not null,
  tipo          text not null,   -- extraccion | bloque | reduce | persistencia
  mensaje       text,
  pagina_inicio int,
  pagina_fin    int,
  duracion_ms   int,
  creado_en     timestamptz not null default now(),
  unique (trabajo_id, id_reporte)
);

-- Bitacora de auditoria. Quien hizo que, cuando y desde donde.
create table auditoria (
  id            uuid primary key default gen_random_uuid(),
  organizacion_id uuid references organizaciones(id),
  usuario_id    uuid references auth.users(id) on delete set null,
  actor         text not null,          -- correo o identificador del actor
  accion        text not null,          -- usuario.creado | documento.eliminado | ...
  entidad       text not null,          -- usuario | documento | plantilla | ...
  entidad_id    uuid,
  detalles      jsonb,
  ip            inet,
  user_agent    text,
  creado_en     timestamptz not null default now()
);

-- =============================================================================
-- Indices
-- =============================================================================

create index documentos_org_idx        on documentos (organizacion_id, creado_en desc);
create index documentos_usuario_idx    on documentos (usuario_id, creado_en desc);
create index documentos_estado_idx     on documentos (estado) where estado = 'en_proceso';
create index bloques_documento_idx     on bloques (documento_id, indice);
create index bloques_riesgos_gin       on bloques using gin (datos_estructurados);
create index analisis_documento_idx    on analisis_documentos (documento_id);
create index historial_documento_idx   on analisis_historial (documento_id, creado_en desc);
create index trabajos_documento_idx    on trabajos (documento_id);
-- Soporta la expiracion perezosa: buscar los trabajos activos sin latido reciente.
create index trabajos_latido_idx       on trabajos (estado, ultimo_latido_en);
create index trabajos_usuario_idx      on trabajos (usuario_id, creado_en desc);
create index trabajos_activos_idx      on trabajos (estado) where estado in ('en_cola','en_proceso');
create index trabajo_actividades_idx   on trabajo_actividades (trabajo_id, creado_en);
create index auditoria_org_idx         on auditoria (organizacion_id, creado_en desc);
create index plantillas_org_idx        on plantillas_extraccion (organizacion_id, activa);
create index miembros_usuario_idx      on organizaciones_miembros (usuario_id);
-- Un documento con el mismo contenido no se vuelve a subir mientras siga vivo.
create unique index documentos_hash_unico
  on documentos (usuario_id, hash_sha256) where eliminado_en is null;
