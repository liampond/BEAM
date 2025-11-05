"""
LLM provider implementations

File: src/llm_integration/base.py
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any
import anthropic
import openai
import google.generativeai as genai
import requests


# ============================================================================
# Base Class
# ============================================================================

class BaseLLM(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, model_name: str, timeout: int = 60, 
                 temperature: float = 0.0, seed: int = None,
                 max_tokens: int = 1024, **kwargs):
        self.model_name = model_name
        self.timeout = timeout
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.extra_params = kwargs
    
    @abstractmethod
    def _call_api(self, prompt: str, temperature: float = None, max_tokens: int = None, seed: int = None, timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        """
        Make the actual API call. Must be implemented by subclasses.
        
        Returns:
            tuple of (response_text, metadata_dict)
        """
        pass
    
    def send_prompt(self, prompt: str, timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        """
        Send prompt to LLM.

        Args:
            prompt: The prompt text
            timeout: Optional override for default timeout
            **kwargs: Additional parameters to pass to API

        Returns:
            Tuple of (response_text, metadata_dict)
        """
        timeout = timeout or self.timeout
        temperature = kwargs.pop('temperature', None)
        max_tokens = kwargs.pop('max_tokens', None)
        seed = kwargs.pop('seed', None)

        try:
            result = self._call_api(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                timeout=timeout,
                **kwargs,
            )
            if isinstance(result, tuple):
                if len(result) >= 2:
                    response_text = result[0]
                    metadata = result[-1] or {}
                else:
                    # Unexpected single-item tuple: stringify and create metadata
                    response_text = str(result[0])
                    metadata = {}
            else:
                response_text = str(result)
                metadata = {}

            metadata = metadata or {}
            metadata = self._normalize_metadata(metadata, temperature=temperature, seed=seed, max_tokens=max_tokens)
            return response_text, metadata
        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {str(e)}")


    def _normalize_metadata(self, metadata: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Normalize provider-specific metadata into canonical keys.

        Canonical keys produced:
          - model: model name
          - backend: provider id/class
          - finish_reason: stop/finish reason string if available
          - seed: seed used (if any)
          - temperature: temperature used
          - raw: original provider metadata (kept for detail)

        The function inspects common provider-specific keys (OpenAI, Anthropic, Google)
        and maps them into the canonical names. It is intentionally forgiving.
        """
        out: Dict[str, Any] = {}
        md = metadata or {}

        out['model'] = md.get('model', self.model_name)
        cls_name = self.__class__.__name__
        backend_name = cls_name.replace('Provider', '') if cls_name.endswith('Provider') else cls_name
        out['backend'] = md.get('backend', backend_name.lower())
        out['temperature'] = kwargs.get('temperature', md.get('temperature', self.temperature))

        finish = md.get('finish_reason') or md.get('stop_reason') or md.get('stop')
        if finish:
            out['finish_reason'] = finish

        seed = kwargs.get('seed', None)
        if seed is None:
            seed = self.seed
        if seed is None:
            seed = md.get('seed')
        if seed is not None:
            out['seed'] = seed
        out['raw'] = md

        return out


# ============================================================================
# Anthropic Claude
# ============================================================================

