"""Publish artifacts. Writes `published.json`.

Actual deploy to GitHub Pages is handled by the bundled GitHub Actions workflow
(`.github/workflows/deploy.yml`), which takes the `site/` tree and pushes it to
the `gh-pages` branch. This module is responsible only for:
- choosing the correct artifact set for `publish.visibility`
- writing the publish manifest
- returning the URL list

For `visibility: private`, no upload is performed; the module returns local
paths and expects downstream workflows (signed-URL / auth-gated host) to take
over.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


def publish(
    *,
    run_id: str,
    site_root: Path,
    repo: str,
    visibility: str = "public",
    custom_domain: str = "",
) -> dict:
    run_dir = Path(site_root) / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run dir does not exist: {run_dir}")
    artifacts: list[dict] = []
    for p in sorted(run_dir.iterdir()):
        if p.is_file():
            artifacts.append(
                {"name": p.name, "size_bytes": p.stat().st_size, "path": str(p.relative_to(site_root))}
            )

    base_url = ""
    if visibility == "public":
        if custom_domain:
            base_url = f"https://{custom_domain.rstrip('/')}"
        elif "/" in repo:
            user, r = repo.split("/", 1)
            base_url = f"https://{user}.github.io/{r}"
        for a in artifacts:
            a["url"] = f"{base_url}/{a['path']}"
    else:
        for a in artifacts:
            a["url"] = f"file://{(site_root / a['path']).resolve()}"

    manifest = {
        "run_id": run_id,
        "visibility": visibility,
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat() + "Z",
        "repo": repo,
        "custom_domain": custom_domain,
        "artifacts": artifacts,
    }
    (run_dir / "published.json").write_text(json.dumps(manifest, indent=2))
    return manifest
