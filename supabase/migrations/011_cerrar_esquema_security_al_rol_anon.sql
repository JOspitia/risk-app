-- =============================================================================
-- 011 — Cerrar el esquema `security` al rol `anon`
--
-- La migracion 009Cerro las funciones al rol `public`, pero en la nube el ACL del
-- esquema `security` quedo asi:
--
--     {postgres=UC/postgres,authenticated=U/postgres,anon=U/postgres}
--
-- El `anon=U` es un privilegio **directo**, no heredado. La migracion 008 lo
-- concedio explicitamente, y por eso el `revoke ... from public` de la 009 no lo
-- toco: revocar al rol del que se hereda no quita un permiso que se concedio
-- directamente a un rol concreto.
--
-- Que `anon` tenga `USAGE` en `security` no le permite ejecutar las funciones de
-- apoyo (sus ACLs ya no incluyen a `anon`, verificado el 2026-11-28). Pero deja
-- la puerta entreabierta: cualquier funcion nueva que se cree en ese esquema
-- nace alcanzable por `anon`, y `anon` puede enumerar el esquema.
--
-- Esta migracion cierra las dos cosas:
--
--   - `USAGE` en el esquema `security` solo para `authenticated` (y `postgres`).
--   - `EXECUTE` en las nueve funciones de apoyo solo para `authenticated`.
--
-- Con `FORCE ROW LEVEL SECURITY` en las 17 tablas (migracion 008) y estas
-- funciones siendo `security definer` con `set row_security = off`, la politica se
-- sigue resolviendo bien: las politicas se ejecutan con los privilegios del rol
-- de la peticion, y `authenticated` si puede llamarlas.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. El uso del esquema
--
-- El orden importa: primero se revoca (a `public` y a `anon` explicitamente),
-- despues se concede. Al reves, el `grant` se pierde.
-- -----------------------------------------------------------------------------

revoke usage on schema security from public;
revoke usage on schema security from anon;
grant  usage on schema security to authenticated;

-- -----------------------------------------------------------------------------
-- 2. Las funciones de apoyo de las politicas
--
-- Revocar a `public` no basta por lo mismo: `anon` puede tener el privilegio
-- directo. Se revoca a los dos.
-- -----------------------------------------------------------------------------

revoke execute on function security.organizacion_activa() from public;
revoke execute on function security.organizacion_activa() from anon;
revoke execute on function security.es_usuario_activo() from public;
revoke execute on function security.es_usuario_activo() from anon;
revoke execute on function security.usuario_tiene_permiso(text) from public;
revoke execute on function security.usuario_tiene_permiso(text) from anon;
revoke execute on function security.es_miembro_de(uuid) from public;
revoke execute on function security.es_miembro_de(uuid) from anon;
revoke execute on function security.documento_visible(uuid) from public;
revoke execute on function security.documento_visible(uuid) from anon;
revoke execute on function security.documento_compartido_conmigo(uuid) from public;
revoke execute on function security.documento_compartido_conmigo(uuid) from anon;
revoke execute on function security.documento_es_mio(uuid) from public;
revoke execute on function security.documento_es_mio(uuid) from anon;
revoke execute on function security.documento_de_mi_organizacion(uuid) from public;
revoke execute on function security.documento_de_mi_organizacion(uuid) from anon;
revoke execute on function security.trabajo_es_mio(uuid) from public;
revoke execute on function security.trabajo_es_mio(uuid) from anon;

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
-- 3. Comprobacion
--
-- El ACL del esquema tiene que quedar:
--
--     {postgres=UC/postgres,authenticated=U/postgres}
--
-- Y el de cada funcion de apoyo:
--
--     {postgres=X/postgres,authenticated=X/postgres}
--
-- Verificado el 2026-11-28 contra el proyecto en la nube.
-- -----------------------------------------------------------------------------
