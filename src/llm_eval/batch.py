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
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
    ) -> str:
        """
        Submit batch of requests.
        
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
                body["response_format"] = {"type": "json_object"}
            
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
    """
    
    def __init__(self, model_name: str, max_tokens: int = 1024, temperature: float = 0.0):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def submit_batch(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
    ) -> str:
        """
        Submit batch of requests.
        
        Returns:
            batch_id for tracking
        """
        batch_requests = []
        
        for req in requests:
            # For Anthropic, enhance system prompt for JSON mode
            system = req.system_prompt or ""
            if json_mode and system:
                system = system + "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object."
            
            params = {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": req.prompt}],
            }
            
            if system:
                params["system"] = system
            
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


class BatchRunner:
    """
    High-level batch runner that handles submission, polling, and result collection.
    
    Usage:
        runner = BatchRunner(provider="openai", model_name="gpt-4o")
        batch_id = runner.submit(requests)
        results = runner.wait_for_completion(batch_id, check_interval=60)
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
        else:
            raise ValueError(f"Batch API not supported for provider: {provider}")
    
    def submit(
        self,
        requests: List[BatchRequest],
        json_mode: bool = True,
    ) -> str:
        """Submit batch and return batch ID."""
        return self.api.submit_batch(requests, json_mode=json_mode)
    
    def get_status(self, batch_id: str) -> BatchStatus:
        """Get current batch status."""
        return self.api.get_status(batch_id)
    
    def wait_for_completion(
        self,
        batch_id: str,
        check_interval: int = 60,
        max_wait_time: int = 3600,
        progress_callback: Optional[callable] = None,
    ) -> List[BatchResult]:
        """
        Wait for batch to complete and return results.
        
        Args:
            batch_id: Batch ID to monitor
            check_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            progress_callback: Optional callback(status) for progress updates
            
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
                    return self.api.get_results(batch_id)
                else:
                    raise RuntimeError(f"Batch {status.status}: {status.failed_requests} failed")
            
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                raise TimeoutError(f"Batch did not complete within {max_wait_time}s")
            
            time.sleep(check_interval)
    
    def cancel(self, batch_id: str) -> bool:
        """Cancel a batch."""
        return self.api.cancel_batch(batch_id)
