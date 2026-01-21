import json
from importlib import resources

from ..settings import LanguageTTSConfig, TTSVoiceOptions, TTSProvider
from ..logging import get_logger

logger = get_logger(__name__)


class DefaultTTSConfigurator:
    def __init__(self, default_provider: TTSProvider) -> None:
        self.default_provider = default_provider
        self.defaults = None

    def _load_defaults(self, provider: str) -> dict[str, str | dict[str, str]]:
        filename = f"tts_defaults_{provider}.json"
        content = resources.files("ankify.resources").joinpath(filename).read_text(encoding="utf-8")
        return json.loads(content)

    def get_config(self, language: str) -> LanguageTTSConfig:
        if self.defaults is None:
            self.defaults = self._load_defaults(self.default_provider)

        language = language.lower()
        if language not in self.defaults:
            raise ValueError(
                f"No default voice exists for language '{language}' (provider: {self.default_provider}). "
                f"Make sure you are using a valid language code. "
                f"Available language codes: {list(self.defaults.keys())}"
            )
        
        value = self.defaults[language]
        options = TTSVoiceOptions(**value)
        return LanguageTTSConfig(
            provider=self.default_provider,
            options=options
        )
