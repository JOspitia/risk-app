"""Recursos de la API de autenticacion.

El Resource es **la frontera de seguridad**: decide que campos salen. Agregar
una columna a la entidad no agrega un campo al Resource, y por eso el
`password_hash`, el refresh token o cualquier columna interna no pueden
aparecer en una respuesta sin que alguien lo escriba aqui (CA-07).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.application.dto.perfil import PerfilDTO
from app.application.dto.sesion import CierreSesionDTO


class PerfilResource(BaseModel):
    """Lo que el cliente ve del perfil.

    No expone `auth.users`, ni el hash de la contrasena, ni el refresh token,
    ni la llave de servicio. Solo lo que la HU-01 describe.
    """

    id: UUID = Field(description="Identificador del usuario")
    nombres: str
    apellido_1: str
    apellido_2: str | None = None
    display_name: str | None = None
    rol: str = Field(description="Rol efectivo del usuario")
    organizacion_id: UUID | None = Field(
        default=None,
        description="Organizacion efectiva del usuario. Nula si no pertenece a ninguna.",
    )
    debe_cambiar_contrasena: bool = False

    @classmethod
    def from_model(cls, perfil: PerfilDTO) -> PerfilResource:
        return cls(
            id=perfil.id,
            nombres=perfil.nombres,
            apellido_1=perfil.apellido_1,
            apellido_2=perfil.apellido_2,
            display_name=perfil.display_name,
            rol=perfil.rol,
            organizacion_id=perfil.organizacion_id,
            debe_cambiar_contrasena=perfil.debe_cambiar_contrasena,
        )


class CierreSesionResource(BaseModel):
    """Confirmacion del cierre de sesion."""

    session_id: str = Field(description="Sesion revocada")
    revocado: bool

    @classmethod
    def from_model(cls, cierre: CierreSesionDTO) -> CierreSesionResource:
        return cls(session_id=cierre.session_id, revocado=cierre.revocado)
