-- =============================================================================
-- 013 — La vista publica que confirma que el esquema esta aplicado
--
-- PROBLEMA
--
-- `docs/ARQUITECTURA.md` 8.1 marca como `[DECIDIDO]` que la sonda consulte una
-- vista publica que confirma que la base responde y que las migraciones estan
-- aplicadas:
--
--     create or replace view public.salud as
--       select
--         (select count(*) from public.roles) as roles_cargados,
--         (select count(*) from public.permisos) as permisos_cargados;
--
-- Esa vista no existia en ninguna migracion. La sonda respondia 200 siempre y
-- no miraba la base: un contenedor sano y una base caida se veian igual.
--
-- QUE RESUELVE
--
-- La vista alimenta a `GET /ready`, la **sonda de disponibilidad**, que es
-- distinta de `GET /health`, la **sonda de supervivencia**:
--
-- - `/health` mira el proceso. Es la que consulta el `HEALTHCHECK` del
--   contenedor, y ese solo mira el codigo de salida. Si dependiera de la base,
--   un tropiezo de Supabase reiniciaria en bucle un contenedor de FastAPI que
--   esta perfectamente sano.
-- - `/ready` mira la base. Si Supabase no responde, o el esquema todavia no
--   esta aplicado, responde 503 y el orquestador deja de mandar trafico en vez
--   de reiniciar procesos.
--
-- POR QUE ES PUBLICA
--
-- La vista cuenta el catalogo del sistema, no datos de persona: ni correos, ni
-- roles asignados, ni documentos. Por eso es legible por `anon` y por
-- `authenticated`, y por eso la sonda **no necesita la llave de servicio**: con
-- la llave de servicio, RLS no aplicaria y la sonda estaria mintiendo sobre lo
-- que el servidor veria de verdad.
--
-- `roles_cargados = 0` significa que el esquema **no esta aplicado**: sin la
-- matriz de roles y permisos no hay permisos que resolver.

create or replace view public.salud as
  select
    (select count(*) from public.roles) as roles_cargados,
    (select count(*) from public.permisos) as permisos_cargados;

comment on view public.salud is
  'Estado del esquema: cuantos roles y permisos estan cargados. No contiene datos de persona.';

-- La vista se crea con los permisos de su dueno, asi que sin estos grants
-- nadie la podria leer. Se abre solo a los dos roles que la sonda usa.
revoke all on public.salud from public;
grant select on public.salud to anon, authenticated;
