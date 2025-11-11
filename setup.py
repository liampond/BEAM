"""Setup configuration for Music Encoding Benchmark."""

from setuptools import setup, find_packages  # type: ignore
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="music-encoding-benchmark",
    version="0.1.0",
    author="Liam Pond",
    description="A benchmark suite for evaluating LLM performance on music notation parsing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/liampond/MusicEncodingBenchmark",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "run-benchmark=cli.run_benchmark:main",
            "add-question=cli.add_question:main",
            "review-passage=cli.review_passage:main",
            "init-database=scripts.init_database:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.txt", "*.md"],
    },
)
