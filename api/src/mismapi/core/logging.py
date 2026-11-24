import logging
import logging.config
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_root_logger(log_level: str) -> None:
    normalized_level = log_level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id_filter": {
                    "()": RequestIDFilter,
                },
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id_filter"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": normalized_level,
            },
        }
    )
