"""Marca cada prueba segun la carpeta donde vive.

`pytest -m unit` tiene que correr **solo** las pruebas que no tocan la base de
datos ni la red. Marcar cada test a mano se olvida: el marcador se pone por
convencion de carpeta, que es la unica forma que no depende de que alguien se
acuerde.

    tests/unit/         -> unit
    tests/integration/  -> integration
    tests/contract/     -> contract
"""

from __future__ import annotations

from pathlib import Path

import pytest

MARCADOR_POR_CARPETA = {
    "unit": "unit",
    "integration": "integration",
    "contract": "contract",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Aplica el marcador de la carpeta a cada prueba recolectada."""
    for item in items:
        partes = Path(str(item.fspath)).parts
        carpeta = next((parte for parte in partes if parte in MARCADOR_POR_CARPETA), None)
        if carpeta is not None:
            item.add_marker(getattr(pytest.mark, MARCADOR_POR_CARPETA[carpeta]))
