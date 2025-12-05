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
        return self.status in ("completed", "failed", "cancelled")
    
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
        except Exception:
            return False


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
        except Exception:
            return False


class GoogleBatchAPI:
    """
    Google Gemini Batch API implementation.
    
    Uses the google-genai SDK to submit batch requests.
    Batch API provides 50% cost savings and higher rate limits.
    
    IMPORTANT: Google's inline batch API returns responses in order but WITHOUT
    custom_ids. We must track the submission order to align results with questions.
    This is handled by storing request_ids in BatchRequestStorage.
    
    Workflow:
        1. Create batch with inline requests or JSONL file
        2. Poll for completion (target: 24h, usually faster)
        3. Retrieve results from inline responses or output file
        4. Align results using stored request_ids mapping
    """
    
    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        from google import genai
        import os
        
        # Get API key from environment
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY must be set for Google batch API")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # In-memory cache for request_ids (per-session backup)
        # Primary storage is BatchRequestStorage on disk
        self._request_ids_cache: Dict[str, List[str]] = {}
    
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
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
        batch_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit batch of requests using inline requests.
        
        Args:
            requests: List of BatchRequest objects
            json_mode: Whether to request JSON output
            batch_metadata: Optional metadata (format, num_measures, question_range)
        
        For small batches (<20MB), inline requests are simpler.
        For larger batches, we'd use file upload.
        
        Returns:
            batch_id for tracking
        """
        inline_requests = []
        
        for req in requests:
            # Build contents for the request
            contents = [{
                'parts': [{'text': req.prompt}],
                'role': 'user'
            }]
            
            request_config = {
                'contents': contents,
            }
            
            # Add system instruction if provided
            if req.system_prompt:
                system_text = req.system_prompt
                if json_mode:
                    system_text += "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object."
                request_config['config'] = {
                    'system_instruction': {'parts': [{'text': system_text}]},
                    'temperature': self.temperature,
                    'max_output_tokens': self.max_tokens,
                }
                if json_mode:
                    request_config['config']['response_mime_type'] = 'application/json'
                    request_config['config']['response_schema'] = {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"}
                        },
                        "required": ["answer"]
                    }
            else:
                config = {
                    'temperature': self.temperature,
                    'max_output_tokens': self.max_tokens,
                }
                if json_mode:
                    config['response_mime_type'] = 'application/json'
                    config['response_schema'] = {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"}
                        },
                        "required": ["answer"]
                    }
                request_config['config'] = config
            
            inline_requests.append(request_config)
        
        # Build descriptive display_name
        display_name = self._build_display_name(requests, batch_metadata)
        
        batch_job = self.client.batches.create(
            model=f"models/{self.model_name}",
            src=inline_requests,
            config={
                'display_name': display_name,
            },
        )
        
        batch_id = batch_job.name
        
        # Store request_ids in memory cache (backup for same-session retrieval)
        request_ids = [req.custom_id for req in requests]
        self._request_ids_cache[batch_id] = request_ids
        
        return batch_id
    
    def get_submitted_request_ids(self, batch_id: str) -> List[str]:
        """
        Get the request_ids that were submitted with a batch.
        
        This is needed for result alignment since Google's API doesn't
        return custom_ids in responses.
        
        Returns:
            List of custom_ids in submission order
            
        Raises:
            ValueError if batch_id not found in cache
        """
        if batch_id not in self._request_ids_cache:
            raise ValueError(
                f"No request_ids found in cache for batch {batch_id}. "
                "This batch may have been submitted in a different session. "
                "Use BatchRequestStorage to load request_ids from disk."
            )
        return self._request_ids_cache[batch_id]
    
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
            'JOB_STATE_EXPIRED': 'failed',
        }
        
        # Google batch doesn't provide individual request counts during processing
        # We'll estimate based on state
        state_name = batch.state.name if hasattr(batch.state, 'name') else str(batch.state)
        status = state_map.get(state_name, 'processing')
        
        # Use cached request_ids if available
        request_ids = self._request_ids_cache.get(batch_id, [])
        total = len(request_ids)
        completed = total if status == 'completed' else 0
        failed = total if status == 'failed' else 0
        
        return BatchStatus(
            batch_id=batch_id,
            provider="google",
            status=status,
            total_requests=total,
            completed_requests=completed,
            failed_requests=failed,
            created_at=None,  # Not readily available
            completed_at=None,
        )
    
    def get_results(self, batch_id: str, request_ids: Optional[List[str]] = None) -> List[BatchResult]:
        """Retrieve results from completed batch.
        
        Args:
            batch_id: The Google batch ID
            request_ids: List of custom_ids in submission order. REQUIRED for
                        alignment since Google's inline responses don't include
                        custom_ids. For batches submitted in the same session,
                        pass None to use the in-memory cache. For batches from
                        previous sessions, load from BatchRequestStorage and pass
                        explicitly.
                        
        Raises:
            ValueError: If request_ids is None and batch not in cache
        """
        batch = self.client.batches.get(name=batch_id)
        
        # Try passed request_ids first, then fall back to in-memory cache
        if request_ids is None:
            request_ids = self._request_ids_cache.get(batch_id, [])
        
        if not request_ids:
            raise ValueError(
                f"No request_ids found for batch {batch_id}. "
                "This batch may have been submitted in a different session. "
                "Load request_ids from batch_ids.json and pass them to get_results()."
            )
        
        results = []
        
        # Check for inline responses
        if batch.dest and batch.dest.inlined_responses:
            for i, inline_response in enumerate(batch.dest.inlined_responses):
                custom_id = request_ids[i] if i < len(request_ids) else f"request-{i}"
                
                if inline_response.response:
                    try:
                        text = inline_response.response.text
                        results.append(BatchResult(
                            custom_id=custom_id,
                            response_text=text,
                            success=True,
                            metadata={
                                "model": self.model_name,
                            }
                        ))
                    except AttributeError:
                        # Fallback if .text isn't available
                        results.append(BatchResult(
                            custom_id=custom_id,
                            response_text=str(inline_response.response),
                            success=True,
                            metadata={"model": self.model_name}
                        ))
                elif inline_response.error:
                    results.append(BatchResult(
                        custom_id=custom_id,
                        response_text="",
                        success=False,
                        error=str(inline_response.error),
                    ))
                else:
                    results.append(BatchResult(
                        custom_id=custom_id,
                        response_text="",
                        success=False,
                        error="No response or error in inline_response",
                    ))
        
        # Check for file-based results
        elif batch.dest and batch.dest.file_name:
            file_content = self.client.files.download(file=batch.dest.file_name)
            content = file_content.decode('utf-8')
            
            for i, line in enumerate(content.strip().split('\n')):
                if not line:
                    continue
                
                data = json.loads(line)
                custom_id = data.get('key', request_ids[i] if i < len(request_ids) else f"request-{i}")
                
                if 'response' in data and data['response']:
                    try:
                        text = data['response']['candidates'][0]['content']['parts'][0]['text']
                        results.append(BatchResult(
                            custom_id=custom_id,
                            response_text=text,
                            success=True,
                            metadata={"model": self.model_name}
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
            raise ValueError("No results found (neither file nor inline)")
        
        return results
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch."""
        try:
            self.client.batches.cancel(name=batch_id)
            return True
        except Exception:
            return False


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
        except Exception:
            return False


