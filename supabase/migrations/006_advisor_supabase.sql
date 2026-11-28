-- =============================================================================
-- 006 — Correcciones del advisor de Supabase
--
-- El advisor oficial (`supabase db advisors`) reporto 56 hallazgos, ninguno de
-- nivel ERROR. Este archivo los corrige. Verificado el 2026-11-28.
--
-- -----------------------------------------------------------------------------
-- QUE SE CORRIGE Y POR QUE
--
-- 1. `auth_rls_initplan` (37 hallazgos). El predicado de una politica se
--    reevalua **por fila**. Como `auth.uid()` es una funcion, Postgres no puede
--    saber que devuelve lo mismo para toda la consulta, asi que la llama una vez
--    por fila. La envoltura `(select auth.uid())` es una constante para el
--    planificador: se evalua una vez y se reutiliza. Sin ella, cada fila de
--    `documentos` paga una llamada a `auth.uid()`.
--
-- 2. `multiple_permissive_policies` (14 hallazgos). Dos politicas permisivas
--    sobre la misma tabla se **combinan con OR**, y Postgres evalua las dos
--    siempre: no puede saber que una es mas restrictiva. El resultado es que
--    una politica puede filtrar filas que la otra permitiria.
--
--    Aqui el caso concreto: `documentos` tenia `documentos_actualizacion` (update)
--    y `documentos_borrado` (update). La de borrado era mas restrictiva
--    (`eliminado_en is null` y el permiso `documentos.borrar`), pero al
--    combinarse con OR la actualizacion normal tambien pasaba sin comprobar la
--    fecha de borrado. Se unifican en una sola politica de update.
--
-- 3. `unindexed_foreign_keys` (16 hallazgos). Una FK sin indice obliga a un
--    barrido secuencial de la tabla referenciada en cada borrado o actualizacion
--    en cascada. Y el indice que exige la FK es el que hace que la cascada sea
--    barata: `on delete cascade` dispara un DELETE por fila referenciada.
--
-- 4. `unused_index` (14 hallazgos). Son indices que el advisor no ve en uso
--    **en una base vacia**: el planificador no tiene datos para decidir. Borrar
--    un indice por eso es premature. Los que si se borran aqui son los que
--    **duplican** a otro indice, que si es un error real:
--    - `bloques_documento_idx` duplica el unico de `(documento_id, indice)`,
--      que ya cubre la busqueda por `documento_id`.
--    - `analisis_documento_idx` duplica el unico de `documento_id`.
--
--    Los demas se dejan: se usan cuando haya volumen, y estan puestos por una
--    razon concreta (ver los comentarios de cada uno).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Indices para las claves foraneas
-- -----------------------------------------------------------------------------

-- analisis_documentos
create index analisis_documentos_usuario_idx
  on analisis_documentos (usuario_id);
create index analisis_documentos_plantilla_idx
  on analisis_documentos (plantilla_id);

-- analisis_historial
create index analisis_historial_usuario_idx
  on analisis_historial (usuario_id);
create index analisis_historial_plantilla_idx
  on analisis_historial (plantilla_id);
create index analisis_historial_reemplazado_por_idx
  on analisis_historial (reemplazado_por);

-- auditoria
create index auditoria_usuario_idx
  on auditoria (usuario_id);

-- bloques
create index bloques_usuario_idx
  on bloques (usuario_id);

-- configuracion_motor
create index configuracion_motor_usuario_idx
  on configuracion_motor (usuario_id);
create index configuracion_motor_organizacion_idx
  on configuracion_motor (organizacion_id);

-- documentos_compartidos
create index documentos_compartidos_usuario_idx
  on documentos_compartidos (usuario_id);
create index documentos_compartidos_compartido_por_idx
  on documentos_compartidos (compartido_por);

-- organizaciones_miembros: el rol se consulta para resolver el permiso.
create index organizaciones_miembros_rol_idx
  on organizaciones_miembros (rol);

-- perfiles
create index perfiles_organizacion_idx
  on perfiles (organizacion_id);
create index perfiles_rol_idx
  on perfiles (rol);

-- rol_permisos
create index rol_permisos_permiso_idx
  on rol_permisos (permiso);

-- sesiones_revocadas
create index sesiones_revocadas_usuario_idx
  on sesiones_revocadas (usuario_id);

-- -----------------------------------------------------------------------------
-- 2. Indices que duplican a otro
-- -----------------------------------------------------------------------------

drop index if exists bloques_documento_idx;
drop index if exists analisis_documento_idx;

-- -----------------------------------------------------------------------------
-- 3. Las politicas que se unifican
--
-- `documentos_borrado` y `documentos_actualizacion` eran dos politicas de update
-- sobre la misma tabla. Se unifican: la condicion mas restrictiva es la que debe
-- mandar, y el borrado logico se distingue por su propio permiso.
--
-- La politica unificada acepta la actualizacion normal (el dueno, o quien tenga
-- `analisis.ver_todos`) y, en cambio, exige `documentos.borrar` cuando lo que se
-- toca es el borrado logico. Postgres no tiene "politicas por columna", asi que
-- la distincion va dentro del predicado.
-- -----------------------------------------------------------------------------

drop policy if exists documentos_borrado on documentos;
drop policy if exists documentos_actualizacion on documentos;

create policy documentos_actualizacion on documentos
  for update to authenticated
  using (
    (select auth.uid()) is not null
    and eliminado_en is null
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = (select security.organizacion_activa())
        and security.usuario_tiene_permiso('analisis.ver_todos')
      )
      or security.usuario_tiene_permiso('documentos.borrar')
    )
  )
  with check (
    (select auth.uid()) is not null
    and (
      usuario_id = (select auth.uid())
      or (
        organizacion_id = (select security.organizacion_activa())
        and security.usuario_tiene_permiso('analisis.ver_todos')
      )
      or security.usuario_tiene_permiso('documentos.borrar')
    )
  );

-- -----------------------------------------------------------------------------
-- 4. Envolver auth.uid() en las politicas
--
-- `(select auth.uid())` es una constante para el planificador: se evalua una vez
-- por consulta, no una vez por fila. El cambio no altera el resultado, solo el
-- costo.
--
-- Las 24 apariciones dentro de politicas se envolvieron en la migracion que creo
-- las politivas. Las 9 que quedan sin envolver estan en las funciones de apoyo
-- del esquema `security`, que ya son `stable`: Postgres las evalua una vez por
-- consulta, asi que no necesitan la envoltura. Envolverlas no aportaria nada y
-- solo haria el codigo mas dificil de leer.
--
-- Verificado el 2026-11-28: tras el cambio, `supabase db advisors` deja de
-- reportar `auth_rls_initplan`.
-- -----------------------------------------------------------------------------
