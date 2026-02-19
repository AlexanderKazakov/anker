"""Unit tests for LLM cost tracking."""

import json
import pytest
from decimal import Decimal

from ankify.llm.llm_cost_tracker import (
    LLMPricing,
    LLMTokenUsage,
    LLMCost,
    LLMPricingLoader,
    LLMUsage,
    _determine_cost_decimals,
    _create_cost_formatter,
)


class TestLLMPricing:
    """Tests for LLMPricing dataclass."""

    def test_default_values(self):
        """Default values are all zero."""
        pricing = LLMPricing()
        assert pricing.cached_input == Decimal(0)
        assert pricing.uncached_input == Decimal(0)
        assert pricing.reasoning == Decimal(0)
        assert pricing.output == Decimal(0)

    def test_is_valid_true(self):
        """Valid pricing has positive values with correct relationships."""
        pricing = LLMPricing(
            cached_input=Decimal("0.0000005"),
            uncached_input=Decimal("0.000001"),
            reasoning=Decimal("0.000002"),
            output=Decimal("0.000002"),
        )
        assert pricing.is_valid

    def test_is_valid_false_when_cached_greater_than_uncached(self):
        """Invalid if cached input cost > uncached input cost."""
        pricing = LLMPricing(
            cached_input=Decimal("0.002"),  # Greater than uncached
            uncached_input=Decimal("0.001"),
            reasoning=Decimal("0.002"),
            output=Decimal("0.002"),
        )
        assert not pricing.is_valid

    def test_is_valid_false_when_zeros(self):
        """Invalid if any value is zero."""
        pricing = LLMPricing(
            cached_input=Decimal("0.001"),
            uncached_input=Decimal(0),  # Zero
            reasoning=Decimal("0.002"),
            output=Decimal("0.002"),
        )
        assert not pricing.is_valid


class TestLLMTokenUsage:
    """Tests for LLMTokenUsage dataclass."""

    def test_default_values(self):
        """Default values are all zero."""
        usage = LLMTokenUsage()
        assert usage.cached_input == 0
        assert usage.uncached_input == 0
        assert usage.reasoning == 0
        assert usage.output == 0
        assert usage.total == 0

    def test_is_valid_true(self):
        """Valid usage sums to total."""
        usage = LLMTokenUsage(
            cached_input=10,
            uncached_input=90,
            reasoning=20,
            output=80,
            total=200,
        )
        assert usage.is_valid

    def test_is_valid_false_when_sum_mismatch(self):
        """Invalid if components don't sum to total."""
        usage = LLMTokenUsage(
            cached_input=10,
            uncached_input=90,
            reasoning=20,
            output=80,
            total=100,  # Wrong total
        )
        assert not usage.is_valid

    def test_is_valid_false_with_negative(self):
        """Invalid if any value is negative."""
        usage = LLMTokenUsage(
            cached_input=-10,
            uncached_input=110,
            reasoning=20,
            output=80,
            total=200,
        )
        assert not usage.is_valid

    def test_add(self):
        """Token usages can be added."""
        usage1 = LLMTokenUsage(10, 90, 20, 80, 200)
        usage2 = LLMTokenUsage(5, 45, 10, 40, 100)
        result = usage1 + usage2
        assert result.cached_input == 15
        assert result.uncached_input == 135
        assert result.reasoning == 30
        assert result.output == 120
        assert result.total == 300

    def test_radd_with_zero(self):
        """sum() works with token usages."""
        usage = LLMTokenUsage(10, 90, 20, 80, 200)
        result = sum([usage])
        assert result.total == 200

    def test_from_completion_usage(self, mocker):
        """Parse OpenAI CompletionUsage."""
        mock_usage = mocker.MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        mock_usage.prompt_tokens_details = mocker.MagicMock(cached_tokens=20)
        mock_usage.completion_tokens_details = mocker.MagicMock(reasoning_tokens=10)

        mocker.patch("ankify.llm.llm_cost_tracker.CompletionUsage", mocker.MagicMock)
        result = LLMTokenUsage._from_openai_completion_usage(mock_usage)

        assert result.cached_input == 20
        assert result.uncached_input == 80  # 100 - 20
        assert result.reasoning == 10
        assert result.output == 40  # 50 - 10
        assert result.total == 150

    def test_from_completion_usage_no_details(self, mocker):
        """Parse CompletionUsage without details."""
        mock_usage = mocker.MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        mock_usage.prompt_tokens_details = None
        mock_usage.completion_tokens_details = None

        mocker.patch("ankify.llm.llm_cost_tracker.CompletionUsage", mocker.MagicMock)
        result = LLMTokenUsage._from_openai_completion_usage(mock_usage)

        assert result.cached_input == 0
        assert result.uncached_input == 100
        assert result.reasoning == 0
        assert result.output == 50

    def test_from_response_usage(self, mocker):
        """Parse OpenAI ResponseUsage."""
        mock_usage = mocker.MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.total_tokens = 150
        mock_usage.input_tokens_details = mocker.MagicMock(cached_tokens=30)
        mock_usage.output_tokens_details = mocker.MagicMock(reasoning_tokens=15)

        mocker.patch("ankify.llm.llm_cost_tracker.ResponseUsage", mocker.MagicMock)
        result = LLMTokenUsage._from_openai_response_usage(mock_usage)

        assert result.cached_input == 30
        assert result.uncached_input == 70  # 100 - 30
        assert result.reasoning == 15
        assert result.output == 35  # 50 - 15


