"""Entidad de dominio del perfil de usuario.

`perfiles` es la tabla de negocio: ahi vive el nombre, el rol y la
organizacion del usuario. `auth.users` la administra Supabase Auth y el backend
no la lee.

La entidad **no** lleva columnas internas de la tabla que el cliente no debe
ver (`.eliminado_en`, `.creado_en`): la fila de la base y el concepto de
dominio no son lo mismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Perfil:
    """Los datos de negocio de un usuario."""

    id: UUID
    nombres: str
    apellido_1: str
    apellido_2: str | None
    display_name: str | None
    correo: str
    rol: str
    organizacion_id: UUID | None
    debe_cambiar_contrasena: bool
    activo: bool

    @property
    def nombre_completo(self) -> str:
        """Nombre para la bitacora y para el contexto de auditoria."""
        if self.display_name:
            return self.display_name
        partes = [self.nombres, self.apellido_1]
        if self.apellido_2:
            partes.append(self.apellido_2)
        return " ".join(partes)


@dataclass(frozen=True)
class Membresia:
    """Pertenencia del usuario a una organizacion, con su rol propio.

    El aislamiento se resuelve **desde aqui**, no desde `perfiles.organizacion_id`:
    un usuario puede pertenecer a varios equipos, y `perfiles` solo tiene uno
    (ADR-33). Ver el comentario de `001_esquema_inicial.sql`.
    """

    organizacion_id: UUID
    rol: str
