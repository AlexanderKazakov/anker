"""Unit tests for Jinja2 prompt formatter."""

import pytest
import jinja2

from ankify.llm.jinja2_prompt_formatter import PromptRenderer, jinja2_raise


class TestPromptRenderer:
    """Tests for PromptRenderer class."""

    def test_render_simple_template(self):
        """Render a simple template with variables."""
        template = "Hello, {{ name }}!"
        result = PromptRenderer.render(template, {"name": "World"})
        assert result == "Hello, World!"

    def test_render_with_multiple_variables(self):
        """Render template with multiple variables."""
        template = "{{ greeting }}, {{ name }}! Language: {{ lang }}"
        result = PromptRenderer.render(
            template,
            {"greeting": "Hello", "name": "User", "lang": "English"},
        )
        assert result == "Hello, User! Language: English"

    def test_render_with_conditionals(self):
        """Render template with Jinja2 conditionals."""
        template = """
{% if include_extra %}
Extra content here
{% endif %}
Main content
"""
        result_with = PromptRenderer.render(template, {"include_extra": True})
        assert "Extra content here" in result_with

        result_without = PromptRenderer.render(template, {"include_extra": False})
        assert "Extra content here" not in result_without
        assert "Main content" in result_without

    def test_render_with_loops(self):
        """Render template with Jinja2 loops."""
        template = """
{% for item in items %}
- {{ item }}
{% endfor %}
"""
        result = PromptRenderer.render(template, {"items": ["one", "two", "three"]})
        assert "- one" in result
        assert "- two" in result
        assert "- three" in result

    def test_undefined_variable_raises(self):
        """Undefined variables raise StrictUndefined error."""
        template = "Hello, {{ undefined_var }}!"
        with pytest.raises(jinja2.UndefinedError):
            PromptRenderer.render(template, {})

    def test_trim_blocks(self):
        """trim_blocks removes newlines after block tags."""
        template = """{% if True %}
content
{% endif %}"""
        result = PromptRenderer.render(template, {})
        # trim_blocks should remove the newline after {% if True %}
        assert result.startswith("content")

    def test_lstrip_blocks(self):
        """lstrip_blocks removes leading whitespace from block tags."""
        template = """    {% if True %}
content
    {% endif %}"""
        result = PromptRenderer.render(template, {})
        # lstrip_blocks should remove leading spaces before {% if True %}
        assert not result.startswith(" ")

    def test_fail_function_available(self):
        """The fail() function is available in templates."""
        template = "{% if error %}{{ fail('Error occurred') }}{% endif %}"
        with pytest.raises(jinja2.TemplateRuntimeError, match="Error occurred"):
            PromptRenderer.render(template, {"error": True})

    def test_fail_function_not_called_when_condition_false(self):
        """fail() is not called when condition is false."""
        template = "{% if error %}{{ fail('Error') }}{% else %}OK{% endif %}"
        result = PromptRenderer.render(template, {"error": False})
        assert result == "OK"

    def test_empty_template(self):
        """Empty template returns empty string."""
        result = PromptRenderer.render("", {})
        assert result == ""

    def test_template_with_special_characters(self):
        """Template handles special characters in variables."""
        template = "Text: {{ text }}"
        result = PromptRenderer.render(template, {"text": "Привет < & > 'quotes'"})
        assert "Привет < & > 'quotes'" in result

    def test_nested_objects(self):
        """Template can access nested object attributes."""
        template = "{{ config.language.name }}"
        context = {"config": {"language": {"name": "English"}}}
        result = PromptRenderer.render(template, context)
        assert result == "English"


class TestJinja2Raise:
    """Tests for jinja2_raise helper function."""

    def test_raises_template_runtime_error(self):
        """jinja2_raise raises TemplateRuntimeError with message."""
        with pytest.raises(jinja2.TemplateRuntimeError, match="Test error"):
            jinja2_raise("Test error")

    def test_raises_with_custom_message(self):
        """jinja2_raise uses the provided message."""
        try:
            jinja2_raise("Custom error message")
            pytest.fail("Expected TemplateRuntimeError")
        except jinja2.TemplateRuntimeError as e:
            assert str(e) == "Custom error message"
