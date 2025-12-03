"""
LLM Provider Implementations with JSON Mode Support

This module provides a unified interface for multiple LLM providers,
with API-level JSON output enforcement where supported.

JSON Mode Support by Provider:
    - OpenAI: response_format={"type": "json_object"}
    - Anthropic: Tool use with structured output OR prompt-based
    - Google: response_mime_type="application/json"
    - Alibaba/Qwen: OpenAI-compatible (json_object mode)
    
Design:
    - BaseLLMProvider: Abstract base with send_prompt() interface
    - Each provider implements _call_api() with JSON mode handling
    - Normalized metadata across all providers
    - Batch API support as a separate capability
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import time


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str  # Raw response text
    parsed_answer: Optional[str] = None  # Extracted answer if JSON parsed
    
    # Metadata
    model: str = ""
    provider: str = ""
    finish_reason: Optional[str] = None
    
    # Timing
    duration_seconds: float = 0.0
    
    # Token usage (if available)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    
    # Raw provider response (for debugging)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error handling
    success: bool = True
    error: Optional[str] = None
    
    def extract_json_answer(self) -> Optional[str]:
        """Try to extract 'answer' field from JSON response."""
        if self.parsed_answer:
            return self.parsed_answer
            
        import re
        try:
            # Find JSON object in response
            json_match = re.search(r'\{[^{}]*\}', self.text)
            if json_match:
                data = json.loads(json_match.group(0))
                for key in ['answer', 'result', 'value']:
                    if key in data:
                        self.parsed_answer = str(data[key])
                        return self.parsed_answer
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Subclasses must implement:
        - _call_api(): Make the actual API call
        - supports_json_mode: Property indicating JSON mode support
        - supports_batch_api: Property indicating batch API support
    """
    
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 300,
        seed: Optional[int] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.seed = seed
        self.extra_params = kwargs
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Whether this provider supports API-level JSON mode."""
        pass
    
    @property
    def supports_batch_api(self) -> bool:
        """Whether this provider supports batch API. Override in subclass."""
        return False
    
    @abstractmethod
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Make the actual API call.
        
        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt
            json_mode: Whether to enforce JSON output
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Tuple of (response_text, metadata_dict)
        """
        pass
    
    def send_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> LLMResponse:
        """
        Send prompt to LLM and return standardized response.
        
        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt
            json_mode: Whether to enforce JSON output (if supported)
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with text, metadata, and parsed answer
        """
        start_time = time.time()
        
        try:
            text, metadata = self._call_api(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode and self.supports_json_mode,
                **kwargs
            )
            
            response = LLMResponse(
                text=text,
                model=self.model_name,
                provider=self.provider_name,
                finish_reason=metadata.get('finish_reason'),
                input_tokens=metadata.get('input_tokens'),
                output_tokens=metadata.get('output_tokens'),
                total_tokens=metadata.get('total_tokens'),
                raw_metadata=metadata,
                duration_seconds=time.time() - start_time,
                success=True,
            )
            
            # Try to extract JSON answer
            response.extract_json_answer()
            
            return response
            
        except Exception as e:
            return LLMResponse(
                text="",
                model=self.model_name,
                provider=self.provider_name,
                duration_seconds=time.time() - start_time,
                success=False,
                error=str(e),
            )


# ============================================================================
# OpenAI Provider
# ============================================================================

