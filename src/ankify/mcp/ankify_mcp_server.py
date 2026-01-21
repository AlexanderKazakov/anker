import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from ..anki.anki_deck_creator import AnkiDeckCreator
from ..settings import AWSProviderAccess, NoteType, ProviderAccessSettings, Text2SpeechSettings
from ..tsv import read_from_string
from ..tts.tts_manager import TTSManager
from ..vocab_entry import VocabEntry
from ..logging import get_logger


logger = get_logger(__name__)

ankify_mcp = FastMCP("Ankify")

load_dotenv()

decks_directory = Path("~/ankify").expanduser().resolve()
decks_directory.mkdir(parents=True, exist_ok=True)

if os.getenv("ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID"):
    tts_settings = Text2SpeechSettings(
        default_provider="aws",
    )
    provider_settings = ProviderAccessSettings(
        aws=AWSProviderAccess(
            access_key_id=os.getenv("ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID"),
            secret_access_key=os.getenv("ANKIFY__PROVIDERS__AWS__SECRET_ACCESS_KEY"),
            region=os.getenv("ANKIFY__PROVIDERS__AWS__REGION"),
        ),
    )
    logger.info("Using AWS TTS provider: %s", provider_settings.aws)
else:
    tts_settings = Text2SpeechSettings(
        default_provider="edge",
    )
    provider_settings = ProviderAccessSettings()
    logger.info("Using Edge TTS provider (as no AWS credentials found in env)")


@ankify_mcp.tool()
def convert_TSV_to_Anki_deck(
    tsv_vocabulary: str,
    note_type: NoteType,
    deck_name: str = "Ankify",
) -> str:
    """
    Creates Anki deck (.apkg) from TSV vocabulary (string).
    
    Args:
        tsv_vocabulary: string with vocabulary in TSV format: 
            `front_text<tab>back_text<tab>front_language<tab>back_language<newline>...`
        
        note_type: type of Anki notes to create: 
            - `forward_and_backward` - two cards per note: forward and backward
            - `forward_only` - one card per note: forward only
        
        deck_name: name of the Anki deck (it's not the file name, it's the deck name within Anki)
    
    Returns:
        URI of the generated .apkg file
    """
    logger.info("Received request to create deck '%s' with note_type '%s'", deck_name, note_type)
    
    try:
        vocab_entries: list[VocabEntry] = read_from_string(tsv_vocabulary)
    except Exception as e:
        msg = f"Failed to parse vocabulary TSV: {e}"
        logger.error(msg)
        raise ValueError(msg)

    with TemporaryDirectory(dir=decks_directory, prefix="media_") as audio_dir:
        synthesize_audio(vocab_entries, Path(audio_dir))
        output_file = package_anki_deck(vocab_entries, decks_directory, deck_name, note_type)
        
    return output_file.resolve().as_uri()


def synthesize_audio(vocab_entries: list[VocabEntry], audio_dir: Path) -> None:
    logger.info("Synthesizing audio to %s", audio_dir)
    try:
        tts_manager = TTSManager(
            tts_settings=tts_settings,
            provider_settings=provider_settings,
        )
        tts_manager.synthesize(vocab_entries, audio_dir)
    except Exception as e:
        msg = f"TTS synthesis failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg)


def package_anki_deck(
    vocab_entries: list[VocabEntry], 
    decks_directory: Path, 
    deck_name: str, 
    note_type: NoteType,
) -> Path:
    safe_deck_name = re.sub(r"\s+", "_", deck_name)
    safe_deck_name = re.sub(r"[^a-zA-Z0-9_-]", "", safe_deck_name)
    if not safe_deck_name:
        safe_deck_name = "Ankify"
    output_file = decks_directory / f"{safe_deck_name}-{uuid4()}.apkg"
    logger.info("Packaging Anki deck to %s", output_file)
    try:
        creator = AnkiDeckCreator(output_file=output_file, deck_name=deck_name, note_type=note_type)
        creator.write_anki_deck(vocab_entries)
    except Exception as e:
        msg = f"Anki deck packaging failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg)
    return output_file


def _test() -> None:
    uri = convert_TSV_to_Anki_deck(
        tsv_vocabulary="""
Hello World!\tHallo Welt!\tEnglish\tGerman
Как дела?\t¿Cómo estás?\tRussian\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese
""",
        note_type="forward_and_backward",
        deck_name="Ankify Test Deck",
    )
    logger.info("Ankify Test Deck: %s", uri)


if __name__ == "__main__":
    # _test()
    ankify_mcp.run(transport="stdio")

