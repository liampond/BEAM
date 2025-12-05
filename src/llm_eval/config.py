"""
Benchmark Configuration Management

Provides a flexible, hierarchical configuration system for the benchmark runner.
Supports filtering by format, passage length, question type, verification status, etc.

Design Principles:
    - Configuration is declarative (YAML-based)
    - All filters are optional (empty = all)
    - Easy to switch between dev/test/production modes
    - Extensible for future filter types
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import yaml
import os
from dotenv import load_dotenv


@dataclass
class FilterConfig:
    """
    Configuration for filtering test cases.
    
    All filters are optional. Empty list/None means "include all".
    Multiple values within a filter are OR'd together.
    Multiple filters are AND'd together.
    
    Examples:
        - formats: ["abc"] -> only ABC format
        - passages: ["P-001", "P-002"] -> only these passages
        - question_types: [1, 2, 3] -> only question types 1, 2, 3
        - verified_only: True -> only verified answers for the selected formats
        - num_measures: [1] -> only 1-bar passages
    """
    # Format filters
    formats: List[str] = field(default_factory=lambda: ["abc"])
    
    # Passage filters
    passages: Optional[List[str]] = None  # None = all passages
    num_measures: Optional[List[int]] = None  # e.g., [1] for 1-bar, [8] for 8-bar
    
    # Question filters
    question_ids: Optional[List[str]] = None  # e.g., ["Q-001", "Q-010"]
    question_types: Optional[List[int]] = None  # e.g., [1, 2, 3] for Q1, Q2, Q3
    
    # Verification filters
    verified_only: bool = True  # Only run questions with verified answers
    
    # Limit (for testing/debugging)
    limit: Optional[int] = None


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""
    provider: str  # anthropic, openai, google, alibaba-cloud, transformers, llama-stack
    name: str  # Model identifier (e.g., "claude-sonnet-4-5")
    enabled: bool = True
    
    # Per-model overrides (None = use global defaults)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    
    # Batch API settings
    use_batch_api: bool = False  # Use batch API if available
    
    # Additional model-specific params
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        """Filesystem-safe display name."""
        return self.name.replace("/", "_").replace(":", "_")


@dataclass
class APISettings:
    """Global API settings (can be overridden per-model)."""
    temperature: float = 0.0  # Deterministic by default
    seed: int = 42  # Reproducibility
    max_tokens: int = 16384  # Response length (high to avoid truncation)
    timeout: int = 300  # 5 minutes
    rate_limit_delay: float = 1.0  # Seconds between requests


@dataclass
class BatchSettings:
    """
    Batch API configuration for supported providers.
    
    Batch mode is enabled per-model via use_batch_api: true.
    These settings control batch behavior when enabled.
    """
    batch_size: int = 50  # Requests per batch
    check_interval: int = 60  # Seconds between status checks
    max_wait_time: int = 3600  # Maximum wait (1 hour)
    save_batch_ids: bool = True  # Save batch IDs for resumption


@dataclass 
class OutputConfig:
    """Output and storage configuration."""
    base_dir: str = "outputs"
    
    # Structure: {base_dir}/{run_id}/{model}/{format}/
    # run_id is auto-generated timestamp or custom name
    run_id: Optional[str] = None  # None = auto-generate
    
    # Resumption settings
    resume_run_id: Optional[str] = None  # Resume from existing run directory
    retry_failed: bool = True  # Retry tests that previously failed (success: false)
    
    # What to save
    save_prompts: bool = True
    save_responses: bool = True
    save_metadata: bool = True
    save_to_database: bool = True
    
    # Summary formats
    generate_csv_summary: bool = True
    generate_json_summary: bool = True


@dataclass
class PromptConfig:
    """Prompt construction settings."""
    system_prompt_file: str = "prompts/system_prompt.txt"
    include_format_hint: bool = True  # Add "[This is ABC format]" hint
    
    # JSON response enforcement
    enforce_json: bool = True  # Use API-level JSON mode where available


@dataclass
class ExecutionConfig:
    """Execution control settings."""
    # Number of runs per question (for consistency analysis)
    runs_per_question: int = 1
    
    # Concurrency (0 = sequential)
    concurrency: int = 0
    
    # Retry logic
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Progress reporting
    show_progress: bool = True
    verbose: bool = False
    
    # Dry run (validate without calling APIs)
    dry_run: bool = False


@dataclass
class BenchmarkConfig:
    """
    Master configuration for benchmark runs.
    
    Can be loaded from YAML file or constructed programmatically.
    """
    # Core components
    filters: FilterConfig = field(default_factory=FilterConfig)
    models: List[ModelConfig] = field(default_factory=list)
    api_settings: APISettings = field(default_factory=APISettings)
    batch_settings: BatchSettings = field(default_factory=BatchSettings)
    output: OutputConfig = field(default_factory=OutputConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    
    # Paths (resolved at load time)
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "BenchmarkConfig":
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            raw = yaml.safe_load(f)
        
        return cls.from_dict(raw, config_path.parent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_path: Optional[Path] = None) -> "BenchmarkConfig":
        """Construct from dictionary (e.g., parsed YAML)."""
        config = cls()
        
        if base_path:
            config.project_root = base_path
        
        # Parse filters
        if "filters" in data:
            f = data["filters"]
            config.filters = FilterConfig(
                formats=f.get("formats", ["abc"]),
                passages=f.get("passages"),
                num_measures=f.get("num_measures"),
                question_ids=f.get("question_ids"),
                question_types=f.get("question_types"),
                verified_only=f.get("verified_only", True),
                limit=f.get("limit"),
            )
        
        # Parse models
        if "models" in data:
            config.models = []
            for m in data["models"]:
                config.models.append(ModelConfig(
                    provider=m["provider"],
                    name=m["name"],
                    enabled=m.get("enabled", True),
                    temperature=m.get("temperature"),
                    max_tokens=m.get("max_tokens"),
                    timeout=m.get("timeout"),
                    use_batch_api=m.get("use_batch_api", False),
                    extra_params=m.get("extra_params", {}),
                ))
        
        # Parse API settings
        if "api_settings" in data:
            a = data["api_settings"]
            config.api_settings = APISettings(
                temperature=a.get("temperature", 0.0),
                seed=a.get("seed", 42),
                max_tokens=a.get("max_tokens", 1024),
                timeout=a.get("timeout", 300),
                rate_limit_delay=a.get("rate_limit_delay", 1.0),
            )
        
        # Parse batch settings
        if "batch_settings" in data:
            b = data["batch_settings"]
            config.batch_settings = BatchSettings(
                batch_size=b.get("batch_size", 50),
                check_interval=b.get("check_interval", 60),
                max_wait_time=b.get("max_wait_time", 3600),
                save_batch_ids=b.get("save_batch_ids", True),
            )
        
        # Parse output config
        if "output" in data:
            o = data["output"]
            config.output = OutputConfig(
                base_dir=o.get("base_dir", "outputs"),
                run_id=o.get("run_id"),
                resume_run_id=o.get("resume_run_id"),
                retry_failed=o.get("retry_failed", True),
                save_prompts=o.get("save_prompts", True),
                save_responses=o.get("save_responses", True),
                save_metadata=o.get("save_metadata", True),
                save_to_database=o.get("save_to_database", True),
                generate_csv_summary=o.get("generate_csv_summary", True),
                generate_json_summary=o.get("generate_json_summary", True),
            )
        
        # Parse prompt config
        if "prompt" in data:
            p = data["prompt"]
            config.prompt = PromptConfig(
                system_prompt_file=p.get("system_prompt_file", "prompts/system_prompt.txt"),
                include_format_hint=p.get("include_format_hint", True),
                enforce_json=p.get("enforce_json", True),
            )
        
        # Parse execution config
        if "execution" in data:
            e = data["execution"]
            config.execution = ExecutionConfig(
                runs_per_question=e.get("runs_per_question", 1),
                concurrency=e.get("concurrency", 0),
                retry_on_failure=e.get("retry_on_failure", True),
                max_retries=e.get("max_retries", 3),
                retry_delay=e.get("retry_delay", 5.0),
                show_progress=e.get("show_progress", True),
                verbose=e.get("verbose", False),
                dry_run=e.get("dry_run", False),
            )
        
        return config
    
    def get_enabled_models(self) -> List[ModelConfig]:
        """Get list of enabled models."""
        return [m for m in self.models if m.enabled]
    
    def get_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = self.project_root / self.prompt.system_prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found: {prompt_path}")
        return prompt_path.read_text().strip()
    
    def get_output_dir(self) -> Path:
        """Get output directory for this run."""
        from datetime import datetime
        # If resuming, use the resume_run_id
        if self.output.resume_run_id:
            return self.project_root / self.output.base_dir / self.output.resume_run_id
        run_id = self.output.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.project_root / self.output.base_dir / run_id
    
    def load_api_keys(self) -> Dict[str, Optional[str]]:
        """Load API keys from .env file and return mapping."""
        load_dotenv(self.project_root / ".env")
        
        keys = {
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
            'DASHSCOPE_API_KEY': os.getenv('DASHSCOPE_API_KEY'),
        }
        
        # Set in environment for libraries
        for key, value in keys.items():
            if value:
                os.environ[key] = value
        
        return keys
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.
        Returns empty list if valid.
        """
        issues = []
        
        # Check for enabled models
        if not self.get_enabled_models():
            issues.append("No models enabled")
        
        # Check format validity
        valid_formats = {"abc", "humdrum", "mei", "musicxml"}
        for fmt in self.filters.formats:
            if fmt.lower() not in valid_formats:
                issues.append(f"Unknown format: {fmt}")
        
        # Check system prompt file exists
        prompt_path = self.project_root / self.prompt.system_prompt_file
        if not prompt_path.exists():
            issues.append(f"System prompt file not found: {prompt_path}")
        
        return issues
    
    def summary(self) -> str:
        """Return human-readable configuration summary."""
        lines = [
            "=" * 60,
            "Benchmark Configuration Summary",
            "=" * 60,
            "",
            "Filters:",
            f"  Formats: {self.filters.formats}",
            f"  Verified only: {self.filters.verified_only}",
            f"  Passages: {self.filters.passages or 'all'}",
            f"  Question types: {self.filters.question_types or 'all'}",
            f"  Num measures: {self.filters.num_measures or 'all'}",
            f"  Limit: {self.filters.limit or 'none'}",
            "",
            "Models:",
        ]
        
        for m in self.get_enabled_models():
            batch_str = " [BATCH]" if m.use_batch_api else ""
            lines.append(f"  - {m.provider}/{m.name}{batch_str}")
        
        lines.extend([
            "",
            "API Settings:",
            f"  Temperature: {self.api_settings.temperature}",
            f"  Seed: {self.api_settings.seed}",
            f"  Max tokens: {self.api_settings.max_tokens}",
            "",
            "Execution:",
            f"  Runs per question: {self.execution.runs_per_question}",
            f"  Dry run: {self.execution.dry_run}",
            f"  Concurrency: {self.execution.concurrency}",
            f"  JSON enforcement: {self.prompt.enforce_json}",
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
