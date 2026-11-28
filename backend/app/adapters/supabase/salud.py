"""Adaptador de salida del estado de salud del esquema.

Lee la vista publica `public.salud`, que cuenta los roles y los permisos
cargados. La vista la crea la migracion 013.

**La credencial que viaja es la del usuario, nunca la llave de servicio.** La
vista no contiene datos de persona: por eso es legible por `anon` y por
`authenticated`, y por eso la sonda no necesita privilegios de servicio. Con la
llave de servicio, RLS no aplicaria y la sonda estaria mintiendo sobre lo que
el servidor veria de verdad.

El adaptador traduce las tres razones por las que no hay estado a una sola
respuesta (`None`):

1. **Supabase no responde.** Es un fallo de red, no de negocio.
2. **La vista no existe todavia.** El esquema no esta aplicado: PostgREST
   responde 404 con el codigo `PGRST205`.
3. **El rol de la peticion no puede leer la vista.** Es un problema de
   permisos del despliegue, no del esquema.

El motivo exacto **no viaja al cliente** (la sonda es publica): queda en el
log, donde si sirve para diagnosing.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.columnas import COLUMNAS_SALUD
from app.domain.entities.salud import EstadoSalud
from app.domain.errors import (
    NoAutenticadoError,
    NoEncontradoError,
    ProhibidoError,
)

logger = logging.getLogger(__name__)

# La vista publica que cuenta el catalogo del esquema.
VISTA_SALUD = "salud"

# La sonda no puede quedarse esperando a la base: si la base no responde, la
# sonda tiene que responder ella. Dos segundos es el techo.
TIMEOUT_SALUD = 2.0


class SaludRepositorySupabase:
    """Implementa el puerto de salud sobre PostgREST."""

    def __init__(self, cliente: ClienteDatos) -> None:
        self._cliente = cliente

    async def consultar(self) -> EstadoSalud | None:
        """El estado del esquema, o `None` si no se pudo saber."""
        try:
            filas = await self._cliente.seleccionar(
                VISTA_SALUD,
                COLUMNAS_SALUD,
                {},
                limite=1,
                timeout=TIMEOUT_SALUD,
            )
        except (httpx.HTTPError, NoEncontradoError, ProhibidoError, NoAutenticadoError) as exc:
            logger.warning("La sonda de disponibilidad no pudo leer la vista: %s", exc)
            return None

        if not filas:
            logger.warning("La sonda de disponibilidad no recibio filas de la vista")
            return None

        return _mapear_estado(filas[0])


def _mapear_estado(fila: dict[str, Any]) -> EstadoSalud:
    """Fila de `public.salud` a la entidad de dominio."""
    return EstadoSalud(
        roles_cargados=int(fila.get("roles_cargados") or 0),
        permisos_cargados=int(fila.get("permisos_cargados") or 0),
    )