class TestLLMCost:
    """Tests for LLMCost dataclass."""

    def test_default_values(self):
        """Default values are all zero."""
        cost = LLMCost()
        assert cost.cached_input == Decimal(0)
        assert cost.total == Decimal(0)

    def test_is_valid_true(self):
        """Valid cost sums to total."""
        cost = LLMCost(
            cached_input=Decimal("0.01"),
            uncached_input=Decimal("0.02"),
            reasoning=Decimal("0.03"),
            output=Decimal("0.04"),
            total=Decimal("0.10"),
        )
        assert cost.is_valid

    def test_is_valid_false_when_sum_mismatch(self):
        """Invalid if components don't sum to total."""
        cost = LLMCost(
            cached_input=Decimal("0.01"),
            uncached_input=Decimal("0.02"),
            reasoning=Decimal("0.03"),
            output=Decimal("0.04"),
            total=Decimal("0.05"),  # Wrong
        )
        assert not cost.is_valid

    def test_calculate(self):
        """Calculate cost from token usage and pricing."""
        usage = LLMTokenUsage(
            cached_input=1000,
            uncached_input=2000,
            reasoning=500,
            output=1500,
            total=5000,
        )
        pricing = LLMPricing(
            cached_input=Decimal("0.000001"),  # $1/million
            uncached_input=Decimal("0.000002"),  # $2/million
            reasoning=Decimal("0.000003"),  # $3/million
            output=Decimal("0.000003"),  # $3/million
        )
        cost = LLMCost.calculate(usage, pricing)

        assert cost.cached_input == Decimal("0.001")  # 1000 * 0.000001
        assert cost.uncached_input == Decimal("0.004")  # 2000 * 0.000002
        assert cost.reasoning == Decimal("0.0015")  # 500 * 0.000003
        assert cost.output == Decimal("0.0045")  # 1500 * 0.000003
        assert cost.total == Decimal("0.011")

    def test_add(self):
        """Costs can be added."""
        cost1 = LLMCost(
            Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"), Decimal("0.10")
        )
        cost2 = LLMCost(
            Decimal("0.005"), Decimal("0.01"), Decimal("0.015"), Decimal("0.02"), Decimal("0.05")
        )
        result = cost1 + cost2
        assert result.total == Decimal("0.15")

    def test_radd_with_zero(self):
        """sum() works with costs."""
        cost = LLMCost(
            Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"), Decimal("0.10")
        )
        result = sum([cost])
        assert result.total == Decimal("0.10")


class TestLLMPricingLoader:
    """Tests for LLMPricingLoader singleton."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        LLMPricingLoader._instance = None
        yield
        LLMPricingLoader._instance = None

    def test_singleton_pattern(self, tmp_path):
        """Same instance returned on repeated calls."""
        loader1 = LLMPricingLoader(cache_dir=tmp_path)
        loader2 = LLMPricingLoader(cache_dir=tmp_path)
        assert loader1 is loader2

    def test_get_pricing_from_cache(self, tmp_path):
        """Load pricing from valid cache file."""
        cache_file = tmp_path / "llm_pricing.json"
        cache_data = {
            "gpt-5": {
                "input_cost_per_token": "0.00003",
                "output_cost_per_token": "0.00006",
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("gpt-5")

        assert pricing.uncached_input == Decimal("0.00003")
        assert pricing.output == Decimal("0.00006")

    def test_get_pricing_unknown_model_returns_zeros(self, tmp_path):
        """Unknown model returns zero pricing."""
        cache_file = tmp_path / "llm_pricing.json"
        cache_file.write_text(json.dumps({"gpt-5": {}}))

        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("unknown-model")

        assert pricing.uncached_input == Decimal(0)
        assert pricing.output == Decimal(0)

    def test_get_pricing_fuzzy_match(self, tmp_path):
        """Fuzzy match on model name prefix."""
        cache_file = tmp_path / "llm_pricing.json"
        cache_data = {
            "openai/gpt-5": {
                "input_cost_per_token": "0.00001",
                "output_cost_per_token": "0.00003",
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("gpt-5")

        assert pricing.uncached_input == Decimal("0.00001")

    def test_cached_input_defaults_to_uncached(self, tmp_path):
        """If no cache_read_input_token_cost, use input cost."""
        cache_file = tmp_path / "llm_pricing.json"
        cache_data = {
            "gpt-5": {
                "input_cost_per_token": "0.00003",
                "output_cost_per_token": "0.00006",
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("gpt-5")

        assert pricing.cached_input == pricing.uncached_input

    def test_cache_read_input_token_cost_used(self, tmp_path):
        """Uses cache_read_input_token_cost when available."""
        cache_file = tmp_path / "llm_pricing.json"
        cache_data = {
            "gpt-5": {
                "input_cost_per_token": "0.00003",
                "cache_read_input_token_cost": "0.000015",
                "output_cost_per_token": "0.00006",
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("gpt-5")

        assert pricing.cached_input == Decimal("0.000015")

    def test_fetch_from_url_when_no_cache(self, tmp_path, mocker):
        """Fetch from URL when cache doesn't exist."""
        mock_data = {
            "gpt-5": {
                "input_cost_per_token": "0.00003",
                "output_cost_per_token": "0.00006",
            }
        }

        mocker.patch.object(LLMPricingLoader, "_fetch_from_url", return_value=mock_data)
        loader = LLMPricingLoader(cache_dir=tmp_path)
        pricing = loader.get_pricing("gpt-5")

        assert pricing.uncached_input == Decimal("0.00003")


