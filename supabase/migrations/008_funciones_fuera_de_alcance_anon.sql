-- =============================================================================
-- 008 — Las funciones RPC salen del alcance de `anon`
--
-- El advisor de Supabase no ve esto, pero la guia oficial de anti-patrones de RLS
-- si. Verificado el 2026-11-28.
--
-- -----------------------------------------------------------------------------
-- EL PROBLEMA
--
-- `public` es el esquema que el Data API expone. Cualquier rol con `EXECUTE` sobre
-- una funcion de `public` puede llamarla por HTTP, **sin token y sin sesion**: ese
-- rol es `anon`.
--
-- Las cinco funciones RPC de `005_funciones_rpc.sql` son `security definer`, asi
-- que se ejecutan con los privilegios del dueno (`postgres`, que tiene
-- `BYPASSRLS`). El RLS **no las protege**: no es el RLS quien decide, es la
-- funcion.
--
-- Comprobado el 2026-11-28 contra el stack local:
--
--     set role anon;
--     select revocar_sesion('sesion-falsa', now() + interval '1 hour');
--     -- INSERT 0 1   <-- escritura sin autenticacion
--
-- `revocar_sesion` no comprobaba nada: cualquier visitor, sin token, revocaba la
-- sesion de cualquier usuario si conocia su `session_id` (que viaja en el JWT).
-- Eso es un denegado de servicio de autenticacion. Las otras tres si validan la
-- propiedad del documento o del trabajo, asi que fallaban, pero por accidente y
-- no por diseno: cualquier funcion nueva en `public` nace con el mismo problema.
--
-- La funcion `mis_permisos()` tambien era alcanzable, aunque devolvia vacio sin
-- sesion.
--
-- -----------------------------------------------------------------------------
-- LA SOLUCION
--
-- Las funciones RPC se mueven al esquema `security`, que no esta expuesto al Data
-- API, y se les revoca `EXECUTE` al rol `anon`.
--
-- El esquema `security` ya existe (migracion 002) y es donde viven las funciones
-- de apoyo de las politicas. Es el sitio natural: es donde van las funciones
-- privilegiadas de este proyecto.
--
-- Por que no basta con revocar a `anon` en `public`: porque una funcion nueva
-- volveria a nacer alcanzable. Moviendo el esquema, el Data API deja de exponer
-- el punto de entrada, y el permiso se vuelve una segunda barrera en vez de la
-- unica.
--
-- Lo que **no** cambia: las funciones siguen siendo `security definer` con
-- `set row_security = off`, porque leen las tablas con los privilegios del dueno
-- para no dispararse a si mismas (ADR-35). Lo que cambia es **quien** puede
-- llamarlas.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Mover las funciones al esquema `security`
--
-- Se recrean con el mismo cuerpo y el mismo `search_path`. El `search_path` de
-- estas funciones ya incluia `public, security` porque llaman a las funciones de
-- apoyo del esquema `security`.
-- -----------------------------------------------------------------------------

create schema if not exists security;

-- --- guardar_analisis -------------------------------------------------------

