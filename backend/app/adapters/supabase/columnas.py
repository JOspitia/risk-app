"""Las columnas de cada tabla, en un solo constante.

Cuando el modelo gana un campo, **todas** las proyecciones, todos los
`RETURNING` y todos los mapeadores de fila tienen que cambiar. Un desajuste
aparece como un fallo en runtime lejos de la edicion que lo causo
(`SKILL.md` 4.4 y 12.9).

Duplicar la proyeccion en varias consultas garantiza que se desincronizan.
"""

from __future__ import annotations

# `perfiles`: los datos de negocio del usuario. No se pide `eliminado_en` ni
# `creado_en`: son columnas internas de la tabla, no conceptos del dominio.
COLUMNAS_PERFIL = (
    "id, nombres, apellido_1, apellido_2, display_name, correo, rol, "
    "organizacion_id, debe_cambiar_contrasena, activo"
)

# `organizaciones_miembros`: la pertenencia que define el aislamiento (ADR-33).
COLUMNAS_MEMBRESIA = "organizacion_id, rol"

# `sesiones_revocadas`: solo el `session_id` se guarda, nunca el token (ADR-31).
COLUMNAS_SESION_REVOCADA = "session_id, usuario_id, revocado_en, expira_en"

# `auditoria`: la bitacora. `creado_en` lo pone la base de datos.
COLUMNAS_AUDITORIA = (
    "usuario_id, organizacion_id, actor, accion, entidad, entidad_id, "
    "detalles, ip, user_agent"
)
