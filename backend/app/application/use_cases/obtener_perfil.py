"""Caso de uso: obtener el perfil del usuario autenticado.

Es el caso de uso de `GET /api/v1/auth/me`. Tiene reglas propias, asi que no
es un passthrough:

1. Si el usuario no tiene perfil, la respuesta es `403` con el codigo
   `perfil_inexistente` (SP-07 de la HU-01). No 404 y no 500.
2. La organizacion y el rol efectivos salen de `organizaciones_miembros`, no de
   `perfiles` (ADR-33).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.perfil import PerfilDTO
from app.domain.errors import PerfilInexistenteError
from app.domain.ports.perfiles import PerfilRepository


@dataclass(frozen=True)
class ObtenerPerfil:
    """Resuelve el perfil del usuario y lo devuelve como DTO."""

    perfiles: PerfilRepository

    async def ejecutar(self, usuario_id: UUID) -> PerfilDTO:
        perfil = await self.perfiles.obtener(usuario_id)
        if perfil is None:
            raise PerfilInexistenteError()

        membresia = await self.perfiles.membresia_actual(usuario_id)

        return PerfilDTO(
            id=perfil.id,
            nombres=perfil.nombres,
            apellido_1=perfil.apellido_1,
            apellido_2=perfil.apellido_2,
            display_name=perfil.display_name,
            rol=membresia.rol if membresia else perfil.rol,
            organizacion_id=(
                membresia.organizacion_id if membresia else perfil.organizacion_id
            ),
            debe_cambiar_contrasena=perfil.debe_cambiar_contrasena,
        )
