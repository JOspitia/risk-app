"""Caso de uso: verificar la disponibilidad del servicio.

Es el caso de uso de `GET /ready`, la **sonda de disponibilidad**: dice si el
servicio puede recibir trafico ahora.

Se separa de `GET /health` a proposito, y la separacion es la decision de
diseno mas importante de este router:

- `/health` es la **sonda de supervivencia**: mira el proceso, no la base. El
  `HEALTHCHECK` del contenedor la consulta y solo mira el codigo de salida, asi
  que si dependiera de Supabase, un tropiezo de la base reiniciaria en bucle
  un contenedor de FastAPI que esta perfectamente sano.
- `/ready` es la **sonda de disponibilidad**: mira la base. Si Supabase no
  responde, o el esquema todavia no esta aplicado, responde 503 y el
  orquestador deja de mandar trafico en vez de reiniciar procesos.

El caso de uso **no conoce HTTP**: decide, y el adaptador de entrada traduce
el 503 al envelope.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.salud import DisponibilidadDTO
from app.domain.errors import ServicioNoDisponibleError
from app.domain.ports.salud import SaludRepository


@dataclass(frozen=True)
class VerificarDisponibilidad:
    """Consulta el estado del esquema y decide si el servicio esta disponible."""

    salud: SaludRepository

    async def ejecutar(self) -> DisponibilidadDTO:
        estado = await self.salud.consultar()
        if estado is None:
            # La base no responde, o la vista todavia no existe.
            raise ServicioNoDisponibleError()

        if estado.roles_cargados <= 0:
            # La vista existe pero el esquema no esta aplicado: sin la matriz
            # de roles y permisos no hay permisos que resolver.
            raise ServicioNoDisponibleError()

        return DisponibilidadDTO(
            estado="ok",
            roles_cargados=estado.roles_cargados,
            permisos_cargados=estado.permisos_cargados,
        )
