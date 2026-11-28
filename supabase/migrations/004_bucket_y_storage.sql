-- =============================================================================
-- 004 — Bucket privado y politicas de almacenamiento
--
-- ADR-20: los documentos se archivan en Supabase Storage, en un bucket privado,
-- subidos directo desde el navegador (la API no puede recibir un PDF de 30 MB).
--
-- La ruta del objeto codifica el ambito:
--   {organizacion_id}/{usuario_id}/{documento_id}.pdf
-- Asi la politica se resuelve por prefijo, sin tabla de busqueda, y el archivo
-- hereda el aislamiento de su documento.
--
-- Se comprueban LOS DOS primeros segmentos: validar solo el primero permitiria a un
-- usuario escribir dentro de la carpeta de otro usuario de su misma organizacion.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- El bucket
-- -----------------------------------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documentos', 'documentos', false,
  52428800,                          -- 50 MB (limite del plan Free de Supabase)
  array['application/pdf']
)
on conflict (id) do update
  set name                = excluded.name,
      public              = excluded.public,
      file_size_limit     = excluded.file_size_limit,
      allowed_mime_types  = excluded.allowed_mime_types;

-- -----------------------------------------------------------------------------
-- Politicas sobre storage.objects
--
-- Controlan toda operacion de archivo, incluida la creacion de URLs firmadas.
-- -----------------------------------------------------------------------------

-- Subida: el prefijo es {organizacion_id}/{usuario_id}/{documento_id}.pdf y los dos
-- primeros segmentos son los del propio usuario.
create policy archivos_insertar on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documentos'
    and (storage.foldername(name))[1] = security.organizacion_activa()::text
    and (storage.foldername(name))[2] = auth.uid()::text
    and (storage.foldername(name))[3] is not null
    and lower(right(name, 4)) = '.pdf'
  );

-- Lectura: la carpeta de la organizacion, o un documento propio archivado.
-- El segundo caso cubre al dueno cuando la organizacion del documento ya no es la
-- organizacion activa (por ejemplo, si el archivo quedo de una membresia anterior).
create policy archivos_leer on storage.objects
  for select to authenticated
  using (
    bucket_id = 'documentos'
    and (
      (storage.foldername(name))[1] = security.organizacion_activa()::text
      or exists (
        select 1
        from documentos d
        where d.ruta_archivo = name
          and d.usuario_id = auth.uid()
          and d.eliminado_en is null
      )
    )
  );

-- Actualizacion: la clave del objeto es la ruta, y la ruta no cambia. Se permite solo
-- para los objetos propios, por si el mismo PDF se reescribe (mismo documento, mismo
-- hash). El `using` y el `with check` exigen el mismo prefijo.
create policy archivos_actualizar on storage.objects
  for update to authenticated
  using (
    bucket_id = 'documentos'
    and (storage.foldername(name))[1] = security.organizacion_activa()::text
    and (storage.foldername(name))[2] = auth.uid()::text
  )
  with check (
    bucket_id = 'documentos'
    and (storage.foldername(name))[1] = security.organizacion_activa()::text
    and (storage.foldername(name))[2] = auth.uid()::text
  );

-- Borrado: se autoriza por la misma regla que la lectura, restringida al dueno.
-- Sin esta politica, un usuario no podria borrar su propio archivo, que es lo que
-- exige RF-25 (HU-12).
create policy archivos_borrar on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'documentos'
    and exists (
      select 1
      from documentos d
      where d.ruta_archivo = name
        and d.usuario_id = auth.uid()
        and d.eliminado_en is null
    )
  );
