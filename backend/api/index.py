"""Punto de entrada en Vercel.

Vercel no busca `main.py`: busca un modulo que exponga `app`. Este archivo es ese
modulo, y su unico trabajo es reexportar la aplicacion.

Se mantiene separado de `app/main.py` a proposito: si Vercel tuviera que importar
`app.main`, cada cambio en la composicion seria un cambio en el punto de entrada
del despliegue.
"""

from app.main import app

__all__ = ["app"]
