"""E2E tests for  Edge TTS synthesis.

These tests use the Edge TTS service (free, no credentials needed).
"""

import pytest

from ankify.tts.edge_tts import EdgeTTSSingleLanguageClient
from ankify.settings import TTSVoiceOptions


class TestEdgeTTS:
    """E2E tests for  Edge TTS synthesis."""

    @pytest.fixture
    def english_voice(self):
        """English voice options."""
        return TTSVoiceOptions(voice_id="en-US-AriaNeural")

    @pytest.fixture
    def german_voice(self):
        """German voice options."""
        return TTSVoiceOptions(voice_id="de-DE-KatjaNeural")

    def test_synthesize_english_text(self, english_voice):
        """Synthesize English text with  Edge TTS."""
        client = EdgeTTSSingleLanguageClient(english_voice)
        entities = {"Hello world": None}

        client.synthesize(entities, "english", None)

        # Should return audio bytes
        audio = entities["Hello world"]
        assert audio is not None
        assert isinstance(audio, bytes)
        assert len(audio) > 1000  # Audio should have substantial size

    def test_synthesize_german_text(self, german_voice):
        """Synthesize German text with  Edge TTS."""
        client = EdgeTTSSingleLanguageClient(german_voice)
        entities = {"Guten Tag": None}

        client.synthesize(entities, "german", None)

        audio = entities["Guten Tag"]
        assert audio is not None
        assert len(audio) > 1000

    def test_synthesize_multiple_texts(self, english_voice):
        """Synthesize multiple texts with  Edge TTS."""
        client = EdgeTTSSingleLanguageClient(english_voice)
        entities = {
            "Hello": None,
            "Goodbye": None,
            "Thank you": None,
        }

        client.synthesize(entities, "english", None)

        for text, audio in entities.items():
            assert audio is not None
            assert isinstance(audio, bytes)
            assert len(audio) > 500, f"Audio for '{text}' too short"

    def test_audio_is_valid_mp3(self, english_voice, tmp_path):
        """Synthesized audio is valid MP3 format."""
        client = EdgeTTSSingleLanguageClient(english_voice)
        entities = {"Test audio format": None}

        client.synthesize(entities, "english", None)

        audio = entities["Test audio format"]

        # Write to file and check
        output_file = tmp_path / "test.mp3"
        output_file.write_bytes(audio)

        # MP3 files typically start with ID3 tag or frame sync bytes
        # ID3v2 starts with "ID3", MP3 frames start with 0xFF 0xFB/FA/FB
        assert audio[:3] == b"ID3" or (audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0)

    def test_synthesize_special_characters(self, english_voice):
        """Synthesize text with special characters."""
        client = EdgeTTSSingleLanguageClient(english_voice)
        # Text with slash and semicolon that gets converted to SSML
        entities = {"yes/no; maybe": None}

        client.synthesize(entities, "english", None)

        audio = entities["yes/no; maybe"]
        assert audio is not None
        assert len(audio) > 500

    def test_synthesize_unicode_text(self):
        """Synthesize text with Unicode characters."""
        voice = TTSVoiceOptions(voice_id="ru-RU-SvetlanaNeural")
        client = EdgeTTSSingleLanguageClient(voice)
        entities = {"Привет мир": None}

        client.synthesize(entities, "russian", None)

        audio = entities["Привет мир"]
        assert audio is not None
        assert len(audio) > 500

    def test_synthesize_chinese_text(self):
        """Synthesize Chinese text."""
        voice = TTSVoiceOptions(voice_id="zh-CN-XiaoxiaoNeural")
        client = EdgeTTSSingleLanguageClient(voice)
        entities = {"你好世界": None}

        client.synthesize(entities, "chinese", None)

        audio = entities["你好世界"]
        assert audio is not None
        assert len(audio) > 500


class TestEdgeTTSWithCostTracking:
    """E2E tests for Edge TTS with cost tracking."""

    def test_cost_tracker_records_usage(self):
        """Cost tracker records character usage."""
        from ankify.tts.tts_cost_tracker import EdgeTTSCostTracker
        from decimal import Decimal

        voice = TTSVoiceOptions(voice_id="en-US-AriaNeural")
        client = EdgeTTSSingleLanguageClient(voice)
        tracker = EdgeTTSCostTracker()

        entities = {"Hello world": None}
        client.synthesize(entities, "english", tracker)

        # Calculate totals from internal usage dict
        total_chars = sum(u.chars for u in tracker._usage.values())
        total_cost = sum(u.cost for u in tracker._usage.values())

        # Should have tracked the usage
        assert total_chars > 0
        assert total_cost == Decimal("0.00")  # Edge TTS is free
