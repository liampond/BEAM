#!/usr/bin/env python3
"""Run gpt-5.4 sequentially for phase5_1bar (batch API is unsupported for this model)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_eval.config import BenchmarkConfig
from src.llm_eval.runner import BenchmarkRunner

config = BenchmarkConfig.from_yaml("config.yaml")
config.load_api_keys()

# Only run gpt-5.4; others are handled by submit_all_batches --poll-only
config.models = [m for m in config.models if m.name == "gpt-5.4" and m.enabled]
if not config.models:
    print("gpt-5.4 not found in config")
    sys.exit(1)

# run_id already set to phase5_1bar; resume_run_id lets it skip already-saved results
config.output.resume_run_id = config.output.run_id

print(f"Running {config.models[0].name} sequentially for {config.output.run_id}")
runner = BenchmarkRunner(config)
summary = runner.run()
print("Done:", summary)
