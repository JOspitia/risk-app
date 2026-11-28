-- =============================================================================
-- 010 — Devolver las funciones RPC al esquema `public` con permisos cerrados
--
-- PROBLEMA
--
-- La migracion 008 movio las cinco funciones RPC al esquema `security` para
-- sacarlas del alcance del rol `anon`. El efecto secundario fue que **dejaron de
-- ser invocables por HTTP**: PostgREST solo resuelve funciones de los esquemas que
-- expone, y su lista por defecto es `public`. Verificado el 2026-11-28 contra el
-- proyecto en la nube: `POST /rest/v1/rpc/mis_permisos` respondia
--
--     PGRST202: Searched for the function public.mis_permisos ... no matches
--
-- Y las variantes con esquema (`rpc/security.mis_permisos`, `rpc/public.mis_permisos`)
-- tampoco: PostgREST no acepta el esquema en la ruta de RPC.
--
-- POR QUE NO SE RESUELVE EN EL PANEL
--
-- Habria dos caminos que no tocan el codigo:
--
--   (a) Configurar `extra_search_path` en Settings -> API -> Data API para exponer
--       `security` en el `search_path` del Data API.
--   (b) Configurar `db_schemas = "public,security"`.
--
-- Los dos dependen de una intervencion manual en el panel de cada proyecto y no
-- quedan en el codigo, asi que un `supabase db reset` o un proyecto nuevo los
-- pierde. Este proyecto despliega por migraciones versionadas: lo que no esta en
-- una migracion no esta desplegado.
--
-- LA VIA QUE SE TOMA
--
-- Devolver las funciones a `public` **con el ACL correcto**. No basta con moverlas:
-- hay que revocar a `public` (el rol del que todos heredan) y volver a dar el
-- permiso a `authenticated`, en ese orden.
--
-- Con esto se cumplen las dos cosas a la vez:
--
--   - `anon` NO puede ejecutarlas. Se verifica con `set role anon` en la suite.
--   - El backend y el frontend las invocan por HTTP, que es como ADR-04 dice que
--     se accede a los datos.
--
-- La proteccion real de estas funciones no es el ACL: es que todas son
-- `security definer` con `set row_security = off` y **comprueban la pertenencia
-- en su propio cuerpo** (`auth.uid()`, `security.usuario_tiene_permiso(...)`).
-- Una funcion que se deja correr sin sesion no puede hacer nada util: lo unico
-- que hace es fallar la comprobacion interna y devolver un error. El ACL evita
-- el ruido; el cuerpo de la funcion es la puerta.
--
-- -----------------------------------------------------------------------------
-- NOTA SOBRE EL ESQUEMA `security`
--
-- El esquema `security` **se queda**. Siguen ahi las nueve funciones de apoyo de
-- las politicas de RLS (`organizacion_activa`, `es_usuario_activo`, ...), que si
-- necesitan el esquema separado para no disparar recursion de RLS (ADR-35).
-- Lo que cambia es que las cinco funciones RPC de negocio vuelven a `public`.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Las cinco funciones RPC vuelven a `public`
--
-- El cuerpo no cambia ni un caracter: son las mismas funciones que ya se
-- verificaron en la nube. Lo unico que cambia es el esquema.
-- -----------------------------------------------------------------------------

create or replace function public.guardar_analisis(
  p_documento_id      uuid,
  p_plantilla_id      uuid,
  p_plantilla_version integer,
  p_modelo            text,
  p_total_bloques     integer,
  p_resumen_ejecutivo text,
  p_riesgos           jsonb,
  p_resumenes         jsonb,
  p_bloques           jsonb
)
returns uuid
language plpgsql
security definer
set search_path to 'public', 'security'
set row_security to 'off'
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

  -- El documento pasa a `completado`: el pipeline finished.
  update documentos
     set estado = 'completado',
         error_mensaje = null,
         actualizado_en = now()
   where id = p_documento_id;

  return v_analisis_id;
end;
$$;

create or replace function public.registrar_actividad(
  p_trabajo_id     uuid,
  p_id_reporte     text,
  p_tipo           text,
  p_mensaje        text,
  p_pagina_inicio  integer,
  p_pagina_fin     integer,
  p_duracion_ms    integer
)
returns void
language plpgsql
security definer
set search_path to 'public', 'security'
set row_security to 'off'
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

create or replace function public.actualizar_trabajo(
  p_trabajo_id   uuid,
  p_estado       text,
  p_progreso     integer,
  p_paso_actual  text,
  p_error        text
)
returns void
language plpgsql
security definer
set search_path to 'public', 'security'
set row_security to 'off'
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

