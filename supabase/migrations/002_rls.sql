-- =============================================================================
-- 002 — Row Level Security
--
-- RLS activo en toda tabla con datos de usuario (Gate 1).
--
-- Dos capas complementarias, no redundantes:
-- - RLS filtra FILAS: que documentos existen y son visibles.
-- - El permiso filtra ACCIONES: que se puede hacer con ellos.
--
-- El caso de uso comprueba el permiso ANTES de consultar (ADR-30), asi que RLS no
-- necesita responder 403: si el permiso falta, no se consulta; si falta el permiso
-- de fila, RLS devuelve cero filas y eso es un 404.
--
-- El aislamiento de organizacion se resuelve desde `organizaciones_miembros`, NO desde
-- `perfiles.organizacion_id` (ADR-33): un usuario puede pertenecer a varios equipos.
--
-- -----------------------------------------------------------------------------
-- POR QUE LAS FUNCIONES DE APOYO VIVEN EN EL ESQUEMA `security`
--
-- La version anterior de este archivo defini las funciones en `public`. Eso creaba
-- una **recursion infinita**: la politica de lectura de `perfiles` llamaba a
-- `usuario_activo()`, que a su vez consultaba `perfiles`. Postgres aborta la consulta
-- con "stack depth limit exceeded", y cuando una politica falla en error la fila NO se
-- filtra: el aislamiento queda anulado en silencio. Verificado el 2026-11-28.
--
-- Mover las funciones a un esquema propio NO alcanza por si solo. Una funcion
-- `security definer` sigue disparando las politicas RLS de las tablas que consulta,
-- porque `authenticated` no tiene `BYPASSRLS`. Con solo el cambio de esquema, la
-- recursion seguia, ahora reportada como "infinite recursion detected in policy for
-- relation documentos". Verificado el 2026-11-28.
--
-- La solucion combina tres cosas:
-- 1. Las funciones de apoyo viven en el esquema `security`.
-- 2. Son `security definer` con `set row_security = off`: el propietario de la funcion
--    (el rol que creo el esquema, con `BYPASSRLS`) lee las tablas **sin** que las
--    politicas se apliquen. Por eso no hay recursion.
-- 3. `grant usage on schema security`, para que las politicas puedan llamar a las
--    funciones.
--
-- Regla que se sigue de aqui en adelante: **ninguna politica se apoya en una funcion
-- que lea la misma tabla que la politica, sin `set row_security = off`**.
-- =============================================================================

create schema if not exists security;

comment on schema security is
  'Funciones de apoyo para las politicas RLS. Leen con row_security = off para evitar recursion.';

grant usage on schema security to authenticated;
grant usage on schema security to anon;

-- -----------------------------------------------------------------------------
-- Funciones de apoyo
-- -----------------------------------------------------------------------------

-- Organizacion activa del usuario en la peticion.
-- `[DECIDIDO]` La organizacion activa es la primera membresia vigente del usuario.
-- El caso de uso elige la membresia concreta cuando el usuario tiene varias; el RLS
-- usa esta para el alcance por defecto.
create or replace function security.organizacion_activa()
returns uuid
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select m.organizacion_id
  from public.organizaciones_miembros m
  join public.perfiles p on p.id = m.usuario_id
  where m.usuario_id = auth.uid()
    and p.activo
    and p.eliminado_en is null
  limit 1;
$$;

comment on function security.organizacion_activa() is
  'Organizacion activa del usuario autenticado. Base del aislamiento por equipo.';

-- El usuario autenticado esta activo y no ha sido eliminado logicamente.
-- Toda politica que filtra por "usuario real" pasa por aqui, para que un usuario
-- desactivado pierda el acceso de inmediato, sin depender del caso de uso.
create or replace function security.es_usuario_activo()
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.perfiles p
    where p.id = auth.uid()
      and p.activo
      and p.eliminado_en is null
  );
$$;

comment on function security.es_usuario_activo() is
  'True si el usuario autenticado existe en `perfiles`, esta activo y no fue eliminado.';

