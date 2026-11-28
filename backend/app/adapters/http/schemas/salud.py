"""Recursos de la API de salud.

El Resource es **la frontera de seguridad**: decide que campos salen. La sonda
de disponibilidad expone el **catalogo** del sistema (cuantos roles y permisos
estan cargados), no datos de persona: ni correos, ni roles asignados, ni
documentos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.application.dto.salud import DisponibilidadDTO


class DisponibilidadResource(BaseModel):
    """Lo que el cliente ve de la disponibilidad del servicio."""

    estado: str = Field(description="`ok` cuando el servicio puede recibir trafico")
    roles_cargados: int = Field(description="Roles cargados en el esquema")
    permisos_cargados: int = Field(description="Permisos cargados en el esquema")

    @classmethod
    def from_model(cls, disponibilidad: DisponibilidadDTO) -> DisponibilidadResource:
        return cls(
            estado=disponibilidad.estado,
            roles_cargados=disponibilidad.roles_cargados,
            permisos_cargados=disponibilidad.permisos_cargados,
        )
