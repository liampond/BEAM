"""
Persistent storage for batch lifecycle state.

Single source of truth for the batch polling loop. For every submitted batch
we persist:
    - the submitted custom_ids (cross-checked against returned keys by
      validate_batch_results below)
    - submission metadata (provider, model, format, config_hash, submitted_at)
    - lifecycle_state (see STATES below)

All writes go through _atomic_write_json (tmp + os.replace) so a crash
mid-write cannot leave a truncated file. Raw provider results are persisted
to a separate JSON per batch (raw_results_<batch_id>.json) so a process
killed between "downloaded" and "saved" can resume without re-downloading.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from dataclasses import dataclass, asdict, field

from .batch import BatchResult


# Lifecycle states. A batch is eligible for polling until it reaches "saved".
STATES = ("submitted", "downloaded", "saved", "failed_stale")


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to tmp then rename. Never leaves a partial file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _safe_batch_id(batch_id: str) -> str:
    return batch_id.replace("/", "_").replace(":", "_")


def compute_config_hash(
    model: str,
    format: Optional[str],
    num_measures: Optional[Any],
    question_ids: Iterable[str],
) -> str:
    """Stable hash of the (model, format, num_measures, question_ids) tuple.

    Used by Phase 3 to detect drift between a submitted batch and the
    current config. Phase 2 just stores it.
    """
    payload = json.dumps(
        {
            "model": model,
            "format": format,
            "num_measures": num_measures,
            "question_ids": sorted(question_ids),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class BatchRequestMapping:
    """Metadata and lifecycle state for a single batch."""
    batch_id: str
    request_ids: List[str]
    provider: str
    model: str
    format: Optional[str] = None
    num_measures: Optional[Any] = None
    question_range: Optional[str] = None
    submitted_at: Optional[str] = None
    count: Optional[int] = None
    config_hash: Optional[str] = None
    run_number: Optional[int] = None
    lifecycle_state: str = "submitted"

    def __post_init__(self):
        if self.submitted_at is None:
            self.submitted_at = datetime.now().isoformat()
        if self.count is None:
            self.count = len(self.request_ids)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, batch_id: str, data: Dict[str, Any]) -> "BatchRequestMapping":
        submitted_at = data.get("submitted_at") or data.get("created_at")
        return cls(
            batch_id=batch_id,
            request_ids=data.get("request_ids", []),
            provider=data.get("provider", "unknown"),
            model=data.get("model", "unknown"),
            format=data.get("format"),
            num_measures=data.get("num_measures"),
            question_range=data.get("question_range"),
            submitted_at=submitted_at,
            count=data.get("count"),
            config_hash=data.get("config_hash"),
            run_number=data.get("run_number"),
            lifecycle_state=data.get("lifecycle_state", "submitted"),
        )


class BatchRequestStorage:
    """Atomic, file-backed storage of batch lifecycle state."""

    FILENAME = "batch_request_mappings.json"

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.storage_path = self.output_dir / self.FILENAME
        self._cache: Dict[str, BatchRequestMapping] = {}
        self._load_cache()

    def _load_cache(self) -> None:
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
        data = {
            batch_id: mapping.to_dict()
            for batch_id, mapping in self._cache.items()
        }
        _atomic_write_json(self.storage_path, data)

    def save(
        self,
        batch_id: str,
        request_ids: List[str],
        provider: str,
        model: str,
        format: Optional[str] = None,
        num_measures: Optional[Any] = None,
        question_range: Optional[str] = None,
        config_hash: Optional[str] = None,
        run_number: Optional[int] = None,
    ) -> BatchRequestMapping:
        """Record a new submission. lifecycle_state starts at "submitted"."""
        mapping = BatchRequestMapping(
            batch_id=batch_id,
            request_ids=request_ids,
            provider=provider,
            model=model,
            format=format,
            num_measures=num_measures,
            question_range=question_range,
            config_hash=config_hash,
            run_number=run_number,
            lifecycle_state="submitted",
        )
        self._cache[batch_id] = mapping
        self._save_cache()
        return mapping

    def load(self, batch_id: str) -> Optional[BatchRequestMapping]:
        return self._cache.get(batch_id)

    def get_request_ids(self, batch_id: str) -> Optional[List[str]]:
        mapping = self.load(batch_id)
        return mapping.request_ids if mapping else None

    def exists(self, batch_id: str) -> bool:
        return batch_id in self._cache

    def list_batches(self) -> List[str]:
        return list(self._cache.keys())

    def get_all(self) -> Dict[str, BatchRequestMapping]:
        return dict(self._cache)

    def get_resumable(self) -> Dict[str, BatchRequestMapping]:
        """All batches whose lifecycle_state is not a terminal state."""
        terminal = {"saved", "failed_stale"}
        return {bid: m for bid, m in self._cache.items() if m.lifecycle_state not in terminal}

    def update_lifecycle(self, batch_id: str, new_state: str) -> None:
        if new_state not in STATES:
            raise ValueError(f"Unknown lifecycle state: {new_state!r}. Valid: {STATES}")
        if batch_id not in self._cache:
            raise KeyError(f"Unknown batch_id: {batch_id}")
        self._cache[batch_id].lifecycle_state = new_state
        self._save_cache()

    def delete(self, batch_id: str) -> bool:
        if batch_id in self._cache:
            del self._cache[batch_id]
            self._save_cache()
            return True
        return False

    def _raw_results_path(self, batch_id: str) -> Path:
        return self.output_dir / f"raw_results_{_safe_batch_id(batch_id)}.json"

    def save_raw_results(self, batch_id: str, raw_results: List[BatchResult]) -> None:
        """Persist raw provider results so the save step can resume after a crash."""
        data = [
            {
                "custom_id": r.custom_id,
                "response_text": r.response_text,
                "success": r.success,
                "error": r.error,
                "metadata": r.metadata,
            }
            for r in raw_results
        ]
        _atomic_write_json(self._raw_results_path(batch_id), data)

    def load_raw_results(self, batch_id: str) -> Optional[List[BatchResult]]:
        path = self._raw_results_path(batch_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return [
            BatchResult(
                custom_id=d["custom_id"],
                response_text=d["response_text"],
                success=d["success"],
                error=d.get("error"),
                metadata=d.get("metadata", {}) or {},
            )
            for d in data
        ]


def find_request_ids_for_batch(batch_id: str, search_dirs: Optional[List[Path]] = None) -> Optional[List[str]]:
    """Search BatchRequestStorage across output directories for a batch_id."""
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
    return None


@dataclass
class ValidatedBatch:
    """Outcome of cross-checking batch results against submitted keys."""
    matched: List[BatchResult] = field(default_factory=list)
    missing: List[BatchResult] = field(default_factory=list)
    unexpected: List[str] = field(default_factory=list)


def validate_batch_results(
    results: List[BatchResult],
    expected_ids: Iterable[str],
    diagnostic_dir: Optional[Path] = None,
    batch_id: Optional[str] = None,
) -> ValidatedBatch:
    """Cross-check a batch's results against the set of submitted custom_ids.

    - Any expected id with no response becomes a synthetic
      ``BatchResult(success=False, error="no response from provider")``
      in both ``matched`` (so downstream save logic sees it) and ``missing``.
    - Any returned id not in the expected set is a hard error: we dump a
      diagnostic JSON next to the output dir and raise ``ValueError``.

    Callers MUST invoke this after every ``get_results`` call. It lives
    outside the API classes so that forgetting to pass ``expected_ids``
    fails loudly at call sites rather than silently skipping validation.
    """
    expected = set(expected_ids)
    by_id: Dict[str, BatchResult] = {}
    unexpected: List[str] = []

    for r in results:
        if r.custom_id in expected:
            by_id[r.custom_id] = r
        else:
            unexpected.append(r.custom_id)

    if unexpected:
        diag = {
            "batch_id": batch_id,
            "unexpected_keys": unexpected,
            "expected_keys": sorted(expected),
            "returned_keys": [r.custom_id for r in results],
        }
        target_dir = diagnostic_dir or Path.cwd()
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        suffix = _safe_batch_id(batch_id) if batch_id else "unknown"
        diag_path = target_dir / f"batch_validation_error_{suffix}_{stamp}.json"
        _atomic_write_json(diag_path, diag)
        raise ValueError(
            f"Batch returned {len(unexpected)} key(s) not in submitted set; "
            f"diagnostic written to {diag_path}"
        )

    matched: List[BatchResult] = []
    missing: List[BatchResult] = []
    for expected_id in expected:
        if expected_id in by_id:
            matched.append(by_id[expected_id])
        else:
            synth = BatchResult(
                custom_id=expected_id,
                response_text="",
                success=False,
                error="no response from provider",
            )
            matched.append(synth)
            missing.append(synth)

    return ValidatedBatch(matched=matched, missing=missing, unexpected=unexpected)
