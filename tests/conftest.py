from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def sample_paper_pdf() -> Path:
    target = ROOT / "example_input" / "papers" / "sample_paper.pdf"
    if not target.exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "make_sample_paper.py")])
    return target


@pytest.fixture
def example_input_dir(sample_paper_pdf: Path) -> Path:  # noqa: ARG001 — forces PDF generation
    return ROOT / "example_input"
