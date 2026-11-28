"""El contrato OpenAPI de la API.

El archivo `openapi.json` de este directorio es un **fixture generado por este
test**, no un archivo escrito a mano: la fuente de verdad es el codigo, y el
snapshot solo detecta que el contrato cambio.

Es lo que consume `npm run api:types` del frontend
(`openapi-typescript ../backend/tests/contract/openapi.json`), asi que el
generador de tipos tiene entrada desde el primer dia.

Para regenerarlo a proposito:

    ACTUALIZAR_CONTRATO=1 pytest tests/contract
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import crear_app

pytestmark = pytest.mark.contract

RUTA_DEL_SNAPSHOT = Path(__file__).parent / "openapi.json"
VARIABLE_PARA_REGENERAR = "ACTUALIZAR_CONTRATO"


@pytest.fixture
def cliente() -> TestClient:
    """La aplicacion real. El contrato no depende de la base de datos."""
    config = Config(
        supabase_url="https://ejemplo.supabase.co",
        supabase_anon_key="pub",
        supabase_service_role_key="srv",
    )
    with TestClient(crear_app(config=config)) as cliente_http:
        yield cliente_http


def _serializar(documento: dict[str, object]) -> str:
    """El snapshot, con un formato estable: el orden de las claves no importa."""
    return json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_el_contrato_openapi_no_cambio(cliente: TestClient) -> None:
    """El contrato de la API es estable (`CHECKLIST.md`, Gate 9)."""
    actual = _serializar(cliente.get("/openapi.json").json())

    regenerar = os.environ.get(VARIABLE_PARA_REGENERAR) == "1"
    if regenerar or not RUTA_DEL_SNAPSHOT.exists():
        RUTA_DEL_SNAPSHOT.write_text(actual, encoding="utf-8")

    esperado = RUTA_DEL_SNAPSHOT.read_text(encoding="utf-8")
    assert esperado == actual, (
        "El contrato OpenAPI cambio. Si el cambio es intencional, regenera el "
        f"snapshot con {VARIABLE_PARA_REGENERAR}=1 y revisa el diff."
    )


def test_el_snapshot_declara_las_rutas_de_autenticacion(cliente: TestClient) -> None:
    """Las rutas que el frontend necesita estan en el contrato."""
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/api/v1/auth/me" in rutas
    assert "/api/v1/auth/logout" in rutas
    assert "/api/v1/auth/login" not in rutas


def test_el_snapshot_describe_el_envelope(cliente: TestClient) -> None:
    """El envelope es el mismo en exito y en error, y esta documentado."""
    componentes = cliente.get("/openapi.json").json()["components"]["schemas"]
    assert "Respuesta_PerfilResource_" in componentes
    envelope = componentes["Respuesta_PerfilResource_"]
    assert set(envelope["properties"]) == {
        "success",
        "message",
        "data",
        "errors",
        "timestamp",
    }
