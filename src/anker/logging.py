import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name."""
    return logging.getLogger(name)


def setup_logging(
    level: int | str = "INFO",
    *,
    include_time: bool = True,
    quiet_third_party: bool = True,
) -> None:
    """Configure root logging to emit to stdout.

    Parameters
    ----------
    level:
        Log level as int or name (e.g., "DEBUG"). Defaults to "INFO".
    include_time:
        Whether to include timestamps in log records.
    quiet_third_party:
        If true, reduces verbosity of common third-party libraries.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers to avoid duplicate logs when re-configuring
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)

    base_parts = []
    if include_time:
        base_parts.append("%(asctime)s")
    base_parts.extend(["%(levelname)s", "%(name)s", "-", "%(message)s"])
    fmt = " ".join(base_parts)

    formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    root.addHandler(handler)

    if quiet_third_party:
        # Allow all logs from our application namespace, but only WARNING+
        # from any other (third-party) loggers without having to list them.
        app_prefix = __name__.split(".")[0]  # "anker"

        class _OnlyAppOrThirdPartyWarnings(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                name = getattr(record, "name", "") or ""
                if name.startswith(app_prefix):
                    return True
                return record.levelno >= logging.WARNING

        handler.addFilter(_OnlyAppOrThirdPartyWarnings())



