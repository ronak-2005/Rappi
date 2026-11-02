"""Structured JSON logs. Every line carries service, component (folder) and run_id, so a log line
points straight at the code that wrote it."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

run_id_var: ContextVar[str] = ContextVar("run_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        parts = record.name.split(".")
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.service,
            "component": ".".join(parts[:3]),
            "run_id": run_id_var.get(),
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "data", None)
        if extra:
            entry["data"] = extra
        return json.dumps(entry, default=str)


def setup_logging(service: str, level: str = "INFO", log_dir=None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / f"{service}.log"))
    for h in handlers:
        h.setFormatter(JsonFormatter(service))
        root.addHandler(h)