class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT provider with JSON mode support.
    
    JSON Mode: Uses response_format={"type": "json_object"}
    Batch API: Supported via /v1/batches endpoint
    """
    
    def __init__(self, model_name: str = "gpt-4o", **kwargs):
        super().__init__(model_name, **kwargs)
        import openai
        self.client = openai.OpenAI()
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def supports_json_mode(self) -> bool:
        return True
    
    @property
    def supports_batch_api(self) -> bool:
        return True
    
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        call_params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        # Newer OpenAI models (gpt-4.1+, gpt-5+, o1, o3, etc.) use max_completion_tokens
        # Older models use max_tokens
        max_tok = kwargs.get("max_tokens", self.max_tokens)
        if any(x in self.model_name for x in ["gpt-4.1", "gpt-5", "o1", "o3"]):
            call_params["max_completion_tokens"] = max_tok
        else:
            call_params["max_tokens"] = max_tok
        
        # Add seed for reproducibility (if model supports it)
        if self.seed is not None:
            call_params["seed"] = self.seed
        
        # JSON mode enforcement
        if json_mode:
            # Use JSON schema for strict structured output
            call_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"}
                        },
                        "required": ["answer"],
                        "additionalProperties": False
                    }
                }
            }
        
        response = self.client.chat.completions.create(**call_params)
        
        text = response.choices[0].message.content or ""
        
        metadata = {
            "finish_reason": response.choices[0].finish_reason,
            "model": response.model,
            "input_tokens": response.usage.prompt_tokens if response.usage else None,
            "output_tokens": response.usage.completion_tokens if response.usage else None,
            "total_tokens": response.usage.total_tokens if response.usage else None,
        }
        
        return text, metadata


# ============================================================================
# Anthropic Provider
# ============================================================================

class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude provider.
    
    JSON Mode: Uses structured outputs beta (response_format with json_schema)
    Batch API: Supported via Message Batches API
    """
    
    def __init__(self, model_name: str = "claude-sonnet-4-20250514", **kwargs):
        super().__init__(model_name, **kwargs)
        import anthropic
        # Use beta header for structured outputs
        self.client = anthropic.Anthropic(
            default_headers={"anthropic-beta": "structured-outputs-2025-11-13"}
        )
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def supports_json_mode(self) -> bool:
        # Now uses native structured outputs
        return True
    
    @property
    def supports_batch_api(self) -> bool:
        return True
    
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        call_params = {
            "model": self.model_name,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            call_params["system"] = system_prompt
        
        # Use structured outputs for JSON mode via beta client
        if json_mode:
            call_params["betas"] = ["structured-outputs-2025-11-13"]
            call_params["output_format"] = {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "type": "string",
                            "description": "The answer to the question"
                        }
                    },
                    "required": ["answer"],
                    "additionalProperties": False
                }
            }
            response = self.client.beta.messages.create(**call_params)
        else:
            response = self.client.messages.create(**call_params)
        
        text = ""
        if response.content:
            text = response.content[0].text
        
        metadata = {
            "finish_reason": response.stop_reason,
            "model": response.model,
            "input_tokens": response.usage.input_tokens if response.usage else None,
            "output_tokens": response.usage.output_tokens if response.usage else None,
        }
        
        return text, metadata


# ============================================================================
# Google Gemini Provider
# ============================================================================

