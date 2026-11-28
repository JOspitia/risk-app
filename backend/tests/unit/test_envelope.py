"""El envelope de la API, sin base de datos ni red.

El envelope es **la misma forma** en exito y en error, y las marcas de tiempo
son cadenas RFC 3339. Son las dos cosas de las que depende el frontend para no
renderizar 1970 ni adivinar donde viene el error (`SKILL.md` 1.9 y 13.7).

La capa 7 completa, contra Supabase real, esta en
`tests/integration/test_envelope.py`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from app.adapters.http.responses import DetalleError, Respuesta

pytestmark = pytest.mark.unit

CAMPOS_DEL_ENVELOPE = {"success", "message", "data", "errors", "timestamp"}

# RFC 3339: una fecha, una `T`, una hora y un desfase (`Z` o `+hh:mm`).
RFC_3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


class TestExito:
    """La respuesta exitosa."""

    def test_tiene_los_cinco_campos(self) -> None:
        envelope = Respuesta.ok(data={"a": 1})
        assert set(envelope.model_dump()) == CAMPOS_DEL_ENVELOPE

    def test_los_errores_son_null(self) -> None:
        envelope = Respuesta.ok(data={"a": 1})
        assert envelope.errors is None
        assert envelope.success is True

    def test_el_mensaje_por_defecto_es_ok(self) -> None:
        assert Respuesta.ok(data=None).message == "OK"


class TestError:
    """La respuesta de error: la misma forma, con un codigo legible."""

    def test_tiene_los_cinco_campos(self) -> None:
        envelope = Respuesta.error(mensaje="No autenticado", codigo="no_autenticado")
        assert set(envelope.model_dump()) == CAMPOS_DEL_ENVELOPE

    def test_los_datos_son_null(self) -> None:
        envelope = Respuesta.error(mensaje="No autenticado", codigo="no_autenticado")
        assert envelope.data is None
        assert envelope.success is False

    def test_tra_el_codigo_legible_por_maquina(self) -> None:
        envelope = Respuesta.error(mensaje="No autenticado", codigo="no_autenticado")
        assert envelope.errors == [
            DetalleError(codigo="no_autenticado", detalle="No autenticado"),
        ]


class TestMarcaDeTiempo:
    """La marca de tiempo es una cadena RFC 3339, no un epoch decimal."""

    def test_es_una_cadena(self) -> None:
        serializado = Respuesta.ok(data=None).model_dump(mode="json")
        assert isinstance(serializado["timestamp"], str)

    def test_cumple_rfc_3339(self) -> None:
        serializado = Respuesta.ok(data=None).model_dump(mode="json")
        assert RFC_3339.match(serializado["timestamp"]), serializado["timestamp"]

    def test_no_es_un_epoch_decimal(self) -> None:
        serializado = Respuesta.ok(data=None).model_dump(mode="json")
        assert not serializado["timestamp"].replace(".", "", 1).isdigit()

    def test_parsea_al_ano_correcto(self) -> None:
        """Lo que hace `new Date(valor)` en JavaScript."""
        serializado = Respuesta.ok(data=None).model_dump(mode="json")
        instante = datetime.fromisoformat(serializado["timestamp"].replace("Z", "+00:00"))
        assert instante.year == datetime.now(UTC).year
        assert instante.tzinfo is not None

    def test_el_error_usa_la_misma_serie(self) -> None:
        serializado = Respuesta.error(mensaje="x", codigo="y").model_dump(mode="json")
        assert RFC_3339.match(serializado["timestamp"]), serializado["timestamp"]
