"""Unit tests for SSML preprocessing in TTS clients."""

from ankify.tts.aws_tts import AWSPollySingleLanguageClient
from ankify.tts.edge_tts import EdgeTTSSingleLanguageClient


class TestAWSPollySSMLPreprocessing:
    """Tests for AWS Polly SSML preprocessing."""

    def test_plain_text_no_special_chars(self):
        """Plain text without special chars is returned as-is."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("Hello World")
        assert result == {"Text": "Hello World"}
        assert "TextType" not in result

    def test_text_with_slash_becomes_ssml(self):
        """Text with slash is converted to SSML with medium break."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("and/or")
        assert result["TextType"] == "ssml"
        assert "<speak>" in result["Text"]
        assert "<break strength='medium'/>" in result["Text"]
        assert "and" in result["Text"]
        assert "or" in result["Text"]
        # Original slash replaced - check it's not between "and" and "or" as literal
        assert "and/or" not in result["Text"]

    def test_text_with_semicolon_becomes_ssml(self):
        """Text with semicolon is converted to SSML with strong break."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("first; second")
        assert result["TextType"] == "ssml"
        assert "<speak>" in result["Text"]
        assert "<break strength='strong'/>" in result["Text"]
        assert "first" in result["Text"]
        assert "second" in result["Text"]
        assert ";" not in result["Text"]

    def test_xml_special_chars_are_escaped(self):
        """XML special characters are properly escaped."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("5 < 10; x > y")
        assert result["TextType"] == "ssml"
        assert "&lt;" in result["Text"]
        assert "&gt;" in result["Text"]
        # Semicolon should be replaced with break
        assert "<break strength='strong'/>" in result["Text"]
        # Original sequence with semicolon should not be present
        assert "10;" not in result["Text"]

    def test_ampersand_is_escaped(self):
        """Ampersand is escaped when SSML is generated."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("Tom & Jerry; friends")
        assert result["TextType"] == "ssml"
        assert "&amp;" in result["Text"]

    def test_multiple_special_chars(self):
        """Multiple special characters are all replaced."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("a/b; c/d")
        assert result["TextType"] == "ssml"
        assert result["Text"].count("<break strength='medium'/>") == 2
        assert result["Text"].count("<break strength='strong'/>") == 1


class TestEdgeTTSSSMLPreprocessing:
    """Tests for Edge TTS SSML preprocessing."""

    def test_plain_text_no_special_chars(self):
        """Plain text without special chars is returned as-is."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml("Hello World")
        assert result == "Hello World"
        assert "<speak>" not in result

    def test_text_with_slash_becomes_ssml(self):
        """Text with slash is converted to SSML with medium break."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml("and/or")
        assert "<speak>" in result
        assert "<break strength='medium'/>" in result
        # Original slash replaced - check it's not between "and" and "or" as literal
        assert "and/or" not in result

    def test_text_with_semicolon_becomes_ssml(self):
        """Text with semicolon is converted to SSML with strong break."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml("first; second")
        assert "<speak>" in result
        assert "<break strength='strong'/>" in result
        assert ";" not in result

    def test_xml_special_chars_are_escaped(self):
        """XML special characters are properly escaped."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml("5 < 10; x > y")
        assert "<speak>" in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_semicolon_replaced_in_sentence(self):
        """Semicolon in sentence is replaced with break."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml('He said "hello"; goodbye')
        assert "<speak>" in result
        assert "<break strength='strong'/>" in result
        # Original semicolon sequence should not be present
        assert '"hello";' not in result

    def test_edge_tts_returns_string(self):
        """Edge TTS preprocessing returns a string, not a dict."""
        result = EdgeTTSSingleLanguageClient.possibly_preprocess_text_into_ssml("test/text")
        assert isinstance(result, str)

    def test_aws_polly_returns_dict(self):
        """AWS Polly preprocessing returns a dict."""
        result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("test/text")
        assert isinstance(result, dict)
        assert "Text" in result


class TestSSMLMappingConsistency:
    """Tests to ensure SSML mappings are consistent between providers."""

    def test_same_characters_mapped(self):
        """Both providers map the same special characters."""
        aws_chars = {c for c, _, _ in AWSPollySingleLanguageClient.ssml_mapping}
        edge_chars = {c for c, _, _ in EdgeTTSSingleLanguageClient.ssml_mapping}
        assert aws_chars == edge_chars

    def test_same_replacements(self):
        """Both providers use the same SSML replacements."""
        aws_replacements = {(c, r) for c, r, _ in AWSPollySingleLanguageClient.ssml_mapping}
        edge_replacements = {(c, r) for c, r, _ in EdgeTTSSingleLanguageClient.ssml_mapping}
        assert aws_replacements == edge_replacements
