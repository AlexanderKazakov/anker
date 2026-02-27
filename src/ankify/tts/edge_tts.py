import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, TYPE_CHECKING

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..logging import get_logger
from ..settings import TTSVoiceOptions
from .tts_base import TTSSingleLanguageClient
from .tts_text_preprocessor import replace_separators_with_plain_text

if TYPE_CHECKING:
    from .tts_cost_tracker import TTSCostTracker


class EdgeTTSSingleLanguageClient(TTSSingleLanguageClient):
    @staticmethod
    def possibly_preprocess_text(text: str) -> str:
        """
        Edge TTS does not support SSML, so we replace slashes with punctuation.
        """
        return replace_separators_with_plain_text(text)

    def __init__(self, language_settings: TTSVoiceOptions) -> None:
        self.logger = get_logger("ankify.tts.edge")
        self.logger.debug(
            "Initializing Edge TTS client for voice id '%s'", language_settings.voice_id
        )
        self._language_settings = language_settings

    def synthesize(
        self,
        entities: dict[str, bytes | None],
        language: str,
        cost_tracker: "TTSCostTracker | None" = None,
    ) -> None:
        self.logger.info(
            "Synthesizing speech for %d entities, voice id '%s'",
            len(entities),
            self._language_settings.voice_id,
        )

        for text in entities:
            entities[text] = self._synthesize_single(text)
            if cost_tracker:
                cost_tracker.track_usage(text, "free", language)

    def _run_coroutine(self, coro_factory: Callable[[], Awaitable[bytes]]) -> bytes:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_factory())

        self.logger.debug("Running Edge TTS coroutine in a dedicated event loop thread")

        def runner() -> bytes:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro_factory())
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(runner).result()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    def _synthesize_single(self, text: str) -> bytes:
        prepared_text = self.possibly_preprocess_text(text)
        return self._run_coroutine(lambda: self._synthesize_single_async(prepared_text))

    async def _synthesize_single_async(self, text: str) -> bytes:
        import edge_tts

        self.logger.debug(
            "Calling Edge TTS: voice=%s text=%s", self._language_settings.voice_id, text
        )
        communicate = edge_tts.Communicate(text, self._language_settings.voice_id)
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            self.logger.error(
                "Edge TTS returned no audio. voice_id='%s' text='%s'",
                self._language_settings.voice_id,
                text,
            )
            raise RuntimeError("Edge TTS response did not contain audio data")

        return b"".join(audio_chunks)
