-- =============================================================================
-- 005 — Funciones RPC (atomicidad en Postgres)
--
-- El camino de ejecucion del backend usa HTTP (PostgREST/RPC), nunca TCP a Postgres.
-- Por eso la atomicidad va aqui: funciones `security definer` que hacen una unidad
-- de trabajo y devuelven el resultado en una sola llamada.
--
-- Reglas de seguridad de una funcion `security definer`:
-- - `set search_path` explicito: sin esto, un objeto malicioso en otro esquema
--   podria interceptar las referencias. Se incluye `security` porque estas funciones
--   llaman a las de apoyo de ese esquema.
-- - `revoke execute` al publico y `grant execute` solo a `authenticated`.
-- - El cuerpo no acepta `service_role`: el permiso se comprueba con las mismas
--   funciones que usa el RLS.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Guardar un analisis completo en una sola transaccion
--
-- Persiste el resultado del pipeline: el analisis vigente, sus bloques y su
-- historial. Si algo falla a mitad, no queda analisis sin bloques.
-- -----------------------------------------------------------------------------

create or replace function guardar_analisis(
  p_documento_id        uuid,
  p_plantilla_id        uuid,
  p_plantilla_version   int,
  p_modelo              text,
  p_total_bloques       int,
  p_resumen_ejecutivo   text,
  p_riesgos             jsonb,
  p_resumenes           jsonb,
  p_bloques             jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public, security
set row_security = off
as $$
declare
  v_usuario_id  uuid;
  v_analisis_id uuid;
  v_analisis_anterior uuid;
begin
  -- El documento tiene que ser del usuario autenticado: el permiso de fila se
  -- comprueba aqui y no solo en la politica.
  select d.usuario_id, d.organizacion_id
    into v_usuario_id
    from documentos d
   where d.id = p_documento_id
     and d.eliminado_en is null
     and d.usuario_id = auth.uid();

  if v_usuario_id is null then
    raise exception 'documento no encontrado o no pertenece al usuario'
      using errcode = 'P0002';
  end if;

  if not security.usuario_tiene_permiso('documentos.analizar') then
    raise exception 'sin permiso para analizar'
      using errcode = '42501';
  end if;

  -- El analisis vigente anterior pasa al historial (ADR-25). Es append-only: no se
  -- borra nada, lo anterior queda referenciado.
  select id into v_analisis_anterior
    from analisis_documentos
   where documento_id = p_documento_id;

  if v_analisis_anterior is not null then
    insert into analisis_historial (
      documento_id, usuario_id, plantilla_id, plantilla_version, modelo,
      resumen_ejecutivo, riesgos, resumenes, creado_en
    )
    select
      documento_id, usuario_id, plantilla_id, plantilla_version, modelo,
      resumen_ejecutivo, riesgos, resumenes, now()
    from analisis_documentos
    where id = v_analisis_anterior;
  end if;

  -- Los bloques se reescriben: un analisis nuevo sobre el mismo documento tiene
  -- bloques nuevos. Se borran los anteriores porque cuelgan del analisis, no del
  -- historial (el historial guarda el resultado, no los bloques crudos).
  delete from bloques where documento_id = p_documento_id;

  insert into bloques (
    documento_id, usuario_id, indice, pagina_inicio, pagina_fin,
    resumen, datos_estructurados
  )
  select
    p_documento_id,
    v_usuario_id,
    (b ->> 'indice')::int,
    (b ->> 'pagina_inicio')::int,
    (b ->> 'pagina_fin')::int,
    b ->> 'resumen',
    coalesce(b -> 'datos_estructurados', '{}'::jsonb)
  from jsonb_array_elements(p_bloques) as b;

  -- El analisis vigente: se actualiza si ya habia uno, se inserta si no.
  insert into analisis_documentos (
    documento_id, usuario_id, plantilla_id, plantilla_version, modelo,
    total_bloques, resumen_ejecutivo, riesgos, resumenes
  )
  values (
    p_documento_id, v_usuario_id, p_plantilla_id, p_plantilla_version, p_modelo,
    p_total_bloques, p_resumen_ejecutivo, p_riesgos, p_resumenes
  )
  on conflict (documento_id) do update
    set plantilla_id      = excluded.plantilla_id,
        plantilla_version = excluded.plantilla_version,
        modelo            = excluded.modelo,
        total_bloques     = excluded.total_bloques,
        resumen_ejecutivo = excluded.resumen_ejecutivo,
        riesgos           = excluded.riesgos,
        resumenes         = excluded.resumenes,
        creado_en         = now()
  returning id into v_analisis_id;

  -- El historial apunta al analisis que lo sustituyo.
  if v_analisis_anterior is not null then
    update analisis_historial
       set reemplazado_por = v_analisis_id
     where documento_id = p_documento_id
       and reemplazado_por is null;
  end if;

  -- El documento pasa a `completado`: el pipelinefinished.
  update documentos
     set estado = 'completado',
         error_mensaje = null,
         actualizado_en = now()
   where id = p_documento_id;

  return v_analisis_id;
end;
$$;

revoke execute on function guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) from public;
grant execute on function guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) to authenticated;