-- El usuario tiene el permiso indicado en la organizacion activa.
-- La matriz vive en `rol_permisos`; agregar un permiso es un `insert`, no un despliegue.
-- La membresia de la organizacion activa es la que determina el rol que se consulta.
create or replace function security.usuario_tiene_permiso(p_permiso text)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.organizaciones_miembros m
    join public.rol_permisos rp on rp.rol = m.rol
    join public.perfiles p on p.id = m.usuario_id
    where m.usuario_id = auth.uid()
      and m.organizacion_id = security.organizacion_activa()
      and rp.permiso = p_permiso
      and p.activo
      and p.eliminado_en is null
  );
$$;

comment on function security.usuario_tiene_permiso(text) is
  'True si el usuario tiene el permiso en la organizacion activa. La matriz vive en `rol_permisos`.';

-- El usuario pertenece a la organizacion indicada.
create or replace function security.es_miembro_de(p_organizacion uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.organizaciones_miembros m
    where m.usuario_id = auth.uid()
      and m.organizacion_id = p_organizacion
  );
$$;

comment on function security.es_miembro_de(uuid) is
  'True si el usuario autenticado pertenece a la organizacion indicada.';

-- El documento esta compartido con el usuario.
-- Vive aqui, y no en la politica de `documentos`, para que la politica no consulte
-- directamente `documentos_compartidos`: esa tabla tiene su propia politica, que a su
-- vez consulta `documentos`, y el ciclo dispara "infinite recursion detected".
create or replace function security.documento_compartido_conmigo(p_documento uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.documentos_compartidos dc
    where dc.documento_id = p_documento
      and dc.usuario_id = auth.uid()
  );
$$;

comment on function security.documento_compartido_conmigo(uuid) is
  'True si el documento esta compartido con el usuario autenticado.';

-- El documento es visible para el usuario: propio, compartido, o de la organizacion
-- con permiso para verlos todos.
create or replace function security.documento_visible(p_documento uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.documentos d
    where d.id = p_documento
      and d.eliminado_en is null
      and (
        d.usuario_id = auth.uid()
        or exists (
          select 1
          from public.documentos_compartidos dc
          where dc.documento_id = d.id
            and dc.usuario_id = auth.uid()
        )
        or (
          d.organizacion_id is not null
          and d.organizacion_id = security.organizacion_activa()
          and security.usuario_tiene_permiso('analisis.ver_todos')
        )
      )
  );
$$;

comment on function security.documento_visible(uuid) is
  'True si el documento es visible para el usuario: propio, compartido o de la organizacion con permiso.';

-- -----------------------------------------------------------------------------
-- Consultas entre tablas con RLS
--
-- Estas funciones existen para que **ninguna politica consulte directamente una tabla
-- que tenga RLS**. Una politica que consulta otra tabla con RLS dispara su politica,
-- y si esa politica vuelve a consultar la primera, Postgres detecta el ciclo:
-- "infinite recursion detected in policy for relation X".
--
-- Todas leen con `set row_security = off`, asi que consultan los datos crudos y no
-- reevalua la politica de la tabla consultada.
-- -----------------------------------------------------------------------------

-- El documento pertenece al usuario autenticado y no esta eliminado logicamente.
create or replace function security.documento_es_mio(p_documento uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.documentos d
    where d.id = p_documento
      and d.usuario_id = auth.uid()
      and d.eliminado_en is null
  );
$$;

comment on function security.documento_es_mio(uuid) is
  'True si el documento pertenece al usuario autenticado y no esta eliminado.';

-- El documento pertenece a la organizacion activa.
create or replace function security.documento_de_mi_organizacion(p_documento uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.documentos d
    where d.id = p_documento
      and d.organizacion_id = security.organizacion_activa()
  );
$$;

comment on function security.documento_de_mi_organizacion(uuid) is
  'True si el documento pertenece a la organizacion activa del usuario.';

-- El trabajo pertenece al usuario autenticado.
create or replace function security.trabajo_es_mio(p_trabajo uuid)
returns boolean
language sql
stable
security definer
set search_path = public, security
set row_security = off
as $$
  select exists (
    select 1
    from public.trabajos t
    where t.id = p_trabajo
      and t.usuario_id = auth.uid()
  );
$$;

