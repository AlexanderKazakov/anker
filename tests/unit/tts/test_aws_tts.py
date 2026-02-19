"""E2E tests for MCP with  AWS Polly.

These tests require AWS credentials:
- ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID
- ANKIFY__PROVIDERS__AWS__SECRET_ACCESS_KEY
"""

from ankify.tts.aws_tts import AWSPollySingleLanguageClient
from ankify.settings import TTSVoiceOptions


class TestAWSPolly:
    """E2E tests for  AWS Polly synthesis."""

    def test_synthesize_english_text(self, aws_access):
        """Synthesize English text with  AWS Polly."""
        voice = TTSVoiceOptions(voice_id="Joanna", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {"Hello world from AWS Polly": None}
        client.synthesize(entities, "english", None)

        audio = entities["Hello world from AWS Polly"]
        assert audio is not None
        assert isinstance(audio, bytes)
        assert len(audio) > 1000

    def test_synthesize_german_text(self, aws_access):
        """Synthesize German text with  AWS Polly."""
        voice = TTSVoiceOptions(voice_id="Vicki", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {"Guten Tag": None}
        client.synthesize(entities, "german", None)

        audio = entities["Guten Tag"]
        assert audio is not None
        assert len(audio) > 1000

    def test_synthesize_with_standard_engine(self, aws_access):
        """Synthesize with standard engine (cheaper)."""
        voice = TTSVoiceOptions(voice_id="Joanna", engine="standard")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {"Standard engine test": None}
        client.synthesize(entities, "english", None)

        audio = entities["Standard engine test"]
        assert audio is not None
        assert len(audio) > 500

    def test_synthesize_multiple_texts(self, aws_access):
        """Synthesize multiple texts with  AWS Polly."""
        voice = TTSVoiceOptions(voice_id="Matthew", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {
            "First": None,
            "Second": None,
            "Third": None,
        }
        client.synthesize(entities, "english", None)

        for text, audio in entities.items():
            assert audio is not None, f"No audio for '{text}'"
            assert len(audio) > 100

    def test_audio_is_valid_mp3(self, aws_access, tmp_path):
        """Synthesized audio is valid MP3 format."""
        voice = TTSVoiceOptions(voice_id="Joanna", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {"Test audio format": None}
        client.synthesize(entities, "english", None)

        audio = entities["Test audio format"]
        output_file = tmp_path / "test.mp3"
        output_file.write_bytes(audio)

        # MP3 files start with ID3 tag or frame sync
        assert audio[:3] == b"ID3" or (audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0)

    def test_synthesize_special_characters(self, aws_access):
        """Synthesize text with special characters using SSML."""
        voice = TTSVoiceOptions(voice_id="Joanna", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)

        entities = {"Option A/B; choose wisely": None}
        client.synthesize(entities, "english", None)

        audio = entities["Option A/B; choose wisely"]
        assert audio is not None
        assert len(audio) > 500


class TestAWSPollyCostTracking:
    """E2E tests for AWS Polly with cost tracking."""

    def test_cost_tracker_records_usage(self, aws_access):
        """Cost tracker records character usage and cost."""
        from ankify.tts.tts_cost_tracker import AWSPollyCostTracker
        from decimal import Decimal

        voice = TTSVoiceOptions(voice_id="Joanna", engine="neural")
        client = AWSPollySingleLanguageClient(aws_access, voice)
        tracker = AWSPollyCostTracker()

        entities = {"Hello world": None}
        client.synthesize(entities, "english", tracker)

        # Calculate totals from internal usage dict
        total_chars = sum(u.chars for u in tracker._usage.values())
        total_cost = sum(u.cost for u in tracker._usage.values())

        assert total_chars > 0
        assert total_cost > Decimal("0.00")  # AWS Polly is not free

