-- =============================================================================
-- seed — Datos iniciales del sistema
--
-- Se aplica automaticamente con `supabase db reset` (y con `supabase start` la
-- primera vez). Es idempotente: se puede reaplicar sin duplicar filas.
--
-- Que trae:
-- - La plantilla semilla v1 (plantilla del sistema, visible para todos).
--
-- NO trae usuarios ni organizaciones: el primer administrador lo crea el script
-- `backend/scripts/bootstrap_admin.py`, que usa la API de administracion de Supabase
-- (`service_role`). Insertar el primer admin con un `insert` en `auth.users` es
-- fragil: Supabase espera filas coordinadas en `auth.users` y `auth.identities`,
-- con un formato interno que cambia entre versiones (ARQUITECTURA.md seccion 5.6).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Plantilla semilla v1
--
-- `[DECIDIDO]` Se siembra para que el sistema pueda probarse de punta a punta desde
-- la primera migracion, sin esperar a que el cliente defina sus campos (PP-13).
--
-- El esquema es JSON Schema, no un formato propio: es lo que el motor entiende y
-- lo que Pydantic valida en el backend (HU-11 seccion 4).
--
-- `organizacion_id` nulo = plantilla del sistema: todos la ven, nadie la edita
-- sin ser admin de una organizacion.
-- -----------------------------------------------------------------------------

insert into plantillas_extraccion (
  organizacion_id, nombre, version, esquema, instruccion, activa
)
values (
  null,
  'Generica v1',
  1,
  '{
    "type": "object",
    "properties": {
      "campo_1": {
        "type": ["string", "null"],
        "description": "Primer campo de riesgo"
      },
      "campo_2": {
        "type": ["string", "null"],
        "description": "Segundo campo de riesgo"
      }
    },
    "required": [],
    "additionalProperties": false
  }'::jsonb,
  'Extrae los campos de riesgo del documento. Si un campo no aparece, dejalo en null. No inventes valores.',
  true
)
on conflict do nothing;
