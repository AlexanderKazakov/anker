from pathlib import Path
import uuid

from .default_tts_configuration import DefaultTTSConfigurator
from ..vocab_entry import VocabEntry
from ..settings import (
    Text2SpeechSettings,
    LanguageTTSConfig,
    ProviderAccessSettings,
)
from ..logging import get_logger
from .tts_base import TTSSingleLanguageClient
from .aws_tts import AWSPollySingleLanguageClient
from .edge_tts import EdgeTTSSingleLanguageClient


def create_tts_single_language_client(
    config: LanguageTTSConfig,
    providers: ProviderAccessSettings,
) -> TTSSingleLanguageClient:
    if config.provider == "aws":
        return AWSPollySingleLanguageClient(
            access_settings=providers.aws,
            language_settings=config.options,
        )
    if config.provider == "edge":
        return EdgeTTSSingleLanguageClient(
            language_settings=config.options,
        )
    else:
        raise ValueError(f"Unsupported TTS provider: {config.provider}")


class TTSManager:
    def __init__(
        self,
        tts_settings: Text2SpeechSettings,
        provider_settings: ProviderAccessSettings,
    ) -> None:

        self.logger = get_logger("ankify.tts.manager")
        self.logger.debug("Initializing TTSManager...")
        self.provider_settings = provider_settings

        # to instantiate a default language client if a language is not explicitly configured in settings
        self.defaults_configurator = DefaultTTSConfigurator(default_provider=tts_settings.default_provider)

        self.tts_clients: dict[str, TTSSingleLanguageClient] = {}
        if tts_settings.languages is not None:
            for language, lang_cfg in tts_settings.languages.items():
                self.tts_clients[language] = create_tts_single_language_client(lang_cfg, provider_settings)
        
        self.logger.debug("Initialized TTSManager")

    def synthesize(self, entries: list[VocabEntry], audio_dir: Path) -> None:
        self.logger.info("Starting TTS synthesis for %d vocabulary entries", len(entries))
        # within each language, de-duplicate by text
        by_language = {}
        for entry in entries:
            front_lang = self._ensure_client_for_language(entry.front_language)
            back_lang = self._ensure_client_for_language(entry.back_language)

            if front_lang not in by_language:
                by_language[front_lang] = {}
            if back_lang not in by_language:
                by_language[back_lang] = {}

            by_language[front_lang][entry.front] = None
            by_language[back_lang][entry.back] = None
        
        for lang, lang_entries in by_language.items():
            self.logger.debug("Language '%s' has %d unique texts to synthesize", lang, len(lang_entries))
            if len(lang_entries) != 0:
                self.tts_clients[lang].synthesize(lang_entries)
                # write audio to disk, keep paths instead of bytes
                for text in lang_entries.keys():
                    audio_file_path = audio_dir / f"ankify-{uuid.uuid4()}.mp3"
                    audio_file_path.write_bytes(lang_entries[text])
                    lang_entries[text] = audio_file_path
        
        for entry in entries:
            # We use _ensure_client_for_language again just to get the normalized key,
            # but we know it's there.
            front_lang = self._ensure_client_for_language(entry.front_language)
            back_lang = self._ensure_client_for_language(entry.back_language)
            entry.front_audio = by_language[front_lang][entry.front]
            entry.back_audio = by_language[back_lang][entry.back]
        
        self.logger.info("Completed TTS synthesis")

    def _ensure_client_for_language(self, language: str) -> str:
        language = language.lower()
        if language in self.tts_clients:
            return language
        
        self.logger.info("Language '%s' not configured; loading defaults", language)
        config = self.defaults_configurator.get_config(language)
        
        # Update the clients map
        self.tts_clients[language] = create_tts_single_language_client(config, self.provider_settings)
        return language
