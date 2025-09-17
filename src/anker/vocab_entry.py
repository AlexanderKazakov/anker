from dataclasses import dataclass


@dataclass
class VocabEntry:
    front: str
    back: str
    front_language: str
    back_language: str
    front_audio: bytes | None = None
    back_audio: bytes | None = None





