from abc import ABC, abstractmethod
from pathlib import Path

from ..vocab_entry import VocabEntry
from ..tsv import read_from_string
from ..logging import get_logger


class LLMClient(ABC):
    def __init__(self) -> None:
        self._logger = get_logger("anker.llm.base")

    def generate_vocabulary(self, input_text: str) -> list[VocabEntry]:
        self._logger.info("Generating vocabulary entries with LLM")
        llm_answer = self._call_llm(input_text)
        vocab = self._parse_llm_answer(llm_answer)
        self._logger.info("Generated %d vocabulary entries", len(vocab))
        return vocab

    @abstractmethod
    def _call_llm(self, input_text: str) -> str:
        raise NotImplementedError

    def _parse_llm_answer(self, llm_answer: str) -> list[VocabEntry]:
        self._logger.info("Parsing LLM answer into vocabulary entries")
        return read_from_string(llm_answer)
    
    def _load_prompt(self, prompt_path: str) -> str:
        with Path(prompt_path).open("r", encoding="utf-8") as f:
            return f.read()

