"""Excepciones compartidas por los servicios del backend."""


class AgroOrbitError(Exception):
    """Error controlado de la aplicación."""


class ExternalServiceError(AgroOrbitError):
    """Falla de un servicio externo."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExternalServiceTimeoutError(ExternalServiceError):
    """Tiempo de espera agotado al consultar un servicio externo."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=504)


class ConfigurationError(AgroOrbitError):
    """Configuración ausente o inválida de la aplicación."""
