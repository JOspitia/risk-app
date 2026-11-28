"""Adaptadores.

- `http/`: adaptador de **entrada** (FastAPI): routers, esquemas, envelope.
- `supabase/`: adaptador de **salida** (PostgREST por HTTP).
- `storage/`, `llm/`, `etl/`, `queue/`: adaptadores de salida intercambiables.

Un adaptador implementa un puerto del dominio. No decide nada: mapea datos.
"""
