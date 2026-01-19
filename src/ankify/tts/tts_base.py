from abc import ABC, abstractmethod


class TTSSingleLanguageClient(ABC):
    @abstractmethod
    def synthesize(self, entities: dict[str, bytes | None]) -> None:
        """
        Text-to-Speech synthesis for a single fixed language and settings.
        For each item, the audio (binary) is synthesized and stored in the dictionary.
        """
        raise NotImplementedError


