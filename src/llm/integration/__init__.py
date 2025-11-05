"""llm_integration package exports.

This file makes the `llm_integration` directory a regular package.
It also re-exports the factory helper so callers can import `get_llm_provider` from `llm_integration`.
"""
from .base import get_llm_provider, BaseLLM  

__all__ = ["get_llm_provider", "BaseLLM"]