class GoogleProvider(BaseLLMProvider):
    """
    Google Gemini provider with JSON mode support.
    
    JSON Mode: Uses response_mime_type="application/json"
    Batch API: Not supported
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash", **kwargs):
        super().__init__(model_name, **kwargs)
        import google.generativeai as genai
        genai.configure()
        self.model = genai.GenerativeModel(model_name)
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def supports_json_mode(self) -> bool:
        return True
    
    @property
    def supports_batch_api(self) -> bool:
        return False
    
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        import google.generativeai as genai
        
        # Combine system prompt with user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        generation_config = {
            "temperature": kwargs.get("temperature", self.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        
        # JSON mode enforcement with schema
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"}
                },
                "required": ["answer"]
            }
        
        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        # Extract text with safety handling
        text = ""
        finish_reason = None
        
        try:
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason.name if hasattr(candidate, 'finish_reason') else None
                
                if hasattr(response, 'text'):
                    text = response.text
                elif hasattr(candidate.content, 'parts') and candidate.content.parts:
                    text = candidate.content.parts[0].text
        except Exception:
            text = str(response)
        
        metadata = {
            "finish_reason": finish_reason,
            "model": self.model_name,
        }
        
        return text, metadata


# ============================================================================
# Alibaba Cloud / Qwen Provider
# ============================================================================

class AlibabaProvider(BaseLLMProvider):
    """
    Alibaba Cloud / Qwen provider (OpenAI-compatible API).
    
    JSON Mode: Supported via response_format (OpenAI-compatible)
    Batch API: Not supported
    """
    
    def __init__(self, model_name: str = "qwen-max", **kwargs):
        super().__init__(model_name, **kwargs)
        import os
        self.api_key = os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        self.api_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    @property
    def provider_name(self) -> str:
        return "alibaba"
    
    @property
    def supports_json_mode(self) -> bool:
        return True
    
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        import requests
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': kwargs.get("temperature", self.temperature),
            'max_tokens': kwargs.get("max_tokens", self.max_tokens),
        }
        
        if json_mode:
            # Use JSON schema for strict structured output
            payload['response_format'] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"}
                        },
                        "required": ["answer"],
                        "additionalProperties": False
                    }
                }
            }
        
        if self.seed is not None:
            payload['seed'] = self.seed
        
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        text = data['choices'][0]['message']['content']
        
        metadata = {
            "finish_reason": data['choices'][0].get('finish_reason'),
            "model": data.get('model'),
            "input_tokens": data.get('usage', {}).get('prompt_tokens'),
            "output_tokens": data.get('usage', {}).get('completion_tokens'),
            "total_tokens": data.get('usage', {}).get('total_tokens'),
        }
        
        return text, metadata


# ============================================================================
# Local Transformers Provider
# ============================================================================

class TransformersProvider(BaseLLMProvider):
    """
    Local model provider using HuggingFace Transformers.
    
    JSON Mode: Prompt-based only
    Batch API: Not applicable (local)
    """
    
    def __init__(self, model_name: str = "microsoft/phi-4", **kwargs):
        super().__init__(model_name, **kwargs)
        
        try:
            import transformers
            import torch
        except ImportError:
            raise ImportError("transformers and torch required. Install with: pip install transformers torch accelerate")
        
        print(f"Loading local model: {model_name}...")
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=model_name,
            model_kwargs={"torch_dtype": "auto"},
            device_map="auto",
        )
        print(f"✓ Model loaded")
    
    @property
    def provider_name(self) -> str:
        return "transformers"
    
    @property
    def supports_json_mode(self) -> bool:
        return False  # Prompt-based only
    
    def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        temperature = kwargs.get("temperature", self.temperature)
        
        outputs = self.pipeline(
            messages,
            max_new_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=max(temperature, 0.1),  # Avoid 0.0
            do_sample=temperature > 0,
        )
        
        text = outputs[0]["generated_text"][-1]["content"]
        
        metadata = {
            "model": self.model_name,
            "finish_reason": "stop",
        }
        
        return text, metadata


# ============================================================================
# Provider Factory
# ============================================================================

PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "alibaba": AlibabaProvider,
    "alibaba-cloud": AlibabaProvider,  # Alias
    "transformers": TransformersProvider,
}


def get_provider(
    provider: str,
    model_name: str,
    **kwargs
) -> BaseLLMProvider:
    """
    Factory function to get LLM provider instance.
    
    Args:
        provider: Provider name (openai, anthropic, google, alibaba, transformers)
        model_name: Model identifier
        **kwargs: Additional parameters (temperature, max_tokens, timeout, seed)
        
    Returns:
        LLM provider instance
        
    Example:
        >>> provider = get_provider("openai", "gpt-4o", temperature=0.0, seed=42)
        >>> response = provider.send_prompt("What is 2+2?", json_mode=True)
        >>> print(response.parsed_answer)
    """
    if provider not in PROVIDER_REGISTRY:
        available = ', '.join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")
    
    provider_class = PROVIDER_REGISTRY[provider]
    return provider_class(model_name=model_name, **kwargs)
