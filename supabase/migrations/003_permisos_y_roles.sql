-- =============================================================================
-- 003 — Roles, permisos y matriz
--
-- La matriz vive en DATOS, no en codigo (ARQUITECTURA.md seccion 5.5). Agregar un
-- permiso es un `insert`, no un despliegue.
--
-- Catalogo de permisos: `[PROPUESTO]` (ARQUITECTURA.md seccion 5.5).
-- Matriz por rol: `[DECIDIDO]` (ARQUITECTURA.md seccion 5.5, HU-02 seccion 3).
--
-- Este archivo es idempotente: se puede reaplicar sin duplicar filas.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Roles
-- -----------------------------------------------------------------------------

insert into roles (clave, nombre, descripcion, is_system)
values
  ('admin',    'Administrador', 'Control total de la organizacion: usuarios, permisos, plantillas y documentos.', true),
  ('analista', 'Analista',      'Analiza documentos propios y compartidos. Es el rol por defecto.', true),
  ('auditor',  'Auditor',       'Solo lectura: consulta documentos, analisis y la bitacora de auditoria.', true)
on conflict (clave) do update
  set nombre      = excluded.nombre,
      descripcion = excluded.descripcion,
      is_system   = excluded.is_system;

-- -----------------------------------------------------------------------------
-- Catalogo de permisos
-- -----------------------------------------------------------------------------

insert into permisos (clave, nombre, descripcion)
values
  ('documentos.ver',       'Ver documentos y sus resultados',   'Consultar el listado y el detalle de los documentos visibles.'),
  ('documentos.analizar',  'Lanzar analisis',                    'Iniciar el analisis de un documento y registrar sus resultados.'),
  ('documentos.borrar',    'Eliminar documentos',                'Hacer el borrado logico de un documento y eliminar su archivo.'),
  ('documentos.compartir', 'Compartir documentos',               'Compartir un documento con otro miembro de la organizacion.'),
  ('archivos.descargar',   'Descargar el archivo original',      'Obtener una URL firmada de vida corta para el PDF archivado.'),
  ('archivos.eliminar',    'Eliminar el archivo del almacenamiento', 'Borrar el objeto del bucket privado.'),
  ('analisis.ver_todos',   'Ver analisis de otros usuarios',      'Consultar documentos y analisis de otros miembros de la organizacion.'),
  ('plantillas.ver',       'Ver plantillas de extraccion',        'Consultar las plantillas disponibles.'),
  ('plantillas.editar',    'Editar plantillas de extraccion',    'Crear, versionar y activar plantillas.'),
  ('configuracion.ver',    'Ver la configuracion del motor',      'Consultar la configuracion del motor IA.'),
  ('configuracion.editar', 'Editar la configuracion del motor',   'Cambiar modelo, chunking y temperatura.'),
  ('usuarios.gestionar',   'Gestionar usuarios',                  'Crear, desactivar y cambiar el rol de los usuarios.'),
  ('organizacion.gestionar','Gestionar la organizacion',          'Cambiar roles y membresias del equipo.'),
  ('auditoria.ver',        'Ver la bitacora de auditoria',        'Consultar el registro de operaciones.')
on conflict (clave) do update
  set nombre      = excluded.nombre,
      descripcion = excluded.descripcion;

-- -----------------------------------------------------------------------------
-- Matriz rol -> permisos
--
-- La regla general es "se ve lo que el permiso autoriza" (ARQUITECTURA.md 5.5).
-- El `analista` NO recibe `analisis.ver_todos` por defecto: ve lo propio y lo que se
-- le comparte de forma explicita. Una organizacion que quiera que su equipo se vea todo
-- lo concede en la matriz, sin cambiar codigo.
-- -----------------------------------------------------------------------------

insert into rol_permisos (rol, permiso)
select 'admin', clave
from permisos
on conflict (rol, permiso) do nothing;

insert into rol_permisos (rol, permiso)
values
  ('analista', 'documentos.ver'),
  ('analista', 'documentos.analizar'),
  ('analista', 'documentos.borrar'),
  ('analista', 'documentos.compartir'),
  ('analista', 'archivos.descargar'),
  ('analista', 'archivos.eliminar'),
  ('analista', 'plantillas.ver'),
  ('analista', 'configuracion.ver'),
  ('analista', 'configuracion.editar')
on conflict (rol, permiso) do nothing;

insert into rol_permisos (rol, permiso)
values
  ('auditor', 'documentos.ver'),
  ('auditor', 'archivos.descargar'),
  ('auditor', 'analisis.ver_todos'),
  ('auditor', 'plantillas.ver'),
  ('auditor', 'configuracion.ver'),
  ('auditor', 'auditoria.ver')
on conflict (rol, permiso) do nothing;
