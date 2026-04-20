"""Command-line interface."""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import click

from . import __version__
from .orchestrator import run_pipeline


def _parse_only(values: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in values:
        if "=" not in v:
            raise click.BadParameter(f"--only must be key=value (got {v!r})")
        k, val = v.split("=", 1)
        out[k.strip()] = val.strip()
    return out


@click.group()
@click.version_option(__version__, prog_name="cs-agent")
def cli() -> None:
    """Computer-science question-paper extraction and teaching agent."""


@cli.command("run")
@click.option("--input", "input_dir", type=click.Path(exists=True, file_okay=False), required=True)
@click.option("--run-id", default=None)
@click.option("--project", "project_yaml", type=click.Path(dir_okay=False), default=None)
@click.option("--site-root", type=click.Path(), default="site", show_default=True)
@click.option("--repo-root", type=click.Path(), default=".", show_default=True)
@click.option("--only", multiple=True, help="Filter: key=value. Repeatable. Keys: question_id, paper, chapter.")
@click.option("--publish/--no-publish", default=False, show_default=True)
def run(
    input_dir: str,
    run_id: str | None,
    project_yaml: str | None,
    site_root: str,
    repo_root: str,
    only: tuple[str, ...],
    publish: bool,
) -> None:
    """Run the full pipeline end-to-end."""
    result = run_pipeline(
        input_dir=input_dir,
        run_id=run_id or _dt.datetime.now(_dt.UTC).strftime("%Y%m%d-%H%M%S"),
        project_yaml=project_yaml,
        site_root=site_root,
        repo_root=repo_root,
        only=_parse_only(only),
        publish=publish,
    )
    click.echo(json.dumps(result, indent=2))


@cli.command("promote-golden")
@click.option("--run-id", required=True)
@click.option("--question-id", required=True)
@click.option("--repo-root", type=click.Path(), default=".", show_default=True)
def promote_golden(run_id: str, question_id: str, repo_root: str) -> None:
    """Promote a reviewer-approved record into tests/goldens/expected/."""
    src = Path(repo_root) / "runs" / run_id / "stage_outputs"
    dst_dir = Path(repo_root) / "tests" / "goldens" / "expected"
    dst_dir.mkdir(parents=True, exist_ok=True)
    bundle: dict = {}
    for stage in ("extract", "match", "answer", "judge_extraction", "judge_answer"):
        f = src / stage / f"{question_id}.json"
        if f.exists():
            bundle[stage] = json.loads(f.read_text())
    if not bundle:
        click.echo(f"no artifacts found for {question_id} in run {run_id}", err=True)
        sys.exit(2)
    out = dst_dir / f"{question_id}.json"
    out.write_text(json.dumps(bundle, indent=2, default=str))
    click.echo(f"promoted -> {out}")


if __name__ == "__main__":
    cli()
