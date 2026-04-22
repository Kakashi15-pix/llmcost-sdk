"""Tests for cost extractors."""

import pytest
from pricing.extractors import (
    AnthropicExtractor,
    OpenAIExtractor,
    get_extractor,
)


class TestAnthropicExtractor:
    """Test Anthropic-specific cost extraction."""

    def test_extract_usage_valid_response(self):
        """Test extracting usage from valid Anthropic response."""
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        }
        
        extractor = AnthropicExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage is not None
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_extract_usage_with_cache(self):
        """Test extracting usage with cache tokens."""
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 25,
                "cache_read_input_tokens": 10,
            }
        }
        
        extractor = AnthropicExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage["cache_creation_tokens"] == 25
        assert usage["cache_read_tokens"] == 10

    def test_extract_model(self):
        """Test extracting model from response."""
        response = {"model": "claude-3-opus-20240229"}
        
        extractor = AnthropicExtractor()
        model = extractor.extract_model(response)
        
        assert model == "claude-3-opus-20240229"

    def test_extract_stop_reason(self):
        """Test extracting stop reason from response."""
        response = {"stop_reason": "end_turn"}
        
        extractor = AnthropicExtractor()
        stop_reason = extractor.extract_stop_reason(response)
        
        assert stop_reason == "end_turn"


class TestOpenAIExtractor:
    """Test OpenAI-specific cost extraction."""

    def test_extract_usage_valid_response(self):
        """Test extracting usage from valid OpenAI response."""
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 0,
            }
        }
        
        extractor = OpenAIExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage is not None
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_extract_usage_with_cache(self):
        """Test extracting usage with cached tokens."""
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_prompt_tokens": 20,
            }
        }
        
        extractor = OpenAIExtractor()
        usage = extractor.extract_usage(response)
        
        assert usage["cache_read_tokens"] == 20

    def test_extract_model(self):
        """Test extracting model from OpenAI response."""
        response = {"model": "gpt-4-turbo"}
        
        extractor = OpenAIExtractor()
        model = extractor.extract_model(response)
        
        assert model == "gpt-4-turbo"


class TestExtractorRegistry:
    """Test extractor registry and lookup."""

    def test_get_anthropic_extractor(self):
        """Test getting Anthropic extractor."""
        extractor = get_extractor("anthropic")
        assert isinstance(extractor, AnthropicExtractor)

    def test_get_openai_extractor(self):
        """Test getting OpenAI extractor."""
        extractor = get_extractor("openai")
        assert isinstance(extractor, OpenAIExtractor)

    def test_get_missing_extractor(self):
        """Test getting extractor for unknown provider."""
        extractor = get_extractor("unknown-provider")
        assert extractor is None
