"""
Persistent storage for batch request mappings.

This module handles the storage and retrieval of request_ids for batch API
submissions, particularly for Google's Gemini API which returns inline responses
in order but without custom_ids.

The storage ensures that:
1. Request order is preserved and can be recovered across sessions
2. Batch metadata is tracked for debugging and verification
3. The mapping between batch_id and request_ids is always available

Storage format (JSON):
{
    "batch_id": {
        "request_ids": ["Q-001_P-001_musicxml", ...],
        "provider": "google",
        "model": "gemini-3-pro-preview",
        "format": "musicxml",
        "num_measures": 8,
        "created_at": "2025-12-05T12:00:00",
        "question_range": "Q-415 to Q-819",
        "count": 405
    }
}
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class BatchRequestMapping:
    """Metadata and request_ids for a single batch."""
    batch_id: str
    request_ids: List[str]
    provider: str
    model: str
    format: Optional[str] = None
    num_measures: Optional[int] = None
    question_range: Optional[str] = None
    created_at: Optional[str] = None
    count: Optional[int] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.count is None:
            self.count = len(self.request_ids)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, batch_id: str, data: Dict[str, Any]) -> "BatchRequestMapping":
        return cls(
            batch_id=batch_id,
            request_ids=data.get("request_ids", []),
            provider=data.get("provider", "unknown"),
            model=data.get("model", "unknown"),
            format=data.get("format"),
            num_measures=data.get("num_measures"),
            question_range=data.get("question_range"),
            created_at=data.get("created_at"),
            count=data.get("count"),
        )


class BatchRequestStorage:
    """
    Persistent storage for batch request mappings.
    
    This is critical for Google batch API which doesn't return custom_ids
    in responses - we must track the submission order to align results.
    
    Usage:
        storage = BatchRequestStorage("/path/to/output_dir")
        
        # On submission
        storage.save(batch_id, request_ids, provider="google", model="gemini-3-pro-preview")
        
        # On retrieval
        mapping = storage.load(batch_id)
        if mapping:
            request_ids = mapping.request_ids
    """
    
    FILENAME = "batch_request_mappings.json"
    
    def __init__(self, output_dir: Path):
        """
        Initialize storage with output directory.
        
        Args:
            output_dir: Directory where batch_request_mappings.json will be stored
        """
        self.output_dir = Path(output_dir)
        self.storage_path = self.output_dir / self.FILENAME
        self._cache: Dict[str, BatchRequestMapping] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load existing mappings from disk into cache."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                for batch_id, mapping_data in data.items():
                    self._cache[batch_id] = BatchRequestMapping.from_dict(batch_id, mapping_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load batch mappings from {self.storage_path}: {e}")
                self._cache = {}
    
    def _save_cache(self) -> None:
        """Persist cache to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        data = {
            batch_id: mapping.to_dict()
            for batch_id, mapping in self._cache.items()
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save(
        self,
        batch_id: str,
        request_ids: List[str],
        provider: str,
        model: str,
        format: Optional[str] = None,
        num_measures: Optional[int] = None,
        question_range: Optional[str] = None,
    ) -> BatchRequestMapping:
        """
        Save request_ids mapping for a batch.
        
        Args:
            batch_id: The batch ID from the API
            request_ids: Ordered list of custom_ids as submitted
            provider: API provider (e.g., "google")
            model: Model name (e.g., "gemini-3-pro-preview")
            format: Music format (abc, humdrum, mei, musicxml)
            num_measures: Number of measures (1 or 8)
            question_range: Human-readable range (e.g., "Q-415 to Q-819")
        
        Returns:
            The created BatchRequestMapping
        """
        mapping = BatchRequestMapping(
            batch_id=batch_id,
            request_ids=request_ids,
            provider=provider,
            model=model,
            format=format,
            num_measures=num_measures,
            question_range=question_range,
        )
        
        self._cache[batch_id] = mapping
        self._save_cache()
        
        return mapping
    
    def load(self, batch_id: str) -> Optional[BatchRequestMapping]:
        """
        Load request_ids mapping for a batch.
        
        Args:
            batch_id: The batch ID to look up
            
        Returns:
            BatchRequestMapping if found, None otherwise
        """
        return self._cache.get(batch_id)
    
    def get_request_ids(self, batch_id: str) -> Optional[List[str]]:
        """
        Get just the request_ids for a batch.
        
        Args:
            batch_id: The batch ID to look up
            
        Returns:
            List of request_ids if found, None otherwise
        """
        mapping = self.load(batch_id)
        return mapping.request_ids if mapping else None
    
    def exists(self, batch_id: str) -> bool:
        """Check if a mapping exists for the given batch_id."""
        return batch_id in self._cache
    
    def list_batches(self) -> List[str]:
        """List all stored batch IDs."""
        return list(self._cache.keys())
    
    def get_all(self) -> Dict[str, BatchRequestMapping]:
        """Get all stored mappings."""
        return dict(self._cache)
    
    def delete(self, batch_id: str) -> bool:
        """
        Delete a mapping.
        
        Returns:
            True if deleted, False if not found
        """
        if batch_id in self._cache:
            del self._cache[batch_id]
            self._save_cache()
            return True
        return False


def find_request_ids_for_batch(batch_id: str, search_dirs: Optional[List[Path]] = None) -> Optional[List[str]]:
    """
    Search for request_ids across multiple output directories.
    
    This is useful when retrieving results for batches submitted in previous
    sessions where we don't know which output directory was used.
    
    Args:
        batch_id: The batch ID to search for
        search_dirs: List of directories to search. If None, searches all
                    directories in ./outputs/
    
    Returns:
        List of request_ids if found, None otherwise
    """
    if search_dirs is None:
        outputs_dir = Path("outputs")
        if outputs_dir.exists():
            search_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
        else:
            search_dirs = []
    
    for dir_path in search_dirs:
        storage = BatchRequestStorage(dir_path)
        request_ids = storage.get_request_ids(batch_id)
        if request_ids:
            return request_ids
    
    # Also check legacy batch_ids.json files
    for dir_path in search_dirs:
        batch_ids_path = dir_path / "batch_ids.json"
        if batch_ids_path.exists():
            try:
                with open(batch_ids_path) as f:
                    data = json.load(f)
                for key, batch_info in data.items():
                    if batch_info.get("batch_id") == batch_id:
                        if "request_ids" in batch_info:
                            return batch_info["request_ids"]
            except (json.JSONDecodeError, IOError):
                continue
    
    return None
