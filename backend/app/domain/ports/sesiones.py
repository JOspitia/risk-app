"""Puerto de salida de las revocaciones de sesion.

El cierre de sesion tiene que ser efectivo **de inmediato**: un JWT es sin
estado, asi que verificar firma, `exp`, `aud` e `iss` no detecta que la sesion
se cerro. El registro de revocacion es lo que lo detecta (ADR-31).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID


class SesionRevocadaRepository(Protocol):
    """Consulta y registro de las sesiones revocadas."""

    async def esta_revocada(self, session_id: str) -> bool:
        """True si la sesion esta revocada y la revocacion sigue vigente.

        Una revocacion caduca con el token: cuando pasa `expira_en`, la fila ya
        no dice nada y el token tampoco sirve.
        """
        ...

    async def revocar(
        self,
        session_id: str,
        usuario_id: UUID,
        expira_en: datetime,
    ) -> None:
        """Registra la revocacion de la sesion.

        Levanta `SesionNoRevocableError` si la sesion no pertenece al usuario
        autenticado. La comprobacion vive en la base de datos, no aqui: el
        adaptador no decide politicas.
        """
        ...
