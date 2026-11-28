"""Adaptador de salida de las revocaciones de sesion.

La revocacion se pide a Postgres por RPC: la comprobacion de pertenencia de la
sesion vive **dentro de la funcion**, en la misma transaccion, y no en el
código de Python (`SKILL.md` 6.1).

El registro es de **solo agregado**: nunca se borra una fila para "desrevocar"
una sesion. Se espera a que expire el token (`SKILL.md` 5.3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.columnas import COLUMNAS_SESION_REVOCADA

# La funcion de Postgres que registra la revocacion y comprueba la pertenencia.
FUNCION_REVOCAR_SESION = "revocar_sesion"


class SesionRevocadaRepositorySupabase:
    """Implementa el puerto de revocaciones sobre PostgREST."""

    def __init__(self, cliente: ClienteDatos) -> None:
        self._cliente = cliente

    async def esta_revocada(self, session_id: str) -> bool:
        """True si la revocacion sigue vigente.

        El filtro por `expira_en` lo hace la base de datos: la revocacion
        caduca con el token, y comparar fechas en Python meteria el reloj del
        backend en la decision.
        """
        ahora = datetime.now(UTC).isoformat()
        filas = await self._cliente.seleccionar(
            "sesiones_revocadas",
            COLUMNAS_SESION_REVOCADA,
            {"session_id": f"eq.{session_id}", "expira_en": f"gt.{ahora}"},
            limite=1,
        )
        return bool(filas)

    async def revocar(
        self,
        session_id: str,
        usuario_id: UUID,
        expira_en: datetime,
    ) -> None:
        """Registra la revocacion.

        `usuario_id` no viaja: lo toma la funcion de `auth.uid()`, que es el
        usuario autenticado de la peticion. Mandarlo como parametro abriria la
        puerta a revocar la sesion de otro.
        """
        await self._cliente.llamar_rpc(
            FUNCION_REVOCAR_SESION,
            {
                "p_session_id": session_id,
                "p_expira_en": expira_en.astimezone(UTC).isoformat(),
            },
        )
