-- =============================================================================
-- 014 — Un usuario no puede cambiarse el rol, ni el estado, ni la organizacion
--
-- PROBLEMA
--
-- La politica `perfiles_actualizacion` (002_rls.sql) comprueba **quien** escribe,
-- no **que** escribe:
--
--   with check (
--     id = (select auth.uid())
--     or (security.es_usuario_activo() and security.usuario_tiene_permiso('usuarios.gestionar'))
--   );
--
-- La primera rama dice "es su propia fila", no "puede cambiar lo que quiera en
-- su propia fila". Con esa politica, un usuario autenticado podia:
--
--   update perfiles set rol = 'admin' where id = auth.uid();
--
-- y como los permisos se resuelven por `perfiles.rol` (matriz `roles` y
-- `rol_permisos`), eso era **escalada de privilegios trivial**: cualquiera se
-- autoproclamaba administrador. Lo mismo pasaba con `activo` y con
-- `organizacion_id`.
--
-- El comentario de la migracion 002 afirmaba que la politica ya impedia cambiar
-- el rol y el estado: no lo impedia, porque no habia nada que lo hiciera. El
-- `with check` de una politica de RLS comprueba la fila **nueva**, no las
-- columnas que cambiaron.
--
-- QUE RESUELVE
--
-- Un trigger BEFORE UPDATE que compara la fila vieja con la nueva y rechaza el
-- cambio de las columnas que dan poder, **salvo** para quien tenga el permiso
-- `usuarios.gestionar`: la administracion de usuarios (HU-03) si necesita
-- cambiar el rol o el estado de alguien.
--
-- El trigger corre como `SECURITY DEFINER` con el `search_path` fijo, para que
-- pueda leer los permisos del actor sin que la recursion de RLS lo muerda.
--
-- Sin usuario autenticado no hay a quien proteger: es la llave de servicio (el
-- bootstrap y el adaptador de administracion) o el propio postgres. Los dos
-- tienen todos los permisos de partida.

create or replace function public.proteger_columnas_de_poder()
returns trigger
language plpgsql
security definer
set search_path = public, security
as $$
declare
  puede_gestionar boolean;
begin
  if (select auth.uid()) is null then
    return new;
  end if;

  if new.rol is distinct from old.rol
     or new.activo is distinct from old.activo
     or new.organizacion_id is distinct from old.organizacion_id
     or new.id is distinct from old.id then

    puede_gestionar := security.es_usuario_activo()
      and security.usuario_tiene_permiso('usuarios.gestionar');

    if not coalesce(puede_gestionar, false) then
      raise exception 'un usuario no puede cambiar su rol, su estado ni su organizacion'
        using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

-- El trigger se dispara con el rol de quien escribe: hace falta que pueda
-- ejecutarlo quien escribe, y nadie mas.
revoke all on function public.proteger_columnas_de_poder() from public;
grant execute on function public.proteger_columnas_de_poder() to authenticated, service_role;

drop trigger if exists perfiles_no_cambia_rol on public.perfiles;

create trigger perfiles_no_cambia_rol
before update on public.perfiles
for each row
execute function public.proteger_columnas_de_poder();
