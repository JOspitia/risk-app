"""Aislamiento de las pruebas unitarias del entorno.

Las pruebas unitarias prueban **la logica**, no la maquina del desarrollador. Si
leen el `.env` local o las variables de entorno de la shell, el resultado depende de
la maquina: las pruebas pasan en un equipo y fallan en otro, sin que haya cambiado
ni una linea del codigo.

Eso ya paso. Con un `.env` presente, `Config(**datos)` no fallaba cuando faltaba una
variable obligatoria: pydantic-settings lee el archivo con prioridad sobre los
argumentos, y la variable se completaba desde el entorno. El test "no hay valor por
defecto utilizable" dejo de comprobar lo que dice comprobar.

Este archivo deja el entorno limpio para toda la sesion de pruebas.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.config import Config

# Variables que la aplicacion lee del entorno. Se borran antes de cada prueba para
# que ningun valor local se cuele en el resultado.
VARIABLES_DEL_ENTORNO = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "SUPABASE_JWKS_URL",
    "DATABASE_URL",
    "MAX_UPLOAD_MB",
    "CORS_ORIGINS",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Borra las variables del entorno antes de cada prueba.

    Autouse: aplica a todas las pruebas de la suite, sin que cada una tenga que
    acordarse. Un `.env` en el directorio de trabajo tambien se neutraliza, porque
    `Config` lo lee en tiempo de construccion.
    """
    for variable in VARIABLES_DEL_ENTORNO:
        monkeypatch.delenv(variable, raising=False)

    # `Config` busca el `.env` en el directorio de trabajo. Se le dice que no lo lea:
    # en una prueba, el `.env` del desarrollador no es la fuente de la configuracion.
    monkeypatch.setattr(
        Config,
        "model_config",
        {**Config.model_config, "env_file": None},
    )

    yield
