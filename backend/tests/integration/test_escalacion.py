"""Pruebas del cierre de la escalada de privilegios en `perfiles`.

La politica `perfiles_actualizacion` (migracion 002) no miraba las columnas:
su `with check` solo comprobaba de que fila se trataba. Un usuario
autenticado podia hacer `UPDATE` de su propia fila y cambiarse `rol`, `activo`
u `organizacion_id` a mano. La migracion 014 lo cierra con un trigger
`BEFORE UPDATE` que compara la fila vieja con la nueva.

Estas pruebas van contra el Supabase local: un mock de repositorio no
detectaria un error de politica, que es justo lo que se esta probando.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Config

from .conftest import AdministracionSupabase, UsuarioDePrueba, actualizar_perfil

pytestmark = pytest.mark.integration


@pytest.fixture
def usuario_normal(usuario_de_prueba: Any) -> UsuarioDePrueba:
    """Un usuario del equipo: no tiene `usuarios.gestionar`."""
    return usuario_de_prueba(rol="analista")


@pytest.fixture
def administrador(usuario_de_prueba: Any) -> UsuarioDePrueba:
    """Un usuario con `usuarios.gestionar`: administra usuarios (HU-03)."""
    return usuario_de_prueba(rol="admin")


def _cambiar(
    config_local: Config,
    token: str,
    usuario_id: str,
    cambios: dict[str, Any],
) -> Any:
    return actualizar_perfil(
        config_local.supabase_url,
        config_local.supabase_anon_key,
        token,
        usuario_id,
        cambios,
    )


class TestEscaladaDePrivilegios:
    """Un usuario normal no puede cambiarse los datos que dan poder."""

    def test_no_puede_cambiarse_el_rol(
        self,
        config_local: Config,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        """Con la politica vieja, un usuario se hacia `admin` a si mismo."""
        respuesta = _cambiar(
            config_local,
            usuario_normal.token,
            usuario_normal.id,
            {"rol": "admin"},
        )
        assert respuesta.status_code == 403

    def test_no_puede_activarse_a_si_mismo(
        self,
        config_local: Config,
        usuario_de_prueba: Any,
        admin: AdministracionSupabase,
    ) -> None:
        """Un usuario desactivado no puede volver a activarse.

        `activo` decide si el usuario existe para `security.es_usuario_activo()`:
        ponerlo en `true` es volver a entrar sin permiso de nadie.

        La respuesta **no** es 403, y no es un defecto del trigger: un usuario
        desactivado tampoco puede leer su propia fila. La politica
        `perfiles_lectura` exige `es_usuario_activo()` en las dos ramas, asi que
        el `PATCH` no alcanza ninguna fila y PostgREST responde 204 con cero
        filas afectadas. Lo que importa es que la fila no cambie, y eso se
        comprueba en `test_su_estado_no_cambio`.
        """
        desactivado = usuario_de_prueba(activo=False)
        respuesta = _cambiar(
            config_local,
            desactivado.token,
            desactivado.id,
            {"activo": True},
        )
        assert respuesta.status_code in (204, 403)
        filas = admin.filas("perfiles", {"id": f"eq.{desactivado.id}"})
        assert filas[0]["activo"] is False

    def test_no_puede_cambiarse_la_organizacion(
        self,
        config_local: Config,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        respuesta = _cambiar(
            config_local,
            usuario_normal.token,
            usuario_normal.id,
            {"organizacion_id": "00000000-0000-4000-8000-000000000000"},
        )
        assert respuesta.status_code == 403

    def test_el_rol_no_cambio(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        """La fila quedo como estaba: el rechazo fue de verdad."""
        _cambiar(
            config_local,
            usuario_normal.token,
            usuario_normal.id,
            {"rol": "admin"},
        )
        filas = admin.filas("perfiles", {"id": f"eq.{usuario_normal.id}"})
        assert filas[0]["rol"] == "analista"

    def test_su_organizacion_no_cambio(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        _cambiar(
            config_local,
            usuario_normal.token,
            usuario_normal.id,
            {"organizacion_id": "00000000-0000-4000-8000-000000000000"},
        )
        filas = admin.filas("perfiles", {"id": f"eq.{usuario_normal.id}"})
        assert str(filas[0]["organizacion_id"]) == usuario_normal.organizacion_id

    def test_su_estado_no_cambio(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        usuario_de_prueba: Any,
    ) -> None:
        desactivado = usuario_de_prueba(activo=False)
        _cambiar(config_local, desactivado.token, desactivado.id, {"activo": True})
        filas = admin.filas("perfiles", {"id": f"eq.{desactivado.id}"})
        assert filas[0]["activo"] is False


class TestAdministracionDeUsuarios:
    """Quien tiene `usuarios.gestionar` si puede: es lo que necesita HU-03."""

    def test_el_administrador_si_puede_cambiar_el_rol(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        administrador: UsuarioDePrueba,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        respuesta = _cambiar(
            config_local,
            administrador.token,
            usuario_normal.id,
            {"rol": "auditor"},
        )
        assert respuesta.status_code in (200, 204)
        filas = admin.filas("perfiles", {"id": f"eq.{usuario_normal.id}"})
        assert filas[0]["rol"] == "auditor"

    def test_el_administrador_si_puede_desactivar(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        administrador: UsuarioDePrueba,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        respuesta = _cambiar(
            config_local,
            administrador.token,
            usuario_normal.id,
            {"activo": False},
        )
        assert respuesta.status_code in (200, 204)
        filas = admin.filas("perfiles", {"id": f"eq.{usuario_normal.id}"})
        assert filas[0]["activo"] is False


class TestLoQueSiPuedeElUsuario:
    """La guarda protege los datos que dan poder, no los datos de la persona."""

    def test_su_propio_nombre_si_lo_puede_cambiar(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
        usuario_normal: UsuarioDePrueba,
    ) -> None:
        """Editar el nombre propio es lo que la politica siempre permitio."""
        respuesta = _cambiar(
            config_local,
            usuario_normal.token,
            usuario_normal.id,
            {"nombres": "Ana Maria"},
        )
        assert respuesta.status_code in (200, 204)
        filas = admin.filas("perfiles", {"id": f"eq.{usuario_normal.id}"})
        assert filas[0]["nombres"] == "Ana Maria"
