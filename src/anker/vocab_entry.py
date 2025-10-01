from dataclasses import dataclass
from pathlib import Path


@dataclass
class VocabEntry:
    front: str
    back: str
    front_language: str
    back_language: str
    front_audio: Path | None = None
    back_audio: Path | None = None





