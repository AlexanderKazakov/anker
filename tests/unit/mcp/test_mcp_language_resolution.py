"""Integration tests for MCP language resolution."""


class TestLanguageAliasResolution:
    """Tests for _resolve_language_alias function."""

    def test_resolve_two_letter_code(self):
        """Two-letter ISO codes are resolved."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("en") == "english"
        assert _resolve_language_alias("de") == "german"
        assert _resolve_language_alias("ru") == "russian"
        assert _resolve_language_alias("fr") == "french"
        assert _resolve_language_alias("es") == "spanish"

    def test_resolve_three_letter_code(self):
        """Three-letter ISO codes are resolved."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("eng") == "english"
        assert _resolve_language_alias("deu") == "german"
        assert _resolve_language_alias("rus") == "russian"

    def test_resolve_case_insensitive(self):
        """Resolution is case-insensitive."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("EN") == "english"
        assert _resolve_language_alias("En") == "english"
        assert _resolve_language_alias("GER") == "german"
        assert _resolve_language_alias("Rus") == "russian"

    def test_resolve_full_name_passthrough(self):
        """Full language names pass through unchanged."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        # Full names not in aliases pass through (lowercase)
        assert _resolve_language_alias("English") == "english"
        assert _resolve_language_alias("German") == "german"

    def test_resolve_unknown_passthrough(self):
        """Unknown languages pass through as lowercase."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("english") == "english"
        assert _resolve_language_alias("german") == "german"
        assert _resolve_language_alias("russian") == "russian"
        assert _resolve_language_alias("french") == "french"
        assert _resolve_language_alias("spanish") == "spanish"
        assert _resolve_language_alias("portuguese") == "portuguese"
        assert _resolve_language_alias("italian") == "italian"
        assert _resolve_language_alias("japanese") == "japanese"
        assert _resolve_language_alias("korean") == "korean"
        assert _resolve_language_alias("chinese") == "chinese"
        assert _resolve_language_alias("arabic") == "arabic"

    def test_resolve_regional_variants(self):
        """Regional variants are resolved."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("en-us") == "english_us"
        assert _resolve_language_alias("en-gb") == "english_british"
        assert _resolve_language_alias("de-at") == "german_austrian"
        assert _resolve_language_alias("fr-ca") == "french_canadian"

    def test_resolve_common_aliases(self):
        """Common informal aliases are resolved."""
        from ankify.mcp.ankify_mcp_server import _resolve_language_alias

        assert _resolve_language_alias("ge") == "german"
        assert _resolve_language_alias("jp") == "japanese"
        assert _resolve_language_alias("kr") == "korean"
        assert _resolve_language_alias("cn") == "chinese"
