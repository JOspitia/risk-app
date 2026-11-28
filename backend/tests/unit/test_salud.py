"""Pruebas del router de salud.

El router de salud tiene **dos** sondas, y cada una tiene una obligacion
distinta:

1. `GET /health` es la **sonda de supervivencia**: comprueba que el proceso
   esta vivo. **No toca la base de datos**, y por eso responde 200 siempre. Es
   la que consulta el `HEALTHCHECK` del contenedor: si dependiera de Supabase,
   un tropiezo de la base reiniciaria en bucle un contenedor sano.
2. `GET /ready` es la **sonda de disponibilidad**: consulta la vista publica
   `public.salud` y dice si el servicio puede recibir trafico. Responde 503 si
   Supabase no responde o si el esquema todavia no esta aplicado.

Ademas, las dos devuelven el **mismo envelope** que el resto de la API: una
sola forma de leer una respuesta, tambien en un endpoint sin token. Y ninguna
filtra informacion: una ruta sin token que devuelve la URL de Supabase o el
emisor del JWT es una ruta abierta a cualquiera que la llame.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config

from .conftest import BaseDeDatosFalsa

pytestmark = pytest.mark.unit

CAMPOS_DEL_ENVELOPE = {"success", "message", "data", "errors", "timestamp"}


class TestHealth:
    """La comprobacion de vida del proceso."""

    def test_responde_200(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health")
        assert respuesta.status_code == 200

    def test_devuelve_el_estado_ok(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health")
        assert respuesta.json()["data"] == {"estado": "ok"}

    def test_devuelve_el_envelope_de_la_api(self, cliente: TestClient) -> None:
        """La sonda usa la misma forma que el resto de la API.

        Un endpoint sin token tambien devuelve envelope: el cliente no tiene que
        aprender una segunda forma de leer una respuesta.
        """
        cuerpo = cliente.get("/health").json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE
        assert cuerpo["success"] is True
        assert cuerpo["errors"] is None

    def test_no_pide_autenticacion(self, cliente: TestClient) -> None:
        """Sin token, y sin ninguna peticion de autenticacion que lo pida.

        Es lo que permite usarlo como `HEALTHCHECK`: si exigiera autenticacion,
        el contenedor se declararia caido aunque la API funcionara.
        """
        respuesta = cliente.get("/health")
        assert respuesta.status_code == 200
        assert "www-authenticate" not in {clave.lower() for clave in respuesta.headers}

    def test_no_consulta_la_base_de_datos(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """La sonda de supervivencia no depende de Supabase.

        Si dependiera de la base, un tropiezo de Supabase haria que el
        orquestador reiniciara en bucle un contenedor de FastAPI que esta
        perfectamente sano.
        """
        cliente.get("/health")
        assert base_de_datos.peticiones == []

    def test_responde_200_aunque_la_base_no_responda(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        base_de_datos.caida = True
        respuesta = cliente.get("/health")
        assert respuesta.status_code == 200


class TestReady:
    """La comprobacion de disponibilidad: la base responde y el esquema esta."""

    def test_responde_200(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 200

    def test_devuelve_el_envelope_de_la_api(self, cliente: TestClient) -> None:
        cuerpo = cliente.get("/ready").json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE
        assert cuerpo["success"] is True
        assert cuerpo["errors"] is None

    def test_reporta_los_roles_y_los_permisos_cargados(self, cliente: TestClient) -> None:
        """Lo que la vista `public.salud` dice del esquema."""
        datos = cliente.get("/ready").json()["data"]
        assert datos["estado"] == "ok"
        assert datos["roles_cargados"] == 3
        assert datos["permisos_cargados"] == 14

    def test_no_pide_autenticacion(self, cliente: TestClient) -> None:
        """Es una sonda de la plataforma, no un endpoint de negocio."""
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 200
        assert "www-authenticate" not in {clave.lower() for clave in respuesta.headers}

    def test_consulta_la_vista_de_salud(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        cliente.get("/ready")
        assert base_de_datos.peticiones
        assert base_de_datos.peticiones[0].url.path.endswith("/salud")

    def test_la_consulta_es_parametrizada(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """Las columnas van como parametro de la peticion, no pegadas en la ruta."""
        cliente.get("/ready")
        url = str(base_de_datos.peticiones[0].url)
        assert "select=roles_cargados" in url
        assert "permisos_cargados" in url

    def test_la_llave_de_servicio_no_viaja(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """CA-08: la llave de servicio no atiende peticiones de usuario."""
        cliente.get("/ready")
        for peticion in base_de_datos.peticiones:
            assert "srv" not in peticion.headers.get("authorization", "")


class TestReadySinBase:
    """Cuando la base no esta disponible, la sonda lo dice con 503."""

    def test_sin_la_vista_responde_503(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """La vista todavia no existe: el esquema no esta aplicado."""
        base_de_datos.salud = None
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 503

    def test_sin_la_base_responde_503(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """Supabase no responde."""
        base_de_datos.caida = True
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 503

    def test_sin_esquema_responde_503(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """La vista existe pero no hay roles cargados: el esquema no esta aplicado."""
        base_de_datos.salud = [{"roles_cargados": 0, "permisos_cargados": 0}]
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 503

    def test_el_error_devuelve_el_envelope(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """El 503 sale con la misma forma que cualquier otra respuesta."""
        base_de_datos.salud = None
        cuerpo = cliente.get("/ready").json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE
        assert cuerpo["success"] is False
        assert cuerpo["data"] is None
        assert cuerpo["errors"][0]["codigo"] == "no_disponible"

    def test_el_error_no_filtra_la_infraestructura(
        self,
        cliente: TestClient,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """Una ruta sin token no dice como esta la base por dentro."""
        base_de_datos.caida = True
        texto = cliente.get("/ready").text
        assert "ejemplo.supabase.co" not in texto
        assert "ConnectError" not in texto


class TestHealthConfig:
    """La comprobacion de que la configuracion se leyo."""

    def test_responde_200(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/health/config")
        assert respuesta.status_code == 200

    def test_confirma_que_las_variables_obligatorias_estan(self, cliente: TestClient) -> None:
        cuerpo = cliente.get("/health/config").json()["data"]
        assert cuerpo["supabase_url_configurada"] is True
        assert cuerpo["anon_key_configurada"] is True
        assert cuerpo["service_role_key_configurada"] is True

    def test_no_devuelve_el_valor_de_las_variables(self, cliente: TestClient) -> None:
        """La garantia que hace que esta ruta sea publicable.

        El cuerpo no puede contener la URL, ni la llave, ni el emisor del JWT.
        """
        cuerpo = cliente.get("/health/config").json()["data"]

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
