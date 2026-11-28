"""Risk-app: API de analisis privado de documentos.

Estructura hexagonal (ADR-04):

- `domain/`: entidades, value objects, puertos y reglas puras. Sin frameworks.
- `application/`: casos de uso, DTO y auditoria. No conoce HTTP.
- `adapters/`: entrada (HTTP) y salida (Supabase, almacenamiento, LLM, ETL).
- `worker/`: consumidor de la cola. Llega en la v2.

La frontera se verifica sola con `import-linter`.
"""
