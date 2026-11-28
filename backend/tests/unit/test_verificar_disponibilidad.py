"""Pruebas del caso de uso `VerificarDisponibilidad`.

La sonda de disponibilidad tiene que distinguir tres situaciones que para el
operador son distintas y que en el codigo se reducen a dos: la base responde y
el esquema esta aplicado, o no esta disponible. La razon exacta no viaja al
cliente (la ruta es publica), pero si tiene que quedar en el log.
"""

from __future__ import annotations

import pytest

from app.application.use_cases.verificar_disponibilidad import VerificarDisponibilidad
from app.domain.entities.salud import EstadoSalud
from app.domain.errors import ServicioNoDisponibleError

pytestmark = pytest.mark.unit


class SaludEnMemoria:
    """Implementacion del puerto de salud, en memoria."""

    def __init__(self, estado: EstadoSalud | None) -> None:
        self.estado = estado
        self.consultas = 0

    async def consultar(self) -> EstadoSalud | None:
        self.consultas += 1
        return self.estado


class TestDisponibilidad:
    """Cuando la base responde y el esquema esta aplicado, el servicio esta."""

    async def test_devuelve_el_dto_de_disponibilidad(self) -> None:
        caso = VerificarDisponibilidad(
            salud=SaludEnMemoria(EstadoSalud(roles_cargados=3, permisos_cargados=14)),
        )
        resultado = await caso.ejecutar()
        assert resultado.estado == "ok"
        assert resultado.roles_cargados == 3
        assert resultado.permisos_cargados == 14

    async def test_consulta_la_salud_una_vez(self) -> None:
        salud = SaludEnMemoria(EstadoSalud(roles_cargados=3, permisos_cargados=14))
        caso = VerificarDisponibilidad(salud=salud)
        await caso.ejecutar()
        assert salud.consultas == 1


class TestNoDisponible:
    """Cuando la base no esta, el error es 503 y no un 500."""

    async def test_sin_respuesta_de_la_base_es_503(self) -> None:
        caso = VerificarDisponibilidad(salud=SaludEnMemoria(None))
        with pytest.raises(ServicioNoDisponibleError) as excepcion:
            await caso.ejecutar()
        assert excepcion.value.status_http == 503

    async def test_sin_roles_cargados_es_503(self) -> None:
        """La vista existe pero el esquema no esta aplicado: no hay Roles."""
        caso = VerificarDisponibilidad(
            salud=SaludEnMemoria(EstadoSalud(roles_cargados=0, permisos_cargados=0)),
        )
        with pytest.raises(ServicioNoDisponibleError):
            await caso.ejecutar()