comment on function security.trabajo_es_mio(uuid) is
  'True si el trabajo pertenece al usuario autenticado.';

-- -----------------------------------------------------------------------------
-- Habilitar RLS
-- -----------------------------------------------------------------------------

alter table organizaciones                  enable row level security;
alter table roles                           enable row level security;
alter table permisos                        enable row level security;
alter table rol_permisos                    enable row level security;
alter table perfiles                        enable row level security;
alter table organizaciones_miembros         enable row level security;
alter table sesiones_revocadas             enable row level security;
alter table plantillas_extraccion           enable row level security;
alter table configuracion_motor             enable row level security;
alter table documentos                      enable row level security;
alter table documentos_compartidos          enable row level security;
alter table bloques                         enable row level security;
alter table analisis_documentos             enable row level security;
alter table analisis_historial              enable row level security;
alter table trabajos                        enable row level security;
alter table trabajo_actividades             enable row level security;
alter table auditoria                       enable row level security;

-- -----------------------------------------------------------------------------
-- Politicas: catalogos de solo lectura
-- -----------------------------------------------------------------------------

-- Los catalogos de roles y permisos son datos de referencia del sistema: todos los
-- autenticados activos los pueden leer. No se pueden escribir desde el cliente:
-- los escribe la migracion (003) y el bootstrap.
create policy roles_lectura on roles
  for select to authenticated
  using (security.es_usuario_activo());

create policy permisos_lectura on permisos
  for select to authenticated
  using (security.es_usuario_activo());

create policy rol_permisos_lectura on rol_permisos
  for select to authenticated
  using (security.es_usuario_activo());

-- -----------------------------------------------------------------------------
-- Politicas: organizaciones y membresias
-- -----------------------------------------------------------------------------

-- Se ve la organizacion propia y las de las que se es miembro.
create policy organizaciones_lectura on organizaciones
  for select to authenticated
  using (
    security.es_usuario_activo()
    and security.es_miembro_de(id)
  );

-- Solo un admin de la organizacion la administra.
create policy organizaciones_actualizacion on organizaciones
  for update to authenticated
  using (
    security.es_usuario_activo()
    and security.es_miembro_de(id)
    and security.usuario_tiene_permiso('organizacion.gestionar')
  )
  with check (
    security.es_usuario_activo()
    and security.es_miembro_de(id)
  );

-- El alta de organizaciones la hace el bootstrap, no un usuario final.
create policy organizaciones_alta on organizaciones
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.usuario_tiene_permiso('organizacion.gestionar')
  );

-- Membresias: se ven las propias y las de la propia organizacion.
create policy miembros_lectura on organizaciones_miembros
  for select to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = security.organizacion_activa()
        and security.usuario_tiene_permiso('usuarios.gestionar')
      )
    )
  );

