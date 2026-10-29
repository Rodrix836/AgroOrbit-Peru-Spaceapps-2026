"""Configuración sencilla de logs para los módulos de la aplicación."""

import logging


def configure_logging(debug: bool = False) -> None:
    """Configura una sola vez el logger de la aplicación."""

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
