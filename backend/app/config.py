"""Configuracion de la aplicacion.

Las variables de entorno son el unico contrato entre la maquina y el proyecto.
El arranque **falla** si falta una obligatoria: una configuracion incompleta que
arranca es peor que una que se niega a arrancar, porque el fallo aparece en
produccion y no en el desarrollo.

Ver seccion 8 de docs/ARQUITECTURA.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Variables de entorno del backend.

    Ningun valor por defecto es utilizable: lo que se puede adivinar, se adivina
    mal. Las unicas excepciones son las que no son secretas y no importan para la
    seguridad.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # `list[str` no tiene representacion JSON: sin esto, pydantic-settings
        # rechaza el valor del entorno antes de que llegue al validador.
        enable_decoding=False,
    )

    # --- Supabase -------------------------------------------------------

    supabase_url: str = Field(
        description="URL del proyecto de Supabase. Define tambien el emisor del JWT.",
    )
    supabase_anon_key: str = Field(
        description="Llave publica. La usa el frontend; nunca la llave de servicio.",
    )
    supabase_service_role_key: str = Field(
        description="Llave de servicio. Solo backend. Confineda al adaptador de administracion.",
    )
    supabase_jwt_secret: str | None = Field(
        default=None,
        description="Solo para proyectos con claves simetricas (HS256). Los nuevos usan JWKS.",
    )
    supabase_jwks_url: str | None = Field(
        default=None,
        description="Claves publicas para validar tokens asimetricos (RS256/ES256).",
    )

    # --- Otros ----------------------------------------------------------

    database_url: str | None = Field(
        default=None,
        description="Solo para el script de validacion de migraciones en desarrollo.",
    )
    max_upload_mb: int = Field(default=50, ge=1, le=200)
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Origenes permitidos. Se leen separados por comas.",
    )
    log_level: str = Field(default="INFO")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _partir_origenes(cls, valor: object) -> object:
        """Acepta la lista separada por comas que llega del `.env`.

        Sin este validador, pydantic-settings intenta parsear el texto como JSON
        y falla antes de que el validador vea el valor.
        """
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @field_validator("cors_origins")
    @classmethod
    def _sin_comodines(cls, valor: list[str]) -> list[str]:
        """`*` con credenciales es una combinacion que el navegador rechaza.

        Y aunque la aceptara, abriria la API a cualquier pagina. Se falla al arrancar
        en lugar de aceptarlo en silencio.
        """
        if "*" in valor:
            raise ValueError(
                "CORS_ORIGINS no puede contener '*' con credenciales: lista los origenes.",
            )
        return valor

    @property
    def jwt_issuer(self) -> str:
        """Emisor del JWT. Supabase emite los tokens en `{SUPABASE_URL}/auth/v1`."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        """URL del conjunto de claves publicas del proyecto."""
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache(maxsize=1)
def obtener_config() -> Config:
    """Configuracion del proceso. Se cachea: leer el entorno cuesta y no cambia.

    El cache hace que un fallo de arranque se reporte una vez, no en cada peticion.
    """
    return Config()  # type: ignore[call-arg]
