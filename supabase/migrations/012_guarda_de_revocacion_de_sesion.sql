-- =============================================================================
-- 012 — Corregir la guarda de `public.revocar_sesion`
--
-- PROBLEMA
--
-- La guarda actual exige que la fila **ya exista** en `sesiones_revocadas`:
--
--   if not exists (
--     select 1
--     from sesiones_revocadas s
--     join auth.users u on u.id = s.usuario_id
--     where s.session_id = p_session_id
--       and s.usuario_id = auth.uid()
--   ) then
--     raise exception 'la sesion no pertenece al usuario autenticado'
--       using errcode = '42501';
--   end if;
--
-- Esa fila es exactamente la que la funcion va a insertar justo despues. El
-- resultado es que **el primer cierre de sesion siempre falla** con 42501: la
-- sesion todavia no esta revocada, asi que la fila no existe, asi que la
-- guarda rechaza la operacion. El endpoint `POST /api/v1/auth/logout` no
-- podia revocar ninguna sesion.
--
-- COMO SE RESUELVE LA PERTENENCIA
--
-- La pertenencia real del `session_id` se resuelve contra `auth.sessions`: la
-- tabla donde Supabase Auth guarda las sesiones vivas. El claim `session_id`
-- del JWT es el `id` de esa fila.
--
-- Pero `auth.sessions` **no basta por si sola**, y el motivo es concreto: al
-- cerrar sesion en Supabase (`signOut()`), GoTrue **borra** la fila de
-- `auth.sessions`. Verificado el 2026-11-28 contra el stack local: tras el
-- `POST /auth/v1/logout` la fila desaparece de la tabla.
--
-- Y el `POST /api/v1/auth/logout` del backend llega **despues** del
-- `signOut()` del navegador (HU-01, seccion 7.4), asi que para entonces la
-- sesion ya no esta en `auth.sessions`. Resolver la pertenencia solo contra
-- esa tabla dejaria el cierre de sesion sin efecto justo en el caso que
-- importa, y el token seguiria sirviendo hasta su `exp`.
--
-- POR ESO LA GUARDA TIENE DOS COMPROBACIONES
--
-- 1. **El claim del propio token.** El `session_id` que se pide revocar tiene
--    que ser el del token de quien llama. Ese claim viaja firmado dentro del
--    JWT, y PostgREST lo deja en `request.jwt.claims` **despues** de verificar
--    la firma. Comparar contra ese claim es una prueba criptografica de
--    pertenencia que no depende de que la fila de `auth.sessions` siga
--    existiendo: sobrevive al `signOut()`.
--
-- 2. **La sesion viva en `auth.sessions`.** Si la sesion sigue viva, tiene
--    que ser del usuario autenticado. Es la comprobacion explicita sobre la
--    tabla, y es la que impide revocar la sesion de otra persona.
--
-- Las dos rechazan con 42501 cuando la sesion no es del usuario. La segunda
-- es la que se apoya en `auth.sessions`; la primera es la que sobrevive al
-- cierre de sesion en Supabase.
--
-- Ademas, la politica de insercion de `sesiones_revocadas` se endurece: hasta
-- aqui un usuario autenticado podia insertar una revocacion con **cualquier**
-- `session_id` mientras pusiera su propio `usuario_id`, y eso le permitia
-- invalidar el token de otra persona. Ahora solo puede revocar la sesion de
-- su propio token, que es lo unico que el caso de uso necesita.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. El `session_id` del token, como funcion de apoyo de las politicas
--
-- Vive en el esquema `security` porque la politica de `sesiones_revocadas` la
-- necesita y las funciones de apoyo de las politicas viven ahi desde la
-- migracion 002. No es `security definer`: no lee ninguna tabla, solo lee el
-- GUC que PostgREST deja con los claims del token verificado.
-- -----------------------------------------------------------------------------

create or replace function security.session_id_del_token()
returns text
language sql
stable
as $$
  select case
    when nullif(current_setting('request.jwt.claims', true), '') is null then null
    else (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'session_id')
  end
$$;

comment on function security.session_id_del_token() is
  'Claim session_id del JWT de la peticion actual. Null si la peticion no lleva token.';

-- -----------------------------------------------------------------------------
-- 2. La politica de alta: solo la sesion del propio token
--
-- Se replaces la politica, no se edita la migracion 002: las migraciones ya
-- aplicadas no se tocan (SKILL.md 12.2).
-- -----------------------------------------------------------------------------

drop policy if exists sesiones_alta on sesiones_revocadas;

create policy sesiones_alta on sesiones_revocadas
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and (
      (
        usuario_id = (select auth.uid())
        and session_id = security.session_id_del_token()
      )
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- -----------------------------------------------------------------------------
-- 3. La guarda de `revocar_sesion`
--
-- El cuerpo cambia; la firma y el ACL no. Por eso se puede usar
-- `create or replace`: no queda ninguna version anterior con la misma
-- firma, y el `grant` de la migracion 010 sigue valiendo.
-- -----------------------------------------------------------------------------

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
declare
  v_claims        text;
  v_session_claim text;
begin
  -- 1. La sesion que se revoca tiene que ser la del token de quien llama.
  --    El claim viaja firmado: compararlo ES la prueba de pertenencia, y no
  --    depende de que la sesion siga viva en `auth.sessions`.
  v_claims := nullif(current_setting('request.jwt.claims', true), '');
  if v_claims is not null then
    begin
      v_session_claim := v_claims::jsonb ->> 'session_id';
    exception when others then
      v_session_claim := null;
    end;
  end if;

  if v_session_claim is null or v_session_claim <> p_session_id then
    raise exception 'la sesion no pertenece al usuario autenticado'
      using errcode = '42501';
  end if;

  -- 2. Si la sesion sigue viva en `auth.sessions`, tiene que ser de este
  --    usuario. Sin esta comprobacion, un `session_id` de otra persona que ya
  --    cerro sesion en Supabase se podria revocar desde cualquier token.
  if exists (
    select 1
    from auth.sessions s
    where s.id::text = p_session_id
      and s.user_id is distinct from auth.uid()
  ) then
    raise exception 'la sesion no pertenece al usuario autenticado'
      using errcode = '42501';
  end if;

  -- 3. El registro es de solo agregado: la revocacion caduca con el token y
  --    nunca se borra una fila para "desrevocar" una sesion (SKILL.md 5.3).
  insert into sesiones_revocadas (session_id, usuario_id, expira_en)
  values (p_session_id, auth.uid(), p_expira_en)
  on conflict (session_id) do update
    set revocado_en = now(),
        expira_en   = excluded.expira_en;
end;
$$;

comment on function public.revocar_sesion(text, timestamptz) is
  'Revoca la sesion del token de quien llama. Rechaza con 42501 cualquier session_id ajeno.';
