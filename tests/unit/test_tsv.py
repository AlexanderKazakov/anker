"""Unit tests for TSV parsing and writing."""

import pytest

from ankify.tsv import read_from_string, read_from_file, write_to_file
from ankify.vocab_entry import VocabEntry


@pytest.fixture
def sample_vocab_entries():
    """Returns a list of sample VocabEntry objects."""
    return [
        VocabEntry(front="Hello", back="Hallo", front_language="english", back_language="german"),
        VocabEntry(front="World", back="Welt", front_language="english", back_language="german"),
        VocabEntry(front="Goodbye", back="Auf Wiedersehen", front_language="english", back_language="german"),
    ]


@pytest.fixture
def sample_tsv_string() -> str:
    """Returns a valid TSV string."""
    return "Hello\tHallo\tenglish\tgerman\nWorld\tWelt\tenglish\tgerman"


@pytest.fixture
def sample_tsv_malformed() -> str:
    """Returns TSV with some malformed rows."""
    return "Hello\tHallo\tenglish\tgerman\nMalformed\tOnly\tThree\nWorld\tWelt\tenglish\tgerman"


class TestReadFromString:
    """Tests for read_from_string function."""

    def test_parse_valid_tsv(self, sample_tsv_string):
        """Parse valid TSV string into VocabEntry list."""
        entries = read_from_string(sample_tsv_string)
        assert len(entries) == 2
        assert entries[0].front == "Hello"
        assert entries[0].back == "Hallo"
        assert entries[0].front_language == "english"
        assert entries[0].back_language == "german"

    def test_parse_single_row(self):
        """Parse TSV with single row."""
        tsv = "Word\tWort\ten\tde"
        entries = read_from_string(tsv)
        assert len(entries) == 1
        assert entries[0].front == "Word"

    def test_parse_empty_string(self):
        """Parse empty string returns empty list."""
        entries = read_from_string("")
        assert entries == []

    def test_skip_malformed_rows(self, sample_tsv_malformed):
        """Skip rows with wrong number of columns."""
        entries = read_from_string(sample_tsv_malformed)
        # Only 2 valid rows (first and last), middle row has 3 columns
        assert len(entries) == 2
        assert entries[0].front == "Hello"
        assert entries[1].front == "World"

    def test_skip_row_with_too_few_columns(self):
        """Skip rows with fewer than 4 columns."""
        tsv = "Only\tTwo"
        entries = read_from_string(tsv)
        assert entries == []

    def test_skip_row_with_too_many_columns(self):
        """Skip rows with more than 4 columns."""
        tsv = "One\tTwo\tThree\tFour\tFive"
        entries = read_from_string(tsv)
        assert entries == []

    def test_parse_with_special_characters(self):
        """Parse TSV with special characters."""
        tsv = "Привет\tHello\tRussian\tEnglish"
        entries = read_from_string(tsv)
        assert len(entries) == 1
        assert entries[0].front == "Привет"

    def test_parse_with_empty_fields(self):
        """Parse TSV with empty fields (tabs with no content)."""
        tsv = "\t\t\t"
        entries = read_from_string(tsv)
        assert len(entries) == 1
        assert entries[0].front == ""
        assert entries[0].back == ""

    def test_parse_preserves_whitespace(self):
        """TSV parsing preserves leading/trailing whitespace in fields."""
        tsv = " Hello \t Hallo \ten\tde"
        entries = read_from_string(tsv)
        assert entries[0].front == " Hello "
        assert entries[0].back == " Hallo "


class TestReadFromFile:
    """Tests for read_from_file function."""

    def test_read_from_file(self, tmp_path, sample_tsv_string):
        """Read TSV from file."""
        tsv_path = tmp_path / "vocab.tsv"
        tsv_path.write_text(sample_tsv_string, encoding="utf-8")

        entries = read_from_file(tsv_path)
        assert len(entries) == 2
        assert entries[0].front == "Hello"

    def test_read_from_file_utf8(self, tmp_path):
        """Read TSV file with UTF-8 characters."""
        tsv_content = "Привет\tHello\tRussian\tEnglish\n你好\tHello\tChinese\tEnglish"
        tsv_path = tmp_path / "vocab.tsv"
        tsv_path.write_text(tsv_content, encoding="utf-8")

        entries = read_from_file(tsv_path)
        assert len(entries) == 2
        assert entries[0].front == "Привет"
        assert entries[1].front == "你好"


class TestWriteToFile:
    """Tests for write_to_file function."""

    def test_write_to_file(self, tmp_path, sample_vocab_entries):
        """Write vocabulary entries to TSV file."""
        tsv_path = tmp_path / "output.tsv"
        write_to_file(sample_vocab_entries, tsv_path)

        content = tsv_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 3
        assert "Hello\tHallo\tenglish\tgerman" in lines[0]

    def test_write_creates_parent_directories(self, tmp_path, sample_vocab_entries):
        """write_to_file creates parent directories if they don't exist."""
        tsv_path = tmp_path / "nested" / "dir" / "output.tsv"
        write_to_file(sample_vocab_entries, tsv_path)

        assert tsv_path.exists()
        content = tsv_path.read_text(encoding="utf-8")
        assert "Hello" in content

    def test_write_empty_list(self, tmp_path):
        """Writing empty list creates empty file."""
        tsv_path = tmp_path / "empty.tsv"
        write_to_file([], tsv_path)

        assert tsv_path.exists()
        content = tsv_path.read_text(encoding="utf-8")
        assert content == ""

    def test_roundtrip(self, tmp_path, sample_vocab_entries):
        """Write and read back produces same entries."""
        tsv_path = tmp_path / "roundtrip.tsv"
        write_to_file(sample_vocab_entries, tsv_path)

        read_entries = read_from_file(tsv_path)

        assert len(read_entries) == len(sample_vocab_entries)
        for orig, read in zip(sample_vocab_entries, read_entries):
            assert orig.front == read.front
            assert orig.back == read.back
            assert orig.front_language == read.front_language
            assert orig.back_language == read.back_language

    def test_write_with_special_characters(self, tmp_path):
        """Write and read UTF-8 characters correctly."""
        entries = [
            VocabEntry(front="Привет", back="Hello", front_language="Russian", back_language="English"),
            VocabEntry(front="你好", back="Hello", front_language="Chinese", back_language="English"),
        ]
        tsv_path = tmp_path / "utf8.tsv"
        write_to_file(entries, tsv_path)

        read_entries = read_from_file(tsv_path)
        assert read_entries[0].front == "Привет"
        assert read_entries[1].front == "你好"
