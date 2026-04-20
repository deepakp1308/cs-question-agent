from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.orchestrator import run_pipeline


@pytest.mark.integration
def test_run_full_pipeline_end_to_end(example_input_dir: Path, tmp_path: Path):
    """Runs the full pipeline with the mock adapter on the generated sample paper.

    Asserts that the expected artifacts exist and the audit/published manifests
    are structured as specified.
    """
    result = run_pipeline(
        input_dir=example_input_dir,
        run_id="pytest-run",
        project_yaml=example_input_dir / "project.yaml",
        site_root=tmp_path / "site",
        repo_root=tmp_path,
        publish=True,
    )
    run_dir = Path(result["run_dir"])
    site_dir = Path(result["site_dir"])

    # Per-stage outputs are present and well-formed.
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "REPORT.md").exists()
    assert (run_dir / "stage_outputs" / "extract").exists()
    assert (run_dir / "stage_outputs" / "match").exists()
    assert (run_dir / "stage_outputs" / "answer").exists()
    assert (run_dir / "stage_outputs" / "judge_extraction").exists()
    assert (run_dir / "stage_outputs" / "judge_answer").exists()

    # Site artifacts.
    assert (site_dir / "index.html").exists()
    assert (site_dir / "audit.html").exists()
    # At least one chapter PDF produced.
    pdfs = list(site_dir.glob("chapter_*.pdf"))
    assert pdfs, f"no chapter PDFs generated in {site_dir}"

    # Publishing manifest
    published = json.loads((site_dir / "published.json").read_text())
    assert published["visibility"] in {"public", "private"}
    assert published["artifacts"], "published manifest must include artifacts"

    # At least some questions must land in auto_publish or gated_publish — the
    # mock-adapter pass rate is high enough that quarantine should not be 100%.
    summary = result["summary"]
    publishable = summary.get("auto_publish", 0) + summary.get("gated_publish", 0)
    assert publishable > 0, f"no publishable questions; summary={summary}"


@pytest.mark.integration
def test_resume_is_idempotent(example_input_dir: Path, tmp_path: Path):
    """Second run with the same inputs must reuse cached stage outputs."""
    kwargs = dict(
        input_dir=example_input_dir,
        run_id="resume-run",
        project_yaml=example_input_dir / "project.yaml",
        site_root=tmp_path / "site",
        repo_root=tmp_path,
        publish=False,
    )
    first = run_pipeline(**kwargs)
    metrics_first = json.loads((Path(first["run_dir"]) / "metrics.json").read_text())
    second = run_pipeline(**kwargs)
    metrics_second = json.loads((Path(second["run_dir"]) / "metrics.json").read_text())
    # Second run should have zero or near-zero additional cost and strictly fewer
    # or equal LLM calls because every cached stage is skipped.
    assert metrics_second["llm_calls"] <= metrics_first["llm_calls"]
