"""Pruebas del contexto de auditoria.

El contexto es lo que viaja hacia adentro: los casos de uso nunca ven el
token. Un contexto anonimo no es un error: es lo que ve una peticion sin
credencial, y la ruta protegida decide que hacer con el.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.application.audit.contexto import AuditContext

pytestmark = pytest.mark.unit

USUARIO_ID = UUID("3ad2a179-04be-4023-86ff-9bfb0660adf7")
ORGANIZACION_ID = UUID("c41a0000-0000-4000-8000-000000000001")


class TestContextoAnonimo:
    """Sin credencial, el contexto existe pero no identifica a nadie."""

    def test_esta_vacio(self) -> None:
        contexto = AuditContext()
        assert contexto.usuario_id is None
        assert contexto.session_id is None
        assert contexto.rol is None
        assert contexto.organizacion_id is None

    def test_se_reconoce_como_anonimo(self) -> None:
        assert AuditContext().es_anonimo is True


class TestContextoIdentificado:
    """Con credencial valida, el contexto lleva los siete campos."""

    def test_lleva_los_datos_del_actor(self) -> None:
        contexto = AuditContext(
            usuario_id=USUARIO_ID,
            nombre="Ana Restrepo Duque",
            session_id="e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd",
            rol="analista",
            organizacion_id=ORGANIZACION_ID,
            accion="sesion.cerrada",
            ip="127.0.0.1",
        )
        assert contexto.usuario_id == USUARIO_ID
        assert contexto.nombre == "Ana Restrepo Duque"
        assert contexto.session_id == "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"
        assert contexto.rol == "analista"
        assert contexto.organizacion_id == ORGANIZACION_ID
        assert contexto.accion == "sesion.cerrada"
        assert contexto.ip == "127.0.0.1"

    def test_no_se_reconoce_como_anonimo(self) -> None:
        assert AuditContext(usuario_id=USUARIO_ID).es_anonimo is False

    def test_es_inmutable(self) -> None:
        """El contexto se transporta, no se modifica en caliente."""
        contexto = AuditContext(usuario_id=USUARIO_ID)
        with pytest.raises(AttributeError):
            contexto.usuario_id = ORGANIZACION_ID  # type: ignore[misc]
