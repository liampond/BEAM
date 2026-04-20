"""
Batch API Support for OpenAI and Anthropic

Batch APIs offer 50% cost savings and higher rate limits by
processing requests asynchronously.

OpenAI Batch API:
    - Submit JSONL file of requests
    - Poll for completion
    - Download results
    
Anthropic Message Batches:
    - Submit array of requests
    - Poll for completion
    - Retrieve results

Usage:
    batch_runner = BatchRunner(config)
    batch_id = batch_runner.submit_batch(test_cases, model_config)
    results = batch_runner.wait_for_completion(batch_id)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import time
import tempfile
import os


def is_retryable(exc: Exception) -> bool:
    """True if exc is a transient error that warrants retry with backoff."""
    try:
        import requests as _req
        if isinstance(exc, (_req.ConnectionError, _req.Timeout)):
            return True
    except ImportError:
        pass
    try:
        import openai as _oai
        if isinstance(exc, _oai.RateLimitError):
            return True
    except ImportError:
        pass
    try:
        import anthropic as _ant
        if isinstance(exc, _ant.RateLimitError):
            return True
    except ImportError:
        pass
    try:
        from google.api_core import exceptions as _gexc
        if isinstance(exc, _gexc.ResourceExhausted):
            return True
    except ImportError:
        pass
    return False


def is_stale_error(exc: Exception) -> bool:
    """True if exc indicates the batch no longer exists (expired, deleted, not found)."""
    try:
        import openai as _oai
        if isinstance(exc, _oai.NotFoundError):
            return True
    except ImportError:
        pass
    try:
        import anthropic as _ant
        if isinstance(exc, _ant.NotFoundError):
            return True
    except ImportError:
        pass
    try:
        from google.api_core import exceptions as _gexc
        if isinstance(exc, _gexc.NotFound):
            return True
    except ImportError:
        pass
    return False


@dataclass
class BatchRequest:
    """A single request within a batch."""
    custom_id: str  # Unique identifier (e.g., "Q-001_abc")
    prompt: str
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result from a completed batch request."""
    custom_id: str
    response_text: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchStatus:
    """Status of a batch job."""
    batch_id: str
    provider: str
    status: str  # pending, processing, completed, failed, cancelled
    total_requests: int
    completed_requests: int
    failed_requests: int
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        return self.status in ("completed", "failed", "cancelled", "expired")
    
    @property
    def progress_pct(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.completed_requests + self.failed_requests) / self.total_requests * 100


