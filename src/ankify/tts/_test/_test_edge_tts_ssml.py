import asyncio
from pathlib import Path
import shutil
from typing import Iterable

import edge_tts

from ...logging import get_logger, setup_logging
from ...settings import Settings


logger = get_logger("ankify.tts.edge.test")
setup_logging("DEBUG")


def _english_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "one, two, three"),
        ("dash", "one - two - three"),
        ("semicolon", "bandage (medical); association (organization)"),
        ("brackets", "bandage (medical)"),
        ("slash", "bandage/medical"),
        ("double_dots", "not only .. but also"),
        ("triple_dots", "not only ... but also"),
        ("ellipsis", "not only … but also"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _german_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "eins, zwei, drei"),
        ("dash", "eins - zwei - drei"),
        ("semicolon", "Verband (medizinisch); Verband (Organisation)"),
        ("brackets", "Verband (medizinisch)"),
        ("slash", "Verband/medizinisch"),
        ("double_dots", "nicht nur .. sondern auch"),
        ("triple_dots", "nicht nur ... sondern auch"),
        ("ellipsis", "nicht nur … sondern auch"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _russian_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "один, два, три"),
        ("dash", "один - два - три"),
        ("semicolon", "бинт (медицинский); ассоциация (организация)"),
        ("brackets", "бинт (медицинский)"),
        ("slash", "бинт/медицинский"),
        ("double_dots", "не только .. но и"),
        ("triple_dots", "не только ... но и"),
        ("ellipsis", "не только … но и"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _iter_languages(settings: Settings) -> Iterable[tuple[str, list[tuple[str, str]]]]:
    # Keep the same language set as the AWS test to compare outputs.
    mapping = {
        "english": _english_samples,
        "german": _german_samples,
        "russian": _russian_samples,
    }
    for lang_key, samples_fn in mapping.items():
        if settings.tts.languages and lang_key in settings.tts.languages:
            # Only run languages that exist in the dev settings, mirroring the AWS test behavior
            yield lang_key, samples_fn()


async def _synthesize_to_file(
    text: str,
    voice: str,
    out_path: Path,
) -> None:
    logger.debug("Calling Edge TTS: voice=%s text=%s", voice, text)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


async def main() -> None:
    # Load settings from YAML config used for dev testing
    settings = Settings(config=Path("./settings/dev_test.yaml").resolve())

    # Where to save results
    out_dir = Path("./tmp/edge_tts_ssml").resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir()

    # Voices to test
    voices = {
        "english": "en-US-AndrewNeural",
        "german": "de-DE-ConradNeural",
        "russian": "ru-RU-DmitryNeural",
    }

    for lang_key, samples in _iter_languages(settings):
        voice_name = voices.get(lang_key)
        if not voice_name:
            continue

        logger.info("Testing language=%s voice=%s", lang_key, voice_name)
        suffix = {"english": "en", "german": "de", "russian": "ru"}[lang_key]

        for name, text in samples:
            # try:
            out_path = out_dir / f"{name}_{suffix}.mp3"
            await _synthesize_to_file(
                text=text,
                voice=voice_name,
                out_path=out_path,
            )
            logger.info("Saved %s", out_path)
            # except Exception:
            #     logger.exception("Edge TTS synthesis failed: lang=%s case=%s", lang_key, name)
            #     continue


if __name__ == "__main__":
    asyncio.run(main())
