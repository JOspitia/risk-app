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

    async def confirmar_cambio_de_contrasena(self, usuario_id: UUID) -> None:
        """Confirma el cambio de credencial del usuario.

        Limpia la bandera `debe_cambiar_contrasena` de la fila del usuario.
        **No cambia la credencial**: esa vive en Supabase Auth (ADR-05) y no
        entra al proyecto.

        El metodo no dice a que fila escribe: es la del `usuario_id` que
        recibe, y la base de datos no deja que sea otra.
        """
        ...
