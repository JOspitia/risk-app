-- =============================================================================
-- 009 — Cerrar las funciones de `security` al rol `public`
--
-- La migracion 008 revoco `EXECUTE` a `anon`, pero eso no alcanza. Verificado el
-- 2026-11-28: en la nube, `anon` **seguia** pudiendo ejecutar las cinco funciones.
--
-- -----------------------------------------------------------------------------
-- POR QUE
--
-- El ACL de una funcion dice quien puede ejecutarla. El de las funciones de
-- `security` (en la nube, antes de esta migracion) era:
--
--     {=X/postgres,postgres=X/postgres,authenticated=X/postgres}
--
-- El `=X/postgres` de la izquierda es el rol **`public`**, que en Postgres significa
-- "cualquier rol". `revoke execute ... from anon` quita el privilegio al rol
-- `anon` explicitamente, pero **no** al privilegio heredado de `public`: el rol
-- `anon` sigue recibiendo el privilegio por herencia, asi que puede ejecutar la
-- funcion.
--
-- Por que no se noto en el stack local: alli el rol `anon` es un rol del sistema de
-- Postgres, con atributos distintos del rol `anon` de Supabase. En la nube `anon` es
-- un rol propio de la plataforma, con `rolinherit = true`, y conserva la herencia.
-- La diferencia solo aparece al desplegar.
--
-- -----------------------------------------------------------------------------
-- LA CORRECCION
--
-- Revocar al rol `public` y **volver a dar el permiso a `authenticated`**. Son las
-- dos mitades de lo mismo: `public` es el rol del que todos heredan, asi que
-- revocar ahi se los quita a todos.
--
-- El orden importa: primero el `revoke` al rol `public`, despues el `grant` a
-- `authenticated`. Al reves, el `grant` se pierde.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Las funciones RPC
-- -----------------------------------------------------------------------------

revoke execute on function security.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) from public;
grant  execute on function security.guardar_analisis(uuid, uuid, int, text, int, text, jsonb, jsonb, jsonb) to authenticated;

revoke execute on function security.registrar_actividad(uuid, text, text, text, int, int, int) from public;
grant  execute on function security.registrar_actividad(uuid, text, text, text, int, int, int) to authenticated;

revoke execute on function security.actualizar_trabajo(uuid, text, int, text, text) from public;
grant  execute on function security.actualizar_trabajo(uuid, text, int, text, text) to authenticated;

revoke execute on function security.mis_permisos() from public;
grant  execute on function security.mis_permisos() to authenticated;

revoke execute on function security.revocar_sesion(text, timestamptz) from public;
grant  execute on function security.revocar_sesion(text, timestamptz) to authenticated;

-- -----------------------------------------------------------------------------
-- 2. Las funciones de apoyo de las politicas
--
-- Estas no son escribibles por el usuario final, pero dejarlas con `EXECUTE` para
-- cualquiera es dejar una puerta abierta: una funcion nueva que se apoye en ellas
-- nace alcanzable.
--
-- Se revoca a `public` **y a `anon` explicitamente**. Un privilegio concedido
-- directamente a un rol sobrevive a un `revoke` hecho sobre el rol del que ese
-- rol hereda: no es lo mismo quitar el privilegio heredado que el directo.
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

-- Y se le devuelven a `authenticated`, que es quien las necesita: las politicas se
-- ejecutan con los privilegios del rol de la peticion, y si no puede llamarlas,
-- la politica falla y **la fila no se filtra**.
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
-- 3. El rol `anon` tampoco debe poder usar el esquema
--
-- Con `USAGE` en el esquema `security`, `anon` puede siquiera intentar llamar a las
-- funciones. Sin `USAGE`, la puerta esta cerrada en los dos niveles.
--
-- Se revoca a `public` y a `anon` explicitamente. En la nube el ACL del esquema
-- `security` era `{postgres=UC,authenticated=U,anon=U}`: `anon` tenia `USAGE`
-- **directo**, no heredado. Revocar solo a `public` lo dejaba con el permiso.
-- -----------------------------------------------------------------------------

revoke usage on schema security from public;
revoke usage on schema security from anon;
grant  usage on schema security to authenticated;

-- -----------------------------------------------------------------------------
-- 4. Comprobacion
--
-- El ACL de cada funcion tiene que quedar sin el `=X` de la izquierda (el rol
-- `public`), y con `authenticated=X`:
--
--     {postgres=X/postgres,authenticated=X/postgres}
--
-- Verificado el 2026-11-28 contra el proyecto en la nube.
-- -----------------------------------------------------------------------------
