"""Unit tests for TTS cost tracking."""

import pytest
from decimal import Decimal

from ankify.tts.tts_cost_tracker import (
    AWSPollyCostTracker,
    AzureTTSCostTracker,
    EdgeTTSCostTracker,
    MultiProviderCostTracker,
    EngineUsage,
    LanguageUsageKey,
)


class TestEngineUsage:
    """Tests for EngineUsage dataclass."""

    def test_default_values(self):
        """Default values are zero."""
        usage = EngineUsage()
        assert usage.chars == 0
        assert usage.cost == Decimal("0.00")

    def test_custom_values(self):
        """Can set custom values."""
        usage = EngineUsage(chars=1000, cost=Decimal("1.50"))
        assert usage.chars == 1000
        assert usage.cost == Decimal("1.50")


class TestLanguageUsageKey:
    """Tests for LanguageUsageKey dataclass."""

    def test_hash_equality(self):
        """Same language+engine produces same hash."""
        key1 = LanguageUsageKey(language="english", engine="neural")
        key2 = LanguageUsageKey(language="english", engine="neural")
        assert hash(key1) == hash(key2)

    def test_equality(self):
        """Same language+engine are equal."""
        key1 = LanguageUsageKey(language="english", engine="neural")
        key2 = LanguageUsageKey(language="english", engine="neural")
        assert key1 == key2

    def test_inequality_different_language(self):
        """Different language means not equal."""
        key1 = LanguageUsageKey(language="english", engine="neural")
        key2 = LanguageUsageKey(language="german", engine="neural")
        assert key1 != key2

    def test_inequality_different_engine(self):
        """Different engine means not equal."""
        key1 = LanguageUsageKey(language="english", engine="neural")
        key2 = LanguageUsageKey(language="english", engine="standard")
        assert key1 != key2

    def test_usable_as_dict_key(self):
        """Can be used as dictionary key."""
        d = {}
        key = LanguageUsageKey(language="english", engine="neural")
        d[key] = "value"
        assert d[key] == "value"


class TestAWSPollyCostTracker:
    """Tests for AWS Polly cost tracker."""

    def test_standard_rate(self):
        """Standard engine uses $4.00 per million chars."""
        tracker = AWSPollyCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "standard")
        assert cost == Decimal("4.00")

    def test_neural_rate(self):
        """Neural engine uses $16.00 per million chars."""
        tracker = AWSPollyCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "neural")
        assert cost == Decimal("16.00")

    def test_long_form_rate(self):
        """Long-form engine uses $100.00 per million chars."""
        tracker = AWSPollyCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "long-form")
        assert cost == Decimal("100.00")

    def test_generative_rate(self):
        """Generative engine uses $30.00 per million chars."""
        tracker = AWSPollyCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "generative")
        assert cost == Decimal("30.00")

    def test_small_text_cost(self):
        """Small text has proportionally small cost."""
        tracker = AWSPollyCostTracker()
        # 1000 chars at $16/million = $0.016
        cost = tracker.calculate_cost("a" * 1000, "neural")
        assert cost == Decimal("0.016")

    def test_empty_text_cost(self):
        """Empty text has zero cost."""
        tracker = AWSPollyCostTracker()
        cost = tracker.calculate_cost("", "neural")
        assert cost == Decimal("0.00")

    def test_track_usage_accumulates(self):
        """track_usage accumulates character counts and costs."""
        tracker = AWSPollyCostTracker()
        tracker.track_usage("hello", "neural", "english")
        tracker.track_usage("world", "neural", "english")

        key = LanguageUsageKey(language="english", engine="neural")
        assert tracker._usage[key].chars == 10

    def test_track_usage_by_language(self):
        """track_usage separates by language."""
        tracker = AWSPollyCostTracker()
        tracker.track_usage("hello", "neural", "english")
        tracker.track_usage("hallo", "neural", "german")

        assert len(tracker._usage) == 2


class TestAzureTTSCostTracker:
    """Tests for Azure TTS cost tracker."""

    def test_neural_rate(self):
        """Neural engine uses $15.00 per million chars."""
        tracker = AzureTTSCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "neural")
        assert cost == Decimal("15.00")

    def test_neural_hd_rate(self):
        """Neural HD engine uses $30.00 per million chars."""
        tracker = AzureTTSCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "neural-hd")
        assert cost == Decimal("30.00")

    def test_hd_detection_case_insensitive(self):
        """HD detection is case-insensitive."""
        tracker = AzureTTSCostTracker()
        cost_lower = tracker.calculate_cost("a" * 1000, "neural-hd")
        cost_upper = tracker.calculate_cost("a" * 1000, "NEURAL-HD")
        assert cost_lower == cost_upper

    def test_default_engine_is_neural(self):
        """None engine defaults to neural rate."""
        tracker = AzureTTSCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, None)
        assert cost == Decimal("15.00")


class TestEdgeTTSCostTracker:
    """Tests for Edge TTS cost tracker."""

    def test_free_rate(self):
        """Edge TTS is free (rate is 0)."""
        tracker = EdgeTTSCostTracker()
        cost = tracker.calculate_cost("a" * 1_000_000, "free")
        assert cost == Decimal("0.00")

    def test_any_engine_is_free(self):
        """Any engine name results in zero cost."""
        tracker = EdgeTTSCostTracker()
        assert tracker.calculate_cost("test", "neural") == Decimal("0.00")
        assert tracker.calculate_cost("test", "anything") == Decimal("0.00")
        assert tracker.calculate_cost("test", None) == Decimal("0.00")

    def test_still_tracks_characters(self):
        """Still tracks character count even though cost is zero."""
        tracker = EdgeTTSCostTracker()
        tracker.track_usage("hello world", "free", "english")

        key = LanguageUsageKey(language="english", engine="free")
        assert tracker._usage[key].chars == 11
        assert tracker._usage[key].cost == Decimal("0.00")


class TestMultiProviderCostTracker:
    """Tests for multi-provider cost tracker."""

    def test_get_tracker_aws(self):
        """get_tracker returns AWS tracker for 'aws'."""
        multi = MultiProviderCostTracker()
        tracker = multi.get_tracker("aws")
        assert isinstance(tracker, AWSPollyCostTracker)

    def test_get_tracker_azure(self):
        """get_tracker returns Azure tracker for 'azure'."""
        multi = MultiProviderCostTracker()
        tracker = multi.get_tracker("azure")
        assert isinstance(tracker, AzureTTSCostTracker)

    def test_get_tracker_edge(self):
        """get_tracker returns Edge tracker for 'edge'."""
        multi = MultiProviderCostTracker()
        tracker = multi.get_tracker("edge")
        assert isinstance(tracker, EdgeTTSCostTracker)

    def test_get_tracker_unknown_raises(self):
        """get_tracker raises for unknown provider."""
        multi = MultiProviderCostTracker()
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            multi.get_tracker("unknown")

    def test_get_tracker_caches(self):
        """get_tracker returns same instance on repeated calls."""
        multi = MultiProviderCostTracker()
        tracker1 = multi.get_tracker("aws")
        tracker2 = multi.get_tracker("aws")
        assert tracker1 is tracker2

    def test_multiple_providers(self):
        """Can track usage across multiple providers."""
        multi = MultiProviderCostTracker()

        aws = multi.get_tracker("aws")
        azure = multi.get_tracker("azure")
        edge = multi.get_tracker("edge")

        aws.track_usage("test", "neural", "english")
        azure.track_usage("test", "neural", "german")
        edge.track_usage("test", "free", "spanish")

        assert len(multi._trackers) == 3
