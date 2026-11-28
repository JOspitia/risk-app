"""Puerto de salida del estado de salud del esquema.

Lo define el dominio y lo implementa la infraestructura
(`adapters/supabase`). El dominio no sabe que existe Supabase, ni una vista,
ni una tabla: solo sabe que puede preguntar si el esquema esta aplicado.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.salud import EstadoSalud


class SaludRepository(Protocol):
    """Lectura del estado de salud del esquema."""

    async def consultar(self) -> EstadoSalud | None:
        """Devuelve el estado del esquema, o `None` si no se pudo saber.

        `None` cubre las dos razones por las que no hay estado: la base de
        datos no responde, o el esquema todavia no esta aplicado. El dominio
        no las distingue porque para el usuario final son lo mismo: el
        servicio no esta disponible.

        El motivo exacto no viaja al cliente (la sonda es publica): lo
        distingue el adaptador, que lo deja en el log.
        """
        ...