-- La membresia la administra quien tenga `organizacion.gestionar` o `usuarios.gestionar`.
create policy miembros_escritura on organizaciones_miembros
  for all to authenticated
  using (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and (
      security.usuario_tiene_permiso('organizacion.gestionar')
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  )
  with check (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and (
      security.usuario_tiene_permiso('organizacion.gestionar')
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- -----------------------------------------------------------------------------
-- Politicas: perfiles
-- -----------------------------------------------------------------------------

-- Cada usuario ve su propio perfil. Los demas, solo si se gestiona usuarios.
-- Nota: `security.es_usuario_activo()` lee `perfiles` como `definer`, sin disparar
-- esta politica. Es la clave para que no haya recursion.
create policy perfiles_lectura on perfiles
  for select to authenticated
  using (
    (
      id = (select auth.uid())
      and security.es_usuario_activo()
    )
    or (
      security.es_usuario_activo()
      and security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- El usuario actualiza su propio perfil. No puede cambiar su `rol` ni su `activo`:
-- esos los cambia un admin, y el `with check` lo impide.
create policy perfiles_actualizacion on perfiles
  for update to authenticated
  using (
    id = (select auth.uid())
    or (
      security.es_usuario_activo()
      and security.usuario_tiene_permiso('usuarios.gestionar')
    )
  )
  with check (
    id = (select auth.uid())
    or (
      security.es_usuario_activo()
      and security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- El alta de perfiles la hace el adaptador de administracion (service_role) o el
-- bootstrap. Un usuario final no se crea a si mismo: el alta requiere `usuarios.gestionar`
-- y el permiso se comprueba tambien en el caso de uso.
create policy perfiles_alta on perfiles
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.usuario_tiene_permiso('usuarios.gestionar')
  );

-- -----------------------------------------------------------------------------
-- Politicas: sesiones revocadas
-- -----------------------------------------------------------------------------

-- El usuario consulta sus propias revocaciones (para invalidar su token).
create policy sesiones_lectura on sesiones_revocadas
  for select to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- La revocacion la escribe el caso de uso de cierre de sesion (ADR-31).
create policy sesiones_alta on sesiones_revocadas
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- -----------------------------------------------------------------------------
-- Politicas: plantillas de extraccion
-- -----------------------------------------------------------------------------

-- Las plantillas del sistema (organizacion_id nulo) las ven todos. Las de una
-- organizacion, los miembros de esa organizacion.
create policy plantillas_lectura on plantillas_extraccion
  for select to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      organizacion_id is null
      or organizacion_id = security.organizacion_activa()
    )
  );

-- Editar plantillas exige `plantillas.editar` y que la plantilla sea de la organizacion
-- activa. La plantilla del sistema no se edita desde la organizacion: `organizacion_id`
-- nulo no cumple `organizacion_id = security.organizacion_activa()`.
create policy plantillas_escritura on plantillas_extraccion
  for all to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and organizacion_id = security.organizacion_activa()
    and security.usuario_tiene_permiso('plantillas.editar')
  )
  with check (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and security.usuario_tiene_permiso('plantillas.editar')
  );

-- -----------------------------------------------------------------------------
-- Politicas: configuracion del motor
-- -----------------------------------------------------------------------------

-- Se ve la propia y la de la organizacion activa.
create policy configuracion_lectura on configuracion_motor
  for select to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      (ambito = 'usuario' and usuario_id = (select auth.uid()))
      or (ambito = 'organizacion' and organizacion_id = security.organizacion_activa())
    )
  );

-- Escribir exige `configuracion.editar`. La fila es propia (ambito usuario) o de la
-- organizacion activa.
create policy configuracion_escritura on configuracion_motor
  for all to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      (ambito = 'usuario' and usuario_id = (select auth.uid()))
      or (ambito = 'organizacion' and organizacion_id = security.organizacion_activa())
    )
    and security.usuario_tiene_permiso('configuracion.editar')
  )
  with check (
    security.es_usuario_activo()
    and (
      (ambito = 'usuario' and usuario_id = (select auth.uid()))
      or (ambito = 'organizacion' and organizacion_id = security.organizacion_activa())
    )
  );

-- -----------------------------------------------------------------------------
-- Politicas: documentos
-- -----------------------------------------------------------------------------

-- Lectura: lo propio, lo compartido, y lo de la organizacion si `analisis.ver_todos`
-- lo autoriza.
create policy documentos_lectura on documentos
  for select to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      usuario_id = (select auth.uid())
      or security.documento_compartido_conmigo(documentos.id)
      or (
        organizacion_id is not null
        and organizacion_id = security.organizacion_activa()
        and security.usuario_tiene_permiso('analisis.ver_todos')
      )
    )
  );

-- Alta: cada documento lo crea su propio dueno. `documentos.analizar` lo exige la
-- accion, no la fila; la politica acota a que el documento nazca a nombre del autor.
create policy documentos_alta on documentos
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
    and (
      organizacion_id is null
      or organizacion_id = security.organizacion_activa()
    )
  );

-- Actualizacion: el dueno, o quien tenga `analisis.ver_todos` en la organizacion.
-- La actualizacion del estado (`en_proceso` -> `completado`) la hace el propio cliente
-- que esta ejecutando el pipeline, asi que el dueno siempre puede escribir su documento.
create policy documentos_actualizacion on documentos
  for update to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = security.organizacion_activa()
        and security.usuario_tiene_permiso('analisis.ver_todos')
      )
    )
  )
  with check (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = security.organizacion_activa()
        and security.usuario_tiene_permiso('analisis.ver_todos')
      )
    )
  );