class TestCostFormatting:
    """Tests for cost formatting utilities."""

    def test_determine_cost_decimals_large_values(self):
        """Large values use 2 decimal places."""
        cost = LLMCost(
            Decimal("1.00"), Decimal("2.00"), Decimal("3.00"), Decimal("4.00"), Decimal("10.00")
        )
        assert _determine_cost_decimals(cost) == 2

    def test_determine_cost_decimals_small_values(self):
        """Small values need more decimal places."""
        cost = LLMCost(
            Decimal("0.0001"),
            Decimal("0.0002"),
            Decimal("0.0003"),
            Decimal("0.0004"),
            Decimal("0.001"),
        )
        # Should show at least 2 significant digits for smallest value
        decimals = _determine_cost_decimals(cost)
        assert decimals >= 4

    def test_determine_cost_decimals_all_zeros(self):
        """All zeros returns default 2."""
        cost = LLMCost()
        assert _determine_cost_decimals(cost) == 2

    def test_cost_formatter_zero(self):
        """Zero is formatted as $0."""
        formatter = _create_cost_formatter(2)
        assert formatter(Decimal(0)) == "$0"

    def test_cost_formatter_positive(self):
        """Positive values are formatted with $ prefix."""
        formatter = _create_cost_formatter(2)
        result = formatter(Decimal("1.50"))
        assert result == "$1.50"

    def test_cost_formatter_respects_decimals(self):
        """Formatter uses specified decimal places."""
        formatter = _create_cost_formatter(4)
        result = formatter(Decimal("0.0015"))
        assert result == "$0.0015"


class TestLLMUsage:
    """Tests for LLMUsage aggregate class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset pricing loader singleton before each test."""
        LLMPricingLoader._instance = None
        yield
        LLMPricingLoader._instance = None

    def test_add_same_model(self):
        """Can add usages for same model."""
        pricing = LLMPricing(
            Decimal("0.000001"), Decimal("0.000001"), Decimal("0.000002"), Decimal("0.000002")
        )
        tokens = LLMTokenUsage(10, 90, 20, 80, 200)
        cost = LLMCost.calculate(tokens, pricing)

        usage1 = LLMUsage("gpt-5", pricing, tokens, cost, 1)
        usage2 = LLMUsage("gpt-5", pricing, tokens, cost, 1)

        result = usage1 + usage2
        assert result.num_calls == 2
        assert result.token_usage.total == 400

    def test_add_different_models_raises(self):
        """Cannot add usages for different models."""
        pricing = LLMPricing(
            Decimal("0.000001"), Decimal("0.000001"), Decimal("0.000002"), Decimal("0.000002")
        )
        tokens = LLMTokenUsage(10, 90, 20, 80, 200)
        cost = LLMCost.calculate(tokens, pricing)

        usage1 = LLMUsage("gpt-5", pricing, tokens, cost, 1)
        usage2 = LLMUsage("gpt-5-nano", pricing, tokens, cost, 1)

        with pytest.raises(ValueError, match="Models must be the same"):
            usage1 + usage2

    def test_table_to_string(self):
        """Table can be converted to string."""
        pricing = LLMPricing(
            Decimal("0.000001"), Decimal("0.000001"), Decimal("0.000002"), Decimal("0.000002")
        )
        tokens = LLMTokenUsage(100, 900, 200, 800, 2000)
        cost = LLMCost.calculate(tokens, pricing)

        usage = LLMUsage("gpt-5", pricing, tokens, cost, 1)
        table_str = usage.table_to_string()

        assert "gpt-5" in table_str
        assert "TOTAL" in table_str