class OpenAIBatchAPI:
    """
    OpenAI Batch API implementation.
    
    Workflow:
        1. Create JSONL file with requests
        2. Upload file to OpenAI
        3. Create batch with file ID
        4. Poll for completion
        5. Download and parse results
    """
    
    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        import openai
        self.client = openai.OpenAI()
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def _build_batch_description(
        self,
        requests: List[BatchRequest],
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a descriptive string for the batch.
        
        Uses batch_metadata if provided, otherwise parses custom_ids as fallback.
        Custom IDs are formatted as "Q-XXX_format_Nbar" (e.g., "Q-001_abc_1-bar")
        
        Returns description like: "abc_1bar_Q-001-to-Q-100"
        """
        # Use passed metadata if available
        if batch_metadata:
            format_name = batch_metadata.get("format", "unknown")
            num_measures = batch_metadata.get("num_measures", "?")
            passage_len = f"{num_measures}bar"
            
            # Get question range from metadata or fall through to compute
            question_range = batch_metadata.get("question_range")
            if question_range:
                return f"{format_name}_{passage_len}_{question_range}"
        else:
            # Fallback: Parse custom_ids
            if not requests:
                return "empty-batch"
            
            first_id = requests[0].custom_id
            parts = first_id.split('_')
            format_name = parts[1] if len(parts) > 1 else "unknown"
            passage_len = parts[2] if len(parts) > 2 else "unknown"
            passage_len = passage_len.replace('-', '')
        
        # Compute question range from requests
        question_ids = []
        for req in requests:
            req_parts = req.custom_id.split('_')
            if req_parts:
                question_ids.append(req_parts[0])
        
        question_ids_sorted = sorted(question_ids)
        first_q = question_ids_sorted[0] if question_ids_sorted else "Q-???"
        last_q = question_ids_sorted[-1] if question_ids_sorted else "Q-???"
        
        if first_q == last_q:
            return f"{format_name}_{passage_len}_{first_q}"
        else:
            return f"{format_name}_{passage_len}_{first_q}-to-{last_q}"
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit batch of requests.
        
        Args:
            requests: List of BatchRequest objects
            json_mode: Whether to request JSON output
            batch_metadata: Optional metadata (format, num_measures, question_range)
        
        Returns:
            batch_id for tracking
        """
        # Create JSONL content
        lines = []
        for req in requests:
            messages = []
            if req.system_prompt:
                messages.append({"role": "system", "content": req.system_prompt})
            messages.append({"role": "user", "content": req.prompt})
            
            body = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
            }
            
            # Newer OpenAI models (gpt-4.1+, gpt-5+, o1, o3, etc.) use max_completion_tokens
            if any(x in self.model_name for x in ["gpt-4.1", "gpt-5", "o1", "o3"]):
                body["max_completion_tokens"] = self.max_tokens
            else:
                body["max_tokens"] = self.max_tokens
            
            if json_mode:
                # Use JSON schema for strict structured output
                body["response_format"] = {
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
            
            line = {
                "custom_id": req.custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
            lines.append(json.dumps(line))
        
        jsonl_content = "\n".join(lines)
        
        # Write to temp file and upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(jsonl_content)
            temp_path = f.name
        
        try:
            # Upload file
            with open(temp_path, 'rb') as f:
                file_response = self.client.files.create(
                    file=f,
                    purpose="batch"
                )
            
            # Build descriptive metadata
            batch_desc = self._build_batch_description(requests, batch_metadata)

            # Create batch with metadata for tracking
            batch = self.client.batches.create(
                input_file_id=file_response.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
                metadata={"description": batch_desc},
            )
            
            return batch.id
            
        finally:
            os.unlink(temp_path)
    
    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current status of a batch."""
        batch = self.client.batches.retrieve(batch_id)
        
        return BatchStatus(
            batch_id=batch_id,
            provider="openai",
            status=batch.status,
            total_requests=batch.request_counts.total if batch.request_counts else 0,
            completed_requests=batch.request_counts.completed if batch.request_counts else 0,
            failed_requests=batch.request_counts.failed if batch.request_counts else 0,
            created_at=str(batch.created_at) if batch.created_at else None,
            completed_at=str(batch.completed_at) if batch.completed_at else None,
        )
    
    def get_results(self, batch_id: str) -> List[BatchResult]:
        """Download and parse results from completed batch."""
        import time
        
        # Sometimes there's a brief delay before output file is available
        for attempt in range(5):
            batch = self.client.batches.retrieve(batch_id)
            
            if batch.status != "completed":
                raise ValueError(f"Batch not completed. Status: {batch.status}")
            
            if batch.output_file_id:
                break
            
            time.sleep(2)  # Wait a bit and retry
        else:
            raise ValueError("No output file available after retries")
        
        # Download output file
        file_response = self.client.files.content(batch.output_file_id)
        content = file_response.text
        
        results = []
        for line in content.strip().split('\n'):
            if not line:
                continue
            
            data = json.loads(line)
            custom_id = data["custom_id"]
            
            if data.get("error"):
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text="",
                    success=False,
                    error=str(data["error"]),
                ))
            else:
                response = data["response"]
                body = response["body"]
                text = body["choices"][0]["message"]["content"]
                
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text=text,
                    success=True,
                    metadata={
                        "model": body.get("model"),
                        "usage": body.get("usage"),
                        "finish_reason": body["choices"][0].get("finish_reason"),
                    }
                ))
        
        return results
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a pending or in-progress batch."""
        try:
            self.client.batches.cancel(batch_id)
            return True
        except Exception as e:
            if is_stale_error(e):
                return False
            raise


class AnthropicBatchAPI:
    """
    Anthropic Message Batches API implementation.
    
    Workflow:
        1. Create batch with array of requests
        2. Poll for completion
        3. Retrieve results
    
    Uses structured outputs beta for guaranteed JSON responses.
    """
    
    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        import anthropic
        # Use beta header for structured outputs
        self.client = anthropic.Anthropic(
            default_headers={"anthropic-beta": "structured-outputs-2025-11-13"}
        )
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit batch of requests.
        
        Args:
            requests: List of BatchRequest objects
            json_mode: Whether to request JSON output
            batch_metadata: Optional metadata (not used by Anthropic, but kept for API consistency)
        
        Returns:
            batch_id for tracking
        """
        batch_requests = []
        
        # JSON schema for structured output
        json_schema = {
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
        
        for req in requests:
            system = req.system_prompt or ""
            
            params = {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": req.prompt}],
            }
            
            if system:
                params["system"] = system
            
            # Use structured output for JSON mode
            # Note: Anthropic uses "output_format" (not "response_format")
            if json_mode:
                params["output_format"] = {
                    "type": "json_schema",
                    "schema": json_schema
                }
            
            batch_requests.append({
                "custom_id": req.custom_id,
                "params": params,
            })
        
        batch = self.client.messages.batches.create(requests=batch_requests)
        return batch.id
    
    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current status of a batch."""
        batch = self.client.messages.batches.retrieve(batch_id)
        
        # Map Anthropic status to our status
        status_map = {
            "in_progress": "processing",
            "ended": "completed",
            "canceling": "cancelled",
            "canceled": "cancelled",
        }
        
        return BatchStatus(
            batch_id=batch_id,
            provider="anthropic",
            status=status_map.get(batch.processing_status, batch.processing_status),
            total_requests=batch.request_counts.processing + batch.request_counts.succeeded + batch.request_counts.errored + batch.request_counts.canceled if batch.request_counts else 0,
            completed_requests=batch.request_counts.succeeded if batch.request_counts else 0,
            failed_requests=batch.request_counts.errored if batch.request_counts else 0,
            created_at=str(batch.created_at) if batch.created_at else None,
            completed_at=str(batch.ended_at) if batch.ended_at else None,
        )
    
    def get_results(self, batch_id: str) -> List[BatchResult]:
        """Retrieve results from completed batch."""
        results = []
        
        # Iterate through paginated results
        for result in self.client.messages.batches.results(batch_id):
            custom_id = result.custom_id
            
            if result.result.type == "succeeded":
                message = result.result.message
                text = message.content[0].text if message.content else ""
                
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text=text,
                    success=True,
                    metadata={
                        "model": message.model,
                        "stop_reason": message.stop_reason,
                        "input_tokens": message.usage.input_tokens if message.usage else None,
                        "output_tokens": message.usage.output_tokens if message.usage else None,
                    }
                ))
            else:
                error_type = result.result.type
                error_msg = str(result.result.error) if hasattr(result.result, 'error') else error_type
                
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text="",
                    success=False,
                    error=error_msg,
                ))
        
        return results
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch."""
        try:
            self.client.messages.batches.cancel(batch_id)
            return True
        except Exception as e:
            if is_stale_error(e):
                return False
            raise


class GoogleBatchAPI:
    """
    Google Gemini Batch API implementation.

    Uses file-based JSONL submission so each request carries a `key` field that
    Google echoes back on the response envelope. This is the only Gemini batch
    mode that supports per-request custom IDs; inline batches do not.

    Workflow:
        1. Write requests to a JSONL file, upload via the Files API
        2. Create a batch job pointing at the uploaded file
        3. Poll for completion
        4. Download the result file and parse by `key`
    """

    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        from google import genai
        import os

        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY must be set for Google batch API")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def _build_display_name(
        self,
        requests: List[BatchRequest],
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a descriptive display_name for the batch.
        
        Uses batch_metadata if provided, otherwise parses custom_ids as fallback.
        Custom IDs are formatted as "Q-XXX_format_Nbar" (e.g., "Q-001_abc_1-bar")
        
        Returns display_name like: "abc_1bar_Q-001-to-Q-100"
        """
        # Use passed metadata if available
        if batch_metadata:
            format_name = batch_metadata.get("format", "unknown")
            num_measures = batch_metadata.get("num_measures", "?")
            passage_len = f"{num_measures}bar"
            
            # Get question range from metadata or fall through to compute
            question_range = batch_metadata.get("question_range")
            if question_range:
                return f"{format_name}_{passage_len}_{question_range}"
        else:
            # Fallback: Parse custom_ids
            if not requests:
                return "empty-batch"
            
            first_id = requests[0].custom_id
            parts = first_id.split('_')
            format_name = parts[1] if len(parts) > 1 else "unknown"
            passage_len = parts[2] if len(parts) > 2 else "unknown"
            passage_len = passage_len.replace('-', '')  # "1-bar" -> "1bar"
        
        # Extract question IDs to determine range
        question_ids = []
        for req in requests:
            req_parts = req.custom_id.split('_')
            if req_parts:
                question_ids.append(req_parts[0])  # e.g., "Q-001"
        
        # Sort to get first and last
        question_ids_sorted = sorted(question_ids)
        first_q = question_ids_sorted[0] if question_ids_sorted else "Q-???"
        last_q = question_ids_sorted[-1] if question_ids_sorted else "Q-???"
        
        # Build display name
        if first_q == last_q:
            return f"{format_name}_{passage_len}_{first_q}"
        else:
            return f"{format_name}_{passage_len}_{first_q}-to-{last_q}"
    
    def _build_request_config(self, req: BatchRequest, json_mode: bool) -> Dict[str, Any]:
        # File-based Gemini batch JSONL uses the raw REST API shape (camelCase),
        # not the google-genai SDK's snake_case `config` wrapper.
        contents = [{
            'parts': [{'text': req.prompt}],
            'role': 'user',
        }]

        generation_config: Dict[str, Any] = {
            'temperature': self.temperature,
            'maxOutputTokens': self.max_tokens,
        }

        request: Dict[str, Any] = {'contents': contents}

        if req.system_prompt:
            system_text = req.system_prompt
            if json_mode:
                system_text += "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object."
            request['systemInstruction'] = {'parts': [{'text': system_text}]}

        if json_mode:
            generation_config['responseMimeType'] = 'application/json'
            generation_config['responseSchema'] = {
                "type": "OBJECT",
                "properties": {"answer": {"type": "STRING"}},
                "required": ["answer"],
            }

        request['generationConfig'] = generation_config
        return request

    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Submit a batch using the file-based JSONL path.

        Each JSONL line has shape ``{"key": custom_id, "request": {...}}``.
        Google echoes the key back on the response envelope, giving us
        alignment without any client-side index bookkeeping.
        """
        seen_keys = set()
        for req in requests:
            if req.custom_id in seen_keys:
                raise ValueError(f"Duplicate custom_id in batch: {req.custom_id}")
            seen_keys.add(req.custom_id)

        jsonl_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.jsonl', delete=False, encoding='utf-8'
            ) as tmp:
                jsonl_path = tmp.name
                for req in requests:
                    line = {
                        'key': req.custom_id,
                        'request': self._build_request_config(req, json_mode),
                    }
                    tmp.write(json.dumps(line) + '\n')

            uploaded = self.client.files.upload(
                file=jsonl_path,
                config={'mime_type': 'jsonl', 'display_name': 'batch-requests'},
            )
        finally:
            if jsonl_path and os.path.exists(jsonl_path):
                os.unlink(jsonl_path)

        display_name = self._build_display_name(requests, batch_metadata)

        batch_job = self.client.batches.create(
            model=f"models/{self.model_name}",
            src=uploaded.name,
            config={'display_name': display_name},
        )

        return batch_job.name

    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current status of a batch."""
        batch = self.client.batches.get(name=batch_id)
        
        # Map Google batch states to our status
        state_map = {
            'JOB_STATE_PENDING': 'pending',
            'JOB_STATE_RUNNING': 'processing',
            'JOB_STATE_SUCCEEDED': 'completed',
            'JOB_STATE_FAILED': 'failed',
            'JOB_STATE_CANCELLED': 'cancelled',
            'JOB_STATE_EXPIRED': 'expired',
        }
        
        state_name = batch.state.name if hasattr(batch.state, 'name') else str(batch.state)
        status = state_map.get(state_name, 'processing')

        return BatchStatus(
            batch_id=batch_id,
            provider="google",
            status=status,
            total_requests=0,
            completed_requests=0,
            failed_requests=0,
            created_at=None,
            completed_at=None,
        )

    def get_results(self, batch_id: str) -> List[BatchResult]:
        """Fetch and parse results for a completed batch.

        Does not validate against submitted keys — callers must run
        ``validate_batch_results`` from ``batch_storage`` to catch missing /
        unexpected keys. Any line missing a ``key`` is returned as a failure
        with a synthesised id so validation can report it explicitly.
        """
        batch = self.client.batches.get(name=batch_id)

        if not (batch.dest and batch.dest.file_name):
            raise ValueError(
                f"Batch {batch_id} has no result file. "
                "File-based submission is required; inline mode is no longer supported."
            )

        file_content = self.client.files.download(file=batch.dest.file_name)
        content = file_content.decode('utf-8')

        results: List[BatchResult] = []
        for line_num, line in enumerate(content.strip().split('\n'), start=1):
            if not line:
                continue

            data = json.loads(line)
            custom_id = data.get('key')
            if not custom_id:
                results.append(BatchResult(
                    custom_id=f"__missing_key_line_{line_num}",
                    response_text="",
                    success=False,
                    error=f"response line {line_num} missing 'key' field",
                ))
                continue

            if 'response' in data and data['response']:
                try:
                    text = data['response']['candidates'][0]['content']['parts'][0]['text']
                    results.append(BatchResult(
                        custom_id=custom_id,
                        response_text=text,
                        success=True,
                        metadata={"model": self.model_name},
                    ))
                except (KeyError, IndexError) as e:
                    results.append(BatchResult(
                        custom_id=custom_id,
                        response_text="",
                        success=False,
                        error=f"Failed to parse response: {e}",
                    ))
            elif 'error' in data:
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text="",
                    success=False,
                    error=str(data['error']),
                ))
            else:
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text="",
                    success=False,
                    error="response line has neither 'response' nor 'error'",
                ))

        return results
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch."""
        try:
            self.client.batches.cancel(name=batch_id)
            return True
        except Exception as e:
            if is_stale_error(e):
                return False
            raise


class AlibabaBatchAPI:
    """
    Alibaba Cloud / DashScope Batch API implementation.
    
    Uses the OpenAI-compatible batch API with DashScope endpoints.
    Singapore region: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    
    Workflow is identical to OpenAI:
        1. Create JSONL file with requests
        2. Upload file to DashScope
        3. Create batch with file ID
        4. Poll for completion
        5. Download and parse results
    
    Provides 50% cost savings compared to real-time inference.
    """
    
    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        import openai
        import os
        
        api_key = os.getenv('DASHSCOPE_API_KEY')
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        
        # Use OpenAI client with DashScope Singapore endpoint
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        )
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit batch of requests.
        
        Args:
            requests: List of BatchRequest objects
            json_mode: Whether to request JSON output
            batch_metadata: Optional metadata (not fully used by Alibaba, but kept for API consistency)
        
        Returns:
            batch_id for tracking
        """
        # Create JSONL content (same format as OpenAI)
        lines = []
        for req in requests:
            messages = []
            if req.system_prompt:
                messages.append({"role": "system", "content": req.system_prompt})
            messages.append({"role": "user", "content": req.prompt})
            
            body = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            if json_mode:
                # Use JSON schema for strict structured output
                body["response_format"] = {
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
            
            line = {
                "custom_id": req.custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
            lines.append(json.dumps(line))
        
        jsonl_content = "\n".join(lines)
        
        # Write to temp file and upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(jsonl_content)
            temp_path = f.name
        
        try:
            # Upload file
            with open(temp_path, 'rb') as f:
                file_response = self.client.files.create(
                    file=f,
                    purpose="batch"
                )
            
            # Create batch
            batch = self.client.batches.create(
                input_file_id=file_response.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )
            
            return batch.id
            
        finally:
            os.unlink(temp_path)
    
    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current status of a batch."""
        batch = self.client.batches.retrieve(batch_id)
        
        return BatchStatus(
            batch_id=batch_id,
            provider="alibaba",
            status=batch.status,
            total_requests=batch.request_counts.total if batch.request_counts else 0,
            completed_requests=batch.request_counts.completed if batch.request_counts else 0,
            failed_requests=batch.request_counts.failed if batch.request_counts else 0,
            created_at=str(batch.created_at) if batch.created_at else None,
            completed_at=str(batch.completed_at) if batch.completed_at else None,
        )
    
    def get_results(self, batch_id: str) -> List[BatchResult]:
        """Download and parse results from completed batch."""
        import time
        
        # Sometimes there's a brief delay before output file is available
        for attempt in range(5):
            batch = self.client.batches.retrieve(batch_id)
            
            if batch.status != "completed":
                raise ValueError(f"Batch not completed. Status: {batch.status}")
            
            if batch.output_file_id:
                break
            
            time.sleep(2)  # Wait a bit and retry
        else:
            raise ValueError("No output file available after retries")
        
        # Download output file
        file_response = self.client.files.content(batch.output_file_id)
        content = file_response.text
        
        results = []
        for line in content.strip().split('\n'):
            if not line:
                continue
            
            data = json.loads(line)
            custom_id = data["custom_id"]
            
            if data.get("error"):
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text="",
                    success=False,
                    error=str(data["error"]),
                ))
            else:
                response = data["response"]
                body = response["body"]
                text = body["choices"][0]["message"]["content"]
                
                results.append(BatchResult(
                    custom_id=custom_id,
                    response_text=text,
                    success=True,
                    metadata={
                        "model": body.get("model"),
                        "usage": body.get("usage"),
                        "finish_reason": body["choices"][0].get("finish_reason"),
                    }
                ))
        
        return results
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a pending or in-progress batch."""
        try:
            self.client.batches.cancel(batch_id)
            return True
        except Exception as e:
            if is_stale_error(e):
                return False
            raise


class BatchRunner:
    """
    High-level batch runner that handles submission, polling, and result collection.

    Usage:
        runner = BatchRunner(provider="openai", model_name="gpt-4o")
        batch_id = runner.submit(requests)
        results = runner.wait_for_completion(batch_id, check_interval=60)

    Callers must pair ``get_results`` / ``wait_for_completion`` with
    ``validate_batch_results`` (see ``batch_storage``) to cross-check
    returned keys against the submitted set.
    """
    
    def __init__(
        self,
        provider: str,
        model_name: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ):
        self.provider = provider
        self.model_name = model_name
        
        if provider == "openai":
            self.api = OpenAIBatchAPI(model_name, max_tokens, temperature)
        elif provider == "anthropic":
            self.api = AnthropicBatchAPI(model_name, max_tokens, temperature)
        elif provider == "google":
            self.api = GoogleBatchAPI(model_name, max_tokens, temperature)
        elif provider == "alibaba":
            self.api = AlibabaBatchAPI(model_name, max_tokens, temperature)
        else:
            raise ValueError(f"Batch API not supported for provider: {provider}")
    
    def submit(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Submit batch and return batch ID."""
        return self.api.submit_batch(requests, json_mode=json_mode, batch_metadata=batch_metadata)

    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current batch status."""
        return self.api.get_status(batch_id)

    def get_results(self, batch_id: str) -> List[BatchResult]:
        """Fetch and parse completed batch results.

        Callers must pass the returned list through
        ``batch_storage.validate_batch_results`` to cross-check against the
        submitted custom_ids.
        """
        return self.api.get_results(batch_id)

    def wait_for_completion(
        self,
        batch_id: str,
        check_interval: int = 60,
        max_wait_time: int = 3600,
        progress_callback: Optional[callable] = None,
    ) -> List[BatchResult]:
        """Wait for batch to complete and return raw results (unvalidated)."""
        start_time = time.time()

        while True:
            status = self.get_status(batch_id)

            if progress_callback:
                progress_callback(status)

            if status.is_complete:
                if status.status == "completed":
                    return self.get_results(batch_id)
                else:
                    raise RuntimeError(f"Batch {status.status}: {status.failed_requests} failed")

            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                raise TimeoutError(f"Batch did not complete within {max_wait_time}s")

            time.sleep(check_interval)
    
    def cancel(self, batch_id: str) -> bool:
        """Cancel a batch."""
        return self.api.cancel_batch(batch_id)
