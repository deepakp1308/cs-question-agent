"""End-to-end resumable DAG orchestration."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from . import cache
from .adapters import build_adapter
from .answer import generate_answer, repair_answer
from .chapters import match_question, parse_selector_dir
from .config import ProjectConfig
from .extract import extract_paper
from .hashing import stable_json_hash
from .ingest import discover_inputs
from .judge import confidence_tier, judge_answer, judge_extraction, judge_match
from .logging import setup_logging
from .models import (
    AnswerRecord,
    ChapterMatch,
    ChapterSpec,
    JudgeResult,
    ModelsUsed,
    QuestionRecord,
    RunManifest,
)
from .publish import publish as publish_run
from .render import build_site
from .retrieval import build_store
from .telemetry import RunTelemetry

log = setup_logging()


class _TelemetryWrapper:
    """Records every LLM call into the run telemetry."""

    def __init__(self, inner, telemetry: RunTelemetry, stage: str) -> None:
        self._inner = inner
        self._telemetry = telemetry
        self._stage = stage
        self.model = getattr(inner, "model", "unknown")
        self.provider = getattr(inner, "provider", "unknown")

    def complete(self, **kwargs):
        resp = self._inner.complete(**kwargs)
        model_id = f"{self.provider}/{self.model}"
        self._telemetry.record_llm(
            stage=self._stage,
            model_id=model_id,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
        )
        return resp


def _wrap_with_telemetry(adapter, telemetry: RunTelemetry, stage: str):
    return _TelemetryWrapper(adapter, telemetry, stage)


def _read_prompt_manifest(prompts_dir: Path) -> dict[str, str]:
    manifest = prompts_dir / "manifest.yaml"
    if not manifest.exists():
        return {}
    import yaml

    return yaml.safe_load(manifest.read_text()) or {}


def _models_used(cfg: ProjectConfig) -> ModelsUsed:
    m = cfg.models
    return ModelsUsed(
        classifier=f"{m.classifier.provider}/{m.classifier.model}",
        generator=f"{m.generator.provider}/{m.generator.model}",
        judge=f"{m.judge.provider}/{m.judge.model}",
        embeddings=f"{m.embeddings.provider}/{m.embeddings.model}",
        reranker=f"{m.reranker.provider}/{m.reranker.model}",
    )


def _filters_match(q: QuestionRecord, chapter_assignment: str | None, only: dict[str, str]) -> bool:
    if not only:
        return True
    if only.get("question_id") and only["question_id"] != q.question_id:
        return False
    if only.get("paper") and only["paper"] != q.paper_id:
        return False
    if only.get("chapter") and only["chapter"] != (chapter_assignment or ""):
        return False
    return True


def run_pipeline(
    *,
    input_dir: str | Path,
    run_id: str | None = None,
    project_yaml: str | Path | None = None,
    site_root: str | Path = "site",
    repo_root: str | Path = ".",
    only: dict[str, str] | None = None,
    publish: bool = False,
) -> dict[str, Any]:
    from .config import load_project

    input_dir = Path(input_dir)
    project_yaml_path = Path(project_yaml) if project_yaml else input_dir / "project.yaml"
    cfg = load_project(project_yaml_path)
    run_id = run_id or _dt.datetime.now(_dt.UTC).strftime("%Y%m%d-%H%M%S")
    repo_root = Path(repo_root)
    run_dir = repo_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    site_root = repo_root / Path(site_root)
    only = only or {}

    telemetry = RunTelemetry(run_id=run_id, run_dir=run_dir, max_cost_usd=cfg.quality.max_run_cost_usd)
    _prompts_dir = repo_root / "prompts"
    _prompt_versions = _read_prompt_manifest(_prompts_dir)  # noqa: F841 — reserved for future per-record pinning
    models_used = _models_used(cfg)

    # 1) Ingest
    manifest: RunManifest = discover_inputs(input_dir, run_id)
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))

    # 2) Chapter selectors
    chapters: list[ChapterSpec] = parse_selector_dir(input_dir / "chapter_selectors")
    if not chapters:
        log.warning("no chapter selectors found under %s", input_dir / "chapter_selectors")

    # 3) Retrieval store
    store = build_store(
        chapter_sources_dir=input_dir / "chapter_sources",
        markschemes_dir=input_dir / "markschemes",
        chapters=[c.model_dump() for c in chapters],
        embeddings_model=cfg.models.embeddings,
    )

    # 4) Extract questions
    questions: list[QuestionRecord] = []
    for paper in manifest.papers:
        records = extract_paper(
            paper_id=paper.paper_id,
            source_file=paper.source_file,
            paper_hash=paper.file_hash,
        )
        for r in records:
            r.models_used = models_used
            cache.write_cached(
                run_dir,
                "extract",
                r.question_id,
                input_hash=paper.file_hash,
                data=r.model_dump(),
            )
        questions.extend(records)
    log.info("extracted %d questions", len(questions))

    # 5) Chapter match (+ match judge)
    classifier = _wrap_with_telemetry(
        build_adapter(cfg.models.classifier.provider, cfg.models.classifier.model),
        telemetry,
        stage="classifier",
    )
    judge_llm = _wrap_with_telemetry(
        build_adapter(cfg.models.judge.provider, cfg.models.judge.model),
        telemetry,
        stage="judge",
    )
    generator = _wrap_with_telemetry(
        build_adapter(cfg.models.generator.provider, cfg.models.generator.model),
        telemetry,
        stage="generator",
    )

    matches: dict[str, ChapterMatch] = {}
    match_judges: dict[str, JudgeResult] = {}
    for q in questions:
        if only and only.get("question_id") and only["question_id"] != q.question_id:
            continue
        if only and only.get("paper") and only["paper"] != q.paper_id:
            continue
        input_hash = stable_json_hash({"q": q.verbatim_text, "chapters": [c.chapter_id for c in chapters]})
        cached = cache.read_cached(run_dir, "match", q.question_id, input_hash)
        if cached:
            matches[q.question_id] = ChapterMatch(**cached)
        else:
            m = match_question(
                question=q,
                chapters=chapters,
                store=store,
                classifier=classifier,
            )
            m.models_used = models_used
            matches[q.question_id] = m
            cache.write_cached(run_dir, "match", q.question_id, input_hash, m.model_dump())
        # Match judge
        mj = judge_match(question=q, match=matches[q.question_id], chapters=chapters, judge_llm=judge_llm)
        match_judges[q.question_id] = mj
        telemetry.record_judge(stage="match", passed=mj.pass_)
        cache.write_cached(
            run_dir,
            "judge_match",
            q.question_id,
            input_hash,
            mj.model_dump(by_alias=True),
        )

    # 6) Extraction judge (Stage 1 deterministic; Stage 2 only when needed)
    extraction_judges: dict[str, JudgeResult] = {}
    for q in questions:
        res = judge_extraction(question=q, judge_llm=judge_llm)
        extraction_judges[q.question_id] = res
        telemetry.record_judge(stage="extraction", passed=res.pass_)
        cache.write_cached(
            run_dir,
            "judge_extraction",
            q.question_id,
            input_hash=q.verbatim_text[:120],
            data=res.model_dump(by_alias=True),
        )

    # 7) Answer + answer judge + repair
    answers: dict[str, AnswerRecord] = {}
    answer_judges: dict[str, JudgeResult] = {}
    for q in questions:
        assignment = matches.get(q.question_id).primary_chapter if q.question_id in matches else None
        if not _filters_match(q, assignment, only):
            continue
        if q.question_id not in matches:
            continue
        match = matches[q.question_id]

        # answer
        a_hash = stable_json_hash({"q": q.verbatim_text, "match": match.model_dump()})
        cached = cache.read_cached(run_dir, "answer", q.question_id, a_hash)
        if cached:
            ans = AnswerRecord(**cached)
        else:
            if telemetry.cost_exceeded():
                log.warning("cost cap reached; skipping answer for %s", q.question_id)
                break
            ans = generate_answer(
                question=q,
                match=match,
                store=store,
                generator=generator,
                quality=cfg.quality,
                teaching_style=cfg.teaching_style,
                ensemble=cfg.runtime.enable_ensemble,
            )
            ans.models_used = models_used
            cache.write_cached(run_dir, "answer", q.question_id, a_hash, ans.model_dump())
        answers[q.question_id] = ans

        # answer judge
        ch_ids = [c for c in [match.primary_chapter, *match.secondary_chapters] if c]
        hits = store.search(q.verbatim_text, k=6, chapter_ids=ch_ids)
        evidence_texts = [c.text for c, _ in hits if c.source_type == "textbook"]
        markscheme_texts = [c.text for c, _ in hits if c.source_type == "markscheme"]
        j = judge_answer(
            question=q,
            answer=ans,
            evidence_texts=evidence_texts,
            markscheme_texts=markscheme_texts,
            judge_llm=judge_llm,
        )
        answer_judges[q.question_id] = j
        telemetry.record_judge(stage="answer", passed=j.pass_)

        # repair loop
        attempts = 0
        while not j.pass_ and attempts < cfg.quality.max_repair_loops and not telemetry.cost_exceeded():
            attempts += 1
            ans = repair_answer(
                question=q,
                match=match,
                store=store,
                generator=generator,
                previous=ans,
                judge=j,
                quality=cfg.quality,
                teaching_style=cfg.teaching_style,
            )
            j = judge_answer(
                question=q,
                answer=ans,
                evidence_texts=evidence_texts,
                markscheme_texts=markscheme_texts,
                judge_llm=judge_llm,
            )
            answer_judges[q.question_id] = j
            telemetry.record_judge(stage="answer_repair", passed=j.pass_)
            cache.write_cached(run_dir, f"repair_{attempts}", q.question_id, a_hash, ans.model_dump())
        answers[q.question_id] = ans
        cache.write_cached(run_dir, "judge_answer", q.question_id, a_hash, j.model_dump(by_alias=True))

    # 8) Tiering
    assignments: dict[str, str | None] = {q.question_id: (matches[q.question_id].primary_chapter if q.question_id in matches else None) for q in questions}
    tiers: dict[str, str] = {}
    for q in questions:
        if q.question_id not in answers:
            tiers[q.question_id] = "quarantine"
            telemetry.record_tier("quarantine")
            continue
        tier, reasons = confidence_tier(
            answer=answers[q.question_id],
            extraction=extraction_judges[q.question_id],
            match=match_judges.get(q.question_id, JudgeResult(**{"pass": True}, score=1.0)),
            answer_judge_result=answer_judges.get(q.question_id, JudgeResult(**{"pass": True}, score=1.0)),
            quality=cfg.quality,
        )
        tiers[q.question_id] = tier
        telemetry.record_tier(tier)
        if tier == "quarantine":
            q_dir = run_dir / "quarantine"
            q_dir.mkdir(parents=True, exist_ok=True)
            (q_dir / f"{q.question_id}.json").write_text(
                json.dumps(
                    {
                        "question": q.model_dump(),
                        "answer": answers[q.question_id].model_dump(),
                        "reasons": reasons,
                        "extraction_judge": extraction_judges[q.question_id].model_dump(by_alias=True),
                        "answer_judge": answer_judges.get(q.question_id, JudgeResult(**{"pass": True}, score=1.0)).model_dump(by_alias=True),
                    },
                    indent=2,
                    default=str,
                )
            )

    # 9) Render site
    site_info = build_site(
        run_id=run_id,
        subject=cfg.subject,
        grade_level=cfg.grade_level,
        chapters=chapters,
        questions=questions,
        answers=answers,
        assignments=assignments,
        tiers=tiers,
        extraction_judges=extraction_judges,
        answer_judges=answer_judges,
        site_root=site_root,
    )

    # 10) Publish
    published = None
    if publish:
        published = publish_run(
            run_id=run_id,
            site_root=site_root,
            repo=cfg.publish.github_pages_repo,
            visibility=cfg.publish.visibility,
            custom_domain=cfg.publish.custom_domain,
        )

    # 11) Metrics + REPORT.md
    telemetry.write()
    _write_report(
        run_dir=run_dir,
        run_id=run_id,
        site_info=site_info,
        published=published,
        telemetry=telemetry,
        cfg=cfg,
    )

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "site_dir": site_info["run_dir"],
        "chapters": site_info["chapters"],
        "summary": site_info["summary"],
        "published": published,
    }


def _write_report(
    *,
    run_dir: Path,
    run_id: str,
    site_info: dict[str, Any],
    published: dict | None,
    telemetry: RunTelemetry,
    cfg: ProjectConfig,
) -> Path:
    lines: list[str] = []
    lines.append(f"# Run {run_id}")
    lines.append("")
    lines.append(f"- generated_at: {_dt.datetime.now(_dt.UTC).isoformat()}Z")
    lines.append(f"- cost_usd_total: {telemetry.total_cost:.4f} / cap {cfg.quality.max_run_cost_usd}")
    lines.append(f"- llm_calls: {telemetry.llm_calls}")
    lines.append("")
    lines.append("## Summary")
    for k, v in site_info["summary"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Chapters")
    for ch in site_info["chapters"]:
        lines.append(f"- {ch['chapter_id']}: {ch['title']} — {ch['question_count']} question(s)")
    lines.append("")
    lines.append("## Artifacts")
    if published:
        for a in published["artifacts"]:
            lines.append(f"- [{a['name']}]({a['url']})")
    else:
        lines.append(f"- local site: {site_info['run_dir']}")
    path = run_dir / "REPORT.md"
    path.write_text("\n".join(lines))
    return path
