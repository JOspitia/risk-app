"""DTO de salida del perfil.

El caso de uso devuelve **DTOs**, no entidades crudas: la frontera de la API
decide que campos salen, y esa decision no se puede cambiar por accidente
agregando una columna a la entidad.

Los DTOs no son modelos de Pydantic: son datos puros. El adaptador de entrada
los convierte en `Resource`, que si es un modelo de la API.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PerfilDTO:
    """Lo que el caso de uso sabe del perfil del usuario autenticado.

    `organizacion_id` es la organizacion **efectiva**: la de la membresia
    vigente en `organizaciones_miembros`, que es donde se resuelve el
    aislamiento (ADR-33). Cuando el usuario no tiene membresia, se usa
    `perfiles.organizacion_id` como respaldo, para que el campo nunca sea una
    organizacion que no sea la del usuario.
    """

    id: UUID
    nombres: str
    apellido_1: str
    apellido_2: str | None
    display_name: str | None
    rol: str
    organizacion_id: UUID | None
    debe_cambiar_contrasena: bool