create or replace function public.mis_permisos()
returns text[]
language sql
stable
security definer
set search_path to 'public', 'security'
set row_security to 'off'
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

create or replace function public.revocar_sesion(
  p_session_id text,
  p_expira_en  timestamptz
)
returns void
language plpgsql
security definer
set search_path to 'public', 'security'
set row_security to 'off'
as $$
begin
  -- La sesion que se revoca tiene que ser **del usuario que llama**. Sin esta
  -- comprobacion, un visitante sin sesion revocaba la sesion de cualquier otro
  -- que conociera su `session_id`. Verificado el 2026-11-28: era el hueco que
  -- permitia la escritura sin autenticacion.
  if not exists (
    select 1
    from sesiones_revocadas s
    join auth.users u on u.id = s.usuario_id
    where s.session_id = p_session_id
      and s.usuario_id = auth.uid()
  ) then
    raise exception 'la sesion no pertenece al usuario autenticado'
      using errcode = '42501';
  end if;

  insert into sesiones_revocadas (session_id, usuario_id, expira_en)
  values (p_session_id, auth.uid(), p_expira_en)
  on conflict (session_id) do update
    set revocado_en = now(),
        expira_en   = excluded.expira_en;
end;
$$;

-- Las copias del esquema `security` se van: si se dejan, quedan dos funciones con
-- el mismo nombre en la base y la de `public` no es la unica que existe. Se
-- eliminan con `cascade` porque ninguna politica las referencia por nombre
-- completo (las politicas usan `security.organizacion_activa()` y las funciones
-- de apoyo se quedan).
drop function if exists security.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) cascade;
drop function if exists security.registrar_actividad(uuid, text, text, text, int, int, int) cascade;
drop function if exists security.actualizar_trabajo(uuid, text, int, text, text) cascade;
drop function if exists security.mis_permisos() cascade;
drop function if exists security.revocar_sesion(text, timestamptz) cascade;

-- -----------------------------------------------------------------------------
-- 2. El ACL de las funciones RPC
--
-- El orden importa: primero se revoca al rol `public` (el rol del que todos
-- heredan) y despues se da el permiso a `authenticated`. Al reves, el `grant` se
-- pierde.
--
-- Verificado el 2026-11-28 en la nube: revocar solo a `anon` no alcanza, porque
-- el privilegio heredado de `public` se conserva. El ACL tiene que quedar:
--
--     {postgres=X/postgres,authenticated=X/postgres}
--
-- Sin el `=X` de la izquierda, que es el rol `public`.
--
-- Y hay que revocar **a `anon` explicitamente**, no solo a `public`. La migracion
-- 008 habia dejado un privilegio directo de `EXECUTE` para `anon`, y ese
-- privilegio directo sobrevive al `revoke` hecho sobre `public`: revocar al rol
-- del que se hereda no quita un permiso que se concedio directamente.
--
-- Verificado el 2026-11-28 en el stack local: con el `revoke` solo sobre `public`
-- el ACL de las cinco funciones quedaba
--
--     {postgres=X,anon=X,authenticated=X,service_role=X}
--
-- y `set role anon` las ejecutaba sin error. Con el `revoke` explicito a `anon`
-- el ACL queda
--
--     {postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres}
--
-- -----------------------------------------------------------------------------

revoke execute on function public.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) from public;
revoke execute on function public.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) from anon;
grant  execute on function public.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) to authenticated;

revoke execute on function public.registrar_actividad(uuid, text, text, text, int, int, int) from public;
revoke execute on function public.registrar_actividad(uuid, text, text, text, int, int, int) from anon;
grant  execute on function public.registrar_actividad(uuid, text, text, text, int, int, int) to authenticated;

revoke execute on function public.actualizar_trabajo(uuid, text, int, text, text) from public;
revoke execute on function public.actualizar_trabajo(uuid, text, int, text, text) from anon;
grant  execute on function public.actualizar_trabajo(uuid, text, int, text, text) to authenticated;

revoke execute on function public.mis_permisos() from public;
revoke execute on function public.mis_permisos() from anon;
grant  execute on function public.mis_permisos() to authenticated;

revoke execute on function public.revocar_sesion(text, timestamptz) from public;
revoke execute on function public.revocar_sesion(text, timestamptz) from anon;
grant  execute on function public.revocar_sesion(text, timestamptz) to authenticated;

-- -----------------------------------------------------------------------------
-- 3. Comprobacion
--
-- El ACL de cada una tiene que quedar sin el `=X` de la izquierda y con
-- `authenticated=X`.
-- -----------------------------------------------------------------------------
