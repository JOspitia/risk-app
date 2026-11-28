"""Pruebas de los errores de dominio.

Cada error lleva su propia semantica HTTP. Si un error pierde su codigo de
estado, el manejador global degrada a 500 todo error de negocio, y eso pasa
sin que nadie lo note: por eso se afirma el codigo exacto de cada uno.
"""

from __future__ import annotations

import pytest

from app.domain.errors import (
    ConflictoError,
    ErrorDominio,
    ErrorInesperado,
    NoAutenticadoError,
    NoEncontradoError,
    PerfilInexistenteError,
    ProhibidoError,
    SesionNoRevocableError,
    ValidacionError,
)

pytestmark = pytest.mark.unit


class TestSemanticaHttp:
    """El mapeo de `SKILL.md` 1.10, error por error."""

    @pytest.mark.parametrize(
        ("error", "status_esperado"),
        [
            (ValidacionError(), 400),
            (NoAutenticadoError(), 401),
            (ProhibidoError(), 403),
            (PerfilInexistenteError(), 403),
            (SesionNoRevocableError(), 403),
            (NoEncontradoError(), 404),
            (ConflictoError(), 409),
            (ErrorInesperado(), 500),
        ],
    )
    def test_el_codigo_de_estado_es_el_previsto(
        self,
        error: ErrorDominio,
        status_esperado: int,
    ) -> None:
        assert error.status_http == status_esperado

    def test_el_codigo_legible_por_maquina_es_el_previsto(self) -> None:
        assert NoAutenticadoError().codigo == "no_autenticado"
        assert PerfilInexistenteError().codigo == "perfil_inexistente"
        assert ProhibidoError().codigo == "prohibido"
        assert ValidacionError().codigo == "validacion"
        assert ConflictoError().codigo == "conflicto"
        assert ErrorInesperado().codigo == "error_inesperado"

    def test_todos_heredan_de_la_base(self) -> None:
        for error in (
            ValidacionError(),
            NoAutenticadoError(),
            ProhibidoError(),
            PerfilInexistenteError(),
            NoEncontradoError(),
            ConflictoError(),
            ErrorInesperado(),
        ):
            assert isinstance(error, ErrorDominio)


class TestMensaje:
    """El mensaje es el que ve la persona; el codigo, el que ve la maquina."""

    def test_el_mensaje_por_defecto_no_es_vacio(self) -> None:
        assert NoAutenticadoError().mensaje

    def test_un_mensaje_propio_reemplaza_al_por_defecto(self) -> None:
        error = NoAutenticadoError("El token ya expiro")
        assert error.mensaje == "El token ya expiro"
        assert str(error) == "El token ya expiro"

    def test_el_error_inesperado_conserva_el_detalle_original(self) -> None:
        """El detalle no viaja al cliente, pero no se pierde para la depuracion."""
        error = ErrorInesperado(detalle="violacion de integridad")
        assert error.detalle == "violacion de integridad"