create or replace function security.guardar_analisis(
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

  -- El documento pasa a `completado`: el pipeline finished.
  update documentos
     set estado = 'completado',
         error_mensaje = null,
         actualizado_en = now()
   where id = p_documento_id;

  return v_analisis_id;
end;
$$;

-- --- registrar_actividad ----------------------------------------------------

create or replace function security.registrar_actividad(
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

-- --- actualizar_trabajo -----------------------------------------------------

create or replace function security.actualizar_trabajo(
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

-- --- mis_permisos -----------------------------------------------------------

create or replace function security.mis_permisos()
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

-- --- revocar_sesion ----------------------------------------------------------

create or replace function security.revocar_sesion(p_session_id text, p_expira_en timestamptz)
returns void
language plpgsql
security definer
set search_path = public, security
set row_security = off
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

-- -----------------------------------------------------------------------------
-- 2. Permisos: solo `authenticated`, nunca `anon`
--
-- `anon` es el rol que atiende las peticiones sin token. Es el unico que no
-- debe poder llegar a una funcion privilegiada.
--
-- Se revoca a `anon` explicitamente y no a `public`: `public` es el rol del que
-- todos heredan, y revocar ahi les quita el permiso tambien a `authenticated`.
-- Por eso cada `revoke` va seguido de su `grant`.
-- -----------------------------------------------------------------------------

revoke execute on function security.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) from anon;
grant  execute on function security.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) to authenticated;

revoke execute on function security.registrar_actividad(uuid, text, text, text, int, int, int) from anon;
grant  execute on function security.registrar_actividad(uuid, text, text, text, int, int, int) to authenticated;

revoke execute on function security.actualizar_trabajo(uuid, text, int, text, text) from anon;
grant  execute on function security.actualizar_trabajo(uuid, text, int, text, text) to authenticated;

revoke execute on function security.mis_permisos() from anon;
grant  execute on function security.mis_permisos() to authenticated;

revoke execute on function security.revocar_sesion(text, timestamptz) from anon;
grant  execute on function security.revocar_sesion(text, timestamptz) to authenticated;

-- Las funciones de apoyo de las politicas tambien se cierran al rol `anon`.
-- Sin sesion devuelven `false` o `{}`, asi que no habian dado acceso a nada, pero
-- un `EXECUTE` de mas es un `EXECUTE` de mas: una funcion nueva que se apoya en
-- ellas no tendria la barrera.
--
-- OJO: se revoca a `anon` **explicitamente**, no a `public`. `public` es el rol del
-- que todos heredan, y revocar ahi les quita el permiso tambien a `authenticated`.
-- La primera version de esta migracion lo hacia, y las politicas se quedaron sin
-- poder llamar a sus propias funciones de apoyo ("permission denied for function
-- organizacion_activa"). Verificado el 2026-11-28.
revoke execute on function security.organizacion_activa() from anon;
revoke execute on function security.es_usuario_activo() from anon;
revoke execute on function security.usuario_tiene_permiso(text) from anon;
revoke execute on function security.es_miembro_de(uuid) from anon;
revoke execute on function security.documento_visible(uuid) from anon;
revoke execute on function security.documento_compartido_conmigo(uuid) from anon;
revoke execute on function security.documento_es_mio(uuid) from anon;
revoke execute on function security.documento_de_mi_organizacion(uuid) from anon;
revoke execute on function security.trabajo_es_mio(uuid) from anon;

-- Y se le devuelven a `authenticated`, que es quien los necesita: las politicas se
-- ejecutan con los privilegios del rol de la peticion.
grant execute on function security.organizacion_activa() to authenticated;
grant execute on function security.es_usuario_activo() to authenticated;
grant execute on function security.usuario_tiene_permiso(text) to authenticated;
grant execute on function security.es_miembro_de(uuid) to authenticated;
grant execute on function security.documento_visible(uuid) to authenticated;
grant execute on function security.documento_compartido_conmigo(uuid) to authenticated;
grant execute on function security.documento_es_mio(uuid) to authenticated;
grant execute on function security.documento_de_mi_organizacion(uuid) to authenticated;
grant execute on function security.trabajo_es_mio(uuid) to authenticated;

-- -----------------------------------------------------------------------------
-- 3. Las funciones viejas de `public` se borran
--
-- Si se dejaran, seguirian siendo alcanzables por el Data API. Se eliminan para
-- que no haya dos puertas a la misma logica: la de `public`, abierta, y la de
-- `security`, cerrada.
-- -----------------------------------------------------------------------------

drop function if exists guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb);
drop function if exists registrar_actividad(uuid, text, text, text, int, int, int);
drop function if exists actualizar_trabajo(uuid, text, int, text, text);
drop function if exists mis_permisos();
drop function if exists revocar_sesion(text, timestamptz);

-- -----------------------------------------------------------------------------
-- 4. `FORCE ROW LEVEL SECURITY`
--
-- Sin esta linea, el **dueno** de la tabla (aqui `postgres`, que tiene
-- `BYPASSRLS`) no respeta el RLS. Eso es lo que exploited el punto 1: las
-- funciones `security definer` corrian con los privilegios del dueno.
--
-- Con `FORCE`, el RLS se aplica tambien al dueno. Y las funciones del esquema
-- `security` siguen leyendo lo que necesitan, porque declaran
-- `set row_security = off`, que es lo que desactiva el RLS **para esa llamada**.
--
-- Es decir: `FORCE` cierra la puerta y `row_security = off` es la llave
-- controlled que usan las funciones privilegiadas. Las dos van juntas.
--
-- Nota: `FORCE` no cambia el comportamiento de `service_role`, que tiene
-- `BYPASSRLS` como rol y no como dueno. El adaptador de administracion (ADR-13)
-- sigue viendo todo, como debe.
-- -----------------------------------------------------------------------------

alter table organizaciones                  force row level security;
alter table roles                           force row level security;
alter table permisos                        force row level security;
alter table rol_permisos                    force row level security;
alter table perfiles                        force row level security;
alter table organizaciones_miembros         force row level security;
alter table sesiones_revocadas             force row level security;
alter table plantillas_extraccion           force row level security;
alter table configuracion_motor             force row level security;
alter table documentos                      force row level security;
alter table documentos_compartidos          force row level security;
alter table bloques                         force row level security;
alter table analisis_documentos             force row level security;
alter table analisis_historial              force row level security;
alter table trabajos                        force row level security;
alter table trabajo_actividades             force row level security;
alter table auditoria                       force row level security;
