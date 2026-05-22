#!/usr/bin/env python3
"""
Run Music Encoding Benchmark

CLI for running LLM benchmarks on music encoding questions.

Usage:
    # Run with default config (benchmark_config.yaml)
    python -m src.llm_eval.run
    
    # Use custom config
    python -m src.llm_eval.run --config my_config.yaml
    
    # Quick test with limited cases
    python -m src.llm_eval.run --limit 5
    
    # Dry run (validate without API calls)
    python -m src.llm_eval.run --dry-run
    
    # Filter by format
    python -m src.llm_eval.run --formats abc humdrum
    
    # Filter by passage length
    python -m src.llm_eval.run --measures 1
    
    # Filter by question types
    python -m src.llm_eval.run --types 1 2 3
    
    # Run specific models only
    python -m src.llm_eval.run --models gpt-4o claude-sonnet-4-20250514
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.llm_eval.config import BenchmarkConfig
from src.llm_eval.runner import BenchmarkRunner
from src.llm_eval.query import TestCaseQuery


def main():
    parser = argparse.ArgumentParser(
        description="Run Music Encoding LLM Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all verified ABC questions
    python -m src.llm_eval.run
    
    # Quick test with 5 cases
    python -m src.llm_eval.run --limit 5
    
    # Test only 1-bar passages
    python -m src.llm_eval.run --measures 1
    
    # Test only question types 1, 2, 3
    python -m src.llm_eval.run --types 1 2 3
    
    # Dry run to see what would be tested
    python -m src.llm_eval.run --dry-run
        """
    )
    
    # Config file
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    # Filter overrides
    parser.add_argument(
        "--formats", "-f",
        nargs="+",
        choices=["abc", "humdrum", "mei", "musicxml"],
        help="Encoding formats to test"
    )
    parser.add_argument(
        "--measures", "-m",
        nargs="+",
        type=int,
        help="Filter by passage length (1 or 8)"
    )
    parser.add_argument(
        "--types", "-t",
        nargs="+",
        type=int,
        help="Question types to test (1-9)"
    )
    parser.add_argument(
        "--passages", "-p",
        nargs="+",
        help="Specific passage IDs (e.g., P-001 P-002)"
    )
    parser.add_argument(
        "--questions", "-q",
        nargs="+",
        help="Specific question IDs (e.g., Q-001 Q-010)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of test cases"
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include unverified questions"
    )
    
    # Model overrides
    parser.add_argument(
        "--models",
        nargs="+",
        help="Specific model names to test"
    )
    
    # Execution options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without calling APIs"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use batch API for supported providers"
    )
    
    # Info commands
    parser.add_argument(
        "--show-summary",
        action="store_true",
        help="Show test case summary and exit"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Create benchmark_config.yaml or specify --config path")
        sys.exit(1)
    
    print(f"Loading config: {config_path}")
    config = BenchmarkConfig.from_yaml(config_path)
    
    # Apply CLI overrides
    if args.formats:
        config.filters.formats = args.formats
    if args.measures:
        config.filters.num_measures = args.measures
    if args.types:
        config.filters.question_types = args.types
    if args.passages:
        config.filters.passages = args.passages
    if args.questions:
        config.filters.question_ids = args.questions
    if args.limit:
        config.filters.limit = args.limit
    if args.include_unverified:
        config.filters.verified_only = False
    if args.dry_run:
        config.execution.dry_run = True
    if args.verbose:
        config.execution.verbose = True
    if args.batch:
        # Enable batch API for supported providers
        for m in config.models:
            if m.provider in ("openai", "anthropic"):
                m.use_batch_api = True
    
    # Filter models if specified
    if args.models:
        for m in config.models:
            m.enabled = m.name in args.models
    
    # Show summary and exit
    if args.show_summary:
        query = TestCaseQuery(config)
        summary = query.get_summary()
        print("\nTest Case Summary:")
        print(f"  Total: {summary['total']}")
        print(f"  By format: {summary['by_format']}")
        print(f"  By question type: {summary['by_question_type']}")
        print(f"  By num measures: {summary['by_num_measures']}")
        print(f"  Verified: {summary['verified_count']}")
        return
    
    # Validate
    issues = config.validate()
    if issues:
        print("Configuration issues:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    
    # Show what we're about to do
    print(config.summary())
    
    # Run benchmark
    runner = BenchmarkRunner(config)
    summary = runner.run()
    
    # Print final summary
    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    
    if "dry_run" in summary:
        print(f"Dry run: {summary['test_cases']} test cases would be run")
    else:
        for model_name, stats in summary.get("models", {}).items():
            accuracy = stats["accuracy"] * 100
            print(f"{model_name}: {stats['correct']}/{stats['total']} ({accuracy:.1f}%)")


if __name__ == "__main__":
    main()
