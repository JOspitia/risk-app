"""Entidad de dominio del estado de salud del esquema.

Es lo que la vista publica `public.salud` cuenta: cuantos roles y cuantos
permisos estan cargados. No es un dato de negocio y no pertenece a ninguna
persona: por eso la vista que lo produce es legible por todos.

Vive en `domain/` porque es un concepto del dominio ("el esquema esta
aplicado"), no un detalle de la tabla.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EstadoSalud:
    """Lo que el esquema tiene cargado.

    `roles_cargados` en cero significa que el esquema **no esta aplicado**: la
    tabla `roles` esta vacia, y sin la matriz de roles y permisos no hay
    permisos que resolver.
    """

    roles_cargados: int
    permisos_cargados: int
