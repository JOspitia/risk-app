"""Adaptador de salida del perfil de usuario.

Las consultas viajan con el **JWT del usuario**, no con la llave de servicio:
por eso RLS filtra las filas y el adaptador no decide que se puede ver. El
adaptador mapea filas; la politica vive en la base de datos.

Que el usuario no vea su propia fila no es un error del adaptador: significa
que no tiene perfil, que esta inactivo o que fue eliminado logicamente. En los
tres casos la respuesta es la misma (`SP-07` de la HU-01).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.columnas import (
    COLUMNAS_CONFIRMACION_CONTRASENA,
    COLUMNAS_MEMBRESIA,
    COLUMNAS_PERFIL,
)
from app.domain.entities.perfil import Membresia, Perfil

# La tabla del perfil del usuario.
TABLA_PERFILES = "perfiles"


class PerfilRepositorySupabase:
    """Implementa el puerto de perfiles sobre PostgREST."""

    def __init__(self, cliente: ClienteDatos) -> None:
        self._cliente = cliente

    async def obtener(self, usuario_id: UUID) -> Perfil | None:
        filas = await self._cliente.seleccionar(
            TABLA_PERFILES,
            COLUMNAS_PERFIL,
            {"id": f"eq.{usuario_id}"},
            limite=1,
        )
        if not filas:
            return None
        return _mapear_perfil(filas[0])

    async def confirmar_cambio_de_contrasena(self, usuario_id: UUID) -> None:
        """Limpia la bandera `debe_cambiar_contrasena` de la fila del usuario.

        El filtro va por `id` y la peticion lleva el JWT del usuario: la
        politica de actualizacion de `perfiles` deja escribir **solo** en la
        propia fila, y el trigger de la migracion 014 impide cambiar los
        datos que dan poder.
        """
        await self._cliente.actualizar(
            TABLA_PERFILES,
            {"id": f"eq.{usuario_id}"},
            {COLUMNAS_CONFIRMACION_CONTRASENA: False},
        )

    async def membresia_actual(self, usuario_id: UUID) -> Membresia | None:
        """La pertenencia vigente: la primera por orden de creacion.

        El orden es explicito porque `limit 1` sin `order by` no tiene orden
        garantizado, y el contexto de auditoria no puede depender de eso.
        """
        filas = await self._cliente.seleccionar(
            "organizaciones_miembros",
            COLUMNAS_MEMBRESIA,
            {"usuario_id": f"eq.{usuario_id}"},
            orden="creado_en.asc",
            limite=1,
        )
        if not filas:
            return None
        return Membresia(
            organizacion_id=UUID(str(filas[0]["organizacion_id"])),
            rol=str(filas[0]["rol"]),
        )


def _mapear_perfil(fila: dict[str, Any]) -> Perfil:
    """Fila de `perfiles` a entidad de dominio. Columna por columna."""
    return Perfil(
        id=UUID(str(fila["id"])),
        nombres=str(fila["nombres"]),
        apellido_1=str(fila["apellido_1"]),
        apellido_2=_texto_opcional(fila.get("apellido_2")),
        display_name=_texto_opcional(fila.get("display_name")),
        correo=str(fila["correo"]),
        rol=str(fila["rol"]),
        organizacion_id=_uuid_opcional(fila.get("organizacion_id")),
        debe_cambiar_contrasena=bool(fila["debe_cambiar_contrasena"]),
        activo=bool(fila["activo"]),
    )


def _texto_opcional(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor)
    return texto or None


def _uuid_opcional(valor: Any) -> UUID | None:
    if valor is None:
        return None
    return UUID(str(valor))
