import contextlib
from typing import Iterator, Any

from .logging import get_logger
from .settings import MLflowConfig

logger = get_logger("anker.observability")

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    logger.debug("MLflow not available, tracking disabled")
    MLFLOW_AVAILABLE = False


class MLflowTracker:
    def __init__(self, config: MLflowConfig) -> None:
        self.config = config
        self.enabled = False

        if not config.tracking_uri:
            return

        if not MLFLOW_AVAILABLE:
            logger.warning(
                "MLflow tracking URI provided (%s), but 'mlflow' package is not installed. "
                "Tracking will be disabled.",
                config.tracking_uri
            )
            return

        try:
            mlflow.set_tracking_uri(config.tracking_uri)
            mlflow.set_experiment(config.experiment_name)
            mlflow.openai.autolog()
            self.enabled = True
            logger.info(
                "Initialized MLflow tracking at %s (experiment: %s)",
                config.tracking_uri,
                config.experiment_name
            )
        
        except Exception as e:
            logger.warning("Failed to initialize MLflow: %s", e)
            self.enabled = False

    @contextlib.contextmanager
    def run_context(self) -> Iterator[None]:
        """Context manager for an MLflow run. No-op if disabled."""
        if not self.enabled:
            yield
            return

        # Check if a run is already active (e.g. from CLI or nested calls)
        if mlflow.active_run():
            yield
            return

        with mlflow.start_run():
            yield

    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters to the current run. No-op if disabled."""
        if not self.enabled:
            return
        
        # Only log if there is an active run
        if mlflow.active_run():
            try:
                mlflow.log_params(params)
            except Exception as e:
                logger.warning("Failed to log params to MLflow: %s", e)