class AnthropicProvider(BaseLLM):
    """Anthropic Claude API provider."""
    
    def __init__(self, model_name: str = "claude-opus-4-1-20250805", **kwargs):
        super().__init__(model_name, **kwargs)
        self.client = anthropic.Anthropic()  
    
    def _call_api(self, prompt: str, temperature: float = None, max_tokens: int = None, seed: int = None, timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature
        timeout = timeout or self.timeout
        call_params = {
            'model': self.model_name,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': [{"role": "user", "content": prompt}],
            'timeout': timeout,
        }

        if seed is not None:
            call_params['seed'] = seed

        response = self.client.messages.create(**call_params)
        
        return self._extract_anthropic_text(response)


    def _extract_anthropic_text(self, response) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from Anthropic response."""
        metadata = {
            'stop_reason': getattr(response, 'stop_reason', None),
        }

        text = None
        try:
            text = response.content[0].text
        except (AttributeError, IndexError, TypeError, KeyError):
            pass # Fallback will handle it
        
        if text is None:
            try:
                text = str(response)
            except Exception:
                text = ''

        return text, metadata

# ============================================================================
# OpenAI GPT
# ============================================================================

class OpenAIProvider(BaseLLM):
    """OpenAI GPT API provider."""
    
    def __init__(self, model_name: str = "gpt-5-2025-08-07", **kwargs):
        super().__init__(model_name, **kwargs)
        self.client = openai.OpenAI()  # Reads OPENAI_API_KEY
    
    def _call_api(self, prompt: str, temperature: float = None, max_tokens: int = None, seed: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        call_max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature
        
        # Build call parameters for responses API (reasoning models)
        response_params = {
            'model': self.model_name,
            'input': prompt,
            'max_output_tokens': call_max_tokens,
            'reasoning': {}
        }

        # Note: GPT-5 reasoning models don't support seed parameter
        # if seed is not None:
        #     response_params['seed'] = seed

        response = self.client.responses.create(**response_params)

        return self._extract_openai_text(response)

    
    def _extract_openai_text(self, response) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from OpenAI reasoning model response."""
        content = None
        finish_reason = None
        metadata = {}

        try:
            # Reasoning model format (responses API)
            for block in response.output:
                if block.type == 'message':
                    finish_reason = getattr(block, 'finish_reason', getattr(block, 'stop_reason', None))
                    
                    for sub_content in block.content:
                        if sub_content.type == 'output_text':
                            content = sub_content.text
                            break 
                
                if content:
                    break  
                
        except (AttributeError, IndexError, TypeError, KeyError):
            pass 

        if content is None:
            try:
                content = str(response) 
            except Exception:
                content = ''

        if finish_reason:
            metadata['finish_reason'] = finish_reason

        return content, metadata
    
# ============================================================================
# Google Gemini
# ============================================================================

class GoogleProvider(BaseLLM):
    """Google Gemini API provider."""
    
    def __init__(self, model_name: str = "gemini-2.5-pro", **kwargs):
        super().__init__(model_name, **kwargs)
        genai.configure()  # Reads GOOGLE_API_KEY
        self.model = genai.GenerativeModel(model_name)
    
    def _call_api(self, prompt: str, temperature: float = None, 
                  max_tokens: int = None, seed: int = None, 
                  timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        generation_config = {
            'temperature': temperature,
            'max_output_tokens': max_tokens,
        }


        if seed is not None:
            generation_config['seed'] = seed

        response = self.model.generate_content(
            prompt,
            generation_config=generation_config
        )

        metadata = {}

        try:
            if response.candidates:
                metadata['finish_reason'] = response.candidates[0].finish_reason.name
        except (AttributeError, IndexError):
            pass

        text = self._extract_google_text(response)

        return text, metadata
    
    def _extract_google_text(self, response) -> str:
        """Extract text from Google response with fallbacks."""
        
        try:
            if not response.candidates:
                 return f"<RESPONSE_BLOCKED: No candidates found.>"
            finish_reason = getattr(response.candidates[0], 'finish_reason', 0) # 0 = unspecified
            if finish_reason.value != 1: # 1 = STOP 
                return f"<RESPONSE_BLOCKED: Finish reason was {finish_reason.name} ({finish_reason.value})>"
        except Exception:
            pass

        if hasattr(response, 'text'):
            return response.text

        try:
            if response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content'):
                    if isinstance(candidate.content, str):
                        return candidate.content
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        return candidate.content.parts[0].text
                if hasattr(candidate, 'text'):
                    return candidate.text
        except (AttributeError, IndexError, TypeError):
            pass
        
        return str(response)

# ============================================================================
# Local/Custom API
# ============================================================================

class LocalProvider(BaseLLM):
    """Local or custom API endpoint provider."""
    
    def __init__(self, model_name: str, api_url: str, **kwargs):
        super().__init__(model_name, **kwargs)
        self.api_url = api_url
    
    def _call_api(self, prompt: str, temperature: float = None, max_tokens: int = None, seed: int = None, timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        call_seed = seed
        if call_seed is None:
            call_seed = self.seed

        payload = {
            'model': self.model_name,
            'prompt': prompt,
            'temperature': temperature if temperature is not None else self.temperature,
            'seed': call_seed,
            'max_tokens': max_tokens if max_tokens is not None else self.max_tokens,
            **kwargs
        }

        response = requests.post(self.api_url, json=payload, timeout=timeout or self.timeout)
        response.raise_for_status()

        data = response.json()
        response_text = data.get('response', data.get('text', ''))

        metadata = {
            'status_code': response.status_code,
            'api_url': self.api_url,
        }

        return response_text, metadata


# ============================================================================
# Alibaba Cloud / Qwen
# ============================================================================

class AlibabaCloudProvider(BaseLLM):
    """Alibaba Cloud / Qwen API provider (Singapore/International region)."""
    
    def __init__(self, model_name: str, **kwargs):
        super().__init__(model_name, **kwargs)
        import os
        # Use DASHSCOPE_API_KEY for international region
        self.api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('QWEN_API_KEY')
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        # Use Singapore/International endpoint
        self.api_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    def _call_api(self, prompt: str, temperature: float = None, max_tokens: int = None, seed: int = None, timeout: int = None, **kwargs) -> Tuple[str, Dict[str, Any]]:
        import requests
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model_name,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': temperature if temperature is not None else self.temperature,
            'max_tokens': max_tokens if max_tokens is not None else self.max_tokens,
        }
        
        # Add seed if provided
        if seed is not None or self.seed is not None:
            payload['seed'] = seed if seed is not None else self.seed
        
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract response text
        response_text = data['choices'][0]['message']['content']
        
        # Extract metadata
        metadata = {
            'model': data.get('model'),
            'usage': data.get('usage'),
            'finish_reason': data['choices'][0].get('finish_reason'),
            'raw': data
        }
        
        return response_text, metadata


# ============================================================================
# Provider Registry and Factory
# ============================================================================

PROVIDER_REGISTRY = {
    'anthropic': AnthropicProvider,
    'openai': OpenAIProvider,
    'google': GoogleProvider,
    'alibaba-cloud': AlibabaCloudProvider,
    'local': LocalProvider,
}


def get_llm_provider(provider: str, model_name: str, **kwargs) -> BaseLLM:
    """
    Factory function to get LLM provider instance.
    
    Args:
        provider: Provider name (anthropic, openai, google, local)
        model_name: Model identifier
        **kwargs: Additional parameters (timeout, temperature, seed, max_tokens, etc.)
        
    Returns:
        LLM provider instance
        
    Example:
        >>> llm = get_llm_provider('openai', 'gpt-4', seed=42, temperature=0.0)
        >>> response, metadata = llm.send_prompt("What is 2+2?")
    """
    if provider not in PROVIDER_REGISTRY:
        available = ', '.join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")
        
    provider_class = PROVIDER_REGISTRY[provider]

    # Handling for local provider to pass api_url
    if provider == 'local':
        api_url = kwargs.pop('api_url', None)
        if not api_url:
            raise ValueError("The 'local' provider requires --api-url")
        return provider_class(model_name, api_url, **kwargs)
    
    # Other providers
    if model_name:
            return provider_class(model_name=model_name, **kwargs)
    else:
            return provider_class(**kwargs)