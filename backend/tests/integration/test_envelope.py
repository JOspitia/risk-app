"""Capa 7 — Contrato de serializacion, contra Supabase real.

El integrador de frontend se amarra a esto, asi que se prueba **sobre el
cuerpo real de la respuesta**, no sobre la configuracion (`SKILL.md` 13.7).

Lo que se afirma:

- Las marcas de tiempo son cadenas RFC 3339, no epoch decimal.
- `new Date(valor)` en JavaScript devuelve el anio correcto.
- Los booleanos son `true`/`false`, no `0`/`1` ni `"true"`.
- Los nulos son `null` explicito: ni claves ausentes ni `"null"`.
- El envelope es el mismo en exito y en error.
- El envelope de error trae un identificador legible por maquina.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from .conftest import UsuarioDePrueba

pytestmark = pytest.mark.integration

RUTA_PERFIL = "/api/v1/auth/me"

CAMPOS_DEL_ENVELOPE = {"success", "message", "data", "errors", "timestamp"}

# RFC 3339: una fecha, una `T`, una hora y un desfase (`Z` o `+hh:mm`).
RFC_3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
)


class TestMarcasDeTiempo:
    """La marca de tiempo es una cadena, y del formato que espera JavaScript."""

    def test_la_marca_de_tiempo_es_una_cadena(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert isinstance(cuerpo["timestamp"], str)

    def test_la_marca_de_tiempo_cumple_rfc_3339(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert RFC_3339.match(cuerpo["timestamp"]), cuerpo["timestamp"]

    def test_la_marca_de_tiempo_no_es_un_epoch_decimal(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """Un epoch decimal pasa las pruebas de status y rompe el frontend."""
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert not cuerpo["timestamp"].replace(".", "", 1).isdigit()

    def test_la_marca_de_tiempo_parsea_al_ano_correcto(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """Lo que hace `new Date(valor)` en JavaScript: el anio, no 1970."""
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        instante = datetime.fromisoformat(cuerpo["timestamp"].replace("Z", "+00:00"))
        assert instante.year == datetime.now(UTC).year
        assert instante.tzinfo is not None

    def test_el_error_tiene_la_misma_forma_de_marca_de_tiempo(self, cliente: TestClient) -> None:
        cuerpo = cliente.get(RUTA_PERFIL).json()
        assert RFC_3339.match(cuerpo["timestamp"]), cuerpo["timestamp"]


class TestFormaDelEnvelope:
    """El envelope es el mismo en exito y en error."""

    def test_el_exito_tiene_los_cinco_campos(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE

    def test_el_error_tiene_los_mismos_cinco_campos(self, cliente: TestClient) -> None:
        cuerpo = cliente.get(RUTA_PERFIL).json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE

    def test_en_exito_los_errores_son_null(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert cuerpo["errors"] is None
        assert cuerpo["success"] is True

    def test_en_error_los_datos_son_null(self, cliente: TestClient) -> None:
        cuerpo = cliente.get(RUTA_PERFIL).json()
        assert cuerpo["data"] is None
        assert cuerpo["success"] is False

    def test_el_error_trae_un_identificador_legible_por_maquina(self, cliente: TestClient) -> None:
        cuerpo = cliente.get(RUTA_PERFIL).json()
        assert isinstance(cuerpo["errors"], list)
        assert cuerpo["errors"][0]["codigo"] == "no_autenticado"
        assert cuerpo["errors"][0]["detalle"]


class TestTipos:
    """Booleanos, nulos e identificadores, en el cuerpo real."""

    def test_los_booleanos_son_booleanos_json(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario_de_prueba().token}"},
        ).json()
        assert cuerpo["data"]["debe_cambiar_contrasena"] is False

    def test_los_nulos_son_nulos_explicitos(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """`apellido_2` es `null`, no una clave ausente ni el texto `"null"`."""
        usuario = usuario_de_prueba(apellido_2=None)
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario.token}"},
        ).json()
        assert "apellido_2" in cuerpo["data"]
        assert cuerpo["data"]["apellido_2"] is None

    def test_los_identificadores_son_cadenas_sin_perder_presicion(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        cuerpo = cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {usuario.token}"},
        ).json()
        assert isinstance(cuerpo["data"]["id"], str)
        assert cuerpo["data"]["id"] == usuario.id
