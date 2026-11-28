"""Puerto de salida del perfil de usuario.

Lo define el dominio y lo implementa la infraestructura (`adapters/supabase`).
El dominio no sabe que existe Supabase: por eso el metodo no habla de tablas
ni de tokens, sino de perfiles y de membresias.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.perfil import Membresia, Perfil


class PerfilRepository(Protocol):
    """Lectura del perfil del usuario y de su organizacion activa."""

    async def obtener(self, usuario_id: UUID) -> Perfil | None:
        """Devuelve el perfil del usuario, o `None` si no tiene fila.

        `None` cubre los dos casos que el backend no puede distinguir con el
        JWT del usuario: que no exista la fila, o que RLS la oculte (porque el
        usuario esta inactivo o eliminado logicamente).
        """
        ...

    async def membresia_actual(self, usuario_id: UUID) -> Membresia | None:
        """Devuelve la pertenencia vigente del usuario, o `None` si no tiene.

        La organizacion efectiva y el rol efectivo salen de aqui, no de
        `perfiles` (ADR-33).
        """
        ...