class BatchRunner:
    """
    High-level batch runner that handles submission, polling, and result collection.
    
    Usage:
        runner = BatchRunner(provider="openai", model_name="gpt-4o")
        batch_id = runner.submit(requests)
        results = runner.wait_for_completion(batch_id, check_interval=60)
        
    For Google batches, you must save request_ids after submission and pass
    them when retrieving results:
        
        batch_id = runner.submit(requests)
        request_ids = runner.get_submitted_request_ids(batch_id)  # Save this!
        # ... later ...
        results = runner.get_results(batch_id, request_ids=request_ids)
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
        """Submit batch and return batch ID.
        
        Args:
            requests: List of BatchRequest objects to submit
            json_mode: Whether to request JSON output format
            batch_metadata: Optional metadata about the batch, e.g.:
                - format: "abc", "humdrum", "mei", "musicxml"
                - num_measures: 1 or 8
                - question_range: "Q-001 to Q-100"
                
        Note: For Google batches, call get_submitted_request_ids() after this
              and save the result for later retrieval.
        """
        return self.api.submit_batch(requests, json_mode=json_mode, batch_metadata=batch_metadata)
    
    def get_submitted_request_ids(self, batch_id: str) -> List[str]:
        """
        Get the request_ids that were just submitted with a batch.
        
        This is REQUIRED for Google batches and should be called immediately
        after submit() to save the request order for later result alignment.
        
        For other providers, this returns an empty list (not needed).
        
        Args:
            batch_id: The batch ID returned from submit()
            
        Returns:
            List of custom_ids in submission order
        """
        if self.provider == "google":
            return self.api.get_submitted_request_ids(batch_id)
        return []
    
    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current batch status."""
        return self.api.get_status(batch_id)
    
    def get_results(
        self,
        batch_id: str,
        request_ids: Optional[List[str]] = None,
    ) -> List[BatchResult]:
        """Get batch results (for completed batches).
        
        Args:
            batch_id: The batch ID
            request_ids: For Google batches only - the list of custom_ids in
                        submission order. Required for batches from previous
                        sessions. Pass None for same-session batches or other
                        providers.
        """
        if self.provider == "google":
            return self.api.get_results(batch_id, request_ids=request_ids)
        return self.api.get_results(batch_id)
    
    def wait_for_completion(
        self,
        batch_id: str,
        check_interval: int = 60,
        max_wait_time: int = 3600,
        progress_callback: Optional[callable] = None,
        request_ids: Optional[List[str]] = None,
    ) -> List[BatchResult]:
        """
        Wait for batch to complete and return results.
        
        Args:
            batch_id: Batch ID to monitor
            check_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            progress_callback: Optional callback(status) for progress updates
            request_ids: For Google batches - the request_ids for alignment
            
        Returns:
            List of BatchResult objects
        """
        start_time = time.time()
        
        while True:
            status = self.get_status(batch_id)
            
            if progress_callback:
                progress_callback(status)
            
            if status.is_complete:
                if status.status == "completed":
                    return self.get_results(batch_id, request_ids=request_ids)
                else:
                    raise RuntimeError(f"Batch {status.status}: {status.failed_requests} failed")
            
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                raise TimeoutError(f"Batch did not complete within {max_wait_time}s")
            
            time.sleep(check_interval)
    
    def cancel(self, batch_id: str) -> bool:
        """Cancel a batch."""
        return self.api.cancel_batch(batch_id)
