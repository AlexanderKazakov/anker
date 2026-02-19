"""E2E tests for MCP with  Azure TTS.

These tests require Azure credentials:
- ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY
"""

from ankify.tts.azure_tts import AzureTTSSingleLanguageClient
from ankify.settings import TTSVoiceOptions


class TestAzureTTS:
    """E2E tests for  Azure TTS synthesis."""

    def test_synthesize_english_text(self, azure_access):
        """Synthesize English text with  Azure TTS."""
        voice = TTSVoiceOptions(voice_id="en-US-AriaNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)

        entities = {"Hello world from Azure TTS": None}
        client.synthesize(entities, "english", None)

        audio = entities["Hello world from Azure TTS"]
        assert audio is not None
        assert isinstance(audio, bytes)
        assert len(audio) > 1000

    def test_synthesize_german_text(self, azure_access):
        """Synthesize German text with  Azure TTS."""
        voice = TTSVoiceOptions(voice_id="de-DE-KatjaNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)

        entities = {"Guten Tag": None}
        client.synthesize(entities, "german", None)

        audio = entities["Guten Tag"]
        assert audio is not None
        assert len(audio) > 1000

    def test_synthesize_multiple_texts(self, azure_access):
        """Synthesize multiple texts with  Azure TTS."""
        voice = TTSVoiceOptions(voice_id="en-US-JennyNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)

        entities = {
            "First sentence": None,
            "Second sentence": None,
            "Third sentence": None,
        }
        client.synthesize(entities, "english", None)

        for text, audio in entities.items():
            assert audio is not None, f"No audio for '{text}'"
            assert len(audio) > 500

    def test_audio_is_valid_format(self, azure_access, tmp_path):
        """Synthesized audio is valid audio format."""
        voice = TTSVoiceOptions(voice_id="en-US-AriaNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)

        entities = {"Test audio format": None}
        client.synthesize(entities, "english", None)

        audio = entities["Test audio format"]
        output_file = tmp_path / "test.mp3"
        output_file.write_bytes(audio)

        # Verify file was written and has content
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_synthesize_special_characters(self, azure_access):
        """Synthesize text with special characters."""
        voice = TTSVoiceOptions(voice_id="en-US-AriaNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)

        entities = {"Option A/B; choose wisely": None}
        client.synthesize(entities, "english", None)

        audio = entities["Option A/B; choose wisely"]
        assert audio is not None
        assert len(audio) > 500


class TestAzureTTSCostTracking:
    """E2E tests for Azure TTS with cost tracking."""

    def test_cost_tracker_records_usage(self, azure_access):
        """Cost tracker records character usage and cost."""
        from ankify.tts.tts_cost_tracker import AzureTTSCostTracker
        from decimal import Decimal

        voice = TTSVoiceOptions(voice_id="en-US-AriaNeural")
        client = AzureTTSSingleLanguageClient(azure_access, voice)
        tracker = AzureTTSCostTracker()

        entities = {"Hello world": None}
        client.synthesize(entities, "english", tracker)

        # Calculate totals from internal usage dict
        total_chars = sum(u.chars for u in tracker._usage.values())
        total_cost = sum(u.cost for u in tracker._usage.values())

        assert total_chars > 0
        assert total_cost > Decimal("0.00")  # Azure TTS is not free

