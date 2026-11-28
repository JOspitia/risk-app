-- =============================================================================
-- 007 — Politicas separadas por operacion
--
-- El advisor de Supabase reporto 7 hallazgos de `multiple_permissive_policies`:
-- una tabla con dos politicas permisivas para la misma operacion.
--
-- -----------------------------------------------------------------------------
-- POR QUE ES UN ERROR Y NO UN ESTILO
--
-- En Postgres, dos politicas permisivas sobre la misma tabla **se combinan con
-- OR**, y Postgres evalua **las dos**, siempre: no puede saber que una es mas
-- restrictiva que la otra. El resultado es que una politica puede dejar pasar
-- filas que la otra prohibia.
--
-- En este proyecto el caso era concreto. Estas siete tablas tenian una politica
-- de lectura y otra de escritura declarada como `for all`:
--
--     bloques                  { bloques_escritura, bloques_lectura }
--     analisis_documentos      { analisis_escritura, analisis_lectura }
--     analisis_historial       { historial_escritura, historial_lectura }
--     configuracion_motor      { configuracion_escritura, configuracion_lectura }
--     organizaciones_miembros  { miembros_escritura, miembros_lectura }
--     plantillas_extraccion    { plantillas_escritura, plantillas_lectura }
--     trabajos                 { trabajos_escritura, trabajos_lectura }
--
-- Como `for all` incluye SELECT, cada tabla tenia **dos** politicas de lectura,
-- y el predicado de la de escritura se aplicaba tambien a las consultas de solo
-- lectura. En `bloques`, por ejemplo, la condicion de escritura exigia que el
-- documento fuera del propio usuario; al combinarse con OR con la de lectura, la
-- lectura pasaba sin esa comprobacion.
--
-- -----------------------------------------------------------------------------
-- LA SOLUCION
--
-- Cada politica `for all` se parte en `for insert`, `for update` y `for delete`,
-- con la misma condicion. asi cada operacion tiene **una sola** politica, y no
-- hay combinacion posible.
--
-- Se conserva el comportamiento verificado el 2026-11-28: el dueno ve lo suyo,
-- lo compartido se ve por el compartido, y el alcance de la organizacion se
-- respeta. Lo que cambia es que las condiciones ya no se contaminan entre
-- operaciones.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- bloques
-- -----------------------------------------------------------------------------

drop policy if exists bloques_escritura on bloques;

create policy bloques_insertar on bloques
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  );

create policy bloques_actualizar on bloques
  for update to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  );

create policy bloques_borrar on bloques
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(bloques.documento_id)
  );

-- -----------------------------------------------------------------------------
-- analisis_documentos
-- -----------------------------------------------------------------------------

drop policy if exists analisis_escritura on analisis_documentos;

create policy analisis_insertar on analisis_documentos
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  );

create policy analisis_actualizar on analisis_documentos
  for update to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  );

create policy analisis_borrar on analisis_documentos
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_documentos.documento_id)
  );

-- -----------------------------------------------------------------------------
-- analisis_historial
-- -----------------------------------------------------------------------------

drop policy if exists historial_escritura on analisis_historial;

create policy historial_insertar on analisis_historial
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  );

create policy historial_actualizar on analisis_historial
  for update to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  )
  with check (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  );

create policy historial_borrar on analisis_historial
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and security.documento_es_mio(analisis_historial.documento_id)
  );

-- -----------------------------------------------------------------------------
-- configuracion_motor
-- -----------------------------------------------------------------------------

drop policy if exists configuracion_escritura on configuracion_motor;

create policy configuracion_insertar on configuracion_motor
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and (
      (ambito = 'usuario' and usuario_id = (select auth.uid()))
      or (ambito = 'organizacion' and organizacion_id = security.organizacion_activa())
    )
  );

create policy configuracion_actualizar on configuracion_motor
  for update to authenticated
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

create policy configuracion_borrar on configuracion_motor
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and (
      (ambito = 'usuario' and usuario_id = (select auth.uid()))
      or (ambito = 'organizacion' and organizacion_id = security.organizacion_activa())
    )
    and security.usuario_tiene_permiso('configuracion.editar')
  );

-- -----------------------------------------------------------------------------
-- organizaciones_miembros
-- -----------------------------------------------------------------------------

drop policy if exists miembros_escritura on organizaciones_miembros;

create policy miembros_insertar on organizaciones_miembros
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and (
      security.usuario_tiene_permiso('organizacion.gestionar')
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

create policy miembros_actualizar on organizaciones_miembros
  for update to authenticated
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

create policy miembros_borrar on organizaciones_miembros
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and (
      security.usuario_tiene_permiso('organizacion.gestionar')
      or security.usuario_tiene_permiso('usuarios.gestionar')
    )
  );

-- -----------------------------------------------------------------------------
-- plantillas_extraccion
-- -----------------------------------------------------------------------------

drop policy if exists plantillas_escritura on plantillas_extraccion;

create policy plantillas_insertar on plantillas_extraccion
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and organizacion_id = security.organizacion_activa()
    and security.usuario_tiene_permiso('plantillas.editar')
  );

create policy plantillas_actualizar on plantillas_extraccion
  for update to authenticated
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

create policy plantillas_borrar on plantillas_extraccion
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and eliminado_en is null
    and organizacion_id = security.organizacion_activa()
    and security.usuario_tiene_permiso('plantillas.editar')
  );

-- -----------------------------------------------------------------------------
-- trabajos
-- -----------------------------------------------------------------------------

drop policy if exists trabajos_escritura on trabajos;

create policy trabajos_insertar on trabajos
  for insert to authenticated
  with check (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  );

create policy trabajos_actualizar on trabajos
  for update to authenticated
  using (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  )
  with check (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  );

create policy trabajos_borrar on trabajos
  for delete to authenticated
  using (
    security.es_usuario_activo()
    and usuario_id = (select auth.uid())
  );

-- -----------------------------------------------------------------------------
-- documento: la unica que queda con dos politicas para la misma operacion
--
-- `documentos_alta` (insert) y `documentos_actualizacion` (update) son de
-- operaciones distintas, asi que no se combinan. Se deja como esta.
-- -----------------------------------------------------------------------------
