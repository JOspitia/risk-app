"""Pruebas del router de salud.

El router de salud es la unica ruta de la API que responde sin token, asi que
tiene dos obligaciones que probar:

1. Responde 200 con un cuerpo minimo: es lo que consulta el `HEALTHCHECK` del
   contenedor y lo que consulta el despliegue antes de mandar trafico.
2. **No filtra informacion.** Devuelve si las variables estan presentes, nunca
   sus valores. Una ruta sin token que devuelve la URL de Supabase o el emisor
   del JWT es una ruta abierta a cualquiera que la llame.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import crear_app


@pytest.fixture
def cliente() -> TestClient:
    """Cliente de pruebas sobre la aplicacion real."""
    return TestClient(crear_app())


class TestHealth:
    """La comprobacion de vida del proceso."""

    def test_responde_200(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health")
        assert respuesta.status_code == 200

    def test_devuelve_el_estado_ok(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health")
        assert respuesta.json() == {"estado": "ok"}

    def test_no_pide_autenticacion(self, cliente: TestClient) -> None:
        """Sin token, y sin ninguna peticion de autenticacion que lo pida.

        Es lo que permite usarlo como `HEALTHCHECK`: si exigiera autenticacion,
        el contenedor se declararia caido aunque la API funcionara.
        """
        respuesta = cliente.get("/health")
        assert respuesta.status_code == 200
        assert "www-authenticate" not in {clave.lower() for clave in respuesta.headers}


class TestHealthConfig:
    """La comprobacion de que la configuracion se leyo."""

    def test_responde_200(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health/config")
        assert respuesta.status_code == 200

    def test_confirma_que_las_variables_obligatorias_estan(self, cliente: TestClient) -> None:
        cuerpo = cliente.get("/health/config").json()
        assert cuerpo["supabase_url_configurada"] is True
        assert cuerpo["anon_key_configurada"] is True
        assert cuerpo["service_role_key_configurada"] is True

    def test_no_devuelve_el_valor_de_las_variables(self, cliente: TestClient) -> None:
        """La garantia que hace que esta ruta sea publicable.

        El cuerpo no puede contener la URL, ni la llave, ni el emisor del JWT.
        """
        cuerpo = cliente.get("/health/config").json()

        config = obtener_config_de_prueba()

        assert config.supabase_url not in str(cuerpo)
        assert config.supabase_anon_key not in str(cuerpo)
        assert config.supabase_service_role_key not in str(cuerpo)
        assert config.jwt_issuer not in str(cuerpo)

        # Y tampoco hay un campo con un nombre que invite a ponerlos.
        assert set(cuerpo) == {
            "estado",
            "supabase_url_configurada",
            "anon_key_configurada",
            "service_role_key_configurada",
        }


def obtener_config_de_prueba() -> Config:
    """La configuracion con la que se construyo la app en la prueba."""
    return Config(
        supabase_url="https://ejemplo.supabase.co",
        supabase_anon_key="pub",
        supabase_service_role_key="srv",
    )