-- -----------------------------------------------------------------------------
-- Registrar un reporte de progreso del trabajo
--
-- El cliente reporta cada paso del pipeline. El `id_reporte` es la clave de
-- idempotencia: un reintento de red con el mismo id no duplica filas (HU-08 CE-06).
-- -----------------------------------------------------------------------------

create or replace function registrar_actividad(
  p_trabajo_id     uuid,
  p_id_reporte     text,
  p_tipo           text,
  p_mensaje        text,
  p_pagina_inicio  int,
  p_pagina_fin    int,
  p_duracion_ms    int
)
returns void
language plpgsql
security definer
set search_path = public, security
set row_security = off
as $$
begin
  if not exists (
    select 1
    from trabajos t
    where t.id = p_trabajo_id
      and t.usuario_id = auth.uid()
  ) then
    raise exception 'trabajo no encontrado o no pertenece al usuario'
      using errcode = 'P0002';
  end if;

  insert into trabajo_actividades (
    trabajo_id, id_reporte, tipo, mensaje,
    pagina_inicio, pagina_fin, duracion_ms
  )
  values (
    p_trabajo_id, p_id_reporte, p_tipo, p_mensaje,
    p_pagina_inicio, p_pagina_fin, p_duracion_ms
  )
  on conflict (trabajo_id, id_reporte) do nothing;
end;
$$;

revoke execute on function registrar_actividad(uuid, text, text, text, int, int, int) from public;
grant execute on function registrar_actividad(uuid, text, text, text, int, int, int) to authenticated;

-- -----------------------------------------------------------------------------
-- Actualizar el progreso de un trabajo
--
-- Calcula la duracion en el servidor, no en el cliente: el unico reloj que cuenta es
-- el del servidor (ARQUITECTURA.md seccion 6.7).
-- -----------------------------------------------------------------------------

create or replace function actualizar_trabajo(
  p_trabajo_id   uuid,
  p_estado       text,
  p_progreso     int,
  p_paso_actual  text,
  p_error        text
)
returns void
language plpgsql
security definer
set search_path = public, security
set row_security = off
as $$
begin
  if not exists (
    select 1
    from trabajos t
    where t.id = p_trabajo_id
      and t.usuario_id = auth.uid()
  ) then
    raise exception 'trabajo no encontrado o no pertenece al usuario'
      using errcode = 'P0002';
  end if;

  update trabajos
     set estado          = coalesce(p_estado, estado),
         progreso        = coalesce(p_progreso, progreso),
         paso_actual     = coalesce(p_paso_actual, paso_actual),
         error_mensaje   = p_error,
         iniciado_en     = coalesce(iniciado_en, case when p_estado = 'en_proceso' then now() end),
         finalizado_en   = case
                             when p_estado in ('completado', 'error', 'cancelado') then now()
                             else null
                           end,
         duracion_ms     = case
                             when p_estado in ('completado', 'error', 'cancelado')
                               and iniciado_en is not null
                             then extract(epoch from (now() - iniciado_en)) * 1000
                             else duracion_ms
                           end,
         ultimo_latido_en = now()
   where id = p_trabajo_id;
end;
$$;

revoke execute on function actualizar_trabajo(uuid, text, int, text, text) from public;
grant execute on function actualizar_trabajo(uuid, text, int, text, text) to authenticated;

-- -----------------------------------------------------------------------------
-- Resolver los permisos del usuario autenticado
--
-- El backend los pide por HTTP (no TCP). Esta funcion devuelve el conjunto de
-- permisos efectivos, para que el frontend decida que mostrar sin adivinar.
-- -----------------------------------------------------------------------------

create or replace function mis_permisos()
returns text[]
language sql stable
security definer
set search_path = public, security
set row_security = off
as $$
  select coalesce(array_agg(distinct rp.permiso), '{}')
    from organizaciones_miembros m
    join rol_permisos rp on rp.rol = m.rol
    join perfiles p on p.id = m.usuario_id
   where m.usuario_id = auth.uid()
     and m.organizacion_id = security.organizacion_activa()
     and p.activo
     and p.eliminado_en is null;
$$;

revoke execute on function mis_permisos() from public;
grant execute on function mis_permisos() to authenticated;

-- -----------------------------------------------------------------------------
-- Revocar la sesion actual
--
-- El cierre de sesion invalida el token de inmediato (ADR-31). Se guarda el
-- `session_id`, nunca el token. La fila caduca con el token (`expira_en`).
-- -----------------------------------------------------------------------------

create or replace function revocar_sesion(p_session_id text, p_expira_en timestamptz)
returns void
language plpgsql
security definer
set search_path = public, security
set row_security = off
as $$
begin
  insert into sesiones_revocadas (session_id, usuario_id, expira_en)
  values (p_session_id, auth.uid(), p_expira_en)
  on conflict (session_id) do update
    set revocado_en = now(),
        expira_en   = excluded.expira_en;
end;
$$;

revoke execute on function revocar_sesion(text, timestamptz) from public;
grant execute on function revocar_sesion(text, timestamptz) to authenticated;