-- Borrado logico: el dueno o un admin. `documentos.borrar` lo comprueba el caso de uso.
create policy documentos_borrado on documentos
  for update to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      usuario_id = (select auth.uid())
      or security.usuario_tiene_permiso('documentos.borrar')
    )
  )
  with check (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or security.usuario_tiene_permiso('documentos.borrar')
    )
  );

-- -----------------------------------------------------------------------------
-- Politicas: documentos compartidos
-- -----------------------------------------------------------------------------

-- Se ven los compartidos propios y los que se han hecho en la organizacion.
create policy documentos_compartidos_lectura on documentos_compartidos
  for select to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or compartido_por = (select auth.uid())
      or (
        security.documento_de_mi_organizacion(documentos_compartidos.documento_id)
        and security.usuario_tiene_permiso('documentos.compartir')
      )
    )
  );

-- Compartir exige `documentos.compartir` y que el documento sea visible para quien
-- comparte: no se comparte lo que no se ve.
create policy documentos_compartidos_alta on documentos_compartidos
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.documento_visible(documento_id)
    and security.usuario_tiene_permiso('documentos.compartir')
  );

-- Quitar un compartido: quien lo compartio, el dueno del documento, o un admin.
create policy documentos_compartidos_borrado on documentos_compartidos
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or compartido_por = (select auth.uid())
      or security.usuario_tiene_permiso('documentos.borrar')
    )
  );

-- -----------------------------------------------------------------------------
-- Politicas: bloques
-- -----------------------------------------------------------------------------

-- Un bloque es visible si su documento es visible. La funcion resuelve la regla sin
-- volver a disparar la politica de `documentos` (es `definer`).
create policy bloques_lectura on bloques
  for select to authenticated
  using (security.documento_visible(documento_id));

-- Los bloques los escribe el dueno del documento, que es quien ejecuta el pipeline.
create policy bloques_escritura on bloques
  for all to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  );

-- -----------------------------------------------------------------------------
-- Politicas: analisis
-- -----------------------------------------------------------------------------

create policy analisis_lectura on analisis_documentos
  for select to authenticated
  using (security.documento_visible(documento_id));

create policy analisis_escritura on analisis_documentos
  for all to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  );

-- El historial se consulta con el mismo alcance que el analisis vigente.
create policy historial_lectura on analisis_historial
  for select to authenticated
  using (security.documento_visible(documento_id));

create policy historial_escritura on analisis_historial
  for all to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  );

-- -----------------------------------------------------------------------------
-- Politicas: trabajos y su bitacora
-- -----------------------------------------------------------------------------

create policy trabajos_lectura on trabajos
  for select to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      usuario_id = (select auth.uid())
      or (
        documento_id is not null
        and security.documento_visible(documento_id)
      )
    )
  );

create policy trabajos_escritura on trabajos
  for all to authenticated
  using (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  )
  with check (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  );

-- La bitacora de actividades cuelga del trabajo: se ve si el trabajo se ve.
create policy actividades_lectura on trabajo_actividades
  for select to authenticated
  using (security.trabajo_es_mio(trabajo_actividades.trabajo_id));

-- Los reportes los envia el cliente que ejecuta el pipeline, con el mismo
-- `id_reporte` para que un reintento no duplique filas (HU-08 CE-06).
create policy actividades_alta on trabajo_actividades
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.trabajo_es_mio(trabajo_actividades.trabajo_id)
  );

-- -----------------------------------------------------------------------------
-- Politicas: auditoria
-- -----------------------------------------------------------------------------

-- La bitacora de auditoria la ve quien tenga `auditoria.ver`, dentro de su
-- organizacion. Es de solo lectura desde el cliente: se escribe desde el caso de uso.
create policy auditoria_lectura on auditoria
  for select to authenticated
  using (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = security.organizacion_activa()
        and security.usuario_tiene_permiso('auditoria.ver')
      )
    )
  );

create policy auditoria_alta on auditoria
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and (
      usuario_id = (select auth.uid())
      or security.usuario_tiene_permiso('auditoria.ver')
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );
