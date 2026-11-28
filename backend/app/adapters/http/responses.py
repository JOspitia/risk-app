"""El envelope de la API: una sola forma, en exito y en error.

Toda respuesta del backend tiene los mismos cinco campos: `success`, `message`,
`data`, `errors` y `timestamp`. El cliente no tiene que adivinar si un error
viene en `data` o en `errors`, y un error **siempre** trae un identificador
legible por maquina (`codigo`), no solo prosa.

Las marcas de tiempo son cadenas **RFC 3339** (`2026-11-27T12:00:00Z`). No un
epoch decimal: JavaScript espera milisegundos, la API envia segundos, y el
cliente renderiza 1970 sin error en ninguna parte (`SKILL.md` 12.10 y 13.7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_serializer


def marca_de_tiempo() -> datetime:
    """Instante actual, en UTC y con zona horaria explicita."""
    return datetime.now(UTC)


class DetalleError(BaseModel):
    """Un error de la respuesta.

    `codigo` es el identificador estable que el cliente decide con (por
    ejemplo `no_autenticado`); `detalle` es la explicacion para una persona.
    """

    codigo: str
    detalle: str


class Respuesta[T](BaseModel):
    """El envelope. La misma forma en exito y en error."""

    success: bool
    message: str
    data: T | None = None
    errors: list[DetalleError] | None = None
    timestamp: datetime

    @classmethod
    def ok(cls, data: T, mensaje: str = "OK") -> Respuesta[T]:
        """Respuesta exitosa. `errors` es `null`, no una lista vacia."""
        return cls(
            success=True,
            message=mensaje,
            data=data,
            errors=None,
            timestamp=marca_de_tiempo(),
        )

    @classmethod
    def error(cls, mensaje: str, codigo: str, detalle: str | None = None) -> Respuesta[Any]:
        """Respuesta de error. `data` es `null`, no un objeto vacio."""
        return cls(
            success=False,
            message=mensaje,
            data=None,
            errors=[DetalleError(codigo=codigo, detalle=detalle or mensaje)],
            timestamp=marca_de_tiempo(),
        )

    @field_serializer("timestamp", mode="plain", return_type=str)
    def _serializar_timestamp(self, valor: datetime) -> str:
        """RFC 3339 con `Z`: es lo que `new Date(valor)` entiende sin ambiguedad."""
        return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")
