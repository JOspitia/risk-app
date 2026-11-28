"""DTO de salida de la disponibilidad del servicio.

El caso de uso devuelve **DTOs**, no entidades crudas: la frontera de la API
decide que campos salen, y esa decision no se puede cambiar por accidente
agregando una columna a la entidad.

Los DTOs no son modelos de Pydantic: son datos puros. El adaptador de entrada
los convierte en `Resource`, que si es un modelo de la API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisponibilidadDTO:
    """Lo que la sonda de disponibilidad sabe del servicio.

    `estado` es `"ok"` cuando el servicio puede recibir trafico. Los conteos
    son del catalogo del sistema: no describen a ninguna persona.
    """

    estado: str
    roles_cargados: int
    permisos_cargados: int
