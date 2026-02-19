import yaml

from pydantic_settings import CliApp

from .logging import get_logger, setup_logging
from .settings import Settings
from .pipeline import Pipeline


def app() -> None:
    """CLI entrypoint.
    Uses pydantic-settings CLI source
    to parse and merge arguments from CLI, env, dotenv, and YAML config.
    """
    settings = CliApp.run(Settings)

    setup_logging(settings.log_level)
    logger = get_logger("ankify.cli")

    logger.info(
        "Settings loaded:\n%s",
        yaml.safe_dump(
            settings.model_dump(mode="json"),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ),
    )

    pipeline = Pipeline(settings)
    pipeline.run()


if __name__ == "__main__":
    app()
